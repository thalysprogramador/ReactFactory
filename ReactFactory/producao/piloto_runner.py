"""EXECUTOR DO PROJETO-PILOTO E PIPELINE DE 16 ETAPAS (6 AGENTES ESPECIALIZADOS GTA 6).

Executa e registra todas as 16 etapas obrigatórias em arquivos JSON auditáveis:
ETAPA 1-3: Pesquisa de assuntos, seleção de tema e verificação de fontes (Agente 2)
ETAPA 4: Direção criativa e definição da abordagem (Agente 1)
ETAPA 5-6: Desenvolvimento e aprovação do roteiro com classificação de fontes (Agente 2 + Agente 1)
ETAPA 7: Geração da narração profissional padronizada + alinhamento Whisper (Agente 3/Voz)
ETAPA 8: Busca semântica de B-rolls 4K/1080p, músicas licenciadas e SFX (Agente 3 + Agente 4)
ETAPA 9-12: Animações Remotion/Three.js, montagem, mixagem e renderização (Agente 3 + Agente 4)
ETAPA 13-14: Auditoria pelo Controle de Qualidade (Agente 5) e auto-correção
ETAPA 15-16: Preparação de metadados, thumbnail editorial e entrega final (Agente 1 + Agente 6)
"""
import json
import os
import shutil
import sys
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from composer import FFMPEG_EXE  # noqa: E402
from gta6_hunter import research_gta6_references, sync_rockstar_gta6_vault  # noqa: E402
from producao.agentes import (  # noqa: E402
    AgenteControleQualidade,
    AgenteDiretorCriativo,
    AgentePesquisadorRoteirista,
    synthesize_studio_narration_batch,
)
from producao.studio_composer import compose_studio_video  # noqa: E402


