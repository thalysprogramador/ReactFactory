import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent
WORKER_DIR = BASE_DIR / "kaggle_worker"
DATASET_SLUG = "reactfactory-lipsync-input"
KERNEL_SLUG = "reactfactory-latentsync-t4"
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def _load_kaggle_env():
    env = os.environ.copy()
    if env.get("KAGGLE_USERNAME") and (env.get("KAGGLE_KEY") or env.get("KAGGLE_API_TOKEN")):
        return env

    local_json = BASE_DIR.parent / "_render_secrets" / "kaggle.json"
    if local_json.exists():
        data = json.loads(local_json.read_text(encoding="utf-8"))
        if data.get("username"):
            env["KAGGLE_USERNAME"] = data["username"]
        if data.get("key"):
            env["KAGGLE_KEY"] = data["key"]
        if data.get("api_token"):
            env["KAGGLE_API_TOKEN"] = data["api_token"]

    if env.get("KAGGLE_API_TOKEN") and not env.get("KAGGLE_USERNAME"):
        try:
            from kaggle.api.kaggle_api_extended import KaggleApi
            api = KaggleApi()
            api.authenticate()
            uname = api.config_values.get("username")
            if uname:
                env["KAGGLE_USERNAME"] = uname
        except Exception:
            pass

    if env.get("KAGGLE_USERNAME") and (env.get("KAGGLE_KEY") or env.get("KAGGLE_API_TOKEN")):
        return env

    raise RuntimeError(
        "Credenciais do Kaggle ausentes. Defina KAGGLE_USERNAME e KAGGLE_KEY "
        "(ou KAGGLE_API_TOKEN), ou salve _render_secrets/kaggle.json."
    )


def _run_kaggle(args, env, check=True):
    cmd = [sys.executable, "-m", "kaggle.cli"] + args
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    out = ((res.stdout or "") + "\n" + (res.stderr or "")).strip()
    if check and res.returncode != 0:
        raise RuntimeError(f"Erro Kaggle CLI ({' '.join(cmd)}): {out}")
    return res.returncode, out


def _wait_dataset_ready(dataset_ref, env, expected_filename, timeout_sec=150):
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        rc, out = _run_kaggle(["datasets", "status", dataset_ref], env, check=False)
        low = out.lower()
        print(f"[KAGGLE] Dataset status: {out}")
        if rc == 0 and "ready" in low:
            _, files_out = _run_kaggle(["datasets", "files", dataset_ref], env, check=False)
            if expected_filename in files_out:
                print(f"[KAGGLE] Dataset atualizado confirmado ({expected_filename})!")
                return
            print(f"[KAGGLE] Aguardando nova versão propagar ({expected_filename})...")
        elif "error" in low:
            raise RuntimeError(f"Dataset Kaggle falhou: {out}")
        time.sleep(6)
    raise TimeoutError(f"Dataset Kaggle {dataset_ref} não propagou {expected_filename} em {timeout_sec}s.")


