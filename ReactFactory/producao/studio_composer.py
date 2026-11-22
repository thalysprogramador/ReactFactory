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
    """Retorna frame estritamente PARA FRENTE (PROIBIDO efeito reverso / ping-pong!)."""
    if not frames_list:
        return None
    n = len(frames_list)
    if n == 1:
        return frames_list[0].copy()
    real_i = min(max(0, int(idx)), n - 1)
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
    Visual Cinema Limpo V7.1 (pós-auditoria Agente 5):
    - ZERO tarjas escuras pesadas no canto inferior nem selos artificiais no topo (poluíam a tela junto com as legendas!).
    - A tela fica 100% limpa na gameplay Full-HD, destacando apenas as legendas Poppins-Black sincronizadas.
    """
    return frame_bgr


def _draw_word_caption_pil(frame_bgr, words, t_sec):
    """
    Legenda Broadcast Cinema V4 para Vídeo Longo (Poppins-Black ExtraBold — Zero Caixa de Fundo):
    - Exibe 2 a 3 palavras grandes por vez (fonte Poppins-Black 66px) no terço inferior (y=930).
    - Contorno escuro limpo + sombra projetada profunda (+6px Y).
    - Palavra ativa em Ouro Elétrico (#FFE01B) e demais em Branco Puro (#FFFFFF).
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
    font = load_font(66, style="poppins")

    tokens = [_clean_ascii(it["w"]).upper() for it in chunk]
    full_str = " ".join(tokens)
    bb = draw.textbbox((0, 0), full_str, font=font)
    tw = bb[2] - bb[0]
    x0 = (1920 - tw) // 2
    y0 = 885

    xc = x0
    for idx_in_chunk, tok in enumerate(tokens):
        is_curr = (chunk_start + idx_in_chunk) == active_idx
        col = (255, 224, 27, 255) if is_curr else (255, 255, 255, 255)
        draw.text(
            (xc + 3, y0 + 6),
            tok,
            font=font,
            fill=(0, 0, 0, 210),
            stroke_width=10,
            stroke_fill=(0, 0, 0, 210),
        )
        draw.text(
            (xc, y0),
            tok,
            font=font,
            fill=col,
            stroke_width=7,
            stroke_fill=(8, 10, 16, 255),
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

    # Sincronização 1-para-1 ESTRITAMENTE PARA FRENTE (V7 — ZERO EFEITO REVERSO / ZERO PING-PONG!):
    # - O bloco usa seu clipe principal sincronizado (`sem_vids[0]`) rodando 100% PARA FRENTE.
    # - Se o clipe principal for mais curto que a duração da narração do bloco, fazemos cross-dissolve
    #   limpo PARA FRENTE para uma 2ª cena relacionada (`sem_vids[1]`) e, se necessário, uma 3ª (`sem_vids[2]`).
    # - NUNCA reverte nem repete o mesmo clipe de trás para frente!
    sem_vids = [v for v in (blk.get("video_clips") or []) if v and os.path.exists(v)]
    sync_lock = bool(blk.get("sync_lock")) or (len(sem_vids) >= 1)
    if not sem_vids and fallback_clips:
        sem_vids = [fallback_clips[job["global_idx"] % len(fallback_clips)]]
        sync_lock = True

    frames_v0 = _load_video_frames(sem_vids[0], max_frames=max(total_frames + 24, 520))
    if sync_lock:
        frames_v1 = frames_v0
        frames_v2 = frames_v0
    else:
        backup_pool = [c for c in (fallback_clips or []) if c and os.path.exists(c) and c not in sem_vids]
        while len(sem_vids) < 3 and backup_pool:
            pick = backup_pool[(job["global_idx"] + len(sem_vids)) % len(backup_pool)]
            sem_vids.append(pick)
            backup_pool = [c for c in backup_pool if c != pick]
        frames_v1 = _load_video_frames(sem_vids[1], max_frames=max(total_frames + 24, 420)) if len(sem_vids) > 1 else frames_v0
        frames_v2 = _load_video_frames(sem_vids[2], max_frames=max(total_frames + 24, 420)) if len(sem_vids) > 2 else frames_v1

    remotion_frames = []
    if is_remotion_scene and job.get("remotion_mp4") and os.path.exists(job["remotion_mp4"]):
        remotion_frames = _load_video_frames(job["remotion_mp4"], max_frames=180)

    if remotion_frames:
        # Sub-cena 1: Remotion (até o fim real do Remotion ou 42% do bloco) -> depois gameplay v0 -> v1 (sempre PARA FRENTE!)
        f1_end = min(len(remotion_frames), int(total_frames * 0.42))
        rem_after_rem = total_frames - f1_end
        if len(frames_v0) >= rem_after_rem:
            # v1 recebe frames_v0 (gameplay principal do bloco) e cobre até o fim para frente
            frames_v2 = frames_v1
            frames_v1 = frames_v0
            f2_end = total_frames
        else:
            # Remotion -> frames_v0 (inteiro para frente) -> frames_v1 (continuação para frente)
            frames_v2 = frames_v1
            frames_v1 = frames_v0
            f2_end = min(total_frames, f1_end + max(24, len(frames_v1) - 2))
    elif sync_lock:
        # TRAVA V8 ABSOLUTA (1 BLOCO = 1 ÚNICO CLIPE SINCRONIZADO DO INÍCIO AO FIM DA FALA — ZERO CORTE PARA CENA DESCONEXA!):
        # - A narração do bloco foi escrita especificamente para `sem_vids[0]` (que tem 18-24s de duração).
        # - Portanto, exibimos EXCLUSIVAMENTE `frames_v0` (100% para frente) durante todo o bloco!
        # - NUNCA corta no meio da frase para um 2º clipe de outro assunto e NUNCA repete clipes de outros blocos!
        f1_end = total_frames
        f2_end = total_frames
    else:
        f1_end = min(len(frames_v0) - 2 if len(frames_v0) > 26 else total_frames, int(total_frames * 0.34))
        f2_end = min(f1_end + max(24, len(frames_v1) - 2), int(total_frames * 0.67))
    trans_len = 10

    headline = blk.get("headline") or blk.get("callout") or "DOSSIE GTA VI"
    subheadline = blk.get("subheadline") or blk.get("asset_subject") or "Gameplay e analise verificada"
    callout = blk.get("callout") or "GTA 6"

    silent_mp4 = os.path.join(work_dir, f"vis_{bid}.mp4")
    proc = subprocess.Popen(
        [
            FFMPEG_EXE, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1920x1080", "-r", str(fps), "-i", "pipe:0",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "19", "-pix_fmt", "yuv420p",
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

    # Extrai o ÁUDIO ORIGINAL da cena pesquisada (se o clipe tiver áudio) para manter o som real do jogo/live!
    orig_aud_wav = os.path.join(work_dir, f"orig_aud_{bid}.wav")
    has_orig_audio = False
    for cand_v in sem_vids:
        if cand_v and os.path.exists(cand_v):
            r_ext = subprocess.run(
                [
                    FFMPEG_EXE, "-y", "-i", cand_v, "-t", f"{dur:.2f}",
                    "-vn", "-ar", "48000", "-ac", "2", orig_aud_wav,
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if r_ext.returncode == 0 and os.path.exists(orig_aud_wav) and os.path.getsize(orig_aud_wav) > 12_000:
                has_orig_audio = True
                break

    # Sound Design Contextual + Áudio Original da Cena (ducked durante a narração, destacado no momento do acontecimento!)
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
    vo_dur = get_media_duration(job["wav_p"])

    if has_orig_audio:
        # Mantém o áudio original do clipe baixo (0.28) enquanto o narrador fala e sobe para 0.96 no respiro da cena!
        aud_fc = (
            f"[1:a]volume=1.24[vo];"
            f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out_st:.2f}:d=0.30,volume=0.14[bm];"
            f"[3:a]volume=0.28[sx1];"
            f"[4:a]adelay={mid_whoosh_ms}|{mid_whoosh_ms},volume=0.22[sx2];"
            f"[5:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.15,afade=t=out:st={fade_out_st:.2f}:d=0.25,"
            f"volume='if(gte(t,{max(0.5, vo_dur - 0.15):.2f}),0.96,0.30)':eval=frame[orig];"
            f"[vo][bm][sx1][sx2][orig]amix=inputs=5:duration=longest:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
        )
        ff_cmd = [
            FFMPEG_EXE, "-y",
            "-i", silent_mp4,
            "-i", job["wav_p"],
            "-stream_loop", "-1", "-ss", f"{job['bgm_ss']:.2f}", "-i", job["bgm_file"],
            "-i", sfx_file,
            "-i", sfx_pack["whoosh"],
            "-stream_loop", "-1", "-i", orig_aud_wav,
            "-filter_complex", aud_fc,
            "-map", "0:v", "-map", "[aout]", "-t", f"{dur:.2f}",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-video_track_timescale", "24000", job["seg_out"],
        ]
    else:
        aud_fc = (
            f"[1:a]volume=1.24[vo];"
            f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.20,afade=t=out:st={fade_out_st:.2f}:d=0.30,volume=0.20[bm];"
            f"[3:a]volume=0.30[sx1];"
            f"[4:a]adelay={mid_whoosh_ms}|{mid_whoosh_ms},volume=0.24[sx2];"
            f"[vo][bm][sx1][sx2]amix=inputs=4:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
        )
        ff_cmd = [
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
        ]

    subprocess.run(ff_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return bid


def build_editorial_thumbnail(jpg_path, headline, subheadline, out_jpg):
    """
    Motor de Thumbnail Cinema 3D V5 (Foco 100% NO JOGO — Visual Humanizado, ZERO Streamer PiP, ZERO Selos 'AO VIVO'):
    - Extrai frame real de alto impacto diretamente da gameplay pesquisada (se receber .mp4 ou .jpg).
    - Tipografia 3D extrudada metálica (Ouro + Branco em fonte Anton Display) extraída da descoberta do vídeo.
    """
    import base64
    import json
    import random

    def _to_b64_data_uri(img_or_path):
        if isinstance(img_or_path, str) and os.path.exists(img_or_path):
            if img_or_path.lower().endswith((".mp4", ".mkv", ".mov")):
                cap = cv2.VideoCapture(img_or_path)
                n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 1)
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(n * 0.45))
                ok, fr = cap.read()
                cap.release()
                if ok and fr is not None:
                    ok2, buf = cv2.imencode(".jpg", fr, [int(cv2.IMWRITE_JPEG_QUALITY), 93])
                    if ok2:
                        return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
            else:
                raw = open(img_or_path, "rb").read()
                return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")
        if isinstance(img_or_path, np.ndarray):
            ok, buf = cv2.imencode(".jpg", img_or_path, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            if ok:
                return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")
        return ""

    hero_uri = _to_b64_data_uri(jpg_path) if jpg_path else ""
    if not hero_uri:
        vault_picks = [
            os.path.join(BASE_DIR, "temp_gta6", "vault", fn)
            for fn in ("img_17.jpg", "img_08.jpg", "img_26.jpg", "img_13.jpg", "img_07.jpg", "img_21.jpg")
            if os.path.exists(os.path.join(BASE_DIR, "temp_gta6", "vault", fn))
        ]
        if vault_picks:
            hero_uri = _to_b64_data_uri(random.choice(vault_picks))

    clean_h = (_clean_ascii(headline) or "BUGS ABSURDOS NO GTA 6!").upper()
    words = clean_h.split()
    if len(words) <= 2:
        line1 = "GTA 6"
        line2 = clean_h
    else:
        mid = max(1, len(words) // 2)
        line1 = " ".join(words[:mid])
        line2 = " ".join(words[mid:])

    clean_sub = (_clean_ascii(subheadline) or "").upper()[:48]

    props = {
        "heroImageUrl": hero_uri,
        "line1": line1,
        "line2": line2,
        "subline": clean_sub,
        "accentColor": "#FFBE0B",
    }

    try:
        bundle_dir = AgenteEditorAudiovisual.ensure_remotion_bundle()
        props_file = out_jpg + ".thumb3d.json"
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props, f, ensure_ascii=False)
        out_png = out_jpg + ".png"
        npx_bin = "npx.cmd" if os.name == "nt" else "npx"
        cmd = [
            npx_bin, "remotion", "still", bundle_dir, "GtaThumbnail3D", out_png,
            "--frame=0", f"--props={props_file}",
        ]
        r = subprocess.run(cmd, cwd=AgenteEditorAudiovisual.STUDIO_DIR, capture_output=True, text=True, timeout=60)
        try:
            os.remove(props_file)
        except OSError:
            pass
        if r.returncode == 0 and os.path.exists(out_png):
            Image.open(out_png).convert("RGB").save(out_jpg, quality=95)
            try:
                os.remove(out_png)
            except OSError:
                pass
            print(f"[THUMB 3D V5] Renderizada via Remotion Chromium (100% Foco no Jogo): {out_jpg}", flush=True)
            return out_jpg
        print(f"[THUMB 3D V5] Aviso Remotion ({r.returncode}): {r.stderr[-220:]}", flush=True)
    except Exception as e_th:
        print(f"[THUMB 3D V5] Fallback ({e_th})", flush=True)

    if jpg_path and os.path.exists(jpg_path) and not jpg_path.lower().endswith(".mp4"):
        Image.open(jpg_path).convert("RGB").resize((1280, 720), Image.Resampling.LANCZOS).save(out_jpg, quality=94)
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

        # RETENÇÃO ELITE V9.3:
        # ZERO cartelas borradas estáticas de capítulo (nem no Ato 1 nem nos Atos 2-5):
        # 100% gameplay real contínuo de ponta a ponta (evita queda de retenção e reprovação por tela estática no Agente 5!).
        bgm_offset = 0.0

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
    with ThreadPoolExecutor(max_workers=4) as pool:
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

    hero_jpg = script_data.get("thumb_hero_path")
    if not (hero_jpg and os.path.exists(hero_jpg)):
        from producao.catalog import IMAGE_SEMANTIC_MAP, VAULT_DIR, _score_text_against_tags  # noqa: WPS433

        thumb_query = (
            f"{script_data.get('long_title', '')} {script_data.get('thumb_text', '')} "
            f"{script_data.get('thumb_subtext', '')}"
        ).lower()
        scored_imgs = []
        for fn, meta in IMAGE_SEMANTIC_MAP.items():
            fp = os.path.join(VAULT_DIR, fn)
            if os.path.exists(fp):
                sc = _score_text_against_tags(thumb_query, meta["tags"])
                scored_imgs.append((sc, fp, meta["subject"]))
        scored_imgs.sort(key=lambda x: x[0], reverse=True)
        if scored_imgs and scored_imgs[0][0] > 0:
            hero_jpg = scored_imgs[0][1]
            print(f"[THUMB SEMÂNTICA V5.5] Selecionada por relevância ({scored_imgs[0][0]} pts): {os.path.basename(hero_jpg)} ({scored_imgs[0][2]})", flush=True)
        else:
            hero_jpg = (block_jobs[0]["blk"].get("primary_img") if block_jobs else None) or (
                scored_imgs[0][1] if scored_imgs else None
            )
    build_editorial_thumbnail(
        hero_jpg,
        script_data.get("thumb_text", "SEGREDOS ABSURDOS NO GTA 6!"),
        script_data.get("thumb_subtext", ""),
        output_thumb_jpg,
    )
    real_dur = get_media_duration(output_mp4)
    return output_mp4, output_thumb_jpg, chapters_ts, music_credits, real_dur
