import math
import os
import subprocess
import cv2
import imageio_ffmpeg
import numpy as np
from PIL import Image, ImageDraw

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

_FONT_CACHE = {}

_POWER_WORDS = {
    "GTA", "6", "VI", "DAVY", "JONES", "BISTECONE", "SANINPLAY", "LIVE", "CHOQUE",
    "SEGREDO", "ABSURDO", "INSANO", "REAL", "VICE", "CITY", "LUCIA", "JASON",
    "POLICIA", "POLÍCIA", "CELULAR", "MISSAO", "MISSÃO", "GRAFICOS", "GRÁFICOS",
    "FISICA", "FÍSICA", "TRAVOU", "NUNCA", "OLHA", "ISSO",
}


def load_font(size, style="poppins"):
    key = (size, style)
    if key in _FONT_CACHE:
        return _FONT_CACHE[key]
    from PIL import ImageFont

    fonts_dir = os.path.join(ASSETS_DIR, "fonts")
    if style == "anton":
        preferred = [
            os.path.join(fonts_dir, "Anton-Regular.ttf"),
            os.path.join(fonts_dir, "BebasNeue-Regular.ttf"),
            os.path.join(fonts_dir, "Poppins-Black.ttf"),
        ]
    elif style == "bebas":
        preferred = [
            os.path.join(fonts_dir, "BebasNeue-Regular.ttf"),
            os.path.join(fonts_dir, "Anton-Regular.ttf"),
            os.path.join(fonts_dir, "Poppins-Black.ttf"),
        ]
    else:
        preferred = [
            os.path.join(fonts_dir, "Poppins-Black.ttf"),
            os.path.join(fonts_dir, "Poppins-ExtraBold.ttf"),
            os.path.join(fonts_dir, "Anton-Regular.ttf"),
        ]

    candidates = preferred + [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                f = ImageFont.truetype(p, size)
                _FONT_CACHE[key] = f
                return f
            except Exception:
                pass
    f = ImageFont.load_default()
    _FONT_CACHE[key] = f
    return f


def get_media_duration(path):
    if not path or not os.path.exists(path):
        return 0.0
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps and fps > 0 and frames and frames > 0:
        return float(frames) / float(fps)
    import wave

    try:
        with wave.open(path, "rb") as wf:
            return wf.getnframes() / float(wf.getframerate())
    except Exception:
        return 5.0


def _clean_text(t):
    return "".join(c for c in (t or "") if ord(c) < 65000).strip()


def draw_caption_chunk(frame_bgr, text, highlight_idx=0, y_center=1415):
    """
    Legenda Viral Profissional V4 (Poppins-Black ExtraBold — Estilo Referência hz4KLLc4Q6Q + CapCut Pro):
    - ZERO caixa preta ou retângulo neon atrás do texto.
    - 1 a 2 palavras gigantes por vez (fonte Poppins-Black 86px) com contorno suave + sombra projetada profunda.
    - Destaque dinâmico em Ouro Elétrico (#FFE01B) na palavra ativa e Ciano (#00F5FF) em gatilhos.
    """
    words = _clean_text(text).upper().split()
    if not words:
        return frame_bgr

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")
    font = load_font(86 if len(" ".join(words)) <= 13 else 74, style="poppins")

    lines = []
    curr = []
    for idx, w in enumerate(words[:3]):
        curr.append((w, idx == highlight_idx))
        if len(curr) >= 2:
            lines.append(curr)
            curr = []
    if curr:
        lines.append(curr)

    y_cursor = y_center if len(lines) == 1 else (y_center - 48)

    for line in lines[:2]:
        full_line_str = " ".join(w for w, _ in line)
        bbox = draw.textbbox((0, 0), full_line_str, font=font)
        line_w = bbox[2] - bbox[0]
        x_cursor = (1080 - line_w) // 2

        for word_str, is_active in line:
            clean_tok = word_str.strip(".,!?\"'")
            if is_active:
                color = (0, 245, 255, 255) if clean_tok in _POWER_WORDS else (255, 224, 27, 255)
            else:
                color = (255, 224, 27, 255) if clean_tok in _POWER_WORDS else (255, 255, 255, 255)

            # Sombra projetada suave em 2 camadas para efeito cinema 3D
            draw.text(
                (x_cursor + 3, y_cursor + 9),
                word_str,
                font=font,
                fill=(0, 0, 0, 195),
                stroke_width=11,
                stroke_fill=(0, 0, 0, 195),
            )
            draw.text(
                (x_cursor, y_cursor),
                word_str,
                font=font,
                fill=color,
                stroke_width=8,
                stroke_fill=(8, 10, 16, 255),
            )
            w_bbox = draw.textbbox((0, 0), word_str + " ", font=font)
            x_cursor += w_bbox[2] - w_bbox[0]

        y_cursor += 96

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_top_headline(frame_bgr, headline_text, progress_0_1=0.0, source_badge=None):
    """
    Gancho Superior Limpo V5 para Shorts (Fonte Anton Display — SEM tarja 'AO VIVO CORTES GTA'):
    - Visual 100% humanizado: apenas o título/gancho forte em Anton no topo, sem selos ou badges artificiais.
    """
    clean_h = _clean_text(headline_text).upper()
    if not clean_h:
        return frame_bgr

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil, "RGBA")

    words = clean_h.split()
    if len(words) <= 4 and len(clean_h) <= 22:
        lines = [clean_h]
    else:
        best_mid = max(1, len(words) // 2)
        best_diff = 999
        for m in range(1, len(words)):
            diff = abs(len(" ".join(words[:m])) - len(" ".join(words[m:])))
            if diff < best_diff:
                best_diff = diff
                best_mid = m
        lines = [" ".join(words[:best_mid]), " ".join(words[best_mid:])]

    max_line_chars = max(len(ln) for ln in lines)
    f_size = 74 if max_line_chars <= 22 else (64 if max_line_chars <= 28 else 54)
    f_head = load_font(f_size, style="anton")
    yy = 215 if len(lines) == 1 else 188
    for idx_l, ln in enumerate(lines):
        lb = draw.textbbox((0, 0), ln, font=f_head)
        lw = lb[2] - lb[0]
        lx = (1080 - lw) // 2
        col = (255, 224, 27, 255) if idx_l == len(lines) - 1 else (255, 255, 255, 255)
        draw.text((lx + 3, yy + 7), ln, font=f_head, fill=(0, 0, 0, 215), stroke_width=9, stroke_fill=(0, 0, 0, 215))
        draw.text((lx, yy), ln, font=f_head, fill=col, stroke_width=6, stroke_fill=(8, 10, 16, 255))
        yy += int(f_size * 1.14)

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def fit_widescreen_cinematic(frame, target_w=1080, target_h=1920, zoom=1.0, pan_x=0.0):
    """
    Enquadramento Vertical V5 para Shorts (ZERO CORTE LATERAL — 100% da imagem 16:9 visível!):
    - Preserva a proporção original do vídeo 16:9 (1080x608 sem cortar absolutamente nada nas laterais!)
      centralizado confortavelmente em y=490..1098 sobre fundo ambiente desfocado e colorido do próprio jogo.
    - Se o vídeo fonte já for vertical (9:16), preenche 1080x1920 nativamente.
    """
    h, w = frame.shape[:2]
    if w <= h * 1.05:
        return crop_resize(frame, target_w, target_h, zoom=1.0, pan_x=0.0)

    # 1. Fundo ambiente desfocado com atmosfera do jogo
    bg_small = cv2.resize(frame, (180, 320), interpolation=cv2.INTER_AREA)
    bg_blur = cv2.GaussianBlur(bg_small, (35, 35), 0)
    bg = cv2.resize(bg_blur, (target_w, target_h), interpolation=cv2.INTER_LINEAR).astype(np.float32) * 0.38
    v_grad = np.ones((target_h, 1, 1), dtype=np.float32)
    v_grad[:420] = np.linspace(0.28, 0.85, 420, dtype=np.float32)[:, None, None]
    v_grad[target_h - 520 :] = np.linspace(0.85, 0.25, 520, dtype=np.float32)[:, None, None]
    bg = np.clip(bg * v_grad, 0, 255).astype(np.uint8)

    # 2. Encaixe exato sem cortes: mantém 100% da largura original (16:9 -> 1080x608)
    exact_h = max(480, min(int(round(target_w * (h / float(w)))), 760))
    fg = cv2.resize(frame, (target_w, exact_h), interpolation=cv2.INTER_AREA)
    fg_f = np.clip((fg.astype(np.float32) - 124.0) * 1.04 + 124.0, 0, 255)

    y0 = (target_h - exact_h) // 2 - 110 if target_h >= 1600 else (target_h - exact_h) // 2
    y0 = max(360, min(y0, target_h - exact_h - 320)) if target_h >= 1600 else max(0, y0)

    # Fusão suave de 14px apenas na borda superior/inferior para visual limpo e sem cortes
    alpha = np.ones((exact_h, 1, 1), dtype=np.float32)
    feather = 14
    alpha[:feather] = np.linspace(0.0, 1.0, feather, dtype=np.float32)[:, None, None]
    alpha[-feather:] = np.linspace(1.0, 0.0, feather, dtype=np.float32)[:, None, None]

    roi = bg[y0 : y0 + exact_h, :].astype(np.float32)
    bg[y0 : y0 + exact_h, :] = np.clip(fg_f * alpha + roi * (1.0 - alpha), 0, 255).astype(np.uint8)
    return bg


def crop_resize(frame, target_w, target_h, zoom=1.0, pan_x=0.0, pan_y=0.0):
    h, w = frame.shape[:2]
    target_ratio = target_w / float(target_h)
    src_ratio = w / float(h)

    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        cropped = frame[:, x0 : x0 + new_w]
    else:
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        cropped = frame[y0 : y0 + new_h, :]

    if zoom > 1.001:
        ch, cw = cropped.shape[:2]
        zw, zh = int(cw / zoom), int(ch / zoom)
        max_dx = max(0, cw - zw)
        max_dy = max(0, ch - zh)
        zx0 = max(0, min(max_dx, int((cw - zw) * (0.5 + 0.5 * pan_x))))
        zy0 = max(0, min(max_dy, int((ch - zh) * (0.5 + 0.5 * pan_y))))
        cropped = cropped[zy0 : zy0 + zh, zx0 : zx0 + zw]

    return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)


