"""Catálogo Semântico de B-Rolls Oficiais GTA 6 (Imagens 4K + Cenas Reais de Trailers).

Regra Fundamental do Agente 3 (Editor Audiovisual):
- NUNCA usar os vídeos de máscara/sticker preto-e-branco do site da Rockstar.
- Cada trecho da narração recebe um asset cujo tema semântico bate com o assunto falado
  (mapa/região, veículo, Lucia/Jason, armas/combate, vida noturna, água/Leonida Keys, lançamento).
- Zero repetição de imagens/cenas dentro do mesmo vídeo.
"""
import glob
import os
import subprocess
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VAULT_DIR = os.path.join(BASE_DIR, "temp_gta6", "vault")
TRAILERS_DIR = os.path.join(BASE_DIR, "temp_gta6", "trailers")
CLIPS_DIR = os.path.join(BASE_DIR, "temp_gta6", "real_clips")

# Mapeamento visual verificado quadro a quadro das 30 imagens 4K oficiais de rockstargames.com/VI
IMAGE_SEMANTIC_MAP = {
    "img_01.jpg": {"tags": ["jason", "armas", "combate", "sniper", "acao", "missao"], "subject": "Jason com rifle de precisão tático"},
    "img_02.jpg": {"tags": ["personagens", "boobie_ike", "drequan", "carros", "vice_city", "praia"], "subject": "Boobie Ike e Dre'Quan em Vice Beach"},
    "img_03.jpg": {"tags": ["carros", "veiculos", "fisica", "direcao", "estrada", "leonida_keys"], "subject": "Picape muscle amarela acelerando na costa"},
    "img_04.jpg": {"tags": ["mapa", "vice_city", "port_gellhorn", "cidade", "por_do_sol", "graficos", "vertical"], "subject": "Skyline de Vice City e porto ao pôr do sol"},
    "img_05.jpg": {"tags": ["lucia", "jason", "assalto", "armas", "crime", "protagonistas", "vertical"], "subject": "Lucia e Jason com equipamento tático de assalto"},
    "img_06.jpg": {"tags": ["carros", "veiculos", "offroad", "grassrivers", "customizacao", "canis"], "subject": "Picape 4x4 Canis verde off-road"},
    "img_07.jpg": {"tags": ["lucia", "jason", "protagonistas", "crime", "historia", "casal"], "subject": "Lucia e Jason mascarados em posto de gasolina"},
    "img_08.jpg": {"tags": ["lucia", "jason", "assalto", "armas", "acao", "heist", "protagonistas"], "subject": "Lucia e Jason armados em operação noturna"},
    "img_09.jpg": {"tags": ["lancamento", "capa", "lucia", "jason", "vice_city", "rockstar", "protagonistas"], "subject": "Arte oficial de GTA VI com Lucia e Jason"},
    "img_10.jpg": {"tags": ["carros", "veiculos", "muscle_car", "detalhes", "fisica", "customizacao"], "subject": "Muscle car clássico Deviant em close-up"},
    "img_11.jpg": {"tags": ["vice_city", "cultura", "rua", "arte", "npcs", "detalhes"], "subject": "Arte urbana Stock 305 em Vice City"},
    "img_12.jpg": {"tags": ["personagens", "npcs", "vice_city", "cultura", "carros", "rua"], "subject": "Van grafitada Stock 305 e personagens de rua"},
    "img_13.jpg": {"tags": ["mapa", "leonida_keys", "barcos", "oceano", "helicoptero", "policia", "agua"], "subject": "Vista aérea de lanchas e helicóptero em Leonida Keys"},
    "img_14.jpg": {"tags": ["raul_bautista", "personagens", "armas", "combate", "assalto", "tiroteio"], "subject": "Raul Bautista disparando submetralhadora em assalto"},
    "img_16.jpg": {"tags": ["lucia", "jason", "assalto", "armas", "vertical"], "subject": "Retrato tático de Lucia e Jason"},
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
    """Detecta vídeos de sticker/máscara ou cartelas pretas de classificação indicativa."""
    try:
        cap = cv2.VideoCapture(mp4_path)
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        for frac in (0.25, 0.5, 0.75):
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, int(n * frac)))
            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                return True
            h, w = frame.shape[:2]
            black_ratio = float(np.mean(np.all(frame < 22, axis=2)))
            bot_white = float(np.mean(np.all(frame[h // 2 :, :] > 235, axis=2)))
            if black_ratio > 0.35 or (black_ratio > 0.25 and bot_white > 0.06):
                cap.release()
                return True
        cap.release()
        return False
    except Exception:
        return True


def extract_real_trailer_clips(ffmpeg_exe):
    """Extrai clipes reais 1080p 16:9 dos trailers oficiais da Rockstar (sem tarjas ou máscaras)."""
    os.makedirs(CLIPS_DIR, exist_ok=True)
    existing = sorted(glob.glob(os.path.join(CLIPS_DIR, "clip_*.mp4")))
    if len(existing) >= 8:
        return existing

    # Remove qualquer mp4 de máscara antigo do vault para nunca ser usado por engano
    for old_mp4 in glob.glob(os.path.join(VAULT_DIR, "mp4_*.mp4")):
        if is_sticker_mask_video(old_mp4):
            try:
                os.remove(old_mp4)
            except OSError:
                pass

    sources = sorted(glob.glob(os.path.join(TRAILERS_DIR, "*.mp4")))
    clips = []
    idx = 0
    for src in sources:
        if is_sticker_mask_video(src):
            continue
        cap = cv2.VideoCapture(src)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        dur = n / float(fps)
        cap.release()
        if dur < 6.0:
            continue
        # Corta janelas limpas do miolo do trailer (ignorando tela preta inicial/final)
        start_t = 1.5
        while start_t + 4.5 < dur - 2.0 and idx < 20:
            out_c = os.path.join(CLIPS_DIR, f"clip_{idx:02d}.mp4")
            if not os.path.exists(out_c):
                subprocess.run(
                    [
                        ffmpeg_exe, "-y", "-ss", f"{start_t:.2f}", "-t", "4.50", "-i", src,
                        "-vf", "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,setsar=1",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p", "-an",
                        out_c,
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            if os.path.exists(out_c) and os.path.getsize(out_c) > 50_000 and not is_sticker_mask_video(out_c):
                clips.append(out_c)
                idx += 1
            start_t += 4.8
    return clips


def select_semantic_assets(blocks, prefer_horizontal=True):
    """
    Associa a cada bloco de roteiro uma imagem 4K oficial e/ou clipe de vídeo real
    cujas tags semânticas correspondam às palavras da narração/tópico, SEM REPETIÇÃO.
    """
    used_imgs = set()
    available_imgs = {}
    for fname, meta in IMAGE_SEMANTIC_MAP.items():
        if prefer_horizontal and "vertical" in meta["tags"]:
            continue
        full_p = os.path.join(VAULT_DIR, fname)
        if os.path.exists(full_p):
            available_imgs[fname] = (full_p, meta["tags"], meta["subject"])

    assignments = []
    for b_idx, blk in enumerate(blocks):
        text_low = (
            f"{blk.get('narration', '')} {blk.get('visual_topic', '')} "
            f"{blk.get('callout', '')} {blk.get('location_key', '')} {blk.get('character_name', '')}"
        ).lower()

        best_fname = None
        best_score = -1
        for fname, (full_p, tags, subj) in available_imgs.items():
            if fname in used_imgs and len(used_imgs) < len(available_imgs):
                continue
            score = 0
            for t in tags:
                if t.replace("_", " ") in text_low or t in text_low:
                    score += 3
            # Bônus por palavras-chave contextuais
            if any(w in text_low for w in ["mapa", "vice city", "leonida", "estado", "região", "keys", "porto"]) and "mapa" in tags:
                score += 4
            if any(w in text_low for w in ["lucia", "jason", "casal", "protagonista"]) and ("lucia" in tags or "jason" in tags):
                score += 4
            if any(w in text_low for w in ["carro", "veículo", "física", "dirigir", "motor", "velocidade"]) and "carros" in tags:
                score += 4
            if any(w in text_low for w in ["polícia", "assalto", "arma", "crime", "tiro"]) and ("armas" in tags or "assalto" in tags):
                score += 4
            if any(w in text_low for w in ["água", "oceano", "barco", "praia", "mar"]) and "agua" in tags:
                score += 4
            if any(w in text_low for w in ["noite", "clube", "luz", "neon"]) and "noite" in tags:
                score += 4
            if score > best_score:
                best_score = score
                best_fname = fname

        if not best_fname and available_imgs:
            unused = [k for k in available_imgs if k not in used_imgs] or list(available_imgs.keys())
            best_fname = unused[b_idx % len(unused)]

        if best_fname:
            used_imgs.add(best_fname)
            full_p, tags, subj = available_imgs[best_fname]
            # Segundo asset complementar diferente para composições multi-camada
            alt_candidates = [
                v[0] for k, v in available_imgs.items()
                if k != best_fname and k not in used_imgs and set(v[1]) & set(tags)
            ] or [v[0] for k, v in available_imgs.items() if k != best_fname]
            alt_p = alt_candidates[b_idx % len(alt_candidates)] if alt_candidates else full_p
            assignments.append({"primary_img": full_p, "secondary_img": alt_p, "subject": subj, "tags": tags})
        else:
            assignments.append({"primary_img": None, "secondary_img": None, "subject": "", "tags": []})

    return assignments
