"""AGENTE PESQUISADOR AO VIVO (V5) — Descoberta ampla e em tempo real de conteúdo sobre GTA 6.

Fluxo (executado do zero a cada produção):
1. Varre o YouTube com dezenas de buscas ordenadas por data (vídeos recém-postados) e lives no ar,
   de criadores grandes E pequenos (sem lista fixa de canais).
2. Baixa as legendas automáticas (PT/EN) dos vídeos candidatos e captura trechos reais das lives no ar.
3. O Gemini (Diretor de Pauta) lê as transcrições e escolhe os MOMENTOS DO JOGO mais impactantes
   (bugs, segredos, detalhes absurdos, mecânicas novas) com timestamp exato.
4. Baixa cada momento COM ÁUDIO ORIGINAL e valida visualmente com o Gemini (é gameplay? mostra o que diz?).
"""
import base64
import glob
import json
import os
import random
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import cv2

from producao.gemini_client import gemini_text

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESEARCH_DIR = os.path.join(BASE_DIR, "temp_gta6", "pesquisa_v5")
HISTORY_V5_FILE = os.path.join(BASE_DIR, "data", "history_v5.json")
COOKIES_PATH = os.path.join(BASE_DIR, "temp_gta6", "yt_cookies_v5.txt")
YTDLP = [
    sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
    "--js-runtimes", "node,deno", "--remote-components", "ejs:github",
]


def _ensure_cookies_file():
    """Decodifica YOUTUBE_COOKIES_B64 (sempre regrava cópia limpa para evitar que o yt-dlp corrompa o cookie entre chamadas!)."""
    b64 = (os.environ.get("YOUTUBE_COOKIES_B64") or "").strip()
    if not b64:
        local_ck = os.path.join(os.path.dirname(BASE_DIR), "_render_secrets", "YOUTUBE_COOKIES_B64.txt")
        if os.path.exists(local_ck):
            b64 = open(local_ck, "r", encoding="utf-8").read().strip()
    if b64:
        try:
            os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
            # Usa arquivo por thread/pid ou regrava limpo para o yt-dlp nunca sobrescrever com sessão bloqueada
            import threading
            ck_file = f"{COOKIES_PATH}.{threading.get_ident()}.txt"
            with open(ck_file, "wb") as f:
                f.write(base64.b64decode(b64))
            return ck_file
        except Exception as err:
            print(f"[COOKIES V5] Aviso ao decodificar YOUTUBE_COOKIES_B64: {err}", flush=True)
    if os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 100:
        return COOKIES_PATH
    return None


def _ytdlp_cmd(mode="default"):
    """
    Constrói comando yt-dlp resiliente para PC residencial e nuvem (com JS runtime Node/Deno + EJS + bgutil PO Token + Proxy opcional):
    - Se YTDLP_PROXY estiver configurado (ex: proxy residencial no GitHub Secrets), passa --proxy automaticamente!
    - mode="default": yt-dlp padrão + Node/Deno EJS (funciona 100% no IP residencial!)
    - mode="pot_nocookies": sem cookies + PO Token via bgutil-pot (http://127.0.0.1:4416)
    - mode="cookies": usa cópia limpa dos cookies autenticados + PO Token bgutil-pot
    """
    cmd = list(YTDLP)
    proxy_url = (os.environ.get("YTDLP_PROXY") or "").strip()
    if proxy_url:
        cmd += ["--proxy", proxy_url]
    is_cloud = os.environ.get("GITHUB_ACTIONS") == "true"
    pot_arg = ";youtubepot-bgutilhttp:base_url=http://127.0.0.1:4416" if (is_cloud and not proxy_url) else ""

    if mode == "default":
        if is_cloud and not proxy_url:
            cmd += ["--extractor-args", f"youtube:player_client=mweb,web{pot_arg}"]
    elif mode == "pot_nocookies":
        cmd += ["--extractor-args", f"youtube:player_client=mweb,web,tv_embedded{pot_arg}"]
    elif mode == "cookies":
        ck = _ensure_cookies_file()
        if ck:
            cmd += ["--cookies", ck]
        if pot_arg:
            cmd += ["--extractor-args", f"youtube:player_client=web,mweb{pot_arg}"]
    elif mode == "alt":
        ck = _ensure_cookies_file()
        if ck:
            cmd += ["--cookies", ck]
        cmd += ["--extractor-args", f"youtube:player_client=mweb,web{pot_arg}"]
    elif mode == "tv":
        cmd += ["--extractor-args", f"youtube:player_client=tv_embedded,mweb{pot_arg}"]
    return cmd


def _load_v5_history():
    if os.path.exists(HISTORY_V5_FILE):
        try:
            return json.load(open(HISTORY_V5_FILE, encoding="utf-8"))
        except Exception:
            pass
    return {"used_video_ids": [], "used_topics": []}


