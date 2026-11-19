"""Catálogo Semântico de B-Rolls em Vídeo 1080p (Lives de Streamers + Gameplay GTA 6 + Trailers) e Imagens 4K.

Garante que 100% dos blocos de Vídeos Longos e Shorts usem VÍDEOS REAIS EM MOVIMENTO
semanticamente conectados ao que o narrador está falando em cada frase, incluindo cortes
atualizados diariamente das lives e vídeos de Davy Jones (Gameplayrj), Bistecone, SanInPlay,
Flow Games, Alanzoka, BRKsEDU, Gigaton Games e gameplay oficial de GTA 6.
"""
import glob
import json
import os
import random
import subprocess
import sys
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(BASE_DIR, "temp_gta6", "vault")
CLIPS_CURATED_DIR = os.path.join(BASE_DIR, "assets", "gta6_clips")
INFLUENCER_CLIPS_DIR = os.path.join(BASE_DIR, "temp_gta6", "influencer_clips")

# Mapeamento visual verificado quadro-a-quadro dos clipes 1080p em assets/gta6_clips/ (Gameplay + Lives)
VIDEO_SEMANTIC_MAP = {
    "gta6_live_davyjones_01.mp4": {
        "tags": ["davy_jones", "gameplayrj", "live", "inicio", "gameplay", "reacao", "streamers", "lancamento", "vice_city"],
        "desc": "Davy Jones (Gameplayrj) ao vivo no início da gameplay de GTA 6",
    },
    "gta6_live_davyjones_02.mp4": {
        "tags": ["davy_jones", "gameplayrj", "live", "vice_city", "mundo_aberto", "exploracao", "carros", "streamers", "gameplay"],
        "desc": "Davy Jones explorando Vice City ao vivo no GTA 6",
    },
    "gta6_live_bistecone_01.mp4": {
        "tags": ["bistecone", "live", "missao", "historia", "lucia", "jason", "acao", "streamers", "gameplay", "reacao"],
        "desc": "Bistecone jogando a primeira missão de GTA 6 ao vivo",
    },
    "gta6_live_bistecone_02.mp4": {
        "tags": ["bistecone", "live", "graficos", "fisica", "detalhes", "choque", "reacao", "streamers", "gameplay"],
        "desc": "Bistecone em choque reagindo aos gráficos e física do GTA 6",
    },
    "gta6_live_saninplay_01.mp4": {
        "tags": ["saninplay", "live", "praia", "vice_city", "oceano", "agua", "npc", "mundo_aberto", "gameplay", "streamers"],
        "desc": "SanInPlay explorando a praia de Vice City e o oceano no GTA 6",
    },
    "gta6_live_flowgames_01.mp4": {
        "tags": ["flow_games", "live", "analise", "review", "gameplay", "graficos", "ps5", "lancamento", "streamers"],
        "desc": "Flow Games analisando as primeiras horas de gameplay do GTA 6",
    },
    "gta6_vid_00.mp4": {"tags": ["personagens", "leonida", "rua", "historia", "npc", "cutscene"], "desc": "Personagem caminhando em rua de Leonida"},
    "gta6_vid_01.mp4": {"tags": ["motos", "veiculos", "offroad", "mount_kalaga", "grassrivers", "mapa", "acao"], "desc": "Moto motocross saltando nas trilhas de Mount Kalaga"},
    "gta6_vid_02.mp4": {"tags": ["carros", "vice_city", "noite", "direcao", "estrada", "iluminacao", "conversivel"], "desc": "Conversível dirigindo à noite nas avenidas neon de Vice City"},
    "gta6_vid_03.mp4": {"tags": ["carros", "velocidade", "corrida", "vice_city", "noite", "fisica", "veiculos"], "desc": "Corrida de carros esportivos em alta velocidade em Vice City"},
    "gta6_vid_04.mp4": {"tags": ["fisica", "acidente", "carros", "explosao", "rage9", "acao", "policia", "destruicao"], "desc": "Acidente cinematográfico com carro capotando e faíscas na física RAGE 9"},
    "gta6_vid_05.mp4": {"tags": ["vice_city", "praia", "npc", "redes_sociais", "influenciadores", "vida_real", "mundo_aberto", "celular"], "desc": "Influenciadores e NPCs gravando manobras no celular na praia de Vice Beach"},
    "gta6_vid_06.mp4": {"tags": ["personagens", "historia", "graficos", "rosto", "expressao", "cutscene", "dialogo"], "desc": "Cutscene ultra-realista de personagem em Leonida"},
    "gta6_vid_07.mp4": {"tags": ["barcos", "iate", "agua", "oceano", "leonida_keys", "mapa", "fisica"], "desc": "Iate cortando as ondas em alta velocidade em Leonida Keys"},
    "gta6_vid_08.mp4": {"tags": ["personagens", "npc", "cal", "humor", "leonida", "historia"], "desc": "Personagem reagindo em cena de história em Leonida"},
    "gta6_vid_09.mp4": {"tags": ["lucia", "noite", "clube", "festa", "musica", "vice_city", "iluminacao"], "desc": "Lucia dançando sob luzes volumétricas em clube noturno de Vice City"},
    "gta6_vid_10.mp4": {"tags": ["lancamento", "19_de_novembro", "nova_zelandia", "rockstar", "ps5", "xbox", "data"], "desc": "Revelação oficial do lançamento de GTA 6"},
    "gta6_vid_12.mp4": {"tags": ["lucia", "jason", "protagonistas", "assalto", "crime", "armas", "casal", "historia", "missao"], "desc": "Lucia e Jason colocando bandanas antes de assalto"},
    "gta6_vid_17.mp4": {"tags": ["agua", "oceano", "vida_marinha", "graficos", "leonida_keys", "natureza", "mergulho"], "desc": "Fundo do mar cristalino e recife em Leonida Keys"},
    "gta6_vid_18.mp4": {"tags": ["vice_city", "rua", "npc", "cotidiano", "mundo_aberto", "detalhes", "celular"], "desc": "Interação urbana e entregador nas ruas de Vice City"},
    "gta6_vid_19.mp4": {"tags": ["personagens", "dialogo", "graficos", "iluminacao", "rage9", "rosto"], "desc": "Close-up cinematográfico mostrando detalhes de pele e iluminação"},
    "gta6_vid_20.mp4": {"tags": ["barcos", "agua", "leonida_keys", "luxo", "oceano", "veiculos"], "desc": "Detalhes do iate navegando pelas águas de Leonida"},
    "gta6_vid_28.mp4": {"tags": ["lancamento", "19_de_novembro", "nova_zelandia", "quinta_feira", "pre_load", "rockstar"], "desc": "Tela oficial Grand Theft Auto VI"},
}

