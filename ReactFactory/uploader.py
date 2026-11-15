import os
import json
import base64
import urllib.request
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)


def get_youtube_access_token(token_index=1):
    """
    Obtém um access_token válido a partir do YOUTUBE_TOKEN_BASE64 (ou YOUTUBE_TOKEN_2_BASE64).
    Funciona 100% em nuvem (GitHub Actions) sem precisar de navegador aberto.
    """
    env_name = "YOUTUBE_TOKEN_BASE64" if token_index == 1 else f"YOUTUBE_TOKEN_{token_index}_BASE64"
    b64_data = os.environ.get(env_name)

    if not b64_data:
        local_secret = os.path.join(ROOT_DIR, "_render_secrets", "6_NEW_CHANNEL_YOUTUBE_TOKEN_B64.txt")
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


def upload_short_to_youtube(video_path, title, description, tags=None, privacy_status="public"):
    """
    Faz upload do vídeo final para o YouTube Shorts usando Resumable Upload API v3.
    """
    access_token = get_youtube_access_token(1)

    if "#shorts" not in title.lower():
        title = f"{title[:88]} #shorts"

    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["shorts", "react", "viral", "curiosidades"],
            "categoryId": "24",  # Entertainment
            "defaultLanguage": "pt-BR",
            "defaultAudioLanguage": "pt-BR",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    init_url = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"
    body_bytes = json.dumps(metadata).encode("utf-8")
    file_size = os.path.getsize(video_path)

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

    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

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

    with urllib.request.urlopen(req_upload, timeout=300) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        yt_id = result.get("id")
        print(f"[UPLOADER] Short publicado com sucesso! https://youtube.com/shorts/{yt_id}")
        return yt_id