def _save_v5_history(video_ids, topic=None):
    os.makedirs(os.path.dirname(HISTORY_V5_FILE), exist_ok=True)
    h = _load_v5_history()
    for vid in video_ids:
        if vid and vid not in h["used_video_ids"]:
            h["used_video_ids"].append(vid)
    if topic and topic not in h["used_topics"]:
        h["used_topics"].append(topic)
    h["used_video_ids"] = h["used_video_ids"][-300:]
    h["used_topics"] = h["used_topics"][-80:]
    with open(HISTORY_V5_FILE, "w", encoding="utf-8") as f:
        json.dump(h, f, ensure_ascii=False, indent=2)

GTA_RE = re.compile(r"gta\s*(6|vi)\b|grand theft auto vi|vice city|leonida", re.I)
BLOCK_RE = re.compile(r"trailer oficial|official trailer|react(ing)? to trailer|previs[aã]o|vai ter|teoria|before you buy|gameranx|tier list|ranking todos", re.I)

QUERY_POOL = [
    "gta 6 bug", "gta 6 bugs engraçados", "gta 6 glitch", "gta 6 segredo", "gta 6 segredos escondidos",
    "gta 6 easter egg", "gta 6 detalhes insanos", "gta 6 coisas que você não sabia", "gta 6 gameplay",
    "gta 6 gameplay pt-br", "gta 6 ao vivo", "gta 6 live", "gta 6 primeira missão", "gta 6 celular",
    "gta 6 polícia", "gta 6 física", "gta 6 npc", "gta 6 momentos engraçados", "gta 6 fails",
    "gta 6 mapa explorando", "gta 6 jacaré", "gta 6 vice beach", "gta 6 carros", "gta 6 dinheiro",
    "gta vi glitch", "gta 6 funny moments", "gta 6 hidden details", "gta 6 crazy physics",
    "gta 6 secrets found", "gta 6 first hours gameplay",
]


def _run(cmd, timeout=40):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except Exception:
        return None


