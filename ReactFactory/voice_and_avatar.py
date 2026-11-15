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


def generate_realistic_voice(text, output_wav_path, style_hint="empolgado, carismático e muito natural"):
    gemini_key = get_secret("GEMINI_API_KEY", "1_GEMINI_API_KEY.txt")
    raw_wav = output_wav_path + ".raw.wav"

    if gemini_key:
        for attempt in range(3):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={gemini_key}"
                prompt = f"Fale em Português do Brasil como um criador/streamer {style_hint}, com ritmo rápido, expressivo e natural de YouTube Shorts: {text}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {
                            "voiceConfig": {
                                "prebuiltVoiceConfig": {"voiceName": "Puck"}
                            }
                        },
                    },
                }
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
                    with wave.open(raw_wav, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(pcm_bytes)

                subprocess.run([
                    FFMPEG_EXE, "-y", "-i", raw_wav,
                    "-af", "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-42dB,acompressor=threshold=-16dB:ratio=3:attack=5:release=50,volume=1.35",
                    "-ar", "24000", "-ac", "1", output_wav_path
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(raw_wav):
                    os.remove(raw_wav)
                print(f"[VOICE] Voz Realista Gemini TTS gerada: {output_wav_path} ({get_audio_duration(output_wav_path):.2f}s)")
                time.sleep(2.5)
                return output_wav_path
            except Exception as e:
                if "429" in str(e) and attempt < 2:
                    wait_s = 62 if attempt == 0 else 45
                    print(f"[VOICE] Rate limit 429 no Gemini TTS, aguardando {wait_s}s ({attempt+1}/3)...")
                    time.sleep(wait_s)
                    continue
                print(f"[VOICE] Aviso Gemini TTS ({e}), usando Edge-TTS Neural Masterizado...")
                break

    import edge_tts
    mp3_temp = output_wav_path + ".mp3"

    async def _run_edge():
        comm = edge_tts.Communicate(text, "pt-BR-AntonioNeural", rate="+10%", pitch="-2Hz")
        await comm.save(mp3_temp)

    asyncio.run(_run_edge())
    subprocess.run([
        FFMPEG_EXE, "-y", "-i", mp3_temp,
        "-af", "silenceremove=start_periods=1:start_silence=0.04:start_threshold=-45dB,equalizer=f=140:width_type=o:width=1.5:g=3.5,acompressor=threshold=-16dB:ratio=3:attack=5:release=50,volume=1.3",
        "-ar", "24000", "-ac", "1", output_wav_path
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(mp3_temp):
        os.remove(mp3_temp)
    return output_wav_path


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