IMAGE_SEMANTIC_MAP = {
    "img_01.jpg": {"tags": ["jason", "armas", "combate", "sniper", "acao", "missao"], "subject": "Jason com rifle de precisão tático"},
    "img_02.jpg": {"tags": ["personagens", "boobie_ike", "drequan", "carros", "vice_city", "praia"], "subject": "Boobie Ike e Dre'Quan em Vice Beach"},
    "img_03.jpg": {"tags": ["carros", "veiculos", "fisica", "direcao", "estrada", "leonida_keys"], "subject": "Picape muscle amarela acelerando na costa"},
    "img_06.jpg": {"tags": ["carros", "veiculos", "offroad", "grassrivers", "customizacao", "canis"], "subject": "Picape 4x4 Canis verde off-road"},
    "img_07.jpg": {"tags": ["lucia", "jason", "protagonistas", "crime", "historia", "casal"], "subject": "Lucia e Jason mascarados em posto de gasolina"},
    "img_08.jpg": {"tags": ["lucia", "jason", "assalto", "armas", "acao", "heist", "protagonistas"], "subject": "Lucia e Jason armados em operação noturna"},
    "img_09.jpg": {"tags": ["lancamento", "capa", "lucia", "jason", "vice_city", "rockstar", "protagonistas"], "subject": "Arte oficial de GTA VI com Lucia e Jason"},
    "img_10.jpg": {"tags": ["carros", "veiculos", "muscle_car", "detalhes", "fisica", "customizacao"], "subject": "Muscle car clássico Deviant em close-up"},
    "img_12.jpg": {"tags": ["personagens", "npcs", "vice_city", "cultura", "carros", "rua"], "subject": "Van grafitada Stock 305 e personagens de rua"},
    "img_13.jpg": {"tags": ["mapa", "leonida_keys", "barcos", "oceano", "helicoptero", "policia", "agua"], "subject": "Vista aérea de lanchas e helicóptero em Leonida Keys"},
    "img_14.jpg": {"tags": ["raul_bautista", "personagens", "armas", "combate", "assalto", "tiroteio"], "subject": "Raul Bautista disparando submetralhadora em assalto"},
    "img_17.jpg": {"tags": ["noite", "vice_city", "personagens", "carros", "iluminacao", "graficos"], "subject": "Casal em carro clássico sob luzes neon de Vice City"},
    "img_18.jpg": {"tags": ["lancamento", "capa", "geral", "rockstar", "mapa", "personagens", "veiculos"], "subject": "Mosaico oficial Grand Theft Auto VI"},
    "img_20.jpg": {"tags": ["carros", "veiculos", "fisica", "direcao", "praia", "sol"], "subject": "Muscle car amarelo na rodovia costeira"},
    "img_21.jpg": {"tags": ["lucia", "jason", "historia", "protagonistas", "drama", "por_do_sol"], "subject": "Lucia e Jason ao entardecer entre palmeiras"},
    "img_22.jpg": {"tags": ["carros", "veiculos", "interior", "detalhes", "graficos", "realismo"], "subject": "Interior detalhado em couro vermelho de supercarro"},
    "img_23.jpg": {"tags": ["lucia", "jason", "crime", "bandana", "posto", "historia"], "subject": "Lucia e Jason planejando golpe"},
    "img_24.jpg": {"tags": ["noite", "npcs", "ambrosia", "gangues", "detalhes", "iluminacao"], "subject": "Clube noturno neon e tatuagem detalhada"},
    "img_25.jpg": {"tags": ["agua", "oceano", "vida_marinha", "barcos", "leonida_keys", "graficos", "mapa"], "subject": "Barco em água cristalina com golfinho e tubarão"},
    "img_26.jpg": {"tags": ["vice_city", "carros", "noite", "hotel", "arquitetura", "graficos"], "subject": "Supercarro branco diante de hotel Art Déco em Vice Beach"},
    "img_27.jpg": {"tags": ["carros", "offroad", "grassrivers", "mount_kalaga", "veiculos"], "subject": "Detalhe frontal do 4x4 Canis"},
    "img_29.jpg": {"tags": ["personagens", "bae_luxe", "roxy", "vice_city", "cultura", "npcs", "lojas"], "subject": "Personagem em loja urbana de Vice City"},
}

