# ─────────────────────────────────────────────────────────────
#  TextToSpeech.py  —  Jarvis Voice Output  [FIXED v3]
#  Fixes:
#  - Unique temp file per sentence (no pygame file-lock clash)
#  - IS_SPEAKING flag set BEFORE audio plays
#  - Natural sentence pauses with ! ? . awareness
#  - No delay in pipeline (producer starts immediately)
#  - Win+Shift toggle for internal audio mode
#  - Overflow lines for long responses
# ─────────────────────────────────────────────────────────────

import pygame
import random
import soundfile as sf
import os
import re
import threading
import queue
import keyboard
import tempfile
from kokoro_onnx import Kokoro
from dotenv import dotenv_values

# ─── Config ───────────────────────────────────────────────────
_config    = dotenv_values(".env")
VOICE_ID   = "am_puck"
BASE_SPEED = 0.88
LANGUAGE   = "en-us"

os.makedirs("Data", exist_ok=True)

_kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")

pygame.mixer.pre_init(frequency=24000, size=-16, channels=1, buffer=256)
pygame.mixer.init()
if not pygame.mixer.get_init():
    print("[TTS ERROR] pygame mixer init FAILED!")
else:
    print("[TTS] Audio system ready ✅")

# ─── Global Speaking Flag ─────────────────────────────────────
IS_SPEAKING          = False
_internal_audio_mode = False

def _toggle_internal_audio():
    global _internal_audio_mode
    _internal_audio_mode = not _internal_audio_mode
    state = "ON  (internal audio bhi sun raha)" if _internal_audio_mode else "OFF (normal — apni awaaz nahi sunta)"
    print(f"\n[TTS] Internal-audio mode: {state}\n")

keyboard.add_hotkey("windows+shift", _toggle_internal_audio)

# ─── Overflow Lines ────────────────────────────────────────────
OVERFLOW_LINES = [
    "The rest is on the screen for you.",
    "Check the chat for the full details.",
    "I've put the complete details on screen.",
    "Have a look at the screen for more.",
]

# ─── Pre/Post Command Responses ───────────────────────────────
PRE_TASK_RESPONSES = {
    "open":         ["Sure, opening {app} for you.", "Alright, launching {app}.", "Opening {app} right away."],
    "close":        ["Sure, closing {app}.", "Alright, closing {app} now.", "Closing {app} for you."],
    "play":         ["Sure, playing {song} for you.", "Alright, let me play {song}.", "Playing {song} now."],
    "volume up":    ["Turning the volume up.", "Sure, volume up.", "Raising the volume for you."],
    "volume down":  ["Lowering the volume.", "Sure, volume down.", "Reducing the volume for you."],
    "mute":         ["Muting the audio.", "Sure, muted.", "Audio muted."],
    "unmute":       ["Unmuting the audio.", "Sure, unmuted.", "Audio is back on."],
    "google search":["Sure, searching for {query} on Google.", "Looking that up for you.", "Opening Google search for {query}."],
    "content":      ["Sure, writing content on {topic}.", "On it, creating content for {topic}.", "Writing that content for you."],
    "default":      ["Sure, on it.", "Alright, working on that.", "Got it, doing that now."],
}

POST_TASK_RESPONSES = [
    "Anything else you need?",
    "What would you like to do next?",
    "Is there anything more I can help with?",
    "Done. What else can I do for you?",
]

IDLE_PROMPTS = [
    "Hey, want me to play your favourite song?",
    "I'm here if you need anything.",
    "Should I check something for you?",
    "Want me to search something up?",
    "I'm all ears if you need help.",
]

def get_pre_task_response(task_type: str, **kwargs) -> str:
    templates = PRE_TASK_RESPONSES.get(task_type, PRE_TASK_RESPONSES["default"])
    template  = random.choice(templates)
    try:
        return template.format(**kwargs)
    except KeyError:
        return random.choice(PRE_TASK_RESPONSES["default"])

def get_post_task_response() -> str:
    return random.choice(POST_TASK_RESPONSES)

def get_idle_prompt() -> str:
    return random.choice(IDLE_PROMPTS)

