"""COMPOSITOR AUDIOVISUAL PROFISSIONAL V3 (Broadcast Editorial + Real Remotion Video + Higgsfield DoP Camera Motion).

Diretrizes V3:
1. Regra Seletiva 75/25:
   - 75% a 80% dos blocos (`scene_type == "cinema_broll"`): Vídeo 1080p real de gameplay/trailer de GTA 6 em tela cheia,
     casado semanticamente com a frase falada, com movimentação de câmera orgânica estilo Higgsfield DoP (Dolly in/out,
     flutuação handheld cinematográfica, vinheta óptica anamórfica) e Lower-Third editorial minimalista apenas nos primeiros 3.8s.
   - 20% a 25% dos blocos (no máximo 1 por Ato, APENAS quando o roteiro pede `map_zoom`, `character_dossier` ou `data_comparison`):
     Renderiza um VÍDEO `.mp4` REAL no Remotion (`npx remotion render` a 24fps com física `spring()`, `@remotion/three`,
     `@remotion/shapes`) nos primeiros 45% do bloco e faz cross-dissolve cinematográfico para 2 clipes 1080p de gameplay.
2. Zero rabiscos OpenCV (`cv2.circle`, `cv2.line` radar, lupas artificiais ou glitch RGB).
3. Nova Identidade Editorial Broadcast (inspirada em Noclip / Digital Foundry / IGN Specials):
   - Obsidian Glass (`rgba(10, 12, 18, 0.88)`), borda especular fina de 1px (`rgba(255,255,255,0.16)`),
   - Acentos em Warm Editorial Gold (`#F59E0B` / `#FFC400`) e Sky Cyan (`#38BDF8`).
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import os
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw

from composer import FFMPEG_EXE, get_media_duration, load_font
from producao.agentes import AgenteEditorAudiovisual
from producao.catalog import extract_real_trailer_clips
from producao.sound_designer import ensure_studio_sfx_pack, fetch_dynamic_bgm_for_mood

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Cache da máscara de vinheta anamórfica 1920x1080 para performance
_VIGNETTE_MASK_1080P = None


def _get_vignette_mask():
    global _VIGNETTE_MASK_1080P
    if _VIGNETTE_MASK_1080P is None:
        yy, xx = np.mgrid[0:1080, 0:1920].astype(np.float32)
        nx = (xx - 960.0) / 960.0
        ny = (yy - 540.0) / 540.0
        dist2 = (nx * 0.85) ** 2 + (ny * 1.05) ** 2
        mask = np.clip(1.0 - 0.24 * (dist2 ** 1.35), 0.72, 1.0)
        _VIGNETTE_MASK_1080P = mask[:, :, None]
    return _VIGNETTE_MASK_1080P


def _clean_ascii(t):
    return "".join(c for c in (t or "") if ord(c) < 65000).strip()


def _load_video_frames(mp4_path, max_frames=165, size=(1920, 1080)):
    """Carrega frames de um clipe MP4 redimensionados para (W, H)."""
    if not mp4_path or not os.path.exists(mp4_path):
        return []
    cap = cv2.VideoCapture(mp4_path)
    frames = []
    while len(frames) < max_frames:
        ret, fr = cap.read()
        if not ret or fr is None:
            break
        if (fr.shape[1], fr.shape[0]) != size:
            fr = cv2.resize(fr, size, interpolation=cv2.INTER_LINEAR)
        frames.append(fr)
    cap.release()
    return frames


def _get_clip_frame(frames_list, idx):
    if not frames_list:
        return None
    n = len(frames_list)
    if n == 1:
        return frames_list[0].copy()
    cycle = 2 * (n - 1)
    pos = idx % cycle
    real_i = pos if pos < n else cycle - pos
    return frames_list[real_i].copy()


def _apply_higgsfield_camera_motion(frame_bgr, f_idx, total_frames, mode=0):
    """
    Movimentação de câmera cinematográfica estilo Higgsfield DoP (Director of Photography):
    - Modo 0: Slow Anamorphic Dolly Push-In (1.00 -> 1.055) + flutuação orgânica handheld
    - Modo 1: Dolly Pull-Back Reveal (1.055 -> 1.005) + leve deriva lateral
    - Modo 2: Tracking Pan Cinematográfico Esquerda -> Direita com estabilização de horizonte
    """
    if frame_bgr is None:
        return np.full((1080, 1920, 3), 10, dtype=np.uint8)
    h, w = frame_bgr.shape[:2]
    p = max(0.0, min(1.0, f_idx / float(max(1, total_frames - 1))))
    # Curva suave ease-in-out
    ease = 0.5 - 0.5 * math.cos(p * math.pi)

    # Flutuação orgânica sutil de câmera de cinema (handheld breathing)
    breath_x = 6.5 * math.sin(f_idx * 0.055 + mode * 1.7)
    breath_y = 4.0 * math.cos(f_idx * 0.042 + mode * 0.9)

    if mode % 3 == 0:
        zoom = 1.005 + 0.050 * ease
        pan_x = breath_x + 14.0 * (ease - 0.5)
        pan_y = breath_y
    elif mode % 3 == 1:
        zoom = 1.055 - 0.048 * ease
        pan_x = breath_x - 14.0 * (ease - 0.5)
        pan_y = breath_y
    else:
        zoom = 1.038
        pan_x = breath_x + 28.0 * (ease - 0.5)
        pan_y = breath_y + 6.0 * (0.5 - ease)

    crop_w = int(round(w / zoom))
    crop_h = int(round(h / zoom))
    cx = int(round(w * 0.5 + pan_x))
    cy = int(round(h * 0.5 + pan_y))

    x0 = max(0, min(w - crop_w, cx - crop_w // 2))
    y0 = max(0, min(h - crop_h, cy - crop_h // 2))
    cropped = frame_bgr[y0 : y0 + crop_h, x0 : x0 + crop_w]
    out = cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)

    # Vinheta óptica sutil nas bordas para acabamento de lente anamórfica
    vig = _get_vignette_mask()
    return (out.astype(np.float32) * vig).astype(np.uint8)


def _apply_editorial_transition(frame_a, frame_b, progress_0_1):
    """Cross-dissolve cinematográfico suave com curva S-curve e sutil bloom de exposição."""
    p = max(0.0, min(1.0, progress_0_1))
    ease = 0.5 - 0.5 * math.cos(p * math.pi)
    blended = cv2.addWeighted(frame_a, 1.0 - ease, frame_b, ease, 0)
    # Leve pulso de exposição cinematográfica no centro da transição (film optical dissolve)
    exposure_boost = 1.0 + 0.045 * math.sin(p * math.pi)
    return np.clip(blended.astype(np.float32) * exposure_boost, 0, 255).astype(np.uint8)


def _build_top_editorial_bar(badge_type, source_label, act_num, total_acts, act_title):
    """Cria a barra editorial superior 1920x64 em Obsidian Glass com selo de verificação e indicador de Ato."""
    bar_pil = Image.new("RGBA", (1920, 64), (7, 9, 14, 218))
    draw = ImageDraw.Draw(bar_pil, "RGBA")
    # Linha inferior especular de 1px
    draw.line([(0, 63), (1920, 63)], fill=(255, 255, 255, 28), width=1)

    badge_colors = {
        "OFICIAL": ((16, 185, 129, 255), "FONTE OFICIAL ROCKSTAR"),
        "CONFIRMADO": ((56, 189, 248, 255), "CONFIRMADO // VERIFICADO"),
        "RUMOR": ((245, 158, 11, 255), "RUMOR DE MERCADO"),
        "ANALISE": ((168, 85, 247, 255), "ANALISE EDITORIAL"),
    }
    b_col, b_text = badge_colors.get((badge_type or "OFICIAL").upper(), badge_colors["OFICIAL"])

    f_badge = load_font(18)
    f_src = load_font(17)
    f_act = load_font(18)

    # Pill do selo à esquerda
    tb = draw.textbbox((0, 0), b_text, font=f_badge)
    bw = (tb[2] - tb[0]) + 34
    draw.rounded_rectangle([40, 14, 40 + bw, 50], radius=6, fill=(15, 20, 30, 240), outline=b_col, width=1)
    draw.ellipse([52, 27, 60, 35], fill=b_col)
    draw.text((68, 21), b_text, font=f_badge, fill=(248, 250, 252, 255))

    # Fonte verificada
    clean_src = _clean_ascii(source_label or "Rockstar Games Official / rockstargames.com/VI")[:64]
    draw.text((40 + bw + 18, 22), clean_src, font=f_src, fill=(148, 163, 184, 235))

    # Indicador de Ato à direita
    act_str = f"ATO {act_num}/{total_acts}  •  {_clean_ascii(act_title).upper()[:34]}"
    ab = draw.textbbox((0, 0), act_str, font=f_act)
    aw = ab[2] - ab[0]
    draw.text((1920 - 44 - aw, 21), act_str, font=f_act, fill=(245, 158, 11, 245))

    return cv2.cvtColor(np.array(bar_pil.convert("RGB")), cv2.COLOR_RGB2BGR)


def _draw_lower_third_and_hud(frame_bgr, top_hud_strip, headline, subheadline, callout, f_idx, show_lower_third=True):
    """
    Aplica a barra editorial superior de 64px e, apenas nos primeiros 3.8 segundos do bloco,
    um Lower-Third broadcast minimalista em Obsidian Glass com acento Warm Gold (#F59E0B).
    """
    out = frame_bgr.copy()
    out[0:64, :] = cv2.addWeighted(top_hud_strip, 0.88, out[0:64, :], 0.12, 0)

    if not show_lower_third:
        return out

    # Entrada suave nos primeiros 12 frames e saída suave nos últimos 12 frames da janela de 92 frames (3.8s)
    if f_idx < 12:
        p = f_idx / 12.0
    elif f_idx > 80:
        p = max(0.0, (92 - f_idx) / 12.0)
    else:
        p = 1.0
    ease = 1.0 - (1.0 - p) ** 3
    x_off = int(-480 * (1.0 - ease))
    alpha_mul = max(0.0, min(1.0, ease))

    img_pil = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")
    f_tag = load_font(19)
    f_head = load_font(36)
    f_sub = load_font(21)

    bx0 = 48 + x_off
    by0 = 758
    bw = 740
    bh = 128

    bg_a = int(224 * alpha_mul)
    bd_a = int(48 * alpha_mul)
    ac_a = int(255 * alpha_mul)
    tx_a = int(250 * alpha_mul)
    sb_a = int(205 * alpha_mul)

    draw.rounded_rectangle(
        [bx0, by0, bx0 + bw, by0 + bh],
        radius=10,
        fill=(10, 12, 18, bg_a),
        outline=(255, 255, 255, bd_a),
        width=1,
    )
    # Barra vertical de acento Warm Editorial Gold (4px)
    draw.rounded_rectangle([bx0, by0 + 10, bx0 + 4, by0 + bh - 10], radius=2, fill=(245, 158, 11, ac_a))

    tag_str = f"DOSSIE GTA VI  •  {_clean_ascii(callout or 'LEONIDA').upper()}"
    draw.text((bx0 + 22, by0 + 14), tag_str[:50], font=f_tag, fill=(245, 158, 11, ac_a))
    draw.text((bx0 + 22, by0 + 42), _clean_ascii(headline).upper()[:40], font=f_head, fill=(248, 250, 252, tx_a))
    draw.text((bx0 + 22, by0 + 90), _clean_ascii(subheadline)[:68], font=f_sub, fill=(148, 163, 184, sb_a))

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _draw_word_caption_pil(frame_bgr, words, t_sec):
    """
    Legenda Broadcast V3 para Vídeo Longo (Zero Caixa de Fundo — Estilo Viral Clean):
    - Exibe 2 a 3 palavras grandes por vez (fonte 64px ExtraBold) no terço inferior (y=935).
    - Contorno preto espesso (stroke_width=8) + sombra projetada profunda (+5px Y).
    - Palavra ativa em Amarelo Elétrico (#FFE600) e demais em Branco Puro (#FFFFFF).
    """
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

    chunk_start = (active_idx // 3) * 3
    chunk = words[chunk_start : chunk_start + 3]
    if not chunk:
        return frame_bgr

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")
    font = load_font(64)

    tokens = [_clean_ascii(it["w"]).upper() for it in chunk]
    full_str = " ".join(tokens)
    bb = draw.textbbox((0, 0), full_str, font=font)
    tw = bb[2] - bb[0]
    x0 = (1920 - tw) // 2
    y0 = 936

    xc = x0
    for idx_in_chunk, tok in enumerate(tokens):
        is_curr = (chunk_start + idx_in_chunk) == active_idx
        col = (255, 230, 0, 255) if is_curr else (255, 255, 255, 255)
        draw.text(
            (xc + 3, y0 + 5),
            tok,
            font=font,
            fill=(0, 0, 0, 235),
            stroke_width=9,
            stroke_fill=(0, 0, 0, 235),
        )
        draw.text(
            (xc, y0),
            tok,
            font=font,
            fill=col,
            stroke_width=8,
            stroke_fill=(0, 0, 0, 255),
        )
        wb_sp = draw.textbbox((0, 0), tok + " ", font=font)
        xc += wb_sp[2] - wb_sp[0]

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _render_block_video(job, fallback_clips, sfx_pack, work_dir):
    """
    Renderiza um bloco de 15-20s aplicando a Regra Seletiva 75/25:
    - Se `scene_type in ("map_zoom", "character_dossier", "data_comparison")` (~20-25% dos blocos):
      Usa o vídeo `.mp4` REAL renderizado pelo Remotion (`remotion_mp4`) nos primeiros 45% do bloco,
      e depois faz cross-dissolve cinematográfico para 2 clipes 1080p de gameplay com câmera Higgsfield DoP.
    - Se `scene_type == "cinema_broll"` (~75-80% dos blocos):
      Exibe 3 clipes 1080p reais de gameplay/trailer de GTA 6 em tela cheia com câmera Higgsfield DoP,
      cross-dissolves suaves de 10 frames e Lower-Third broadcast apenas nos primeiros 3.8s (92 frames).
    """
    bid = job["bid"]
    blk = job["blk"]
    dur = job["dur"]
    words = job["words"]
    fps = 24
    total_frames = max(24, int(round(dur * fps)))
    scene_type = blk.get("scene_type", "cinema_broll")
    is_remotion_scene = scene_type in ("map_zoom", "character_dossier", "data_comparison")

    top_hud_strip = _build_top_editorial_bar(
        blk.get("badge_type", "OFICIAL"),
        blk.get("source_label", "Rockstar Games Official / rockstargames.com/VI"),
        job["act_num"],
        job["total_acts"],
        job["act_title"],
    )

    # Carrega os 3 vídeos 1080p semânticos distintos atribuídos a este bloco
    sem_vids = list(blk.get("video_clips") or [])
    while len(sem_vids) < 3 and fallback_clips:
        sem_vids.append(fallback_clips[(job["global_idx"] * 3 + len(sem_vids)) % len(fallback_clips)])

    frames_v0 = _load_video_frames(sem_vids[0] if len(sem_vids) > 0 else None, max_frames=140)
    frames_v1 = _load_video_frames(sem_vids[1] if len(sem_vids) > 1 else None, max_frames=140) or frames_v0
    frames_v2 = _load_video_frames(sem_vids[2] if len(sem_vids) > 2 else None, max_frames=140) or frames_v1

    remotion_frames = []
    if is_remotion_scene and job.get("remotion_mp4") and os.path.exists(job["remotion_mp4"]):
        remotion_frames = _load_video_frames(job["remotion_mp4"], max_frames=140)

    f1_end = int(total_frames * (0.45 if remotion_frames else 0.34))
    f2_end = int(total_frames * (0.73 if remotion_frames else 0.67))
    trans_len = 10

    headline = blk.get("headline") or blk.get("callout") or "DOSSIE GTA VI"
    subheadline = blk.get("subheadline") or blk.get("asset_subject") or "Gameplay e analise verificada"
    callout = blk.get("callout") or "GTA 6"

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

    for f_idx in range(total_frames):
        t_sec = f_idx / float(fps)

        if f_idx < f1_end:
            if remotion_frames:
                # Sub-cena 1 com Motion Graphic REAL renderizado em vídeo pelo Remotion (24fps)
                rem_fr = _get_clip_frame(remotion_frames, f_idx)
                # Se for map_zoom ou character_dossier, injeta o vídeo 1080p vivo suavemente no painel de mídia
                frame_p1 = rem_fr
            else:
                v0_raw = _get_clip_frame(frames_v0, f_idx)
                v0_cam = _apply_higgsfield_camera_motion(v0_raw, f_idx, f1_end, mode=job["global_idx"])
                frame_p1 = _draw_lower_third_and_hud(
                    v0_cam, top_hud_strip, headline, subheadline, callout, f_idx, show_lower_third=(f_idx < 92)
                )

            if f_idx >= f1_end - trans_len:
                tp = (f_idx - (f1_end - trans_len)) / float(trans_len)
                v1_raw = _get_clip_frame(frames_v1, 0)
                v1_cam = _apply_higgsfield_camera_motion(v1_raw, 0, f2_end - f1_end, mode=job["global_idx"] + 1)
                target_b = _draw_lower_third_and_hud(
                    v1_cam, top_hud_strip, headline, subheadline, callout, f_idx, show_lower_third=(f_idx < 92)
                )
                base = _apply_editorial_transition(frame_p1, target_b, tp)
            else:
                base = frame_p1

        elif f_idx < f2_end:
            rel_f = f_idx - f1_end
            v1_raw = _get_clip_frame(frames_v1, rel_f)
            v1_cam = _apply_higgsfield_camera_motion(v1_raw, rel_f, f2_end - f1_end, mode=job["global_idx"] + 1)
            # Se a Sub-cena 1 foi Remotion, mostra o lower-third brevemente ao entrar no gameplay da Sub-cena 2
            show_lt = (rel_f < 72) if remotion_frames else (f_idx < 92)
            lt_frame = rel_f if remotion_frames else f_idx
            frame_p2 = _draw_lower_third_and_hud(
                v1_cam, top_hud_strip, headline, subheadline, callout, lt_frame, show_lower_third=show_lt
            )

            if f_idx >= f2_end - trans_len:
                tp = (f_idx - (f2_end - trans_len)) / float(trans_len)
                v2_raw = _get_clip_frame(frames_v2, 0)
                v2_cam = _apply_higgsfield_camera_motion(v2_raw, 0, total_frames - f2_end, mode=job["global_idx"] + 2)
                target_c = _draw_lower_third_and_hud(
                    v2_cam, top_hud_strip, headline, subheadline, callout, f_idx, show_lower_third=False
                )
                base = _apply_editorial_transition(frame_p2, target_c, tp)
            else:
                base = frame_p2

        else:
            rel_f2 = f_idx - f2_end
            v2_raw = _get_clip_frame(frames_v2, rel_f2)
            v2_cam = _apply_higgsfield_camera_motion(v2_raw, rel_f2, total_frames - f2_end, mode=job["global_idx"] + 2)
            base = _draw_lower_third_and_hud(
                v2_cam, top_hud_strip, headline, subheadline, callout, f_idx, show_lower_third=False
            )

        frame_with_sub = _draw_word_caption_pil(base, words, t_sec)
        proc.stdin.write(frame_with_sub.tobytes())

    proc.stdin.close()
    proc.wait()

    # Sound Design Contextual (Agente 4) — sutil e calibrado para broadcast
    if scene_type == "map_zoom":
        sfx_file = sfx_pack["radar_ping"]
    elif scene_type == "data_comparison":
        sfx_file = sfx_pack["sub_drop"]
    elif scene_type == "character_dossier":
        sfx_file = sfx_pack["telemetry"]
    else:
        sfx_file = sfx_pack["whoosh"]

    mid_whoosh_ms = int(dur * (0.45 if remotion_frames else 0.34) * 1000)
    fade_out_st = max(0.0, dur - 0.30)
    aud_fc = (
        f"[1:a]volume=1.24[vo];"
        f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out_st:.2f}:d=0.30,volume=0.20[bm];"
        f"[3:a]volume=0.32[sx1];"
        f"[4:a]adelay={mid_whoosh_ms}|{mid_whoosh_ms},volume=0.26[sx2];"
        f"[vo][bm][sx1][sx2]amix=inputs=4:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
    )
    subprocess.run(
        [
            FFMPEG_EXE, "-y",
            "-i", silent_mp4,
            "-i", job["wav_p"],
            "-stream_loop", "-1", "-ss", f"{job['bgm_ss']:.2f}", "-i", job["bgm_file"],
            "-i", sfx_file,
            "-i", sfx_pack["whoosh"],
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
    """
    Motor de Thumbnail Viral Gaming V3 (1280x720 — Alto CTR para Lançamento & Lives de GTA 6):
    - Fundo 1080p vibrante de Vice City / Lucia & Jason com contraste de cinema e vinheta direcional.
    - Janela Picture-in-Picture da Live (Davy Jones / Bistecone) no canto superior direito com badge '🔴 AO VIVO'.
    - Tipografia de impacto gigante em 1-2 linhas (Branco Puro + Amarelo Elétrico #FFE600) com contorno preto 3D.
    """
    if jpg_path and os.path.exists(jpg_path):
        hero = Image.open(jpg_path).convert("RGB")
    else:
        hero = Image.new("RGB", (1280, 720), (12, 16, 26))

    sc = max(1280.0 / hero.width, 720.0 / hero.height)
    hero = hero.resize((int(hero.width * sc), int(hero.height * sc)), Image.Resampling.LANCZOS)
    x0, y0 = (hero.width - 1280) // 2, (hero.height - 720) // 2
    canvas = hero.crop((x0, y0, x0 + 1280, y0 + 720))

    # Color boost viral (saturação + contraste local + gradiente escuro apenas no terço inferior para o texto)
    arr = np.array(canvas, dtype=np.float32)
    mean = arr.mean(axis=2, keepdims=True)
    arr = np.clip(mean + (arr - mean) * 1.34, 0, 255)
    arr = np.clip((arr - 124) * 1.15 + 124, 0, 255)
    grad = np.ones((720, 1, 1), dtype=np.float32)
    grad[340:] = np.linspace(1.0, 0.12, 720 - 340, dtype=np.float32)[:, None, None]
    arr = arr * grad
    canvas = Image.fromarray(arr.astype(np.uint8))

    # Injeta PiP real de streamer em live (Bistecone / Davy Jones) no canto superior direito
    live_pip_candidates = [
        os.path.join(BASE_DIR, "assets", "gta6_clips", "gta6_live_bistecone_01.mp4"),
        os.path.join(BASE_DIR, "assets", "gta6_clips", "gta6_live_davyjones_02.mp4"),
    ]
    for lp in live_pip_candidates:
        if os.path.exists(lp):
            cap = cv2.VideoCapture(lp)
            cap.set(cv2.CAP_PROP_POS_FRAMES, 35)
            ok, lfr = cap.read()
            cap.release()
            if ok and lfr is not None:
                pip_rgb = cv2.cvtColor(cv2.resize(lfr, (376, 212), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
                pip_im = Image.fromarray(pip_rgb)
                canvas.paste(pip_im, (868, 34))
                break

    draw = ImageDraw.Draw(canvas, "RGBA")
    # Moldura do PiP da Live + Selo 🔴 AO VIVO
    draw.rounded_rectangle([866, 32, 1246, 248], radius=10, outline=(255, 230, 0, 255), width=4)
    f_live = load_font(24)
    draw.rounded_rectangle([878, 42, 1042, 82], radius=8, fill=(220, 20, 20, 245))
    draw.ellipse([890, 54, 904, 68], fill=(255, 255, 255, 255))
    draw.text((912, 48), "AO VIVO", font=f_live, fill=(255, 255, 255, 255))

    # Badge superior esquerdo de autoridade com largura calculada dinamicamente
    f_badge = load_font(32)
    badge_txt = "LANCAMENTO GTA 6 // LIVES"
    btb = draw.textbbox((0, 0), badge_txt, font=f_badge)
    bbw = (btb[2] - btb[0]) + 86
    draw.rounded_rectangle([36, 34, 36 + bbw, 96], radius=12, fill=(10, 12, 18, 235), outline=(255, 230, 0, 255), width=3)
    draw.ellipse([54, 55, 74, 75], fill=(255, 45, 45, 255))
    draw.text((88, 47), badge_txt, font=f_badge, fill=(255, 255, 255, 255))

    # Título gigante de impacto (até 4 palavras curtas)
    f_big = load_font(112)
    clean_h = (_clean_ascii(headline) or "JOGO LIBERADO!").upper()
    tb = draw.textbbox((0, 0), clean_h, font=f_big)
    tw = tb[2] - tb[0]
    while tw > 1190 and f_big.size > 68:
        f_big = load_font(f_big.size - 6)
        tb = draw.textbbox((0, 0), clean_h, font=f_big)
        tw = tb[2] - tb[0]
    tx = 44
    draw.text((tx + 6, 468 + 8), clean_h, font=f_big, fill=(0, 0, 0, 245), stroke_width=12, stroke_fill=(0, 0, 0, 245))
    draw.text((tx, 468), clean_h, font=f_big, fill=(255, 230, 0, 255), stroke_width=10, stroke_fill=(0, 0, 0, 255))

    # Subtítulo de curiosidade extrema na base
    f_sub = load_font(44)
    clean_s = (_clean_ascii(subheadline) or "DAVY JONES E BISTECONE EM CHOQUE EM VICE CITY").upper()[:46]
    sb = draw.textbbox((0, 0), clean_s, font=f_sub)
    sw = sb[2] - sb[0]
    draw.rounded_rectangle([42, 608, 42 + sw + 36, 678], radius=10, fill=(220, 25, 25, 245), outline=(255, 255, 255, 220), width=2)
    draw.text((60, 618), clean_s, font=f_sub, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255))

    canvas.save(out_jpg, quality=95)
    return out_jpg


def compose_studio_video(script_data, wav_map, words_map, work_dir, output_mp4, output_thumb_jpg):
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
                "[1:a]volume=0.65[s];[2:a]atrim=0:2.20,volume=0.90[b];[s][b]amix=inputs=2:duration=longest:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[a]",
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
                "remotion_mp4": None,
            })
            bgm_offset += dur
            total_t += dur
            global_idx += 1

    # Renderiza vídeos .MP4 REAIS no Remotion APENAS para os blocos especiais (Regra 75/25: map_zoom, character_dossier, data_comparison)
    remotion_jobs = [j for j in block_jobs if j["blk"].get("scene_type") in ("map_zoom", "character_dossier", "data_comparison")]
    print(
        f"[STUDIO COMPOSER V3] {len(block_jobs)} blocos totais | "
        f"{len(remotion_jobs)} animações Remotion em vídeo (.mp4) | "
        f"{len(block_jobs) - len(remotion_jobs)} blocos Cinema B-Roll 1080p com câmera Higgsfield DoP...",
        flush=True,
    )

    for job in remotion_jobs:
        bid = job["bid"]
        rem_mp4 = os.path.join(work_dir, f"remotion_vid_{bid}.mp4")
        if not os.path.exists(rem_mp4):
            blk = job["blk"]
            rem_dur = min(5.0, max(3.0, job["dur"] * 0.45))
            props = {
                "sceneType": blk.get("scene_type", "map_zoom"),
                "badgeType": blk.get("badge_type", "OFICIAL"),
                "sourceLabel": blk.get("source_label", "Rockstar Games Official / rockstargames.com/VI"),
                "actNum": job["act_num"],
                "totalActs": job["total_acts"],
                "actTitle": job["act_title"],
                "headline": blk.get("headline") or blk.get("callout") or "DOSSIE GTA VI",
                "subheadline": blk.get("subheadline") or blk.get("asset_subject") or "Analise audiovisual verificada",
                "locationKey": blk.get("location_key", "vice_city"),
                "characterName": blk.get("character_name", "LUCIA & JASON"),
                "characterRole": blk.get("character_role", "PROTAGONISTAS // LEONIDA"),
                "characterFacts": blk.get("character_facts", []),
                "statValue": blk.get("stat_value", "19 NOV"),
                "statUnit": blk.get("stat_unit", "LANCAMENTO OFICIAL"),
                "statLabel": blk.get("stat_label", "TELEMETRIA & DADOS VERIFICADOS"),
                "comparisonItems": blk.get("comparison_items", []),
                "primaryImageUrl": blk.get("primary_img") or "",
                "secondaryImageUrl": blk.get("secondary_img") or "",
                "words": [],
            }
            print(f"[REMOTION VIDEO V3] Renderizando {bid} ({props['sceneType']}, {rem_dur:.1f}s a 24fps)...", flush=True)
            AgenteEditorAudiovisual.render_remotion_motion_scene(props, dur_sec=rem_dur, out_mp4=rem_mp4)
        job["remotion_mp4"] = rem_mp4

    done = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [pool.submit(_render_block_video, j, trailer_clips, sfx_pack, work_dir) for j in block_jobs]
        for fut in as_completed(futs):
            fut.result()
            done += 1
            print(f"[STUDIO COMPOSER V3] Bloco {done}/{len(block_jobs)} concluído.", flush=True)

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
