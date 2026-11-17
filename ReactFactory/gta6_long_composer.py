import os
import random
import subprocess
import sys
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from composer import ASSETS_DIR, FFMPEG_EXE, get_media_duration, load_font  # noqa: E402
from sfx import ensure_pop_sfx, ensure_sfx  # noqa: E402

BGM_MOOD_MAP = {
    "synth": "bgm_gta_synth.mp3",
    "story": "bgm_gta_story.mp3",
    "tension": "bgm_gta_tension.mp3",
    "urban": "bgm_gta_urban.mp3",
}


def _clean_txt(t):
    return "".join(c for c in (t or "") if ord(c) < 65000).strip()


def _split_sub_chunks(text, total_dur):
    words = (text or "").split()
    if not words:
        return []
    n_chunks = max(2, min(6, (len(words) + 5) // 6))
    per = max(1, (len(words) + n_chunks - 1) // n_chunks)
    chunks = [" ".join(words[i:i + per]) for i in range(0, len(words), per)]
    tot_chars = max(1, sum(len(c) for c in chunks))
    timed = []
    t_cur = 0.0
    for i, c in enumerate(chunks):
        span = total_dur * (len(c) / tot_chars)
        t_end = total_dur if i == len(chunks) - 1 else min(total_dur, t_cur + span)
        timed.append((c, t_cur, t_end))
        t_cur = t_end
    return timed


def _make_doc_subtitle_png(text, highlight_word, out_png):
    """Legenda cinematográfica no terço inferior (alta legibilidade, zero poluição)."""
    img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = load_font(56)

    words = _clean_txt(text).upper().split()
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        if len(" ".join(cur)) >= 36 or len(cur) >= 7:
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    lines = lines[:2]

    hl = _clean_txt(highlight_word).upper().strip()
    y = 920 if len(lines) == 1 else 860
    for line_words in lines:
        full_s = " ".join(line_words)
        bb = draw.textbbox((0, 0), full_s, font=font)
        tw = bb[2] - bb[0]
        th = bb[3] - bb[1]
        x_start = (1920 - tw) // 2
        draw.rounded_rectangle(
            [x_start - 26, y - 10, x_start + tw + 26, y + th + 16],
            radius=14, fill=(8, 10, 18, 205), outline=(255, 70, 180, 175), width=2,
        )
        xc = x_start
        for w in line_words:
            is_hl = hl and (w.strip(".,!?") in hl or hl in w)
            col = (255, 232, 45, 255) if is_hl else (255, 255, 255, 255)
            draw.text((xc, y - 4), w, font=font, fill=col, stroke_width=5, stroke_fill=(0, 0, 0, 255))
            wb = draw.textbbox((0, 0), w + " ", font=font)
            xc += wb[2] - wb[0]
        y += 74

    img.save(out_png)
    return out_png


def _make_chapter_card_jpg(act_num, act_title, bg_img_path, out_jpg):
    """Card cinematográfico estilo GTA Vice City neon abrindo cada Ato."""
    if bg_img_path and os.path.exists(bg_img_path):
        im = Image.open(bg_img_path).convert("RGB")
        iw, ih = im.size
        sc = max(1920 / float(iw), 1080 / float(ih))
        im = im.resize((int(iw * sc), int(ih * sc)), Image.Resampling.LANCZOS)
        x0, y0 = (im.width - 1920) // 2, (im.height - 1080) // 2
        bg = im.crop((x0, y0, x0 + 1920, y0 + 1080)).filter(ImageFilter.GaussianBlur(18))
    else:
        bg = Image.new("RGB", (1920, 1080), (14, 10, 24))

    overlay = Image.new("RGBA", (1920, 1080), (12, 8, 22, 165))
    canvas = Image.alpha_composite(bg.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(canvas)

    # Barra gradiente neon rosa/ciano GTA 6
    draw.rectangle([160, 390, 1760, 400], fill=(255, 70, 180, 255))
    draw.rectangle([160, 670, 1760, 680], fill=(0, 235, 255, 255))

    f_tag = load_font(48)
    f_title = load_font(86)
    tag = f"CAPÍTULO {act_num}"
    tb = draw.textbbox((0, 0), tag, font=f_tag)
    tw = tb[2] - tb[0]
    draw.rounded_rectangle([(1920 - tw) // 2 - 28, 310, (1920 + tw) // 2 + 28, 376], radius=14, fill=(255, 70, 180, 245))
    draw.text(((1920 - tw) // 2, 316), tag, font=f_tag, fill=(255, 255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0, 255))

    clean_t = _clean_txt(act_title).upper()
    words = clean_t.split()
    lines = []
    cur = []
    for w in words:
        cur.append(w)
        if len(" ".join(cur)) > 26:
            lines.append(" ".join(cur[:-1]))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))
    lines = lines[:2]

    yy = 450 if len(lines) == 2 else 495
    for ln in lines:
        lb = draw.textbbox((0, 0), ln, font=f_title)
        lw = lb[2] - lb[0]
        draw.text(((1920 - lw) // 2, yy), ln, font=f_title, fill=(255, 245, 210, 255), stroke_width=6, stroke_fill=(0, 0, 0, 255))
        yy += 102

    canvas.convert("RGB").save(out_jpg, quality=92)
    return out_jpg


def _make_hud_top_png(act_num, total_acts, callout, out_png):
    img = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Barra de progresso discreta GTA Vice City
    draw.rectangle([0, 0, 1920, 7], fill=(16, 16, 26, 200))
    prog = act_num / float(max(1, total_acts))
    draw.rectangle([0, 0, int(1920 * prog), 7], fill=(255, 75, 185, 255))

    clean_co = _clean_txt(callout).upper()
    if clean_co:
        f_co = load_font(36)
        bb = draw.textbbox((0, 0), clean_co, font=f_co)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        draw.rounded_rectangle([38, 28, 38 + tw + 40, 28 + th + 24], radius=12, fill=(14, 12, 24, 210), outline=(0, 235, 255, 230), width=3)
        draw.text((58, 36), clean_co, font=f_co, fill=(255, 240, 80, 255), stroke_width=2, stroke_fill=(0, 0, 0, 255))

    img.save(out_png)
    return out_png


def _render_visual_plate(dur, mp4_pool, jpg_pool, idx_cursor, hud_png, out_silent_mp4, work_dir, tag):
    """
    Gera o vídeo visual 1920x1080@30fps de um bloco (~16-20s) trocando de cena a cada ~4.5-6s,
    alternando MP4s oficiais da Rockstar e animações Ken Burns de screenshots 4K.
    """
    sub_clips = []
    remaining = dur
    sub_idx = 0
    while remaining > 0.1:
        span = min(remaining, random.uniform(4.4, 6.2))
        if remaining - span < 2.2:
            span = remaining
        seg_p = os.path.join(work_dir, f"vis_{tag}_{sub_idx}.mp4")
        use_mp4 = bool(mp4_pool) and (sub_idx % 2 == 0 or not jpg_pool)
        if use_mp4:
            src_v = mp4_pool[(idx_cursor + sub_idx) % len(mp4_pool)]
            src_dur = max(1.0, get_media_duration(src_v))
            ss = random.uniform(0.0, max(0.0, src_dur - span - 0.2)) if src_dur > span + 0.5 else 0.0
            subprocess.run([
                FFMPEG_EXE, "-y", "-stream_loop", "-1", "-ss", f"{ss:.2f}", "-i", src_v,
                "-t", f"{span:.2f}",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,eq=contrast=1.05:saturation=1.10,fps=30,setsar=1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an",
                seg_p,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            src_img = jpg_pool[(idx_cursor + sub_idx) % len(jpg_pool)]
            frames_n = max(30, int(round(span * 30)))
            zoom_expr = "min(zoom+0.0014,1.16)" if sub_idx % 4 == 1 else "if(eq(on,1),1.15,max(1.0,zoom-0.0012))"
            subprocess.run([
                FFMPEG_EXE, "-y", "-loop", "1", "-t", f"{span:.2f}", "-i", src_img,
                "-vf", f"scale=2560:1440:force_original_aspect_ratio=increase,crop=2560:1440,zoompan=z='{zoom_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames_n}:s=1920x1080:fps=30,eq=contrast=1.05:saturation=1.10,setsar=1",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-an",
                seg_p,
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        sub_clips.append(seg_p)
        remaining -= span
        sub_idx += 1

    ct = os.path.join(work_dir, f"vis_{tag}_concat.txt")
    with open(ct, "w", encoding="utf-8") as f:
        for sp in sub_clips:
            f.write(f"file '{os.path.abspath(sp).replace(chr(92), '/')}'\n")
    raw_vis = os.path.join(work_dir, f"vis_{tag}_raw.mp4")
    subprocess.run([FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", ct, "-c", "copy", raw_vis], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    subprocess.run([
        FFMPEG_EXE, "-y", "-i", raw_vis, "-i", hud_png,
        "-filter_complex", "[0:v][1:v]overlay=0:0,format=yuv420p[v]",
        "-map", "[v]", "-t", f"{dur:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30", "-an",
        out_silent_mp4,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_silent_mp4, sub_idx


def build_gta6_long_thumbnail(jpg_vault, thumb_text, out_jpg):
    """Thumbnail nível canal grande de GTA 6 (1280x720, zero avatar, foco total em contraste/curiosidade)."""
    hero = None
    for p in jpg_vault:
        im = Image.open(p)
        if im.width >= 1000 and im.width > im.height:
            hero = im.convert("RGB")
            break
    if hero is None and jpg_vault:
        hero = Image.open(jpg_vault[0]).convert("RGB")
    if hero is None:
        hero = Image.new("RGB", (1280, 720), (25, 12, 42))

    # Resize/crop cover 1280x720 + punch de cor Vice City
    sc = max(1280 / float(hero.width), 720 / float(hero.height))
    hero = hero.resize((int(hero.width * sc), int(hero.height * sc)), Image.Resampling.LANCZOS)
    x0, y0 = (hero.width - 1280) // 2, (hero.height - 720) // 2
    canvas = hero.crop((x0, y0, x0 + 1280, y0 + 720))

    arr = np.array(canvas, dtype=np.float32)
    # Saturação + contraste cinematográfico + vinheta escura embaixo para o texto explodir
    mean = arr.mean(axis=2, keepdims=True)
    arr = np.clip(mean + (arr - mean) * 1.25, 0, 255)
    arr = np.clip((arr - 128) * 1.12 + 128, 0, 255)
    # Gradiente escuro inferior 100% suave (sem linha de corte horizontal)
    grad = np.ones((720, 1, 1), dtype=np.float32)
    grad[340:] = np.linspace(1.0, 0.26, 720 - 340, dtype=np.float32)[:, None, None]
    arr = arr * grad
    canvas = Image.fromarray(arr.astype(np.uint8))

    draw = ImageDraw.Draw(canvas)
    # Badge GTA 6 canto superior esquerdo
    f_badge = load_font(56)
    draw.rounded_rectangle([32, 28, 250, 108], radius=16, fill=(235, 36, 130), outline=(255, 232, 45), width=5)
    draw.text((54, 38), "GTA 6", font=f_badge, fill=(255, 255, 255), stroke_width=4, stroke_fill=(0, 0, 0))

    # Texto gigante na base
    f_big = load_font(118)
    clean_t = (_clean_txt(thumb_text) or "VAI MUDAR TUDO!").upper()
    tb = draw.textbbox((0, 0), clean_t, font=f_big)
    tw = tb[2] - tb[0]
    while tw > 1200 and f_big.size > 68:
        f_big = load_font(f_big.size - 8)
        tb = draw.textbbox((0, 0), clean_t, font=f_big)
        tw = tb[2] - tb[0]
    tx = (1280 - tw) // 2
    draw.text((tx + 6, 545 + 6), clean_t, font=f_big, fill=(0, 0, 0))
    draw.text((tx, 545), clean_t, font=f_big, fill=(255, 235, 30), stroke_width=10, stroke_fill=(0, 0, 0))

    canvas.save(out_jpg, quality=95)
    return out_jpg


def compose_gta6_long_video(script_data, wav_map, mp4_vault, jpg_vault, work_dir, output_mp4, output_thumb_jpg):
    sfx_whoosh, sfx_freeze = ensure_sfx()
    sfx_pop = ensure_pop_sfx()

    acts = script_data["acts"]
    total_acts = len(acts)
    segments = []
    idx_cursor = 0
    chapters_ts = []
    total_t = 0.0

    for a_idx, act in enumerate(acts):
        act_num = int(act.get("act_num", a_idx + 1))
        act_title = act.get("act_title", f"ATO {act_num}")
        mood = act.get("bgm_mood", "synth")
        bgm_file = os.path.join(ASSETS_DIR, BGM_MOOD_MAP.get(mood, "bgm_gta_synth.mp3"))
        if not os.path.exists(bgm_file):
            bgm_file = os.path.join(ASSETS_DIR, "bgm_gta_synth.mp3")
        bgm_dur = max(15.0, get_media_duration(bgm_file))

        mm, ss = divmod(int(total_t), 60)
        chapters_ts.append(f"{mm}:{ss:02d} {act_title}")

        # Card animado de abertura de Capítulo (2.2s) com BGM + whoosh
        card_jpg = os.path.join(work_dir, f"act_{act_num}_card.jpg")
        bg_img = jpg_vault[a_idx % len(jpg_vault)] if jpg_vault else None
        _make_chapter_card_jpg(act_num, act_title, bg_img, card_jpg)
        card_mp4 = os.path.join(work_dir, f"seg_act{act_num:02d}_00_card.mp4")
        subprocess.run([
            FFMPEG_EXE, "-y", "-loop", "1", "-t", "2.20", "-i", card_jpg,
            "-i", sfx_whoosh, "-stream_loop", "-1", "-i", bgm_file,
            "-filter_complex", (
                "[0:v]scale=2112:1188,zoompan=z='min(zoom+0.002,1.10)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=66:s=1920x1080:fps=30,format=yuv420p[v];"
                "[1:a]volume=0.55[s];[2:a]atrim=0:2.20,volume=1.10[b];[s][b]amix=inputs=2:duration=longest:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[a]"
            ),
            "-map", "[v]", "-map", "[a]", "-t", "2.20",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-video_track_timescale", "30000",
            card_mp4,
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        segments.append(card_mp4)
        total_t += 2.20

        bgm_offset = 2.2
        for b_idx, blk in enumerate(act.get("blocks", [])):
            bid = f"a{act_num}_b{b_idx}"
            wav_p = wav_map[bid]
            dur = max(2.2, get_media_duration(wav_p) + 0.18)

            hud_png = os.path.join(work_dir, f"hud_{bid}.png")
            _make_hud_top_png(act_num, total_acts, blk.get("callout", ""), hud_png)

            vis_silent = os.path.join(work_dir, f"vis_{bid}_silent.mp4")
            _, used_sub = _render_visual_plate(dur, mp4_vault, jpg_vault, idx_cursor, hud_png, vis_silent, work_dir, bid)
            idx_cursor += used_sub

            # Sobrepõe legendas profissionais sincronizadas + mixa narração (-14.5 LUFS) + trilha sonora do Ato
            chunks = _split_sub_chunks(blk["narration"], dur)
            sub_inputs = []
            ov_parts = []
            cur_lbl = "0:v"
            for ci, (ctext, t0, t1) in enumerate(chunks):
                sp = os.path.join(work_dir, f"sub_{bid}_{ci}.png")
                _make_doc_subtitle_png(ctext, blk.get("callout", ""), sp)
                sub_inputs += ["-i", sp]
                inp_i = 4 + ci
                nxt = f"sv_{ci}"
                ov_parts.append(f"[{cur_lbl}][{inp_i}:v]overlay=0:0:enable='between(t,{t0:.2f},{t1:.2f})'[{nxt}]")
                cur_lbl = nxt
            ov_parts.append(f"[{cur_lbl}]format=yuv420p[vout]")

            bgm_ss = bgm_offset % max(2.0, bgm_dur - dur - 2.0)
            fade_st = max(0.0, dur - 0.35)
            sfx_p = sfx_pop if b_idx > 0 else sfx_freeze
            aud_fc = (
                f"[1:a]volume=1.18[vo];"
                f"[2:a]atrim=0:{dur:.2f},afade=t=in:st=0:d=0.25,afade=t=out:st={fade_st:.2f}:d=0.35,volume=0.88[bm];"
                f"[3:a]volume=0.28[sx];"
                f"[vo][bm][sx]amix=inputs=3:duration=first:normalize=0,aformat=sample_rates=48000:channel_layouts=stereo[aout]"
            )

            seg_out = os.path.join(work_dir, f"seg_{act_num:02d}_{b_idx:02d}.mp4")
            cmd = [
                FFMPEG_EXE, "-y",
                "-i", vis_silent,
                "-i", wav_p,
                "-stream_loop", "-1", "-ss", f"{bgm_ss:.2f}", "-i", bgm_file,
                "-i", sfx_p,
            ] + sub_inputs + [
                "-filter_complex", ";".join(ov_parts) + ";" + aud_fc,
                "-map", "[vout]", "-map", "[aout]", "-t", f"{dur:.2f}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-r", "30",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", "-video_track_timescale", "30000",
                seg_out,
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            segments.append(seg_out)
            bgm_offset += dur
            total_t += dur

    concat_txt = os.path.join(work_dir, "gta6_long_concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{os.path.abspath(s).replace(chr(92), '/')}'\n")

    print(f"[GTA6 LONG COMPOSER] Concatenando {len(segments)} cenas em 1920x1080 ({total_t/60:.2f} min)...", flush=True)
    subprocess.run([
        FFMPEG_EXE, "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c", "copy", "-movflags", "+faststart", output_mp4,
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    build_gta6_long_thumbnail(jpg_vault, script_data.get("thumb_text", "QUINTA-FEIRA!"), output_thumb_jpg)
    real_dur = get_media_duration(output_mp4)
    print(f"[GTA6 LONG COMPOSER] Vídeo longo finalizado: {output_mp4} ({real_dur/60:.2f} min | {real_dur:.1f}s)")
    return output_mp4, output_thumb_jpg, chapters_ts, real_dur