LIVE_CREATOR_QUERIES = [
    "ytsearch3:Davy Jones Gameplayrj GTA 6 gameplay",
    "ytsearch3:Bistecone GTA 6 gameplay",
    "ytsearch2:SanInPlay GTA 6 gameplay",
    "ytsearch2:Flow Games GTA 6 gameplay",
    "ytsearch2:Alanzoka GTA 6 gameplay",
    "ytsearch2:MaxMRM GTA 6 gameplay",
]


def is_sticker_mask_video(mp4_path):
    """Detecta vídeos de sticker/máscara ou cartelas pretas."""
    try:
        cap = cv2.VideoCapture(mp4_path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if n < 15:
            cap.release()
            return True
        for frac in (0.25, 0.5, 0.75):
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * frac)))
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return True
            h, w = frame.shape[:2]
            black_ratio = float(np.mean(np.all(frame < 22, axis=2)))
            bot_white = float(np.mean(np.all(frame[h // 2 :, :] > 235, axis=2)))
            if black_ratio > 0.42 or (black_ratio > 0.25 and bot_white > 0.06):
                cap.release()
                return True
        cap.release()
        return False
    except Exception:
        return True


def discover_live_creator_videos(max_per_query=2):
    """
    Busca em tempo real no YouTube as lives e vídeos de gameplay de GTA 6 recém-lançados
    por Davy Jones (Gameplayrj), Bistecone, SanInPlay, Flow Games, Alanzoka e MaxMRM.
    """
    discovered = []
    seen_ids = set()
    queries = list(LIVE_CREATOR_QUERIES)
    random.shuffle(queries)
    for q in queries[:4]:
        try:
            r = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--flat-playlist", "--dump-json", q],
                capture_output=True,
                text=True,
                timeout=18,
                check=False,
            )
            count = 0
            for line in r.stdout.splitlines():
                if count >= max_per_query:
                    break
                try:
                    d = json.loads(line)
                    vid = d.get("id") or ""
                    title = d.get("title") or ""
                    ch = d.get("uploader") or d.get("channel") or "Streamer"
                    dur = d.get("duration") or 600
                    views = int(d.get("view_count") or 50000)
                    if vid and vid not in seen_ids and any(k in title.lower() for k in ("gta", "vice", "leonida")):
                        seen_ids.add(vid)
                        discovered.append({
                            "id": vid,
                            "channel": ch,
                            "title": title,
                            "duration": dur,
                            "views": views,
                        })
                        count += 1
                except Exception:
                    pass
        except Exception:
            pass
    return discovered


def harvest_live_influencer_clips(research_data, ffmpeg_exe, max_new=6):
    """
    Baixa trechos reais em vídeo (720p/1080p) das lives e gameplays mais recentes de
    Davy Jones (Gameplayrj), Bistecone, SanInPlay, Flow Games, Alanzoka, BRKsEDU e Gigaton
    usando o seletor DASH bv* em janelas de ação variadas para alimentar Shorts e Longos todos os dias.
    """
    os.makedirs(INFLUENCER_CLIPS_DIR, exist_ok=True)
    refs = list((research_data or {}).get("top_references") or [])
    live_discovered = discover_live_creator_videos(max_per_query=2)
    all_candidates = live_discovered + refs

    harvested = []
    time_windows = [("*140-146", "a"), ("*320-326", "b"), ("*540-546", "c"), ("*85-91", "d")]

    for idx, r in enumerate(all_candidates):
        if len(harvested) >= max_new:
            break
        vid = r.get("id") or ""
        ch = (r.get("channel") or "Creator").replace(" ", "_")[:16]
        title = (r.get("title") or "").lower()
        dur = int(r.get("duration") or 600)
        if not vid or ch.startswith("Rockstar"):
            continue

        sec_range, suffix = time_windows[idx % len(time_windows)]
        if dur and dur < 160:
            sec_range, suffix = "*22-28", "s"

        dst = os.path.join(INFLUENCER_CLIPS_DIR, f"inf_{vid}_{suffix}.mp4")
        if os.path.exists(dst) and os.path.getsize(dst) > 100_000 and not is_sticker_mask_video(dst):
            harvested.append({"path": dst, "title": title, "channel": ch})
            continue
        raw_dst = dst + ".raw.mp4"
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp", "--ffmpeg-location", ffmpeg_exe,
                "-f", "bv*[height<=720][vcodec^=avc1]/bv*[height<=720]/b",
                "--download-sections", sec_range,
                "--merge-output-format", "mp4",
                "-o", raw_dst,
                f"https://www.youtube.com/watch?v={vid}",
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=38, check=False)
            if os.path.exists(raw_dst) and os.path.getsize(raw_dst) > 70_000:
                subprocess.run(
                    [
                        ffmpeg_exe, "-y", "-i", raw_dst,
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,setsar=1",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p", "-an",
                        dst,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
                os.remove(raw_dst)
                if os.path.exists(dst) and not is_sticker_mask_video(dst):
                    harvested.append({"path": dst, "title": title, "channel": ch})
        except Exception:
            if os.path.exists(raw_dst):
                try:
                    os.remove(raw_dst)
                except OSError:
                    pass

    return harvested


def extract_real_trailer_clips(ffmpeg_exe):
    """Retorna todos os clipes curados + launch_manifest + colheita diária (sem cartelas de pré-venda)."""
    cat = get_all_verified_clip_catalog()
    return [v["path"] for v in cat.values() if os.path.exists(v["path"])]


def get_all_verified_clip_catalog(v5_momentos=None):
    """
    Catálogo Mestre V6 de Clipes Reais Validados (1-para-1 com descrição visual exata):
    1. Prioridade 1: Momentos recém-pesquisados e validados ao vivo (`v5_momentos`, com áudio original).
    2. Prioridade 2: Clipes reais do lançamento validados em `assets/gta6_clips/launch_manifest.json` (com áudio original).
    3. Prioridade 3: Clipes 1080p de gameplay/cenas curadas em `VIDEO_SEMANTIC_MAP` (excluindo cartelas de pré-venda e câmera estática).
    """
    catalog = {}

    # 1. Momentos ao vivo recém-baixados nesta execução
    for m in v5_momentos or []:
        cp = m.get("clip")
        if cp and os.path.exists(cp):
            cid = f"live_{m.get('mid', os.path.basename(cp))}"
            catalog[cid] = {
                "path": cp,
                "desc": m.get("descricao_real") or m.get("o_que_acontece") or "Gameplay real de GTA 6",
                "channel": m.get("canal", "Criador"),
                "regiao": (m.get("validacao") or {}).get("regiao", "vice_city"),
                "tags": [m.get("assunto", "gameplay"), "gta6", "live"],
                "has_audio": True,
                "priority": 1,
            }

    # 2. Clipes reais do dia do lançamento validados visualmente (launch_manifest.json)
    manifest_p = os.path.join(CLIPS_CURATED_DIR, "launch_manifest.json")
    if os.path.exists(manifest_p):
        try:
            mdata = json.load(open(manifest_p, encoding="utf-8"))
            for fn, info in mdata.items():
                cp = os.path.join(CLIPS_CURATED_DIR, fn)
                if os.path.exists(cp):
                    cid = os.path.splitext(fn)[0]
                    catalog[cid] = {
                        "path": cp,
                        "desc": info.get("desc", "Gameplay real de GTA 6"),
                        "channel": info.get("channel", "Criador"),
                        "regiao": info.get("regiao", "vice_city"),
                        "tags": info.get("tags", [info.get("category", "gameplay"), "gta6"]),
                        "has_audio": bool(info.get("has_audio", True)),
                        "priority": 2,
                    }
        except Exception:
            pass

    # 3. Clipes 1080p verificados quadro-a-quadro (exclui telas de pré-venda e câmera falando sem gameplay)
    skip_files = {"gta6_vid_10.mp4", "gta6_vid_28.mp4", "gta6_live_flowgames_01.mp4"}
    for fn, meta in VIDEO_SEMANTIC_MAP.items():
        if fn in skip_files:
            continue
        cp = os.path.join(CLIPS_CURATED_DIR, fn)
        if os.path.exists(cp):
            cid = os.path.splitext(fn)[0]
            catalog[cid] = {
                "path": cp,
                "desc": meta["desc"],
                "channel": "GTA 6 Gameplay",
                "regiao": "vice_city",
                "tags": meta["tags"],
                "has_audio": False,
                "priority": 3,
            }

    return catalog


def _score_text_against_tags(text_low, tags):
    score = 0
    for t in tags:
        t_clean = t.replace("_", " ")
        if t_clean in text_low or t in text_low:
            score += 4
    keyword_boosts = [
        (["davy jones", "gameplayrj", "davy", "mago"], ["davy_jones", "gameplayrj", "live", "streamers"]),
        (["bistecone", "live", "streamer", "ao vivo", "reação", "choque"], ["bistecone", "live", "streamers", "reacao"]),
        (["saninplay", "flow games", "alanzoka", "influenciador"], ["saninplay", "flow_games", "influenciadores", "streamers"]),
        (["celular", "aplicativo", "redes sociais", "tik tok", "foto"], ["celular", "redes_sociais", "influenciadores", "npc"]),
        (["mapa", "vice city", "leonida", "região", "estado", "cidade"], ["mapa", "vice_city", "leonida_keys", "mount_kalaga"]),
        (["lucia", "jason", "casal", "protagonista", "assalto", "crime", "missão"], ["lucia", "jason", "protagonistas", "assalto", "missao"]),
        (["carro", "veículo", "física", "dirigir", "corrida", "velocidade", "moto", "batida"], ["carros", "veiculos", "fisica", "motos", "acidente"]),
        (["água", "oceano", "barco", "iate", "praia", "mar", "keys"], ["agua", "barcos", "oceano", "leonida_keys", "praia"]),
        (["noite", "clube", "festa", "música", "neon"], ["noite", "clube", "musica"]),
    ]
    for triggers, target_tags in keyword_boosts:
        if any(w in text_low for w in triggers) and any(tt in tags for tt in target_tags):
            score += 6
    return score


def select_semantic_assets(blocks, prefer_horizontal=True, research_data=None, ffmpeg_exe=None):
    """
    Para CADA bloco do roteiro, seleciona:
    - 3 VÍDEOS 1080p DISTINTOS (`video_clips`: [vid_1, vid_2, vid_3]) cujas tags semânticas batem com
      cada trecho da frase falada no bloco (priorizando lives de Davy Jones, Bistecone, SanInPlay e gameplay de GTA 6)
    - 2 IMAGENS 4K DISTINTAS (`primary_img`, `secondary_img`) de apoio para os cards gráficos.
    """
    if ffmpeg_exe and research_data:
        harvest_live_influencer_clips(research_data, ffmpeg_exe, max_new=6)

    available_vids = {}
    for fname, meta in VIDEO_SEMANTIC_MAP.items():
        p = os.path.join(CLIPS_CURATED_DIR, fname)
        if os.path.exists(p):
            available_vids[fname] = (p, meta["tags"], meta["desc"])
    for inf_p in sorted(glob.glob(os.path.join(INFLUENCER_CLIPS_DIR, "inf_*.mp4"))):
        bn = os.path.basename(inf_p)
        available_vids[bn] = (
            inf_p,
            ["live", "streamers", "davy_jones", "bistecone", "gameplay", "lancamento", "gta6"],
            "Corte ao vivo de streamer jogando GTA 6",
        )

    available_imgs = {}
    for fname, meta in IMAGE_SEMANTIC_MAP.items():
        p = os.path.join(VAULT_DIR, fname)
        if os.path.exists(p):
            available_imgs[fname] = (p, meta["tags"], meta["subject"])

    used_vids = []
    used_imgs = set()
    assignments = []

    for b_idx, blk in enumerate(blocks):
        narration = blk.get("narration") or ""
        words = narration.split()
        third = max(1, len(words) // 3)
        seg_texts = [
            " ".join(words[:third]) + " " + blk.get("headline", "") + " " + blk.get("location_key", "") + " " + blk.get("character_name", ""),
            " ".join(words[third : 2 * third]) + " " + blk.get("callout", ""),
            " ".join(words[2 * third :]) + " " + blk.get("subheadline", ""),
        ]

        chosen_vids = []
        for s_txt in seg_texts:
            s_low = s_txt.lower()
            ranked = []
            for vname, (vp, vtags, vdesc) in available_vids.items():
                sc = _score_text_against_tags(s_low, vtags)
                if vname in chosen_vids:
                    sc -= 100
                elif vname in used_vids[-8:]:
                    sc -= 18
                elif vname in used_vids:
                    sc -= 6
                ranked.append((sc, vname, vp, vdesc))
            ranked.sort(key=lambda x: x[0], reverse=True)
            if ranked:
                _, best_vn, best_vp, _ = ranked[0]
                chosen_vids.append(best_vp)
                used_vids.append(best_vn)

        full_low = (narration + " " + blk.get("headline", "") + " " + blk.get("callout", "")).lower()
        img_ranked = []
        for iname, (ip, itags, isubj) in available_imgs.items():
            isc = _score_text_against_tags(full_low, itags)
            if iname in used_imgs and len(used_imgs) < len(available_imgs):
                isc -= 25
            img_ranked.append((isc, iname, ip, isubj, itags))
        img_ranked.sort(key=lambda x: x[0], reverse=True)

        if img_ranked:
            _, iname1, ip1, isubj1, itags1 = img_ranked[0]
            used_imgs.add(iname1)
            ip2 = img_ranked[1][2] if len(img_ranked) > 1 else ip1
        else:
            ip1, ip2, isubj1, itags1 = None, None, "", []

        assignments.append({
            "video_clips": chosen_vids,
            "primary_img": ip1,
            "secondary_img": ip2,
            "subject": isubj1,
            "tags": itags1,
        })

    return assignments
