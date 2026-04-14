# ─────────────────────────────────────────────────────────────
#  Main.py  —  Jarvis Entry Point
#  - Voice reply PEHLE, phir task
#  - EQ emotion-aware TTS (rate + pitch)
#  - Clear cache = sirf cache, emotions safe
#  - Crash-safe file operations
# ─────────────────────────────────────────────────────────────

from Frontend.GUI import (
    GraphicalUserInterface,
    SetAssistantStatus,
    ShowTextToScreen,
    TempDirectoryPath,
    SetMicrophoneStatus,
    AnswerModifier,
    QueryModifier,
    GetMicrophoneStatus,
    GetAssistantStatus
)
from Backend.Model            import Brain as FirstLayerDMM
from Backend.RealtimeSearchEngine import ask as RealtimeSearchEngine
from Backend.Automation       import Automation
from Backend.SpeechToText     import SpeechRecognition
from Backend.Chatbot          import ChatBot
from Backend.TextToSpeech     import say as TextToSpeech
from dotenv import dotenv_values
from asyncio import run
from time import sleep
import subprocess
import threading
import json
import os

# ── EQ Import ─────────────────────────────────────────────────
try:
    from Backend.Eq import EQProcess
    EQ_AVAILABLE = True
except ImportError:
    EQ_AVAILABLE = False
    EQProcess    = None

# ── Memory Import ─────────────────────────────────────────────
try:
    from Backend.Memory import clear_cache_only, start_session
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# ── ENV ────────────────────────────────────────────────────────
env_vars      = dotenv_values(".env")
Username      = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")

DefaultMessage = (
    f"{Username} : Hello {Assistantname}, How are you?\n"
    f"{Assistantname}: Welcome {Username}. I am doing well. How may I help you?"
)

subprocesses = []
Functions    = ["open", "close", "play", "system", "content", "google search", "youtube search"]

# ── Safe File Helpers ──────────────────────────────────────────
def _safe_read(filepath: str, retries: int = 5, delay: float = 0.3) -> str:
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            sleep(delay)
        except FileNotFoundError:
            return ""
    return ""


def _safe_write(filepath: str, content: str, retries: int = 5, delay: float = 0.3) -> bool:
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            return True
        except PermissionError:
            sleep(delay)
    return False


# ── Chat Setup ─────────────────────────────────────────────────
def ShowDefaultChatIfNoChats():
    chat_path = os.path.join("Data", "ChatLog.json")
    content   = _safe_read(chat_path)
    if len(content) < 5:
        _safe_write(TempDirectoryPath("Database.data"), "")
        _safe_write(TempDirectoryPath("Responses.data"), DefaultMessage)