def descobrir_conteudo(n_queries=16, por_query=12, ffmpeg_exe=None):
    """Busca ampla por vídeos recém-postados (ytsearchdate) + lives no ar. Retorna candidatos diversificados."""
    queries = random.sample(QUERY_POOL, min(n_queries, len(QUERY_POOL)))
    found = {}

    def _search(q):
        out = []
        if isinstance(q, tuple):
            url = q[1]
        else:
            # sp=CAI%3D -> ordenar por data de upload (recém-postados)
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}&sp=CAI%3D"
        # NUNCA usar cookies nas 20 buscas paralelas (evita que o YouTube dê rate-limit de 1h na sessão do cookie!)
        r = _run(YTDLP + ["--flat-playlist", "--dump-json", "--playlist-end", str(por_query), url], timeout=45)
        if r and r.stdout:
            for line in r.stdout.splitlines():
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return (q if isinstance(q, str) else "live"), out

    for lq in ["gta 6", "gta 6 ao vivo", "gta vi live", "gta 6 gameplay"]:
        queries.append(("__live__", f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(lq)}&sp=EgJAAQ%3D%3D"))

    with ThreadPoolExecutor(max_workers=6) as pool:
        for q, items in pool.map(_search, queries):
            for d in items:
                vid = d.get("id")
                title = d.get("title") or ""
                if not vid or vid in found or not GTA_RE.search(title) or BLOCK_RE.search(title):
                    continue
                found[vid] = {
                    "id": vid,
                    "title": title,
                    "channel": d.get("channel") or d.get("uploader") or "Criador",
                    "duration": d.get("duration") or 0,
                    "views": int(d.get("view_count") or 0),
                    "live": (d.get("live_status") == "is_live") or (not d.get("duration")),
                    "query": q,
                }

    hist = _load_v5_history()
    used_ids = set(hist.get("used_video_ids") or [])
    per_ch = {}
    cands = []
    for c in sorted(found.values(), key=lambda x: x["views"], reverse=True):
        if c["id"] in used_ids:
            continue
        ch = c["channel"]
        if per_ch.get(ch, 0) >= 2:
            continue
        per_ch[ch] = per_ch.get(ch, 0) + 1
        cands.append(c)
    print(f"[PESQUISA V5] {len(found)} vídeos encontrados em {len(queries)} buscas | {len(cands)} candidatos "
          f"de {len(per_ch)} canais diferentes ({sum(1 for c in cands if c['live'])} lives no ar).", flush=True)
    return cands


def _vtt_to_lines(vtt_text):
    """Converte VTT em linhas '[mm:ss] texto' deduplicadas (legenda automática repete muito)."""
    lines, last = [], ""
    cur_t = None
    for raw in vtt_text.splitlines():
        m = re.match(r"(\d+):(\d+):(\d+)\.\d+ -->", raw)
        if m:
            cur_t = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            continue
        txt = re.sub(r"<[^>]+>", "", raw).strip()
        if not txt or txt.startswith(("WEBVTT", "Kind:", "Language:")) or cur_t is None:
            continue
        if txt == last or txt in last:
            continue
        last = txt
        lines.append((cur_t, txt))
    merged, bucket, b_t = [], [], None
    for t, txt in lines:
        if b_t is None:
            b_t = t
        bucket.append(txt)
        if t - b_t >= 12:
            merged.append(f"[{b_t // 60}:{b_t % 60:02d}] {' '.join(bucket)}")
            bucket, b_t = [], None
    if bucket:
        merged.append(f"[{b_t // 60}:{b_t % 60:02d}] {' '.join(bucket)}")
    return merged


def baixar_transcricoes(cands, max_videos=14, max_chars=26000):
    os.makedirs(RESEARCH_DIR, exist_ok=True)
    vods = [c for c in cands if not c["live"] and 90 <= (c["duration"] or 0) <= 4 * 3600][:max_videos]

    def _sub(c):
        base = os.path.join(RESEARCH_DIR, f"sub_{c['id']}")
        for f in glob.glob(base + "*"):
            os.remove(f)
        files = []
        sub_modes = ("pot_nocookies", "cookies", "default") if os.environ.get("GITHUB_ACTIONS") == "true" else ("default", "cookies")
        for mode in sub_modes:
            _run(_ytdlp_cmd(mode=mode) + [
                "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "pt.*,pt,en.*,en",
                "--sub-format", "vtt", "-o", base, f"https://www.youtube.com/watch?v={c['id']}"
            ], timeout=45)
            files = sorted(glob.glob(base + "*.vtt"), key=lambda p: (".pt" not in p, len(p)))
            if files:
                break
        if not files:
            return None
        txt = "\n".join(_vtt_to_lines(open(files[0], encoding="utf-8", errors="replace").read()))
        if len(txt) > max_chars:
            # amostra uniforme ao longo do vídeo para cobrir tudo
            chunk = max_chars // 6
            step = len(txt) // 6
            txt = "\n...\n".join(txt[i * step: i * step + chunk] for i in range(6))
        c["transcript"] = txt
        return c

    with ThreadPoolExecutor(max_workers=5) as pool:
        ok = [c for c in pool.map(_sub, vods) if c and c.get("transcript")]

    # Inclui também vídeos curtos/médios (40s-300s) de criadores pequenos/médios (ex: bugs, segredos, fails)
    # mesmo sem legenda automática, usando título + duração para o Diretor de Pauta selecionar trechos reais!
    seen_ids = {c["id"] for c in ok}
    short_picks = [
        c for c in cands
        if not c["live"] and c["id"] not in seen_ids and 35 <= (c["duration"] or 0) <= 300
    ][:8]
    for sp in short_picks:
        dur = int(sp.get("duration") or 60)
        sp["transcript"] = (
            f"[0:08] (Vídeo curto/direto sem legenda automática — duração total {dur}s. "
            f"Título: {sp['title']}. Sugestão de janela: start=8 end={min(dur - 2, 24)})"
        )
        ok.append(sp)

    print(f"[PESQUISA V5] Transcrições/Candidatos analisáveis: {len(ok)} ({len(short_picks)} vídeos curtos de criadores variados)", flush=True)
    return ok


def capturar_lives(cands, ffmpeg_exe, max_lives=3, secs=40):
    """Grava os últimos ~40s de lives que estão no ar AGORA (com áudio) para o Diretor de Pauta avaliar."""
    os.makedirs(RESEARCH_DIR, exist_ok=True)
    lives = [c for c in cands if c["live"]][:max_lives]
    caps = []
    for c in lives:
        url = ""
        for mode in ("default", "cookies"):
            r = _run(_ytdlp_cmd(mode=mode) + ["-g", "-f", "best[height<=720]/best", f"https://www.youtube.com/watch?v={c['id']}"], timeout=30)
            url = (r.stdout.strip().splitlines() or [""])[0] if r and r.stdout else ""
            if url:
                break
        if not url:
            continue
        dst = os.path.join(RESEARCH_DIR, f"live_{c['id']}.mp4")
        subprocess.run([ffmpeg_exe, "-y", "-i", url, "-t", str(secs), "-c", "copy", dst],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=secs + 40)
        if os.path.exists(dst) and os.path.getsize(dst) > 200_000:
            c["capture"] = dst
            caps.append(c)
    print(f"[PESQUISA V5] Lives no ar capturadas: {len(caps)}", flush=True)
    return caps


def _frames_b64(mp4, n=4, size=512):
    cap = cv2.VideoCapture(mp4)
    tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(tot * (0.12 + 0.76 * i / max(1, n - 1))))
        ok, fr = cap.read()
        if ok:
            h, w = fr.shape[:2]
            s = size / max(h, w)
            fr = cv2.resize(fr, (int(w * s), int(h * s)))
            out.append(base64.b64encode(cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]).decode())
    cap.release()
    return out


