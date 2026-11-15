import os
import json
import base64
import subprocess
import tempfile
import urllib.request
import cv2
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_gemini_key():
    env_key = os.environ.get("GEMINI_API_KEY")
    if env_key:
        return env_key.strip()
    secret_file = os.path.join(ROOT_DIR, "_render_secrets", "1_GEMINI_API_KEY.txt")
    if os.path.exists(secret_file):
        with open(secret_file, "r", encoding="utf-8") as f:
            return f.read().strip()
    raise RuntimeError("GEMINI_API_KEY não encontrada.")


def extract_video_frames_b64(video_path, num_frames=8):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = total_frames / fps if total_frames > 0 else 20.0

    frames_b64 = []
    if total_frames > 0:
        indices = [int(total_frames * (i / (num_frames - 1))) for i in range(num_frames)]
        indices[-1] = max(0, total_frames - 2)
        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if ret:
                h, w = frame.shape[:2]
                scale = 512 / max(h, w)
                if scale < 1.0:
                    frame = cv2.resize(frame, (int(w * scale), int(h * scale)))
                _, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
                frames_b64.append(base64.b64encode(buf).decode("utf-8"))
    cap.release()
    return frames_b64, duration


def extract_audio_mp3_b64(video_path, max_sec=28):
    """Extrai o áudio leve (mono 16kHz 32kbps MP3) para o Gemini ouvir falas/piadas reais do vídeo."""
    tmp_mp3 = None
    try:
        fd, tmp_mp3 = tempfile.mkstemp(suffix=".mp3")
        os.close(fd)
        proc = subprocess.run(
            [
                FFMPEG_EXE, "-y", "-t", str(max_sec), "-i", video_path,
                "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k", tmp_mp3,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=25,
        )
        if proc.returncode == 0 and os.path.exists(tmp_mp3) and os.path.getsize(tmp_mp3) > 512:
            with open(tmp_mp3, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception as e:
        print(f"[BRAIN] Aviso ao extrair áudio (seguindo só com frames): {e}")
    finally:
        if tmp_mp3 and os.path.exists(tmp_mp3):
            try:
                os.remove(tmp_mp3)
            except Exception:
                pass
    return None


def generate_react_script(video_path, original_title="Viral Video", original_desc=""):
    api_key = get_gemini_key()
    frames_b64, duration = extract_video_frames_b64(video_path, num_frames=8)
    audio_b64 = extract_audio_mp3_b64(video_path, max_sec=28)

    mid_default = round(min(max(duration * 0.45, 4.5), min(max(duration - 3.5, 5.5), 15.0)), 1)
    audio_note = (
        "Você também está OUVINDO O ÁUDIO REAL do vídeo em anexo! Reaja especificamente ao que foi falado/aconteceu na cena (cite a fala, a piada ou o detalhe sonoro para parecer 100% autêntico)."
        if audio_b64
        else "Analise visualmente cada frame em detalhe para reagir exatamente ao que acontece."
    )

    prompt = f"""Você é um criador brasileiro carismático de YouTube Shorts de REACT focado em RETENÇÃO EXTREMA (taxa de swipe > 78% e retenção > 105%) e CONTEÚDO TRANSFORMATIVO (opinião real, contexto e humor próprio, zero repost genérico).
Você está analisando 8 frames em ordem cronológica de um vídeo viral brasileiro de {duration:.1f} segundos.
{audio_note}
Título original do vídeo: "{original_title}"
Contexto/Descrição original: "{original_desc}"

REGRAS DE OURO (PROIBIDO CLICHÊS DE IA!):
- NUNCA use frases robóticas como "Imagina a calma antes do caos", "Acompanhe essa reação", "Prepare-se para ver", "Você não vai acreditar", "Veja até o fim". Fale como um criador brasileiro espontâneo no microfone!
- NÃO apenas descreva o óbvio na tela: traga OPINIÃO FORTE, contexto rápido, piada afiada ou um detalhe escondido que gera debate.
- Frases ULTRA CURTAS para ritmo frenético e lip-sync perfeito nos 3 primeiros segundos.

Crie as 3 intervenções afiadas:
1. `hook_text` (MÁXIMO 8 palavras — ~2 segundos!): Gancho explosivo de curiosidade ou conflito logo no segundo 0 (ex: "Olha o erro absurdo aos quatro segundos!", "Esse cara achou mesmo que ia colar?").
2. `interrupt_sec` (número decimal entre 4.5 e {min(max(duration - 3.5, 5.5), 15.5):.1f}): Momento exato antes da virada/clímax para congelar a tela e comentar.
3. `interrupt_text` (MÁXIMO 11 palavras): Reação ou comentário editorial certeiro em cima da fala/ação antes do desfecho.
4. `outro_text` (MÁXIMO 8 palavras): Fechamento seco com PERGUNTA POLARIZADORA para gerar comentários e prender o loop (ex: "Quem tá certo nessa história, 1 ou 2?", "Você faria igual ou corria?").
5. `reaction_mood`: Escolha EXATAMENTE UM entre: "chocado", "rindo", "pensativo", "impressionado".
6. `headline_top` (MÁXIMO 4 palavras em MAIÚSCULAS): Lacuna de curiosidade SEM entregar o spoiler do final!
7. `yt_title`: Título chamativo de alta taxa de clique em PT-BR com 1 emoji e #shorts #viral #react.
8. `yt_description`: Legenda envolvente em PT-BR resumindo o corte + pergunta pros comentários + hashtags (#shorts #brasil #viral #react #trends).
9. `yt_tags`: Lista com 7 a 10 tags estratégicas em português para alcance no YouTube Shorts Brasil.

Responda APENAS com um JSON válido:
{{
  "headline_top": "...",
  "hook_text": "...",
  "interrupt_sec": {mid_default},
  "interrupt_text": "...",
  "outro_text": "...",
  "reaction_mood": "rindo",
  "yt_title": "...",
  "yt_description": "...",
  "yt_tags": ["react", "shorts", "viral", "brasil", "humor", "curiosidades", "trends"]
}}"""

    parts = [{"text": prompt}]
    for b64 in frames_b64:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": b64
            }
        })
    if audio_b64:
        parts.append({
            "inline_data": {
                "mime_type": "audio/mp3",
                "data": audio_b64
            }
        })

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.75,
            "responseMimeType": "application/json"
        }
    }

    for model_name in ["gemini-3.5-flash", "gemini-2.5-flash"]:
        try:
            print(f"[BRAIN] Gerando roteiro afiado com {model_name}...")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text_resp = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text_resp.startswith("```"):
                    text_resp = text_resp.strip("`")
                    if text_resp.lower().startswith("json"):
                        text_resp = text_resp[4:].strip()
                script = json.loads(text_resp)
                script["video_duration"] = duration
                script["model_used"] = model_name
                script["used_audio_context"] = bool(audio_b64)
                return script
        except Exception as e:
            print(f"[BRAIN] Fallback de {model_name} ({e})...")

    raise RuntimeError("Não foi possível gerar o roteiro no Gemini.")
