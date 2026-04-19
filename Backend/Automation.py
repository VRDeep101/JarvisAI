# ─────────────────────────────────────────────────────────────
#  Automation.py  —  Jarvis System Automation  [FIXED v3]
#
#  NEW FEATURES:
#  - Screenshot: "take screenshot" → PIL + pywin32
#  - Screen recording: "start screen recording" → OBS/subprocess
#  - Bluetooth: "enable/disable bluetooth"
#  - Brightness: "brightness up/down/set 50"
#  - Lock screen: "lock screen"
#  - Snap/pause handling integrated
#  - All previous fixes retained
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
import time
import datetime

# ── AIWebBrowser ──────────────────────────────────────────────
try:
    from Backend.AIWebBrowser import ask_ai_website, route_query, get_pre_message
    AI_WEB_AVAILABLE = True
except ImportError:
    AI_WEB_AVAILABLE = False

# ── Volume Control ────────────────────────────────────────────
try:
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    PYCAW_AVAILABLE = True
except ImportError:
    PYCAW_AVAILABLE = False

try:
    import keyboard
    KEYBOARD_AVAILABLE = True
except ImportError:
    KEYBOARD_AVAILABLE = False

# ── Screenshot ────────────────────────────────────────────────
try:
    from PIL import ImageGrab
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# ── Screen Brightness ─────────────────────────────────────────
try:
    import screen_brightness_control as sbc
    SBC_AVAILABLE = True
except ImportError:
    SBC_AVAILABLE = False

# ── CodeWriter ────────────────────────────────────────────────
try:
    from Backend.CodeWriter import WriteCode
    CODE_WRITER_AVAILABLE = True
except ImportError:
    try:
        from CodeWriter import WriteCode
        CODE_WRITER_AVAILABLE = True
    except ImportError:
        CODE_WRITER_AVAILABLE = False

# ── ENV ───────────────────────────────────────────────────────
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

# ── Known App Paths ───────────────────────────────────────────
_DESKTOP_APP_PATHS = {
    "whatsapp": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "WhatsApp", "WhatsApp.exe"),
    ],
    "spotify": [
        os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe"),
    ],
    "discord": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Discord", "app-*", "Discord.exe"),
    ],
    "vlc": [
        r"C:\Program Files\VideoLAN\VLC\vlc.exe",
        r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe",
    ],
    "notepad":       ["notepad.exe"],
    "calculator":    ["calc.exe"],
    "paint":         ["mspaint.exe"],
    "settings":      ["ms-settings:"],
    "camera":        ["microsoft.windows.camera:"],
    "photos":        ["ms-photos:"],
    "file explorer": ["explorer.exe"],
    "task manager":  ["taskmgr.exe"],
    "cmd":           ["cmd.exe"],
    "powershell":    ["powershell.exe"],
    "terminal":      ["wt.exe", "cmd.exe"],
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"C:\Program Files\Mozilla Firefox\firefox.exe",
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
    ],
    "vscode": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "visual studio code": [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Microsoft VS Code", "Code.exe"),
    ],
}

_WEB_APP_MAP = {
    "claude":        "https://claude.ai",
    "chatgpt":       "https://chatgpt.com",
    "gmail":         "https://mail.google.com",
    "youtube":       "https://youtube.com",
    "instagram":     "https://instagram.com",
    "twitter":       "https://twitter.com",
    "x":             "https://twitter.com",
    "facebook":      "https://facebook.com",
    "github":        "https://github.com",
    "reddit":        "https://reddit.com",
    "netflix":       "https://netflix.com",
    "amazon":        "https://amazon.in",
    "flipkart":      "https://flipkart.com",
    "whatsapp web":  "https://web.whatsapp.com",
}

_CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]

