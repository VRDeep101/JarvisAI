import pygame
import random
import soundfile as sf
import os
import re
import threading
import queue
from kokoro_onnx import Kokoro
from dotenv import dotenv_values

# ─── Config ──────────────────────────────────────────────────────────────────

_config    = dotenv_values(".env")

VOICE_ID   = "am_puck"
SPEED      = 0.8
LANGUAGE   = "en-us"
AUDIO_PATH = r"Data\speech_{}.wav"   # {} = slot index (double-buffered)

_kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
pygame.mixer.init()

# ─── Overflow Messages ────────────────────────────────────────────────────────

OVERFLOW_LINES = [
    "The rest of the answer is up on the screen for you — do have a look.",
    "The remaining details are right there on the screen sir,whenever you're ready.",
    "There's more to it — check the chat screen for the complete picture.",
    
]

# ─── Sentence Splitter ───────────────────────────────────────────────────────

def _split_sentences(text: str) -> list[str]:
    """Split on . ! ? — keep non-empty, stripped sentences."""
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip()]

# ─── Natural Text Preprocessor ───────────────────────────────────────────────

def _make_natural(text: str) -> str:
    text = re.sub(
        r'\s+(and|but|so|because|however|though|although|which|who)\s+',
        r', \1 ', text, flags=re.IGNORECASE
    )
    text = re.sub(r'[,]{2,}', ',', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ─── Streaming Speak ─────────────────────────────────────────────────────────

def speak(text: str, callback=lambda r=None: True) -> bool:
    """
    Pipeline approach:
      - Producer thread: generates audio for each sentence → puts (samples, rate, slot) in queue
      - Main thread: plays each chunk as soon as it's ready
    First audio starts playing while sentence 2 is still being generated → near-zero wait.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return False

    audio_q: queue.Queue = queue.Queue(maxsize=2)   # at most 2 chunks buffered
    DONE = object()                                  # sentinel

    os.makedirs(os.path.dirname(AUDIO_PATH.format(0)), exist_ok=True)

    def producer():
        for idx, sentence in enumerate(sentences):
            try:
                natural = _make_natural(sentence)
                samples, sample_rate = _kokoro.create(
                    natural, voice=VOICE_ID, speed=SPEED, lang=LANGUAGE
                )
                slot = idx % 2          # double-buffer: alternates between slot 0 and 1
                path = AUDIO_PATH.format(slot)
                sf.write(path, samples, sample_rate)
                audio_q.put((path, sample_rate))
            except Exception as exc:
                print(f"[TTS] Generation error (sentence {idx}): {exc}")
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
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if not callback():
                    pygame.mixer.music.stop()
                    success = False
                    break
                pygame.time.Clock().tick(10)
        except Exception as exc:
            print(f"[TTS] Playback error: {exc}")
            success = False

        if not success:
            break

    try:
        callback(False)
        pygame.mixer.music.stop()
    except Exception:
        pass

    t.join(timeout=2)
    return success


def say(text: str, callback=lambda r=None: True) -> None:
    """Smart speak — long text gets truncated to first 2 sentences + overflow."""
    sentences = _split_sentences(str(text))
    is_long   = len(sentences) > 4 and len(text) >= 250

    if is_long:
        short = ". ".join(sentences[:2]) + ". " + random.choice(OVERFLOW_LINES)
        speak(short, callback)
    else:
        speak(text, callback)


# ─── Entry Point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[ TTS Engine ready ] Type something and press Enter. ('exit' to quit)")
    while True:
        user_input = input(":) ").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("Later!")
            break
        if user_input:
            say(user_input)