import os
import sys
import json
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from hunter import hunt_viral_video, save_history
from brain import generate_react_script
from sfx import ensure_sfx
from voice_and_avatar import (
    generate_realistic_voice,
    pick_avatar_clips,
    generate_batch_lipsync_clips,
)
from composer import compose_react_short
from uploader import upload_short_to_youtube

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)


def run_pipeline(do_upload=False):
    print("====================================================")
    print("   INICIANDO ESTEIRA V4 (LATENTSYNC KAGGLE + CURIOSIDADE)")
    print("====================================================")

    sfx_whoosh, sfx_freeze = ensure_sfx()

    print("[1/5] Minerando vídeo viral recente de curiosidade/ciência...")
    viral_info = hunt_viral_video(os.path.join(TEMP_DIR, "viral_raw.mp4"))
    viral_path = viral_info["path"]

    print("[2/5] Analisando contexto e vídeo com Gemini Flash e criando roteiro de retenção...")
    script_data = generate_react_script(
        viral_path,
        viral_info["title"],
        viral_info.get("description", ""),
    )
    print("[ROTEIRO GERADO]:", json.dumps(script_data, indent=2, ensure_ascii=False))

    clips = pick_avatar_clips(script_data.get("reaction_mood", "chocado"))
    print(f"[AVATAR] Clipes selecionados: fala={[os.path.basename(p) for p in clips['talking']]} | "
          f"reação1={os.path.basename(clips['reaction_primary'])} | reação2={os.path.basename(clips['reaction_secondary'])}")

    print("[3/5] Gerando vozes realistas e sincronizando lábios via ByteDance LatentSync v1.5 (Kaggle T4)...")
    hook_wav = os.path.join(TEMP_DIR, "voice_hook.wav")
    inter_wav = os.path.join(TEMP_DIR, "voice_inter.wav")
    outro_wav = os.path.join(TEMP_DIR, "voice_outro.wav")

    mood = script_data.get("reaction_mood", "chocado")
    tone_styles = {
        "rindo": ("bem-humorado, rindo e super espontâneo", "rachando o bico apontando a cena", "zoeiro chamando a galera pra comentar"),
        "chocado": ("chocado, incrédulo e com muita energia", "muito surpreso revelando o detalhe absurdo", "intrigado perguntando o que o público achou"),
        "pensativo": ("curioso, intrigado e misterioso", "revelando um detalhe que ninguém reparou", "provocativo perguntando a opinião do público"),
        "impressionado": ("empolgado, admirado e vibrante", "admirado destacando o ponto mais insano", "entusiasmado puxando o público pros comentários"),
    }
    h_style, i_style, o_style = tone_styles.get(mood, tone_styles["chocado"])

    generate_realistic_voice(script_data["hook_text"], hook_wav, h_style)
    generate_realistic_voice(script_data["interrupt_text"], inter_wav, i_style)
    generate_realistic_voice(script_data["outro_text"], outro_wav, o_style)

    synced = generate_batch_lipsync_clips(
        hook_wav=hook_wav,
        inter_wav=inter_wav,
        outro_wav=outro_wav,
        talking_clips=clips["talking"],
        out_dir=TEMP_DIR,
    )

    print("[4/5] Renderizando edição V4 (Reação Silenciosa Variada + LatentSync + Legendas Gigantes)...")
    final_output = os.path.join(BASE_DIR, "output_react_short_v4.mp4")
    compose_react_short(
        viral_video_path=viral_path,
        hook_avatar_mp4=synced["hook"],
        hook_audio_wav=hook_wav,
        interrupt_avatar_mp4=synced["inter"],
        interrupt_audio_wav=inter_wav,
        outro_avatar_mp4=synced["outro"],
        outro_audio_wav=outro_wav,
        idle_avatar_mp4=clips["reaction_primary"],
        idle_avatar_mp4_2=clips["reaction_secondary"],
        script_data=script_data,
        sfx_whoosh_path=sfx_whoosh,
        sfx_freeze_path=sfx_freeze,
        output_final_mp4=final_output,
    )

    yt_video_id = None
    if do_upload:
        print("[5/5] Fazendo upload automático para o YouTube Shorts...")
        yt_video_id = upload_short_to_youtube(
            video_path=final_output,
            title=script_data.get("yt_title", "Olha o que aconteceu! #shorts"),
            description=script_data.get("yt_description", "#shorts #react #viral"),
            tags=script_data.get("yt_tags", ["shorts", "react", "viral"]),
            privacy_status="public",
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
