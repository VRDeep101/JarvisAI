# Import required libraries
from AppOpener import close, open as appopen
from pywhatkit import search, playonyt
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from rich import print
from groq import Groq
from CodeWriter import WriteCode          # ← Claude API, code only
import webbrowser
import subprocess
import requests
import keyboard
import asyncio
import os

# ── Environment & Client Setup ─────────────────────────────────────────────────
env_vars   = dotenv_values(".env")
GroqAPIKey = env_vars.get("GroqAPIKey")
Username   = env_vars.get("Username", "User")

client = Groq(api_key=GroqAPIKey)         # Groq — everything except code

# ── Constants ──────────────────────────────────────────────────────────────────
USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/100.0.4896.75 Safari/537.36"
)

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = [
    {
        "role": "system",
        "content": (
            f"Hello, I am {Username}. You are a professional content writer. "
            "Write well-structured, formal content such as letters, applications, "
            "emails, and essays. Keep the tone professional and the format clean."
        ),
    }
]

messages = []

# ── Google Search ──────────────────────────────────────────────────────────────
def GoogleSearch(topic: str) -> bool:
    search(topic)
    return True

# ── Content Writer (Groq) ──────────────────────────────────────────────────────
def Content(topic: str) -> bool:
    """Generate written content via Groq and open it in Notepad."""

    def open_notepad(filepath: str) -> None:
        subprocess.Popen(["notepad.exe", filepath])

    def write_with_ai(prompt: str) -> str:
        messages.append({"role": "user", "content": prompt})

        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=SYSTEM_PROMPT + messages,
            max_tokens=2048,
            temperature=0.7,
            top_p=1,
            stream=True,
            stop=None,
        )

        answer = ""
        for chunk in completion:
            delta = chunk.choices[0].delta.content
            if delta:
                answer += delta

        answer = answer.replace("</s>", "").strip()
        messages.append({"role": "assistant", "content": answer})
        return answer

    clean_topic  = topic.replace("Content", "").strip()
    content_text = write_with_ai(clean_topic)

    os.makedirs("Data", exist_ok=True)
    safe_name = clean_topic.lower().replace(" ", "_")
    filepath  = rf"Data\{safe_name}.txt"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content_text)

    open_notepad(filepath)
    return True

# ── YouTube ────────────────────────────────────────────────────────────────────
def YouTubeSearch(topic: str) -> bool:
    webbrowser.open(f"https://www.youtube.com/results?search_query={topic}")
    return True

def PlayYoutube(query: str) -> bool:
    playonyt(query)
    return True

# ── App Open / Close ───────────────────────────────────────────────────────────
_session = requests.Session()

def _extract_links(html: str) -> list:
    soup  = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", {"jsname": "UWckNb"})
    return [link.get("href") for link in links]

def _open_in_chrome(query: str) -> bool:
    """Search Google for query and open first result in Chrome."""
    target_url = f"https://www.google.com/search?q={query}"
    try:
        response = _session.get(
            target_url,
            headers={"User-Agent": USERAGENT},
            timeout=8,
        )
        if response.status_code == 200:
            links = _extract_links(response.text)
            if links and links[0]:
                target_url = links[0]
    except Exception:
        pass

    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            subprocess.Popen([chrome_path, target_url])
            return True

    webbrowser.open(target_url)
    return True

def OpenApp(app: str) -> bool:
    try:
        appopen(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception:
        print(f"[yellow]'{app}' not found locally. Searching and opening in Chrome...[/yellow]")
        return _open_in_chrome(app)

def CloseApp(app: str) -> bool:
    if "chrome" in app.lower():
        return False
    try:
        close(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception:
        return False

# ── System Controls ────────────────────────────────────────────────────────────
def System(command: str) -> bool:
    _actions = {
        "mute":        "volume mute",
        "unmute":      "volume mute",
        "volume up":   "volume up",
        "volume down": "volume down",
    }
    key = _actions.get(command.lower())
    if key:
        keyboard.press_and_release(key)
    return True

# ── Async Dispatcher ───────────────────────────────────────────────────────────
async def TranslateAndExecute(commands: list[str]):
    funcs = []

    for command in commands:
        cmd = command.strip()

        if cmd.startswith("open"):
            if "open it" in cmd or "open file" in cmd:
                continue
            funcs.append(asyncio.to_thread(OpenApp, cmd.removeprefix("open").strip()))

        elif cmd.startswith("close"):
            funcs.append(asyncio.to_thread(CloseApp, cmd.removeprefix("close").strip()))

        elif cmd.startswith("play"):
            funcs.append(asyncio.to_thread(PlayYoutube, cmd.removeprefix("play").strip()))

        elif cmd.startswith("content"):
            funcs.append(asyncio.to_thread(Content, cmd.removeprefix("content").strip()))

        # ── Code writing → Claude API (CodeWriter.py) ─────────────────────
        elif cmd.startswith("writecode") or cmd.startswith("write code") or cmd.startswith("code"):
            clean = (
                cmd.removeprefix("writecode")
                   .removeprefix("write code")
                   .removeprefix("code")
                   .strip()
            )
            funcs.append(asyncio.to_thread(WriteCode, clean))

        elif cmd.startswith("google search"):
            funcs.append(asyncio.to_thread(GoogleSearch, cmd.removeprefix("google search").strip()))

        elif cmd.startswith("youtube search"):
            funcs.append(asyncio.to_thread(YouTubeSearch, cmd.removeprefix("youtube search").strip()))

        elif cmd.startswith("system"):
            funcs.append(asyncio.to_thread(System, cmd.removeprefix("system").strip()))

        elif cmd.startswith("general") or cmd.startswith("realtime"):
            pass

        else:
            print(f"[yellow]No handler found for:[/yellow] {cmd}")

    results = await asyncio.gather(*funcs)
    for result in results:
        yield result

# ── Main Entry Point ───────────────────────────────────────────────────────────
async def Automation(commands: list[str]) -> bool:
    async for _ in TranslateAndExecute(commands):
        pass
    return True