def ReadChatLogJson():
    try:
        with open(os.path.join("Data", "ChatLog.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def ChatLogIntegration():
    json_data        = ReadChatLogJson()
    formatted_chatlog = ""
    for entry in json_data:
        if entry["role"] == "user":
            formatted_chatlog += f"{Username} : {entry['content']}\n"
        elif entry["role"] == "assistant":
            formatted_chatlog += f"{Assistantname} : {entry['content']}\n"
    _safe_write(TempDirectoryPath("Database.data"), AnswerModifier(formatted_chatlog))


def ShowChatsOnGUI():
    data = _safe_read(TempDirectoryPath("Database.data"))
    if len(str(data)) > 0:
        lines  = data.split("\n")
        result = "\n".join(lines)
        _safe_write(TempDirectoryPath("Responses.data"), result)


def InitialExecution():
    SetMicrophoneStatus("False")
    ShowTextToScreen("")
    ShowDefaultChatIfNoChats()
    ChatLogIntegration()
    ShowChatsOnGUI()
    if MEMORY_AVAILABLE:
        try:
            start_session()
        except Exception:
            pass


InitialExecution()


# ── EQ-Aware TTS ───────────────────────────────────────────────
def SpeakWithEQ(text: str, query: str = "") -> None:
    """
    Pehle voice output — phir kuch nahi. Task alag se hota hai.
    EQ se rate + pitch milta hai.
    """
    rate  = "+0%"
    pitch = "+0Hz"

    if EQ_AVAILABLE and EQProcess and query:
        try:
            eq    = EQProcess(query)
            tone  = eq.get("tone", {})
            rate  = tone.get("rate",  "+0%")
            pitch = tone.get("pitch", "+0Hz")
            print(f"[EQ] Emotion: {eq.get('emotion','neutral')} | Rate: {rate} | Pitch: {pitch}")
        except Exception:
            pass

    TextToSpeech(text, rate=rate, pitch=pitch)


def SpeakInBackground(text: str, query: str = "") -> None:
    """Background thread mein speak karo."""
    t = threading.Thread(target=SpeakWithEQ, args=(text, query), daemon=True)
    t.start()


# ── Clear Cache Command ────────────────────────────────────────
def _handle_clear_cache() -> None:
    """
    'clear old data' → cache + chat history delete,
    but emotions + personality safe rahe.
    """
    # Chat log clear
    chat_path = os.path.join("Data", "ChatLog.json")
    _safe_write(chat_path, "[]")

    # Data cache files clear
    for fname in ["Database.data", "Responses.data"]:
        _safe_write(TempDirectoryPath(fname), "")

    # Generated files clear (images + speech)
    for folder, exts in [("Data", [".jpg", ".png", ".wav"]), ]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if any(file.endswith(ext) for ext in exts):
                    try:
                        os.remove(os.path.join(folder, file))
                    except Exception:
                        pass

    # Memory cache (NOT emotions)
    if MEMORY_AVAILABLE:
        try:
            clear_cache_only()
        except Exception:
            pass

    print("[Main] Cache cleared ✅ Emotions & personality safe hain.")
    ShowDefaultChatIfNoChats()


# ── Main Execution Loop ────────────────────────────────────────
def MainExecution():
    TaskExecution        = False
    ImageExecution       = False
    ImageGenerationQuery = ""

    SetAssistantStatus("Listening...")
    Query = SpeechRecognition()
    if not Query:
        return

    ShowTextToScreen(f"{Username}: {Query}")
    SetAssistantStatus("Thinking...")

    # Clear cache command detection
    if any(kw in Query.lower() for kw in ["clear old data", "clear cache", "delete old data"]):
        _handle_clear_cache()
        answer = "Done. I've cleared the cache. Your memories and personality are still safe with me."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SetAssistantStatus("Answering...")
        SpeakInBackground(answer, query=Query)
        return

    Decision = FirstLayerDMM(Query)
    print(f"\n[Decision] {Decision}\n")

    G = any(i.startswith("general")  for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Merged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision
         if i.startswith("general") or i.startswith("realtime")]
    )

    # Image generation check
    for queries in Decision:
        if "generate" in queries:
            raw = queries.strip()
            for prefix in ["generate image", "generate images", "generate"]:
                if raw.startswith(prefix):
                    raw = raw[len(prefix):].strip()
                    break
            ImageGenerationQuery = raw
            ImageExecution       = True

    # ── STEP 1: Reply FIRST (voice output) ──────────────────────
    if G and R or R:
        SetAssistantStatus("Searching...")
        Answer = RealtimeSearchEngine(QueryModifier(Merged_query))
        ShowTextToScreen(f"{Assistantname} : {Answer}")
        SetAssistantStatus("Answering...")
        SpeakInBackground(Answer, query=Query)   # ← Voice pehle

    else:
        for Queries in Decision:
            if "general" in Queries:
                SetAssistantStatus("Thinking...")
                QueryFinal = Queries.replace("general", "").strip()
                Answer     = ChatBot(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakInBackground(Answer, query=QueryFinal)  # ← Voice pehle
                break

            elif "realtime" in Queries:
                SetAssistantStatus("Searching...")
                QueryFinal = Queries.replace("realtime", "").strip()
                Answer     = RealtimeSearchEngine(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakInBackground(Answer, query=QueryFinal)  # ← Voice pehle
                break

            elif "exit" in Queries:
                Answer = ChatBot(QueryModifier("Okay, Bye!"))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakWithEQ(Answer)  # Synchronous — phir exit
                sleep(2)
                os._exit(0)

    # ── STEP 2: Task BAAD MEIN (automation) ─────────────────────
    for queries in Decision:
        if not TaskExecution:
            if any(queries.startswith(func) for func in Functions):
                run(Automation(list(Decision)))
                TaskExecution = True

    # ── STEP 3: Image generation subprocess ─────────────────────
    if ImageExecution:
        data_to_write = f"{ImageGenerationQuery},True"
        _safe_write(os.path.join("Frontend", "Files", "ImageGeneration.data"), data_to_write)
        try:
            p1 = subprocess.Popen(
                ["python", os.path.join("Backend", "ImageGeneration.py")],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                shell=False
            )
            subprocesses.append(p1)
        except Exception as e:
            print(f"[ImageGen] Launch error: {e}")


# ── Threads ───────────────────────────────────────────────────
def FirstThread():
    while True:
        CurrentStatus = GetMicrophoneStatus()
        if CurrentStatus == "True":
            MainExecution()
        else:
            AIStatus = GetAssistantStatus()
            if "Available..." not in AIStatus:
                SetAssistantStatus("Available...")
            sleep(0.1)


def SecondThread():
    GraphicalUserInterface()


if __name__ == "__main__":
    t1 = threading.Thread(target=FirstThread, daemon=True)
    t1.start()
    SecondThread()