# ── Screenshot ────────────────────────────────────────────────
def TakeScreenshot(reason: str = "") -> bool:
    """
    Screenshot leke Data/Screenshots/ mein save karo.
    """
    os.makedirs("Data/Screenshots", exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath  = f"Data/Screenshots/screenshot_{timestamp}.png"

    if PIL_AVAILABLE:
        try:
            img = ImageGrab.grab()
            img.save(filepath)
            print(f"[Screenshot] Saved: {filepath}")
            try:
                os.startfile(os.path.abspath(filepath))
            except Exception:
                pass
            return True
        except Exception as e:
            print(f"[Screenshot] PIL error: {e}")

    # Fallback: Windows Snipping Tool
    try:
        subprocess.Popen(["snippingtool", "/clip"])
        return True
    except Exception:
        pass

    # Fallback: PrintScreen via keyboard
    if KEYBOARD_AVAILABLE:
        try:
            keyboard.press_and_release("printscreen")
            return True
        except Exception:
            pass

    return False

# ── Screen Recording ──────────────────────────────────────────
_screen_recording_proc = None

def StartScreenRecording() -> bool:
    """Start screen recording via OBS or Windows Game Bar."""
    global _screen_recording_proc

    # Try OBS first
    obs_paths = [r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"]
    for obs in obs_paths:
        if os.path.exists(obs):
            try:
                _screen_recording_proc = subprocess.Popen([obs, "--startrecording"])
                print("[ScreenRec] OBS recording started")
                return True
            except Exception:
                pass

    # Fallback: Windows Game Bar (Win+Alt+R)
    if KEYBOARD_AVAILABLE:
        try:
            keyboard.press_and_release("windows+alt+r")
            print("[ScreenRec] Windows Game Bar recording started")
            return True
        except Exception:
            pass

    return False

def StopScreenRecording() -> bool:
    global _screen_recording_proc
    if KEYBOARD_AVAILABLE:
        try:
            keyboard.press_and_release("windows+alt+r")
            print("[ScreenRec] Recording stopped")
            return True
        except Exception:
            pass
    if _screen_recording_proc:
        try:
            _screen_recording_proc.terminate()
            _screen_recording_proc = None
            return True
        except Exception:
            pass
    return False

# ── Bluetooth ─────────────────────────────────────────────────
def SetBluetooth(enable: bool) -> bool:
    """Enable/disable Bluetooth via PowerShell."""
    action = "Enable" if enable else "Disable"
    ps_cmd = (
        f"$bluetooth = [Windows.Devices.Radios.Radio,Windows.System.Devices,ContentType=WindowsRuntime];"
        f"$radios = [Windows.Devices.Radios.Radio]::GetRadiosAsync().GetResults();"
        f"foreach($radio in $radios) {{"
        f"if ($radio.Kind -eq 'Bluetooth') {{"
        f"$radio.SetStateAsync([Windows.Devices.Radios.RadioState]::{action}).GetResults()"
        f"}}}}"
    )
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_cmd],
            capture_output=True, timeout=10
        )
        print(f"[Bluetooth] {action}d")
        return True
    except Exception:
        # Fallback: open Bluetooth settings
        try:
            subprocess.Popen(["explorer.exe", "ms-settings:bluetooth"])
            return True
        except Exception:
            return False

# ── Brightness ────────────────────────────────────────────────
def SetBrightness(level: int = None, direction: str = None) -> bool:
    """Set/adjust screen brightness."""
    if SBC_AVAILABLE:
        try:
            current = sbc.get_brightness(display=0)[0]
            if direction == "up":
                new_level = min(100, current + 10)
            elif direction == "down":
                new_level = max(0, current - 10)
            elif level is not None:
                new_level = max(0, min(100, level))
            else:
                return False
            sbc.set_brightness(new_level)
            print(f"[Brightness] Set to {new_level}%")
            return True
        except Exception as e:
            print(f"[Brightness] sbc error: {e}")

    # Fallback: WMI
    try:
        if direction == "up":
            ps = "powershell (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [math]::Min(100, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness + 10))"
        elif direction == "down":
            ps = "powershell (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, [math]::Max(0, (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightness).CurrentBrightness - 10))"
        elif level is not None:
            ps = f"powershell (Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1, {level})"
        else:
            return False
        subprocess.run(ps, shell=True, capture_output=True)
        return True
    except Exception:
        return False

