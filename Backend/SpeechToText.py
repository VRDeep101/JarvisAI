# ─────────────────────────────────────────────────────────────
#  SpeechToText.py  —  Jarvis Voice Input  [FIXED v2]
#  Fixes:
#  - IS_SPEAKING check is tight (50ms polling)
#  - Chrome output cleared BEFORE restarting recognition
#  - No self-loop: waits fully until IS_SPEAKING = False
#  - Reduced recognition delay (faster result detection loop)
#  - headless Chrome, fake mic, allow file access
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
import threading
import itertools
import sys

# ── IS_SPEAKING flag from TextToSpeech ────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
import TextToSpeech as _tts

env_vars      = dotenv_values(".env")
InputLanguage = env_vars.get("InputLanguage", "en-IN")

# ── Voice HTML ─────────────────────────────────────────────────
HtmlCode = f'''<!DOCTYPE html>
<html lang="en">
<head><title>Speech Recognition</title></head>
<body>
<button id="start" onclick="startRecognition()">Start</button>
<button id="end"   onclick="stopRecognition()">Stop</button>
<p id="output"></p>
<script>
    const output = document.getElementById('output');
    let recognition;

    function startRecognition() {{
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang            = '{InputLanguage}';
        recognition.continuous      = true;
        recognition.interimResults  = false;
        recognition.maxAlternatives = 1;
        recognition._stopped        = false;

        recognition.onresult = function(event) {{
            const result = event.results[event.results.length - 1];
            if (result.isFinal) {{
                output.textContent = result[0].transcript.trim();
            }}
        }};

        recognition.onend = function() {{
            if (!recognition._stopped) recognition.start();
        }};

        recognition.onerror = function(event) {{
            if (event.error !== 'no-speech') output.textContent = '';
        }};

        recognition.start();
    }}

    function stopRecognition() {{
        if (recognition) {{
            recognition._stopped = true;
            recognition.stop();
        }}
        output.textContent = '';
    }}

    function clearOutput() {{
        output.textContent = '';
    }}
</script>
</body>
</html>'''

os.makedirs("Data", exist_ok=True)
with open(os.path.join("Data", "Voice.html"), "w") as f:
    f.write(HtmlCode)

current_dir = os.getcwd()
Link        = f"file:///{current_dir}/Data/Voice.html"
TempDirPath = os.path.join(current_dir, "Frontend", "Files")
os.makedirs(TempDirPath, exist_ok=True)

# ── Safe File Helpers ─────────────────────────────────────────
def _safe_read(filepath: str, retries: int = 5, delay: float = 0.2) -> str:
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            time.sleep(delay)
        except FileNotFoundError:
            return ""
    return ""


def _safe_write(filepath: str, content: str, retries: int = 5, delay: float = 0.2) -> bool:
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except PermissionError:
            time.sleep(delay)
    return False


# ── Chrome Setup ──────────────────────────────────────────────
chrome_options = Options()
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")
chrome_options.add_argument("--allow-file-access-from-files")
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--window-position=-10000,0")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
)

print("⚙️  Setting up Jarvis...")
driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)
driver.get(Link)
time.sleep(0.6)
print("✅ Jarvis is ready!\n")


# ── Helpers ───────────────────────────────────────────────────
def SetAssistantStatus(Status: str) -> None:
    path = os.path.join(TempDirPath, "Status.data")
    _safe_write(path, Status)


def UniversalTranslator(Text: str) -> str:
    try:
        return mt.translate(Text, "en", "auto")
    except Exception:
        return Text


def QueryModifier(Query: str) -> str:
    q = Query.lower().strip()
    if not q:
        return Query
    words = q.split()
    question_starters = {
        "how", "what", "who", "where", "when", "why", "which",
        "whose", "whom", "is", "are", "do", "does", "did",
        "will", "would", "could", "should", "can"
    }
    is_question = words[0] in question_starters
    if q[-1] in ".?!":
        q = q[:-1]
    return (q + ("?" if is_question else ".")).capitalize()


def _clear_chrome_output():
    """Clear the recognition output box in Chrome."""
    try:
        driver.execute_script("document.getElementById('output').textContent = '';")
    except Exception:
        pass


def _stop_chrome_recognition():
    try:
        driver.find_element(By.ID, "end").click()
    except Exception:
        pass


def _start_chrome_recognition():
    try:
        driver.find_element(By.ID, "start").click()
        return True
    except Exception:
        return False


# ── Main Voice Recognition ─────────────────────────────────────
def SpeechRecognition() -> str:
    """
    Listens for user voice input.
    - Blocks while Jarvis is speaking (IS_SPEAKING = True)
    - Clears output before starting to avoid picking up own voice
    - Fast 50ms polling loop for minimal delay
    """

    # ── Wait if Jarvis is currently speaking ─────────────────
    while _tts.IS_SPEAKING and not _tts._internal_audio_mode:
        time.sleep(0.05)

    # ── Clear any stale output first ─────────────────────────
    _clear_chrome_output()

    # ── Start recognition ─────────────────────────────────────
    if not _start_chrome_recognition():
        return ""

    # ── Polling loop — fast 50ms ──────────────────────────────
    while True:

        # If Jarvis starts speaking mid-listen, stop and wait
        if _tts.IS_SPEAKING and not _tts._internal_audio_mode:
            _stop_chrome_recognition()
            _clear_chrome_output()

            while _tts.IS_SPEAKING and not _tts._internal_audio_mode:
                time.sleep(0.05)

            # Restart cleanly
            _clear_chrome_output()
            if not _start_chrome_recognition():
                return ""

        # Check for recognized text
        try:
            text = driver.find_element(By.ID, "output").text.strip()
            if text:
                _stop_chrome_recognition()
                _clear_chrome_output()

                if "en" not in InputLanguage.lower():
                    SetAssistantStatus("Translating...")
                    text = UniversalTranslator(text)

                return QueryModifier(text)
        except Exception:
            pass

        time.sleep(0.05)   # 50ms — fast polling


if __name__ == "__main__":
    while True:
        try:
            text = SpeechRecognition()
            if text:
                print(f"You: {text}\n")
        except KeyboardInterrupt:
            print("\n👋 Jarvis stopped.")
            driver.quit()
            break
        except EOFError:
            continue