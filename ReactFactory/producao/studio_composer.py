"""COMPOSITOR AUDIOVISUAL PROFISSIONAL (Remotion + Three.js + OpenCV + FFmpeg + Sound Design).

Une a estética broadcast do estúdio Remotion/Three.js com velocidade de renderização
para nuvem (GitHub Actions) e local:
- Renderiza os layouts gráficos de cada bloco (Map Zoom, Character Dossier, 3D Data Comparison,
  Feature Spotlight) via Remotion + Three.js e aplica movimento contínuo de câmera/radar/3D,
  intercalando com cortes reais 1080p dos trailers oficiais da Rockstar e legendas palavra-por-palavra
  sincronizadas via faster-whisper.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
import os
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from composer import FFMPEG_EXE, get_media_duration, load_font
from producao.agentes import AgenteEditorAudiovisual
from producao.catalog import extract_real_trailer_clips, is_sticker_mask_video
from producao.sound_designer import ensure_studio_sfx_pack, fetch_dynamic_bgm_for_mood

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BADGE_COLORS_BGR = {
    "OFICIAL": ((118, 230, 0), "FONTE OFICIAL ROCKSTAR"),
    "CONFIRMADO": ((255, 240, 0), "CONFIRMADO POR FONTES"),
    "RUMOR": ((0, 109, 255), "RUMOR / NAO OFICIAL"),
    "TEORIA": ((255, 136, 179), "ANALISE & TEORIA DA COMUNIDADE"),
}


def _clean_ascii(t):
    return "".join(c for c in (t or "") if ord(c) < 65000).strip()


def _draw_word_caption_pil(frame_bgr, words, t_sec):
    """Desenha a legenda sincronizada palavra-por-palavra estilo Remotion sobre o frame 1080p."""
    if not words:
        return frame_bgr
    active_idx = -1
    for i, w in enumerate(words):
        if w["s"] <= t_sec <= w["e"] + 0.10:
            active_idx = i
            break
    if active_idx == -1:
        for i in range(len(words) - 1, -1, -1):
            if t_sec >= words[i]["s"]:
                active_idx = i
                break
    if active_idx == -1:
        active_idx = 0

    chunk_start = (active_idx // 5) * 5
    chunk = words[chunk_start : chunk_start + 5]
    if not chunk:
        return frame_bgr

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")
    font = load_font(44)

    tokens = [_clean_ascii(it["w"]).upper() for it in chunk]
    full_str = " ".join(tokens)
    bb = draw.textbbox((0, 0), full_str, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x0 = (1920 - tw) // 2
    y0 = 968

    draw.rounded_rectangle(
        [x0 - 30, y0 - 14, x0 + tw + 30, y0 + th + 18],
        radius=14,
        fill=(9, 11, 18, 228),
        outline=(255, 42, 133, 195),
        width=2,
    )
    xc = x0
    for idx_in_chunk, tok in enumerate(tokens):
        is_curr = (chunk_start + idx_in_chunk) == active_idx
        col = (255, 184, 0, 255) if is_curr else (248, 250, 252, 255)
        draw.text((xc, y0 - 2), tok, font=font, fill=col, stroke_width=4, stroke_fill=(0, 0, 0, 255))
        wb = draw.textbbox((0, 0), tok + " ", font=font)
        xc += wb[2] - wb[0]

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _render_remotion_still_plate(props, frame_num, out_png):
    """Renderiza um quadro mestre 1920x1080 no Remotion + Three.js (sem legendas inferiores fixas)."""
    import base64

    studio_dir = AgenteEditorAudiovisual.STUDIO_DIR
    bundle_dir = AgenteEditorAudiovisual.ensure_remotion_bundle()
    props_clean = dict(props)
    props_clean["words"] = []  # As legendas são animadas a 24fps quadro-a-quadro
    for k in ("primaryImageUrl", "secondaryImageUrl"):
        p = props_clean.get(k) or ""
        if p and os.path.exists(p) and not p.startswith("data:"):
            b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
            props_clean[k] = f"data:image/jpeg;base64,{b64}"

    pf = out_png + ".json"
    with open(pf, "w", encoding="utf-8") as f:
        json.dump(props_clean, f, ensure_ascii=False)

    npx_bin = "npx.cmd" if os.name == "nt" else "npx"
    cmd = [npx_bin, "remotion", "still", bundle_dir, "GtaStudioScene", out_png, f"--frame={frame_num}", f"--props={pf}"]
    r = subprocess.run(cmd, cwd=studio_dir, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"Remotion still falhou ({r.returncode}): {r.stderr[-300:]}")
    try:
        os.remove(pf)
    except OSError:
        pass
    return out_png


def _render_block_video(job, trailer_clips, sfx_pack, work_dir):
    """
    Renderiza um bloco completo combinando:
    - Parte A (0 -> 58% da duração): Composição gráfica contextual Remotion + Three.js
      (Map Zoom com radar animado, Dossiê de Personagem, Comparativo 3D Three.js ou Spotlight)
    - Parte B (58% -> 100% da duração): B-roll cinematográfico em movimento (corte real 1080p de trailer
      oficial da Rockstar ou segunda tomada 4K com HUD de verificação)
    - Legendas sincronizadas palavra-por-palavra (faster-whisper) em 100% do bloco
    - Mixagem de áudio com SFX contextual (radar_ping, sub_drop, telemetry, whoosh) + BGM com ducking.
    """
    bid = job["bid"]
    blk = job["blk"]
    dur = job["dur"]
    words = job["words"]
    fps = 24
    total_frames = max(24, int(round(dur * fps)))

    props = {
        "sceneType": blk.get("scene_type", "feature_spotlight"),
        "badgeType": blk.get("badge_type", "OFICIAL"),
        "sourceLabel": blk.get("source_label", "Rockstar Games Official / rockstargames.com/VI"),
        "actNum": job["act_num"],
        "totalActs": job["total_acts"],
        "actTitle": job["act_title"],
        "headline": blk.get("headline") or blk.get("callout") or "DOSSIÊ GTA VI",
        "subheadline": blk.get("subheadline") or blk.get("asset_subject") or "Análise audiovisual verificada",
        "locationKey": blk.get("location_key", "vice_city"),
        "characterName": blk.get("character_name", "LUCIA & JASON"),
        "characterRole": blk.get("character_role", "PROTAGONISTAS // LEONIDA"),
        "characterFacts": blk.get("character_facts", []),
        "statValue": blk.get("stat_value", "19 NOV"),
        "statUnit": blk.get("stat_unit", "QUINTA • 00:00"),
        "statLabel": blk.get("stat_label", "TELEMETRIA & DADOS VERIFICADOS"),
        "comparisonItems": blk.get("comparison_items", []),
        "primaryImageUrl": blk.get("primary_img") or "",
        "secondaryImageUrl": blk.get("secondary_img") or "",
    }

    # Quadro mestre Remotion + Three.js (renderizado no pico da animação spring)
    plate_png = os.path.join(work_dir, f"remotion_{bid}.png")
    if not os.path.exists(plate_png):
        _render_remotion_still_plate(props, frame_num=55, out_png=plate_png)
    remotion_img = cv2.imread(plate_png)
    if remotion_img is None:
        remotion_img = np.full((1080, 1920, 3), 14, dtype=np.uint8)

    # Segunda tomada visual (clipe real 1080p de trailer ou segunda imagem 4K) para mudança de plano no meio do bloco
    broll_frames = []
    valid_clips = [c for c in trailer_clips if not is_sticker_mask_video(c)]
    if valid_clips and (job["global_idx"] % 2 == 0):
        clip_p = valid_clips[job["global_idx"] % len(valid_clips)]
        cap = cv2.VideoCapture(clip_p)
        while len(broll_frames) < total_frames:
            ret, fr = cap.read()
            if not ret:
                break
            if fr.shape[:2] != (1080, 1920):
                fr = cv2.resize(fr, (1920, 1080), interpolation=cv2.INTER_LINEAR)
            broll_frames.append(fr)
        cap.release()

    sec_img_path = blk.get("secondary_img") or blk.get("primary_img")
    sec_img = cv2.imread(sec_img_path) if (sec_img_path and os.path.exists(sec_img_path)) else remotion_img
    if sec_img is not None:
        sh, sw = sec_img.shape[:2]
        sc = max(1920.0 / sw, 1080.0 / sh)
        sec_img = cv2.resize(sec_img, (max(1920, int(sw * sc)), max(1080, int(sh * sc))), interpolation=cv2.INTER_AREA)
        x0, y0 = (sec_img.shape[1] - 1920) // 2, (sec_img.shape[0] - 1080) // 2
        sec_img = sec_img[y0 : y0 + 1080, x0 : x0 + 1920].copy()

    silent_mp4 = os.path.join(work_dir, f"vis_{bid}.mp4")
    proc = subprocess.Popen(
        [
            FFMPEG_EXE, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1920x1080", "-r", str(fps), "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "superfast", "-crf", "19", "-pix_fmt", "yuv420p",
            "-video_track_timescale", "24000", "-an", silent_mp4,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    split_frame = int(total_frames * 0.56)
    for f_idx in range(total_frames):
        t_sec = f_idx / float(fps)
        if f_idx < split_frame:
            # Parte A: Composição Remotion + Three.js com leve câmera viva e pulso de radar
            p = f_idx / float(max(1, split_frame - 1))
            z = 1.0 + 0.045 * p
            cw, ch = int(1920 / z), int(1080 / z)
            cx, cy = (1920 - cw) // 2, (1080 - ch) // 2
            base = cv2.resize(remotion_img[cy : cy + ch, cx : cx + cw], (1920, 1080), interpolation=cv2.INTER_LINEAR)
        else:
            # Parte B: Corte dinâmico para B-roll 1080p de trailer ou 4K secundário com barra HUD superior preservada
            b_idx = f_idx - split_frame
            if broll_frames:
                raw_b = broll_frames[b_idx % len(broll_frames)].copy()
            else:
                p2 = b_idx / float(max(1, total_frames - split_frame))
                z2 = 1.10 - 0.08 * p2
                cw, ch = int(1920 / z2), int(1080 / z2)
                cx, cy = (1920 - cw) // 2, (1080 - ch) // 2
                raw_b = cv2.resize(sec_img[cy : cy + ch, cx : cx + cw], (1920, 1080), interpolation=cv2.INTER_LINEAR)
            # Preserva o topo editorial (barra de progresso + selo de fonte do Remotion) nos primeiros 82px
            raw_b[0:82, :] = cv2.addWeighted(remotion_img[0:82, :], 0.88, raw_b[0:82, :], 0.12, 0)
            # Transição suave cross-dissolve de 6 frames entre Parte A e Parte B
            if b_idx < 6:
                alpha = (b_idx + 1) / 6.0
                base = cv2.addWeighted(raw_b, alpha, remotion_img, 1.0 - alpha, 0)
            else:
                base = raw_b

        frame_with_sub = _draw_word_caption_pil(base, words, t_sec)
        proc.stdin.write(frame_with_sub.tobytes())

    proc.stdin.close()
    proc.wait()

    # Seleção do efeito sonoro contextual (Agente 4 — Sound Designer)
    st = blk.get("scene_type", "feature_spotlight")
    if st == "map_zoom":
        sfx_file = sfx_pack["radar_ping"]
    elif st == "data_comparison":
        sfx_file = sfx_pack["sub_drop"]
    elif st == "character_dossier":
        sfx_file = sfx_pack["telemetry"]
    else:
        sfx_file = sfx_pack["whoosh"]

    fade_out_st = max(0.0, dur - 0.30)
    aud_fc = (
        f"[1:a]volume=1.22[vo];"
        f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out_st:.2f}:d=0.30,volume=0.22[bm];"
        f"[3:a]volume=0.38[sx];"
        f"[vo][bm][sx]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
    )
    subprocess.run(
        [
            FFMPEG_EXE, "-y",
            "-i", silent_mp4,
            "-i", job["wav_p"],
            "-stream_loop", "-1", "-ss", f"{job['bgm_ss']:.2f}", "-i", job["bgm_file"],
            "-i", sfx_file,
            "-filter_complex", aud_fc,
            "-map", "0:v", "-map", "[aout]", "-t", f"{dur:.2f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-video_track_timescale", "24000", job["seg_out"],
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return bid


def build_editorial_thumbnail(jpg_path, headline, subheadline, out_jpg):
    """Gera thumbnail 1280x720 estilo marca editorial de games (Vice Pulse Editorial)."""
    if jpg_path and os.path.exists(jpg_path):
        hero = Image.open(jpg_path).convert("RGB")
    else:
        hero = Image.new("RGB", (1280, 720), (14, 18, 32))

    sc = max(1280.0 / hero.width, 720.0 / hero.height)
    hero = hero.resize((int(hero.width * sc), int(hero.height * sc)), Image.Resampling.LANCZOS)
    x0, y0 = (hero.width - 1280) // 2, (hero.height - 720) // 2
    canvas = hero.crop((x0, y0, x0 + 1280, y0 + 720))

    arr = np.array(canvas, dtype=np.float32)
    mean = arr.mean(axis=2, keepdims=True)
    arr = np.clip(mean + (arr - mean) * 1.28, 0, 255)
    arr = np.clip((arr - 128) * 1.14 + 128, 0, 255)
    grad = np.ones((720, 1, 1), dtype=np.float32)
    grad[300:] = np.linspace(1.0, 0.18, 720 - 300, dtype=np.float32)[:, None, None]
    arr = arr * grad
    canvas = Image.fromarray(arr.astype(np.uint8))

    draw = ImageDraw.Draw(canvas, "RGBA")
    # Moldura sutil neon e selo editorial superior
    draw.rectangle([0, 0, 1279, 719], outline=(255, 42, 133, 220), width=6)
    f_badge = load_font(38)
    draw.rounded_rectangle([36, 32, 420, 96], radius=12, fill=(9, 11, 18, 235), outline=(0, 240, 255, 255), width=3)
    draw.text((56, 44), "DOSSIE GTA VI // 19 NOV", font=f_badge, fill=(0, 240, 255, 255))

    # Título principal de alto impacto
    f_big = load_font(108)
    clean_h = (_clean_ascii(headline) or "LANCAMENTO GTA 6").upper()
    tb = draw.textbbox((0, 0), clean_h, font=f_big)
    tw = tb[2] - tb[0]
    while tw > 1180 and f_big.size > 64:
        f_big = load_font(f_big.size - 6)
        tb = draw.textbbox((0, 0), clean_h, font=f_big)
        tw = tb[2] - tb[0]
    tx = (1280 - tw) // 2
    draw.text((tx + 6, 495 + 6), clean_h, font=f_big, fill=(0, 0, 0, 255))
    draw.text((tx, 495), clean_h, font=f_big, fill=(255, 184, 0, 255), stroke_width=8, stroke_fill=(0, 0, 0, 255))

    # Subtítulo editorial inferior
    f_sub = load_font(42)
    clean_s = (_clean_ascii(subheadline) or "ANALISE COMPLETA E FONTES VERIFICADAS").upper()[:48]
    sb = draw.textbbox((0, 0), clean_s, font=f_sub)
    sw = sb[2] - sb[0]
    sx = (1280 - sw) // 2
    draw.rounded_rectangle([sx - 24, 622, sx + sw + 24, 684], radius=10, fill=(255, 42, 133, 240))
    draw.text((sx, 630), clean_s, font=f_sub, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

    canvas.save(out_jpg, quality=95)
    return out_jpg


def compose_studio_video(script_data, wav_map, words_map, work_dir, output_mp4, output_thumb_jpg):
    """
    ETAPAS 9 a 12 — Desenvolvimento das animações Remotion/Three.js, montagem audiovisual,
    sound design dinâmico e renderização master 1920x1080@24fps.
    """
    from gta6_long_composer import _make_chapter_card_jpg, _render_kenburns_cv2  # noqa: WPS433

    os.makedirs(work_dir, exist_ok=True)
    sfx_pack = ensure_studio_sfx_pack()
    trailer_clips = extract_real_trailer_clips(FFMPEG_EXE)
    AgenteEditorAudiovisual.ensure_remotion_bundle()

    acts = script_data.get("acts", [])
    total_acts = len(acts)
    ordered_segments = []
    block_jobs = []
    chapters_ts = []
    music_credits = []
    total_t = 0.0
    global_idx = 0

    for a_idx, act in enumerate(acts):
        act_num = int(act.get("act_num", a_idx + 1))
        act_title = act.get("act_title", f"ATO {act_num}")
        mood = act.get("bgm_mood", "synth")

        bgm_file, credit = fetch_dynamic_bgm_for_mood(mood, FFMPEG_EXE)
        music_credits.append(credit)
        bgm_dur = max(15.0, get_media_duration(bgm_file))

        mm, ss = divmod(int(total_t), 60)
        chapters_ts.append(f"{mm}:{ss:02d} {act_title}")

        # Card de abertura de Ato (2.20s) com impacto sub_drop + BGM
        first_img = (act.get("blocks") or [{}])[0].get("primary_img")
        card_jpg = os.path.join(work_dir, f"act_{act_num}_card.jpg")
        _make_chapter_card_jpg(act_num, act_title, first_img, card_jpg)
        card_vis = os.path.join(work_dir, f"card_act{act_num:02d}_vis.mp4")
        _render_kenburns_cv2(card_jpg, 2.20, card_vis, zoom_in=True, fps=24)
        card_mp4 = os.path.join(work_dir, f"seg_act{act_num:02d}_00_card.mp4")
        subprocess.run(
            [
                FFMPEG_EXE, "-y", "-i", card_vis,
                "-i", sfx_pack["sub_drop"], "-stream_loop", "-1", "-i", bgm_file,
                "-filter_complex",
                "[1:a]volume=0.70[s];[2:a]atrim=0:2.20,volume=0.95[b];[s][b]amix=inputs=2:duration=longest:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[a]",
                "-map", "0:v", "-map", "[a]", "-t", "2.20",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                "-video_track_timescale", "24000", card_mp4,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        ordered_segments.append(card_mp4)
        total_t += 2.20
        bgm_offset = 2.20

        for b_idx, blk in enumerate(act.get("blocks", [])):
            bid = f"a{act_num}_b{b_idx}"
            wav_p = wav_map[bid]
            dur = max(2.4, get_media_duration(wav_p) + 0.20)
            seg_out = os.path.join(work_dir, f"seg_{act_num:02d}_{b_idx:02d}.mp4")
            ordered_segments.append(seg_out)
            bgm_ss = bgm_offset % max(2.0, bgm_dur - dur - 1.0)
            block_jobs.append({
                "bid": bid,
                "global_idx": global_idx,
                "act_num": act_num,
                "total_acts": total_acts,
                "act_title": act_title,
                "blk": blk,
                "wav_p": wav_p,
                "words": words_map.get(bid, []),
                "dur": dur,
                "bgm_file": bgm_file,
                "bgm_ss": bgm_ss,
                "seg_out": seg_out,
            })
            bgm_offset += dur
            total_t += dur
            global_idx += 1

    print(f"[STUDIO COMPOSER] Renderizando {len(block_jobs)} blocos (Remotion + Three.js + B-Roll 1080p)...", flush=True)
    # Renderiza os plates Remotion sequencialmente (evita contenção de instâncias Chromium) e os vídeos em paralelo
    for job in block_jobs:
        bid = job["bid"]
        plate_png = os.path.join(work_dir, f"remotion_{bid}.png")
        if not os.path.exists(plate_png):
            blk = job["blk"]
            props = {
                "sceneType": blk.get("scene_type", "feature_spotlight"),
                "badgeType": blk.get("badge_type", "OFICIAL"),
                "sourceLabel": blk.get("source_label", "Rockstar Games Official / rockstargames.com/VI"),
                "actNum": job["act_num"],
                "totalActs": job["total_acts"],
                "actTitle": job["act_title"],
                "headline": blk.get("headline") or blk.get("callout") or "DOSSIÊ GTA VI",
                "subheadline": blk.get("subheadline") or blk.get("asset_subject") or "Análise audiovisual verificada",
                "locationKey": blk.get("location_key", "vice_city"),
                "characterName": blk.get("character_name", "LUCIA & JASON"),
                "characterRole": blk.get("character_role", "PROTAGONISTAS // LEONIDA"),
                "characterFacts": blk.get("character_facts", []),
                "statValue": blk.get("stat_value", "19 NOV"),
                "statUnit": blk.get("stat_unit", "QUINTA • 00:00"),
                "statLabel": blk.get("stat_label", "TELEMETRIA & DADOS VERIFICADOS"),
                "comparisonItems": blk.get("comparison_items", []),
                "primaryImageUrl": blk.get("primary_img") or "",
                "secondaryImageUrl": blk.get("secondary_img") or "",
            }
            _render_remotion_still_plate(props, frame_num=55, out_png=plate_png)

    done = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_render_block_video, j, trailer_clips, sfx_pack, work_dir) for j in block_jobs]
        for fut in as_completed(futs):
            fut.result()
            done += 1
            print(f"[STUDIO COMPOSER] Bloco {done}/{len(block_jobs)} concluído.", flush=True)

    concat_txt = os.path.join(work_dir, "studio_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in ordered_segments:
            f.write(f"file '{os.path.abspath(s).replace(chr(92), '/')}'\n")

    subprocess.run(
        [
            FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
            "-c", "copy", "-movflags", "+faststart", output_mp4,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Escolhe arte oficial com rostos de protagonistas (Lucia & Jason) para maximizar CTR da Thumbnail
    thumb_candidates = [
        os.path.join(BASE_DIR, "temp_gta6", "vault", fn)
        for fn in ("img_09.jpg", "img_07.jpg", "img_21.jpg", "img_08.jpg", "img_26.jpg")
    ]
    hero_jpg = next((p for p in thumb_candidates if os.path.exists(p)), None) or (
        block_jobs[0]["blk"].get("primary_img") if block_jobs else None
    )
    build_editorial_thumbnail(
        hero_jpg,
        script_data.get("thumb_text", "19 DE NOVEMBRO"),
        script_data.get("thumb_subtext", "DOSSIE OFICIAL GTA 6"),
        output_thumb_jpg,
    )
    real_dur = get_media_duration(output_mp4)
    return output_mp4, output_thumb_jpg, chapters_ts, music_credits, real_dur
