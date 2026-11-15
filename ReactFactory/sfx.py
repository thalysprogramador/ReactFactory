import os
import math
import wave
import struct
import random

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)


def generate_whoosh(filepath, duration=0.38, sample_rate=44100):
    """Gera um efeito sonoro de Whoosh cinematográfico para transições."""
    n_samples = int(duration * sample_rate)
    with wave.open(filepath, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        prev = 0.0
        for i in range(n_samples):
            t = i / sample_rate
            env = math.sin(math.pi * (t / duration)) ** 1.8
            freq = 160 + 620 * (t / duration)
            tone = math.sin(2 * math.pi * freq * t) * 0.35
            noise = (random.random() * 2 - 1) * 0.65
            # Filtro passa-baixa dinâmico
            alpha = 0.08 + 0.35 * env
            filtered = prev + alpha * (noise - prev)
            prev = filtered
            val = max(-1.0, min(1.0, (filtered + tone) * env * 0.75))
            wav.writeframes(struct.pack("<h", int(val * 32767)))


def generate_freeze_hit(filepath, duration=0.32, sample_rate=44100):
    """Gera um impacto grave + tape-stop curto para o momento da interrupção no meio."""
    n_samples = int(duration * sample_rate)
    with wave.open(filepath, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        phase = 0.0
        for i in range(n_samples):
            t = i / sample_rate
            env = math.exp(-t * 11.0)
            freq = max(45.0, 280.0 * (1.0 - (t / duration) * 0.82))
            phase += 2 * math.pi * freq / sample_rate
            sub = math.sin(phase) * 0.8
            click = ((random.random() * 2 - 1) * 0.4) if t < 0.03 else 0.0
            val = max(-1.0, min(1.0, (sub + click) * env * 0.85))
            wav.writeframes(struct.pack("<h", int(val * 32767)))


def generate_pop_cue(filepath, duration=0.14, sample_rate=44100):
    """Gera um pop agudo curto e limpo para cortes e trocas de cena."""
    n_samples = int(duration * sample_rate)
    with wave.open(filepath, "w") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        phase = 0.0
        for i in range(n_samples):
            t = i / sample_rate
            norm = t / duration
            env = math.sin(math.pi * min(1.0, norm * 2.5)) * math.exp(-t * 22.0)
            freq = 320.0 + 480.0 * norm
            phase += 2 * math.pi * freq / sample_rate
            val = max(-1.0, min(1.0, math.sin(phase) * env * 0.7))
            wav.writeframes(struct.pack("<h", int(val * 32767)))


def ensure_sfx():
    whoosh_path = os.path.join(ASSETS_DIR, "sfx_whoosh.wav")
    freeze_path = os.path.join(ASSETS_DIR, "sfx_freeze.wav")
    if not os.path.exists(whoosh_path):
        generate_whoosh(whoosh_path)
    if not os.path.exists(freeze_path):
        generate_freeze_hit(freeze_path)
    ensure_pop_sfx()
    return whoosh_path, freeze_path


def ensure_pop_sfx():
    pop_path = os.path.join(ASSETS_DIR, "sfx_pop.wav")
    if not os.path.exists(pop_path):
        generate_pop_cue(pop_path)
    return pop_path


if __name__ == "__main__":
    print(ensure_sfx())
