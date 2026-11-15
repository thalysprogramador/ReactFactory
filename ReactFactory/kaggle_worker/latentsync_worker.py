import json
import os
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

WORK_DIR = Path("/kaggle/working")
REPO_DIR = Path("/tmp/LatentSync")
VENV_DIR = Path("/tmp/ls_venv")
INPUT_ROOT = Path("/kaggle/input")


def run(cmd, cwd=None, check=True):
    print(f"[CMD] {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    res = subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {cmd}")
    return res.returncode


def find_input_dir():
    print(f"[INPUT] Scanning {INPUT_ROOT}...", flush=True)
    for p in INPUT_ROOT.rglob("manifest.json"):
        print(f"[INPUT] Found manifest at {p}", flush=True)
        return p.parent
    entries = [str(p) for p in list(INPUT_ROOT.rglob("*"))[:50]]
    raise FileNotFoundError(f"manifest.json not found under {INPUT_ROOT}. Found: {entries}")


def get_wav_duration(wav_path):
    try:
        with wave.open(str(wav_path), "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 4.5


def trim_video_for_job(src_vid, dst_vid, start_sec, dur_sec):
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_sec:.2f}",
        "-i", str(src_vid),
        "-t", f"{dur_sec:.2f}",
        "-vf", "scale=1280:720:flags=lanczos",
        "-r", "25",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "16",
        "-an",
        str(dst_vid),
    ]
    run(cmd)


def setup_latentsync():
    run("nvidia-smi", check=False)
    if shutil.which("ffmpeg") is None:
        run("apt-get update -qq && apt-get install -y -qq ffmpeg libgl1 libglib2.0-0", check=False)

    if not REPO_DIR.exists():
        run(["git", "clone", "--depth", "1", "https://github.com/bytedance/LatentSync.git", str(REPO_DIR)])

    if not (VENV_DIR / "bin" / "python").exists():
        run([sys.executable, "-m", "pip", "install", "-q", "uv"])
        uv_bin = shutil.which("uv") or "uv"
        run([uv_bin, "venv", str(VENV_DIR), "--python", "3.10"])
        vpy = str(VENV_DIR / "bin" / "python")
        run([
            uv_bin, "pip", "install", "--python", vpy, "-q",
            "torch==2.5.1", "torchvision==0.20.1", "torchaudio==2.5.1",
            "--index-url", "https://download.pytorch.org/whl/cu121",
        ])

        # Filtra requirements.txt do LatentSync para não sobrescrever torch cu121
        req_file = REPO_DIR / "requirements.txt"
        filtered_reqs = []
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#") or s.startswith("--"):
                    continue
                low = s.lower()
                if low.startswith("torch==") or low.startswith("torchvision==") or low.startswith("torchaudio=="):
                    continue
                filtered_reqs.append(s)
        filtered_req_path = Path("/tmp/ls_filtered_reqs.txt")
        filtered_req_path.write_text("\n".join(filtered_reqs) + "\n", encoding="utf-8")
        run([uv_bin, "pip", "install", "--python", vpy, "-q", "-r", str(filtered_req_path)], check=False)

        run([
            uv_bin, "pip", "install", "--python", vpy, "-q",
            "DeepCache", "diffusers==0.32.2", "transformers==4.48.0", "huggingface-hub==0.25.2",
            "accelerate==0.34.2", "einops==0.8.0", "omegaconf==2.3.0", "safetensors==0.4.5",
            "opencv-python-headless==4.10.0.84", "mediapipe==0.10.14",
            "insightface==0.7.3", "onnxruntime-gpu==1.19.2",
            "librosa==0.10.2.post1", "soundfile==0.12.1", "scenedetect==0.6.4",
            "ffmpeg-python==0.2.0", "imageio==2.36.0", "imageio-ffmpeg==0.5.1",
            "av==13.1.0", "kornia==0.7.3", "face-alignment==1.4.1",
            "python_speech_features==0.6", "decord==0.6.0", "numpy==1.26.4",
            "scipy==1.13.1", "pillow==10.4.0", "tqdm"
        ])

    vpy = str(VENV_DIR / "bin" / "python")
    ckpt_dir = REPO_DIR / "checkpoints"
    if not (ckpt_dir / "latentsync_unet.pt").exists():
        print("[HF] Downloading ByteDance/LatentSync-1.5 checkpoints...", flush=True)
        dl_code = (
            "from huggingface_hub import snapshot_download; "
            f"snapshot_download(repo_id='ByteDance/LatentSync-1.5', local_dir={repr(str(ckpt_dir))}, local_dir_use_symlinks=False)"
        )
        run([vpy, "-c", dl_code])
    return vpy