def escolher_pauta(transcritos, lives_cap):
    """Diretor de Pauta: escolhe os momentos DO JOGO mais fortes para o vídeo longo e para o Short."""
    blocos = []
    for c in transcritos:
        blocos.append(f"### VIDEO id={c['id']} | canal={c['channel']} | views={c['views']} | titulo={c['title']}\n{c['transcript']}")
    parts_extra = []
    for c in lives_cap:
        blocos.append(f"### LIVE NO AR id={c['id']} | canal={c['channel']} | titulo={c['title']} | "
                      f"(imagens anexadas: capturei os últimos 40s; use start=0 end=40 se valer a pena)")
        for b in _frames_b64(c["capture"], n=3):
            parts_extra.append({"inline_data": {"mime_type": "image/jpeg", "data": b}})

    prompt = f"""Você é o DIRETOR DE PAUTA de um canal brasileiro de GTA 6. O jogo acabou de ser lançado.
Abaixo estão transcrições (com timestamps [min:seg]) de vídeos recém-postados e lives de criadores GRANDES E PEQUENOS.

OBJETIVO: encontrar os MOMENTOS DO JOGO mais impactantes — bugs bizarros, segredos/easter eggs, detalhes absurdos de realismo,
mecânicas novas, cenas engraçadas/loucas de física, NPCs, polícia, celular, mapa. O protagonista é SEMPRE O JOGO (nunca a reação do streamer).
Use as falas do streamer só como pista do que está aparecendo na tela naquele instante.

REGRAS:
- Cada momento: janela de 18 a 24 segundos onde a ação ACONTECE na tela (start/end em segundos absolutos do vídeo) para cobrir o bloco inteiro para frente sem cortar nem reverter!
- PROIBIDO escolher momentos de trailer oficial, tela de logo do GTA VI, tela de pré-venda, menu, carregamento, conversa com chat, propaganda ou só webcam.
- Varie canais (no máximo 2 momentos do mesmo vídeo) e varie assuntos.
- Selecione 18 momentos candidatos (vou validar visualmente quadro a quadro e descartar os fracos).
- Depois proponha 1 pauta de VÍDEO LONGO e 1 pauta de SHORT (formato de alta retenção: "Top N", "coisas escondidas", "bugs insanos" ou descoberta específica de gameplay).

{chr(10).join(blocos)}

Responda APENAS um objeto JSON (não lista):
{{
 "momentos": [{{"mid": "m1", "video_id": "...", "canal": "...", "start": 0, "end": 22, "assunto": "bug|segredo|detalhe|mecanica|engracado|mapa", "o_que_acontece": "descrição objetiva do que aparece no jogo", "potencial": 1-10}}],
 "pauta_longo": {{"tema": "...", "angulo": "...", "mids_sugeridos": ["m1","m2","..."]}},
 "pauta_short": {{"tema": "...", "formato": "top_n|descoberta|lista", "mids_sugeridos": ["..."]}}
}}"""
    data, model = gemini_text(prompt, json_mode=True, temperature=0.5, parts_extra=parts_extra or None)
    if isinstance(data, list):
        data = data[0] if (data and isinstance(data[0], dict)) else {"momentos": data, "pauta_longo": {}, "pauta_short": {}}
    print(f"[DIRETOR DE PAUTA] {len(data.get('momentos', []))} momentos escolhidos via {model} | "
          f"Longo='{(data.get('pauta_longo') or {}).get('tema')}' | Short='{(data.get('pauta_short') or {}).get('tema')}'", flush=True)
    return data


