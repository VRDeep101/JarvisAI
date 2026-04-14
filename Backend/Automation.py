# ─────────────────────────────────────────────────────────────
#  Automation.py  —  Jarvis System Automation  [FIXED v2]
#  Fixes:
#  - App open: checks installed apps FIRST, then web, no Google fallback for local apps
#  - WhatsApp, Spotify, VLC etc. open from desktop properly
#  - Volume up/down: pycaw primary, keyboard fallback
#  - Image generation: writes correct data file
#  - Content writer: working with file output
#  - generate image: handled via ImageGeneration.data
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

# ── Volume Control — pycaw ────────────────────────────────────
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
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

# ── ENV ────────────────────────────────────────────────────────
env_vars   = dotenv_values(".env")
GroqAPIKey = env_vars.get("GroqAPIKey")
Username   = env_vars.get("Username", "User")

client = Groq(api_key=GroqAPIKey)

USERAGENT  = (
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

# ── Known Desktop App Paths (Windows) ─────────────────────────
# Maps app name → common install paths to check
_DESKTOP_APP_PATHS = {
    "whatsapp": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "WhatsApp", "WhatsApp.exe"),
        os.path.join(os.environ.get("APPDATA", ""),      "Microsoft", "Windows", "Start Menu", "Programs", "WhatsApp.lnk"),
    ],
    "spotify": [
        os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WindowsApps", "Spotify.exe"),
    ],
    "discord": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"),
        os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Discord Inc", "Discord.lnk"),
    ],
    "vlc": [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "paint": ["mspaint.exe"],
    "settings": ["ms-settings:"],
    "camera": ["microsoft.windows.camera:"],
    "photos": ["ms-photos:"],
    "file explorer": ["explorer.exe"],
    "task manager": ["taskmgr.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
        r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
    "telegram": [
        os.path.join(os.environ.get("APPDATA", ""), "Telegram Desktop", "Telegram.exe"),
    ],
    "zoom": [
        os.path.join(os.environ.get("APPDATA", ""), "Zoom", "bin", "Zoom.exe"),
    ],
    "obs": [
        r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
        r"C:\Program Files (x86)\obs-studio\bin\32bit\obs32.exe",
    ],
    "vscode": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "visual studio code": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
    ],
}

# Known web apps — open in browser directly
_WEB_APP_MAP = {
    "claude":    "https://claude.ai",
    "chatgpt":   "https://chatgpt.com",
    "gmail":     "https://mail.google.com",
    "youtube":   "https://youtube.com",
    "instagram": "https://instagram.com",
    "twitter":   "https://twitter.com",
    "x":         "https://twitter.com",
    "facebook":  "https://facebook.com",
    "github":    "https://github.com",
    "reddit":    "https://reddit.com",
    "netflix":   "https://netflix.com",
    "amazon":    "https://amazon.in",
    "flipkart":  "https://flipkart.com",
    "whatsapp web": "https://web.whatsapp.com",
}

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
    if not clean_topic:
        return False
    content_text = write_with_ai(clean_topic)
    os.makedirs("Data", exist_ok=True)
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in clean_topic.lower()).replace(" ", "_")
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

# ── Chrome Helper ─────────────────────────────────────────────
_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

def _open_url_in_chrome(url: str) -> bool:
    for chrome_path in _CHROME_PATHS:
        if os.path.exists(chrome_path):
            subprocess.Popen([chrome_path, url])
            return True
    webbrowser.open(url)
    return True

# ── App Open ──────────────────────────────────────────────────
def OpenApp(app: str) -> bool:
    app_lower = app.lower().strip()

    # Step 1: Check known web apps
    for keyword, url in _WEB_APP_MAP.items():
        if keyword in app_lower:
            return _open_url_in_chrome(url)

    # Step 2: Check known desktop app paths
    for app_key, paths in _DESKTOP_APP_PATHS.items():
        if app_key in app_lower or app_lower in app_key:
            for path in paths:
                if path.endswith(":"):
                    # URI scheme (e.g. ms-settings:)
                    try:
                        os.startfile(path)
                        return True
                    except Exception:
                        pass
                elif os.path.exists(path):
                    try:
                        subprocess.Popen([path])
                        return True
                    except Exception:
                        pass
                elif not os.path.dirname(path):
                    # Just a filename like notepad.exe
                    try:
                        subprocess.Popen([path])
                        return True
                    except Exception:
                        pass

    # Step 3: Try AppOpener (installed apps via Start Menu)
    try:
        appopen(app, match_closest=True, output=False, throw_error=True)
        return True
    except Exception:
        pass

    # Step 4: Try os.startfile for apps that might be in PATH
    try:
        os.startfile(app_lower)
        return True
    except Exception:
        pass

    # Step 5: Last resort — Google search in Chrome (only for non-local queries)
    print(f"[AppOpen] Could not find '{app}' locally, searching online.")
    webbrowser.open(f"https://www.google.com/search?q={app}")
    return True


