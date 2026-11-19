"""Cliente Gemini robusto (retry com backoff + fallback de modelos).

Corrige a causa raiz das falhas de 17/11 (HTTP 503 sem retry derrubando o vídeo longo).
Uso: gemini_generate(payload, models=TEXT_MODELS) -> dict de resposta.
"""
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

TEXT_MODELS = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-3.1-flash-lite", "gemini-3.5-flash", "gemini-3.8-flash"]
TTS_MODELS = ["gemini-2.5-flash-preview-tts", "gemini-3.8-flash-tts", "gemini-3.1-flash-tts-preview"]
RETRYABLE = (429, 500, 502, 503, 504)


def get_api_key():
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        return key.strip()
    from voice_and_avatar import get_secret  # noqa: WPS433
    return get_secret("GEMINI_API_KEY", "1_GEMINI_API_KEY.txt")


def gemini_generate(payload, models=None, attempts_per_model=4, timeout=180, verbose=True):
    models = models or TEXT_MODELS
    key = get_api_key()
    last_err = None
    for model in models:
        for attempt in range(attempts_per_model):
            try:
                req = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                if not data.get("candidates"):
                    raise RuntimeError(f"sem candidates: {data.get('promptFeedback')}")
                data["_model"] = model
                return data
            except urllib.error.HTTPError as err:
                last_err = err
                body = err.read()[:200].decode("utf-8", "ignore")
                if err.code in RETRYABLE and attempt < attempts_per_model - 1:
                    wait = min(60, (2 ** attempt) * 4 + random.uniform(0, 3))
                    if verbose:
                        print(f"[GEMINI] {model} HTTP {err.code} -> retry em {wait:.0f}s ({body[:80]})", flush=True)
                    time.sleep(wait)
                    continue
                if verbose:
                    print(f"[GEMINI] {model} falhou HTTP {err.code}: {body[:120]} -> próximo modelo", flush=True)
                break
            except Exception as err:  # timeouts, JSON etc.
                last_err = err
                if attempt < attempts_per_model - 1:
                    wait = min(45, (2 ** attempt) * 3)
                    if verbose:
                        print(f"[GEMINI] {model} erro {err} -> retry em {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                break
    raise RuntimeError(f"Todos os modelos Gemini falharam: {last_err}")


def gemini_text(prompt, models=None, json_mode=False, temperature=0.7, parts_extra=None):
    parts = list(parts_extra or []) + [{"text": prompt}]
    cfg = {"temperature": temperature}
    if json_mode:
        cfg["responseMimeType"] = "application/json"
    data = gemini_generate({"contents": [{"parts": parts}], "generationConfig": cfg}, models=models)
    txt = "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]).strip()
    if json_mode:
        if txt.startswith("```"):
            txt = txt.strip("`").lstrip("json").strip()
        parsed = json.loads(txt)
        # Alguns modelos fallback (ex: gemini-2.5-flash) retornam [{...}] em vez de {...}
        if isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], dict):
            parsed = parsed[0]
        return parsed, data["_model"]
    return txt, data["_model"]
