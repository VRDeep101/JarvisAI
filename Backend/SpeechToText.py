from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from dotenv import dotenv_values
import os
import mtranslate as mt
import time

# .env se InputLanguage lo
env_vars = dotenv_values(".env")
InputLanguage = env_vars.get("InputLanguage")

HtmlCode = '''<!DOCTYPE html>
<html lang="en">
<head>
    <title>Speech Recognition</title>
</head>
<body>
    <button id="start" onclick="startRecognition()">Start Recognition</button>
    <button id="end" onclick="stopRecognition()">Stop Recognition</button>
    <p id="output"></p>
    <script>
        const output = document.getElementById('output');
        let recognition;

        function startRecognition() {
            recognition = new webkitSpeechRecognition() || new SpeechRecognition();
            recognition.lang = 'en-IN';
            recognition.continuous = true;
            recognition.interimResults = false;

            recognition.onresult = function(event) {
                const transcript = event.results[event.results.length - 1][0].transcript;
                output.textContent += transcript;
            };

            recognition.onend = function() {
                recognition.start();
            };

            recognition.onerror = function(event) {
                output.textContent = '';
            };

            recognition.start();
        }

        function stopRecognition() {
            recognition.stop();
            output.innerHTML = "";
        }
    </script>
</body>
</html>'''

# Replace lang dynamically from .env
HtmlCode = HtmlCode.replace(
    "recognition.lang = 'en-IN';",
    "recognition.lang = '" + InputLanguage + "';"
)

os.makedirs("Data", exist_ok=True)
with open("Data/Voice.html", "w") as f:
    f.write(HtmlCode)

current_dir = os.getcwd()
Link = f"{current_dir}/Data/Voice.html"

chrome_options = Options()
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36"
chrome_options.add_argument(f"user-agent={user_agent}")
chrome_options.add_argument("--use-fake-ui-for-media-stream")       # mic permission auto-allow
chrome_options.add_argument("--use-fake-device-for-media-stream")   # fake mic device use karo
chrome_options.add_argument("--allow-file-access-from-files")
chrome_options.add_argument("--origin-trial-disabled-features=WebSpeechAPI")
chrome_options.add_argument("--disable-features=MediaStreamTrack")
# HEADLESS HATA DIYA — Speech API headless mein kaam nahi karti
# Agar window dikhna nahi chahte toh yeh lagao:
chrome_options.add_argument("--window-position=-10000,0")  # window screen ke bahar

chrome_service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=chrome_service, options=chrome_options)

TempDirPath = rf"{current_dir}/Frontend/Files"


def SetAssistantStatus(Status):
    os.makedirs(TempDirPath, exist_ok=True)
    with open(rf"{TempDirPath}/Status.data", "w", encoding="utf-8") as files:
        files.write(Status)


def UniversalTranslator(Text):
    return mt.translate(Text, "en", "auto")


def QueryModifier(Query):
    new_query = Query.lower().strip()
    query_words = new_query.split()

    if not query_words:
        return Query

    question_words = [
        "how", "what", "who", "where", "when", "why", "which",
        "whose", "whom", "can you", "what's", "how's"
    ]

    is_question = any(new_query.startswith(word) for word in question_words)

    if is_question:
        if query_words[-1][-1] in ['.', '?', '!']:
            new_query = new_query[:-1] + "?"
        else:
            new_query += "?"
    else:
        if query_words[-1][-1] in ['.', '?', '!']:
            new_query = new_query[:-1] + "."
        else:
            new_query += "."

    return new_query.capitalize()


def SpeechRecognition():
    driver.get("file:///" + Link)
    time.sleep(1)  # page load hone do
    driver.find_element(by=By.ID, value="start").click()

    while True:
        try:
            Text = driver.find_element(by=By.ID, value="output").text
            if Text:
                driver.find_element(by=By.ID, value="end").click()

                if "en" in InputLanguage.lower():
                    return QueryModifier(Text)
                else:
                    SetAssistantStatus("Translating...")
                    return QueryModifier(UniversalTranslator(Text))

        except Exception as e:
            pass


if __name__ == "__main__":
    while True:
        try:
            Text = SpeechRecognition()
            if not Text:
                continue
            print(Text)
        except KeyboardInterrupt:
            continue
        except EOFError:
            continue