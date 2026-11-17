import json
import os
import sys
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from brain import get_gemini_key  # noqa: E402


def generate_gta6_long_script(research_brief):
    """
    Estuda os vídeos virais reais de GTA 6 do research_brief e cria um roteiro
    cinematográfico de STORYTELLING em 5 Atos (~1.250-1.400 palavras = 8 a 9 minutos),
    com 4 climas musicais distintos e alta retenção de ponta a ponta.
    """
    api_key = get_gemini_key()

    refs_str = "\n".join(
        f"- ({r.get('views', 0):,} views | {r.get('channel', '')}) \"{r.get('title', '')}\""
        for r in (research_brief.get("top_references") or [])[:10]
    )
    news_str = "\n".join(f"- {h}" for h in (research_brief.get("news_headlines") or [])[:6])
    notes_str = research_brief.get("grounding_notes", "")[:800]
    chosen_angle = research_brief.get("chosen_angle", "COMO VAI SER O DIA DO LANÇAMENTO DO GTA 6")

    prompt = f"""Você é o roteirista-chefe de um canal gamer brasileiro gigante (estilo Blader Koyotte, BRKsEDU, Gameplayrj, PlayStationGrenade) focado em bater **100.000+ views** com documentários/ensaios virais sobre **GTA 6**, que lança nesta QUINTA-FEIRA!

REFERÊNCIAS REAIS QUE ESTÃO EXPLODINDO EM VIEWS AGORA:
{refs_str}

NOTÍCIAS E HIPÓTESES ATUAIS DO LANÇAMENTO:
{news_str}
{notes_str}

TEMA CENTRAL DESTE VÍDEO DE 8 A 9 MINUTOS:
"{chosen_angle}"

OBJETIVO MESTRE (STORYTELLING & RETENÇÃO):
1. Analise o padrão psicológico dos títulos acima ("vai mudar tudo", "o que você perdeu", "dia do lançamento", "segredos ocultos") e crie uma **NARRATIVA DE STORYTELLING IMERSIVA EM 5 ATOS**.
2. NUNCA comece com clichês ("Oi pessoal, no vídeo de hoje..."). Comece direto no Ato 1 transportando o espectador para uma cena cinematográfica ("Quinta-feira. Zero hora. Milhões de telas acendendo ao mesmo tempo em Vice City...").
3. Cada Ato deve criar uma **ponte de curiosidade ("open loop")** pro próximo Ato para segurar a retenção acima de 55–65% até o minuto 9!
4. Escreva **EXATAMENTE 5 ATOS**, com **7 blocos de narração por Ato (35 blocos ao todo)**.
   - IMPORTANTE SOBRE DURAÇÃO (8m20s a 9m15s para monetização com mid-rolls!): cada bloco (`narration`) deve ter **42 a 50 palavras** (entre **245 e 285 caracteres** — limite rígido: **MÁXIMO 285 caracteres por bloco!**).
   - 35 blocos × ~42 palavras = ~1.350 a 1.500 palavras (~8 minutos e 30 segundos a 9 minutos de vídeo contínuo!).
   - Fale em Português do Brasil **super natural, falado, humano**, com vírgulas, pausas dramáticas (`...`) e perguntas retóricas — zero linguagem acadêmica ou robótica!
5. Cada Ato usa um clima musical diferente (`bgm_mood`), escolhendo entre: `"synth"`, `"story"`, `"tension"`, `"urban"`.
   - Ato 1: `"synth"` (Clima Vice City épico / Gancho de Abertura)
   - Ato 2: `"story"` (Contexto histórico / A espera de 13 anos e comparações)
   - Ato 3: `"tension"` (Segredos escondidos, teorias, mapa de Leonida e polícia/IA)
   - Ato 4: `"urban"` (O impacto no dia do lançamento / mecânicas absurdas / clímax)
   - Ato 5: `"synth"` (Conclusão emocionante + debate polarizador pros comentários)

Responda APENAS com JSON válido seguindo exatamente esta estrutura:
{{
  "long_title": "Título magnético de alto CTR até 78 caracteres sem #shorts",
  "thumb_text": "2 OU 3 PALAVRAS GIGANTES",
  "long_description": "Descrição SEO em PT-BR envolvente sobre GTA 6 + pergunta pros comentários + hashtags (#gta6 #gtavi #rockstargames #games)",
  "long_tags": ["gta 6", "gta vi", "lancamento gta 6", "gta 6 novidades", "gta 6 segredos", "gta 6 curiosidades", "gta 6 mapa", "gta 6 historia", "rockstar games", "vice city", "leonida", "lucia", "jason", "gta 6 gameplay", "games 2026"],
  "acts": [
    {{
      "act_num": 1,
      "act_title": "A NOITE QUE VAI PARAR O MUNDO",
      "bgm_mood": "synth",
      "blocks": [
        {{
          "narration": "Texto falado em português natural com no máximo 290 caracteres...",
          "callout": "QUINTA-FEIRA",
          "visual_cue": "action"
        }}
      ]
    }}
  ]
}}"""

    safety = [
        {"category": cat, "threshold": "BLOCK_ONLY_HIGH"}
        for cat in [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
        ]
    ]

    last_err = None
    data = None
    for model in ["gemini-2.5-flash", "gemini-3.5-flash"]:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "safetySettings": safety,
            "generationConfig": {
                "temperature": 0.72,
                "responseMimeType": "application/json",
            },
        }
        try:
            print(f"[GTA6 LONG BRAIN] Gerando roteiro storytelling 5 Atos com {model}...", flush=True)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            cands = body.get("candidates") or []
            if not cands:
                raise RuntimeError(f"Sem candidates ({body.get('promptFeedback')})")
            data = json.loads(cands[0]["content"]["parts"][0]["text"])
            data["model_used"] = model
            break
        except Exception as err:
            last_err = err
            print(f"[GTA6 LONG BRAIN] Aviso {model}: {err}", flush=True)

    if not data or not data.get("acts"):
        raise RuntimeError(f"Falha no Gemini ao gerar roteiro GTA 6 longo: {last_err}")

    # Quebra qualquer bloco que tenha passado de 290 caracteres em sub-blocos limpos por pontuação
    for act in data["acts"]:
        clean_blocks = []
        for blk in act.get("blocks", []):
            txt = (blk.get("narration") or "").strip()
            if not txt:
                continue
            if len(txt) <= 290:
                clean_blocks.append(blk)
            else:
                sents = [s.strip() for s in txt.replace("...", "…").split(". ") if s.strip()]
                buf = ""
                for s in sents:
                    piece = s if s.endswith((".", "!", "?", "…")) else s + "."
                    if len(buf) + len(piece) + 1 <= 285:
                        buf = (buf + " " + piece).strip()
                    else:
                        if buf:
                            clean_blocks.append({**blk, "narration": buf})
                        buf = piece[:285]
                if buf:
                    clean_blocks.append({**blk, "narration": buf})
        act["blocks"] = clean_blocks

    total_words = sum(len(b["narration"].split()) for a in data["acts"] for b in a["blocks"])
    total_blocks = sum(len(a["blocks"]) for a in data["acts"])
    print(f"[GTA6 LONG BRAIN] Roteiro pronto: {len(data['acts'])} Atos | {total_blocks} blocos | {total_words} palavras | Título: {data.get('long_title')}")
    return data
