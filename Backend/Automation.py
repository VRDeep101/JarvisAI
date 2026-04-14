# ─────────────────────────────────────────────────────────────
#  Automation.py  —  Jarvis System Automation
#  - Volume up/down FIX (pycaw use karo — reliable)
#  - App open: desktop pehle, phir Google
#  - Fast execution
# ─────────────────────────────────────────────────────────────

from AppOpener import close, open as appopen
from pywhatkit import search, playonyt
from dotenv import dotenv_values
from bs4 import BeautifulSoup
from rich import print
from groq import Groq
import webbrowser
import subprocess
import requests
import asyncio
import os

# ── Volume Control — pycaw (reliable Windows) ────────────────
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    import comtypes
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False
    print("[yellow]⚠️ pycaw not found — using keyboard fallback for volume[/yellow]")
    try:
        import keyboard
        KEYBOARD_AVAILABLE = True
    except ImportError:
        KEYBOARD_AVAILABLE = False

# ── CodeWriter Optional ────────────────────────────────────────
try:
    from Backend.CodeWriter import WriteCode
    CODE_WRITER_AVAILABLE = True
except ImportError:
    try:
        from CodeWriter import WriteCode
        CODE_WRITER_AVAILABLE = True
    except ImportError:
        CODE_WRITER_AVAILABLE = False

# ── ENV Setup ─────────────────────────────────────────────────
env_vars   = dotenv_values(".env")
GroqAPIKey = env_vars.get("GroqAPIKey")
Username   = env_vars.get("Username", "User")

client = Groq(api_key=GroqAPIKey)

USERAGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/100.0.4896.75 Safari/537.36"
)

GROQ_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = [{
    "role": "system",
    "content": (
        f"Hello, I am {Username}. You are a professional content writer. "
        "Write well-structured, formal content. Keep the tone professional."
    ),
}]

messages = []

# ── Google Search ──────────────────────────────────────────────
def GoogleSearch(topic: str) -> bool:
    search(topic)
    return True

# ── Content Writer ─────────────────────────────────────────────
def Content(topic: str) -> bool:
    def open_notepad(filepath):
        subprocess.Popen(["notepad.exe", filepath])

    def write_with_ai(prompt):
        messages.append({"role": "user", "content": prompt})
        completion = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=SYSTEM_PROMPT + messages,
            max_tokens=2048,
            temperature=0.7,
            stream=True,
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
    filepath  = os.path.join("Data", f"{safe_name}.txt")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content_text)
    open_notepad(filepath)
    return True

# ── YouTube ────────────────────────────────────────────────────
def YouTubeSearch(topic: str) -> bool:
    webbrowser.open(f"https://www.youtube.com/results?search_query={topic}")
    return True

def PlayYoutube(query: str) -> bool:
    playonyt(query)
    return True

# ── App Open / Close ───────────────────────────────────────────
_session = requests.Session()

def _extract_links(html: str) -> list:
    soup  = BeautifulSoup(html, "html.parser")
    links = soup.find_all("a", {"jsname": "UWckNb"})
    return [link.get("href") for link in links]

