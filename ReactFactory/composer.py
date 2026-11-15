import os
import subprocess
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_media_duration(path):
    cmd = [FFMPEG_EXE, "-i", path]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in proc.stderr.splitlines():
        if "Duration:" in line:
            t_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t_str.split(":")
            return int(h) * 3600 + int(m) * 60 + float(s)
    return 4.0


def load_font(size):
    for font_candidate in [
        "C:/Windows/Fonts/impact.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]:
        if os.path.exists(font_candidate):
            try:
                return ImageFont.truetype(font_candidate, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_caption_chunk(frame_bgr, text, highlight_idx=-1):
    """
    Desenha legendas GIGANTES (estilo Hormozi/CapCut Pro, tamanho 88px),
    com até 3 palavras por linha, contorno preto super grosso (7px) e destaque amarelo neon.
    """
    if not text:
        return frame_bgr

    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = load_font(88)

    words = text.upper().split()
    if not words:
        return frame_bgr

    # Quebra em no máximo 2 linhas de 2 a 3 palavras para ficar GIGANTE na tela
    lines = []
    curr = []
    w_idx = 0
    for w in words:
        curr.append((w, w_idx == highlight_idx))
        w_idx += 1
        if len(curr) >= 3:
            lines.append(curr)
            curr = []
    if curr:
        lines.append(curr)

    y_base = 985 if len(lines) > 1 else 1045
    for line in lines[:2]:
        full_line_str = " ".join(w for w, _ in line)
        bbox = draw.textbbox((0, 0), full_line_str, font=font)
        line_w = bbox[2] - bbox[0]
        x_cursor = (1080 - line_w) // 2

        for word_str, is_active in line:
            color = (255, 235, 0) if is_active else (255, 255, 255)
            # Sombra projetada + Contorno preto grosso
            draw.text(
                (x_cursor, y_base),
                word_str,
                font=font,
                fill=color,
                stroke_width=8,
                stroke_fill=(0, 0, 0),
            )
            wb = draw.textbbox((0, 0), word_str + " ", font=font)
            x_cursor += (wb[2] - wb[0])
        y_base += 98

    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def draw_top_headline(frame_bgr, headline_text):
    if not headline_text:
        return frame_bgr
    img_pil = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img_pil)
    font = load_font(54)

    clean_text = headline_text.upper().strip()
    # Mantém acentos em português, remove apenas emojis que a fonte Impact não renderiza
    clean_text = "".join(c for c in clean_text if ord(c) < 65000).strip() or "ESPERA ATÉ O FINAL!"
    bbox = draw.textbbox((0, 0), clean_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x, pad_y = 38, 20
    x1 = max(30, (1080 - tw) // 2 - pad_x)
    y1 = 64
    x2 = min(1050, (1080 + tw) // 2 + pad_x)
    y2 = y1 + th + pad_y * 2

    draw.rounded_rectangle([x1, y1, x2, y2], radius=24, fill=(12, 12, 18), outline=(255, 225, 0), width=5)
    draw.text(
        ((1080 - tw) // 2, y1 + pad_y - 6),
        clean_text,
        font=font,
        fill=(255, 255, 255),
        stroke_width=3,
        stroke_fill=(0, 0, 0),
    )
    return cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)


def crop_resize(frame, target_w, target_h, zoom=1.0):
    h, w = frame.shape[:2]
    target_ratio = target_w / float(target_h)
    src_ratio = w / float(h)

    if src_ratio > target_ratio:
        new_w = int(h * target_ratio)
        x0 = (w - new_w) // 2
        cropped = frame[:, x0:x0 + new_w]
    else:
        new_h = int(w / target_ratio)
        y0 = (h - new_h) // 2
        cropped = frame[y0:y0 + new_h, :]

    if zoom > 1.001:
        ch, cw = cropped.shape[:2]
        zw, zh = int(cw / zoom), int(ch / zoom)
        zx0, zy0 = (cw - zw) // 2, (ch - zh) // 2
        cropped = cropped[zy0:zy0 + zh, zx0:zx0 + zw]

    return cv2.resize(cropped, (target_w, target_h), interpolation=cv2.INTER_LINEAR)


class VideoClipReader:
    def __init__(self, path):
        self.path = path
        self.cap = cv2.VideoCapture(path)
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.frames = []
        while True:
            ret, f = self.cap.read()
            if not ret:
                break
            self.frames.append(f)
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
        return self.frames[idx]


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
    fps = 25
    top_h = 1230
    bot_h = 1920 - top_h  # 690

    hook_dur = get_media_duration(hook_audio_wav)
    inter_dur = get_media_duration(interrupt_audio_wav)
    outro_dur = get_media_duration(outro_audio_wav)
    viral_dur = get_media_duration(viral_video_path)

    max_viral_use = min(viral_dur, 26.0)
    inter_sec = float(script_data.get("interrupt_sec", max_viral_use * 0.55))
    inter_sec = min(max(4.5, inter_sec), max(5.0, max_viral_use - 3.5))

    part1_dur = inter_sec
    part2_dur = max(3.5, max_viral_use - inter_sec)

    t_hook_end = hook_dur
    t_part1_end = t_hook_end + part1_dur
    t_inter_end = t_part1_end + inter_dur
    t_total = t_inter_end + part2_dur

    print(f"[COMPOSER] Linha do tempo: Hook={hook_dur:.1f}s | Parte1={part1_dur:.1f}s | Interrupção={inter_dur:.1f}s | Clímax={part2_dur:.1f}s | Total={t_total:.1f}s")

    viral_reader = VideoClipReader(viral_video_path)
    hook_reader = VideoClipReader(hook_avatar_mp4)
    inter_reader = VideoClipReader(interrupt_avatar_mp4)
    outro_reader = VideoClipReader(outro_avatar_mp4)
    idle_reader = VideoClipReader(idle_avatar_mp4)
    idle_reader_2 = VideoClipReader(idle_avatar_mp4_2) if idle_avatar_mp4_2 else idle_reader

    headline = script_data.get("headline_top", "ESPERA SÓ ATÉ O FINAL!")
    hook_words = script_data.get("hook_text", "").split()
    inter_words = script_data.get("interrupt_text", "").split()
    outro_words = script_data.get("outro_text", "").split()

    # Chunks de 4 palavras para caber perfeitamente em 2 linhas gigantes!
    def get_active_chunk(words_list, progress_0_1):
        if not words_list:
            return "", -1
        total_w = len(words_list)
        curr_w = min(total_w - 1, max(0, int(progress_0_1 * total_w)))
        chunk_start = (curr_w // 4) * 4
        chunk = words_list[chunk_start:chunk_start + 4]
        return " ".join(chunk), (curr_w - chunk_start)

    silent_video = os.path.join(TEMP_DIR, "composed_video_only.mp4")
    writer = cv2.VideoWriter(silent_video, cv2.VideoWriter_fourcc(*"mp4v"), fps, (1080, 1920))

    total_frames = int(t_total * fps)
    for f_idx in range(total_frames):
        t = f_idx / float(fps)
        canvas = np.zeros((1920, 1080, 3), dtype=np.uint8)

        caption_str = ""
        active_word_idx = -1
        is_speaking = False

        if t < t_hook_end:
            prog = t / max(0.1, hook_dur)
            v_frame = viral_reader.get_frame_at(inter_sec, loop=False)
            top_img = crop_resize(v_frame, 1080, top_h, zoom=1.04 + 0.08 * prog)
            av_frame = hook_reader.get_frame_at(t, loop=False)
            bot_img = crop_resize(av_frame, 1080, bot_h, zoom=1.02)
            caption_str, active_word_idx = get_active_chunk(hook_words, prog)
            is_speaking = True

        elif t < t_part1_end:
            v_t = t - t_hook_end
            v_frame = viral_reader.get_frame_at(v_t, loop=False)
            top_img = crop_resize(v_frame, 1080, top_h, zoom=1.03)
            av_frame = idle_reader.get_frame_at(v_t, loop=True, pingpong=True)
            bot_img = crop_resize(av_frame, 1080, bot_h, zoom=1.0)

        elif t < t_inter_end:
            inter_t = t - t_part1_end
            prog = inter_t / max(0.1, inter_dur)
            v_frame = viral_reader.get_frame_at(inter_sec, loop=False)
            top_img = crop_resize(v_frame, 1080, top_h, zoom=1.08 + 0.06 * prog)
            gray = cv2.cvtColor(top_img, cv2.COLOR_BGR2GRAY)
            gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            top_img = cv2.addWeighted(top_img, 0.45, gray_bgr, 0.55, -15)

            av_frame = inter_reader.get_frame_at(inter_t, loop=False)
            bot_img = crop_resize(av_frame, 1080, bot_h, zoom=1.04)
            caption_str, active_word_idx = get_active_chunk(inter_words, prog)
            is_speaking = True

        else:
            part2_t = t - t_inter_end
            v_t = inter_sec + part2_t
            v_frame = viral_reader.get_frame_at(v_t, loop=False)
            top_img = crop_resize(v_frame, 1080, top_h, zoom=1.03)

            time_left = t_total - t
            if time_left <= outro_dur:
                outro_t = outro_dur - time_left
                prog = outro_t / max(0.1, outro_dur)
                av_frame = outro_reader.get_frame_at(outro_t, loop=False)
                bot_img = crop_resize(av_frame, 1080, bot_h, zoom=1.03)
                caption_str, active_word_idx = get_active_chunk(outro_words, prog)
                is_speaking = True
            else:
                av_frame = idle_reader_2.get_frame_at(part2_t, loop=True, pingpong=True)
                bot_img = crop_resize(av_frame, 1080, bot_h, zoom=1.0)

        canvas[0:top_h, :] = top_img
        canvas[top_h:1920, :] = bot_img

        bar_color = (0, 230, 255) if is_speaking else (255, 190, 0)
        cv2.rectangle(canvas, (0, top_h - 6), (1080, top_h + 6), bar_color, -1)

        canvas = draw_top_headline(canvas, headline)

        if caption_str:
            canvas = draw_caption_chunk(canvas, caption_str, active_word_idx)

        writer.write(canvas)

    writer.release()

    v_aud_p1 = os.path.join(TEMP_DIR, "v_aud_p1.wav")
    v_aud_p2 = os.path.join(TEMP_DIR, "v_aud_p2.wav")
    subprocess.run([
        FFMPEG_EXE, "-y", "-ss", "0", "-t", f"{part1_dur:.2f}", "-i", viral_video_path,
        "-vn", "-af", "volume=0.85", "-ar", "24000", "-ac", "1", v_aud_p1
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        FFMPEG_EXE, "-y", "-ss", f"{inter_sec:.2f}", "-t", f"{part2_dur:.2f}", "-i", viral_video_path,
        "-vn", "-af", "volume=0.80", "-ar", "24000", "-ac", "1", v_aud_p2
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    ms_part1 = int(t_hook_end * 1000)
    ms_inter = int(t_part1_end * 1000)
    ms_part2 = int(t_inter_end * 1000)
    ms_outro = max(ms_part2, int((t_total - outro_dur) * 1000))

    filter_complex = (
        f"[0:a]volume=1.45[a_hook];"
        f"[1:a]adelay={ms_part1}|{ms_part1},volume=0.75[a_vp1];"
        f"[2:a]adelay={ms_inter}|{ms_inter},volume=1.45[a_inter];"
        f"[3:a]adelay={ms_part2}|{ms_part2},volume=0.55[a_vp2];"
        f"[4:a]adelay={ms_outro}|{ms_outro},volume=1.5[a_outro];"
        f"[5:a]volume=0.65[a_whoosh];"
        f"[6:a]adelay={ms_inter}|{ms_inter},volume=0.75[a_freeze];"
        f"[a_hook][a_vp1][a_inter][a_vp2][a_outro][a_whoosh][a_freeze]amix=inputs=7:duration=longest:dropout_transition=0,volume=2.2[a_final]"
    )

    mixed_audio = os.path.join(TEMP_DIR, "mixed_master.wav")
    subprocess.run([
        FFMPEG_EXE, "-y",
        "-i", hook_audio_wav,
        "-i", v_aud_p1,
        "-i", interrupt_audio_wav,
        "-i", v_aud_p2,
        "-i", outro_audio_wav,
        "-i", sfx_whoosh_path,
        "-i", sfx_freeze_path,
        "-filter_complex", filter_complex,
        "-map", "[a_final]",
        "-t", f"{t_total:.2f}",
        mixed_audio
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        FFMPEG_EXE, "-y",
        "-i", silent_video,
        "-i", mixed_audio,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_final_mp4
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"[COMPOSER] Vídeo Final V2 Renderizado com Sucesso: {output_final_mp4}")
    return output_final_mp4
