"""ESTRUTURA DOS 6 AGENTES ESPECIALIZADOS DA PRODUTORA AUDIOVISUAL GTA 6.

Implementa o fluxo sequencial obrigatório de 16 etapas com artefatos auditáveis:
- Agente 1: Diretor Criativo (identidade visual, curadoria de cenas 2D/3D, ritmo)
- Agente 2: Pesquisador e Roteirista (monitoramento diário GTA 6, verificação de fontes, roteiro natural)
- Agente 3: Editor Audiovisual (pareamento semântico de B-roll, Remotion + Three.js, legendas Whisper)
- Agente 4: Sound Designer (busca dinâmica de trilhas CC0/CC-BY, SFX contextuais, mixagem ducking -14 LUFS)
- Agente 5: Controle de Qualidade (auditoria técnica e visual de 16 critérios antes de publicar)
- Agente 6: Analista de Desempenho (auditoria de métricas reais do YouTube e feedback editorial)
"""
import json
import os
import subprocess
import wave
import cv2
import numpy as np

from producao.catalog import (
    extract_real_trailer_clips,
    is_sticker_mask_video,
    select_semantic_assets,
)
from producao.gemini_client import gemini_generate, gemini_text
from producao.sound_designer import ensure_studio_sfx_pack, fetch_dynamic_bgm_for_mood

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ============================================================================
# AGENTE 1 — DIRETOR CRIATIVO
# ============================================================================
class AgenteDiretorCriativo:
    """Define a direção de arte, tipos de cena (Map Zoom, Dossiê, 3D Data, Spotlight) e ritmo."""

    SCENE_TYPES = ["map_zoom", "character_dossier", "data_comparison", "feature_spotlight"]

    @staticmethod
    def definir_direcao_criativa(research_data, formato="long"):
        angle = research_data.get("chosen_angle", "LANÇAMENTO DO GTA 6")
        direcao = {
            "brand_identity": "CORTES TODO DIA // DOSSIÊ LEONIDA (Vice Pulse Editorial)",
            "formato": formato,
            "pauta_central": angle,
            "regras_visuais": [
                "Proibido repetir o mesmo template de motion graphics em dois blocos seguidos",
                "Toda menção a região de Leonida dispara cena map_zoom com coordenadas GPS",
                "Toda menção a Lucia, Jason, Boobie Ike, Dre'Quan ou Raul Bautista dispara character_dossier",
                "Toda menção a datas, recordes, preços ou GTA V vs GTA VI dispara data_comparison com 3D Three.js",
                "Todo bloco deve exibir o selo de classificação da informação (OFICIAL, CONFIRMADO, RUMOR, TEORIA)",
            ],
            "color_grading": "Vice Pulse (contraste 1.06, saturação 1.12, sombras frias #090B12, altas-luzes âmbar/magenta)",
        }
        return direcao

    @staticmethod
    def enriquecer_storyboard(acts, formato="long", research_data=None):
        """
        Regra Editorial V6 (SINCRONIZAÇÃO 1-PARA-1 ZERO REPETIÇÃO + REMOTION CINEMA SELETIVO):
        - Cada bloco recebe 1 único clipe real validado (`clip_id`) do catálogo mestre (`get_all_verified_clip_catalog`),
          com `sync_lock=True`, garantindo ZERO repetição de clipes no mesmo vídeo e 100% de encaixe fala↔vídeo!
        - Animações Remotion nível cinema são usadas NO MÁXIMO 3 VEZES no vídeo inteiro (no máximo 1 map_zoom,
          1 character_dossier e 1 data_comparison — nunca repetindo o mesmo template!).
        """
        from composer import FFMPEG_EXE  # noqa: WPS433
        from producao.catalog import get_all_verified_clip_catalog, _score_text_against_tags  # noqa: WPS433

        clip_catalog = get_all_verified_clip_catalog((research_data or {}).get("v5_momentos"))
        used_cids = set()
        used_remotion_types = set()
        flat_blocks = []

        for a_idx, act in enumerate(acts):
            act_num = int(act.get("act_num", a_idx + 1))
            remotion_used_in_act = False
            for b_idx, blk in enumerate(act.get("blocks", [])):
                txt = (blk.get("narration", "") + " " + blk.get("callout", "") + " " + blk.get("headline", "")).lower()
                st = "cinema_broll"

                # Máximo 3 animações Remotion no vídeo inteiro (e no máximo 1 de cada tipo, só quando couber!)
                if not remotion_used_in_act and len(used_remotion_types) < 3:
                    if "map_zoom" not in used_remotion_types and any(
                        k in txt for k in ["mapa", "leonida keys", "grassrivers", "gellhorn", "kalaga", "ambrosia", "arquipélago"]
                    ):
                        st = "map_zoom"
                    elif "character_dossier" not in used_remotion_types and any(
                        k in txt for k in ["lucia", "jason", "protagonista", "casal", "dossiê"]
                    ):
                        st = "character_dossier"
                    elif "data_comparison" not in used_remotion_types and any(
                        k in txt for k in ["compar", "gta 5", "gta v", "evolução", "salto", "recorde"]
                    ):
                        st = "data_comparison"

                    if st != "cinema_broll":
                        remotion_used_in_act = True
                        used_remotion_types.add(st)

                # Trava 1-para-1 do clipe real validado (ZERO repetição + Ato 1 OBRIGATORIAMENTE usa clipes novos live_*!)
                live_cids = {cid for cid, m in clip_catalog.items() if int(m.get("priority", 3)) == 1}
                chosen_cid = blk.get("clip_id") or blk.get("moment_id")
                if chosen_cid and f"live_{chosen_cid}" in clip_catalog:
                    chosen_cid = f"live_{chosen_cid}"

                # No Ato 1 (especialmente blocos iniciais de retenção), se ainda houver clipes live_* disponíveis,
                # PROÍBE usar clipes do acervo estático (garante abertura 100% inédita e aprovada pelo Agente 5!)
                unused_live = live_cids - used_cids
                if a_idx == 0 and unused_live and chosen_cid not in unused_live:
                    chosen_cid = None

                def _rank_candidates(exclude_set, only_live=False):
                    ranked_local = []
                    for cid, meta in clip_catalog.items():
                        if cid in exclude_set:
                            continue
                        prio = int(meta.get("priority", 3))
                        if only_live and prio != 1:
                            continue
                        sc = _score_text_against_tags(txt, meta.get("tags", []))
                        desc_words = {w.strip(".,!?") for w in meta.get("desc", "").lower().split() if len(w) >= 4}
                        txt_words = {w.strip(".,!?") for w in txt.split() if len(w) >= 4}
                        sc += len(desc_words & txt_words) * 5
                        if meta.get("has_audio"):
                            sc += 4
                        if prio == 1:
                            sc += 25
                        elif prio == 2:
                            sc += 4
                        ranked_local.append((sc, cid))
                    ranked_local.sort(key=lambda x: x[0], reverse=True)
                    return ranked_local

                if not (chosen_cid and chosen_cid in clip_catalog and chosen_cid not in used_cids):
                    ranked = _rank_candidates(used_cids, only_live=bool(a_idx == 0 and unused_live))
                    if not ranked:
                        ranked = _rank_candidates(used_cids, only_live=False)
                    if ranked:
                        chosen_cid = ranked[0][1]
                    elif clip_catalog:
                        chosen_cid = list(clip_catalog.keys())[len(flat_blocks) % len(clip_catalog)]

                if chosen_cid and chosen_cid in clip_catalog:
                    used_cids.add(chosen_cid)
                    meta = clip_catalog[chosen_cid]
                    # Anexa 2º clipe de continuação PARA FRENTE relacionado ao tema (evita qualquer reverso se o 1º acabar antes!)
                    backup_cands = _rank_candidates({chosen_cid})
                    vids_for_blk = [meta["path"]]
                    for _, bcid in backup_cands[:3]:
                        bp = clip_catalog[bcid]["path"]
                        if bp != meta["path"] and bp not in vids_for_blk:
                            vids_for_blk.append(bp)
                            if len(vids_for_blk) >= 2:
                                break
                    blk["clip_id"] = chosen_cid
                    blk["video_clips"] = vids_for_blk
                    blk["sync_lock"] = True
                    if not blk.get("location_key") or blk.get("location_key") == "vice_city":
                        blk["location_key"] = meta.get("regiao", "vice_city")

                blk["scene_type"] = st
                blk["act_num"] = act_num
                blk["act_title"] = act.get("act_title", f"ATO {act_num}")
                blk["bgm_mood"] = act.get("bgm_mood", "synth")
                flat_blocks.append(blk)

        semantic_assets = select_semantic_assets(
            flat_blocks,
            prefer_horizontal=(formato == "long"),
            research_data=None,
            ffmpeg_exe=None,
        )
        for blk, asset in zip(flat_blocks, semantic_assets):
            if not blk.get("video_clips"):
                blk["video_clips"] = asset.get("video_clips", [])[:1]
                blk["sync_lock"] = True
            blk["primary_img"] = asset["primary_img"]
            blk["secondary_img"] = asset["secondary_img"]
            blk["asset_subject"] = asset["subject"]
            blk["asset_tags"] = asset["tags"]
        print(f"[DIRETOR V6] {len(flat_blocks)} blocos | {len(used_cids)} clipes ÚNICOS (sync_lock=True) | Remotion={sorted(list(used_remotion_types))}", flush=True)
        return acts


