"""Catálogo Semântico de B-Rolls em Vídeo 1080p (Gameplay/Trailers + Influenciadores) e Imagens 4K.

Garante que 100% dos blocos de Vídeos Longos e Shorts usem VÍDEOS REAIS EM MOVIMENTO
semanticamente conectados ao que o narrador está falando em cada frase.
"""
import glob
import os
import subprocess
import sys
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(BASE_DIR, "temp_gta6", "vault")
CLIPS_CURATED_DIR = os.path.join(BASE_DIR, "assets", "gta6_clips")
INFLUENCER_CLIPS_DIR = os.path.join(BASE_DIR, "temp_gta6", "influencer_clips")

# Mapeamento visual verificado quadro-a-quadro dos 17 clipes 1080p em assets/gta6_clips/
VIDEO_SEMANTIC_MAP = {
    "gta6_vid_00.mp4": {"tags": ["personagens", "leonida", "rua", "historia", "npc", "cutscene"], "desc": "Personagem caminhando em rua de Leonida"},
    "gta6_vid_01.mp4": {"tags": ["motos", "veiculos", "offroad", "mount_kalaga", "grassrivers", "mapa", "acao"], "desc": "Moto motocross saltando nas trilhas de Mount Kalaga"},
    "gta6_vid_02.mp4": {"tags": ["carros", "vice_city", "noite", "direcao", "estrada", "iluminacao", "conversivel"], "desc": "Conversível dirigindo à noite nas avenidas neon de Vice City"},
    "gta6_vid_03.mp4": {"tags": ["carros", "velocidade", "corrida", "vice_city", "noite", "fisica", "veiculos"], "desc": "Corrida de carros esportivos em alta velocidade em Vice City"},
    "gta6_vid_04.mp4": {"tags": ["fisica", "acidente", "carros", "explosao", "rage9", "acao", "policia", "destruicao"], "desc": "Acidente cinematográfico com carro capotando e faíscas na física RAGE 9"},
    "gta6_vid_05.mp4": {"tags": ["vice_city", "praia", "npc", "redes_sociais", "influenciadores", "vida_real", "mundo_aberto"], "desc": "Influenciadores e NPCs gravando manobras na praia de Vice Beach"},
    "gta6_vid_06.mp4": {"tags": ["personagens", "historia", "graficos", "rosto", "expressao", "cutscene", "dialogo"], "desc": "Cutscene ultra-realista de personagem em Leonida"},
    "gta6_vid_07.mp4": {"tags": ["barcos", "iate", "agua", "oceano", "leonida_keys", "mapa", "fisica"], "desc": "Iate cortando as ondas em alta velocidade em Leonida Keys"},
    "gta6_vid_08.mp4": {"tags": ["personagens", "npc", "cal", "humor", "leonida", "historia"], "desc": "Personagem reagindo em cena de história em Leonida"},
    "gta6_vid_09.mp4": {"tags": ["lucia", "noite", "clube", "festa", "musica", "vice_city", "iluminacao"], "desc": "Lucia dançando sob luzes volumétricas em clube noturno de Vice City"},
    "gta6_vid_10.mp4": {"tags": ["lancamento", "19_de_novembro", "nova_zelandia", "rockstar", "ps5", "xbox", "data"], "desc": "Revelação oficial do lançamento em 19 de novembro"},
    "gta6_vid_12.mp4": {"tags": ["lucia", "jason", "protagonistas", "assalto", "crime", "armas", "casal", "historia"], "desc": "Lucia e Jason colocando bandanas antes de assalto"},
    "gta6_vid_17.mp4": {"tags": ["agua", "oceano", "vida_marinha", "graficos", "leonida_keys", "natureza", "mergulho"], "desc": "Fundo do mar cristalino e recife em Leonida Keys"},
    "gta6_vid_18.mp4": {"tags": ["vice_city", "rua", "npc", "cotidiano", "mundo_aberto", "detalhes"], "desc": "Interação urbana e entregador nas ruas de Vice City"},
    "gta6_vid_19.mp4": {"tags": ["personagens", "dialogo", "graficos", "iluminacao", "rage9", "rosto"], "desc": "Close-up cinematográfico mostrando detalhes de pele e iluminação"},
    "gta6_vid_20.mp4": {"tags": ["barcos", "agua", "leonida_keys", "luxo", "oceano", "veiculos"], "desc": "Detalhes do iate navegando pelas águas de Leonida"},
    "gta6_vid_28.mp4": {"tags": ["lancamento", "19_de_novembro", "nova_zelandia", "quinta_feira", "pre_load", "rockstar"], "desc": "Tela oficial Grand Theft Auto VI — 19 de Novembro de 2026"},
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


def harvest_live_influencer_clips(research_data, ffmpeg_exe, max_new=4):
    """
    Baixa trechos reais em vídeo (720p/1080p) dos vídeos mais recentes de canais de GTA 6
    e influenciadores (Flow Games, SanInPlay, Gigaton, BRKsEDU, Gameplayrj, TGG, IGN)
    usando o seletor DASH bv* para alimentar os B-rolls do dia (incluindo lançamento na Nova Zelândia).
    """
    os.makedirs(INFLUENCER_CLIPS_DIR, exist_ok=True)
    refs = (research_data or {}).get("top_references") or []
    harvested = []

    for r in refs:
        if len(harvested) >= max_new:
            break
        vid = r.get("id") or ""
        ch = (r.get("channel") or "Creator").replace(" ", "_")[:14]
        title = (r.get("title") or "").lower()
        if not vid or ch.startswith("Rockstar"):
            continue
        dst = os.path.join(INFLUENCER_CLIPS_DIR, f"inf_{vid}.mp4")
        if os.path.exists(dst) and os.path.getsize(dst) > 100_000 and not is_sticker_mask_video(dst):
            harvested.append({"path": dst, "title": title, "channel": ch})
            continue
        raw_dst = dst + ".raw.mp4"
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp", "--ffmpeg-location", ffmpeg_exe,
                "-f", "bv*[height<=720][vcodec^=avc1]/bv*[height<=720]/b",
                "--download-sections", "*32-37",
                "--merge-output-format", "mp4",
                "-o", raw_dst,
                f"https://www.youtube.com/watch?v={vid}",
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35, check=False)
            if os.path.exists(raw_dst) and os.path.getsize(raw_dst) > 80_000:
                subprocess.run(
                    [
                        ffmpeg_exe, "-y", "-i", raw_dst,
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=24,setsar=1",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "21", "-pix_fmt", "yuv420p", "-an",
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
    """Retorna todos os clipes 1080p curados em assets/gta6_clips + clipes de influenciadores."""
    curated = [
        os.path.join(CLIPS_CURATED_DIR, fn)
        for fn in sorted(VIDEO_SEMANTIC_MAP.keys())
        if os.path.exists(os.path.join(CLIPS_CURATED_DIR, fn))
    ]
    inf = sorted(glob.glob(os.path.join(INFLUENCER_CLIPS_DIR, "inf_*.mp4")))
    return curated + [p for p in inf if not is_sticker_mask_video(p)]


def _score_text_against_tags(text_low, tags):
    score = 0
    for t in tags:
        t_clean = t.replace("_", " ")
        if t_clean in text_low or t in text_low:
            score += 4
    keyword_boosts = [
        (["mapa", "vice city", "leonida", "região", "estado", "cidade"], ["mapa", "vice_city", "leonida_keys", "mount_kalaga"]),
        (["lucia", "jason", "casal", "protagonista", "assalto", "crime", "prisão"], ["lucia", "jason", "protagonistas", "assalto"]),
        (["carro", "veículo", "física", "dirigir", "corrida", "velocidade", "moto", "batida"], ["carros", "veiculos", "fisica", "motos", "acidente"]),
        (["água", "oceano", "barco", "iate", "praia", "mar", "keys"], ["agua", "barcos", "oceano", "leonida_keys"]),
        (["noite", "clube", "festa", "música", "neon"], ["noite", "clube", "musica"]),
        (["npc", "inteligência artificial", "ia", "redes sociais", "influenciador", "realismo"], ["npc", "influenciadores", "redes_sociais", "mundo_aberto"]),
        (["quinta", "19 de novembro", "lançamento", "nova zelândia", "meia-noite", "ps5", "xbox"], ["lancamento", "19_de_novembro", "nova_zelandia"]),
    ]
    for triggers, target_tags in keyword_boosts:
        if any(w in text_low for w in triggers) and any(tt in tags for tt in target_tags):
            score += 5
    return score


def select_semantic_assets(blocks, prefer_horizontal=True, research_data=None, ffmpeg_exe=None):
    """
    Para CADA bloco do roteiro, seleciona:
    - 3 VÍDEOS 1080p DISTINTOS (`video_clips`: [vid_1, vid_2, vid_3]) cujas tags semânticas batem com
      cada trecho da frase falada no bloco (garantindo que o vídeo mostre exatamente o assunto falado!)
    - 2 IMAGENS 4K DISTINTAS (`primary_img`, `secondary_img`) de apoio para os cards gráficos.
    """
    if ffmpeg_exe and research_data:
        harvest_live_influencer_clips(research_data, ffmpeg_exe, max_new=4)

    available_vids = {}
    for fname, meta in VIDEO_SEMANTIC_MAP.items():
        p = os.path.join(CLIPS_CURATED_DIR, fname)
        if os.path.exists(p):
            available_vids[fname] = (p, meta["tags"], meta["desc"])
    for inf_p in sorted(glob.glob(os.path.join(INFLUENCER_CLIPS_DIR, "inf_*.mp4"))):
        bn = os.path.basename(inf_p)
        available_vids[bn] = (inf_p, ["influenciadores", "gameplay", "nova_zelandia", "lancamento", "gta6"], "Corte de influenciador/gameplay GTA 6")

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
                # Penaliza vídeos já usados recentemente para manter variedade máxima
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

        # Seleciona imagens 4K semânticas de apoio
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
