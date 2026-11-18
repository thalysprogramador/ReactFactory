import json
import os
import random
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
ROOT_DIR = os.path.dirname(BASE_DIR)
GTA6_TEMP_DIR = os.path.join(BASE_DIR, "temp_gta6")
GTA6_VAULT_DIR = os.path.join(GTA6_TEMP_DIR, "vault")
GTA6_HISTORY_FILE = os.path.join(DATA_DIR, "history_gta6.json")

sys.path.insert(0, BASE_DIR)
from composer import FFMPEG_EXE, get_media_duration  # noqa: E402
from hunter import _ensure_h264_mp4, _fetch_videos_metadata_api, _is_blocked, load_history  # noqa: E402

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(GTA6_VAULT_DIR, exist_ok=True)

# Canais de referência verificados (feeds RSS públicos = ZERO consumo de quota search.list!)
GTA6_REFERENCE_CHANNELS = {
    "Rockstar Games": "UC6VcWc1rAoWdBCM0JxrRQ3A",
    "Rockstar Games Brasil": "UCv-czORaMV_EiaRVHz5ECxA",
    "Gameplayrj": "UCJAbkIY17zAmCTNQHH0bQoQ",
    "BRKsEDU": "UCWKtHaeXVzUscYGcm0hEunw",
    "Flow Games": "UCUZfhX79dQrJvAgYefiXCCA",
    "Gigaton Games": "UCAjKLSz8h3XJM5CSJWvmoNA",
    "SanInPlay": "UCiQotbmKsXF1n3xp3MYvoiw",
    "Games EduUu": "UCYzp8-P162Em-3uZnCuGJOg",
    "TGG": "UChLDRvS2OeJ0f5Xi2j7uofA",
    "PlayStationGrenade": "UC-KM4Su6AEkUNea4TnYbBBg",
    "Sev7n Games OFICIAL": "UCvpGyfQIzrghmPdm7KUDFmg",
}

GTA6_TIKTOK_CREATORS = [
    "@saninplay", "@gigatongames", "@gameplayrj", "@flowgames",
    "@rockstargames", "@gta6brasil", "@davyjones", "@brksedu",
    "@gameseduuu", "@sev7ngames",
]

GTA6_SHORT_ANGLES = [
    "5 segredos absurdos confirmados para o GTA 6 que ninguém percebeu no trailer",
    "Como o sistema de polícia e NPCs com IA do GTA 6 vai destruir o GTA 5",
    "Por que o lançamento do GTA 6 na quinta-feira vai parar a internet mundial",
    "Os detalhes mais realistas de Vice City e Leonida revelados pela Rockstar",
    "Teorias chocantes sobre a história de Lucia e Jason no GTA 6",
    "Coisas insanas do mapa gigante de GTA 6 comparadas com o GTA 5",
    "O preço e as edições do GTA 6: o que realmente vale a pena no dia do lançamento",
    "Carros, motos, barcos e física revolucionária confirmada no GTA 6",
]

GTA6_LONG_ANGLES = [
    "COMO VAI SER O DIA DO LANÇAMENTO DO GTA 6 (A QUINTA-FEIRA QUE VAI PARAR O MUNDO)",
    "TUDO QUE A ROCKSTAR ESCONDEU NO GTA 6: SEGREDOS, MAPA E TEORIAS QUE VOCÊ PERDEU",
    "POR QUE O GTA 6 VAI MUDAR OS GAMES PARA SEMPRE (E NADA SERÁ IGUAL DEPOIS DE QUINTA)",
    "AS PRIMEIRAS HORAS JOGANDO GTA 6: O GUIA DEFINITIVO DE LEONIDA E VICE CITY",
    "7 MECÂNICAS REVOLUCIONÁRIAS QUE CONSERTAM TODOS OS ERROS DO GTA 5 NO GTA 6",
    "A VERDADE POR TRÁS DE LUCIA E JASON: ANÁLISE PROFUNDA DA HISTÓRIA DO GTA 6",
]

_GTA_TERMS = ("gta", "grand theft auto", "rockstar", "vice city", "leonida", "lucia", "jason")


def load_gta6_history():
    if os.path.exists(GTA6_HISTORY_FILE):
        try:
            with open(GTA6_HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"used_ids": [], "short_angles": [], "long_angles": [], "posts": []}


