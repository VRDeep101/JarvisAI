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

env_vars = dotenv_values(".env")
InputLanguage = env_vars.get("InputLanguage", "en-IN")

HtmlCode = f'''<!DOCTYPE html>
<html lang="en">
<head><title>Speech Recognition</title></head>
<body>
<button id="start" onclick="startRecognition()">Start</button>
<button id="end" onclick="stopRecognition()">Stop</button>
<p id="output"></p>
<script>
    const output = document.getElementById('output');
    let recognition;

    function startRecognition() {{
        recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
        recognition.lang = '{InputLanguage}';
        recognition.continuous = true;
        recognition.interimResults = false;
        recognition.maxAlternatives = 1;
        recognition._stopped = false;

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
</script>
</body>
</html>'''

os.makedirs("Data", exist_ok=True)
with open("Data/Voice.html", "w") as f:
    f.write(HtmlCode)

current_dir = os.getcwd()
Link = f"file:///{current_dir}/Data/Voice.html"

TempDirPath = rf"{current_dir}/Frontend/Files"


# ── Animations ──────────────────────────────────────────────

def animate(frames, stop_event, delay=0.4):
    for frame in itertools.cycle(frames):
        if stop_event.is_set():
            break
        sys.stdout.write(f"\r{frame}")
        sys.stdout.flush()
        time.sleep(delay)
    sys.stdout.write("\r" + " " * 40 + "\r")
    sys.stdout.flush()


def run_animation(frames, delay=0.4):
    stop_event = threading.Event()
    t = threading.Thread(target=animate, args=(frames, stop_event, delay), daemon=True)
    t.start()
    return stop_event, t


def stop_animation(stop_event, t):
    stop_event.set()
    t.join()


# ── Chrome Setup ─────────────────────────────────────────────

setup_frames = [
    "⚙️  Setting up your Jarvis   ",
    "⚙️  Setting up your Jarvis.  ",
    "⚙️  Setting up your Jarvis.. ",
    "⚙️  Setting up your Jarvis...",
]
stop_event, t = run_animation(setup_frames)

chrome_options = Options()
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")
chrome_options.add_argument("--allow-file-access-from-files")
chrome_options.add_argument("--window-position=-10000,0")
chrome_options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
)

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=chrome_options
)
driver.get(Link)
time.sleep(0.8)

stop_animation(stop_event, t)
print("✅ Jarvis is ready!\n")


# ── Helpers ───────────────────────────────────────────────────

def SetAssistantStatus(Status):
    os.makedirs(TempDirPath, exist_ok=True)
    with open(rf"{TempDirPath}/Status.data", "w", encoding="utf-8") as f:
        f.write(Status)


def UniversalTranslator(Text):
    return mt.translate(Text, "en", "auto")


def QueryModifier(Query):
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


# ── Main Loop ─────────────────────────────────────────────────

def SpeechRecognition():
    # Recognising animation shuru
    rec_frames = [
        
        "🎙  Recognising Voice...",
    ]
    stop_event, t = run_animation(rec_frames)

    driver.find_element(By.ID, "start").click()

    while True:
        try:
            text = driver.find_element(By.ID, "output").text.strip()
            if text:
                stop_animation(stop_event, t)
                driver.find_element(By.ID, "end").click()
                if "en" in InputLanguage.lower():
                    return QueryModifier(text)
                else:
                    SetAssistantStatus("Translating...")
                    return QueryModifier(UniversalTranslator(text))
        except Exception:
            pass
        time.sleep(0.1)


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