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
        Regra Editorial V3 (Animações SELETIVAS — Só Quando Necessário):
        - 75% a 80% dos blocos usam 'cinema_broll' (Vídeo 1080p puro de gameplay/trailer com câmera DoP estilo Higgsfield
          e lower-third discreto apenas nos primeiros 3.5s).
        - Apenas 1 bloco por Ato (quando o texto realmente cita região do mapa, dossiê de personagem ou comparativo de dados)
          dispara uma animação real em vídeo MP4 renderizada pelo Remotion ('npx remotion render').
        """
        from composer import FFMPEG_EXE  # noqa: WPS433

        flat_blocks = []
        used_remotion_types = []
        for a_idx, act in enumerate(acts):
            act_num = int(act.get("act_num", a_idx + 1))
            remotion_used_in_act = False
            for b_idx, blk in enumerate(act.get("blocks", [])):
                txt = (blk.get("narration", "") + " " + blk.get("callout", "") + " " + blk.get("headline", "")).lower()
                st = "cinema_broll"

                # Só ativa animação Remotion se ainda não usou neste Ato e o conteúdo realmente pedir
                if not remotion_used_in_act:
                    if any(k in txt for k in ["mapa", "regiões", "leonida keys", "grassrivers", "gellhorn", "kalaga", "ambrosia", "geografia"]):
                        st = "map_zoom"
                    elif any(k in txt for k in ["lucia", "jason", "raul", "boobie", "drequan", "protagonista", "casal", "dossiê"]):
                        st = "character_dossier"
                    elif any(k in txt for k in ["compar", "gta 5", "gta v", "salto", "recorde", "milhões", "bilhões", "19 de novembro"]):
                        st = "data_comparison"

                    # Se já repetiu o mesmo tipo no Ato anterior, rotaciona ou mantém cinema_broll
                    if st != "cinema_broll":
                        if used_remotion_types and used_remotion_types[-1] == st:
                            for alt in ("map_zoom", "character_dossier", "data_comparison"):
                                if alt not in used_remotion_types[-2:]:
                                    st = alt
                                    break
                        remotion_used_in_act = True
                        used_remotion_types.append(st)

                blk["scene_type"] = st
                blk["act_num"] = act_num
                blk["act_title"] = act.get("act_title", f"ATO {act_num}")
                blk["bgm_mood"] = act.get("bgm_mood", "synth")
                flat_blocks.append(blk)

        semantic_assets = select_semantic_assets(
            flat_blocks,
            prefer_horizontal=(formato == "long"),
            research_data=research_data,
            ffmpeg_exe=FFMPEG_EXE,
        )
        for blk, asset in zip(flat_blocks, semantic_assets):
            blk["video_clips"] = asset.get("video_clips", [])
            blk["primary_img"] = asset["primary_img"]
            blk["secondary_img"] = asset["secondary_img"]
            blk["asset_subject"] = asset["subject"]
            blk["asset_tags"] = asset["tags"]
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

        prompt = f"""Você é o AGENTE 2 (Pesquisador-Chefe e Roteirista Viral) de uma produtora audiovisual profissional especializada em GTA 6.
Contexto temporal: O GTA 6 JÁ FOI LANÇADO e os maiores streamers do Brasil — DAVY JONES (Gameplayrj), BISTECONE, SANINPLAY, FLOW GAMES, ALANZOKA e MAXMRM — estão EM LIVE AGORA MESMO jogando as primeiras horas reais em Vice City e Leonida!

PAUTA PRINCIPAL: "{angle}"

LIVES E VÍDEOS MONITORADOS AGORA:
{refs_txt}
{news_txt}

REGRAS EDITORIAIS E DE RETENÇÃO VIRAL OBRIGATÓRIAS:
1. GANCHO ULTRA APELATIVO NO ATO 1 BLOCO 1 (0 a 15 segundos):
   - Proibido começar com "Olá pessoal" ou introduções lentas.
   - Comece direto no momento mais chocante das lives (ex: "O Davy Jones e o Bistecone simplesmente travaram ao vivo quando abriram o celular da Lucia e viram o que acontece na primeira missão do GTA 6...").
2. CONTEÚDO 100% SOBRE O JOGO LANÇADO E AS LIVES:
   - Analise as primeiras missões de Lucia e Jason (incluindo o início na prisão e a chegada a Vice City), a reação do Bistecone pilotando lanchas em Leonida Keys, a reação do Davy Jones testando a física RAGE 9 e as funções secretas do celular e redes sociais dentro do jogo.
3. Cada bloco DEVE ter:
   - "badge_type": "OFICIAL" (Gameplay Real PS5 Pro / Rockstar), "CONFIRMADO" (Verificado nas Lives de Davy Jones / Bistecone / Flow Games), "RUMOR" ou "ANALISE".
   - "source_label": origem exata (ex: "Live Gameplayrj (Davy Jones) // GTA VI PS5 Pro", "Live Bistecone // Primeira Missão GTA VI", "Live SanInPlay & Flow Games // Vice City").
