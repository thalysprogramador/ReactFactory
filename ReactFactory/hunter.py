import os
import json
import random
import re
import base64
import urllib.request
import urllib.parse
from datetime import datetime, timezone
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# 1. Hashtags brasileiras que capturam trends do TikTok/Reels/Influenciadores/Memes/Curiosidades no YouTube BR
BR_HASHTAG_FEEDS = [
    "humorbrasil",
    "memesbrasil",
    "tiktokbrasil",
    "influenciadores",
    "podpah",
    "shortsbrasil",
    "brasilviral",
    "comediabrasil",
    "curiosidadesbrasil",
    "fypbrasil",
]

# 2. Canais brasileiros gigantes de trends, entretenimento, humor, curiosidades e influenciadores
SOURCE_CHANNELS = [
    "@Enaldinho", "@vocesabia", "@AlmanaqueSOS", "@DiogoDefante",
    "@cienciatododia", "@CazeTV", "@Nostalgia", "@t3ddy",
    "@CortesdoCasimitoOFICIAL", "@ManualdoMundo", "@PortaDosFundos",
    "@rezendeevil", "@FatosDesconhecidos", "@Podpah", "@FlowPodcast", "@felipeneto",
]

BLOCKED_WORDS = [
    "crime", "morte", "morreu", "execu", "assassin", "tiro", "bala", "acidente",
    "tragedia", "tragédia", "sangue", "policia", "polícia", "preso", "facção",
    "kill", "dead", "death", "murder", "shooting", "gun", "crash", "accident",
    "fight", "briga", "war", "guerra", "nsfw", "blood", "luto", "morre ",
]

# Evita vídeos em espanhol/gringo que às vezes usam #fypbrasil
_SPANISH_MARKERS = (" esto ", " los ", " las ", " pero ", " cuando ", " increíble", " hicieron ", " para ti ")
_PT_MARKERS = (" não ", " nao ", " pra ", " você", " voce", " gente", " mano", " olha", " como ", " quando ", " por que ", " pq ", " de ", " do ", " da ", " é ", " tá ", " kkk", "brasil")


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"used_ids": []}


def save_history(video_id, metadata=None):
    hist = load_history()
    if video_id not in hist["used_ids"]:
        hist["used_ids"].append(video_id)
    if metadata:
        hist.setdefault("posts", []).append(metadata)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)


def _is_blocked(title):
    t = (title or "").lower()
    return any(w in t for w in BLOCKED_WORDS)


def _looks_non_brazilian(full_info):
    lang = (full_info.get("language") or "").lower()
    if lang.startswith("pt"):
        return False
    if lang and lang not in ("pt", "pt-br", "und", "zxx"):
        return True
    txt = f" {full_info.get('title', '')} {full_info.get('description', '')[:250]} ".lower()
    has_pt_chars = bool(re.search(r"[ãõçáéíóúâêô]", txt)) or any(m in txt for m in _PT_MARKERS)
    has_es = any(m in txt for m in _SPANISH_MARKERS) or ("¿" in txt or "¡" in txt)
    if has_es and not has_pt_chars:
        return True
    return False


def _views_per_day(info):
    views = info.get("view_count") or 0
    ts = info.get("timestamp")
    up = info.get("upload_date")
    try:
        if ts:
            pub = datetime.fromtimestamp(ts, tz=timezone.utc)
        elif up:
            pub = datetime.strptime(up, "%Y%m%d").replace(tzinfo=timezone.utc)
        else:
            return 0.0, 9999
        days = max(0.5, (datetime.now(timezone.utc) - pub).total_seconds() / 86400)
        return views / days, days
    except Exception:
        return 0.0, 9999


def _parse_iso_duration(iso_dur):
    if not iso_dur or not iso_dur.startswith("PT"):
        return 0
    total, num = 0, ""
    for ch in iso_dur[2:]:
        if ch.isdigit():
            num += ch
        else:
            val = int(num or 0)
            num = ""
            if ch == "H":
                total += val * 3600
            elif ch == "M":
                total += val * 60
            elif ch == "S":
                total += val
    return total