# ── Lock Screen ───────────────────────────────────────────────
def LockScreen() -> bool:
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return True
    except Exception:
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            return True
        except Exception:
            return False
        
# ── Ask AI Website ────────────────────────────────────────────
def AskAIWebsite(query: str, preferred_ai: str = None) -> bool:
    """
    Claude / ChatGPT / Gemini website khole, query bheje, response bole.
    Code ke liye Claude, content/image ke liye ChatGPT, backup Gemini.
    """
    if not AI_WEB_AVAILABLE:
        print("[AskAI] Install karo: pip install selenium webdriver-manager")
        return False

    # Lazy imports (circular import avoid karne ke liye)
    try:
        from Frontend.GUI         import ShowTextToScreen
        from Backend.TextToSpeech import say as _TTS
        from dotenv               import dotenv_values as _dv
        _aname = _dv(".env").get("Assistantname", "Jarvis")
    except Exception:
        ShowTextToScreen = lambda x: print(x)
        _TTS             = lambda x, **kw: None
        _aname           = "Jarvis"

    def _say_and_show(msg: str):
        try:
            ShowTextToScreen(f"{_aname} : {msg}")
            _TTS(msg)
        except Exception:
            print(f"[AskAI] {msg}")

    result = ask_ai_website(
        query,
        preferred_ai=preferred_ai,
        on_status=_say_and_show
    )

    if result.get("response"):
        full_resp   = result["response"]
        speech_resp = result["speech_text"]
        ai_used     = result["ai_used"]

        # Screen pe full response dikhao (pehle 400 chars + indicator)
        preview = full_resp[:400] + ("..." if len(full_resp) > 400 else "")
        try:
            ShowTextToScreen(f"{_aname} [{ai_used}]: {preview}")
        except Exception:
            pass

        # TTS ke liye truncated version bolo
        _say_and_show(speech_resp)
        return True

    else:
        err = result.get("error", "Sabhi AI websites fail ho gayi.")
        _say_and_show(err)
        return False        

# ── Google Search ─────────────────────────────────────────────
def GoogleSearch(topic: str) -> bool:
    search(topic)
    return True

# ── Content Writer ────────────────────────────────────────────
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

    clean_topic  = topic.strip()
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

# ── YouTube ───────────────────────────────────────────────────
def YouTubeSearch(topic: str) -> bool:
    webbrowser.open(f"https://www.youtube.com/results?search_query={topic}")
    return True

def PlayYoutube(query: str) -> bool:
    playonyt(query)
    return True

# ── Chrome Helper ─────────────────────────────────────────────
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

    for keyword, url in _WEB_APP_MAP.items():
        if keyword in app_lower:
            return _open_url_in_chrome(url)

    for app_key, paths in _DESKTOP_APP_PATHS.items():
        if app_key in app_lower or app_lower in app_key:
            for path in paths:
                if path.endswith(":"):
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
                    try:
                        subprocess.Popen([path])
                        return True
                    except Exception:
                        pass

    try:
        appopen(app, match_closest=True, output=False, throw_error=True)
        return True
    except Exception:
        pass

    try:
        os.startfile(app_lower)
        return True
    except Exception:
        pass

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
    try:
        subprocess.run(["taskkill", "/f", "/im", f"{app}.exe"], capture_output=True)
        return True
    except Exception:
        return False

# ── Volume Control ────────────────────────────────────────────
def _get_volume_interface():
    try:
        devices   = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return None

