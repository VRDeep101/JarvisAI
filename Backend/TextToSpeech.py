import pygame
import random
import soundfile as sf
import os
import re
from kokoro_onnx import Kokoro
from dotenv import dotenv_values

# ─── Config ──────────────────────────────────────────────────────────────────

_config    = dotenv_values(".env")

VOICE_ID   = "am_puck"
SPEED      = 0.7
LANGUAGE   = "en-us"
AUDIO_PATH = r"Data\speech.wav"

_kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

# ─── Pygame Mixer — once at startup ──────────────────────────────────────────
# Init once here so first playback has zero delay — no word skipping

pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=512)
pygame.mixer.init()

# ─── Overflow Messages ────────────────────────────────────────────────────────

OVERFLOW_LINES = [
    "The rest of the answer is up on the screen for you — do have a look.",
    "I've kept it brief here; the full response is waiting on the chat screen.",
    "The remaining details are right there on the screen whenever you're ready.",
    "There's more to it — check the chat screen for the complete picture.",
    "I'll stop here; the rest is displayed on the screen for your convenience.",
    "The continuation is on the chat screen — it's all there for you.",
    "Kindly glance at the screen — the full answer is printed there.",
    "The chat screen has everything else you need. Do take a look.",
    "I've only read part of it aloud — the rest is on the screen for you.",
    "The complete response has been laid out on the chat screen.",
    "You'll find the remaining text on the screen — it's all there.",
    "The answer continues on the chat screen; please have a look when you can.",
    "There's quite a bit more — it's all visible on the chat screen.",
    "For the full breakdown, the chat screen has you covered.",
    "I've summarised the start; do check the screen for the rest.",
    "The remainder of the response is on display — the screen has it all.",
    "The chat screen holds the rest of what you need to know.",
    "Everything else is right there on the screen — please do check.",
    "I kept the audio short on purpose; the full text is on the screen.",
    "The screen has the complete answer ready for you. Kindly take a look.",
    "More details are printed on the chat screen — have a glance at your leisure.",
    "The tail end of the response is on the screen, all ready for you.",
    "To get the full picture, the chat screen is your best bet right now.",
    "I've only scratched the surface here — the rest lives on the chat screen.",
    "The chat panel has the remaining information laid out clearly for you.",
    "The longer portion is displayed on the screen — it's worth a read.",
    "Hop over to the chat screen — the complete answer is printed there.",
    "What follows is on the screen; I didn't want to read it all out.",
    "The full reply is on the chat screen — nothing's been left out.",
    "For everything else, the screen's got you. Do give it a look.",
]

# ─── Natural Text Preprocessor ───────────────────────────────────────────────

def _make_natural(text: str) -> str:
    text = re.sub(
        r'\s+(and|but|so|because|however|though|although|which|who)\s+',
        r', \1 ', text, flags=re.IGNORECASE
    )
    text = re.sub(
        r'(\b(what|when|where|who|why|how|is|are|was|were|do|does|did|can|could|will|would)\b[^.?!]{5,})(?=\.\s)',
        r'\1?', text, flags=re.IGNORECASE
    )
    text = re.sub(r'[,]{2,}', ',', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# ─── Core Audio Generation ────────────────────────────────────────────────────

def _generate_audio(text: str) -> tuple:
    """Convert text to audio samples via Kokoro."""
    natural_text = _make_natural(text)
    samples, sample_rate = _kokoro.create(
        natural_text,
        voice=VOICE_ID,
        speed=SPEED,
        lang=LANGUAGE
    )
    return samples, sample_rate

# ─── Playback ────────────────────────────────────────────────────────────────

def _play_audio(samples, sample_rate, callback=lambda r=None: True) -> bool:
    """
    Play audio — mixer already initialized at startup so zero delay.
    """
    try:
        os.makedirs(os.path.dirname(AUDIO_PATH), exist_ok=True)
        sf.write(AUDIO_PATH, samples, sample_rate)

        pygame.mixer.music.load(AUDIO_PATH)
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            if not callback():
                break
            pygame.time.Clock().tick(10)

        return True

    except Exception as exc:
        print(f"[TTS] Playback error: {exc}")
        return False

    finally:
        try:
            callback(False)
            pygame.mixer.music.stop()
        except Exception as exc:
            print(f"[TTS] Cleanup error: {exc}")

# ─── Public API ──────────────────────────────────────────────────────────────

def speak(text: str, callback=lambda r=None: True) -> bool:
    """Generate audio from text and play it."""
    try:
        samples, sample_rate = _generate_audio(text)
    except Exception as exc:
        print(f"[TTS] Generation error: {exc}")
        return False
    return _play_audio(samples, sample_rate, callback)


def say(text: str, callback=lambda r=None: True) -> None:
    """
    Smart speak — long text (>= 250 chars, > 4 sentences) gets truncated
    to first 2 sentences + overflow message.
    """
    sentences = str(text).split(".")
    is_long   = len(sentences) > 4 and len(text) >= 250

    if is_long:
        short_version = ". ".join(sentences[:2]).strip() + ". " + random.choice(OVERFLOW_LINES)
        speak(short_version, callback)
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