def _get_youtube_cookies_file():
    """Prepara cookies.txt autenticado a partir do secret YOUTUBE_COOKIES_B64 ou arquivo local."""
    cookie_dest = os.path.join(TEMP_DIR, "yt_cookies.txt")
    b64_val = os.environ.get("YOUTUBE_COOKIES_B64", "").strip()
    if b64_val:
        raw = base64.b64decode(b64_val).decode("utf-8", errors="replace")
        with open(cookie_dest, "w", encoding="utf-8") as f:
            f.write(raw)
        return cookie_dest

    raw_txt = os.environ.get("YOUTUBE_COOKIES_TXT", "").strip()
    if raw_txt:
        with open(cookie_dest, "w", encoding="utf-8") as f:
            f.write(raw_txt)
        return cookie_dest

    local_cookie = os.path.join(ROOT_DIR, "_render_secrets", "youtube_cookies.txt")
    if os.path.exists(local_cookie) and os.path.getsize(local_cookie) > 50:
        return local_cookie
    return None


def _fetch_videos_metadata_api(video_ids):
    """Busca metadados oficiais de até 50 vídeos de uma vez via YouTube Data API v3 (sem anti-bot)."""
    try:
        from uploader import get_youtube_access_token
        token = get_youtube_access_token(1)
    except Exception as e:
        print(f"[HUNTER BR] Aviso OAuth Data API ({e}), tentando fallback yt-dlp...")
        return {}

    result = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i + 50]
        url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,contentDetails,statistics&id={urllib.parse.quote(','.join(chunk))}"
        )
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("items", []):
            vid = item["id"]
            sn = item.get("snippet", {})
            cd = item.get("contentDetails", {})
            st = item.get("statistics", {})
            pub_iso = sn.get("publishedAt", "")
            ts = None
            if pub_iso:
                ts = datetime.fromisoformat(pub_iso.replace("Z", "+00:00")).timestamp()
            result[vid] = {
                "id": vid,
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "language": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
                "duration": _parse_iso_duration(cd.get("duration", "")),
                "view_count": int(st.get("viewCount") or 0),
                "timestamp": ts,
                "webpage_url": f"https://www.youtube.com/watch?v={vid}",
            }
    return result