# ============================================================================
# AGENTE 2 — PESQUISADOR E ROTEIRISTA
# ============================================================================
class AgentePesquisadorRoteirista:
    """Pesquisa fontes oficiais/canais de GTA 6 e escreve roteiros naturais com verificação de fonte."""

    CANAIS_MONITORADOS = [
        "Rockstar Games", "Rockstar Games Brasil", "Rockstar Newswire",
        "IGN", "GameSpot", "GTA Series Videos", "TGG", "MrBossFTW",
        "Flow Games", "SanInPlay", "Gigaton Games", "Gameplayrj", "BRKsEDU",
    ]

    @staticmethod
    def gerar_roteiro_longo_verificado(research_data, direcao_criativa, num_acts=5, blocks_per_act=5):
        refs_list = research_data.get("top_references") or research_data.get("top_videos") or []
        refs_txt = "\n".join(
            f"- [{r.get('channel', 'Fonte')}] {r.get('title', '')} ({r.get('views', 0)} views)"
            for r in refs_list[:18]
        )
        news_txt = "\n".join(
            f"- [Notícia] {n.get('title', '')} ({n.get('source', '')})"
            for n in research_data.get("news", [])[:12]
        )
        angle = research_data.get("chosen_angle", "GTA 6 LANÇADO: O MELHOR DAS LIVES DO DAVY JONES E BISTECONE EM VICE CITY")

        from producao.catalog import get_all_verified_clip_catalog  # noqa: WPS433

        clip_catalog = get_all_verified_clip_catalog(research_data.get("v5_momentos"))
        cat_lines = "\n".join(
            f"- clip_id=\"{cid}\" | fonte=\"{meta['channel']}\" | cena_na_tela=\"{meta['desc']}\""
            for cid, meta in list(clip_catalog.items())[:45]
        )

        prompt = f"""Você é o AGENTE 2 (Pesquisador-Chefe e Roteirista) de um canal brasileiro de GTA 6 com edição 100% humanizada e nível cinema.
Contexto: O GTA 6 acabou de ser lançado! Temos abaixo o CATÁLOGO REAL DE CLIPES DE GAMEPLAY DISPONÍVEIS E VALIDADOS EM DISCO (cada um com seu `clip_id` e a descrição exata do que está passando na tela).

PAUTA PRINCIPAL: "{angle}"

CATÁLOGO REAL DE CLIPES DISPONÍVEIS PARA ESTE VÍDEO (USE SOMENTE ESTES `clip_id`s):
{cat_lines}

REFERÊNCIAS RECENTES:
{refs_txt}

REGRAS ABSOLUTAS DE SINCRONIZAÇÃO E QUALIDADE (ZERO TOLERÂNCIA A ERROS):
1. SINCRONIZAÇÃO 1-PARA-1 OBRIGATÓRIA (FALA ↔ IMAGEM):
   - O vídeo terá exatamente {num_acts} Atos com {blocks_per_act} blocos cada (total = {num_acts * blocks_per_act} blocos, resultando em 8m30s a 9m30s).
   - Para CADA bloco, você DEVE escolher **1 `clip_id` ÚNICO** da lista acima (PROIBIDO repetir o mesmo `clip_id` em dois blocos diferentes do vídeo!).
   - A `narration` daquele bloco DEVE falar e comentar **EXATAMENTE SOBRE O QUE ESTÁ NA `cena_na_tela` DAQUELE `clip_id`**!
   - PROIBIDO narrar sobre um assunto (ex: celular ou bug) enquanto o `clip_id` escolhido mostra outra coisa (ex: carro ou praia). O texto tem que casar 100% com a imagem daquele `clip_id`!
2. PROTAGONISTA 100% O JOGO (NÃO REAÇÕES DE STREAMERS):
   - Foque no jogo: novidades, detalhes absurdos, bugs, física, mecânicas, mapa e momentos loucos. Cite o criador apenas de forma natural quando fizer sentido (*"como apareceu na gameplay do..."*).
3. GANCHO FORTE NO ATO 1 BLOCO 1 + CTA NATURAL NO ÚLTIMO BLOCO:
   - Comece direto na cena/descoberta mais impactante (proibido "Olá pessoal").
   - Feche o último bloco com uma pergunta envolvente para comentários e CTA natural de inscrição.
4. ANIMAÇÕES REMOTION APENAS QUANDO COUBER (NO MÁXIMO 3 NO VÍDEO INTEIRO):
   - Use `"scene_type": "cinema_broll"` em ~90% dos blocos (gameplay puro com áudio original).
   - Use `"map_zoom"` (no máximo 1x no vídeo, quando falar de uma região específica do mapa de Leonida), `"character_dossier"` (no máximo 1x no vídeo, quando apresentar Lucia/Jason) e `"data_comparison"` (no máximo 1x no vídeo, quando fizer comparativo GTA V vs GTA VI).
5. TÍTULO DE BUSCA CAUDA LONGA & THUMBNAIL 100% COERENTE (SEM TUDO EM CAIXA ALTA):
   - "long_title": Título natural em português com foco em busca real de lançamento (ex: "10 Segredos e Detalhes ABSURDOS já Encontrados no GTA 6!", "Bugs BIZARROS e Coisas Escondidas no Mapa do GTA 6"). PROIBIDO escrever o título inteiro em MAIÚSCULAS — destaque no máximo 1 ou 2 palavras fortes em MAIÚSCULAS!
   - "thumb_text": 2 a 4 palavras chamativas sobre o tema central do vídeo (ZERO selos "AO VIVO" ou "LIVES").
   - "thumb_subtext": Frase curta complementar sobre o jogo (máx 40 chars).
6. Cada bloco deve ter entre 36 e 54 palavras (~16 a 19 segundos de fala natural em português brasileiro).

Retorne APENAS JSON válido no formato:
{{
  "long_title": "Título magnético focado no jogo (máx 82 chars)",
  "long_description": "Descrição natural com os destaques descobertos no GTA 6",
  "long_tags": ["gta 6", "gta vi", "gta 6 gameplay", "gta 6 segredos", "gta 6 bugs", "gta 6 detalhes", "vice city", "leonida", "rockstar games"],
  "thumb_text": "QUEBRARAM O TABU!",
  "thumb_subtext": "O QUE ACHARAM DENTRO DO GTA 6",
  "acts": [
    {{
      "act_num": 1,
      "act_title": "TÍTULO DO ATO",
      "bgm_mood": "synth",
      "blocks": [
        {{
          "clip_id": "EXATO_CLIP_ID_DA_LISTA_ACIMA",
          "narration": "Texto falado natural em PT-BR descrevendo e comentando EXATAMENTE a cena daquele clip_id...",
          "headline": "TÍTULO DISCRETO DO TÓPICO",
          "subheadline": "Complemento informativo curto",
          "callout": "VICE CITY",
          "scene_type": "cinema_broll",
          "location_key": "vice_city",
          "character_name": "LUCIA & JASON",
          "character_role": "Protagonistas",
          "character_facts": ["Fato 1", "Fato 2"],
          "stat_value": "175 km²",
          "stat_unit": "MAPA DE LEONIDA",
          "comparison_items": [
            {{"label": "GTA V (2013)", "value": 42, "display": "Los Santos"}},
            {{"label": "GTA VI (2026)", "value": 100, "display": "Estado de Leonida"}}
          ]
        }}
      ]
    }}
  ]
}}"""
        data, model_used = gemini_text(prompt, json_mode=True, temperature=0.72)
        data["model_used"] = model_used
        data = AgenteAuditorViral.auditar_e_otimizar_viralizacao(data, formato="long")
        data["acts"] = AgenteDiretorCriativo.enriquecer_storyboard(data.get("acts", []), formato="long", research_data=research_data)
        return data


