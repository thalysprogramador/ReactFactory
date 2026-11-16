import os
import json
import time
import base64
import wave
import subprocess
import asyncio
import urllib.request
import imageio_ffmpeg

from kaggle_lipsync import run_batch_lipsync_kaggle

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def get_secret(env_name, filename):
    val = os.environ.get(env_name)
    if val:
        return val.strip()
    path = os.path.join(ROOT_DIR, "_render_secrets", filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return None


def get_audio_duration(audio_path):
    if audio_path.endswith(".wav"):
        try:
            with wave.open(audio_path, "rb") as wf:
                return wf.getnframes() / float(wf.getframerate())
        except Exception:
            pass
    cmd = [FFMPEG_EXE, "-i", audio_path]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            t_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 3.5


UNIFIED_VOICE_PERSONA = (
    "Leia em Português do Brasil mantendo EXATAMENTE o mesmo tom de voz, altura, timbre, "
    "cadência rápida e energia constante de um único criador jovem de YouTube Shorts, "
    "falando com firmeza e naturalidade sem mudar de humor nem dar risadas forçadas"
)


def _master_voice_wav(raw_input_path, output_wav_path):
    """Padroniza timbre, presença vocal, corte de silêncio e volume (LUFS) entre todas as falas."""
    af = (
        "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-42dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_silence=0.03:start_threshold=-42dB,"
        "areverse,"
        "equalizer=f=150:width_type=o:width=1.5:g=2.0,"
        "equalizer=f=3200:width_type=o:width=1.5:g=1.5,"
        "acompressor=threshold=-18dB:ratio=2.8:attack=5:release=60,"
        "loudnorm=I=-15:TP=-1.5:LRA=4"
    )
    subprocess.run([
        FFMPEG_EXE, "-y", "-i", raw_input_path,
        "-af", af,
        "-ar", "24000", "-ac", "1", output_wav_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_wav_path


def _call_gemini_tts(text, raw_wav_path, gemini_key, persona_prompt=UNIFIED_VOICE_PERSONA):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={gemini_key}"
    prompt = f"{persona_prompt}: \"{text}\""
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": "Puck"}
                }
            },
        },
    }
    for attempt in range(2):
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            pcm_b64 = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
            pcm_bytes = base64.b64decode(pcm_b64)
            with wave.open(raw_wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(pcm_bytes)
            return True
        except Exception as e:
            err_s = str(e)
            if "400" in err_s and "temperature" in payload.get("generationConfig", {}):
                payload["generationConfig"].pop("temperature", None)
                continue
            if "429" in err_s and attempt == 0:
                print("[VOICE] Rate limit 429 no Gemini TTS, aguardando 22s antes de decidir...")
                time.sleep(22)
                continue
            print(f"[VOICE] Aviso Gemini TTS ({e}).")
            return False
    return False


def _call_edge_tts(text, raw_mp3_path):
    import edge_tts

    async def _run_edge():
        comm = edge_tts.Communicate(text, "pt-BR-AntonioNeural", rate="+12%", pitch="+0Hz")
        await comm.save(raw_mp3_path)

    asyncio.run(_run_edge())
    return raw_mp3_path


def generate_realistic_voice(text, output_wav_path, style_hint=None):
    gemini_key = get_secret("GEMINI_API_KEY", "1_GEMINI_API_KEY.txt")
    raw_wav = output_wav_path + ".raw.wav"
    persona = style_hint or UNIFIED_VOICE_PERSONA

    if gemini_key and _call_gemini_tts(text, raw_wav, gemini_key, persona):
        _master_voice_wav(raw_wav, output_wav_path)
        if os.path.exists(raw_wav):
            os.remove(raw_wav)
        print(f"[VOICE] Gemini TTS padronizado: {output_wav_path} ({get_audio_duration(output_wav_path):.2f}s)")
        return output_wav_path

    mp3_temp = output_wav_path + ".mp3"
    _call_edge_tts(text, mp3_temp)
    _master_voice_wav(mp3_temp, output_wav_path)
    if os.path.exists(mp3_temp):
        os.remove(mp3_temp)
    print(f"[VOICE] Edge-TTS Neural padronizado: {output_wav_path} ({get_audio_duration(output_wav_path):.2f}s)")
    return output_wav_path


def generate_consistent_voices(texts_by_key, output_paths_by_key):
    """
    Gera todas as falas (hook, inter, outro) com o MESMO motor, MESMO timbre e
    MESMA masterização (LUFS idêntico) — nunca mistura vozes diferentes no mesmo vídeo.
    """
    gemini_key = get_secret("GEMINI_API_KEY", "1_GEMINI_API_KEY.txt")
    keys = list(texts_by_key.keys())

    if gemini_key:
        raw_files = {}
        all_ok = True
        for i, k in enumerate(keys):
            raw_wav = output_paths_by_key[k] + ".raw.wav"
            ok = _call_gemini_tts(texts_by_key[k], raw_wav, gemini_key, UNIFIED_VOICE_PERSONA)
            if not ok:
                all_ok = False
                break
            raw_files[k] = raw_wav
            if i < len(keys) - 1:
                time.sleep(2.0)

        if all_ok:
            for k in keys:
                _master_voice_wav(raw_files[k], output_paths_by_key[k])
                if os.path.exists(raw_files[k]):
                    os.remove(raw_files[k])
                print(f"[VOICE] Gemini TTS uniforme [{k}]: {output_paths_by_key[k]} ({get_audio_duration(output_paths_by_key[k]):.2f}s)")
            return "gemini"

        for p in raw_files.values():
            if os.path.exists(p):
                os.remove(p)
        print("[VOICE] Padronizando 100% das falas em Edge-TTS Neural (evitando troca de voz no meio do vídeo)...")

    for k in keys:
        mp3_temp = output_paths_by_key[k] + ".mp3"
        _call_edge_tts(texts_by_key[k], mp3_temp)
        _master_voice_wav(mp3_temp, output_paths_by_key[k])
        if os.path.exists(mp3_temp):
            os.remove(mp3_temp)
        print(f"[VOICE] Edge-TTS uniforme [{k}]: {output_paths_by_key[k]} ({get_audio_duration(output_paths_by_key[k]):.2f}s)")
    return "edge"


def _first_existing(candidates):
    for name in candidates:
        p = os.path.join(ASSETS_DIR, name)
        if os.path.exists(p) and os.path.getsize(p) > 50_000:
            return p
    return None


def pick_avatar_clips(reaction_mood="chocado"):
    """
    Seleciona os clipes de FALA (boca/expressão) e REAÇÃO SILENCIOSA (boca fechada)
    enviados pelo usuário em `ReactFactory/assets/`.
    """
    fala_1 = _first_existing(["fala_1.mp4", "flow_talking.mp4"])
    fala_2 = _first_existing(["fala_2.mp4", "fala_1.mp4", "flow_talking.mp4"])
    if not fala_1:
        raise FileNotFoundError("Nenhum clipe de fala encontrado em ReactFactory/assets/ (fala_1.mp4 / flow_talking.mp4).")

    mood_map = {
        "chocado": ["reacao_chocado.mp4", "reacao_impressionado.mp4", "flow_react_pure_silent.mp4", "flow_react_surprise.mp4"],
        "rindo": ["reacao_rindo.mp4", "reacao_impressionado.mp4", "flow_react_pure_silent.mp4", "flow_react_surprise.mp4"],
        "pensativo": ["reacao_pensativo.mp4", "reacao_chocado.mp4", "flow_react_pure_silent.mp4", "flow_react_surprise.mp4"],
        "impressionado": ["reacao_impressionado.mp4", "reacao_chocado.mp4", "flow_react_pure_silent.mp4", "flow_react_surprise.mp4"],
    }
    primary_list = mood_map.get(reaction_mood, mood_map["chocado"])
    reaction_primary = _first_existing(primary_list)

    # Segundo clipe de reação distinto para a Parte 2 (evita repetição mecânica!)
    secondary_candidates = [
        name for name in ["reacao_impressionado.mp4", "reacao_pensativo.mp4", "reacao_chocado.mp4", "reacao_rindo.mp4", "flow_react_pure_silent.mp4", "flow_react_surprise.mp4"]
        if not reaction_primary or os.path.basename(reaction_primary) != name
    ]
    reaction_secondary = _first_existing(secondary_candidates) or reaction_primary

    return {
        "talking": [fala_1, fala_2 or fala_1, fala_1],
        "reaction_primary": reaction_primary,
        "reaction_secondary": reaction_secondary,
    }


def generate_batch_lipsync_clips(hook_wav, inter_wav, outro_wav, talking_clips, out_dir=TEMP_DIR):
    """
    Envia os 3 trechos (hook, interrupção, outro) em um único job para o Kaggle T4 GPU
    rodar ByteDance LatentSync v1.5 com sincronização labial de alta fidelidade.
    """
    jobs = [
        {
            "name": "hook",
            "video_path": talking_clips[0],
            "audio_path": hook_wav,
            "output_name": "synced_hook.mp4",
            "guidance_scale": 1.5,
            "inference_steps": 20,
        },
        {
            "name": "inter",
            "video_path": talking_clips[1],
            "audio_path": inter_wav,
            "output_name": "synced_inter.mp4",
            "guidance_scale": 1.5,
            "inference_steps": 20,
        },
        {
            "name": "outro",
            "video_path": talking_clips[2],
            "audio_path": outro_wav,
            "output_name": "synced_outro.mp4",
            "guidance_scale": 1.5,
            "inference_steps": 20,
        },
    ]
    return run_batch_lipsync_kaggle(jobs, out_dir=out_dir)