def System(command: str) -> bool:
    cmd = command.lower().strip()

    # ── Lock Screen ──────────────────────────────────────────
    if cmd in ("lock", "lock screen", "lock pc", "lock computer"):
        return LockScreen()

    # ── Screenshot ───────────────────────────────────────────
    if any(kw in cmd for kw in ("screenshot", "take screenshot", "capture screen", "snap screen")):
        return TakeScreenshot()

    # ── Screen Recording ─────────────────────────────────────
    if any(kw in cmd for kw in ("start screen recording", "start recording", "record screen")):
        return StartScreenRecording()
    if any(kw in cmd for kw in ("stop recording", "stop screen recording")):
        return StopScreenRecording()

    # ── Bluetooth ─────────────────────────────────────────────
    if any(kw in cmd for kw in ("bluetooth on", "enable bluetooth", "turn on bluetooth", "bluetooth chalu")):
        return SetBluetooth(True)
    if any(kw in cmd for kw in ("bluetooth off", "disable bluetooth", "turn off bluetooth", "bluetooth band")):
        return SetBluetooth(False)

    # ── Brightness ────────────────────────────────────────────
    if any(kw in cmd for kw in ("brightness up", "increase brightness", "bright up")):
        return SetBrightness(direction="up")
    if any(kw in cmd for kw in ("brightness down", "decrease brightness", "dim screen")):
        return SetBrightness(direction="down")
    if "set brightness" in cmd:
        try:
            level = int(''.join(filter(str.isdigit, cmd.replace("set brightness", ""))))
            return SetBrightness(level=level)
        except Exception:
            pass

    # ── Volume ────────────────────────────────────────────────
    if PYCAW_AVAILABLE:
        volume = _get_volume_interface()
        if volume is not None:
            try:
                if cmd in ("mute", "unmute"):
                    current = volume.GetMute()
                    volume.SetMute(0 if current else 1, None)
                    return True
                elif cmd == "volume up":
                    new_vol = min(1.0, volume.GetMasterVolumeLevelScalar() + 0.10)
                    volume.SetMasterVolumeLevelScalar(new_vol, None)
                    return True
                elif cmd == "volume down":
                    new_vol = max(0.0, volume.GetMasterVolumeLevelScalar() - 0.10)
                    volume.SetMasterVolumeLevelScalar(new_vol, None)
                    return True
                elif cmd.startswith("set volume"):
                    try:
                        level = int(cmd.replace("set volume", "").strip()) / 100
                        volume.SetMasterVolumeLevelScalar(max(0.0, min(1.0, level)), None)
                        return True
                    except Exception:
                        pass
            except Exception as e:
                print(f"[Volume] pycaw error: {e}")

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

    print(f"[System] Command not handled: {command}")
    return False

# ── Image Generation ──────────────────────────────────────────
def TriggerImageGeneration(query: str) -> bool:
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

# ── Async Dispatcher ──────────────────────────────────────────
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
                clean = cmd.replace("writecode","").replace("write code","").replace("code","").strip()
                funcs.append(asyncio.to_thread(WriteCode, clean))

        elif cmd.startswith("google search"):
            funcs.append(asyncio.to_thread(GoogleSearch, command.strip()[13:].strip()))

        elif cmd.startswith("aicode"):
            # "aicode write bubble sort in python"
            q = command.strip()[6:].strip()
            funcs.append(asyncio.to_thread(AskAIWebsite, q, "claude"))

        elif cmd.startswith("aicontent"):
            # "aicontent write a blog about AI"
            q = command.strip()[9:].strip()
            funcs.append(asyncio.to_thread(AskAIWebsite, q, "chatgpt"))

        elif cmd.startswith("askai"):
            # "askai what is quantum computing"  (auto-route)
            q = command.strip()[5:].strip()
            funcs.append(asyncio.to_thread(AskAIWebsite, q, None))    

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
            pass

        else:
            print(f"[yellow]No handler for:[/yellow] {cmd}")

    results = await asyncio.gather(*funcs, return_exceptions=True)
    for result in results:
        yield result


async def Automation(commands: list) -> bool:
    async for _ in TranslateAndExecute(commands):
        pass
    return True