def save_gta6_history(video_id=None, angle=None, kind="short", metadata=None):
    hist = load_gta6_history()
    if video_id and video_id not in hist["used_ids"]:
        hist["used_ids"].append(video_id)
    if angle:
        bucket = "short_angles" if kind == "short" else "long_angles"
        if angle not in hist[bucket]:
            hist[bucket].append(angle)
    if metadata:
        hist.setdefault("posts", []).append(metadata)
    with open(GTA6_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, indent=2, ensure_ascii=False)


def _is_gta_related(text):
    t = (text or "").lower()
    return any(k in t for k in _GTA_TERMS)


def research_gta6_references(kind="short"):
    """
    Pesquisa referências virais REAIS de canais grandes (RSS sem gastar quota search.list + 1 chamada videos.list)
    + notícias atuais de lançamento + busca aberta Gemini sobre GTA 6.
    """
    hdr = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/131.0.0.0"}
    rss_entries = []
    ns = {"yt": "http://www.youtube.com/xml/schemas/2015", "atom": "http://www.w3.org/2005/Atom"}

    for ch_name, ch_id in GTA6_REFERENCE_CHANNELS.items():
        try:
            url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=8) as r:
                root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
            for ent in root.findall("atom:entry", ns)[:8]:
                title = (ent.findtext("atom:title", default="", namespaces=ns) or "").strip()
                vid = (ent.findtext("yt:videoId", default="", namespaces=ns) or "").strip()
                if vid and title and _is_gta_related(title):
                    rss_entries.append((vid, ch_name, title))
        except Exception:
            pass

    api_meta = _fetch_videos_metadata_api([e[0] for e in rss_entries[:45]]) if rss_entries else {}
    top_refs = []
    for vid, ch_name, title in rss_entries:
        m = api_meta.get(vid, {})
        views = int(m.get("view_count") or 0)
        top_refs.append({
            "id": vid,
            "channel": ch_name,
            "title": title,
            "views": views,
            "duration": m.get("duration", 0),
        })
    top_refs.sort(key=lambda x: x["views"], reverse=True)

    news_headlines = []
    for q in ["GTA 6 lançamento novidades", "GTA 6 segredos trailer mapa"]:
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
            req = urllib.request.Request(url, headers=hdr)
            with urllib.request.urlopen(req, timeout=8) as r:
                root = ET.fromstring(r.read().decode("utf-8", errors="replace"))
            for it in root.findall(".//item")[:5]:
                t = (it.findtext("title") or "").strip()
                if t and not _is_blocked(t):
                    news_headlines.append(t)
        except Exception:
            pass

    # Busca aberta leve no Gemini Google Search para hipóteses/detalhes quentes de lançamento na quinta
    grounding_notes = ""
    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not gemini_key:
        sec = os.path.join(ROOT_DIR, "_render_secrets", "1_GEMINI_API_KEY.txt")
        if os.path.exists(sec):
            with open(sec, "r", encoding="utf-8") as f:
                gemini_key = f.read().strip()
    if gemini_key:
        try:
            payload = {
                "contents": [{"parts": [{"text": (
                    "Resuma em 6 tópicos curtos em português as novidades, segredos, hipóteses de gameplay, "
                    "mapa de Leonida/Vice City e expectativa de lançamento mais comentados AGORA sobre GTA 6 "
                    "por canais gamers e comunidade."
                )}]}],
                "tools": [{"google_search": {}}],
                "generationConfig": {"temperature": 0.3},
            }
            req = urllib.request.Request(
                f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_key}",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=25) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            grounding_notes = body.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")[:900]
        except Exception as err:
            print(f"[GTA6 RESEARCH] Aviso Gemini grounding: {err}")

    hist = load_gta6_history()
    pool_angles = GTA6_SHORT_ANGLES if kind == "short" else GTA6_LONG_ANGLES
    used_angles = set(hist.get("short_angles" if kind == "short" else "long_angles", []))
    avail = [a for a in pool_angles if a not in used_angles] or pool_angles
    chosen_angle = random.choice(avail)

    print(
        f"[GTA6 RESEARCH] Refs virais={len(top_refs)} | Notícias={len(news_headlines)} | "
        f"Ângulo escolhido='{chosen_angle[:60]}'"
    )
    return {
        "chosen_angle": chosen_angle,
        "top_references": top_refs[:12],
        "news_headlines": news_headlines[:8],
        "grounding_notes": grounding_notes,
    }


