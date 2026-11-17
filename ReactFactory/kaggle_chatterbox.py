import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from kaggle_lipsync import (
    _dump_kernel_error_log,
    _load_kaggle_env,
    _run_kaggle,
    _wait_dataset_ready,
)
from voice_and_avatar import _call_edge_tts, _master_voice_wav, normalize_ptbr_phonetics

BASE_DIR = Path(__file__).resolve().parent
WORKER_DIR = BASE_DIR / "kaggle_worker_tts"
DATASET_SLUG = "reactfactory-gta-tts-input"


def run_batch_chatterbox_kaggle(chunks, out_dir, ref_audio_path=None, timeout_sec=1200):
    """
    Sintetiza todos os blocos de narração do vídeo longo em batch único na GPU T4 do Kaggle
    usando ChatterboxMultilingualTTS (voz humana PT-BR contínua e padronizada).
    Fallback seguro: Edge-TTS uniforme masterizado caso Kaggle falhe.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if ref_audio_path is None:
        ref_audio_path = BASE_DIR / "assets" / "voice_ref_ptbr.wav"
    else:
        ref_audio_path = Path(ref_audio_path)

    if not ref_audio_path.exists():
        raise FileNotFoundError(f"Referência vocal não encontrada: {ref_audio_path}")

    env = _load_kaggle_env()
    username = env["KAGGLE_USERNAME"]
    dataset_ref = f"{username}/{DATASET_SLUG}"
    run_id = str(int(time.time()))
    kernel_ref = f"{username}/reactfactory-tts-{run_id}"

    manifest_chunks = []
    for ch in chunks:
        manifest_chunks.append({
            "id": ch["id"],
            "text": normalize_ptbr_phonetics(ch["text"])[:295],
            "output": f"raw_{ch['id']}.wav",
            "exaggeration": ch.get("exaggeration", 0.56),
            "cfg_weight": ch.get("cfg_weight", 0.5),
            "temperature": ch.get("temperature", 0.65),
        })

    try:
        with tempfile.TemporaryDirectory(prefix="rf_cb_") as tmp:
            tmp_path = Path(tmp)
            ds_dir = tmp_path / "dataset"
            kn_dir = tmp_path / "kernel"
            ds_dir.mkdir()
            kn_dir.mkdir()

            ref_name = f"ref_{run_id}.wav"
            shutil.copy2(ref_audio_path, ds_dir / ref_name)
            (ds_dir / "manifest.json").write_text(
                json.dumps({"run_id": run_id, "ref_audio": ref_name, "seed": 42, "chunks": manifest_chunks}, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            (ds_dir / "dataset-metadata.json").write_text(
                json.dumps({"title": "ReactFactory GTA TTS Input", "id": dataset_ref, "licenses": [{"name": "CC0-1.0"}]}, indent=2),
                encoding="utf-8",
            )

            rc, out = _run_kaggle(["datasets", "version", "-p", str(ds_dir), "-m", f"tts-{run_id}", "--dir-mode", "zip"], env, check=False)
            print(f"[KAGGLE TTS] Dataset version (rc={rc}): {out}")
            if rc != 0 or "404" in out or "not found" in out.lower() or "error" in out.lower():
                _run_kaggle(["datasets", "create", "-p", str(ds_dir), "--dir-mode", "zip"], env, check=True)

            _wait_dataset_ready(dataset_ref, env, expected_filename=ref_name, timeout_sec=150)
            time.sleep(6)

            shutil.copy2(WORKER_DIR / "chatterbox_worker.py", kn_dir / "chatterbox_worker.py")
            meta_obj = json.loads((WORKER_DIR / "kernel-metadata.json").read_text(encoding="utf-8"))
            meta_obj["id"] = kernel_ref
            meta_obj["title"] = f"ReactFactory TTS {run_id}"
            meta_obj["dataset_sources"] = [dataset_ref]
            (kn_dir / "kernel-metadata.json").write_text(json.dumps(meta_obj, indent=2), encoding="utf-8")

            print(f"[KAGGLE TTS] Disparando kernel {kernel_ref} ({len(chunks)} falas)...")
            _, push_out = _run_kaggle(["kernels", "push", "-p", str(kn_dir)], env, check=True)
            print(f"[KAGGLE TTS] {push_out}")

            deadline = time.time() + timeout_sec
            while time.time() < deadline:
                time.sleep(20)
                rc_st, st_out = _run_kaggle(["kernels", "status", kernel_ref], env, check=False)
                low = st_out.lower()
                print(f"[KAGGLE TTS] Status: {st_out}")
                if rc_st != 0 or "connecttimeouterror" in low or "max retries exceeded" in low or "connectionerror" in low:
                    continue
                if "kernelworkerstatus.complete" in low or '"complete"' in low:
                    break
                if "kernelworkerstatus.error" in low or "kernelworkerstatus.cancel" in low:
                    _dump_kernel_error_log(kernel_ref, env)
                    raise RuntimeError(f"Kernel Kaggle TTS falhou: {st_out}")
            else:
                raise TimeoutError(f"Kernel Kaggle TTS excedeu {timeout_sec}s.")

            dl_dir = tmp_path / "dl_out"
            dl_dir.mkdir()
            _run_kaggle(["kernels", "output", kernel_ref, "-p", str(dl_dir)], env, check=True)

            status_path = dl_dir / "status.json"
            if not status_path.exists():
                raise RuntimeError("status.json não retornado pelo Kaggle TTS.")
            st_data = json.loads(status_path.read_text(encoding="utf-8"))
            if str(st_data.get("run_id")) != str(run_id):
                raise RuntimeError("run_id antigo retornado pelo Kaggle TTS.")

            outputs = {}
            for ch in chunks:
                cid = ch["id"]
                src_p = dl_dir / f"raw_{cid}.wav"
                dst_p = Path(ch["output_wav"])
                _master_voice_wav(str(src_p), str(dst_p))
                outputs[cid] = str(dst_p)
            print(f"[KAGGLE TTS] {len(outputs)} narrações Chatterbox PT-BR masterizadas com sucesso!")
            return outputs, "chatterbox_kaggle"
    except Exception as err:
        print(f"[KAGGLE TTS] Aviso ({err}) — aplicando Edge-TTS uniforme em 100% do vídeo para manter consistência...")
        outputs = {}
        for ch in chunks:
            dst_p = Path(ch["output_wav"])
            mp3_tmp = str(dst_p) + ".mp3"
            _call_edge_tts(ch["text"], mp3_tmp, rate="+5%")
            _master_voice_wav(mp3_tmp, str(dst_p))
            if os.path.exists(mp3_tmp):
                os.remove(mp3_tmp)
            outputs[ch["id"]] = str(dst_p)
        return outputs, "edge_fallback"
