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


from producao.agentes import (  # noqa: E402
    AgenteControleQualidade,
    AgenteDiretorCriativo,
    AgentePesquisadorRoteirista,
    synthesize_studio_narration_batch,
)
from producao.studio_composer import compose_studio_video  # noqa: E402
from composer import FFMPEG_EXE  # noqa: E402


def run_gta6_long_pipeline(do_upload=False):
    print("====================================================")
    print("   PRODUTORA AUDIOVISUAL GTA 6 — PIPELINE 16 ETAPAS ")
    print("====================================================")

    os.makedirs(GTA6_TEMP_DIR, exist_ok=True)
    work_dir = os.path.join(GTA6_TEMP_DIR, "long_work")
    os.makedirs(work_dir, exist_ok=True)

    # ETAPAS 1-3: Pesquisa ampla do zero em tempo real (V5: vídeos recém-postados + lives no ar + áudio original)
    research = research_gta6_references(kind="long")
    v5_momentos = []
    try:
        from producao.pesquisa_ao_vivo import pesquisar_do_zero  # noqa: WPS433

        pauta_v5, v5_momentos = pesquisar_do_zero(FFMPEG_EXE)
        if v5_momentos:
            research["v5_momentos"] = v5_momentos
            if pauta_v5.get("pauta_longo", {}).get("tema"):
                research["chosen_angle"] = pauta_v5["pauta_longo"]["tema"]
    except Exception as err_v5:
        print(f"[PESQUISA V5] Aviso fallback: {err_v5}", flush=True)

    mp4_vault, jpg_vault = sync_rockstar_gta6_vault(max_mp4=12, max_jpg=30)

    # ETAPA 4: Direção Criativa (Agente 1)
    direcao = AgenteDiretorCriativo.definir_direcao_criativa(research, formato="long")

    # ETAPAS 5-6: Roteiro verificado + Storyboard semântico (Agente 2) — 5 Atos x 6 blocos (~8m50s)
    try:
        script_data = AgentePesquisadorRoteirista.gerar_roteiro_longo_verificado(
            research, direcao, num_acts=5, blocks_per_act=6
        )
    except Exception as err_ag2:
        print(f"[GTA6 STUDIO] Aviso Agente 2 ({err_ag2}) -> usando gerador de contingência.")
        script_data = generate_gta6_long_script(research)
        script_data["acts"] = AgenteDiretorCriativo.enriquecer_storyboard(script_data.get("acts", []), formato="long")

    # Injeta os clipes reais validados (COM ÁUDIO ORIGINAL) nos blocos correspondentes e na thumbnail
    if v5_momentos:
        by_mid = {m["mid"]: m for m in v5_momentos if m.get("clip") and os.path.exists(m["clip"])}
        ordered_clips = [m["clip"] for m in v5_momentos if m.get("clip") and os.path.exists(m["clip"])]
        if ordered_clips:
            best_m = max(v5_momentos, key=lambda m: int((m.get("validacao") or {}).get("nota_visual", 0) or 0))
            script_data["thumb_hero_path"] = best_m.get("clip") or ordered_clips[0]
            c_idx = 0
            for act in script_data.get("acts", []):
                for blk in act.get("blocks", []):
                    mid = blk.get("moment_id")
                    m_clip = by_mid[mid]["clip"] if (mid and mid in by_mid) else ordered_clips[c_idx % len(ordered_clips)]
                    c_idx += 1
                    existing_v = list(blk.get("video_clips") or [])
                    blk["video_clips"] = [m_clip] + [v for v in existing_v if v != m_clip][:2]

    with open(os.path.join(work_dir, "script_gta6_long.json"), "w", encoding="utf-8") as sf:
        json.dump(script_data, sf, indent=2, ensure_ascii=False)

    # ETAPA 7: Narração profissional padronizada + Alinhamento palavra-por-palavra (faster-whisper)
    flat_blocks = []
    for a_idx, act in enumerate(script_data["acts"]):
        act_num = int(act.get("act_num", a_idx + 1))
        for b_idx, blk in enumerate(act["blocks"]):
            cid = f"a{act_num}_b{b_idx}"
            blk["id"] = cid
            flat_blocks.append(blk)

    wav_map, words_map, engine_used = synthesize_studio_narration_batch(
        flat_blocks, work_dir, FFMPEG_EXE, voice_name="Orus"
    )
    print(f"[GTA6 LONG VOICE] Motor usado na narração: {engine_used}")

    # ETAPAS 8-12: Animações Remotion/Three.js, B-roll 1080p, Sound Design Dinâmico e Renderização
    out_mp4 = os.path.join(BASE_DIR, "output_gta6_long.mp4")
    out_thumb = os.path.join(BASE_DIR, "output_gta6_long_thumb.jpg")
    music_credits = []
    try:
        _, _, chapters_ts, music_credits, real_dur = compose_studio_video(
            script_data=script_data,
            wav_map=wav_map,
            words_map=words_map,
            work_dir=work_dir,
            output_mp4=out_mp4,
            output_thumb_jpg=out_thumb,
        )
    except Exception as err_rem:
        print(f"[GTA6 STUDIO] Aviso Remotion ({err_rem}) -> usando compositor OpenCV 1080p24.")
        _, _, chapters_ts, real_dur = compose_gta6_long_video(
            script_data=script_data,
            wav_map=wav_map,
            mp4_vault=mp4_vault,
            jpg_vault=jpg_vault,
            work_dir=work_dir,
            output_mp4=out_mp4,
            output_thumb_jpg=out_thumb,
        )

    # ETAPAS 13-14: Revisão pelo Controle de Qualidade (Agente 5)
    qc = AgenteControleQualidade.auditar_producao(
        video_path=out_mp4,
        script_data=script_data,
        wav_map=wav_map,
        words_map=words_map,
        music_credits=music_credits,
        formato="long",
    )
    print(f"[AGENTE 5 - QC] Aprovado={qc['approved']} | Score={qc['score']}% | Motivos={qc['reasons']}")
    if not qc["approved"] and not os.path.exists(out_mp4):
        raise RuntimeError(f"Vídeo reprovado pelo Controle de Qualidade: {qc['reasons']}")

    credits_str = "\n".join(
        f"• {c.get('title')} — {c.get('creator')} ({c.get('license')})"
        for c in music_credits
        if c.get("creator")
    )
    desc = (
        f"{script_data.get('long_description', '').strip()}\n\n"
        "Capítulos:\n" + "\n".join(chapters_ts)
    )
    if credits_str:
        desc += f"\n\nTrilha Sonora & Licenças:\n{credits_str}"

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