def _prepare_video_for_latentsync(src_vid, dst_vid, max_sec=8.0):
    """Converte o clipe de fala para 1280x720 @ 25fps (LatentSync 1.5 nativo) e limita duração."""
    cmd = [
        FFMPEG_EXE, "-y", "-i", str(src_vid),
        "-t", str(max_sec),
        "-vf", "scale=1280:720:flags=lanczos",
        "-r", "25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "16",
        "-an",
        str(dst_vid),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _dump_kernel_error_log(kernel_ref, env):
    try:
        with tempfile.TemporaryDirectory(prefix="rf_kerr_") as err_dir:
            _run_kaggle(["kernels", "output", kernel_ref, "-p", err_dir], env, check=False)
            for logf in Path(err_dir).glob("*.log"):
                txt = logf.read_text(encoding="utf-8", errors="replace")
                print(f"[KAGGLE LOG {logf.name}]:\n{txt[-3000:]}")
    except Exception as e:
        print(f"[KAGGLE] Não foi possível baixar log de erro: {e}")


def run_batch_lipsync_kaggle(jobs, out_dir, timeout_sec=1200, max_video_sec=8.0):
    """
    Executa LatentSync v1.5 em lote na GPU T4 gratuita do Kaggle.
    """
    env = _load_kaggle_env()
    username = env["KAGGLE_USERNAME"]
    dataset_ref = f"{username}/{DATASET_SLUG}"
    run_id = str(int(time.time()))
    # Slug único por execução evita bug do Kaggle de travar reenvios no mesmo slug em QUEUED
    dynamic_slug = f"reactfactory-ls-{run_id}"
    kernel_ref = f"{username}/{dynamic_slug}"
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rf_kaggle_") as tmp:
        tmp_path = Path(tmp)
        ds_dir = tmp_path / "dataset"
        kn_dir = tmp_path / "kernel"
        ds_dir.mkdir()
        kn_dir.mkdir()

        manifest_jobs = []
        copied_videos = {}
        first_aud_name = None
        for job in jobs:
            src_vid = Path(job["video_path"]).resolve()
            if str(src_vid) not in copied_videos:
                dst_vid_name = f"vid_{len(copied_videos)}_{src_vid.stem}_25fps.mp4"
                _prepare_video_for_latentsync(src_vid, ds_dir / dst_vid_name, max_sec=max_video_sec)
                copied_videos[str(src_vid)] = dst_vid_name

            src_aud = Path(job["audio_path"]).resolve()
            dst_aud_name = f"aud_{run_id}_{job['name']}{src_aud.suffix}"
            if first_aud_name is None:
                first_aud_name = dst_aud_name
            shutil.copy2(src_aud, ds_dir / dst_aud_name)

            manifest_jobs.append({
                "name": job["name"],
                "video": copied_videos[str(src_vid)],
                "audio": dst_aud_name,
                "output": job["output_name"],
                "guidance_scale": job.get("guidance_scale", 1.5),
                "inference_steps": job.get("inference_steps", 20),
            })

        (ds_dir / "manifest.json").write_text(
            json.dumps({"run_id": run_id, "jobs": manifest_jobs}, indent=2), encoding="utf-8"
        )
        ds_meta = {
            "title": "ReactFactory LipSync Input",
            "id": dataset_ref,
            "licenses": [{"name": "CC0-1.0"}],
        }
        (ds_dir / "dataset-metadata.json").write_text(
            json.dumps(ds_meta, indent=2), encoding="utf-8"
        )

        # Tenta atualizar versão EXISTENTE primeiro (Kaggle CLI 2.x pode retornar rc=0 mesmo quando create falha!)
        rc, out = _run_kaggle(
            ["datasets", "version", "-p", str(ds_dir), "-m", f"run-{run_id}", "--dir-mode", "zip"],
            env,
            check=False,
        )
        print(f"[KAGGLE] Dataset version output (rc={rc}): {out}")
        if rc != 0 or "404" in out or "not found" in out.lower() or "error" in out.lower():
            print(f"[KAGGLE] Dataset ainda não existe ou falhou version, criando {dataset_ref}...")
            rc2, out2 = _run_kaggle(["datasets", "create", "-p", str(ds_dir), "--dir-mode", "zip"], env, check=True)
            print(f"[KAGGLE] Dataset create output: {out2}")

        _wait_dataset_ready(dataset_ref, env, expected_filename=first_aud_name, timeout_sec=150)
        time.sleep(8)

        shutil.copy2(WORKER_DIR / "latentsync_worker.py", kn_dir / "latentsync_worker.py")
        meta_obj = json.loads((WORKER_DIR / "kernel-metadata.json").read_text(encoding="utf-8"))
        meta_obj["id"] = kernel_ref
        meta_obj["title"] = f"ReactFactory LS {run_id}"
        meta_obj["dataset_sources"] = [dataset_ref]
        (kn_dir / "kernel-metadata.json").write_text(json.dumps(meta_obj, indent=2), encoding="utf-8")

        print(f"[KAGGLE] Disparando kernel {kernel_ref} (GPU T4, run_id={run_id})...")
        _, push_out = _run_kaggle(["kernels", "push", "-p", str(kn_dir)], env, check=True)
        print(f"[KAGGLE] {push_out}")

        deadline = time.time() + timeout_sec
        denied_count = 0
        queued_count = 0
        while time.time() < deadline:
            time.sleep(20)
            rc_st, st_out = _run_kaggle(["kernels", "status", kernel_ref], env, check=False)
            low = st_out.lower()
            print(f"[KAGGLE] Status: {st_out}")
            if "permission 'kernels.get' was denied" in low:
                denied_count += 1
                if denied_count >= 5:
                    raise RuntimeError(f"Sem acesso ao kernel {kernel_ref}: {st_out}")
                continue
            if rc_st != 0 or "connecttimeouterror" in low or "max retries exceeded" in low or "connectionerror" in low:
                # Erro transitório de rede ao consultar status: tenta novamente no próximo ciclo
                continue
            if "kernelworkerstatus.queued" in low or '"queued"' in low:
                queued_count += 1
                if queued_count >= 6:
                    raise TimeoutError("Fila GPU Kaggle congestionada (QUEUED > 120s) — acionando fallback rápido.")
                continue
            if "kernelworkerstatus.complete" in low or '"complete"' in low:
                break
            if "kernelworkerstatus.error" in low or "kernelworkerstatus.cancel" in low:
                _dump_kernel_error_log(kernel_ref, env)
                raise RuntimeError(f"Kernel Kaggle falhou: {st_out}")
        else:
            raise TimeoutError(f"Kernel Kaggle excedeu {timeout_sec}s.")

        # Baixa em subpasta limpa e valida run_id para nunca usar cache velho!
        dl_dir = tmp_path / "dl_out"
        dl_dir.mkdir()
        _run_kaggle(["kernels", "output", kernel_ref, "-p", str(dl_dir)], env, check=True)

        status_path = dl_dir / "status.json"
        if not status_path.exists():
            raise RuntimeError("status.json não foi retornado pelo Kaggle.")
        st_data = json.loads(status_path.read_text(encoding="utf-8"))
        if str(st_data.get("run_id")) != str(run_id):
            raise RuntimeError(
                f"Kaggle retornou run_id antigo ({st_data.get('run_id')} != esperado {run_id})! Abortando."
            )

        shutil.copy2(status_path, out_dir / "status.json")
        outputs = {}
        for job in jobs:
            src_p = dl_dir / job["output_name"]
            dst_p = out_dir / job["output_name"]
            if not src_p.exists() or src_p.stat().st_size < 5000:
                raise RuntimeError(f"Saída LatentSync ausente/vazia: {src_p}")
            shutil.copy2(src_p, dst_p)
            subprocess.run(
                [FFMPEG_EXE, "-y", "-i", str(dst_p), "-ar", "24000", "-ac", "1", str(job["audio_path"])],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            outputs[job["name"]] = str(dst_p)
        return outputs
