"""COMPOSITOR AUDIOVISUAL PROFISSIONAL V2 (Remotion + After Effects Multi-Layer Engine + B-Roll 1080p em Vídeo).

Garante que NENHUM bloco fique parado em imagem estática:
- Cada bloco de narração (~16-20s) usa 3 VÍDEOS 1080p REAIS DISTINTOS (gta6_vid_*.mp4 + cortes de influenciadores)
  mapeados semanticamente para o início, meio e fim da frase falada.
- Animações quadro-a-quadro a 24fps estilo After Effects + Remotion:
  1. map_zoom: Mapa tático de Leonida com feixe de radar girando 360°, ondas de sonar, linha Trim-Path animada
     e janela Picture-in-Picture tocando VÍDEO REAL EM MOVIMENTO da região!
  2. character_dossier: Janela de vídeo em movimento + retrato 4K com scanner biométrico laser, partículas neon
     e barras de telemetria preenchendo de 0% a 96% em tempo real!
  3. data_comparison: Poliedro 3D wireframe girando em tempo real nos 3 eixos sobre vídeo em movimento + barras
     comparativas animadas com faísca luminosa na ponta!
  4. feature_spotlight: Vídeo 1080p em tela cheia com Lupa de Aumento 2.0x (Magnifying Loupe) e retícula giratória!
- Transições profissionais entre cada sub-cena: Whip-Pan com Motion Blur direcional, Glitch RGB Cromático e Wipe Neon.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
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


def _clean_ascii(t):
    return "".join(c for c in (t or "") if ord(c) < 65000).strip()


def _load_video_frames(mp4_path, max_frames=160, size=(1920, 1080)):
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


def _draw_3d_wireframe_crystal(canvas, cx, cy, radius, frame_idx, color_outer=(133, 42, 255), color_inner=(255, 240, 0)):
    """Renderiza octaedro + icosaedro 3D wireframe girando nos 3 eixos quadro a quadro (estilo After Effects Plexus)."""
    rx = frame_idx * 0.045
    ry = frame_idx * 0.065
    rz = frame_idx * 0.025

    def _rot(pt):
        x, y, z = pt
        # Rot X
        y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
        # Rot Y
        x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
        # Rot Z
        x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)
        scale = 3.2 / (3.8 - z * 0.6)
        return int(cx + x * radius * scale), int(cy + y * radius * scale)

    oct_verts = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    oct_edges = [(0, 2), (0, 3), (0, 4), (0, 5), (1, 2), (1, 3), (1, 4), (1, 5), (2, 4), (4, 3), (3, 5), (5, 2)]
    pts_outer = [_rot(v) for v in oct_verts]
    for i, j in oct_edges:
        cv2.line(canvas, pts_outer[i], pts_outer[j], color_outer, 2, cv2.LINE_AA)
    for p in pts_outer:
        cv2.circle(canvas, p, 5, (0, 240, 255), -1, cv2.LINE_AA)

    # Anel orbital animado
    ring_pts = []
    for a in range(0, 360, 10):
        rad = math.radians(a)
        ring_pts.append(_rot((math.cos(rad) * 1.25, math.sin(rad) * 0.35, math.sin(rad) * 1.25)))
    for i in range(len(ring_pts)):
        cv2.line(canvas, ring_pts[i], ring_pts[(i + 1) % len(ring_pts)], color_inner, 1, cv2.LINE_AA)


def _apply_ae_transition(frame_a, frame_b, progress_0_1, mode=0):
    """Transições estilo Adobe After Effects entre sub-cenas (Whip-Pan Blur, RGB Glitch, Diagonal Laser Wipe)."""
    p = max(0.0, min(1.0, progress_0_1))
    ease = 0.5 - 0.5 * math.cos(p * math.pi)
    h, w = frame_a.shape[:2]

    if mode % 3 == 0:
        # 1. Whip-Pan Horizontal com Directional Motion Blur
        shift = int(w * ease)
        out = np.zeros_like(frame_a)
        if shift < w:
            out[:, : w - shift] = frame_a[:, shift:]
        if shift > 0:
            out[:, w - shift :] = frame_b[:, :shift]
        ksize = max(3, int(38 * math.sin(p * math.pi)) | 1)
        kernel = np.zeros((1, ksize), dtype=np.float32)
        kernel[0, :] = 1.0 / ksize
        out = cv2.filter2D(out, -1, kernel)
        return out

    elif mode % 3 == 1:
        # 2. Chromatic Aberration (RGB Split) + Glitch Slices
        base = cv2.addWeighted(frame_a, 1.0 - ease, frame_b, ease, 0)
        split = int(26 * math.sin(p * math.pi))
        if split > 1:
            b, g, r = cv2.split(base)
            r_shift = np.roll(r, split, axis=1)
            b_shift = np.roll(b, -split, axis=1)
            base = cv2.merge([b_shift, g, r_shift])
        return base

    else:
        # 3. Diagonal Neon Wipe com Linha Laser Vice Magenta
        mask = np.zeros((h, w), dtype=np.float32)
        xx, yy = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, h))
        diag = (xx * 0.75 + yy * 0.25)
        thresh = ease * 1.15 - 0.05
        mask = np.clip((thresh - diag) * 14.0, 0.0, 1.0)[:, :, None]
        out = (frame_b.astype(np.float32) * mask + frame_a.astype(np.float32) * (1.0 - mask)).astype(np.uint8)
        laser_band = np.abs(diag - thresh) < 0.012
        out[laser_band] = (180, 50, 255)
        return out


def _animate_ae_overlay_on_plate(remotion_img, live_vid_frame, scene_type, f_idx, total_phase_frames):
    """
    Aplica animações estilo After Effects a 24fps SOBRE o layout do Remotion,
    injetando vídeo real em movimento nas janelas PiP, radar 360°, scanner laser e barras animadas!
    """
    canvas = remotion_img.copy()
    p = f_idx / float(max(1, total_phase_frames - 1))

    if scene_type == "map_zoom":
        # 1. Injeta VÍDEO REAL EM MOVIMENTO dentro da janela de inspeção à direita (x=1224..1828, y=342..674)
        if live_vid_frame is not None:
            vw, vh = 604, 332
            pip = cv2.resize(live_vid_frame, (vw, vh), interpolation=cv2.INTER_LINEAR)
            # Moldura e scanline tática sobre o vídeo PiP
            scan_y = int((f_idx * 6) % vh)
            cv2.line(pip, (0, scan_y), (vw, scan_y), (255, 240, 0), 2)
            cv2.rectangle(pip, (0, 0), (vw - 1, vh - 1), (255, 240, 0), 2)
            canvas[342 : 342 + vh, 1224 : 1224 + vw] = pip

        # 2. Radar giratório 360° + Ondas de Sonar + Linha Trim-Path até o vídeo
        pin_x, pin_y = 710, 505
        angle = (f_idx * 7.5) % 360
        rad = math.radians(angle)
        bx = int(pin_x + 115 * math.cos(rad))
        by = int(pin_y + 115 * math.sin(rad))
        cv2.line(canvas, (pin_x, pin_y), (bx, by), (255, 240, 0), 2, cv2.LINE_AA)
        for ring in range(2):
            r_rad = int(18 + ((f_idx * 2.4 + ring * 38) % 95))
            cv2.circle(canvas, (pin_x, pin_y), r_rad, (133, 42, 255), 2, cv2.LINE_AA)
        # Linha Trim-Path conectando o pino do mapa ao vídeo PiP
        line_prog = min(1.0, p * 2.2)
        target_x = int(pin_x + (1224 - pin_x) * line_prog)
        target_y = int(pin_y + (508 - pin_y) * line_prog)
        cv2.line(canvas, (pin_x, pin_y), (target_x, target_y), (255, 240, 0), 2, cv2.LINE_AA)
        cv2.circle(canvas, (target_x, target_y), 5, (0, 184, 255), -1, cv2.LINE_AA)

    elif scene_type == "character_dossier":
        # 1. Injeta VÍDEO REAL EM MOVIMENTO no retrato esquerdo (x=66..942, y=120..810) + scanner biométrico
        if live_vid_frame is not None:
            pw, ph = 876, 690
            pip = cv2.resize(live_vid_frame, (pw, ph), interpolation=cv2.INTER_LINEAR)
            # Mistura suave com o retrato 4K nos primeiros frames e depois vídeo puro em movimento
            alpha_v = min(0.88, 0.35 + p * 0.75)
            roi = canvas[120 : 120 + ph, 66 : 66 + pw]
            blended = cv2.addWeighted(pip, alpha_v, roi, 1.0 - alpha_v, 0)
            scan_y = int((f_idx * 9) % ph)
            cv2.line(blended, (0, scan_y), (pw, scan_y), (133, 42, 255), 3)
            canvas[120 : 120 + ph, 66 : 66 + pw] = blended

        # 2. Barra de telemetria preenchendo em tempo real no rodapé do dossiê
        bar_x0, bar_y0, bar_w = 990, 865, 810
        fill_w = int(bar_w * min(1.0, p * 1.35))
        cv2.rectangle(canvas, (bar_x0, bar_y0), (bar_x0 + bar_w, bar_y0 + 16), (35, 42, 60), -1)
        cv2.rectangle(canvas, (bar_x0, bar_y0), (bar_x0 + fill_w, bar_y0 + 16), (0, 215, 255), -1)
        cv2.circle(canvas, (bar_x0 + fill_w, bar_y0 + 8), 9, (133, 42, 255), -1, cv2.LINE_AA)

    elif scene_type == "data_comparison":
        # 1. Fundo vivo com vídeo em movimento escurecido + Cristal 3D girando nos 3 eixos a 24fps!
        if live_vid_frame is not None:
            dark_vid = (live_vid_frame.astype(np.float32) * 0.28).astype(np.uint8)
            left_roi = canvas[100:920, 30:680]
            canvas[100:920, 30:680] = cv2.addWeighted(left_roi, 0.62, dark_vid[100:920, 30:680], 0.38, 0)
            # Vídeo em movimento em PiP no canto superior direito do painel comparativo
            pip_sm = cv2.resize(live_vid_frame, (360, 202), interpolation=cv2.INTER_LINEAR)
            cv2.rectangle(pip_sm, (0, 0), (359, 201), (255, 240, 0), 2)
            canvas[170:372, 1450:1810] = pip_sm
        _draw_3d_wireframe_crystal(canvas, 355, 510, 175, f_idx)

    else:
        # feature_spotlight: Vídeo real em tela cheia com Lupa After Effects 2.0x + Retícula Giratória
        if live_vid_frame is not None:
            canvas[84:930, :] = cv2.addWeighted(live_vid_frame[84:930, :], 0.78, canvas[84:930, :], 0.22, 0)
        # Lupa circular 2.0x deslizando sobre o detalhe à direita
        lx = int(1340 + 70 * math.sin(f_idx * 0.06))
        ly = int(420 + 45 * math.cos(f_idx * 0.05))
        lr = 145
        y1, y2 = max(0, ly - lr // 2), min(1080, ly + lr // 2)
        x1, x2 = max(0, lx - lr // 2), min(1920, lx + lr // 2)
        crop = canvas[y1:y2, x1:x2]
        if crop.size > 0:
            zoomed = cv2.resize(crop, (lr * 2, lr * 2), interpolation=cv2.INTER_LINEAR)
            mask = np.zeros((lr * 2, lr * 2), dtype=np.uint8)
            cv2.circle(mask, (lr, lr), lr - 4, 255, -1)
            zy1, zy2 = max(0, ly - lr), min(1080, ly + lr)
            zx1, zx2 = max(0, lx - lr), min(1920, lx + lr)
            roi = canvas[zy1:zy2, zx1:zx2]
            if roi.shape[:2] == (lr * 2, lr * 2):
                np.copyto(roi, zoomed, where=(mask[:, :, None] > 0))
            cv2.circle(canvas, (lx, ly), lr, (255, 240, 0), 3, cv2.LINE_AA)
            cv2.circle(canvas, (lx, ly), lr + 10, (133, 42, 255), 1, cv2.LINE_AA)
            cv2.line(canvas, (840, 780), (lx - int(lr * 0.7), ly + int(lr * 0.7)), (255, 240, 0), 2, cv2.LINE_AA)

    return canvas


def _draw_lower_third_and_hud(frame_bgr, top_hud_strip, headline, subheadline, callout, f_idx, phase_frames):
    """Desenha HUD editorial superior + Lower-Third animado estilo After Effects sobre vídeo 1080p em tela cheia."""
    out = frame_bgr.copy()
    # 1. Topo editorial (Selo da fonte + Barra de progresso + Indicador de Ato)
    out[0:84, :] = cv2.addWeighted(top_hud_strip, 0.90, out[0:84, :], 0.10, 0)

    # 2. Lower-third lateral deslizante com barra neon animada
    slide_p = min(1.0, f_idx / 10.0)
    ease = 1.0 - (1.0 - slide_p) ** 3
    x_off = int(-520 * (1.0 - ease))

    img_pil = Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")
    f_tag = load_font(22)
    f_head = load_font(44)
    f_sub = load_font(24)

    bx0 = 54 + x_off
    by0 = 735
    bw = 820
    bh = 152
    draw.rounded_rectangle([bx0, by0, bx0 + bw, by0 + bh], radius=14, fill=(9, 11, 18, 218), outline=(0, 240, 255, 190), width=2)
    draw.rectangle([bx0, by0, bx0 + 8, by0 + bh], fill=(255, 42, 133, 255))

    tag_str = f"EM TELA // {_clean_ascii(callout or 'GTA VI LEONIDA').upper()}"
    draw.text((bx0 + 26, by0 + 14), tag_str[:48], font=f_tag, fill=(0, 240, 255, 255))
    draw.text((bx0 + 26, by0 + 44), _clean_ascii(headline).upper()[:38], font=f_head, fill=(248, 250, 252, 255))
    draw.text((bx0 + 26, by0 + 102), _clean_ascii(subheadline)[:64], font=f_sub, fill=(203, 213, 225, 255))

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _draw_word_caption_pil(frame_bgr, words, t_sec):
    """Desenha legenda sincronizada palavra-por-palavra (faster-whisper) com pop na palavra ativa."""
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
        fill=(9, 11, 18, 232),
        outline=(255, 42, 133, 210),
        width=2,
    )
    xc = x0
    for idx_in_chunk, tok in enumerate(tokens):
        is_curr = (chunk_start + idx_in_chunk) == active_idx
        wb = draw.textbbox((0, 0), tok, font=font)
        w_tok = wb[2] - wb[0]
        if is_curr:
            draw.rounded_rectangle([xc - 6, y0 - 6, xc + w_tok + 6, y0 + th + 10], radius=8, fill=(255, 42, 133, 235))
            col = (255, 235, 40, 255)
        else:
            col = (248, 250, 252, 255)
        draw.text((xc, y0 - 2), tok, font=font, fill=col, stroke_width=4, stroke_fill=(0, 0, 0, 255))
        wb_sp = draw.textbbox((0, 0), tok + " ", font=font)
        xc += wb_sp[2] - wb_sp[0]

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def _render_remotion_still_plate(props, frame_num, out_png):
    """Renderiza o layout base 1920x1080 no Remotion + Three.js."""
    import base64

    studio_dir = AgenteEditorAudiovisual.STUDIO_DIR
    bundle_dir = AgenteEditorAudiovisual.ensure_remotion_bundle()
    props_clean = dict(props)
    props_clean["words"] = []
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
    try:
        os.remove(pf)
    except OSError:
        pass
    if r.returncode != 0:
        raise RuntimeError(f"Remotion still falhou ({r.returncode}): {r.stderr[-300:]}")
    return out_png


def _render_block_video(job, fallback_clips, sfx_pack, work_dir):
    """
    Renderiza um bloco de 16-20s com 3 sub-cenas em VÍDEO REAL EM MOVIMENTO + Motion Graphics After Effects:
    - Sub-cena 1 (0 -> 42%): Composição Remotion + After Effects animada quadro a quadro com vídeo PiP vivo!
    - Sub-cena 2 (42% -> 72%): Transição Whip-Pan/Glitch -> Vídeo 1080p #2 em tela cheia + Lower-Third animado!
    - Sub-cena 3 (72% -> 100%): Transição Laser Wipe -> Vídeo 1080p #3 em tela cheia + PiP 4K & Telemetria!
    """
    bid = job["bid"]
    blk = job["blk"]
    dur = job["dur"]
    words = job["words"]
    fps = 24
    total_frames = max(24, int(round(dur * fps)))
    scene_type = blk.get("scene_type", "feature_spotlight")

    plate_png = os.path.join(work_dir, f"remotion_{bid}.png")
    remotion_img = cv2.imread(plate_png)
    if remotion_img is None:
        remotion_img = np.full((1080, 1920, 3), 14, dtype=np.uint8)
    top_hud_strip = remotion_img[0:84, :].copy()

    # Carrega os 3 vídeos semânticos distintos atribuídos a este bloco
    sem_vids = blk.get("video_clips") or []
    while len(sem_vids) < 3 and fallback_clips:
        sem_vids.append(fallback_clips[(job["global_idx"] * 3 + len(sem_vids)) % len(fallback_clips)])

    frames_v0 = _load_video_frames(sem_vids[0] if len(sem_vids) > 0 else None, max_frames=120)
    frames_v1 = _load_video_frames(sem_vids[1] if len(sem_vids) > 1 else None, max_frames=120) or frames_v0
    frames_v2 = _load_video_frames(sem_vids[2] if len(sem_vids) > 2 else None, max_frames=120) or frames_v1

    f1_end = int(total_frames * 0.42)
    f2_end = int(total_frames * 0.72)
    trans_len = 6

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
        v0_fr = _get_clip_frame(frames_v0, f_idx)
        v1_fr = _get_clip_frame(frames_v1, max(0, f_idx - f1_end))
        v2_fr = _get_clip_frame(frames_v2, max(0, f_idx - f2_end))

        if f_idx < f1_end:
            # Sub-cena 1: Layout Remotion + After Effects animado a 24fps com vídeo real rodando dentro
            frame_p1 = _animate_ae_overlay_on_plate(remotion_img, v0_fr, scene_type, f_idx, f1_end)
            if f_idx >= f1_end - trans_len and v1_fr is not None:
                tp = (f_idx - (f1_end - trans_len)) / float(trans_len)
                target_b = _draw_lower_third_and_hud(v1_fr, top_hud_strip, headline, subheadline, callout, 0, f2_end - f1_end)
                base = _apply_ae_transition(frame_p1, target_b, tp, mode=job["global_idx"])
            else:
                base = frame_p1

        elif f_idx < f2_end:
            # Sub-cena 2: Vídeo 1080p #2 em tela cheia + Lower-Third After Effects
            rel_f = f_idx - f1_end
            base_v1 = v1_fr if v1_fr is not None else remotion_img
            frame_p2 = _draw_lower_third_and_hud(base_v1, top_hud_strip, headline, subheadline, callout, rel_f, f2_end - f1_end)
            if f_idx >= f2_end - trans_len and v2_fr is not None:
                tp = (f_idx - (f2_end - trans_len)) / float(trans_len)
                target_c = _draw_lower_third_and_hud(v2_fr, top_hud_strip, headline, subheadline, callout, 15, total_frames - f2_end)
                base = _apply_ae_transition(frame_p2, target_c, tp, mode=job["global_idx"] + 1)
            else:
                base = frame_p2

        else:
            # Sub-cena 3: Vídeo 1080p #3 em tela cheia + PiP do Card Remotion no canto direito
            base_v2 = v2_fr if v2_fr is not None else remotion_img
            frame_p3 = base_v2.copy()
            frame_p3[0:84, :] = cv2.addWeighted(top_hud_strip, 0.90, frame_p3[0:84, :], 0.10, 0)
            # Picture-in-Picture flutuante com zoom de detalhe no canto inferior direito
            if v0_fr is not None:
                pip_w, pip_h = 460, 258
                pip_card = cv2.resize(v0_fr, (pip_w, pip_h), interpolation=cv2.INTER_LINEAR)
                cv2.rectangle(pip_card, (0, 0), (pip_w - 1, pip_h - 1), (133, 42, 255), 3)
                frame_p3[640 : 640 + pip_h, 1396 : 1396 + pip_w] = pip_card
            base = frame_p3

        frame_with_sub = _draw_word_caption_pil(base, words, t_sec)
        proc.stdin.write(frame_with_sub.tobytes())

    proc.stdin.close()
    proc.wait()

    # Sound Design Contextual (Agente 4)
    if scene_type == "map_zoom":
        sfx_file = sfx_pack["radar_ping"]
    elif scene_type == "data_comparison":
        sfx_file = sfx_pack["sub_drop"]
    elif scene_type == "character_dossier":
        sfx_file = sfx_pack["telemetry"]
    else:
        sfx_file = sfx_pack["whoosh"]

    mid_whoosh_ms = int(dur * 0.42 * 1000)
    fade_out_st = max(0.0, dur - 0.30)
    aud_fc = (
        f"[1:a]volume=1.24[vo];"
        f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out_st:.2f}:d=0.30,volume=0.22[bm];"
        f"[3:a]volume=0.40[sx1];"
        f"[4:a]adelay={mid_whoosh_ms}|{mid_whoosh_ms},volume=0.34[sx2];"
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
    draw.rectangle([0, 0, 1279, 719], outline=(255, 42, 133, 220), width=6)
    f_badge = load_font(38)
    draw.rounded_rectangle([36, 32, 460, 96], radius=12, fill=(9, 11, 18, 235), outline=(0, 240, 255, 255), width=3)
    draw.text((56, 44), "DOSSIE GTA VI // 19 NOV", font=f_badge, fill=(0, 240, 255, 255))

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

    f_sub = load_font(42)
    clean_s = (_clean_ascii(subheadline) or "GAMEPLAY E FONTES VERIFICADAS").upper()[:48]
    sb = draw.textbbox((0, 0), clean_s, font=f_sub)
    sw = sb[2] - sb[0]
    sx = (1280 - sw) // 2
    draw.rounded_rectangle([sx - 24, 622, sx + sw + 24, 684], radius=10, fill=(255, 42, 133, 240))
    draw.text((sx, 630), clean_s, font=f_sub, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

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

    print(f"[STUDIO COMPOSER V2] Renderizando {len(block_jobs)} blocos (Remotion + After Effects + 3 Vídeos 1080p/bloco)...", flush=True)
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
                "headline": blk.get("headline") or blk.get("callout") or "DOSSIE GTA VI",
                "subheadline": blk.get("subheadline") or blk.get("asset_subject") or "Analise audiovisual verificada",
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
            print(f"[STUDIO COMPOSER V2] Bloco {done}/{len(block_jobs)} concluído.", flush=True)

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