def pick_unet_config():
    for candidate in [
        REPO_DIR / "configs" / "unet" / "stage2.yaml",
        REPO_DIR / "configs" / "unet" / "stage2_efficient.yaml",
    ]:
        if candidate.exists():
            return str(candidate.relative_to(REPO_DIR))
    raise FileNotFoundError("No stage2 unet config found in LatentSync/configs/unet")


def main():
    t0 = time.time()
    input_dir = find_input_dir()
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    print(f"[INPUT] Loaded manifest from {input_dir}: {manifest}", flush=True)

    vpy = setup_latentsync()
    unet_cfg = pick_unet_config()
    ckpt_path = "checkpoints/latentsync_unet.pt"
    inf_src = (REPO_DIR / "scripts" / "inference.py").read_text(encoding="utf-8", errors="ignore")
    has_deepcache_flag = "--enable_deepcache" in inf_src
    print(f"[CFG] Using unet_config={unet_cfg}, deepcache_flag={has_deepcache_flag}", flush=True)

    offsets = {"hook": 0.0, "inter": 3.5, "outro": 7.0}
    results = {}
    for idx, job in enumerate(manifest.get("jobs", [])):
        name = job["name"]
        vid_in = input_dir / job["video"]
        aud_in = input_dir / job["audio"]
        vid_out = WORK_DIR / job["output"]

        aud_dur = get_wav_duration(aud_in)
        start_sec = offsets.get(name, idx * 3.0)
        trimmed_vid = Path(f"/tmp/trim_{name}.mp4")
        trim_video_for_job(vid_in, trimmed_vid, start_sec=start_sec, dur_sec=aud_dur + 0.4)
        if not trimmed_vid.exists() or trimmed_vid.stat().st_size < 5000:
            trim_video_for_job(vid_in, trimmed_vid, start_sec=0.0, dur_sec=aud_dur + 0.4)

        t_job = time.time()
        print(f"[JOB] Starting {name} ({aud_dur:.2f}s): video={trimmed_vid.name}, audio={aud_in.name} -> {vid_out.name}", flush=True)
        cmd = [
            vpy, "-m", "scripts.inference",
            "--unet_config_path", unet_cfg,
            "--inference_ckpt_path", ckpt_path,
            "--video_path", str(trimmed_vid),
            "--audio_path", str(aud_in),
            "--video_out_path", str(vid_out),
            "--guidance_scale", str(job.get("guidance_scale", 1.5)),
            "--inference_steps", str(job.get("inference_steps", 20)),
        ]
        if has_deepcache_flag:
            cmd.append("--enable_deepcache")
        run(cmd, cwd=str(REPO_DIR))
        if not vid_out.exists() or vid_out.stat().st_size < 5000:
            raise RuntimeError(f"Output missing or empty for {name}: {vid_out}")

        results[name] = {
            "output": vid_out.name,
            "size_bytes": vid_out.stat().st_size,
            "elapsed_sec": round(time.time() - t_job, 2),
        }
        print(f"[JOB] Done {name} in {results[name]['elapsed_sec']}s", flush=True)

    status = {
        "ok": True,
        "run_id": manifest.get("run_id"),
        "total_elapsed_sec": round(time.time() - t0, 2),
        "jobs": results,
    }
    (WORK_DIR / "status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(f"[ALL DONE] {json.dumps(status)}", flush=True)


if __name__ == "__main__":
    main()