def CloseApp(app: str) -> bool:
    if "chrome" in app.lower():
        return False
    try:
        close(app, match_closest=True, output=False, throw_error=True)
        return True
    except Exception:
        pass

    # Try taskkill as fallback
    try:
        subprocess.run(["taskkill", "/f", "/im", f"{app}.exe"], capture_output=True)
        return True
    except Exception:
        return False


# ── Volume Control ─────────────────────────────────────────────
def _get_volume_interface():
    try:
        devices   = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception as e:
        print(f"[Volume] Could not get audio interface: {e}")
        return None


def System(command: str) -> bool:
    cmd = command.lower().strip()

    if PYCAW_AVAILABLE:
        volume = _get_volume_interface()
        if volume is not None:
            try:
                if cmd in ("mute", "unmute"):
                    current = volume.GetMute()
                    volume.SetMute(0 if current else 1, None)
                    return True

                elif cmd == "volume up":
                    current_vol = volume.GetMasterVolumeLevelScalar()
                    new_vol     = min(1.0, current_vol + 0.10)
                    volume.SetMasterVolumeLevelScalar(new_vol, None)
                    print(f"[Volume] Up → {int(new_vol * 100)}%")
                    return True

                elif cmd == "volume down":
                    current_vol = volume.GetMasterVolumeLevelScalar()
                    new_vol     = max(0.0, current_vol - 0.10)
                    volume.SetMasterVolumeLevelScalar(new_vol, None)
                    print(f"[Volume] Down → {int(new_vol * 100)}%")
                    return True

                elif cmd.startswith("set volume"):
                    try:
                        level = int(cmd.replace("set volume", "").strip()) / 100
                        level = max(0.0, min(1.0, level))
                        volume.SetMasterVolumeLevelScalar(level, None)
                        print(f"[Volume] Set → {int(level * 100)}%")
                        return True
                    except Exception:
                        pass

            except Exception as e:
                print(f"[Volume] pycaw error: {e}")

    # ── Keyboard fallback ──────────────────────────────────────
    if KEYBOARD_AVAILABLE:
        key_map = {
            "mute":        "volume mute",
            "unmute":      "volume mute",
            "volume up":   "volume up",
            "volume down": "volume down",
        }
        key = key_map.get(cmd)
        if key:
            keyboard.press_and_release(key)
            return True

    # ── nircmd fallback ────────────────────────────────────────
    nircmd_map = {
        "volume up":   ["nircmd.exe", "changesysvolume", "6553"],
        "volume down": ["nircmd.exe", "changesysvolume", "-6553"],
        "mute":        ["nircmd.exe", "mutesysvolume",   "1"],
        "unmute":      ["nircmd.exe", "mutesysvolume",   "0"],
    }
    if cmd in nircmd_map:
        try:
            subprocess.Popen(nircmd_map[cmd])
            return True
        except Exception:
            pass

    print(f"[System] Command not handled: {command}")
    return False


# ── Image Generation ───────────────────────────────────────────
def TriggerImageGeneration(query: str) -> bool:
    """
    Write image generation query to file and launch subprocess.
    """
    clean = query.strip()
    os.makedirs("Frontend/Files", exist_ok=True)
    filepath = os.path.join("Frontend", "Files", "ImageGeneration.data")
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"{clean},True")
        print(f"[ImageGen] Triggered: {clean}")
        return True
    except Exception as e:
        print(f"[ImageGen] Write error: {e}")
        return False


# ── Async Dispatcher ───────────────────────────────────────────
async def TranslateAndExecute(commands: list):
    funcs = []

    for command in commands:
        cmd = command.strip().lower()

        if cmd.startswith("open"):
            app_name = command.strip()[4:].strip()
            if app_name and app_name not in ("it", "file", ""):
                funcs.append(asyncio.to_thread(OpenApp, app_name))

        elif cmd.startswith("close"):
            funcs.append(asyncio.to_thread(CloseApp, command.strip()[5:].strip()))

        elif cmd.startswith("play"):
            funcs.append(asyncio.to_thread(PlayYoutube, command.strip()[4:].strip()))

        elif cmd.startswith("content"):
            funcs.append(asyncio.to_thread(Content, command.strip()[7:].strip()))

        elif cmd.startswith(("writecode", "write code", "code")):
            if CODE_WRITER_AVAILABLE:
                clean = cmd.replace("writecode", "").replace("write code", "").replace("code", "").strip()
                funcs.append(asyncio.to_thread(WriteCode, clean))
            else:
                print("[red]CodeWriter not available.[/red]")

        elif cmd.startswith("google search"):
            funcs.append(asyncio.to_thread(GoogleSearch, command.strip()[13:].strip()))

        elif cmd.startswith("youtube search"):
            funcs.append(asyncio.to_thread(YouTubeSearch, command.strip()[14:].strip()))

        elif cmd.startswith("system"):
            funcs.append(asyncio.to_thread(System, command.strip()[6:].strip()))

        elif cmd.startswith("generate"):
            raw = command.strip()[8:].strip()
            for prefix in ["image ", "images ", "image", "images"]:
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):].strip()
                    break
            funcs.append(asyncio.to_thread(TriggerImageGeneration, raw))

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