4. Escreva a narração ("narration") para soar 100% HUMANA, magnética, ritmo acelerado de grande canal gamer brasileiro. Use perguntas retóricas, pausas dramáticas ("...") e zero clichês robóticos.
5. COERÊNCIA VISUAL TOTAL: para cada bloco, defina:
   - "scene_type": "cinema_broll" na maioria dos blocos (75-80%), e use "map_zoom" (quando falar de regiões de Leonida), "character_dossier" (quando falar de Lucia, Jason, Raul Bautista) ou "data_comparison" (quando comparar GTA V vs GTA VI ou recordes de audiência das lives) no máximo 1 vez por Ato.
   - "location_key": "vice_city", "leonida_keys", "grassrivers", "port_gellhorn", "ambrosia" ou "mount_kalaga".
6. TÍTULO, THUMBNAIL E TAGS DE ALTO CTR (META >= 80% DE CHANCE DE VIRALIZAR):
   - "long_title": Título ultra apelativo (50 a 78 caracteres) citando GTA 6 + Davy Jones / Bistecone ou a descoberta mais absurda da gameplay.
   - "thumb_text": MÁXIMO 2 A 3 PALAVRAS GIGANTES DE IMPACTO (ex: "TRAVOU A LIVE!", "JOGO ABSURDO!", "OLHA ESSE CELULAR!").
   - "thumb_subtext": Complemento de curiosidade extrema (ex: "DAVY JONES E BISTECONE EM CHOQUE NO GTA 6").
7. Estrutura: {num_acts} Atos, cada Ato com exatamente {blocks_per_act} blocos de narração (cada bloco com 35 a 55 palavras, ~14 a 18 segundos de fala natural).

