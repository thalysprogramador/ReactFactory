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
    "Davy Jones e Bistecone em choque na primeira missão do GTA 6 ao vivo: o detalhe que ninguém esperava",
    "Funções secretas do celular no GTA 6 que deixaram os streamers de queixo caído nas lives",
    "Bistecone testando a velocidade dos barcos e o oceano de Leonida Keys no GTA 6 ao vivo",
    "O início do GTA 6 com Lucia na prisão: a reação do Davy Jones (Gameplayrj) ao ver os gráficos reais",
    "Explorando a praia de Vice City no GTA 6 ao vivo: a inteligência artificial absurda dos NPCs",
    "Como a polícia do GTA 6 encurrala o jogador: o momento mais tenso das lives de lançamento",
    "Davy Jones descobrindo o tamanho real do mapa de Vice City e Leonida nas primeiras horas de GTA 6",
    "Física de batidas e destruição de carros no GTA 6 ao vivo: o teste que parou a live do Bistecone",
    "7 segredos insanos que os streamers já descobriram na primeira hora jogando GTA 6 no PS5 Pro",
    "Lucia e Jason no primeiro assalto do GTA 6: tudo que rolou nas lives de Gameplayrj e Flow Games",
]

GTA6_LONG_ANGLES = [
    "GTA 6 LANÇADO: O MELHOR DAS LIVES DO DAVY JONES E BISTECONE NAS PRIMEIRAS HORAS EM VICE CITY",
    "O INÍCIO DO GTA 6 COMPLETO: ANÁLISE DA PRIMEIRA MISSÃO, REAÇÕES AO VIVO E SEGREDOS DE LEONIDA",
    "TUDO QUE DESCOBRIRAM NAS LIVES DE GTA 6 HOJE: CELULAR, FÍSICA RAGE 9, MAPA E IA DOS NPCS",
    "DAVY JONES, BISTECONE E SANINPLAY NO GTA 6: OS MOMENTOS MAIS INSANOS DO LANÇAMENTO AO VIVO",
    "EXPLORANDO VICE CITY E LEONIDA KEYS NO GTA 6: O QUE REALMENTE MUDOU NA GAMEPLAY REAL",
    "7 FUNÇÕES E MECÂNICAS SECRETAS DO GTA 6 QUE DEIXARAM OS STREAMERS EM CHOQUE NAS LIVES",
    "A HISTÓRIA DE LUCIA E JASON NO GTA 6: ANÁLISE COMPLETA DO INÍCIO DO JOGO E PRIMEIRAS MISSÕES",
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

    # Busca ativa em tempo real das lives de Davy Jones (Gameplayrj), Bistecone, SanInPlay, Flow Games e Alanzoka
    try:
        from producao.catalog import discover_live_creator_videos  # noqa: WPS433

        live_vids = discover_live_creator_videos(max_per_query=2)
        seen_v = {r["id"] for r in top_refs}
        for lv in live_vids:
            if lv["id"] not in seen_v:
                top_refs.append(lv)
                seen_v.add(lv["id"])
    except Exception as e_lv:
        print(f"[GTA6 LIVE DISCOVERY] Aviso: {e_lv}")

    top_refs.sort(key=lambda x: x.get("views", 0), reverse=True)

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


def _build_rockstar_montage_clip(mp4_vault, jpg_vault, output_path, bgm_path=None, angle_text="", research_data=None, v5_clips=None):
    """Monta um clipe dinâmico multi-cenas (~24s) 100% em VÍDEO REAL COM ÁUDIO ORIGINAL das cenas pesquisadas."""
    from producao.catalog import select_semantic_assets  # noqa: WPS433

    sem = select_semantic_assets(
        [
            {"narration": angle_text, "headline": angle_text, "callout": "GTA 6"},
            {"narration": "gameplay bugs segredos vice city lucia jason", "headline": "LEONIDA"},
        ],
        prefer_horizontal=False,
        research_data=research_data,
        ffmpeg_exe=FFMPEG_EXE,
    )
    sem_vids = list(v5_clips or [])
    for item in sem:
        for v in item.get("video_clips", []):
            if v not in sem_vids and os.path.exists(v):
                sem_vids.append(v)

    picks = sem_vids + [p for p in mp4_vault if p not in sem_vids]
    chosen = picks[:6] if picks else list(mp4_vault)[:5]
    segs = []
    for i, src in enumerate(chosen):
        seg_p = os.path.join(GTA6_TEMP_DIR, f"short_cut_{i}.mp4")
        d = min(4.2, max(3.0, get_media_duration(src)))
        # Mantém proporção 1920x1080 original SEM CORTE e PRESERVA ÁUDIO ORIGINAL (ou anullsrc se o clipe for mudo)
        r_has_aud = subprocess.run(
            [FFMPEG_EXE, "-y", "-t", f"{d:.2f}", "-i", src,
             "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1",
             "-map", "0:v:0", "-map", "0:a:0",
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", seg_p],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
        if r_has_aud.returncode != 0 or not os.path.exists(seg_p) or os.path.getsize(seg_p) < 50_000:
            subprocess.run([
                FFMPEG_EXE, "-y", "-t", f"{d:.2f}", "-i", src,
                "-f", "lavfi", "-t", f"{d:.2f}", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1",
                "-map", "0:v:0", "-map", "1:a:0", "-shortest",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", seg_p,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segs.append(seg_p)

    concat_txt = os.path.join(GTA6_TEMP_DIR, "short_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"file '{os.path.abspath(s).replace(chr(92), '/')}'\n")

    subprocess.run([
        FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c", "copy", output_path,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return get_media_duration(output_path)


def hunt_gta6_short_source(output_path=None):
    """
    Retorna fonte + research_brief para um Short PRO de GTA 6:
    alterna entre cortes reais do TikTok gamer BR e montagens oficiais 1080p da Rockstar Games.
    """
    if output_path is None:
        output_path = os.path.join(GTA6_TEMP_DIR, "viral_raw.mp4")

    research = research_gta6_references(kind="short")
    v5_clips = []
    try:
        from producao.pesquisa_ao_vivo import pesquisar_do_zero  # noqa: WPS433

        pauta_v5, v5_moms = pesquisar_do_zero(FFMPEG_EXE)
        if v5_moms:
            research["v5_momentos"] = v5_moms
            v5_clips = [m["clip"] for m in v5_moms if m.get("clip") and os.path.exists(m["clip"])]
            if pauta_v5.get("pauta_short", {}).get("tema"):
                research["chosen_angle"] = pauta_v5["pauta_short"]["tema"]
    except Exception as err_v5:
        print(f"[PESQUISA V5 SHORT] Aviso fallback: {err_v5}", flush=True)

    mp4_vault, jpg_vault = sync_rockstar_gta6_vault(max_mp4=10, max_jpg=20)
    used_ids = set(load_history().get("used_ids", [])) | set(load_gta6_history().get("used_ids", []))

    dur = _build_rockstar_montage_clip(
        mp4_vault, jpg_vault, output_path, angle_text=research["chosen_angle"], research_data=research, v5_clips=v5_clips
    )
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
