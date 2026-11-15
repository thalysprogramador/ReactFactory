import os
import json
import base64
import urllib.request
import cv2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)


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


def generate_react_script(video_path, original_title="Viral Video", original_desc=""):
    api_key = get_gemini_key()
    frames_b64, duration = extract_video_frames_b64(video_path, num_frames=8)

    mid_default = round(min(max(duration * 0.45, 5.0), min(max(duration - 4.0, 6.0), 16.0)), 1)

    prompt = f"""Você é um criador brasileiro carismático de YouTube Shorts de REACT (estilo trends atuais do Brasil, memes, influenciadores e curiosidades de altíssima retenção).
Você está analisando 8 frames em ordem cronológica de um vídeo viral brasileiro de {duration:.1f} segundos.
Título original do vídeo: "{original_title}"
Contexto/Descrição original: "{original_desc}"

REGRAS DE OURO (PROIBIDO CLICHÊS DE IA!):
- NUNCA use frases robóticas como "Imagina a calma antes do caos", "Acompanhe essa reação", "Prepare-se para ver", "Você não vai acreditar". Fale como um influenciador brasileiro natural trocando ideia no microfone!
- Se o vídeo for de humor/trend/influenciador, comente a graça, o absurdo ou a reviravolta da situação. Se for curiosidade, entregue o fato surpreendente na hora!
- Mantenha as falas curtas e rápidas para dar ritmo frenético (sem enrolar).

Crie as 3 intervenções curtas e afiadas:
1. `hook_text` (máx 13 palavras): Já abra prendendo o espectador na situação ou curiosidade da cena logo nos primeiros 3 segundos!
2. `interrupt_sec` (número decimal entre 5.0 e {min(max(duration - 4.0, 6.0), 16.5):.1f}): Momento exato antes da virada/clímax para congelar e comentar.
3. `interrupt_text` (máx 13 palavras): Aponte o detalhe engraçado/chocante ou aumente a expectativa bem antes do desfecho.
4. `outro_text` (máx 10 palavras): Fechamento rápido com pergunta direta pra gerar comentários ("Você faria igual ou corria? Comenta aí!").
5. `reaction_mood`: Escolha EXATAMENTE UM entre: "chocado", "rindo", "pensativo", "impressionado".
6. `headline_top` (máx 4 palavras em MAIÚSCULAS): Manchete curta e chamativa fixa no topo.
7. `yt_title`: Título apelativo de alta taxa de clique em PT-BR com emoji e #shorts #viral #react.
8. `yt_description`: Legenda envolvente em PT-BR resumindo a trend/curiosidade + chamada pra comentar + hashtags (#shorts #brasil #viral #react #trends).
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
                text_resp = data["candidates"][0]["content"]["parts"][0]["text"]
                script = json.loads(text_resp)
                script["video_duration"] = duration
                script["model_used"] = model_name
                return script
        except Exception as e:
            print(f"[BRAIN] Fallback de {model_name} ({e})...")

    raise RuntimeError("Não foi possível gerar o roteiro no Gemini.")