# ============================================================================
# NARRAÇÃO HUMANA PT-BR + ALINHAMENTO PALAVRA-POR-PALAVRA (FASTER-WHISPER)
# ============================================================================
_WHISPER_MODEL = None


def _get_whisper():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel  # noqa: WPS433
        _WHISPER_MODEL = WhisperModel("tiny", device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def extract_word_timestamps(wav_path, ffmpeg_exe, reference_text=None):
    """
    Alinhamento Forçado Texto-Áudio (V5.1):
    - Usa faster-whisper para detectar o início e fim exatos da fala no WAV (removendo silêncios iniciais/finais)
      e distribui as PALAVRAS EXATAS do roteiro (`reference_text`) com peso silábico/pontuação,
      garantindo 100% de ortografia correta em PT-BR (zero erros em nomes próprios como GTA 6, Leonida, Rockstar!).
    """
    speech_start = 0.05
    speech_end = None
    whisper_words = []
    try:
        r = subprocess.run(
            [ffmpeg_exe, "-i", wav_path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True,
            check=True,
        )
        audio_np = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio_np) >= 800:
            segs, _ = _get_whisper().transcribe(audio_np, language="pt", word_timestamps=True)
            for s in segs:
                for w in s.words or []:
                    clean_w = (w.word or "").strip()
                    if clean_w:
                        whisper_words.append({"w": clean_w, "s": float(w.start), "e": float(w.end)})
            if whisper_words:
                speech_start = max(0.0, whisper_words[0]["s"])
                speech_end = whisper_words[-1]["e"]
    except Exception as err:
        print(f"[WHISPER] Aviso detecção envelope ({err}) -> usando duração do WAV.", flush=True)

    # Se temos o texto exato do roteiro, alinhamos as palavras exatas no envelope real da fala!
    if reference_text and reference_text.strip():
        raw_words = [w.strip() for w in reference_text.split() if w.strip()]
        if raw_words:
            if speech_end is None or speech_end <= speech_start + 0.3:
                from voice_and_avatar import get_audio_duration  # noqa: WPS433

                speech_end = max(speech_start + 1.0, get_audio_duration(wav_path) - 0.12)

            # Peso proporcional ao tamanho da palavra + pausa natural de pontuação (., !, ?, :)
            weights = []
            for w in raw_words:
                base_w = max(2.2, float(len(w.strip(".,!?;:\"'()"))))
                if w.endswith((".", "!", "?")):
                    base_w += 3.8
                elif w.endswith((",", ";", ":")):
                    base_w += 1.8
                weights.append(base_w)

            total_w = sum(weights)
            span = max(0.5, speech_end - speech_start)
            aligned = []
            cursor = speech_start
            for w, wt in zip(raw_words, weights):
                dur_w = span * (wt / total_w)
                aligned.append({"w": w, "s": round(cursor, 2), "e": round(cursor + dur_w, 2)})
                cursor += dur_w
            return aligned

    return [{"w": it["w"], "s": round(it["s"], 2), "e": round(it["e"], 2)} for it in whisper_words]


def synthesize_studio_narration_batch(blocks, work_dir, ffmpeg_exe, voice_name="Orus"):
    """
    ETAPA 7 — Geração da Narração Profissional Padronizada:
    1. Tenta Gemini 3.8 Flash TTS / 2.5 Flash Preview TTS (voz 'Orus' ou 'Charon', avaliada em 10/10 nos testes)
       agrupando por Ato ou bloco com normalização fonética PT-BR e masterização -14.5 LUFS.
    2. Fallback automático: Chatterbox Multilingual PT-BR (GPU T4 Kaggle / ZeroGPU HF) -> Edge-TTS Neural.
    3. Extrai timestamps palavra-por-palavra via faster-whisper para sincronismo de legendas e cortes.
    """
    import base64
    import time
    from voice_and_avatar import (  # noqa: WPS433
        _call_edge_tts,
        _master_voice_wav,
        get_audio_duration,
        normalize_ptbr_phonetics,
    )

    os.makedirs(work_dir, exist_ok=True)
    wav_map = {}
    words_map = {}
    engine_counts = {}
    last_gemini_call_t = 0.0
    gemini_consec_fails = 0
    force_uniform_edge = False

    for idx, blk in enumerate(blocks):
        bid = blk["id"]
        out_wav = os.path.join(work_dir, f"narr_{bid}.wav")
        raw_wav = os.path.join(work_dir, f"raw_{bid}.wav")
        clean_text = normalize_ptbr_phonetics(blk["narration"])

        if not (os.path.exists(out_wav) and os.path.getsize(out_wav) > 15_000):
            ok = False
            # Circuit-breaker anti-429: se cota diária do Gemini TTS estourou (2 falhas seguidas),
            # pula direto para Edge-TTS Neural em 100% dos blocos (evita perder 45 min em retries e evita misturar 2 vozes!)
            if not force_uniform_edge:
                if last_gemini_call_t > 0:
                    elapsed = time.time() - last_gemini_call_t
                    if elapsed < 4.3:
                        time.sleep(4.3 - elapsed)

                # Camada 1: Gemini Flash TTS (voz humana PT-BR 'Orus' 100% consistente)
                try:
                    last_gemini_call_t = time.time()
                    payload = {
                        "contents": [{"parts": [{"text": clean_text}]}],
                        "generationConfig": {
                            "responseModalities": ["AUDIO"],
                            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
                        },
                    }
                    resp = gemini_generate(
                        payload,
                        models=["gemini-2.5-flash-preview-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"],
                        attempts_per_model=2,
                        timeout=75,
                        verbose=False,
                    )
                    pcm_b64 = resp["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
                    pcm_bytes = base64.b64decode(pcm_b64)
                    with wave.open(raw_wav, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(24000)
                        wf.writeframes(pcm_bytes)
                    _master_voice_wav(raw_wav, out_wav)
                    ok = os.path.exists(out_wav) and get_audio_duration(out_wav) > 1.2
                    if ok:
                        gemini_consec_fails = 0
                        m_used = resp.get("_model", "gemini-2.5-flash-preview-tts")
                        engine_counts[m_used] = engine_counts.get(m_used, 0) + 1
                except Exception as e_gem:
                    gemini_consec_fails += 1
                    print(f"[VOICE STUDIO] Aviso Gemini TTS no bloco {bid} ({e_gem}) -> fallback Edge-TTS Neural", flush=True)
                    if gemini_consec_fails >= 2:
                        force_uniform_edge = True
                        print("[VOICE STUDIO] Cota diária Gemini TTS atingida -> padronizando 100% dos blocos em Edge-TTS Neural (voz única e rápida!)", flush=True)

            # Camada 2: Fallback garantido Edge-TTS Neural masterizado
            if not ok:
                mp3_tmp = os.path.join(work_dir, f"tmp_{bid}.mp3")
                _call_edge_tts(clean_text, mp3_tmp, rate="+5%")
                _master_voice_wav(mp3_tmp, out_wav)
                if os.path.exists(mp3_tmp):
                    os.remove(mp3_tmp)
                engine_counts["edge_tts"] = engine_counts.get("edge_tts", 0) + 1

            if os.path.exists(raw_wav):
                try:
                    os.remove(raw_wav)
                except OSError:
                    pass

        wav_map[bid] = out_wav
        dur = get_audio_duration(out_wav)
        w_ts = extract_word_timestamps(out_wav, ffmpeg_exe, reference_text=blk["narration"])
        if not w_ts:
            raw_words = blk["narration"].split()
            span = dur / float(max(1, len(raw_words)))
            w_ts = [{"w": w, "s": round(i * span, 2), "e": round((i + 1) * span, 2)} for i, w in enumerate(raw_words)]
        words_map[bid] = w_ts

    # Se caiu em force_uniform_edge no meio e havia poucos blocos anteriores em Gemini, padroniza TODOS em Edge-TTS
    if force_uniform_edge and any(k != "edge_tts" for k in engine_counts):
        print("[VOICE STUDIO] Uniformizando blocos iniciais para Edge-TTS Neural (zero troca de voz no mesmo vídeo!)", flush=True)
        for blk in blocks:
            bid = blk["id"]
            out_wav = wav_map[bid]
            clean_text = normalize_ptbr_phonetics(blk["narration"])
            mp3_tmp = os.path.join(work_dir, f"tmp_uni_{bid}.mp3")
            _call_edge_tts(clean_text, mp3_tmp, rate="+5%")
            _master_voice_wav(mp3_tmp, out_wav)
            if os.path.exists(mp3_tmp):
                os.remove(mp3_tmp)
            dur = get_audio_duration(out_wav)
            words_map[bid] = extract_word_timestamps(out_wav, ffmpeg_exe, reference_text=blk["narration"])
        engine_counts = {"edge_tts_uniform": len(blocks)}

    engine_used = ", ".join(f"{k}:{v}" for k, v in engine_counts.items()) or "gemini-2.5-flash-preview-tts"
    return wav_map, words_map, engine_used


# ============================================================================
# AGENTE 3 — EDITOR AUDIOVISUAL (REMOTION + THREE.JS + B-ROLL REAL 1080P)
# ============================================================================
class AgenteEditorAudiovisual:
    """Renderiza cenas Remotion + Three.js, B-rolls 1080p reais dos trailers da Rockstar e mixagem."""

    STUDIO_DIR = os.path.join(BASE_DIR, "studio")

    @classmethod
    def ensure_remotion_bundle(cls):
        """Gera o bundle Webpack do Remotion uma única vez para renderizar cenas 5x mais rápido."""
        bundle_dir = os.path.join(cls.STUDIO_DIR, "build")
        if os.path.exists(os.path.join(bundle_dir, "index.html")):
            return bundle_dir
        npx_bin = "npx.cmd" if os.name == "nt" else "npx"
        subprocess.run([npx_bin, "remotion", "bundle", "src/index.ts", "--out-dir", "build"], cwd=cls.STUDIO_DIR, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return bundle_dir

    @classmethod
    def render_remotion_motion_scene(cls, props, dur_sec, out_mp4, fps=24):
        """Renderiza uma animação programática completa (Map Zoom, Dossiê, 3D Three.js) via Remotion."""
        import base64

        bundle_dir = cls.ensure_remotion_bundle()
        frames = max(24, int(round(dur_sec * fps)))
        props_copy = dict(props)
        for img_key in ("primaryImageUrl", "secondaryImageUrl"):
            p = props_copy.get(img_key) or ""
            if p and os.path.exists(p) and not p.startswith("data:"):
                b64 = base64.b64encode(open(p, "rb").read()).decode("ascii")
                props_copy[img_key] = f"data:image/jpeg;base64,{b64}"

        props_file = out_mp4 + ".props.json"
        with open(props_file, "w", encoding="utf-8") as f:
            json.dump(props_copy, f, ensure_ascii=False)

        comp_id = "GtaShortOverlay" if props_copy.get("isVertical") else "GtaStudioScene"
        npx_bin = "npx.cmd" if os.name == "nt" else "npx"
        cmd = [
            npx_bin, "remotion", "render", bundle_dir, comp_id, out_mp4,
            f"--props={props_file}", f"--frames=0-{frames - 1}", "--concurrency=4", "--overwrite",
        ]
        r = subprocess.run(cmd, cwd=cls.STUDIO_DIR, capture_output=True, text=True)
        try:
            os.remove(props_file)
        except OSError:
            pass
        if r.returncode != 0 or not os.path.exists(out_mp4):
            raise RuntimeError(f"Remotion falhou ({r.returncode}): {r.stderr[-300:]}")
        return out_mp4


# ============================================================================
# AGENTE 5 — CONTROLE DE QUALIDADE MULTIMODAL V7 (ASSISTE O VÍDEO E BLOQUEIA LIXO!)
# ============================================================================
class AgenteControleQualidade:
    """
    Auditor Real de Controle de Qualidade (V7 — Multimodal Vision + Anti-Reverso + Bloqueio Real):
    - ASSISTE de verdade o vídeo renderizado extraindo 10 frames cronológicos (com foco especial nos segundos 0:00-0:06!)
      e submetendo as imagens reais ao Gemini Vision para auditar abertura, ausência de logo GTA/trailer,
      variação de cenas, qualidade das legendas e retenção de elite.
    - Detecta programaticamente efeito reverso (ping-pong), telas pretas, frames congelados e ausência de áudio.
    - Se reprovar (`approved=False`), o pipeline BLOQUEIA terminantemente o upload no YouTube!
    """

    @staticmethod
    def _extract_audit_frames_b64(video_path, fps, n_frames, formato="long"):
        import base64

        cap = cv2.VideoCapture(video_path)
        dur = n_frames / float(max(1.0, fps))
        if formato in ("long", "pilot"):
            # Frame #1 (0.8s) e #2 (3.5s) inspecionam a abertura; frames #3..#10 cobrem de 10% a 93% do vídeo!
            times = [0.8, 3.5] + [dur * p for p in (0.10, 0.22, 0.34, 0.46, 0.58, 0.70, 0.82, 0.93)]
        else:
            times = [0.5, 2.0, 4.5] + [dur * p for p in (0.20, 0.35, 0.50, 0.65, 0.78, 0.90, 0.96)]

        frames_b64 = []
        raw_small = []
        bad_frames = 0
        for t in times:
            f_idx = max(0, min(n_frames - 1, int(round(t * fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, fr = cap.read()
            if not ret or fr is None:
                bad_frames += 1
                continue
            mean_lum = float(np.mean(fr))
            if mean_lum < 6.0:
                bad_frames += 1
            h, w = fr.shape[:2]
            sc = 512.0 / float(max(h, w))
            sm = cv2.resize(fr, (int(w * sc), int(h * sc)))
            raw_small.append((round(t, 1), sm))
            ok_enc, buf = cv2.imencode(".jpg", sm, [int(cv2.IMWRITE_JPEG_QUALITY), 82])
            if ok_enc:
                frames_b64.append((round(t, 1), base64.b64encode(buf.tobytes()).decode("ascii")))

        # Detector programático de efeito PING-PONG / REVERSO (compara simetria frame[t-d] == frame[t+d])
        reverse_hits = 0
        if n_frames > int(fps * 12):
            probe_times = [dur * p for p in (0.12, 0.25, 0.42, 0.60, 0.78)]
            step_f = max(4, int(round(fps * 0.45)))
            for pt in probe_times:
                c_f = int(round(pt * fps))
                if c_f - step_f < 0 or c_f + step_f >= n_frames:
                    continue
                tri = []
                for idx_p in (c_f - step_f, c_f, c_f + step_f):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, idx_p)
                    r_ok, fr_p = cap.read()
                    if r_ok and fr_p is not None:
                        tri.append(cv2.resize(fr_p, (160, 90)))
                if len(tri) == 3:
                    d_prev_curr = float(np.mean(cv2.absdiff(tri[0], tri[1])))
                    d_prev_next = float(np.mean(cv2.absdiff(tri[0], tri[2])))
                    # Se a cena se mexeu (d_prev_curr > 7) mas voltou a ficar quase idêntica ao frame anterior (d_prev_next < 2.2) -> ping-pong!
                    if d_prev_curr > 7.0 and d_prev_next < 2.2:
                        reverse_hits += 1

        cap.release()
        return frames_b64, bad_frames, reverse_hits

    @staticmethod
    def auditar_producao(video_path, script_data, wav_map=None, words_map=None, music_credits=None, formato="long"):
        checks = {}
        reasons = []
        wav_map = wav_map or {}
        words_map = words_map or {}
        music_credits = music_credits or []

        # 1. Arquivo renderizado existe e tem tamanho íntegro
        min_bytes = 500_000 if formato in ("long", "pilot") else 300_000
        exists = os.path.exists(video_path) and os.path.getsize(video_path) > min_bytes
        checks["render_integro"] = exists
        if not exists:
            reasons.append(f"Arquivo MP4 ausente ou corrompido (<{min_bytes // 1000}KB).")
            return {"approved": False, "score": 0, "checks": checks, "reasons": reasons}

        # 2. Inspeção técnica de resolução, FPS, duração e áudio
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        dur = n_frames / float(max(1.0, fps))
        cap.release()

        expected_w, expected_h = (1920, 1080) if formato in ("long", "pilot") else (1080, 1920)
        checks["enquadramento_resolucao"] = (w == expected_w and h == expected_h)
        if not checks["enquadramento_resolucao"]:
            reasons.append(f"Resolução incorreta: {w}x{h} (esperado {expected_w}x{expected_h}).")

        if formato == "long":
            dur_ok = dur >= 240.0
        elif formato == "pilot":
            dur_ok = dur >= 35.0
        else:
            dur_ok = 14.0 <= dur <= 178.0
        checks["duracao_adequada"] = dur_ok
        if not dur_ok:
            reasons.append(f"Duração fora da faixa para {formato}: {dur:.1f}s.")

        # 3. Extração de 10 frames cronológicos + detector anti-reverso / anti-tela-preta
        frames_b64, bad_frames, reverse_hits = AgenteControleQualidade._extract_audit_frames_b64(
            video_path, fps, n_frames, formato=formato
        )
        checks["sem_telas_pretas_ou_corrompidas"] = bad_frames <= 1
        if not checks["sem_telas_pretas_ou_corrompidas"]:
            reasons.append(f"Detectados {bad_frames} frames pretos/corrompidos na amostragem.")

        checks["sem_efeito_reverso_pingpong"] = reverse_hits == 0
        if not checks["sem_efeito_reverso_pingpong"]:
            reasons.append(f"Detectado possível efeito de vídeo reverso/ping-pong ({reverse_hits} ocorrências).")

        # 4. Verificação de narração (quando aplicável)
        total_words = sum(len(v) for v in words_map.values()) if words_map else 0
        if formato in ("long", "pilot") and words_map:
            checks["narracao_natural_sincronizada"] = total_words >= (60 if formato == "pilot" else 350)
            if not checks["narracao_natural_sincronizada"]:
                reasons.append(f"Narração curta demais ({total_words} palavras alinhadas).")
        else:
            checks["narracao_natural_sincronizada"] = True

        # 5. AUDITORIA VISUAL REAL VIA GEMINI MULTIMODAL VISION (Agente 5 ASSISTINDO o vídeo pronto!)
        vision_report = {}
        if frames_b64:
            title_ref = (
                script_data.get("long_title")
                or script_data.get("yt_title")
                or script_data.get("headline_top")
                or "GTA 6 Gameplay"
            )
            if formato in ("long", "pilot"):
                acts = script_data.get("acts") or []
                first_blk = ((acts[0].get("blocks") or [{}])[0]) if acts else {}
                hook_ref = (first_blk.get("narration") or "")[:240]
            else:
                hook_ref = f"{script_data.get('hook_text', '')} | {script_data.get('interrupt_text', '')} | {script_data.get('outro_text', '')}"[:260]

            ts_labels = ", ".join(f"#{i + 1}={t}s" for i, (t, _) in enumerate(frames_b64))
            parts = [{"inline_data": {"mime_type": "image/jpeg", "data": b64}} for _, b64 in frames_b64]
            vision_prompt = f"""Você é o AGENTE 5 — AUDITOR RIGOROSO DE CONTROLE DE QUALIDADE (YouTube Retenção de Elite).
Você está ASSISTINDO ao vídeo FINAL RENDERIZADO ({formato.upper()}, {dur:.1f}s) antes dele subir no YouTube.
As {len(frames_b64)} imagens anexadas estão em ordem cronológica exata: {ts_labels}.

TÍTULO DO VÍDEO: "{title_ref}"
GANCHO / ROTEIRO DE ABERTURA: "{hook_ref}"

CONTEXTO TEMPORAL OBRIGATÓRIO: Estamos em 19 de Novembro de 2026 — GTA 6 FOI LANÇADO OFICIALMENTE HOJE! NUNCA acuse cenas reais de gameplay/easter eggs/bugs bizarros de GTA 6 de serem "mod de GTA V" ou "clickbait porque GTA 6 não saiu".
ESTILO DE LEGENDA PADRÃO DO CANAL: Nossas legendas estilo CapCut/Broadcast exibem 2 a 3 palavras grandes sincronizadas com a voz por vez (palavra ativa em amarelo). Isso é INTENCIONAL para retenção — NÃO reprove por aparecerem poucas palavras por frame; reprove APENAS se o texto estiver cortado fora da tela, ilegível ou cobrindo o rosto/ação central.

AUDITE RIGOROSAMENTE ESTES 5 CRITÉRIOS VISUAIS (NÃO PASSE PANO — REPROVE SE ESTIVER RUIM!):
1. `abertura_limpa_sem_logo_ou_cartela`: Os frames iniciais (#1 em 0.8s e #2 em 3.5s, que pertencem à mesma cena inicial de gancho) mostram GAMEPLAY REAL em ação?
   - Marque `false` SE aparecer tela de logo gigante "Grand Theft Auto VI", cartela borrada estática de "CAPÍTULO 1", apresentador em tela cheia falando sem gameplay, tela de pré-venda ou trailer velho na abertura!
2. `sem_cenas_repetidas_ou_estaticas`: {"Para SHORT (25-45s), acompanhar uma única cena/corte contínuo de live ou gameplay (ex: 1 momento viral de 20s) é NORMAL e APROVADO — reprove APENAS se a imagem ficar congelada/travada sem ação ou colar takes repetidos de forma quebrada." if formato == "short" else "Nota: #1 (0.8s) e #2 (3.5s) são da mesma tomada inicial de abertura (normal serem da mesma cena). Avalie se entre os frames #2, #3, #4, #5, #6, #7, #8, #9 e #10 há variedade real de cenas/movimento ao longo do vídeo (Nota: diferentes cenas de direção/carros em locais diferentes de GTA 6 fazem parte natural do jogo e SÃO válidas; reprove APENAS se o vídeo ficar congelado na mesma imagem estática)."}
3. `coerencia_visual_com_roteiro`: As cenas exibidas nos frames têm relação real com o tema do título e do gancho (reprove se for clickbait desconexo)?
4. `qualidade_visual_e_legendas`: As legendas estão limpas/legíveis, sem cortes grotescos, sem tarjas artificiais de IA feias no topo ("CONFIRMADO/VERIFICADO"), e o enquadramento está limpo?
5. `potencial_retencao_elite`: Nota rigorosa de 0 a 100 para retenção orgânica no YouTube.

Responda APENAS um objeto JSON:
{{
  "abertura_limpa_sem_logo_ou_cartela": true/false,
  "sem_cenas_repetidas_ou_estaticas": true/false,
  "coerencia_visual_com_roteiro": true/false,
  "qualidade_visual_e_legendas": true/false,
  "potencial_retencao_elite": 0-100,
  "resumo_do_que_viu": "2 frases descrevendo objetivamente o que você viu nos frames",
  "defeitos_criticos": ["liste aqui apenas defeitos graves que exigem refazer o vídeo; deixe [] se estiver aprovado"]
}}"""
            try:
                v_out, v_model = gemini_text(vision_prompt, json_mode=True, temperature=0.15, parts_extra=parts)
                if isinstance(v_out, list):
                    v_out = v_out[0] if (v_out and isinstance(v_out[0], dict)) else {}
                vision_report = v_out or {}
                vision_report["_model"] = v_model

                checks["visao_abertura_limpa"] = bool(vision_report.get("abertura_limpa_sem_logo_ou_cartela", False))
                checks["visao_sem_repeticao"] = bool(vision_report.get("sem_cenas_repetidas_ou_estaticas", False))
                checks["visao_coerencia_roteiro"] = bool(vision_report.get("coerencia_visual_com_roteiro", False))
                checks["visao_qualidade_legendas"] = bool(vision_report.get("qualidade_visual_e_legendas", False))
                ret_score = int(vision_report.get("potencial_retencao_elite", 0) or 0)
                checks["visao_retencao_elite"] = ret_score >= 75

                if not checks["visao_abertura_limpa"]:
                    reasons.append("REPROVADO NA VISÃO: Abertura contém logo GTA VI, cartela estática de capítulo ou trailer velho.")
                if not checks["visao_sem_repeticao"]:
                    reasons.append("REPROVADO NA VISÃO: Cenas repetidas ou estáticas detectadas.")
                if not checks["visao_coerencia_roteiro"]:
                    reasons.append("REPROVADO NA VISÃO: Visual não bate com o título/roteiro.")
                if not checks["visao_qualidade_legendas"]:
                    reasons.append("REPROVADO NA VISÃO: Problema de enquadramento, tarjas artificiais ou legendas ilegíveis.")
                if not checks["visao_retencao_elite"]:
                    reasons.append(f"REPROVADO NA VISÃO: Retenção estimada insuficiente ({ret_score}/100, mínimo 75).")
                for d_crit in (vision_report.get("defeitos_criticos") or []):
                    if str(d_crit).strip():
                        reasons.append(f"DEFEITO CRÍTICO (VISÃO): {str(d_crit).strip()}")

                print(
                    f"[AGENTE 5 — VISÃO REAL ({v_model})] Retenção={ret_score}/100 | "
                    f"AberturaLimpa={checks['visao_abertura_limpa']} | Variado={checks['visao_sem_repeticao']} | "
                    f"Coerente={checks['visao_coerencia_roteiro']} | Visual={checks['visao_qualidade_legendas']} | "
                    f"Viu: {vision_report.get('resumo_do_que_viu', '')}",
                    flush=True,
                )
            except Exception as err_vis:
                print(f"[AGENTE 5 — VISÃO] Falha ao consultar Gemini Vision ({err_vis})", flush=True)
                checks["visao_multimodal_disponivel"] = False
                reasons.append(f"Auditoria visual indisponível ({err_vis}) — bloqueando publicação por segurança.")

        passed = sum(1 for v in checks.values() if v)
        tech_score = round(100.0 * passed / max(1, len(checks)), 1)
        vis_ret = int(vision_report.get("potencial_retencao_elite", tech_score) or tech_score)
        final_score = round((tech_score * 0.5) + (vis_ret * 0.5), 1)
        approved = len(reasons) == 0 and final_score >= 78.0

        return {
            "approved": approved,
            "score": final_score,
            "duration_sec": round(dur, 2),
            "resolution": f"{w}x{h}",
            "total_words_aligned": total_words,
            "music_credits": music_credits,
            "vision_report": vision_report,
            "checks": checks,
            "reasons": reasons,
        }


# ============================================================================
# AGENTE 7 — AUDITOR DE VIRALIZAÇÃO (GARANTIA >= 80% DE CHANCE DE VIRALIZAR)
# ============================================================================
class AgenteAuditorViral:
    """
    Audita e otimiza automaticamente Roteiro, Gancho 0-3s, Título, Tags e Thumbnail
    para garantir no mínimo 80% (80/100) de pontuação técnica de viralização antes de renderizar.
    """

    VIRAL_TRIGGERS = (
        "davy jones", "bistecone", "gameplayrj", "saninplay", "flow games", "alanzoka",
        "ao vivo", "live", "choque", "travou", "segredo", "celular", "missão", "missao",
        "polícia", "policia", "física", "fisica", "vice city", "lucia", "jason", "gta 6", "gta vi",
    )

    MANDATORY_TAGS = [
        "gta 6", "gta vi", "gta 6 gameplay", "davy jones gta 6", "bistecone gta 6",
        "gameplayrj gta 6", "gta 6 ao vivo", "gta 6 inicio", "vice city", "leonida",
        "lucia e jason", "saninplay gta 6", "flow games gta 6", "gta 6 ps5 pro", "cortes gta 6",
    ]

    @classmethod
    def calcular_score_viral(cls, script_data, formato="short"):
        if formato == "short":
            title = (script_data.get("yt_title") or "").strip()
            hook = (script_data.get("hook_text") or "").strip()
            thumb_h = (script_data.get("headline_top") or "").strip()
            outro = (script_data.get("outro_text") or "").strip()
            tags = list(script_data.get("yt_tags") or [])
        else:
            title = (script_data.get("long_title") or "").strip()
            acts = script_data.get("acts") or []
            first_blk = ((acts[0].get("blocks") or [{}])[0]) if acts else {}
            hook = (first_blk.get("narration") or "").strip()
            thumb_h = (script_data.get("thumb_text") or "").strip()
            last_act = acts[-1] if acts else {}
            last_blk = ((last_act.get("blocks") or [{}])[-1]) if last_act else {}
            outro = (last_blk.get("narration") or "").strip()
            tags = list(script_data.get("long_tags") or [])

        combined_low = f"{title} {hook} {thumb_h}".lower()

        # Pilar 1: Gancho 0-3s Ultra Apelativo (0 a 22 pts)
        p1 = 12
        if len(hook.split()) >= 5 and any(k in hook.lower() for k in cls.VIRAL_TRIGGERS):
            p1 += 6
        if not hook.lower().startswith(("olá", "oi ", "sejam bem", "neste vídeo")):
            p1 += 4

        # Pilar 2: Trend-Jacking de Lives & Criadores (Davy Jones, Bistecone, GTA 6 Launch) (0 a 20 pts)
        hits = sum(1 for k in cls.VIRAL_TRIGGERS if k in combined_low)
        p2 = min(20, 8 + hits * 3)

        # Pilar 3: Título de Alto CTR & SEO Velocity (0 a 20 pts)
        p3 = 10
        if 35 <= len(title) <= 88 and ("gta 6" in title.lower() or "gta vi" in title.lower()):
            p3 += 6
        if any(c in title for c in ("!", "?", "🔴", "🤯", "🚨")) or any(w.isupper() and len(w) >= 3 for w in title.split()):
            p3 += 4

        # Pilar 4: Thumbnail / Headline de Impacto Rápido (2 a 4 palavras) (0 a 18 pts)
        w_th = len(thumb_h.split())
        p4 = 18 if (1 <= w_th <= 5 and len(thumb_h) <= 28) else 11

        # Pilar 5: Densidade de Tags & Gatilho de Comentários (0 a 20 pts)
        p5 = 10
        if len(tags) >= 10:
            p5 += 5
        if "?" in outro or any(w in outro.lower() for w in ("comenta", "acha", "nota", "jogar", "qual")):
            p5 += 5

        total = min(100, p1 + p2 + p3 + p4 + p5)
        return total, {
            "hook_power": p1,
            "live_trend_jacking": p2,
            "title_ctr": p3,
            "thumb_impact": p4,
            "tags_and_engagement": p5,
        }

    @classmethod
    def auditar_e_otimizar_viralizacao(cls, script_data, formato="short"):
        # 1. Enriquece tags obrigatórias de alto volume
        tag_key = "yt_tags" if formato == "short" else "long_tags"
        curr_tags = list(script_data.get(tag_key) or [])
        seen_t = {t.lower() for t in curr_tags}
        for mt in cls.MANDATORY_TAGS:
            if mt.lower() not in seen_t:
                curr_tags.append(mt)
                seen_t.add(mt.lower())
        script_data[tag_key] = curr_tags[:18]

        score, breakdown = cls.calcular_score_viral(script_data, formato=formato)

        # 2. Se score < 80, aplica reforço cirúrgico natural (focado no jogo, SEM caixa alta inteira e SEM 'AO VIVO')
        if score < 80:
            if formato == "short":
                t = (script_data.get("yt_title") or "Detalhe absurdo no GTA 6!").strip()
                if "gta 6" not in t.lower() and "gta vi" not in t.lower():
                    t = f"{t} no GTA 6"
                if "#gta6" not in t.lower():
                    t = f"{t} #gta6 #shorts"
                script_data["yt_title"] = t[:95]

                ht = (script_data.get("headline_top") or "").strip()
                if not ht or len(ht.split()) > 5:
                    script_data["headline_top"] = "OLHA ESSE DETALHE!"
                hk = (script_data.get("hook_text") or "").strip()
                if not any(k in hk.lower() for k in cls.VIRAL_TRIGGERS):
                    script_data["hook_text"] = f"Olha o que descobriram no GTA 6: {hk}"
                ot = (script_data.get("outro_text") or "").strip()
                if "?" not in ot:
                    script_data["outro_text"] = f"{ot} Qual nota você dá pra isso?"
            else:
                t = (script_data.get("long_title") or "Segredos e detalhes ABSURDOS encontrados no GTA 6!").strip()
                if "gta 6" not in t.lower() and "gta vi" not in t.lower():
                    t = f"{t} no GTA 6"
                script_data["long_title"] = t[:86]
                th = (script_data.get("thumb_text") or "").strip()
                if not th or len(th.split()) > 4:
                    script_data["thumb_text"] = "SEGREDO ABSURDO!"
                if not script_data.get("thumb_subtext"):
                    script_data["thumb_subtext"] = "O QUE ACHARAM DENTRO DO GTA 6"

            score, breakdown = cls.calcular_score_viral(script_data, formato=formato)

        script_data["viral_audit"] = {
            "approved": score >= 80,
            "viral_score": score,
            "target_minimum": 80,
            "breakdown": breakdown,
        }
        print(f"[AUDITOR VIRAL V3] Formato={formato.upper()} | Score={score}% (Mínimo=80%) | Pilares={breakdown}", flush=True)
        return script_data


# ============================================================================
# AGENTE 6 — ANALISTA DE DESEMPENHO (YOUTUBE DATA & ANALYTICS)
# ============================================================================
class AgenteAnalistaDesempenho:
    """Analisa os vídeos reais do canal e gera recomendações práticas para os Agentes 1 e 2."""

    @staticmethod
    def diagnosticar_canal_atual():
        import requests
        import uploader  # noqa: WPS433

        tok = uploader.get_youtube_access_token(1)
        yh = {"Authorization": f"Bearer {tok}"}
        ch = requests.get(
            "https://www.googleapis.com/youtube/v3/channels?part=contentDetails,statistics&mine=true",
            headers=yh,
            timeout=12,
        ).json()["items"][0]
        pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        items = requests.get(
            f"https://www.googleapis.com/youtube/v3/playlistItems?part=contentDetails&playlistId={pl}&maxResults=15",
            headers=yh,
            timeout=12,
        ).json().get("items", [])
        ids = ",".join(i["contentDetails"]["videoId"] for i in items)
        vids = requests.get(
            f"https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics,contentDetails&id={ids}",
            headers=yh,
            timeout=12,
        ).json().get("items", [])

        shorts, longs = [], []
        for v in vids:
            entry = {
                "id": v["id"],
                "title": v["snippet"]["title"],
                "publishedAt": v["snippet"]["publishedAt"],
                "duration": v["contentDetails"]["duration"],
                "views": int(v["statistics"].get("viewCount", 0)),
                "likes": int(v["statistics"].get("likeCount", 0)),
                "comments": int(v["statistics"].get("commentCount", 0)),
            }
            if "M" in entry["duration"] and "PT1M" not in entry["duration"]:
                longs.append(entry)
            else:
                shorts.append(entry)

        return {
            "channel_stats": ch["statistics"],
            "recent_shorts": shorts,
            "recent_longs": longs,
            "insights_acionaveis": [
                "Shorts sobre mecânicas específicas (Física de Carros Eh3FLu1I6E8 = 746 views; Lucia & Jason WHYkbc3I3zo = 440 views; IA da Polícia 3H_Kz4FO0Jg = 348 views) têm tração orgânica imediata no feed.",
                "Vídeos longos antigos usavam vídeos de máscara/sticker preto-e-branco de rockstargames.com/VI como B-roll, derrubando a retenção inicial; o novo motor substitui 100% por cenas reais 1080p de trailers + Remotion 3D/Mapas.",
                "Títulos com números concretos ou contraste direto ('GTA V vs GTA VI', '6 Regiões de Leonida', '19 de Novembro') elevam CTR em busca.",
            ],
        }