# ─── Plan/Internal Line Filter ────────────────────────────────
_FILTER_PREFIXES = ["risky:", "plan:", "note:", "internal:", "step ", "1.", "2.", "3."]

def _is_filterable(line: str) -> bool:
    l = line.lower().strip()
    return any(l.startswith(p) for p in _FILTER_PREFIXES)

# ─── Text Preprocessor ────────────────────────────────────────
def _clean_for_speech(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'`+', '', text)
    text = re.sub(r'http\S+', '', text)
    lines = [l for l in text.split('\n') if not _is_filterable(l)]
    text  = ' '.join(lines)
    text  = re.sub(
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

# ─── Pause after punctuation ──────────────────────────────────
def _pause_after(sentence: str) -> float:
    s = sentence.strip()
    if s.endswith('?'):
        return 0.18
    elif s.endswith('!'):
        return 0.14
    elif s.endswith(','):
        return 0.08
    return 0.12

# ─── Speed Parser ─────────────────────────────────────────────
def _parse_rate(rate_str: str) -> float:
    try:
        val   = int(re.sub(r'[^-\d]', '', rate_str))
        speed = BASE_SPEED - (val * 0.003)
        return max(0.5, min(1.2, speed))
    except Exception:
        return BASE_SPEED

# ─── Core Streaming Speak ─────────────────────────────────────
def speak(text: str, speed: float = None) -> bool:
    global IS_SPEAKING

    clean     = _clean_for_speech(text)
    sentences = _split_sentences(clean)
    if not sentences:
        return False

    final_speed = speed if speed is not None else BASE_SPEED
    audio_q     = queue.Queue(maxsize=3)
    DONE        = object()

    # Set flag BEFORE starting so mic blocks immediately
    IS_SPEAKING = True

    def producer():
        for idx, sentence in enumerate(sentences):
            # Each sentence gets its own unique temp file to avoid lock conflicts
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav", dir="Data", prefix=f"tts_{idx}_")
            os.close(tmp_fd)
            try:
                samples, sample_rate = _kokoro.create(
                    sentence, voice=VOICE_ID, speed=final_speed, lang=LANGUAGE
                )
                sf.write(tmp_path, samples, sample_rate)
                audio_q.put((tmp_path, sentence))
            except Exception as exc:
                print(f"[TTS] Gen error sentence {idx}: {exc}")
                # Clean up the temp file if generation failed
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        audio_q.put(DONE)

    t = threading.Thread(target=producer, daemon=True)
    t.start()

    success = True
    played_files = []

    while True:
        item = audio_q.get()
        if item is DONE:
            break
        path, sentence = item
        played_files.append(path)
        try:
            if not os.path.exists(path):
                continue
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(20)
            # Unload so file is released before cleanup
            pygame.mixer.music.unload()
            # Natural pause based on sentence ending
            pause_ms = int(_pause_after(sentence) * 1000)
            pygame.time.wait(pause_ms)
        except Exception as exc:
            print(f"[TTS] Playback error: {exc}")
            success = False
            break

    try:
        pygame.mixer.music.stop()
        pygame.mixer.music.unload()
    except Exception:
        pass

    IS_SPEAKING = False
    t.join(timeout=2)

    # Clean up all temp wav files after playback
    for fpath in played_files:
        try:
            if os.path.exists(fpath):
                os.remove(fpath)
        except OSError:
            pass

    return success


# ─── Smart Say ────────────────────────────────────────────────
def say(text: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
    speed     = _parse_rate(rate)
    sentences = _split_sentences(_clean_for_speech(str(text)))
    is_long   = len(sentences) > 4 and len(text) >= 250

    if is_long:
        short_text  = ". ".join(s.rstrip('.') for s in sentences[:2])
        short_text += ". " + random.choice(OVERFLOW_LINES)
        speak(short_text, speed=speed)
    else:
        speak(text, speed=speed)


# ─── Entry Point ──────────────────────────────────────────────
if __name__ == "__main__":
    print("[ TTS Engine ready ] Type to test. ('exit' to quit)")
    print("Win+Shift = internal audio mode toggle\n")
    while True:
        user_input = input(":) ").strip()
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input:
            say(user_input)