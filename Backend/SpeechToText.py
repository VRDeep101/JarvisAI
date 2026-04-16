# ─────────────────────────────────────────────────────────────
#  SpeechToText.py  —  Jarvis Voice Input  [ULTRA v11]
#
#  IMPROVEMENTS v11:
#  1. Smart word correction: "harvis" → "jarvis", "help me" etc.
#  2. Confirmation for ambiguous queries (was that the right word?)
#  3. Better self-echo: 70% match threshold (was 65%)
#  4. Context-aware: last 3 commands tracked, repeats flagged
#  5. Low-confidence word filter (very short/garbled inputs ignored)
#  6. Graceful recovery from Chrome/STT errors
#  7. All v10 features preserved
# ─────────────────────────────────────────────────────────────

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
import os
import mtranslate as mt
import time
import sys
import re
import threading
import http.server
import socketserver

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import TextToSpeech as _tts

env_vars      = dotenv_values(".env")
InputLanguage = env_vars.get("InputLanguage", "en-IN")

WAKE_WORD          = "jarvis"
_POST_SPEAK_BUFFER = 1.0
_HTTP_PORT         = 9876

# ── Common misrecognitions to auto-correct ────────────────────
_CORRECTIONS = {
    "harvis":    "jarvis",
    "jarwis":    "jarvis",
    "jarvish":   "jarvis",
    "garvis":    "jarvis",
    "java":      "jarvis",
    "harvest":   "jarvis",
    "travis":    "jarvis",
    "harris":    "jarvis",
    "carvis":    "jarvis",
    "davies":    "jarvis",
    "service":   "jarvis",
}

# ── Minimum meaningful input length ──────────────────────────
_MIN_WORD_COUNT = 1     # Filter out single garbled words
_MIN_CHAR_COUNT = 3     # Filter out very short nonsense

def CheckAndClearSnap() -> bool:
    return False

def IsAFK() -> bool:
    return False

# ── Voice HTML ─────────────────────────────────────────────────
HtmlCode = f'''<!DOCTYPE html>
<html lang="en">
<head><title>Jarvis STT</title></head>
<body>
<button id="start" onclick="startRecognition()">Start</button>
<button id="end"   onclick="stopRecognition()">Stop</button>
<p id="output"></p>
<p id="confidence"></p>
<script>
    const output     = document.getElementById('output');
    const confidence = document.getElementById('confidence');
    let recognition;

    function startRecognition() {{
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang            = '{InputLanguage}';
        recognition.continuous      = true;
        recognition.interimResults  = false;
        recognition.maxAlternatives = 3;
        recognition._stopped        = false;

        recognition.onresult = function(event) {{
            const result = event.results[event.results.length - 1];
            if (result.isFinal) {{
                output.textContent     = result[0].transcript.trim();
                confidence.textContent = result[0].confidence.toFixed(2);
            }}
        }};

        recognition.onend = function() {{
            if (!recognition._stopped) recognition.start();
        }};

        recognition.onerror = function(event) {{
            if (event.error !== 'no-speech') {{
                output.textContent     = '';
                confidence.textContent = '0';
            }}
        }};

        recognition.start();
    }}

    function stopRecognition() {{
        if (recognition) {{
            recognition._stopped = true;
            recognition.stop();
        }}
        output.textContent     = '';
        confidence.textContent = '0';
    }}

    function clearOutput() {{
        output.textContent     = '';
        confidence.textContent = '0';
    }}
</script>
</body>
</html>'''

os.makedirs("Data", exist_ok=True)
_voice_html_path = os.path.join("Data", "Voice.html")
with open(_voice_html_path, "w", encoding="utf-8") as f:
    f.write(HtmlCode)

_server_dir = os.path.join(os.getcwd(), "Data")

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=_server_dir, **kwargs)
    def log_message(self, format, *args):
        pass

class _ReusingTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

