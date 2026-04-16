# ─────────────────────────────────────────────────────────────
#  TextToSpeech.py  —  Jarvis Voice  [ULTRA v9 — edge-tts]
#
#  WHY edge-tts:
#    → Microsoft Neural voices (same engine as Azure TTS / ElevenLabs quality)
#    → 100% FREE, no API key, no limit
#    → 400+ voices: Indian English, British, American, etc.
#    → Streamed playback — low latency
#    → Sounds like a real human, not a robot
#
#  VOICES (change VOICE_ID below):
#    en-US-AndrewNeural      → calm American male (default)
#    en-US-GuyNeural         → energetic American male
#    en-US-AriaNeural        → warm American female
#    en-IN-PrabhatNeural     → Indian English male ← recommended for Jarvis
#    en-IN-NeerjaExpressiveNeural → Indian English female
#    en-GB-RyanNeural        → British male (very classy)
#
#  3-STATE SYSTEM:
#    IS_SPEAKING = True  → set BEFORE audio starts
#    IS_SPEAKING = False → set AFTER pygame fully stops + files deleted
#    SpeechToText polls _tts.IS_SPEAKING — never overlaps
# ─────────────────────────────────────────────────────────────

import asyncio
import os
import re
import random
import threading
import tempfile
import time

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False
    print("[TTS] ⚠️  edge-tts not installed. Run: pip install edge-tts")

try:
    import pygame
    pygame.mixer.pre_init(frequency=22050, size=-16, channels=1, buffer=512)
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception:
    PYGAME_AVAILABLE = False

try:
    import keyboard
    _KB = True
except ImportError:
    _KB = False

# ── Config ────────────────────────────────────────────────────
VOICE_ID    = "en-US-BrianNeural"   # Change to your preference
RATE_DEFAULT = "+0%"
PITCH_DEFAULT = "+0Hz"

os.makedirs("Data", exist_ok=True)

# ── IS_SPEAKING: THE CRITICAL FLAG ───────────────────────────
IS_SPEAKING: bool           = False
INTERNAL_AUDIO_BLOCKED: bool = True

def _toggle_internal_audio():
    global INTERNAL_AUDIO_BLOCKED
    INTERNAL_AUDIO_BLOCKED = not INTERNAL_AUDIO_BLOCKED
    print(f"[TTS] Audio: {'UNBLOCKED' if not INTERNAL_AUDIO_BLOCKED else 'BLOCKED'}")

if _KB:
    try:
        keyboard.add_hotkey("windows+shift", _toggle_internal_audio)
    except Exception:
        pass

# ── STT word cache sync ───────────────────────────────────────
def _register_words_in_stt(text: str) -> None:
    try:
        import sys
        stt = sys.modules.get("Backend.SpeechToText") or sys.modules.get("SpeechToText")
        if stt and hasattr(stt, "RegisterTTSWords"):
            stt.RegisterTTSWords(text)
    except Exception:
        pass

def _clear_stt_word_cache() -> None:
    try:
        import sys
        stt = sys.modules.get("Backend.SpeechToText") or sys.modules.get("SpeechToText")
        if stt and hasattr(stt, "ClearTTSWordCache"):
            stt.ClearTTSWordCache()
    except Exception:
        pass

# ── Text Cleaner ──────────────────────────────────────────────
_FILTER_PREFIXES = ["risky:", "plan:", "note:", "internal:"]

def _clean_for_speech(text: str) -> str:
    text = re.sub(r'\*+', '', text)
    text = re.sub(r'#+\s*', '', text)
    text = re.sub(r'`+', '', text)
    text = re.sub(r'http\S+', '', text)
    lines = [l for l in text.split('\n')
             if not any(l.lower().strip().startswith(p) for p in _FILTER_PREFIXES)]
    text = ' '.join(lines)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def _split_sentences(text: str) -> list:
    parts = re.split(r'(?<=[.!?])\s+', text.strip())
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]

# ── Core: Generate + Play with edge-tts ──────────────────────
async def _generate_audio_edge(text: str, rate: str, pitch: str, output_path: str) -> bool:
    """Generate speech using edge-tts and save to output_path."""
    try:
        communicate = edge_tts.Communicate(
            text=text,
            voice=VOICE_ID,
            rate=rate,
            pitch=pitch,
        )
        await communicate.save(output_path)
        return True
    except Exception as e:
        print(f"[TTS] edge-tts error: {e}")
        return False

def _play_file(filepath: str) -> bool:
    """Play audio file using pygame."""
    if not PYGAME_AVAILABLE:
        return False
    try:
        pygame.mixer.music.load(filepath)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)
        pygame.mixer.music.unload()
        return True
    except Exception as e:
        print(f"[TTS] Playback error: {e}")
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        return False