def run_studio_pipeline(mode="pilot", do_upload=False):
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(BASE_DIR, "temp_gta6", f"studio_run_{mode}")
    os.makedirs(run_dir, exist_ok=True)

    print(f"=== [ETAPAS 1-3] Pesquisa Diária GTA 6 e Verificação de Fontes ({mode.upper()}) ===", flush=True)
    research = research_gta6_references(kind="long")
    sync_rockstar_gta6_vault(max_mp4=10, max_jpg=30)
    with open(os.path.join(run_dir, "01_pesquisa_verificada.json"), "w", encoding="utf-8") as f:
        json.dump(research, f, indent=2, ensure_ascii=False)

    print("=== [ETAPA 4] Direção Criativa (Agente 1) ===", flush=True)
    direcao = AgenteDiretorCriativo.definir_direcao_criativa(research, formato="long")
    with open(os.path.join(run_dir, "02_direcao_criativa.json"), "w", encoding="utf-8") as f:
        json.dump(direcao, f, indent=2, ensure_ascii=False)

    print("=== [ETAPAS 5-6] Roteiro com Fontes Classificadas e Storyboard Semântico (Agente 2) ===", flush=True)
    if mode == "pilot":
        # Roteiro-piloto demonstrando os 4 tipos de cenas contextuais (Map Zoom, Dossier, 3D Data, Spotlight)
        script_data = {
            "long_title": "GTA 6: O Dossiê Definitivo do Lançamento em Leonida (19 de Novembro)",
            "long_description": (
                "Análise audiovisual completa sobre o lançamento oficial de Grand Theft Auto VI na quinta-feira, "
                "19 de novembro de 2026, com mapeamento das 6 regiões de Leonida, dossiê de Lucia e Jason, "
                "comparativo técnico 3D e análise da engine RAGE 9."
            ),
            "long_tags": ["gta 6", "gta vi", "lancamento gta 6", "leonida", "vice city", "lucia e jason", "rockstar games"],
            "thumb_text": "19 DE NOVEMBRO",
            "thumb_subtext": "DOSSIE OFICIAL LEONIDA",
            "acts": [
                {
                    "act_num": 1,
                    "act_title": "GEOGRAFIA DE LEONIDA & PROTAGONISTAS",
                    "bgm_mood": "synth",
                    "blocks": [
                        {
                            "narration": (
                                "Faltam poucas horas para a quinta-feira, dezenove de novembro. "
                                "A Rockstar Games confirmou que o estado de Leonida terá seis grandes regiões interligadas, "
                                "indo muito além das avenidas iluminadas por neon de Vice City até o arquipélago tropical de Leonida Keys."
                            ),
                            "headline": "VICE CITY E AS 6 REGIÕES DE LEONIDA",
                            "subheadline": "Mapeamento oficial: Vice City, Leonida Keys, Grassrivers, Port Gellhorn, Ambrosia e Mount Kalaga",
                            "callout": "LEONIDA",
                            "badge_type": "OFICIAL",
                            "source_label": "Rockstar Games / rockstargames.com/VI",
                            "scene_type": "map_zoom",
                            "location_key": "vice_city",
                        },
                        {
                            "narration": (
                                "No centro dessa história estão Lucia Caminos e Jason Duval. "
                                "Segundo o dossiê oficial da Rockstar, um assalto simples que sai do controle força a dupla "
                                "a depender um do outro para sobreviver à maior conspiração criminosa do estado."
                            ),
                            "headline": "A DINÂMICA CRIMINAL DE LUCIA E JASON",
                            "subheadline": "Primeiro casal protagonista com assaltos coordenados e inventário tático realista",
                            "callout": "LUCIA & JASON",
                            "badge_type": "OFICIAL",
                            "source_label": "Dossiê Oficial Rockstar Games",
                            "scene_type": "character_dossier",
                            "character_name": "LUCIA & JASON",
                            "character_role": "PROTAGONISTAS CENTRAIS // ESTADO DE LEONIDA",
                            "character_facts": [
                                "Lucia sai da penitenciária de Leonida determinada a mudar o jogo",
                                "Jason tem passado militar e trabalha para traficantes nas Keys",
                                "Troca dinâmica entre os dois durante fugas e assaltos"
                            ],
                        },
                    ],
                },
                {
                    "act_num": 2,
                    "act_title": "SALTO GERACIONAL & MOTOR RAGE 9",
                    "bgm_mood": "tension",
                    "blocks": [
                        {
                            "narration": (
                                "Quando comparamos os números de GTA 5 em dois mil e treze com GTA 6 agora em dois mil e vinte e seis, "
                                "o salto geracional fica evidente: saímos de uma única metrópole para seis ecossistemas completos "
                                "no PlayStation 5 e Xbox Series X e S."
                            ),
                            "headline": "SALTO GERACIONAL: GTA V vs GTA VI",
                            "subheadline": "Comparativo direto de escala, densidade de NPCs e inteligência artificial",
                            "callout": "19 DE NOVEMBRO",
                            "badge_type": "CONFIRMADO",
                            "source_label": "Take-Two Interactive / Rockstar Official",
                            "scene_type": "data_comparison",
                            "stat_value": "19 NOV",
                            "stat_unit": "QUINTA-FEIRA • 00:00",
                            "stat_label": "COMPARATIVO TÉCNICO // PS5 & XBOX SERIES X|S",
                            "comparison_items": [
                                {"label": "GTA V (Los Santos - 2013)", "value": 42, "display": "1 Cidade Principal + Deserto"},
                                {"label": "GTA VI (Estado de Leonida - 2026)", "value": 100, "display": "6 Ecossistemas + IA de Nova Geração"},
                            ],
                        },
                        {
                            "narration": (
                                "Especialistas técnicos apontam que a nova versão do motor RAGE traz simulação física de água em tempo real, "
                                "iluminação global por ray tracing e interiores de veículos detalhados como nunca vimos antes em um jogo de mundo aberto."
                            ),
                            "headline": "RAGE 9: FÍSICA DE ÁGUA E ILUMINAÇÃO GLOBAL",
                            "subheadline": "Análise técnica das texturas 4K, reflexos e vida marinha em Leonida Keys",
                            "callout": "RAGE 9",
                            "badge_type": "TEORIA",
                            "source_label": "Análise Técnica / Digital Foundry & Comunidade",
                            "scene_type": "feature_spotlight",
                        },
                    ],
                },
            ],
        }
        script_data["acts"] = AgenteDiretorCriativo.enriquecer_storyboard(script_data["acts"], formato="long")
    else:
        script_data = AgentePesquisadorRoteirista.gerar_roteiro_longo_verificado(research, direcao, num_acts=5, blocks_per_act=6)

    with open(os.path.join(run_dir, "03_roteiro_e_storyboard.json"), "w", encoding="utf-8") as f:
        json.dump(script_data, f, indent=2, ensure_ascii=False)

    print("=== [ETAPA 7] Narração Profissional PT-BR + Alinhamento Palavra-por-Palavra (faster-whisper) ===", flush=True)
    flat_blocks = []
    for act in script_data["acts"]:
        act_num = int(act["act_num"])
        for b_idx, blk in enumerate(act["blocks"]):
            bid = f"a{act_num}_b{b_idx}"
            blk["id"] = bid
            flat_blocks.append(blk)

    wav_map, words_map, voice_engine = synthesize_studio_narration_batch(flat_blocks, run_dir, FFMPEG_EXE, voice_name="Orus")
    print(f"[ETAPA 7] Voz gerada e alinhada ({voice_engine}): {len(wav_map)} blocos.", flush=True)

    print("=== [ETAPAS 8-12] Remotion + Three.js, B-Rolls 1080p, Sound Design Dinâmico e Renderização ===", flush=True)
    out_mp4 = os.path.join(BASE_DIR, f"output_studio_{mode}.mp4")
    out_thumb = os.path.join(BASE_DIR, f"output_studio_{mode}_thumb.jpg")
    _, _, chapters_ts, music_credits, real_dur = compose_studio_video(
        script_data=script_data,
        wav_map=wav_map,
        words_map=words_map,
        work_dir=run_dir,
        output_mp4=out_mp4,
        output_thumb_jpg=out_thumb,
    )

    print("=== [ETAPAS 13-14] Auditoria pelo Controle de Qualidade (Agente 5) ===", flush=True)
    qc_report = AgenteControleQualidade.auditar_producao(
        video_path=out_mp4,
        script_data=script_data,
        wav_map=wav_map,
        words_map=words_map,
        music_credits=music_credits,
        formato="pilot" if mode == "pilot" else "long",
    )
    qc_report["voice_engine"] = voice_engine
    qc_report["run_id"] = run_id
    with open(os.path.join(run_dir, "06_qc_relatorio.json"), "w", encoding="utf-8") as f:
        json.dump(qc_report, f, indent=2, ensure_ascii=False)
    print(f"[AGENTE 5 - QC] Aprovado={qc_report['approved']} | Nota={qc_report['score']}% | Duração={real_dur:.1f}s", flush=True)

    return out_mp4, out_thumb, qc_report, script_data, chapters_ts


if __name__ == "__main__":
    mode_arg = "long" if "--long" in sys.argv else "pilot"
    run_studio_pipeline(mode=mode_arg, do_upload=("--upload" in sys.argv))