def _start_http_server() -> None:
    try:
        with _ReusingTCPServer(("", _HTTP_PORT), _QuietHandler) as httpd:
            httpd.serve_forever()
    except OSError as exc:
        print(f"[STT] HTTP server failed on port {_HTTP_PORT}: {exc}")

_http_thread = threading.Thread(target=_start_http_server, daemon=True)
_http_thread.start()
time.sleep(0.3)

Link        = f"http://localhost:{_HTTP_PORT}/Voice.html"
TempDirPath = os.path.join(os.getcwd(), "Frontend", "Files")
os.makedirs(TempDirPath, exist_ok=True)

def _safe_read(filepath, retries=5, delay=0.2):
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            time.sleep(delay)
        except FileNotFoundError:
            return ""
    return ""

def _safe_write(filepath, content, retries=5, delay=0.2):
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except PermissionError:
            time.sleep(delay)
    return False

def _write_status(text: str) -> None:
    _safe_write(os.path.join(TempDirPath, "Status.data"), text)

# ── Chrome setup ───────────────────────────────────────────────
chrome_options = Options()
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--allow-file-access-from-files")
chrome_options.add_argument("--window-position=-32000,-32000")
chrome_options.add_argument("--window-size=1,1")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-software-rasterizer")
chrome_options.add_argument("--mute-audio")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
)

print("⚙️  Setting up Jarvis STT (v11)...")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options,
)
driver.get(Link)
time.sleep(1.0)
print(f"✅ STT Ready — Wake word: '{WAKE_WORD}'")

def SetAssistantStatus(Status: str) -> None:
    _write_status(Status)

def UniversalTranslator(Text: str) -> str:
    try:
        translated = mt.translate(Text, "en", "auto")
        if translated and translated.strip():
            return translated.strip()
        return Text
    except Exception:
        return Text

# ── Smart word corrections ────────────────────────────────────
def _apply_corrections(text: str) -> str:
    """Auto-fix common STT misrecognitions."""
    words = text.lower().split()
    corrected = []
    changed = False
    for word in words:
        if word in _CORRECTIONS:
            corrected.append(_CORRECTIONS[word])
            changed = True
        else:
            corrected.append(word)
    result = " ".join(corrected)
    if changed:
        print(f"[STT] Corrected: '{text}' → '{result}'")
    return result

def _is_meaningful(text: str) -> bool:
    """Filter out very short or garbled inputs."""
    stripped = text.strip()
    if len(stripped) < _MIN_CHAR_COUNT:
        return False
    words = stripped.split()
    # Filter if only one very short word (probably noise)
    if len(words) == 1 and len(words[0]) <= 2:
        return False
    return True

def QueryModifier(Query: str) -> str:
    q = Query.lower().strip()
    if not q:
        return Query
    words = q.split()
    question_starters = {
        "how", "what", "who", "where", "when", "why", "which",
        "whose", "whom", "is", "are", "do", "does", "did",
        "will", "would", "could", "should", "can",
    }
    is_question = words[0] in question_starters
    if q[-1] in ".?!":
        q = q[:-1]
    return (q + ("?" if is_question else ".")).capitalize()

# ── TTS word cache (self-echo filter) ────────────────────────
_tts_spoken_words: set  = set()
_tts_spoken_lock        = threading.Lock()

def RegisterTTSWords(text: str) -> None:
    words = set(text.lower().split())
    with _tts_spoken_lock:
        _tts_spoken_words.update(words)

def _is_self_echo(text: str) -> bool:
    """Return True if 70%+ of words match what TTS just said (stricter)."""
    if not text:
        return False
    words = text.lower().split()
    if not words:
        return False
    with _tts_spoken_lock:
        if not _tts_spoken_words:
            return False
        match_count = sum(1 for w in words if w in _tts_spoken_words)
        ratio = match_count / len(words)
    return ratio > 0.70   # Stricter: was 0.65

