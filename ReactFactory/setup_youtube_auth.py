import os
import json
import base64
import urllib.parse
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
SECRETS_DIR = os.path.join(ROOT_DIR, "_render_secrets")
CLIENT_SECRET_FILE = os.path.join(SECRETS_DIR, "3_CLIENT_SECRET_JSON.txt")
OUTPUT_TOKEN_B64_FILE = os.path.join(SECRETS_DIR, "6_NEW_CHANNEL_YOUTUBE_TOKEN_B64.txt")

PORT = 8089
REDIRECT_URI = f"http://localhost:{PORT}"
SCOPES = (
    "https://www.googleapis.com/auth/youtube.upload "
    "https://www.googleapis.com/auth/youtube.readonly "
    "https://www.googleapis.com/auth/yt-analytics.readonly"
)


def run_oauth_flow():
    with open(CLIENT_SECRET_FILE, "r", encoding="utf-8") as f:
        cs_data = json.load(f)

    cfg = cs_data.get("installed") or cs_data.get("web")
    client_id = cfg["client_id"]
    client_secret = cfg["client_secret"]
    auth_uri = cfg.get("auth_uri", "https://accounts.google.com/o/oauth2/auth")
    token_uri = cfg.get("token_uri", "https://oauth2.googleapis.com/token")

    auth_params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent select_account",
    })
    url = f"{auth_uri}?{auth_params}"
    print("\n========================================================")
    print("ABRINDO NAVEGADOR PARA SELECIONAR O CANAL DO YOUTUBE:")
    print(url)
    print("========================================================\n")
    webbrowser.open(url)

    captured = {"code": None}

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            qs = urllib.parse.parse_qs(parsed.query)
            if "code" in qs:
                captured["code"] = qs["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body style='font-family:sans-serif;text-align:center;padding:50px;'>"
                    b"<h1>Canal do YouTube Conectado com Sucesso!</h1>"
                    b"<p>Pode fechar esta janela e voltar ao Antigravity.</p></body></html>"
                )
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("localhost", PORT), OAuthHandler)
    while captured["code"] is None:
        server.handle_request()
    server.server_close()

    # Troca o code pelo refresh_token definitivo
    token_payload = urllib.parse.urlencode({
        "code": captured["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode("utf-8")

    req = urllib.request.Request(
        token_uri,
        data=token_payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        t_resp = json.loads(resp.read().decode("utf-8"))

    final_token_obj = {
        "token": t_resp.get("access_token"),
        "refresh_token": t_resp.get("refresh_token"),
        "token_uri": token_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": SCOPES.split(),
    }

    b64_str = base64.b64encode(json.dumps(final_token_obj).encode("utf-8")).decode("utf-8")
    with open(OUTPUT_TOKEN_B64_FILE, "w", encoding="utf-8") as f:
        f.write(b64_str)

    print("TOKEN SALVO COM SUCESSO EM:", OUTPUT_TOKEN_B64_FILE)
    try:
        ch_req = urllib.request.Request(
            "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
            headers={"Authorization": f"Bearer {t_resp.get('access_token')}"},
        )
        with urllib.request.urlopen(ch_req, timeout=15) as r:
            ch_data = json.loads(r.read().decode("utf-8"))
            for item in ch_data.get("items", []):
                print("CANAL AUTENTICADO:", item["snippet"]["title"], "| ID:", item["id"])
    except Exception as e:
        print("Aviso ao consultar nome do canal:", e)


if __name__ == "__main__":
    run_oauth_flow()