def hunt_viral_video(output_path=None, max_age_days=15):
    """
    Minera Shorts BRASILEIROS em alta de trends (estilo TikTok/Reels), humor,
    influenciadores e curiosidades atuais, ranqueando por velocidade viral (views/dia)
    e outlier score.
    """
    if output_path is None:
        output_path = os.path.join(TEMP_DIR, "viral_raw.mp4")

    import yt_dlp

    used_ids = set(load_history().get("used_ids", []))
    hdrs = {"Accept-Language": "pt-BR,pt;q=0.9"}
    flat_opts = {
        "quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
        "ignoreerrors": True, "skip_download": True, "playlistend": 12,
        "http_headers": hdrs,
    }
    full_opts = {
        "quiet": True, "no_warnings": True, "ignoreerrors": True,
        "skip_download": True, "http_headers": hdrs,
    }

    feeds = [(f"https://www.youtube.com/hashtag/{tag}/shorts", f"#{tag}", True) for tag in BR_HASHTAG_FEEDS]
    feeds += [(f"https://www.youtube.com/{ch}/shorts", ch, False) for ch in SOURCE_CHANNELS]
    random.shuffle(feeds)

    candidates = []
    seen_cand = set()
    with yt_dlp.YoutubeDL(flat_opts) as ydl_flat:
        for url, label, is_tag in feeds[:16]:
            info = ydl_flat.extract_info(url, download=False) or {}
            es = [e for e in (info.get("entries") or []) if e and e.get("id")]
            if not es:
                continue
            views = sorted((e.get("view_count") or 0) for e in es)
            median = max(1, views[len(views) // 2])
            for e in es:
                vid = e["id"]
                if vid in used_ids or vid in seen_cand or _is_blocked(e.get("title")):
                    continue
                v = e.get("view_count") or 0
                if v < 50_000:
                    continue
                seen_cand.add(vid)
                e["_outlier"] = min(5.0, v / median)
                e["_source"] = label
                e["_tag_bonus"] = 1.25 if is_tag else 1.0
                candidates.append(e)
            print(f"[HUNTER BR] {label}: {len(es)} shorts, mediana {median:,}")

    # Ordena candidatos dando prioridade a alto alcance + outlier
    candidates.sort(key=lambda x: ((x.get("view_count") or 0) * x["_outlier"] * x["_tag_bonus"]), reverse=True)

    scored = []
    fallback_scored = []
    top_candidates = candidates[:36]
    api_meta = _fetch_videos_metadata_api([c["id"] for c in top_candidates])
    cookie_file = _get_youtube_cookies_file()
    if cookie_file:
        full_opts["cookiefile"] = cookie_file
        print("[HUNTER BR] Cookies autenticados carregados para download.")

    ydl_full = yt_dlp.YoutubeDL(full_opts) if not api_meta else None
    try:
        for e in top_candidates:
            full = api_meta.get(e["id"])
            if not full and ydl_full:
                full = ydl_full.extract_info(f"https://www.youtube.com/watch?v={e['id']}", download=False)
            if not full or _is_blocked(full.get("title")):
                continue
            if _looks_non_brazilian(full):
                continue
            dur = full.get("duration") or 0
            if not (10 <= dur <= 55):
                continue
            vpd, age = _views_per_day(full)
            full["_outlier"] = e["_outlier"]
            full["_source"] = e["_source"]
            # Prioridade máxima para trends quentes das últimas 24h-72h + duração ágil (12-34s)
            recency_bonus = 3.2 if age <= 3.0 else (1.8 if age <= 7.0 else (1.1 if age <= 15.0 else 0.7))
            dur_bonus = 1.25 if 12 <= dur <= 34 else 1.0
            score = vpd * (0.5 + min(e["_outlier"], 4.0)) * e["_tag_bonus"] * recency_bonus * dur_bonus
            item = (score, vpd, age, full)
            if age <= max_age_days:
                scored.append(item)
            elif age <= 45:
                fallback_scored.append(item)
    finally:
        if ydl_full:
            ydl_full.close()

    if not scored:
        scored = fallback_scored
    scored.sort(key=lambda x: x[0], reverse=True)

    for _, vpd, age, full in scored:
        vid_id = full["id"]
        print(f"[HUNTER BR] Selecionado ({full.get('_source')}): {full.get('title')} | "
              f"{full.get('view_count'):,} views | {age:.1f} dias | {vpd:,.0f} views/dia")
        if os.path.exists(output_path):
            os.remove(output_path)
        dl_opts = {
            "format": "bestvideo[ext=mp4][height<=1920]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "outtmpl": output_path, "ffmpeg_location": FFMPEG_EXE,
            "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
        }
        if cookie_file:
            dl_opts["cookiefile"] = cookie_file
        try:
            with yt_dlp.YoutubeDL(dl_opts) as ydl_dl:
                ydl_dl.download([full["webpage_url"]])
        except Exception as err:
            print(f"[HUNTER BR] Falhou download ({err}), próximo...")
            continue
        if os.path.exists(output_path) and os.path.getsize(output_path) > 50_000:
            return {
                "id": vid_id,
                "source": full.get("_source", ""),
                "title": full.get("title", ""),
                "description": (full.get("description") or "")[:800],
                "duration": full.get("duration", 25),
                "views": full.get("view_count", 0),
                "views_per_day": int(vpd),
                "age_days": round(age, 1),
                "outlier_score": round(full.get("_outlier", 1.0), 2),
                "url": full["webpage_url"],
                "path": output_path,
            }

    raise RuntimeError("Nenhum viral brasileiro recente encontrado.")


if __name__ == "__main__":
    print(json.dumps(hunt_viral_video(), indent=2, ensure_ascii=False))
