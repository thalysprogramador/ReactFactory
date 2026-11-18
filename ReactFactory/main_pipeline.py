import os
import sys
import json
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from hunter import hunt_viral_video, save_history
from gta6_hunter import hunt_gta6_short_source, save_gta6_history
from brain import generate_react_script
from sfx import ensure_sfx
from voice_and_avatar import (
    generate_consistent_voices,
    pick_avatar_clips,
    generate_batch_lipsync_clips,
)
from composer import compose_react_short, build_short_thumbnail
from uploader import upload_short_to_youtube, set_video_thumbnail

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def run_pipeline(do_upload=False):
    theme = os.environ.get("CHANNEL_THEME", "gta6").strip().lower()
    print("====================================================")
    print(f"   INICIANDO ESTEIRA PRO SHORTS ({theme.upper()} + LATENTSYNC)")
    print("====================================================")

    sfx_whoosh, sfx_freeze = ensure_sfx()

    if theme == "gta6":
        print("[1/5] Pesquisando referências virais + cenas oficiais de GTA 6...")
        viral_info = hunt_gta6_short_source(os.path.join(TEMP_DIR, "viral_raw.mp4"))
    else:
        print("[1/5] Minerando vídeo viral recente...")
        viral_info = hunt_viral_video(os.path.join(TEMP_DIR, "viral_raw.mp4"))
    viral_path = viral_info["path"]

    print("[2/5] Analisando contexto, referências e frames com Gemini Flash...")
    script_data = generate_react_script(
        viral_path,
        viral_info["title"],
        viral_info.get("description", ""),
        research_brief=viral_info.get("research_brief"),
    )
    print("[ROTEIRO GERADO]:", json.dumps(script_data, indent=2, ensure_ascii=False))

    print("[3/5] Gerando narração profissional padronizada (Gemini 3.8 Flash TTS 'Orus' -14.5 LUFS)...")
    hook_wav = os.path.join(TEMP_DIR, "voice_hook.wav")
    inter_wav = os.path.join(TEMP_DIR, "voice_inter.wav")
    outro_wav = os.path.join(TEMP_DIR, "voice_outro.wav")

    generate_consistent_voices(
        {
            "hook": script_data["hook_text"],
            "inter": script_data["interrupt_text"],
            "outro": script_data["outro_text"],
        },
        {
            "hook": hook_wav,
            "inter": inter_wav,
            "outro": outro_wav,
        },
    )

    print("[4/5] Renderizando Short V3 (Full-Screen Cortes de Lives + Proporção Cinema + Legendas Gigantes Sem Caixa)...")
    final_output = os.path.join(BASE_DIR, "output_react_short_v4.mp4")
    compose_react_short(
        viral_video_path=viral_path,
        hook_avatar_mp4=None,
        hook_audio_wav=hook_wav,
        interrupt_avatar_mp4=None,
        interrupt_audio_wav=inter_wav,
        outro_avatar_mp4=None,
        outro_audio_wav=outro_wav,
        idle_avatar_mp4=None,
        idle_avatar_mp4_2=None,
        script_data=script_data,
        sfx_whoosh_path=sfx_whoosh,
        sfx_freeze_path=sfx_freeze,
        output_final_mp4=final_output,
    )

    short_thumb = os.path.join(BASE_DIR, "output_short_thumb.jpg")
    try:
        build_short_thumbnail(
            viral_video_path=viral_path,
            headline_text=script_data.get("headline_top", "TRAVOU A LIVE NO GTA 6!"),
            reaction_video_path=None,
            out_jpg=short_thumb,
        )
    except Exception as terr:
        print(f"[THUMB SHORT] Aviso: {terr}")
        short_thumb = None

    yt_video_id = None
    if do_upload:
        print("[5/5] Fazendo upload automático para o YouTube Shorts...")
        yt_video_id = upload_short_to_youtube(
            video_path=final_output,
            title=script_data.get("yt_title", "Segredo absurdo do GTA 6! #gta6 #shorts"),
            description=script_data.get("yt_description", "#gta6 #gtavi #rockstargames #shorts"),
            tags=script_data.get("yt_tags", ["gta 6", "gta vi", "rockstar games", "shorts", "viral"]),
            privacy_status="public",
        )
        if yt_video_id and short_thumb and os.path.exists(short_thumb):
            try:
                set_video_thumbnail(yt_video_id, short_thumb)
            except Exception as err:
                print(f"[UPLOADER] Aviso capa Short (YouTube pode limitar API thumb em Shorts): {err}")

    if theme == "gta6":
        save_gta6_history(
            video_id=viral_info["id"],
            angle=(viral_info.get("research_brief") or {}).get("chosen_angle"),
            kind="short",
            metadata={
                "viral_id": viral_info["id"],
                "original_title": viral_info["title"],
                "yt_title": script_data.get("yt_title"),
                "yt_uploaded_id": yt_video_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    save_history(
        viral_info["id"],
        {
            "viral_id": viral_info["id"],
            "original_title": viral_info["title"],
            "views": viral_info.get("views"),
            "yt_title": script_data.get("yt_title"),
            "yt_uploaded_id": yt_video_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )

    print("====================================================")
    print(f"   CONCLUÍDO! VÍDEO V3 SALVO EM: {final_output}")
    print("====================================================")
    return final_output, script_data


if __name__ == "__main__":
    upload_flag = "--upload" in sys.argv
    run_pipeline(do_upload=upload_flag)
