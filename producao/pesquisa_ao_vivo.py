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
YTDLP = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--quiet"]


def _ensure_cookies_file():
    """Decodifica YOUTUBE_COOKIES_B64 (secret do GitHub Actions) para liberar downloads/legendas em IPs de nuvem."""
    if os.path.exists(COOKIES_PATH) and os.path.getsize(COOKIES_PATH) > 100:
        return COOKIES_PATH
    b64 = (os.environ.get("YOUTUBE_COOKIES_B64") or "").strip()
    if not b64:
        local_ck = os.path.join(os.path.dirname(BASE_DIR), "_render_secrets", "YOUTUBE_COOKIES_B64.txt")
        if os.path.exists(local_ck):
            b64 = open(local_ck, "r", encoding="utf-8").read().strip()
    if b64:
        try:
            os.makedirs(os.path.dirname(COOKIES_PATH), exist_ok=True)
            with open(COOKIES_PATH, "wb") as f:
                f.write(base64.b64decode(b64))
            return COOKIES_PATH
        except Exception:
            pass
    return None


def _ytdlp_cmd(mode="default"):
    """
    Constrói comando yt-dlp resiliente para PC residencial e nuvem:
    - mode="default": yt-dlp padrão (sem player_client forçado e sem cookies expirados -> funciona 100% no IP residencial!)
    - mode="cookies": usa cookies autenticados + web/mweb (para IPs de nuvem como GitHub Actions)
    - mode="alt": fallback player_client alternativo
    """
    cmd = list(YTDLP)
    if mode == "cookies":
        ck = _ensure_cookies_file()
        if ck:
            cmd += ["--cookies", ck, "--extractor-args", "youtube:player_client=web,mweb"]
    elif mode == "alt":
        cmd += ["--extractor-args", "youtube:player_client=web,mweb"]
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
BLOCK_RE = re.compile(r"trailer oficial|official trailer|react(ing)? to trailer|previs[aã]o|vai ter|teoria", re.I)

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
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}&sp=CAI%253D"
        r = _run(YTDLP + ["--flat-playlist", "--dump-json", "--playlist-end", str(por_query), url], timeout=45)
        if r and r.stdout:
            for line in r.stdout.splitlines():
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return (q if isinstance(q, str) else "live"), out

    for lq in ["gta 6", "gta 6 ao vivo", "gta vi live", "gta 6 gameplay"]:
        queries.append(("__live__", f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(lq)}&sp=EgJAAQ%253D%253D"))

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
        for mode in ("default", "cookies"):
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

            # Tentativa 1: yt-dlp padrão (sem player_client forçado e sem cookies expirados -> funciona 100% no IP residencial!)
            # Tentativa 2: yt-dlp padrão baixando arquivo completo (<=65MB) e cortando localmente no FFmpeg (imune a erro HTTP 403 em seek!)
            # Tentativa 3: yt-dlp com cookies web/mweb (fallback para IPs de nuvem / GitHub Actions)
            strategies = [
                ("default", True, "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/b[height<=720]/b"),
                ("default", True, "b[height<=720]/b"),
                ("default", False, "b[height<=720][filesize<65M]/b[height<=480][filesize<65M]/b[height<=720]"),
                ("cookies", True, "bv*[height<=720][vcodec^=avc1]+ba[ext=m4a]/b[height<=720]/b"),
            ]
            for mode, use_sections, fmt in strategies:
                if os.path.exists(raw):
                    try:
                        os.remove(raw)
                    except OSError:
                        pass
                cmd = _ytdlp_cmd(mode=mode) + [
                    "--ffmpeg-location", ffmpeg_exe, "-f", fmt,
                    "--merge-output-format", "mp4", "-o", raw,
                ]
                if use_sections:
                    cmd += ["--download-sections", f"*{s:.0f}-{e:.0f}", "--force-keyframes-at-cuts"]
                else:
                    cmd += ["--max-filesize", "65M"]
                cmd.append(f"https://www.youtube.com/watch?v={vid}")
                r_dl = _run(cmd, timeout=110)
                if os.path.exists(raw) and os.path.getsize(raw) > 50_000:
                    trimmed_in_raw = use_sections
                    break
                if r_dl and r_dl.stderr:
                    last_err = r_dl.stderr.strip().splitlines()[-1][:160]
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

    with ThreadPoolExecutor(max_workers=4) as pool:
        baixados = [m for m in pool.map(_dl, momentos) if m]

    validados = []
    for m in baixados:
        frames = _frames_b64(m["clip"], n=4)
        parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b}} for b in frames]
        prompt = (f"Estas são 4 imagens em ordem de um trecho de vídeo de GTA 6. Descrição esperada: '{m['o_que_acontece']}'.\n"
                  "Responda APENAS um objeto JSON: {\"e_gameplay\": true/false (true SOMENTE se mostra gameplay real do jogo, false se for só webcam/menu/tela preta/estática), "
                  "\"tem_logo_ou_trailer\": true/false (true se aparecer logo gigante 'Grand Theft Auto VI', tela de pré-venda, contagem regressiva ou cartela oficial de trailer), "
                  "\"tem_overlay_poluido\": true/false (true APENAS se houver QR code grande, banner de patrocinador cobrindo a tela, ou apresentador em tela cheia falando sem gameplay; uma facecam pequena no canto durante gameplay real NÃO é poluído), "
                  "\"bate_com_descricao\": true/false, \"descricao_real\": \"o que realmente aparece no jogo, objetivo, 1 frase\", "
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


def pesquisar_do_zero(ffmpeg_exe):
    """Executa o ciclo completo de pesquisa V5 e retorna (pauta, momentos_validados)."""
    cands = descobrir_conteudo(ffmpeg_exe=ffmpeg_exe)
    transcritos = baixar_transcricoes(cands)
    lives_cap = capturar_lives(cands, ffmpeg_exe)
    if not transcritos and not lives_cap:
        raise RuntimeError("Pesquisa V5 sem material real (nenhuma transcrição/live). Abortando para não inventar conteúdo.")
    pauta = escolher_pauta(transcritos, lives_cap)
    by_id = {c["id"]: c for c in cands}
    momentos = [m for m in pauta.get("momentos", []) if m.get("video_id") in by_id]
    momentos = sorted(momentos, key=lambda m: -int(m.get("potencial", 0) or 0))
    validados = baixar_e_validar_momentos(momentos, by_id, ffmpeg_exe)
    with open(os.path.join(RESEARCH_DIR, "pauta.json"), "w", encoding="utf-8") as f:
        json.dump({"pauta": pauta, "validados": validados}, f, ensure_ascii=False, indent=2)
    _save_v5_history(
        [m.get("video_id") for m in validados],
        topic=(pauta.get("pauta_longo") or {}).get("tema"),
    )
    return pauta, validados