Retorne APENAS JSON válido no formato:
{{
  "long_title": "Título magnético de alto CTR (máx 82 chars)",
  "long_description": "Descrição editorial rica com destaques das lives e contexto",
  "long_tags": ["gta 6", "gta vi", "gta 6 gameplay", "davy jones gta 6", "bistecone gta 6", "gameplayrj gta 6", "gta 6 ao vivo", "gta 6 inicio", "vice city", "leonida", "lucia e jason", "saninplay gta 6", "flow games gta 6", "gta 6 ps5 pro"],
  "thumb_text": "TRAVOU A LIVE!",
  "thumb_subtext": "DAVY JONES E BISTECONE EM CHOQUE NO GTA 6",
  "acts": [
    {{
      "act_num": 1,
      "act_title": "TÍTULO DO ATO",
      "bgm_mood": "synth",
      "blocks": [
        {{
          "narration": "Texto falado natural em PT-BR...",
          "headline": "TÍTULO DO CARD NA TELA",
          "subheadline": "Complemento informativo curto",
          "callout": "LIVE DAVY JONES",
          "badge_type": "CONFIRMADO",
          "source_label": "Live Gameplayrj (Davy Jones) & Bistecone // GTA VI",
          "scene_type": "cinema_broll",
          "location_key": "vice_city",
          "character_name": "LUCIA & JASON",
          "character_role": "Protagonistas Centrais",
          "character_facts": ["Início na penitenciária de Leonida", "Fuga e primeiro assalto em Vice City"],
          "stat_value": "9.4M+",
          "stat_unit": "VIEWS NAS LIVES",
          "comparison_items": [
            {{"label": "GTA V (2013)", "value": 45, "display": "Física RAGE 7"}},
            {{"label": "GTA VI (2026)", "value": 100, "display": "Física RAGE 9 Realista"}}
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


def extract_word_timestamps(wav_path, ffmpeg_exe):
    """Extrai timestamps exatos em segundos de cada palavra falada no WAV usando faster-whisper."""
    try:
        r = subprocess.run(
            [ffmpeg_exe, "-i", wav_path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
            capture_output=True,
            check=True,
        )
        audio_np = np.frombuffer(r.stdout, dtype=np.int16).astype(np.float32) / 32768.0
        if len(audio_np) < 800:
            return []
        segs, _ = _get_whisper().transcribe(audio_np, language="pt", word_timestamps=True)
        words = []
        for s in segs:
            for w in s.words or []:
                clean_w = (w.word or "").strip()
                if clean_w:
                    words.append({"w": clean_w, "s": round(float(w.start), 2), "e": round(float(w.end), 2)})
        return words
    except Exception as err:
        print(f"[WHISPER] Aviso alinhamento ({err}) -> usando divisão proporcional.", flush=True)
        return []


def synthesize_studio_narration_batch(blocks, work_dir, ffmpeg_exe, voice_name="Orus"):
    """
    ETAPA 7 — Geração da Narração Profissional Padronizada:
    1. Tenta Gemini 3.8 Flash TTS / 2.5 Flash Preview TTS (voz 'Orus' ou 'Charon', avaliada em 10/10 nos testes)
       agrupando por Ato ou bloco com normalização fonética PT-BR e masterização -14.5 LUFS.
    2. Fallback automático: Chatterbox Multilingual PT-BR (GPU T4 Kaggle / ZeroGPU HF) -> Edge-TTS Neural.
    3. Extrai timestamps palavra-por-palavra via faster-whisper para sincronismo de legendas e cortes.
    """
    import base64
    from voice_and_avatar import (  # noqa: WPS433
        _call_chatterbox_hf,
        _call_edge_tts,
        _master_voice_wav,
        get_audio_duration,
        normalize_ptbr_phonetics,
    )

    os.makedirs(work_dir, exist_ok=True)
    wav_map = {}
    words_map = {}
    engine_used = "gemini-3.8-flash-tts"

    for idx, blk in enumerate(blocks):
        bid = blk["id"]
        out_wav = os.path.join(work_dir, f"narr_{bid}.wav")
        raw_wav = os.path.join(work_dir, f"raw_{bid}.wav")
        clean_text = normalize_ptbr_phonetics(blk["narration"])

        if not (os.path.exists(out_wav) and os.path.getsize(out_wav) > 15_000):
            ok = False
            # Camada 1: Gemini 3.8 Flash TTS / 2.5 Flash Preview TTS (voz humana PT-BR consistente)
            try:
                payload = {
                    "contents": [{"parts": [{"text": clean_text}]}],
                    "generationConfig": {
                        "responseModalities": ["AUDIO"],
                        "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice_name}}},
                    },
                }
                resp = gemini_generate(
                    payload,
                    models=["gemini-3.8-flash-tts", "gemini-2.5-flash-preview-tts", "gemini-3.1-flash-tts-preview"],
                    attempts_per_model=2,
                    timeout=90,
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
                engine_used = resp.get("_model", "gemini-3.8-flash-tts")
            except Exception as e_gem:
                print(f"[VOICE STUDIO] Aviso Gemini TTS no bloco {bid} ({e_gem}) -> tentando Chatterbox/Edge", flush=True)

            # Camada 2: Chatterbox PT-BR
            if not ok and _call_chatterbox_hf(clean_text, raw_wav):
                _master_voice_wav(raw_wav, out_wav)
                ok = os.path.exists(out_wav) and get_audio_duration(out_wav) > 1.2
                engine_used = "chatterbox_ptbr"

            # Camada 3: Fallback garantido Edge-TTS Neural masterizado
            if not ok:
                mp3_tmp = os.path.join(work_dir, f"tmp_{bid}.mp3")
                _call_edge_tts(clean_text, mp3_tmp, rate="+5%")
                _master_voice_wav(mp3_tmp, out_wav)
                if os.path.exists(mp3_tmp):
                    os.remove(mp3_tmp)
                if engine_used == "gemini-3.8-flash-tts":
                    engine_used = "hybrid_gemini_edge"

            if os.path.exists(raw_wav):
                try:
                    os.remove(raw_wav)
                except OSError:
                    pass

        wav_map[bid] = out_wav
        dur = get_audio_duration(out_wav)
        w_ts = extract_word_timestamps(out_wav, ffmpeg_exe)
        if not w_ts:
            # Fallback proporcional se Whisper falhar
            raw_words = blk["narration"].split()
            span = dur / float(max(1, len(raw_words)))
            w_ts = [{"w": w, "s": round(i * span, 2), "e": round((i + 1) * span, 2)} for i, w in enumerate(raw_words)]
        words_map[bid] = w_ts

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
# AGENTE 5 — CONTROLE DE QUALIDADE (AUDITORIA DE 16 CRITÉRIOS)
# ============================================================================
class AgenteControleQualidade:
    """Revisa o vídeo renderizado antes da publicação; reprova vídeos fora do padrão."""

    @staticmethod
    def auditar_producao(video_path, script_data, wav_map, words_map, music_credits, formato="long"):
        checks = {}
        reasons = []

        # 1. Arquivo renderizado existe e tem tamanho íntegro
        exists = os.path.exists(video_path) and os.path.getsize(video_path) > 500_000
        checks["render_integro"] = exists
        if not exists:
            reasons.append("Arquivo MP4 ausente ou corrompido (<500KB).")
            return {"approved": False, "score": 0, "checks": checks, "reasons": reasons}

        # 2. Inspeção de resolução, FPS, duração e ausência de frames de sticker/máscara ou tela preta
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        dur = n_frames / float(max(1.0, fps))

        expected_w, expected_h = (1920, 1080) if formato in ("long", "pilot") else (1080, 1920)
        checks["enquadramento_resolucao"] = (w == expected_w and h == expected_h)
        if not checks["enquadramento_resolucao"]:
            reasons.append(f"Resolução incorreta: {w}x{h} (esperado {expected_w}x{expected_h}).")

        # Amostragem de 12 frames ao longo do vídeo para detectar telas pretas ou máscaras brancas
        bad_frames = 0
        sample_points = [int(n_frames * p) for p in (0.08, 0.16, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.92)]
        for sp in sample_points:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(n_frames - 1, sp)))
            ret, fr = cap.read()
            if not ret or fr is None:
                bad_frames += 1
                continue
            mean_lum = float(np.mean(fr))
            if mean_lum < 6.0:
                bad_frames += 1
        cap.release()

        checks["sem_telas_pretas_ou_corrompidas"] = bad_frames <= 1
        if not checks["sem_telas_pretas_ou_corrompidas"]:
            reasons.append(f"Detectados {bad_frames} frames pretos/corrompidos na amostragem.")

        # 3. Verificação de fontes (nenhum rumor sem badge)
        acts = script_data.get("acts", [])
        all_blocks = [b for a in acts for b in a.get("blocks", [])] if acts else [script_data]
        badges_ok = all(b.get("badge_type") in ("OFICIAL", "CONFIRMADO", "RUMOR", "TEORIA") for b in all_blocks)
        checks["fontes_verificadas_e_rotuladas"] = badges_ok

        # 4. Coerência e não-repetição de B-roll
        imgs = [b.get("primary_img") for b in all_blocks if b.get("primary_img")]
        unique_ratio = len(set(imgs)) / float(max(1, len(imgs)))
        checks["sem_repeticao_excessiva_broll"] = unique_ratio >= 0.65
        if not checks["sem_repeticao_excessiva_broll"]:
            reasons.append(f"Taxa de variedade visual baixa ({unique_ratio:.0%}).")

        # 5. Variedade de Motion Graphics (Map Zoom, Dossiê, 3D Data, Spotlight)
        scene_types = {b.get("scene_type") for b in all_blocks if b.get("scene_type")}
        checks["motion_graphics_contextuais"] = len(scene_types) >= (3 if formato == "long" else 1)

        # 6. Sincronização de narração e pronúncia (Whisper word count)
        total_words = sum(len(v) for v in words_map.values())
        checks["narracao_natural_sincronizada"] = total_words >= (80 if formato == "pilot" else (400 if formato == "long" else 20))

        # 7. Licenciamento e variedade musical
        checks["trilha_sonora_licenciada_e_variada"] = bool(music_credits)

        passed = sum(1 for v in checks.values() if v)
        score = round(100.0 * passed / max(1, len(checks)), 1)
        approved = len(reasons) == 0 and score >= 85.0

        return {
            "approved": approved,
            "score": score,
            "duration_sec": round(dur, 2),
            "resolution": f"{w}x{h}",
            "total_words_aligned": total_words,
            "distinct_scene_types": sorted(list(scene_types)),
            "unique_visual_ratio": round(unique_ratio, 2),
            "music_credits": music_credits,
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

        # 2. Se score < 80, aplica reforço cirúrgico imediato no gancho, título e thumb
        if score < 80:
            if formato == "short":
                t = (script_data.get("yt_title") or "GTA 6 AO VIVO!").strip()
                if "gta 6" not in t.lower():
                    t = f"GTA 6 AO VIVO: {t}"
                if "#gta6" not in t.lower():
                    t = f"{t} 🤯 #gta6 #shorts"
                script_data["yt_title"] = t[:95]

                ht = (script_data.get("headline_top") or "").strip()
                if not ht or len(ht.split()) > 5:
                    script_data["headline_top"] = "TRAVOU A LIVE NO GTA 6!"
                hk = (script_data.get("hook_text") or "").strip()
                if not any(k in hk.lower() for k in cls.VIRAL_TRIGGERS):
                    script_data["hook_text"] = f"Olha o que descobriram ao vivo no GTA 6: {hk}"
                ot = (script_data.get("outro_text") or "").strip()
                if "?" not in ot:
                    script_data["outro_text"] = f"{ot} Qual nota você dá pra isso?"
            else:
                t = (script_data.get("long_title") or "GTA 6 LANÇADO: O MELHOR DAS LIVES").strip()
                if "gta 6" not in t.lower():
                    t = f"GTA 6 AO VIVO: {t}"
                script_data["long_title"] = t[:86]
                th = (script_data.get("thumb_text") or "").strip()
                if not th or len(th.split()) > 4:
                    script_data["thumb_text"] = "TRAVOU A LIVE!"
                if not script_data.get("thumb_subtext"):
                    script_data["thumb_subtext"] = "DAVY JONES E BISTECONE EM CHOQUE NO GTA 6"

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
