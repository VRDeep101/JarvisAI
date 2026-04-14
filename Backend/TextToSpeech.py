# ─────────────────────────────────────────────────────────────
#  TextToSpeech.py  —  Jarvis Voice Output
#  - EQ tone aware (rate + pitch)
#  - Natural pauses between sentences
#  - Plan lines voice mein nahi aate
#  - Fast streaming pipeline
# ─────────────────────────────────────────────────────────────

import pygame
import random
import soundfile as sf
import os
import re
import threading
import queue
from kokoro_onnx import Kokoro
from dotenv import dotenv_values

# ─── Config ───────────────────────────────────────────────────
_config  = dotenv_values(".env")

VOICE_ID  = "am_puck"
BASE_SPEED = 0.85        # slightly slower = more natural
LANGUAGE  = "en-us"

AUDIO_PATH = os.path.join("Data", "speech_{}.wav")
os.makedirs("Data", exist_ok=True)

_kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
pygame.mixer.init()
if not pygame.mixer.get_init():
    print("[TTS ERROR] pygame mixer init FAILED!")
else:
    print("[TTS] Audio system ready ✅")

# ─── Overflow Lines ────────────────────────────────────────────
OVERFLOW_LINES = [
    "The rest is on the screen for you.",
    "Check the chat for the full details.",
    "There's more up on the screen, have a look.",
]

# ─── Plan/Internal Line Filter ────────────────────────────────
_FILTER_PREFIXES = [
    "risky:", "plan:", "note:", "internal:", "step ", "1.", "2.", "3."
]

def _is_filterable(line: str) -> bool:
    l = line.lower().strip()
    for prefix in _FILTER_PREFIXES:
        if l.startswith(prefix):
            return True
    return False


# ─── Text Preprocessor ────────────────────────────────────────
def _clean_for_speech(text: str) -> str:
    # Remove markdown
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'`+', '', text)
    # Remove URLs
    text = re.sub(r'http\S+', '', text)
    # Filter plan lines
    lines = [l for l in text.split('\n') if not _is_filterable(l)]
    text = ' '.join(lines)
    # Natural commas before connectors
    text = re.sub(
        r'\s+(and|but|so|because|however|though|although|which|who)\s+',
        r', \1 ', text, flags=re.IGNORECASE
    )
    text = re.sub(r'[,]{2,}', ',', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


# ─── Sentence Splitter ────────────────────────────────────────
def _split_sentences(text: str) -> list:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]


# ─── Speed Parser ─────────────────────────────────────────────
def _parse_rate(rate_str: str) -> float:
    """
    Convert EQ rate string to kokoro speed float.
    '+8%' → 0.93  (faster = lower kokoro speed value)
    '-12%' → 0.97 (slower = higher kokoro speed value)
    """
    try:
        val = int(re.sub(r'[^-\d]', '', rate_str))
        # kokoro speed: 1.0 = normal, <1 = slower, but feels faster
        # EQ rate +% means faster speech = lower kokoro speed
        speed = BASE_SPEED - (val * 0.003)
        return max(0.5, min(1.2, speed))
    except Exception:
        return BASE_SPEED


# ─── Core Streaming Speak ─────────────────────────────────────
def speak(text: str, speed: float = None) -> bool:
    """
    Streaming TTS:
    - Producer generates audio sentence by sentence
    - Player plays as soon as each is ready
    """
    clean     = _clean_for_speech(text)
    sentences = _split_sentences(clean)
    if not sentences:
        return False

    final_speed = speed if speed is not None else BASE_SPEED
    audio_q = queue.Queue(maxsize=2)
    DONE    = object()

    def producer():
        for idx, sentence in enumerate(sentences):
            try:
                samples, sample_rate = _kokoro.create(
                    sentence, voice=VOICE_ID, speed=final_speed, lang=LANGUAGE
                )
                slot = idx % 2
                path = AUDIO_PATH.format(slot)
                sf.write(path, samples, sample_rate)
                audio_q.put((path, sample_rate))
            except Exception as exc:
                print(f"[TTS] Gen error sentence {idx}: {exc}")
        audio_q.put(DONE)

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    success = True
    while True:
        item = audio_q.get()
        if item is DONE:
            break
        path, _ = item
        try:
            if not os.path.exists(path):
                continue
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            # Natural pause between sentences
            pygame.time.wait(120)
        except Exception as exc:
            print(f"[TTS] Playback error: {exc}")
            success = False
            break

    try:
        pygame.mixer.music.stop()
    except Exception:
        pass

    t.join(timeout=2)
    return success


# ─── Smart Say ────────────────────────────────────────────────
def say(text: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
    """
    Main TTS function:
    - Long text: first 2 sentences + overflow message
    - EQ rate/pitch applied to speed
    - Plan lines filtered automatically
    """
    speed     = _parse_rate(rate)
    sentences = _split_sentences(_clean_for_speech(str(text)))
    is_long   = len(sentences) > 4 and len(text) >= 250

    if is_long:
        short_text = ". ".join(s.rstrip('.') for s in sentences[:2])
        short_text += ". " + random.choice(OVERFLOW_LINES)
        speak(short_text, speed=speed)
    else:
        speak(text, speed=speed)


# ─── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    print("[ TTS Engine ready ] Type to test. ('exit' to quit)")
    while True:
        user_input = input(":) ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input:
            say(user_input)