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


def generate_react_script(video_path, original_title="Viral Video", original_desc="", research_brief=None):
    api_key = get_gemini_key()
    frames_b64, duration = extract_video_frames_b64(video_path, num_frames=8)
    audio_b64 = extract_audio_mp3_b64(video_path, max_sec=28)

    mid_default = round(min(max(duration * 0.45, 4.5), min(max(duration - 3.5, 5.5), 15.0)), 1)
    audio_note = (
        "Você também está OUVINDO O ÁUDIO REAL do vídeo em anexo! Reaja especificamente ao que foi falado/aconteceu na cena."
        if audio_b64
        else "Analise visualmente cada frame em detalhe para reagir exatamente ao que acontece."
    )

    ref_block = ""
    if research_brief:
        top_titles = "\n".join(
            f"- ({r.get('views', 0):,} views) {r.get('channel', '')}: {r.get('title', '')}"
            for r in (research_brief.get("top_references") or [])[:6]
        )
        ref_block = f"""
TEMA OBRIGATÓRIO DO CANAL NESTA SEMANA (LANÇAMENTO NA QUINTA-FEIRA): **GTA 6 (Grand Theft Auto VI)**
Ângulo específico deste vídeo: "{research_brief.get('chosen_angle', original_title)}"
Referências virais de canais grandes bombando AGORA:
{top_titles}
Notícias/hipóteses atuais: {research_brief.get('grounding_notes', '')[:450]}
Missão neste Short (meta: 30.000+ views): transformar essa cena/corte de GTA 6 em curiosidade viciante, top novidades, segredo escondido ou teoria polêmica para quem está contando as horas para quinta-feira!
"""

    prompt = f"""Você é um criador gamer brasileiro TOP 1% de YouTube Shorts focado em BATER 30K–1M+ DE VIEWS (meta: swipe rate > 84%, retenção média > 115% em loop e explosão de comentários) + CONTEÚDO TRANSFORMATIVO autêntico.
Você está analisando 8 frames em ordem cronológica de um vídeo de {duration:.1f} segundos.
{audio_note}
{ref_block}
Título/Contexto base: "{original_title}"
Detalhes adicionais: "{original_desc}"

REGRAS DE OURO PARA RETENÇÃO ABSURDA (PROIBIDO CLICHÊS DE IA!):
- NUNCA use frases robóticas: "Imagina a calma", "Ninguém esperava esse clima", "Acompanhe essa reação", "Prepare-se para ver", "Você não vai acreditar", "Veja até o fim".
- Fale como gamer/streamer brasileiro espontâneo no microfone ("Mano", "Olha isso", "Cara", "Sério"), curto, direto, mantendo UM ÚNICO TOM firme e magnético do início ao fim.
- REGRA DO GANCHO (0-2s): Crie uma LACUNA DE CURIOSIDADE ou apontamento cirúrgico para um detalhe do GTA 6 / cena nos primeiros 2 segundos sem entregar a surpresa!
- REGRA DA INTERRUPÇÃO: Traga informação real, segredo, hipótese ou opinião forte sobre GTA 6 — nunca só narre o óbvio!

Crie as 3 intervenções afiadas:
1. `hook_text` (MÁXIMO 7 palavras — ~1.8s a 2.3s!): Gancho magnético logo no segundo 0 (ex: "Ninguém reparou nesse segredo do GTA 6!", "Olha a física absurda dessa cena aqui!").
2. `interrupt_sec` (número decimal entre 4.5 e {min(max(duration - 3.5, 5.5), 15.5):.1f}): Segundo exato antes da melhor cena/clímax para pausar e revelar o detalhe.
3. `interrupt_text` (MÁXIMO 9 palavras): Revelação, curiosidade ou comparação cirúrgica que aumenta o hype para o desfecho.
4. `outro_text` (MÁXIMO 7 palavras): Fechamento rápido com PERGUNTA POLARIZADORA para explodir comentários (ex: "Vai jogar na quinta ou vai esperar?", "Nota zero a dez pra esse detalhe!").
5. `reaction_mood`: Escolha EXATAMENTE UM entre: "chocado", "rindo", "pensativo", "impressionado".
6. `headline_top` (MÁXIMO 4 palavras em MAIÚSCULAS): Gancho de curiosidade sobre GTA 6 SEM entregar tudo (ex: "SEGREDO DO GTA 6!", "OLHA ESSA FÍSICA 🤯", "QUINTA-FEIRA VAI PARAR").
7. `yt_title`: Título magnético SEO de alto CTR em PT-BR com palavra-chave GTA 6 + 1 emoji + #gta6 #shorts.
8. `yt_description`: Resumo em PT-BR otimizado para busca de GTA 6 + pergunta pros comentários + hashtags (#gta6 #gtavi #rockstargames #games #shorts #viral #curiosidades).
9. `yt_tags`: Lista com 12 a 15 tags estratégicas de alto volume para GTA 6 no YouTube Brasil ("gta 6", "gta vi", "gta 6 lancamento", "gta 6 novidades", "gta 6 segredos", "rockstar games", "gta 6 trailer", "gta 6 curiosidades", "gta 6 brasil", "vice city", "leonida", "shorts", etc.).

Responda APENAS com um JSON válido:
{{
  "headline_top": "...",
  "hook_text": "...",
  "interrupt_sec": {mid_default},
  "interrupt_text": "...",
  "outro_text": "...",
  "reaction_mood": "impressionado",
  "yt_title": "...",
  "yt_description": "...",
  "yt_tags": ["gta 6", "gta vi", "gta 6 novidades", "gta 6 segredos", "gta 6 lancamento", "rockstar games", "vice city", "leonida", "games", "shorts", "viral", "curiosidades"]
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

    from producao.gemini_client import gemini_generate  # noqa: WPS433

    print("[BRAIN] Gerando roteiro afiado com retry resiliente...")
    data = gemini_generate(payload)
    text_resp = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    if text_resp.startswith("```"):
        text_resp = text_resp.strip("`")
        if text_resp.lower().startswith("json"):
            text_resp = text_resp[4:].strip()
    script = json.loads(text_resp)
    script["video_duration"] = duration
    script["model_used"] = data.get("_model", "gemini-2.5-flash")
    script["used_audio_context"] = bool(audio_b64)
    return script
