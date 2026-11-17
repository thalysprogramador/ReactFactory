import json
import os
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from gta6_hunter import (  # noqa: E402
    GTA6_TEMP_DIR,
    research_gta6_references,
    save_gta6_history,
    sync_rockstar_gta6_vault,
)
from gta6_long_brain import generate_gta6_long_script  # noqa: E402
from gta6_long_composer import compose_gta6_long_video  # noqa: E402
from kaggle_chatterbox import run_batch_chatterbox_kaggle  # noqa: E402
from uploader import upload_long_to_youtube  # noqa: E402


def run_gta6_long_pipeline(do_upload=False):
    print("====================================================")
    print("   INICIANDO ESTEIRA PRO GTA 6 LONGO (8-9 MIN 16:9)")
    print("====================================================")

    os.makedirs(GTA6_TEMP_DIR, exist_ok=True)
    work_dir = os.path.join(GTA6_TEMP_DIR, "long_work")
    os.makedirs(work_dir, exist_ok=True)

    research = research_gta6_references(kind="long")
    mp4_vault, jpg_vault = sync_rockstar_gta6_vault(max_mp4=10, max_jpg=22)

    script_data = generate_gta6_long_script(research)
    with open(os.path.join(work_dir, "script_gta6_long.json"), "w", encoding="utf-8") as sf:
        json.dump(script_data, sf, indent=2, ensure_ascii=False)

    chunks = []
    for a_idx, act in enumerate(script_data["acts"]):
        act_num = int(act.get("act_num", a_idx + 1))
        for b_idx, blk in enumerate(act["blocks"]):
            cid = f"a{act_num}_b{b_idx}"
            chunks.append({
                "id": cid,
                "text": blk["narration"],
                "output_wav": os.path.join(work_dir, f"narr_{cid}.wav"),
                "exaggeration": 0.56,
            })

    wav_map, engine_used = run_batch_chatterbox_kaggle(chunks, out_dir=work_dir, timeout_sec=1200)
    print(f"[GTA6 LONG VOICE] Motor usado em 100% da narração: {engine_used}")

    out_mp4 = os.path.join(BASE_DIR, "output_gta6_long.mp4")
    out_thumb = os.path.join(BASE_DIR, "output_gta6_long_thumb.jpg")
    _, _, chapters_ts, real_dur = compose_gta6_long_video(
        script_data=script_data,
        wav_map=wav_map,
        mp4_vault=mp4_vault,
        jpg_vault=jpg_vault,
        work_dir=work_dir,
        output_mp4=out_mp4,
        output_thumb_jpg=out_thumb,
    )

    desc = (
        f"{script_data.get('long_description', '').strip()}\n\n"
        "Capítulos:\n" + "\n".join(chapters_ts)
    )

    yt_id = None
    if do_upload:
        yt_id = upload_long_to_youtube(
            video_path=out_mp4,
            title=script_data["long_title"],
            description=desc,
            tags=script_data.get("long_tags", ["gta 6", "gta vi", "rockstar games", "games"]),
            thumb_path=out_thumb,
            privacy_status="public",
        )
        save_gta6_history(
            angle=research["chosen_angle"],
            kind="long",
            metadata={
                "yt_uploaded_id": yt_id,
                "title": script_data["long_title"],
                "duration_sec": round(real_dur, 1),
                "voice_engine": engine_used,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    else:
        print(f"[GTA6 LONG] Preview salvo em: {out_mp4} e {out_thumb}")

    return out_mp4, out_thumb, yt_id


if __name__ == "__main__":
    run_gta6_long_pipeline(do_upload=("--upload" in sys.argv))