def _open_in_chrome(query: str) -> bool:
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
    # Step 1: Known websites — open directly in Chrome
    site_map = {
        "claude":    "https://claude.ai",
        "chatgpt":   "https://chatgpt.com",
        "gmail":     "https://mail.google.com",
        "youtube":   "https://youtube.com",
        "whatsapp":  "https://web.whatsapp.com",
        "instagram": "https://instagram.com",
        "twitter":   "https://twitter.com",
        "facebook":  "https://facebook.com",
        "github":    "https://github.com",
    }
    for keyword, url in site_map.items():
        if keyword in app.lower():
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            for chrome_path in chrome_paths:
                if os.path.exists(chrome_path):
                    subprocess.Popen([chrome_path, url])
                    return True
            webbrowser.open(url)
            return True

    # Step 2: Installed desktop apps
    try:
        appopen(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception:
        pass

    # Step 3: Google search fallback
    return _open_in_chrome(app)


def CloseApp(app: str) -> bool:
    if "chrome" in app.lower():
        return False
    try:
        close(app, match_closest=True, output=True, throw_error=True)
        return True
    except Exception:
        return False


# ── Volume Control — FIXED ─────────────────────────────────────
def _get_volume_interface():
    """Get Windows audio endpoint — pycaw se."""
    try:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as e:
        print(f"[Volume] Could not get audio interface: {e}")
        return None


def System(command: str) -> bool:
    cmd = command.lower().strip()

    if PYCAW_AVAILABLE:
        volume = _get_volume_interface()
        if volume is None:
            return False

        try:
            if cmd in ("mute", "unmute"):
                current = volume.GetMute()
                volume.SetMute(0 if current else 1, None)
                return True

            elif cmd == "volume up":
                current_vol = volume.GetMasterVolumeLevelScalar()
                new_vol = min(1.0, current_vol + 0.10)  # +10%
                volume.SetMasterVolumeLevelScalar(new_vol, None)
                print(f"[Volume] Volume up → {int(new_vol * 100)}%")
                return True

            elif cmd == "volume down":
                current_vol = volume.GetMasterVolumeLevelScalar()
                new_vol = max(0.0, current_vol - 0.10)  # -10%
                volume.SetMasterVolumeLevelScalar(new_vol, None)
                print(f"[Volume] Volume down → {int(new_vol * 100)}%")
                return True

            elif cmd.startswith("set volume"):
                # "set volume 50" → set to 50%
                try:
                    level = int(cmd.replace("set volume", "").strip()) / 100
                    level = max(0.0, min(1.0, level))
                    volume.SetMasterVolumeLevelScalar(level, None)
                    print(f"[Volume] Set to {int(level * 100)}%")
                    return True
                except Exception:
                    pass

        except Exception as e:
            print(f"[Volume] pycaw error: {e}")

    # ── Keyboard fallback ──
    elif KEYBOARD_AVAILABLE:
        _kb_actions = {
            "mute":        "volume mute",
            "unmute":      "volume mute",
            "volume up":   "volume up",
            "volume down": "volume down",
        }
        key = _kb_actions.get(cmd)
        if key:
            import keyboard
            keyboard.press_and_release(key)
            return True

    # ── subprocess fallback (nircmd) ──
    nircmd_actions = {
        "volume up":   ["nircmd.exe", "changesysvolume", "6553"],
        "volume down": ["nircmd.exe", "changesysvolume", "-6553"],
        "mute":        ["nircmd.exe", "mutesysvolume", "1"],
        "unmute":      ["nircmd.exe", "mutesysvolume", "0"],
    }
    if cmd in nircmd_actions:
        try:
            subprocess.Popen(nircmd_actions[cmd])
            return True
        except Exception:
            pass

    print(f"[System] Command not handled: {command}")
    return False


# ── Async Dispatcher ───────────────────────────────────────────
async def TranslateAndExecute(commands: list):
    funcs = []

    for command in commands:
        cmd = command.strip()

        if cmd.startswith("open"):
            app_name = cmd.removeprefix("open").strip()
            if app_name in ("it", "file", ""):
                continue
            funcs.append(asyncio.to_thread(OpenApp, app_name))

        elif cmd.startswith("close"):
            funcs.append(asyncio.to_thread(CloseApp, cmd.removeprefix("close").strip()))

        elif cmd.startswith("play"):
            funcs.append(asyncio.to_thread(PlayYoutube, cmd.removeprefix("play").strip()))

        elif cmd.startswith("content"):
            funcs.append(asyncio.to_thread(Content, cmd.removeprefix("content").strip()))

        elif cmd.startswith(("writecode", "write code", "code")):
            if CODE_WRITER_AVAILABLE:
                clean = cmd.replace("writecode", "").replace("write code", "").replace("code", "").strip()
                funcs.append(asyncio.to_thread(WriteCode, clean))
            else:
                print("[red]CodeWriter not available.[/red]")

        elif cmd.startswith("google search"):
            funcs.append(asyncio.to_thread(GoogleSearch, cmd.removeprefix("google search").strip()))

        elif cmd.startswith("youtube search"):
            funcs.append(asyncio.to_thread(YouTubeSearch, cmd.removeprefix("youtube search").strip()))

        elif cmd.startswith("system"):
            funcs.append(asyncio.to_thread(System, cmd.removeprefix("system").strip()))

        elif cmd.startswith(("general", "realtime")):
            pass  # handled by chatbot/realtime engine

        else:
            print(f"[yellow]No handler for:[/yellow] {cmd}")

    results = await asyncio.gather(*funcs, return_exceptions=True)
    for result in results:
        yield result


async def Automation(commands: list) -> bool:
    async for _ in TranslateAndExecute(commands):
        pass
    return True