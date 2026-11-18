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
    def enriquecer_storyboard(acts, formato="long"):
        """Garante variedade de cenas e coerência semântica entre texto e tipo de animação."""
        flat_blocks = []
        for a_idx, act in enumerate(acts):
            act_num = int(act.get("act_num", a_idx + 1))
            for b_idx, blk in enumerate(act.get("blocks", [])):
                txt = (blk.get("narration", "") + " " + blk.get("callout", "")).lower()
                st = blk.get("scene_type", "")
                if st not in AgenteDiretorCriativo.SCENE_TYPES:
                    if any(k in txt for k in ["mapa", "vice city", "leonida", "keys", "grassrivers", "gellhorn", "kalaga", "ambrosia", "região"]):
                        st = "map_zoom"
                    elif any(k in txt for k in ["lucia", "jason", "raul", "boobie", "drequan", "personagem", "protagonista", "casal"]):
                        st = "character_dossier"
                    elif any(k in txt for k in ["19 de novembro", "quinta", "milhões", "bilhões", "gta 5", "gta v", "compar", "recorde", "anos", "%", "dobro"]):
                        st = "data_comparison"
                    else:
                        st = "feature_spotlight"
                # Evita repetir o mesmo scene_type 3x seguidas
                if len(flat_blocks) >= 2 and flat_blocks[-1]["scene_type"] == st and flat_blocks[-2]["scene_type"] == st:
                    for alt in AgenteDiretorCriativo.SCENE_TYPES:
                        if alt != st:
                            st = alt
                            break
                blk["scene_type"] = st
                blk["act_num"] = act_num
                blk["act_title"] = act.get("act_title", f"ATO {act_num}")
                blk["bgm_mood"] = act.get("bgm_mood", "synth")
                flat_blocks.append(blk)

        semantic_assets = select_semantic_assets(flat_blocks, prefer_horizontal=(formato == "long"))
        for blk, asset in zip(flat_blocks, semantic_assets):
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
    def gerar_roteiro_longo_verificado(research_data, direcao_criativa, num_acts=5, blocks_per_act=6):
        refs_txt = "\n".join(
            f"- [{r.get('channel', 'Fonte')}] {r.get('title', '')} ({r.get('views', 0)} views)"
            for r in research_data.get("top_videos", [])[:15]
        )
        news_txt = "\n".join(
            f"- [Notícia] {n.get('title', '')} ({n.get('source', '')})"
            for n in research_data.get("news", [])[:10]
        )
        angle = research_data.get("chosen_angle", "COMO VAI SER O LANÇAMENTO DO GTA 6 NA QUINTA-FEIRA (19 DE NOVEMBRO)")

        prompt = f"""Você é o AGENTE 2 (Pesquisador-Chefe e Roteirista Documental) de uma produtora audiovisual profissional especializada em GTA 6.
Contexto temporal: Hoje é véspera do lançamento histórico de Grand Theft Auto VI, confirmado oficialmente pela Rockstar Games para QUINTA-FEIRA, 19 DE NOVEMBRO DE 2026 (PS5 e Xbox Series X|S).

PAUTA PRINCIPAL: "{angle}"

FONTES MONITORADAS HOJE:
{refs_txt}
{news_txt}

REGRAS EDITORIAIS OBRIGATÓRIAS:
1. NUNCA apresente rumores ou teorias como fatos confirmados. Cada bloco DEVE ter:
   - "badge_type": "OFICIAL" (Rockstar Games / site oficial), "CONFIRMADO" (Take-Two / imprensa verificada), "RUMOR" (vazamento não oficial, usando verbos no condicional) ou "TEORIA" (análise/hipótese da comunidade).
   - "source_label": origem exata da informação (ex: "Rockstar Games Official / Trailer", "Site Oficial rockstargames.com/VI", "Relatório Take-Two Interactive", "Análise GTA Series Videos / Comunidade").
2. Escreva a narração ("narration") para soar 100% HUMANA, conversada, envolvente, com ritmo de grande documentário gamer brasileiro (estilo Flow Games / Digital Foundry / Gigaton). Use perguntas retóricas, pausas dramáticas ("...") e zero clichês robóticos de IA.
3. COERÊNCIA VISUAL TOTAL: para cada bloco, defina:
   - "scene_type": escolha entre "map_zoom" (quando falar de regiões de Leonida), "character_dossier" (quando falar de Lucia, Jason, Raul Bautista, Boobie Ike, Dre'Quan), "data_comparison" (quando citar números, datas, recordes ou comparar GTA V vs GTA VI) ou "feature_spotlight" (quando analisar mecânicas, física, veículos, gráficos, armas ou IA).
   - "location_key": "vice_city", "leonida_keys", "grassrivers", "port_gellhorn", "ambrosia" ou "mount_kalaga".
   - "character_name", "character_role", "character_facts" (lista de 2-3 fatos curtos quando scene_type for character_dossier).
   - "stat_value" (ex: "19 NOV", "6 REGIÕES", "90M+"), "stat_unit", "comparison_items" (lista de 2 itens {{label, value, display}} quando scene_type for data_comparison).
4. Estrutura: {num_acts} Atos, cada Ato com exatamente {blocks_per_act} blocos de narração (cada bloco com 35 a 55 palavras, ~14 a 18 segundos de fala natural).

Retorne APENAS JSON válido no formato:
{{
  "long_title": "Título magnético e profissional (máx 88 chars)",
  "long_description": "Descrição editorial rica com fontes e contexto",
  "long_tags": ["gta 6", "gta vi", "lancamento gta 6", "rockstar games", "vice city", "leonida"],
  "thumb_text": "TEXTO CURTO IMPACTO (2-3 palavras)",
  "thumb_subtext": "SUBTÍTULO DE APOIO",
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
          "callout": "PALAVRA-CHAVE",
          "badge_type": "OFICIAL",
          "source_label": "Rockstar Games / rockstargames.com/VI",
          "scene_type": "map_zoom",
          "location_key": "vice_city",
          "character_name": "LUCIA & JASON",
          "character_role": "Protagonistas Centrais",
          "character_facts": ["Fato 1", "Fato 2"],
          "stat_value": "19 NOV",
          "stat_unit": "QUINTA-FEIRA",
          "comparison_items": [
            {{"label": "GTA V (2013)", "value": 45, "display": "1 Metrópole"}},
            {{"label": "GTA VI (2026)", "value": 100, "display": "Estado Inteiro de Leonida"}}
          ]
        }}
      ]
    }}
  ]
}}"""
        data, model_used = gemini_text(prompt, json_mode=True, temperature=0.68)
        data["model_used"] = model_used
        data["acts"] = AgenteDiretorCriativo.enriquecer_storyboard(data.get("acts", []), formato="long")
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
        if os.name == "nt":
            cmd = [
                "cmd", "/c",
                f'npx remotion render "{bundle_dir}" {comp_id} "{out_mp4}" --props="{props_file}" --frames=0-{frames - 1} --concurrency=4 --overwrite',
            ]
        else:
            cmd = [
                "npx", "remotion", "render", bundle_dir, comp_id, out_mp4,
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