def build_short_thumbnail(viral_video_path, headline_text, reaction_video_path=None, out_jpg="output_short_thumb.jpg"):
    """Gera capa 1080x1920 de alto CTR para o Short (100% focada na cena do jogo/live, sem avatar)."""
    c1 = cv2.VideoCapture(viral_video_path)
    n1 = max(1, int(c1.get(cv2.CAP_PROP_FRAME_COUNT)))
    c1.set(cv2.CAP_PROP_POS_FRAMES, int(n1 * 0.42))
    ok1, f_top = c1.read()
    c1.release()
    if not ok1 or f_top is None:
        f_top = np.zeros((1080, 1920, 3), dtype=np.uint8)

    canvas = fit_widescreen_cinematic(f_top, 1080, 1920, zoom=1.02)
    canvas = draw_top_headline(canvas, headline_text, progress_0_1=0.0)
    canvas = draw_caption_chunk(canvas, "OLHA ISSO!", highlight_idx=0, y_center=1340)

    img_pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    img_pil.save(out_jpg, quality=95)
    return out_jpg


class VideoClipReader:
    def __init__(self, path, max_dim=1440, max_frames=None, compress=True):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.compress = compress
        self.frames = []
        self._last_idx = -1
        self._last_frame = None
        while True:
            ret, f = self.cap.read()
            if not ret:
                break
            if max_dim:
                fh, fw = f.shape[:2]
                biggest = max(fh, fw)
                if biggest > max_dim:
                    scale = max_dim / float(biggest)
                    f = cv2.resize(f, (max(2, int(fw * scale)), max(2, int(fh * scale))), interpolation=cv2.INTER_AREA)
            if compress:
                ok, buf = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 92])
                self.frames.append(buf if ok else f)
            else:
                self.frames.append(f)
            if max_frames and len(self.frames) >= max_frames:
                break
        self.cap.release()
        if not self.frames:
            raise RuntimeError(f"Não foi possível ler frames de {path}")

    def get_frame_at(self, t_sec, loop=True, pingpong=False):
        idx = int(t_sec * self.fps)
        n = len(self.frames)
        if pingpong and n > 1:
            cycle = 2 * (n - 1)
            pos = idx % cycle
            idx = pos if pos < n else cycle - pos
        elif loop:
            idx = idx % n
        else:
            idx = min(max(0, idx), n - 1)
        if idx == self._last_idx and self._last_frame is not None:
            return self._last_frame
        item = self.frames[idx]
        if isinstance(item, np.ndarray) and item.ndim == 1:
            frame = cv2.imdecode(item, cv2.IMREAD_COLOR)
        elif self.compress and item.ndim <= 2:
            frame = cv2.imdecode(item, cv2.IMREAD_COLOR)
        else:
            frame = item
        self._last_idx = idx
        self._last_frame = frame
        return frame