def speak(text: str, rate: str = "+0%", pitch: str = "+0Hz") -> bool:
    """
    Main TTS function. Generates audio with edge-tts and plays it.
    IS_SPEAKING = True BEFORE anything, False AFTER complete cleanup.
    """
    global IS_SPEAKING

    if not EDGE_TTS_AVAILABLE:
        print(f"[TTS] {text}")
        return False

    clean = _clean_for_speech(text)
    if not clean:
        return False

    # ── RULE 1: Flag True BEFORE everything ─────────────────
    IS_SPEAKING = True
    _register_words_in_stt(clean)

    tmp_files = []

    try:
        sentences = _split_sentences(clean)
        if not sentences:
            return False

        for i, sentence in enumerate(sentences):
            # Generate audio
            tmp_fd, tmp_path = tempfile.mkstemp(
                suffix=".mp3", dir="Data", prefix=f"tts_{i}_"
            )
            os.close(tmp_fd)
            tmp_files.append(tmp_path)

            loop = asyncio.new_event_loop()
            success = loop.run_until_complete(
                _generate_audio_edge(sentence, rate, pitch, tmp_path)
            )
            loop.close()

            if success and os.path.exists(tmp_path):
                _play_file(tmp_path)

                # Pause between sentences
                if sentence.strip().endswith('?'):
                    time.sleep(0.18)
                elif sentence.strip().endswith('!'):
                    time.sleep(0.14)
                else:
                    time.sleep(0.12)

        return True

    except Exception as e:
        print(f"[TTS] speak error: {e}")
        return False

    finally:
        # ── RULE 2: Full cleanup BEFORE IS_SPEAKING = False ──
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        for fpath in tmp_files:
            try:
                if os.path.exists(fpath):
                    os.remove(fpath)
            except Exception:
                pass

        _clear_stt_word_cache()
        IS_SPEAKING = False  # ← Very last thing

# ── Overflow / Pre / Post responses ──────────────────────────
OVERFLOW_LINES = [
    "The rest is on the screen for you.",
    "Check the chat for the full details.",
    "I've put everything on the screen.",
    "Have a look at the screen for more.",
    "Details are up on the display.",
]

PRE_TASK_RESPONSES = {
    "open":          ["Sure, opening {app} for you.", "Alright, launching {app}.", "Opening {app} right away."],
    "close":         ["Sure, closing {app}.", "Alright, closing {app} now.", "Closing {app} for you."],
    "play":          ["Sure, playing {song} for you.", "Playing {song} now.", "Here you go — {song}."],
    "volume up":     ["Turning the volume up.", "Sure, volume up.", "Cranking it up."],
    "volume down":   ["Lowering the volume.", "Sure, volume down.", "Bringing it down."],
    "mute":          ["Muting the audio.", "Muted.", "Going silent."],
    "unmute":        ["Unmuting.", "Audio is back on.", "You can hear me now."],
    "google search": ["Sure, searching for {query} on Google.", "Looking that up for you.", "On it — searching now."],
    "content":       ["Sure, writing content on {topic}.", "Let me write that up.", "Working on it."],
    "screenshot":    ["Taking a screenshot now.", "Screenshot incoming.", "Captured."],
    "screen record": ["Starting screen recording.", "Recording your screen now."],
    "default":       ["Sure, on it.", "Alright, working on that.", "Got it.", "Consider it done.", "Right away."],
}

POST_TASK_RESPONSES = [
    "Anything else you need?",
    "What would you like to do next?",
    "Done. What else can I help with?",
    "All good. What's next?",
    "Task complete. Need anything else?",
]

IDLE_PROMPTS = [
    "Hey, want me to play your favourite song?",
    "I'm here if you need anything.",
    "Should I check something for you?",
    "Want me to search something up?",
    "I'm all ears if you need help.",
    "Quiet day. Need me to do anything?",
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

# ── EQ-aware rate mapping ─────────────────────────────────────
_RATE_MAP = {
    "happy":     "+10%",
    "excited":   "+15%",
    "sad":       "-12%",
    "angry":     "-8%",
    "anxious":   "-10%",
    "tired":     "-12%",
    "love":      "-5%",
    "lonely":    "-10%",
    "proud":     "+5%",
    "grateful":  "+3%",
    "bored":     "+5%",
    "motivated": "+12%",
    "neutral":   "+0%",
}

_PITCH_MAP = {
    "happy":     "+4Hz",
    "excited":   "+6Hz",
    "sad":       "-3Hz",
    "angry":     "-2Hz",
    "anxious":   "-2Hz",
    "tired":     "-2Hz",
    "love":      "+2Hz",
    "lonely":    "-3Hz",
    "proud":     "+3Hz",
    "grateful":  "+1Hz",
    "bored":     "+1Hz",
    "motivated": "+4Hz",
    "neutral":   "+0Hz",
}

def get_rate_for_emotion(emotion: str) -> str:
    return _RATE_MAP.get(emotion, "+0%")

def get_pitch_for_emotion(emotion: str) -> str:
    return _PITCH_MAP.get(emotion, "+0Hz")

# ── Public entry: say() ───────────────────────────────────────
def say(text: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
    """
    Public TTS entry. Long text truncated to 3 sentences + overflow line.
    """
    sentences = _split_sentences(_clean_for_speech(str(text)))
    is_long   = len(sentences) > 3 or len(text) >= 200

    if is_long:
        short  = ". ".join(s.rstrip('.') for s in sentences[:2])
        short += ". " + random.choice(OVERFLOW_LINES)
        speak(short, rate=rate, pitch=pitch)
    else:
        speak(text, rate=rate, pitch=pitch)

# ── CLI test ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("[ Edge-TTS Engine ready — type to test ]")
    print(f"[ Voice: {VOICE_ID} ]")
    while True:
        try:
            user_input = input(":) ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye.")
            break
        if user_input.lower() in {"exit", "quit"}:
            break
        if user_input:
            say(user_input)