def sync_rockstar_gta6_vault(max_mp4=10, max_jpg=22):
    """
    Baixa vídeos MP4 oficiais em alta definição (1920px/1280px) e screenshots 4K direto da Rockstar Games (/VI),
    garantindo acervo visual oficial 100% compatível com H.264/OpenCV na nuvem.
    """
    existing_mp4 = sorted(
        os.path.join(GTA6_VAULT_DIR, f) for f in os.listdir(GTA6_VAULT_DIR)
        if f.startswith("mp4_") and f.endswith(".mp4") and os.path.getsize(os.path.join(GTA6_VAULT_DIR, f)) > 80_000
    )
    existing_jpg = sorted(
        os.path.join(GTA6_VAULT_DIR, f) for f in os.listdir(GTA6_VAULT_DIR)
        if f.startswith("img_") and f.endswith(".jpg") and os.path.getsize(os.path.join(GTA6_VAULT_DIR, f)) > 40_000
    )
    if len(existing_mp4) >= min(6, max_mp4) and len(existing_jpg) >= min(14, max_jpg):
        print(f"[GTA6 VAULT] Cache pronto: {len(existing_mp4)} MP4s + {len(existing_jpg)} JPGs oficiais Rockstar.")
        return existing_mp4, existing_jpg

    print("[GTA6 VAULT] Sincronizando trailers/cenas e artworks oficiais de rockstargames.com/VI...")
    hdr = {"User-Agent": "Mozilla/5.0"}
    html = urllib.request.urlopen(urllib.request.Request("https://www.rockstargames.com/VI", headers=hdr), timeout=20).read().decode("utf-8", errors="replace")
    all_media = sorted(set(m.split("?")[0].replace("&amp;", "") for m in re.findall(r"/_next/static/media/[^\s\"'<>\\]+", html)))

    mp4_1920 = [f"https://www.rockstargames.com/VI{m}" for m in all_media if m.endswith(".mp4") and "1920_av1" in m]
    mp4_1280 = [f"https://www.rockstargames.com/VI{m}" for m in all_media if m.endswith(".mp4") and ("1280_hvec" in m or "1280_av1" in m)]
    mp4_urls = mp4_1920 + [u for u in mp4_1280 if u not in mp4_1920]

    # Filtra JPGs grandes (exclui variantes localizadas repetidas de pré-venda)
    jpg_urls = [
        f"https://www.rockstargames.com/VI{m}" for m in all_media
        if m.endswith(".jpg") and not any(loc in m for loc in ("_fr_fr", "_ja_jp", "_ko_kr", "_zh_", "_de_de", "_es_es"))
    ]
    random.shuffle(jpg_urls)

    downloaded_jpg = list(existing_jpg)
    for idx, u in enumerate(jpg_urls[:max_jpg]):
        dst = os.path.join(GTA6_VAULT_DIR, f"img_{idx:02d}.jpg")
        if os.path.exists(dst) and os.path.getsize(dst) > 40_000:
            if dst not in downloaded_jpg:
                downloaded_jpg.append(dst)
            continue
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=15) as r:
                data = r.read()
            if len(data) > 40_000:
                with open(dst, "wb") as f:
                    f.write(data)
                downloaded_jpg.append(dst)
        except Exception:
            pass

    # Substitui os vídeos de máscara/sticker do site por clipes reais 1080p dos trailers oficiais da Rockstar
    from producao.catalog import extract_real_trailer_clips, is_sticker_mask_video  # noqa: WPS433

    trailers_dir = os.path.join(GTA6_TEMP_DIR, "trailers")
    os.makedirs(trailers_dir, exist_ok=True)
    for t_name, t_url in [
        ("preload_now", "https://www.youtube.com/watch?v=sXCiA142w8Y"),
        ("extended_look", "https://www.youtube.com/watch?v=f-prPijSTLo"),
        ("the_festival", "https://www.youtube.com/watch?v=AvBcfBrBl60"),
    ]:
        tp = os.path.join(trailers_dir, f"{t_name}.mp4")
        if not (os.path.exists(tp) and os.path.getsize(tp) > 300_000):
            subprocess.run(
                [
                    sys.executable, "-m", "yt_dlp", "--ffmpeg-location", FFMPEG_EXE,
                    "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
                    "--merge-output-format", "mp4", "-o", tp, t_url,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    downloaded_mp4 = [p for p in extract_real_trailer_clips(FFMPEG_EXE) if not is_sticker_mask_video(p)]
    print(f"[GTA6 VAULT] Vault atualizado: {len(downloaded_mp4)} clipes reais 1080p + {len(downloaded_jpg)} JPGs 4K oficiais!")
    return downloaded_mp4, downloaded_jpg


def _try_tiktok_gta6_clip(output_path, used_ids):
    import yt_dlp

    flat_opts = {
        "quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
        "ignoreerrors": True, "skip_download": True, "playlistend": 10,
    }
    creators = list(GTA6_TIKTOK_CREATORS)
    random.shuffle(creators)
    matches = []
    with yt_dlp.YoutubeDL(flat_opts) as ydl:
        for cr in creators[:6]:
            try:
                res = ydl.extract_info(f"https://www.tiktok.com/{cr}", download=False) or {}
                for e in (res.get("entries") or []):
                    vid = str(e.get("id") or "")
                    title = (e.get("title") or e.get("description") or "").strip()
                    if not vid or vid in used_ids or f"tt_{vid}" in used_ids or _is_blocked(title):
                        continue
                    if not _is_gta_related(title):
                        continue
                    dur = e.get("duration") or 0
                    if dur and not (12 <= dur <= 52):
                        continue
                    matches.append((int(e.get("view_count") or 0), cr, e))
            except Exception:
                pass

    matches.sort(key=lambda x: x[0], reverse=True)
    for v, cr, e in matches[:6]:
        u = e.get("url") or e.get("webpage_url")
        if not u:
            continue
        vid = str(e["id"])
        if os.path.exists(output_path):
            os.remove(output_path)
        try:
            with yt_dlp.YoutubeDL({
                "outtmpl": output_path, "ffmpeg_location": FFMPEG_EXE,
                "merge_output_format": "mp4", "quiet": True, "no_warnings": True,
            }) as ydl_dl:
                ydl_dl.download([u])
            if os.path.exists(output_path) and os.path.getsize(output_path) > 60_000:
                _ensure_h264_mp4(output_path)
                return {
                    "id": f"tt_{vid}",
                    "source": f"TikTok {cr}",
                    "title": (e.get("title") or "GTA 6 Viral")[:120],
                    "description": (e.get("description") or "")[:600],
                    "duration": e.get("duration") or 24,
                    "views": v,
                    "views_per_day": v,
                    "age_days": 2.0,
                    "outlier_score": 3.0,
                    "url": u,
                    "path": output_path,
                }
        except Exception:
            pass
    return None


def _build_rockstar_montage_clip(mp4_vault, jpg_vault, output_path, bgm_path=None):
    """Monta um clipe dinâmico multi-cenas (~22s) com trailers/cenas oficiais do GTA 6 + BGM Synthwave."""
    picks = list(mp4_vault)
    random.shuffle(picks)
    chosen = picks[:5]
    segs = []
    for i, src in enumerate(chosen):
        seg_p = os.path.join(GTA6_TEMP_DIR, f"short_cut_{i}.mp4")
        d = min(4.8, max(3.2, get_media_duration(src)))
        zoom_dir = "1.04+0.0018*on" if i % 2 == 0 else "1.12-0.0018*on"
        subprocess.run([
            FFMPEG_EXE, "-y", "-t", f"{d:.2f}", "-i", src,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-an",
            seg_p,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segs.append(seg_p)

    # Adiciona 2 cenas animadas rápidas de screenshots 4K oficiais para variar ritmo
    if jpg_vault:
        import cv2
        import numpy as np

        for k_idx, img_src in enumerate(random.sample(jpg_vault, min(2, len(jpg_vault)))):
            kb_p = os.path.join(GTA6_TEMP_DIR, f"short_cut_kb_{k_idx}.mp4")
            src = cv2.imread(img_src)
            if src is not None:
                sh, sw = src.shape[:2]
                sc = max(1080.0 / sw, 1920.0 / sh)
                src = cv2.resize(src, (max(1080, int(sw * sc)), max(1920, int(sh * sc))), interpolation=cv2.INTER_AREA)
                x0, y0 = (src.shape[1] - 1080) // 2, (src.shape[0] - 1920) // 2
                src = src[y0 : y0 + 1920, x0 : x0 + 1080].copy()
                proc = subprocess.Popen(
                    [
                        FFMPEG_EXE, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1080x1920", "-r", "30", "-i", "pipe:0",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p", "-an", kb_p,
                    ],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                for fi in range(110):
                    z = 1.0 + 0.14 * (fi / 109.0) if k_idx % 2 == 0 else (1.14 - 0.12 * (fi / 109.0))
                    cw, ch = int(1080 / z), int(1920 / z)
                    cx, cy = (1080 - cw) // 2, (1920 - ch) // 2
                    fr = cv2.resize(src[cy : cy + ch, cx : cx + cw], (1080, 1920), interpolation=cv2.INTER_LINEAR)
                    proc.stdin.write(fr.tobytes())
                proc.stdin.close()
                proc.wait()
                if os.path.exists(kb_p):
                    segs.insert(min(len(segs), 1 + k_idx * 2), kb_p)

    concat_txt = os.path.join(GTA6_TEMP_DIR, "short_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"file '{os.path.abspath(s).replace(chr(92), '/')}'\n")

    silent_mp4 = os.path.join(GTA6_TEMP_DIR, "short_silent_montage.mp4")
    subprocess.run([
        FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c", "copy", silent_mp4,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    dur = get_media_duration(silent_mp4)
    bgm = bgm_path if (bgm_path and os.path.exists(bgm_path)) else os.path.join(BASE_DIR, "assets", "bgm_gta_synth.mp3")
    if os.path.exists(bgm):
        subprocess.run([
            FFMPEG_EXE, "-y", "-i", silent_mp4, "-stream_loop", "-1", "-i", bgm,
            "-t", f"{dur:.2f}",
            "-filter_complex", "[1:a]volume=0.85,aformat=sample_rates=48000:channel_layouts=stereo[a]",
            "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            output_path,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run([
            FFMPEG_EXE, "-y", "-i", silent_mp4, "-f", "lavfi", "-t", f"{dur:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", output_path,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dur


def hunt_gta6_short_source(output_path=None):
    """
    Retorna fonte + research_brief para um Short PRO de GTA 6:
    alterna entre cortes reais do TikTok gamer BR e montagens oficiais 1080p da Rockstar Games.
    """
    if output_path is None:
        output_path = os.path.join(GTA6_TEMP_DIR, "viral_raw.mp4")

    research = research_gta6_references(kind="short")
    mp4_vault, jpg_vault = sync_rockstar_gta6_vault(max_mp4=10, max_jpg=20)
    used_ids = set(load_history().get("used_ids", [])) | set(load_gta6_history().get("used_ids", []))

    # Alterna 50/50 entre clipe real do TikTok gamer BR e montagem oficial Rockstar para variar formato!
    prefer_tiktok = (len(load_gta6_history().get("posts", [])) % 2 == 1)
    if prefer_tiktok:
        tt = _try_tiktok_gta6_clip(output_path, used_ids)
        if tt:
            tt["research_brief"] = research
            tt["vault_jpgs"] = jpg_vault
            return tt

    dur = _build_rockstar_montage_clip(mp4_vault, jpg_vault, output_path)
    uid = f"gta6_official_{int(datetime.now(timezone.utc).timestamp())}"
    return {
        "id": uid,
        "source": "Rockstar Official GTA 6",
        "title": research["chosen_angle"],
        "description": research.get("grounding_notes", "")[:500],
        "duration": dur,
        "views": 1_500_000,
        "views_per_day": 500_000,
        "age_days": 1.0,
        "outlier_score": 4.0,
        "url": "https://www.rockstargames.com/VI",
        "path": output_path,
        "research_brief": research,
        "vault_jpgs": jpg_vault,
    }