def compose_react_short(
    viral_video_path,
    hook_avatar_mp4,
    hook_audio_wav,
    interrupt_avatar_mp4,
    interrupt_audio_wav,
    outro_avatar_mp4,
    outro_audio_wav,
    idle_avatar_mp4,
    script_data,
    sfx_whoosh_path,
    sfx_freeze_path,
    output_final_mp4,
    idle_avatar_mp4_2=None,
):
    """
    Compositor de Shorts Virais V3 (100% Gameplay & Cortes de Lives — SEM AVATAR do usuário):
    - Dedica a tela vertical inteira (1080x1920) aos cortes de GTA 6 (Davy Jones, Bistecone, SanInPlay, Gameplay)
      em proporção Cinema Showcase confortável de assistir (sem ultra-zoom!).
    - Narração profissional padronizada (Gemini 3.8 Flash TTS 'Orus') com legendas gigantes de 2 palavras
      sem caixa de fundo (estilo referência hz4KLLc4Q6Q).
    """
    os.makedirs(TEMP_DIR, exist_ok=True)
    fps = 25

    hook_dur = get_media_duration(hook_audio_wav)
    inter_dur = get_media_duration(interrupt_audio_wav)
    outro_dur = get_media_duration(outro_audio_wav)
    viral_dur = get_media_duration(viral_video_path)

    max_viral_use = min(viral_dur, 24.5)
    inter_sec = float(script_data.get("interrupt_sec", max_viral_use * 0.52))
    inter_sec = min(max(4.5, inter_sec), max(5.0, max_viral_use - 3.2))

    part1_dur = inter_sec
    part2_dur = max(3.5, max_viral_use - inter_sec)

    t_hook_end = hook_dur
    t_part1_end = t_hook_end + part1_dur
    t_inter_end = t_part1_end + inter_dur
    t_total = t_inter_end + part2_dur

    print(
        f"[COMPOSER V3 SHORT] Sem Avatar | Hook={hook_dur:.1f}s | Corte1={part1_dur:.1f}s | "
        f"Analise={inter_dur:.1f}s | Climax={part2_dur:.1f}s | Total={t_total:.1f}s"
    )

    viral_reader = VideoClipReader(viral_video_path, max_dim=1440, compress=True)

    headline = script_data.get("headline_top", "DAVY JONES E BISTECONE NO GTA 6!")
    source_badge = script_data.get("source_badge", "AO VIVO // CORTES GTA 6")
    hook_words = script_data.get("hook_text", "").split()
    inter_words = script_data.get("interrupt_text", "").split()
    outro_words = script_data.get("outro_text", "").split()

    # Chunks curtos de 2 palavras (estilo referência hz4KLLc4Q6Q: leitura instantânea e dinâmica!)
    def get_active_chunk(words_list, progress_0_1):
        if not words_list:
            return "", -1
        total_w = len(words_list)
        curr_w = min(total_w - 1, max(0, int(progress_0_1 * total_w)))
        chunk_start = (curr_w // 2) * 2
        chunk = words_list[chunk_start : chunk_start + 2]
        return " ".join(chunk), (curr_w - chunk_start)

    silent_video = os.path.join(TEMP_DIR, "composed_video_only.mp4")
    writer = cv2.VideoWriter(silent_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))

    total_frames = int(t_total * fps)
    for f_idx in range(total_frames):
        t = f_idx / float(fps)
        caption_str = ""
        active_word_idx = -1

        if t < t_hook_end:
            prog = t / max(0.1, hook_dur)
            teaser_t = min(max_viral_use - 0.1, max(0.0, inter_sec - 1.6) + t * 0.65)
            v_frame = viral_reader.get_frame_at(teaser_t, loop=False)
            canvas = fit_widescreen_cinematic(
                v_frame, 1080, 1920, zoom=1.01 + 0.02 * prog, pan_x=0.06 * math.sin(t * 1.4)
            )
            caption_str, active_word_idx = get_active_chunk(hook_words, prog)

        elif t < t_part1_end:
            v_t = t - t_hook_end
            prog_p1 = v_t / max(0.1, part1_dur)
            v_frame = viral_reader.get_frame_at(v_t, loop=False)
            canvas = fit_widescreen_cinematic(
                v_frame, 1080, 1920, zoom=1.00 + 0.025 * prog_p1, pan_x=0.08 * math.sin(v_t * 0.8)
            )

        elif t < t_inter_end:
            inter_t = t - t_part1_end
            prog = inter_t / max(0.1, inter_dur)
            v_frame = viral_reader.get_frame_at(inter_sec + inter_t * 0.55, loop=True)
            canvas = fit_widescreen_cinematic(v_frame, 1080, 1920, zoom=1.015 + 0.02 * prog)
            caption_str, active_word_idx = get_active_chunk(inter_words, prog)

        else:
            part2_t = t - t_inter_end
            prog_p2 = part2_t / max(0.1, part2_dur)
            v_t = inter_sec + part2_t
            v_frame = viral_reader.get_frame_at(v_t, loop=False)
            canvas = fit_widescreen_cinematic(
                v_frame, 1080, 1920, zoom=1.01 + 0.025 * prog_p2, pan_x=-0.07 * math.sin(part2_t * 0.8)
            )

            time_left = t_total - t
            if time_left <= outro_dur:
                outro_t = outro_dur - time_left
                prog = outro_t / max(0.1, outro_dur)
                caption_str, active_word_idx = get_active_chunk(outro_words, prog)

        canvas = draw_top_headline(canvas, headline, progress_0_1=(t / max(0.1, t_total)))

        if caption_str:
            canvas = draw_caption_chunk(canvas, caption_str, active_word_idx, y_center=1230)

        writer.write(canvas)

    writer.release()
    del viral_reader

    v_aud_p1 = os.path.join(TEMP_DIR, "v_aud_p1.wav")
    v_aud_p2 = os.path.join(TEMP_DIR, "v_aud_p2.wav")
    subprocess.run(
        [
            FFMPEG_EXE, "-y", "-ss", "0", "-t", f"{part1_dur:.2f}", "-i", viral_video_path,
            "-vn", "-af", "volume=1.05", "-ar", "24000", "-ac", "1", v_aud_p1,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        [
            FFMPEG_EXE, "-y", "-ss", f"{inter_sec:.2f}", "-t", f"{part2_dur:.2f}", "-i", viral_video_path,
            "-vn", "-af", "volume=1.05", "-ar", "24000", "-ac", "1", v_aud_p2,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    ms_part1 = int(t_hook_end * 1000)
    ms_inter = int(t_part1_end * 1000)
    ms_part2 = int(t_inter_end * 1000)
    ms_outro = max(ms_part2, int((t_total - outro_dur) * 1000))

    from sfx import ensure_pop_sfx  # noqa: WPS433

    sfx_pop_path = ensure_pop_sfx()
    outro_rel_p2 = max(0.0, (ms_outro - ms_part2) / 1000.0)
    filter_complex = (
        f"[0:a]volume=1.22[a_hook];"
        f"[1:a]adelay={ms_part1}|{ms_part1},volume=0.88[a_vp1];"
        f"[2:a]adelay={ms_inter}|{ms_inter},volume=1.22[a_inter];"
        f"[3:a]volume='if(gte(t,{outro_rel_p2:.2f}),0.22,0.88)':eval=frame,adelay={ms_part2}|{ms_part2}[a_vp2];"
        f"[4:a]adelay={ms_outro}|{ms_outro},volume=1.22[a_outro];"
        f"[5:a]volume=0.30[a_whoosh];"
        f"[6:a]adelay={ms_inter}|{ms_inter},volume=0.34[a_freeze];"
        f"[7:a]adelay={ms_part1}|{ms_part1},volume=0.26[a_pop1];"
        f"[8:a]adelay={ms_outro}|{ms_outro},volume=0.26[a_pop2];"
        f"[a_hook][a_vp1][a_inter][a_vp2][a_outro][a_whoosh][a_freeze][a_pop1][a_pop2]amix=inputs=9:duration=longest:dropout_transition=0:normalize=0,volume=0.96[a_final]"
    )

    mixed_audio = os.path.join(TEMP_DIR, "mixed_master.wav")
    subprocess.run(
        [
            FFMPEG_EXE, "-y",
            "-i", hook_audio_wav,
            "-i", v_aud_p1,
            "-i", interrupt_audio_wav,
            "-i", v_aud_p2,
            "-i", outro_audio_wav,
            "-i", sfx_whoosh_path,
            "-i", sfx_freeze_path,
            "-i", sfx_pop_path,
            "-i", sfx_pop_path,
            "-filter_complex", filter_complex,
            "-map", "[a_final]",
            "-t", f"{t_total:.2f}",
            mixed_audio,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    subprocess.run(
        [
            FFMPEG_EXE, "-y",
            "-i", silent_video,
            "-i", mixed_audio,
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "19",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_final_mp4,
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    print(f"[COMPOSER V3 SHORT] Short Renderizado com Sucesso (Sem Avatar / Proporção Cinema): {output_final_mp4}")
    return output_final_mp4