def baixar_e_validar_momentos(momentos, cands_by_id, ffmpeg_exe, pad=1.0):
    """Baixa cada momento (18-24s contínuos PARA FRENTE) COM ÁUDIO ORIGINAL (720p) e valida visualmente com Gemini."""
    clips_dir = os.path.join(RESEARCH_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    def _dl(m):
        vid = m["video_id"]
        cand = cands_by_id.get(vid, {})
        dst = os.path.join(clips_dir, f"{m['mid']}_{vid}.mp4")
        if cand.get("capture"):
            src = cand["capture"]
            s = max(0.0, float(m.get("start", 0)))
            e = min(40.0, max(s + 18.0, float(m.get("end", s + 22))))
            subprocess.run([ffmpeg_exe, "-y", "-ss", f"{s:.2f}", "-i", src, "-t", f"{max(10.0, e - s):.2f}",
                            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1",
                            "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            s = max(0.0, float(m.get("start", 0)) - pad)
            e = float(m.get("end", s + 20)) + pad
            # Garante janelas longas (18s a 24s) para o clipe rodar 100% PARA FRENTE durante o bloco inteiro!
            if e - s < 18.0:
                e = s + 20.0
            e = min(e, s + 24.0)
            dur_req = max(12.0, e - s)
            raw = dst + ".raw.mp4"
            trimmed_in_raw = False
            last_err = ""

            # No GitHub Actions (nuvem), prioriza pot_nocookies (PO Token via bgutil sem gastar rate-limit da conta!)
            # e usa --downloader ffmpeg com -ss/-to direto (funciona em VODs longos sem erro 4294967262!).
            if os.environ.get("GITHUB_ACTIONS") == "true":
                strategies = [
                    ("default", "sections", "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b")
                    if os.environ.get("YTDLP_PROXY")
                    else ("pot_nocookies", "ffmpeg_slice", "bv*[height<=720]+ba/b[height<=720]/b"),
                    ("cookies", "ffmpeg_slice", "bv*[height<=720]+ba/b[height<=720]/b"),
                    ("cookies", "sections", "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"),
                ]
            else:
                # Local residencial: 2 estratégias rápidas (timeout 40s) -> baixa 15 clipes em ~2 min em vez de 25 min!
                strategies = [
                    ("default", "sections", "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/bv*[height<=720]+ba/b[height<=720]/b"),
                    ("default", "ffmpeg_slice", "bv*[height<=720]+ba/b[height<=720]/b"),
                ]
            errs = []
            for mode, cut_mode, fmt in strategies:
                if os.path.exists(raw):
                    try:
                        os.remove(raw)
                    except OSError:
                        pass
                cmd = _ytdlp_cmd(mode=mode) + [
                    "--ffmpeg-location", ffmpeg_exe, "-f", fmt,
                    "--merge-output-format", "mp4", "-o", raw,
                ]
                if cut_mode == "sections":
                    cmd += ["--download-sections", f"*{s:.0f}-{e:.0f}", "--force-keyframes-at-cuts"]
                else:
                    cmd += [
                        "--downloader", "ffmpeg",
                        "--downloader-args", f"ffmpeg_i:-ss {s:.2f} -to {e:.2f}",
                    ]
                cmd.append(f"https://www.youtube.com/watch?v={vid}")
                r_dl = _run(cmd, timeout=45)
                if os.path.exists(raw) and os.path.getsize(raw) > 50_000:
                    trimmed_in_raw = True
                    break
                if r_dl and r_dl.stderr:
                    err_line = r_dl.stderr.strip().splitlines()[-1][:140]
                    errs.append(f"{mode}/{cut_mode}:{err_line}")
                    last_err = " | ".join(errs[-2:])
            if not (os.path.exists(raw) and os.path.getsize(raw) > 50_000):
                print(f"[PESQUISA V5 DL] Falha em {m['mid']} ({vid}): {last_err}", flush=True)
                return None

            ff_cmd = [ffmpeg_exe, "-y"]
            if not trimmed_in_raw:
                ff_cmd += ["-ss", f"{s:.2f}", "-i", raw, "-t", f"{dur_req:.2f}"]
            else:
                ff_cmd += ["-i", raw, "-t", f"{dur_req:.2f}"]
            ff_cmd += [
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1",
                "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-c:a", "aac", "-ar", "48000", "-ac", "2", dst,
            ]
            subprocess.run(ff_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                os.remove(raw)
            except OSError:
                pass
        if not os.path.exists(dst) or os.path.getsize(dst) < 150_000:
            return None
        m["clip"] = dst
        m["canal"] = cand.get("channel", m.get("canal", "Criador"))
        return m

    dl_workers = 2 if os.environ.get("GITHUB_ACTIONS") == "true" else 4
    with ThreadPoolExecutor(max_workers=dl_workers) as pool:
        baixados = [m for m in pool.map(_dl, momentos) if m]

    validados = []
    for m in baixados:
        frames = _frames_b64(m["clip"], n=5)
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in frames]
        prompt = (f"Estas são 5 imagens em ordem (início, meio e fim) de um trecho de vídeo de GTA 6. Descrição esperada: '{m['o_que_acontece']}'.\n"
                  "Responda APENAS um objeto JSON: {\"e_gameplay\": true/false (true SOMENTE se TODAS as 5 imagens mostrarem gameplay contínua real de GTA 6, false se houver tela de encerramento/outro de canal, outro jogo, menu, tela preta ou apresentador em tela cheia), "
                  "\"tem_logo_ou_trailer\": true/false (true se aparecer logo gigante 'Grand Theft Auto VI', logo/outro de canal tipo Gameranx/IGN, tela de pré-venda ou cartela oficial de trailer), "
                  "\"tem_overlay_poluido\": true/false (true APENAS se houver QR code grande, banner de patrocinador cobrindo a tela, ou apresentador em tela cheia falando sem gameplay; uma facecam pequena no canto durante gameplay real NÃO é poluído), "
                  "\"bate_com_descricao\": true/false, \"descricao_real\": \"o que realmente aparece no jogo em todas as imagens, objetivo, 1 frase\", "
                  "\"nota_visual\": 1-10 (impacto/curiosidade da cena), \"frase_thumb\": \"2 a 4 palavras de impacto sobre a cena\", "
                  "\"regiao\": \"vice_city|leonida_keys|grassrivers|port_gellhorn|ambrosia|mount_kalaga|nenhuma\"}")
        try:
            v, _ = gemini_text(prompt, json_mode=True, temperature=0.2, parts_extra=parts)
            if isinstance(v, list):
                v = v[0] if (v and isinstance(v[0], dict)) else {}
        except Exception as err:
            print(f"[VALIDAÇÃO] {m['mid']} erro {err}", flush=True)
            continue
        m.update({"validacao": v, "descricao_real": v.get("descricao_real", m["o_que_acontece"])})
        # Sobrescreve o_que_acontece com o que o Gemini REALMENTE VIU nos frames do clipe (evita narração desalinhada!)
        m["o_que_acontece"] = m["descricao_real"]
        has_logo = bool(v.get("tem_logo_ou_trailer"))
        has_clutter = bool(v.get("tem_overlay_poluido"))
        aprovado = bool(v.get("e_gameplay")) and (not has_logo) and (not has_clutter) and int(v.get("nota_visual", 0) or 0) >= 6
        print(f"[VALIDAÇÃO] {m['mid']} ({m['canal']}) gameplay={v.get('e_gameplay')} logo={has_logo} clutter={has_clutter} bate={v.get('bate_com_descricao')} "
              f"nota={v.get('nota_visual')} -> {'OK' if aprovado else 'DESCARTADO'} | {m['descricao_real']}", flush=True)
        if aprovado:
            validados.append(m)
    return validados


NSFW_RE = re.compile(
    r"strip|stripper|private\s*dance|nud[eo]|boob|sex|nsfw|horny|gyatt|twerk|prostit|shoe\s*store|"
    r"porno|pelad[ao]|bunda|peito|safad|boate\s*adult|lap\s*dance|naked|bikini\s*mod",
    re.I,
)


def pesquisar_clipes_twitch(ffmpeg_exe, min_valid=1):
    """
    MOTOR CLOUD-NATIVE V9 (100% GRÁTIS, 100% NUVEM 24h NO GITHUB ACTIONS — ZERO BLOQUEIO AZURE / ZERO COOKIES!):
    - Consulta a API pública GraphQL da Twitch para a categoria 'Grand Theft Auto VI' (PT-BR + EN, últimas 24h e 7 dias).
    - Filtra NSFW/strip club por título + valida 5 frames no Gemini Vision (gameplay real, monetização segura, sem overlay poluído).
    - Baixa clipes virais já cortados pela comunidade no clímax exato (14-60s) com áudio original direto da CDN da Twitch!
    """
    import requests

    os.makedirs(RESEARCH_DIR, exist_ok=True)
    clips_dir = os.path.join(RESEARCH_DIR, "clips")
    os.makedirs(clips_dir, exist_ok=True)

    hist = _load_v5_history()
    used_ids = set(hist.get("used_video_ids") or [])

    hdr = {"Client-ID": "kimne78kx3ncx6brgo4mv6wki5h1ko", "Content-Type": "application/json"}
    gql = """
    query($name: String!, $first: Int!, $period: ClipsPeriod!, $langs: [Language!]) {
      game(name: $name) {
        clips(first: $first, criteria: { period: $period, languages: $langs }) {
          edges {
            node {
              slug
              title
              url
              viewCount
              durationSeconds
              language
              broadcaster { displayName }
            }
          }
        }
      }
    }
    """

    candidates = []
    seen_slugs = set()
    per_streamer = {}

    queries = [
        ("LAST_DAY", ["PT"], 35),
        ("LAST_DAY", ["EN"], 35),
        ("LAST_WEEK", ["PT"], 40),
        ("LAST_WEEK", ["EN"], 40),
    ]
    for period, langs, limit in queries:
        try:
            r = requests.post(
                "https://gql.twitch.tv/gql",
                headers=hdr,
                json={"query": gql, "variables": {"name": "Grand Theft Auto VI", "first": limit, "period": period, "langs": langs}},
                timeout=18,
            )
            edges = ((((r.json().get("data") or {}).get("game") or {}).get("clips") or {}).get("edges") or [])
            for e in edges:
                n = e.get("node") or {}
                slug = n.get("slug") or ""
                title = (n.get("title") or "").strip()
                dur = int(n.get("durationSeconds") or 0)
                ch = ((n.get("broadcaster") or {}).get("displayName") or "Streamer").strip()
                if not slug or slug in seen_slugs or slug in used_ids:
                    continue
                if dur < 14 or dur > 65:
                    continue
                if NSFW_RE.search(title):
                    continue
                if per_streamer.get(ch, 0) >= 2:
                    continue
                seen_slugs.add(slug)
                per_streamer[ch] = per_streamer.get(ch, 0) + 1
                candidates.append({
                    "slug": slug,
                    "video_id": f"tw_{slug[:24]}",
                    "title": title,
                    "url": n.get("url") or f"https://clips.twitch.tv/{slug}",
                    "views": int(n.get("viewCount") or 0),
                    "duration": dur,
                    "lang": n.get("language") or langs[0],
                    "canal": ch,
                    "period": period,
                })
        except Exception as err:
            print(f"[TWITCH V9] Aviso busca {period}/{langs}: {err}", flush=True)

    # Prioriza PT-BR de hoje + virais globais de hoje com leve aleatoriedade para variedade
    pt_day = [c for c in candidates if c["lang"] == "PT" and c["period"] == "LAST_DAY"]
    en_day = [c for c in candidates if c["lang"] == "EN" and c["period"] == "LAST_DAY"]
    others = [c for c in candidates if c not in pt_day and c not in en_day]
    random.shuffle(pt_day)
    random.shuffle(en_day)
    random.shuffle(others)
    ordered = pt_day + en_day + others
    print(f"[TWITCH V9] {len(ordered)} clipes novos candidatos ({len(pt_day)} PT 24h, {len(en_day)} EN 24h) | zero cookies!", flush=True)

    if not ordered:
        return {}, []

    # Baixa em lotes até atingir min_valid clipes aprovados na validação visual 5-frames!
    validados = []
    batch_size = max(8, min(28, min_valid + 10))
    to_try = ordered[:batch_size]

    def _dl_tw(idx_c):
        idx, c = idx_c
        mid = f"tw_m{idx + 1}"
        dst = os.path.join(clips_dir, f"{mid}_{c['slug'][:18]}.mp4")
        raw = dst + ".raw.mp4"
        if os.path.exists(raw):
            try:
                os.remove(raw)
            except OSError:
                pass
        r_dl = _run([
            sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet",
            "-f", "best[height<=720]/best",
            "-o", raw, c["url"],
        ], timeout=45)
        if not (os.path.exists(raw) and os.path.getsize(raw) > 100_000):
            err_l = (r_dl.stderr.strip().splitlines()[-1][:120] if (r_dl and r_dl.stderr) else "timeout")
            print(f"[TWITCH DL] Falha em {c['canal']} ({c['slug'][:16]}): {err_l}", flush=True)
            return None
        # Normaliza para 1920x1080 24fps H.264 + AAC 48kHz preservando áudio original (máx 24s)
        dur_cut = min(24.0, float(c["duration"]))
        subprocess.run([
            ffmpeg_exe, "-y", "-i", raw, "-t", f"{dur_cut:.2f}",
            "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=24,setsar=1",
            "-c:v", "libx264", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-ar", "48000", "-ac", "2", dst,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False, timeout=60)
        try:
            os.remove(raw)
        except OSError:
            pass
        if not (os.path.exists(dst) and os.path.getsize(dst) > 150_000):
            return None
        return {
            "mid": mid,
            "video_id": c["slug"],
            "canal": c["canal"],
            "o_que_acontece": f"Clipe viral da live de {c['canal']} no GTA 6: {c['title']}",
            "assunto": "gameplay",
            "potencial": 9 if c["views"] >= 5000 else 7,
            "clip": dst,
            "views": c["views"],
            "url": c["url"],
        }

    with ThreadPoolExecutor(max_workers=4) as pool:
        baixados = [m for m in pool.map(_dl_tw, enumerate(to_try)) if m]

    print(f"[TWITCH V9] Baixados com sucesso: {len(baixados)}/{len(to_try)} clipes HD com áudio original!", flush=True)

    for m in baixados:
        if len(validados) >= max(min_valid + 3, 4 if min_valid == 1 else min_valid + 2):
            break
        frames = _frames_b64(m["clip"], n=5)
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in frames]
        prompt = (
            f"Estas são 5 imagens em ordem (início, meio e fim) de um clipe viral da Twitch de GTA 6 do streamer '{m['canal']}' (título: '{m['o_que_acontece']}').\n"
            "Responda APENAS um objeto JSON:\n"
            "{\"e_gameplay\": true/false (true SOMENTE se TODAS as 5 imagens mostrarem gameplay real de GTA 6, false se for só webcam/chat/menu/outro jogo/tela preta), "
            "\"seguro_monetizacao\": true/false (false se houver nudez, strip club, conteúdo +18 ou violência gráfica explícita que desmonetize no YouTube), "
            "\"tem_logo_ou_trailer\": true/false (true se for trailer oficial ou tela de logo estática), "
            "\"tem_overlay_poluido\": true/false (true APENAS se houver QR code gigante, banner cobrindo a tela ou webcam em tela cheia; uma facecam pequena no canto durante gameplay real NÃO é poluído), "
            "\"assunto\": \"bug|segredo|detalhe|mecanica|engracado|acao|mapa\", "
            "\"descricao_real\": \"descreva objetivamente em 1 frase em PT-BR o que REALMENTE acontece no jogo GTA 6 neste clipe\", "
            "\"nota_visual\": 1-10 (impacto/curiosidade/entretenimento da cena), "
            "\"frase_thumb\": \"2 a 4 palavras de impacto sobre a cena\", "
            "\"regiao\": \"vice_city|leonida_keys|grassrivers|port_gellhorn|ambrosia|mount_kalaga|nenhuma\"}"
        )
        try:
            v, _ = gemini_text(prompt, json_mode=True, temperature=0.2, parts_extra=parts)
            if isinstance(v, list):
                v = v[0] if (v and isinstance(v[0], dict)) else {}
        except Exception as err:
            print(f"[TWITCH VALIDAÇÃO] {m['mid']} erro {err}", flush=True)
            continue
        m.update({
            "validacao": v,
            "descricao_real": v.get("descricao_real") or m["o_que_acontece"],
            "assunto": v.get("assunto") or "gameplay",
        })
        m["o_que_acontece"] = m["descricao_real"]
        ok_game = bool(v.get("e_gameplay"))
        ok_safe = bool(v.get("seguro_monetizacao", True))
        has_logo = bool(v.get("tem_logo_ou_trailer"))
        has_clutter = bool(v.get("tem_overlay_poluido"))
        nota = int(v.get("nota_visual", 0) or 0)
        aprovado = ok_game and ok_safe and (not has_logo) and (not has_clutter) and nota >= 6
        print(
            f"[TWITCH VALIDAÇÃO] {m['mid']} ({m['canal']}) game={ok_game} safe={ok_safe} logo={has_logo} "
            f"clutter={has_clutter} nota={nota} -> {'OK' if aprovado else 'DESCARTADO'} | {m['descricao_real']}",
            flush=True,
        )
        if aprovado:
            validados.append(m)

    pauta = {
        "momentos": validados,
        "pauta_longo": {
            "tema": "Os Melhores Bugs, Segredos e Momentos Insanos de GTA 6 nas Lives de Hoje",
            "angulo": "Compilado editorial narrado das descobertas mais recentes de gameplay do GTA 6",
        },
        "pauta_short": {
            "tema": validados[0]["descricao_real"] if validados else "Momento insano no GTA 6",
            "formato": "descoberta",
        },
    }
    return pauta, validados


def pesquisar_do_zero(ffmpeg_exe, min_valid=1):
    """
    Executa o ciclo completo de pesquisa V9 (Cloud-Native 24/7 + Residencial):
    - Na nuvem do GitHub Actions (sem YTDLP_PROXY), usa TWITCH CLIPS ('Grand Theft Auto VI' PT + EN) como motor primário:
      100% grátis, zero bloqueio de IP da Azure, zero cookies, clipes virais novos todo dia!
    - No PC residencial (ou com YTDLP_PROXY), tenta YouTube e complementa automaticamente com Twitch Clips se precisar!
    """
    is_cloud_no_proxy = (os.environ.get("GITHUB_ACTIONS") == "true") and not (os.environ.get("YTDLP_PROXY") or "").strip()

    all_validados = []
    seen_vids = set()
    pauta_final = {}

    if is_cloud_no_proxy:
        print("[PESQUISA V9 CLOUD] Ambiente GitHub Actions detectado -> usando Twitch Clips GTA 6 (zero bloqueio Azure / zero cookies)!", flush=True)
        pauta_tw, vals_tw = pesquisar_clipes_twitch(ffmpeg_exe, min_valid=min_valid)
        pauta_final = pauta_tw
        all_validados.extend(vals_tw)
    else:
        for round_idx in range(1, 3):
            cands = descobrir_conteudo(n_queries=18, por_query=14, ffmpeg_exe=ffmpeg_exe)
            cands = [c for c in cands if c["id"] not in seen_vids]
            transcritos = baixar_transcricoes(cands, max_videos=16)
            lives_cap = capturar_lives(cands, ffmpeg_exe) if round_idx == 1 else []
            if not transcritos and not lives_cap:
                break
            pauta = escolher_pauta(transcritos, lives_cap)
            if not pauta_final:
                pauta_final = pauta
            by_id = {c["id"]: c for c in cands}
            momentos = [m for m in pauta.get("momentos", []) if m.get("video_id") in by_id]
            momentos = sorted(momentos, key=lambda m: -int(m.get("potencial", 0) or 0))
            for idx_m, m in enumerate(momentos):
                m["mid"] = f"r{round_idx}_m{idx_m + 1}"
            validados = baixar_e_validar_momentos(momentos, by_id, ffmpeg_exe)
            for v in validados:
                all_validados.append(v)
                seen_vids.add(v.get("video_id"))
            print(f"[PESQUISA V9 YT RODADA {round_idx}] Clipes novos validados acumulados: {len(all_validados)} (meta={min_valid})", flush=True)
            if len(all_validados) >= min_valid:
                break

        # Se ainda faltarem clipes para atingir min_valid, complementa instantaneamente com Twitch Clips GTA 6!
        if len(all_validados) < min_valid:
            faltam = max(1, min_valid - len(all_validados))
            print(f"[PESQUISA V9] Complementando {faltam} clipe(s) novo(s) via Twitch Clips GTA 6...", flush=True)
            pauta_tw, vals_tw = pesquisar_clipes_twitch(ffmpeg_exe, min_valid=faltam)
            if not pauta_final:
                pauta_final = pauta_tw
            all_validados.extend(vals_tw)

    with open(os.path.join(RESEARCH_DIR, "pauta.json"), "w", encoding="utf-8") as f:
        json.dump({"pauta": pauta_final, "validados": all_validados}, f, ensure_ascii=False, indent=2)
    _save_v5_history(
        [m.get("video_id") for m in all_validados],
        topic=(pauta_final.get("pauta_longo") or {}).get("tema"),
    )
    return pauta_final, all_validados
