import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

WORK_DIR = Path("/kaggle/working")
VENV_DIR = Path("/tmp/cb_venv")
INPUT_ROOT = Path("/kaggle/input")


def run(cmd, check=True):
    print(f"[CMD] {' '.join(cmd) if isinstance(cmd, list) else cmd}", flush=True)
    res = subprocess.run(cmd, shell=isinstance(cmd, str))
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed ({res.returncode}): {cmd}")
    return res.returncode


def find_input_dir():
    for p in INPUT_ROOT.rglob("manifest.json"):
        print(f"[INPUT] Found manifest at {p}", flush=True)
        return p.parent
    entries = [str(p) for p in list(INPUT_ROOT.rglob("*"))[:40]]
    raise FileNotFoundError(f"manifest.json not found under {INPUT_ROOT}. Found: {entries}")


def setup_chatterbox():
    run("nvidia-smi", check=False)
    if not (VENV_DIR / "bin" / "python").exists():
        run([sys.executable, "-m", "pip", "install", "-q", "uv"])
        uv_bin = shutil.which("uv") or "uv"
        run([uv_bin, "venv", str(VENV_DIR), "--python", "3.11"])
        vpy = str(VENV_DIR / "bin" / "python")
        run([
            uv_bin, "pip", "install", "--python", vpy, "-q",
            "torch==2.6.0", "torchaudio==2.6.0",
            "--index-url", "https://download.pytorch.org/whl/cu124",
        ])
        run([
            uv_bin, "pip", "install", "--python", vpy, "-q",
            "chatterbox-tts", "soundfile",
        ])
    return str(VENV_DIR / "bin" / "python")


SYNTH_RUNNER = r'''
import json, random, sys, time
from pathlib import Path
import numpy as np
import soundfile as sf
import torch
from chatterbox.mtl_tts import ChatterboxMultilingualTTS

manifest_path = Path(sys.argv[1])
work_dir = Path(sys.argv[2])
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
ref_wav = str(manifest_path.parent / manifest["ref_audio"])
seed = int(manifest.get("seed", 42))

def set_seed(s):
    random.seed(s)
    np.random.seed(s)
    torch.manual_seed(s)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(s)

print("[CB] Loading ChatterboxMultilingualTTS on CUDA...", flush=True)
t0 = time.time()
model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
print(f"[CB] Loaded in {time.time()-t0:.1f}s | sr={model.sr}", flush=True)

results = {}
for item in manifest["chunks"]:
    cid = item["id"]
    txt = item["text"]
    out_wav = work_dir / item["output"]
    set_seed(seed)
    t1 = time.time()
    wav = model.generate(
        txt,
        language_id="pt",
        audio_prompt_path=ref_wav,
        exaggeration=float(item.get("exaggeration", 0.56)),
        cfg_weight=float(item.get("cfg_weight", 0.5)),
        temperature=float(item.get("temperature", 0.65)),
    )
    arr = wav.squeeze(0).detach().cpu().numpy()
    sf.write(str(out_wav), arr, model.sr)
    print(f"[CB] {cid}: {len(arr)/model.sr:.2f}s audio in {time.time()-t1:.1f}s", flush=True)
    results[cid] = item["output"]

(work_dir / "status.json").write_text(
    json.dumps({"run_id": manifest["run_id"], "results": results}, indent=2),
    encoding="utf-8",
)
print("[CB] ALL DONE!", flush=True)
'''


def main():
    input_dir = find_input_dir()
    vpy = setup_chatterbox()
    runner_py = Path("/tmp/run_cb.py")
    runner_py.write_text(SYNTH_RUNNER, encoding="utf-8")
    run([vpy, str(runner_py), str(input_dir / "manifest.json"), str(WORK_DIR)])


if __name__ == "__main__":
    main()
