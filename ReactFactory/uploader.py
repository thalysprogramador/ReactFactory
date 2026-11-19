import os
import json
import base64
import urllib.error
import urllib.request
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)


def _get_local_secret_path(token_index):
    if token_index == 1:
        return os.path.join(ROOT_DIR, "_render_secrets", "6_NEW_CHANNEL_YOUTUBE_TOKEN_B64.txt")
    return os.path.join(ROOT_DIR, "_render_secrets", f"YOUTUBE_TOKEN_{token_index}_B64.txt")


def get_youtube_access_token(token_index=1):
    """
    Obtém um access_token válido a partir de YOUTUBE_TOKEN_BASE64, YOUTUBE_TOKEN_2_BASE64 ou YOUTUBE_TOKEN_3_BASE64.
    Funciona 100% em nuvem (GitHub Actions) sem precisar de navegador aberto.
    """
    env_name = "YOUTUBE_TOKEN_BASE64" if token_index == 1 else f"YOUTUBE_TOKEN_{token_index}_BASE64"
    b64_data = (os.environ.get(env_name) or "").strip()

    if not b64_data:
        local_secret = _get_local_secret_path(token_index)
        if os.path.exists(local_secret):
            with open(local_secret, "r", encoding="utf-8") as f:
                b64_data = f.read().strip()

    if not b64_data:
        raise RuntimeError(f"Credencial {env_name} não encontrada.")

    token_info = json.loads(base64.b64decode(b64_data).decode("utf-8"))
    refresh_token = token_info.get("refresh_token")
    client_id = token_info.get("client_id")
    client_secret = token_info.get("client_secret")
    token_uri = token_info.get("token_uri", "https://oauth2.googleapis.com/token")

    payload = urllib.parse.urlencode({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }).encode("utf-8")

    req = urllib.request.Request(
        token_uri,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["access_token"]


def _available_token_indices():
    """Retorna os índices de projetos YouTube Data API configurados (1, 2, 3) para rotação automática de cota."""
    avail = []
    for idx in (1, 2, 3):
        env_name = "YOUTUBE_TOKEN_BASE64" if idx == 1 else f"YOUTUBE_TOKEN_{idx}_BASE64"
        if (os.environ.get(env_name) or "").strip() or os.path.exists(_get_local_secret_path(idx)):
            avail.append(idx)
    return avail or [1]


def _resumable_upload_with_rotation(video_path, metadata, upload_timeout=600):
    """
    Executa upload resumable na YouTube Data API v3 com ROTAÇÃO AUTOMÁTICA DE COTA entre os Projetos 1, 2 e 3:
    se o Projeto 1 retornar 403 quotaExceeded, troca instantaneamente para o Projeto 2 e depois Projeto 3!
    Retorna (yt_id, access_token_usado).
    """
    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    body_bytes = json.dumps(metadata).encode("utf-8")
    file_size = os.path.getsize(video_path)
    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    indices = _available_token_indices()
    last_err = None

    for idx in indices:
        try:
            access_token = get_youtube_access_token(idx)
            req_init = urllib.request.Request(
                init_url,
                data=body_bytes,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json; charset=UTF-8",
                    "X-Upload-Content-Length": str(file_size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                method="POST",
            )
            with urllib.request.urlopen(req_init, timeout=45) as resp:
                upload_url = resp.headers.get("Location")

            req_upload = urllib.request.Request(
                upload_url,
                data=video_bytes,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Length": str(file_size),
                    "Content-Type": "video/mp4",
                },
                method="PUT",
            )
            with urllib.request.urlopen(req_upload, timeout=upload_timeout) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                yt_id = result.get("id")
                print(f"[UPLOADER] Sucesso usando Projeto YT #{idx} -> video_id={yt_id}", flush=True)
                return yt_id, access_token
        except urllib.error.HTTPError as herr:
            err_body = ""
            try:
                err_body = herr.read().decode("utf-8", errors="replace")[:300]
            except Exception:
                pass
            print(f"[UPLOADER] Projeto YT #{idx} retornou HTTP {herr.code}: {err_body} -> tentando próximo projeto...", flush=True)
            last_err = RuntimeError(f"Projeto YT #{idx} HTTP {herr.code}: {err_body}")
        except Exception as err:
            print(f"[UPLOADER] Projeto YT #{idx} falhou ({err}) -> tentando próximo projeto...", flush=True)
            last_err = err

    raise last_err or RuntimeError("Nenhum projeto YouTube Data API disponível conseguiu concluir o upload.")


def upload_short_to_youtube(video_path, title, description, tags=None, privacy_status="public"):
    """Faz upload do vídeo final para o YouTube Shorts com rotação automática entre Projetos YT 1, 2 e 3."""
    if "#shorts" not in title.lower():
        title = f"{title[:88]} #shorts"

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["shorts", "gta 6", "viral", "curiosidades"],
            "categoryId": "20",  # Gaming / Jogos
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    yt_id, _ = _resumable_upload_with_rotation(video_path, metadata, upload_timeout=300)
    print(f"[UPLOADER] Short publicado com sucesso! https://youtube.com/shorts/{yt_id}")
    return yt_id


def set_video_thumbnail(video_id, thumb_path, access_token=None):
    """Define thumbnail customizada (1280x720) para vídeo longo no YouTube."""
    with open(thumb_path, "rb") as tf:
        img_bytes = tf.read()
    ctype = "image/png" if thumb_path.lower().endswith(".png") else "image/jpeg"
    url = f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={urllib.parse.quote(video_id)}&uploadType=media"

    tokens_to_try = [access_token] if access_token else [get_youtube_access_token(i) for i in _available_token_indices()]
    last_err = None
    for tok in tokens_to_try:
        try:
            req = urllib.request.Request(
                url,
                data=img_bytes,
                headers={
                    "Authorization": f"Bearer {tok}",
                    "Content-Type": ctype,
                    "Content-Length": str(len(img_bytes)),
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                print(f"[UPLOADER] Thumbnail aplicada ao vídeo {video_id}!")
                return res
        except Exception as err:
            last_err = err
    if last_err:
        raise last_err


def upload_long_to_youtube(video_path, title, description, tags=None, thumb_path=None, privacy_status="public"):
    """Faz upload de vídeo longo 16:9 com rotação automática entre Projetos YT 1, 2 e 3 + thumbnail customizada."""
    metadata = {
        "snippet": {
            "title": (title or "GTA 6 NOVIDADES!")[:100],
            "description": description or "",
            "tags": (tags or ["gta 6", "gta vi", "rockstar games", "games"])[:25],
            "categoryId": "20",  # Gaming / Jogos
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    yt_id, used_token = _resumable_upload_with_rotation(video_path, metadata, upload_timeout=600)
    print(f"[UPLOADER] Vídeo longo publicado com sucesso! https://www.youtube.com/watch?v={yt_id}")

    if thumb_path and os.path.exists(thumb_path) and yt_id:
        try:
            set_video_thumbnail(yt_id, thumb_path, access_token=used_token)
        except Exception as err:
            print(f"[UPLOADER] Aviso ao enviar thumbnail: {err}")

    return yt_id