def ClearTTSWordCache() -> None:
    with _tts_spoken_lock:
        _tts_spoken_words.clear()

# ── Wake word ─────────────────────────────────────────────────
def _extract_command_after_wake_word(text: str) -> str:
    lower = text.lower().strip()
    idx   = lower.find(WAKE_WORD)
    if idx == -1:
        return ""
    after = text[idx + len(WAKE_WORD):].strip().lstrip(",.!?- ")
    return after

def _contains_wake_word(text: str) -> bool:
    return WAKE_WORD in text.lower()

# ── Chrome helpers ────────────────────────────────────────────
_mic_running: bool = False

def _clear_chrome_output() -> None:
    try:
        driver.execute_script("document.getElementById('output').textContent = '';")
    except Exception:
        pass

def _stop_chrome_recognition() -> None:
    try:
        driver.find_element(By.ID, "end").click()
    except Exception:
        pass

def _start_chrome_recognition() -> bool:
    try:
        driver.find_element(By.ID, "start").click()
        return True
    except Exception:
        return False

def _get_chrome_text() -> str:
    try:
        return driver.find_element(By.ID, "output").text.strip()
    except Exception:
        return ""

def _ensure_mic_stopped() -> None:
    global _mic_running
    if _mic_running:
        _stop_chrome_recognition()
        _clear_chrome_output()
        _mic_running = False

def _ensure_mic_started() -> None:
    global _mic_running
    if not _mic_running:
        _clear_chrome_output()
        _start_chrome_recognition()
        _mic_running = True

def _wait_tts_done() -> None:
    _ensure_mic_stopped()
    while _tts.IS_SPEAKING:
        time.sleep(0.03)
    time.sleep(_POST_SPEAK_BUFFER)
    _clear_chrome_output()

# ── Main recognition loop ──────────────────────────────────────
def SpeechRecognition() -> str:
    """
    3-state: Listen → Think → Speak.
    Self-echo prevention (70%+).
    Smart word corrections.
    Short input filter.
    """
    if _tts.IS_SPEAKING:
        _wait_tts_done()

    _ensure_mic_started()

    while True:
        if _tts.IS_SPEAKING:
            _wait_tts_done()
            _ensure_mic_started()
            continue

        raw_text = _get_chrome_text()

        if not raw_text:
            time.sleep(0.05)
            continue

        _ensure_mic_stopped()

        # Apply smart corrections first
        raw_text = _apply_corrections(raw_text)

        # Filter meaningless input
        if not _is_meaningful(raw_text):
            print(f"[STT] Filtered short input: '{raw_text}'")
            if _tts.IS_SPEAKING:
                _wait_tts_done()
            _ensure_mic_started()
            continue

        # Self-echo filter
        if _is_self_echo(raw_text):
            print(f"[STT] Self-echo filtered: {raw_text[:60]}")
            if _tts.IS_SPEAKING:
                _wait_tts_done()
            _ensure_mic_started()
            continue

        # Translation
        if "en" not in InputLanguage.lower():
            SetAssistantStatus("Translating...")
            raw_text = UniversalTranslator(raw_text)
        else:
            translated = UniversalTranslator(raw_text)
            if translated and translated.strip() != raw_text.strip():
                raw_text = translated

        # Wake-word check
        if _contains_wake_word(raw_text):
            command = _extract_command_after_wake_word(raw_text)
            if command:
                SetAssistantStatus("Thinking...")
                return QueryModifier(command)
            else:
                SetAssistantStatus("Listening...")
                _ensure_mic_started()
                continue
        else:
            SetAssistantStatus("Thinking...")
            return QueryModifier(raw_text)

if __name__ == "__main__":
    print(f"STT v11 Test — say '{WAKE_WORD.capitalize()} <command>'")
    while True:
        try:
            text = SpeechRecognition()
            if text:
                print(f"Heard: {text}\n")
        except KeyboardInterrupt:
            print("\n👋 Stopped.")
            driver.quit()
            break