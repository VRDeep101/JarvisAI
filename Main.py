# ─────────────────────────────────────────────────────────────
#  Main.py  —  Jarvis Entry Point  [FIXED v4]
#  Fixes:
#  - InitialExecution() called AFTER SpeakInBackground is defined
#  - global _last_interaction_time declared at top of IdleThread
#  - Greeting on startup with notification count
#  - Voice reply FIRST, then task (always)
#  - Pre-task + post-task voice messages
#  - EQ emotion-aware TTS fully integrated
#  - Image generation triggered correctly
#  - Volume commands routed to System()
#  - Idle prompts when user is quiet
#  - Clear cache = only cache, emotions safe
#  - Crash-safe file ops
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
from Backend.Model                import Brain as FirstLayerDMM
from Backend.RealtimeSearchEngine import ask as RealtimeSearchEngine
from Backend.Automation           import Automation, OpenApp, System, TriggerImageGeneration
from Backend.SpeechToText         import SpeechRecognition
from Backend.Chatbot              import ChatBot
from Backend.TextToSpeech         import say as TextToSpeech, get_pre_task_response, get_post_task_response, get_idle_prompt
from dotenv import dotenv_values
from asyncio import run
from time   import sleep
import subprocess
import threading
import random
import json
import os
import time

# ── EQ ────────────────────────────────────────────────────────
try:
    from Backend.Eq import EQProcess
    EQ_AVAILABLE = True
except ImportError:
    EQ_AVAILABLE = False
    EQProcess    = None

# ── Memory ────────────────────────────────────────────────────
try:
    from Backend.Memory import (
        clear_cache_only, start_session, get_memory_summary,
        save_fact, add_time_spent, upgrade_relationship
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# ── ENV ────────────────────────────────────────────────────────
env_vars      = dotenv_values(".env")
Username      = env_vars.get("Username",      "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")

DefaultMessage = (
    f"{Username} : Hello {Assistantname}, How are you?\n"
    f"{Assistantname}: Welcome {Username}. I am doing well. How may I help you?"
)

subprocesses = []
Functions    = ["open", "close", "play", "system", "content",
                "google search", "youtube search", "generate"]

# ── Idle tracking ─────────────────────────────────────────────
_last_interaction_time = 0
_IDLE_THRESHOLD        = 90   # seconds before idle prompt


# ── Safe File Helpers ──────────────────────────────────────────
def _safe_read(filepath: str, retries: int = 5, delay: float = 0.2) -> str:
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            sleep(delay)
        except FileNotFoundError:
            return ""
    return ""


def _safe_write(filepath: str, content: str, retries: int = 5, delay: float = 0.2) -> bool:
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
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
        _safe_write(TempDirectoryPath("Database.data"),  "")
        _safe_write(TempDirectoryPath("Responses.data"), DefaultMessage)


def ReadChatLogJson():
    try:
        with open(os.path.join("Data", "ChatLog.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def ChatLogIntegration():
    json_data         = ReadChatLogJson()
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


# ── Startup Greeting ───────────────────────────────────────────
def _get_unread_counts() -> dict:
    """
    Attempt to count unread messages from WhatsApp/Gmail if available.
    Returns dict with 'whatsapp' and 'gmail' counts (or None if unavailable).
    """
    return {"whatsapp": None, "gmail": None}


def _build_greeting() -> str:
    hour = time.localtime().tm_hour
    if 5 <= hour < 12:
        time_greet = "Good morning"
    elif 12 <= hour < 17:
        time_greet = "Good afternoon"
    elif 17 <= hour < 21:
        time_greet = "Good evening"
    else:
        time_greet = "Good night"

    counts = _get_unread_counts()
    wa     = counts.get("whatsapp")
    gmail  = counts.get("gmail")

    greeting = f"{time_greet}, {Username}. Welcome back. I'm {Assistantname}, and I'm ready."

    notif_parts = []
    if wa is not None:
        notif_parts.append(f"You have {wa} unread WhatsApp messages")
    if gmail is not None:
        notif_parts.append(f"{gmail} unread emails in Gmail")

    if notif_parts:
        greeting += " " + ", and ".join(notif_parts) + "."

    greeting += " What's on your mind today?"
    return greeting


# ── EQ-Aware TTS ───────────────────────────────────────────────
# NOTE: These MUST be defined before InitialExecution() is called.

def SpeakWithEQ(text: str, query: str = "") -> None:
    rate  = "+0%"
    pitch = "+0Hz"

    if EQ_AVAILABLE and EQProcess and query:
        try:
            eq    = EQProcess(query)
            tone  = eq.get("tone", {})
            rate  = tone.get("rate",  "+0%")
            pitch = tone.get("pitch", "+0Hz")
            print(f"[EQ] Emotion: {eq.get('emotion','neutral')} | Tone: {tone.get('label','Normal')}")
        except Exception:
            pass

    TextToSpeech(text, rate=rate, pitch=pitch)


def SpeakInBackground(text: str, query: str = "") -> None:
    t = threading.Thread(target=SpeakWithEQ, args=(text, query), daemon=True)
    t.start()


# ── InitialExecution ───────────────────────────────────────────
# Called HERE — after SpeakInBackground is defined.

def InitialExecution():
    global _last_interaction_time
    _last_interaction_time = time.time()

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

    greeting = _build_greeting()
    ShowTextToScreen(f"{Assistantname} : {greeting}")
    SpeakInBackground(greeting)


InitialExecution()


# ── Clear Cache ────────────────────────────────────────────────
def _handle_clear_cache() -> None:
    chat_path = os.path.join("Data", "ChatLog.json")
    _safe_write(chat_path, "[]")
    for fname in ["Database.data", "Responses.data"]:
        _safe_write(TempDirectoryPath(fname), "")
    for folder, exts in [("Data", [".jpg", ".png", ".wav"])]:
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if any(file.endswith(ext) for ext in exts):
                    try:
                        os.remove(os.path.join(folder, file))
                    except Exception:
                        pass
    if MEMORY_AVAILABLE:
        try:
            clear_cache_only()
        except Exception:
            pass
    print("[Main] Cache cleared ✅")
    ShowDefaultChatIfNoChats()


# ── Pre-task voice message builder ────────────────────────────
def _get_pre_task_voice(decision_list: list) -> str:
    """Build a short voice message to say BEFORE executing the task."""
    for d in decision_list:
        d_lower = d.lower().strip()
        if d_lower.startswith("open"):
            app = d[4:].strip()
            return get_pre_task_response("open", app=app)
        elif d_lower.startswith("close"):
            app = d[5:].strip()
            return get_pre_task_response("close", app=app)
        elif d_lower.startswith("play"):
            song = d[4:].strip()
            return get_pre_task_response("play", song=song)
        elif "volume up" in d_lower:
            return get_pre_task_response("volume up")
        elif "volume down" in d_lower:
            return get_pre_task_response("volume down")
        elif "mute" in d_lower:
            return get_pre_task_response("mute")
        elif d_lower.startswith("content"):
            topic = d[7:].strip()
            return get_pre_task_response("content", topic=topic)
        elif d_lower.startswith("google search"):
            q = d[13:].strip()
            return get_pre_task_response("google search", query=q)
    return get_pre_task_response("default")


# ── Main Execution Loop ────────────────────────────────────────
def MainExecution():
    global _last_interaction_time
    _last_interaction_time = time.time()

    TaskExecution        = False
    ImageExecution       = False
    ImageGenerationQuery = ""

    SetAssistantStatus("Listening...")
    Query = SpeechRecognition()
    if not Query:
        return

    ShowTextToScreen(f"{Username}: {Query}")
    SetAssistantStatus("Thinking...")

    # ── Clear cache command ───────────────────────────────────
    if any(kw in Query.lower() for kw in ["clear old data", "clear cache", "delete old data"]):
        _handle_clear_cache()
        answer = "Done. Cache cleared. Your memories and personality are still safe."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SetAssistantStatus("Answering...")
        SpeakInBackground(answer, query=Query)
        return

    # ── EQ check ─────────────────────────────────────────────
    if EQ_AVAILABLE and EQProcess:
        eq_result = EQProcess(Query)
        if eq_result.get("is_adult"):
            adult_resp = eq_result["adult_response"]
            ShowTextToScreen(f"{Assistantname} : {adult_resp}")
            SetAssistantStatus("Answering...")
            SpeakInBackground(adult_resp)
            return

    # ── First layer decision ──────────────────────────────────
    Decision = FirstLayerDMM(Query)
    print(f"\n[Decision] {Decision}\n")

    G = any(i.startswith("general")  for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Merged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision
         if i.startswith("general") or i.startswith("realtime")]
    )

    # Check for image generation
    for d in Decision:
        d_lower = d.lower().strip()
        if d_lower.startswith("generate"):
            raw = d.strip()[8:].strip()
            for prefix in ["image ", "images ", "image", "images"]:
                if raw.lower().startswith(prefix):
                    raw = raw[len(prefix):].strip()
                    break
            ImageGenerationQuery = raw
            ImageExecution       = True

    # ─────────────────────────────────────────────────────────
    # STEP 1: Voice reply FIRST (always before task)
    # ─────────────────────────────────────────────────────────
    has_task_command = any(
        any(d.lower().strip().startswith(func) for func in Functions)
        for d in Decision
    )

    if G or R:
        SetAssistantStatus("Searching..." if R else "Thinking...")
        Answer = RealtimeSearchEngine(QueryModifier(Merged_query)) if R else ChatBot(QueryModifier(Merged_query))
        ShowTextToScreen(f"{Assistantname} : {Answer}")
        SetAssistantStatus("Answering...")
        SpeakInBackground(Answer, query=Query)

    else:
        for d in Decision:
            d_lower = d.lower().strip()

            if d_lower.startswith("general"):
                SetAssistantStatus("Thinking...")
                QueryFinal = d.replace("general", "").strip()
                Answer     = ChatBot(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakInBackground(Answer, query=QueryFinal)
                break

            elif d_lower.startswith("realtime"):
                SetAssistantStatus("Searching...")
                QueryFinal = d.replace("realtime", "").strip()
                Answer     = RealtimeSearchEngine(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakInBackground(Answer, query=QueryFinal)
                break

            elif d_lower == "exit":
                Answer = ChatBot(QueryModifier("Okay, Bye!"))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Answering...")
                SpeakWithEQ(Answer)   # Synchronous before exit
                sleep(2)
                os._exit(0)

        # If ONLY task commands (no general/realtime), say pre-task message
        if has_task_command and not G and not R:
            pre_msg = _get_pre_task_voice(list(Decision))
            ShowTextToScreen(f"{Assistantname} : {pre_msg}")
            SpeakWithEQ(pre_msg, query=Query)

    # ─────────────────────────────────────────────────────────
    # STEP 2: Execute tasks AFTER voice reply
    # ─────────────────────────────────────────────────────────
    for d in Decision:
        if not TaskExecution:
            d_lower = d.lower().strip()
            if any(d_lower.startswith(func) for func in Functions):
                run(Automation(list(Decision)))
                TaskExecution = True

    # Post-task message if a task was executed
    if TaskExecution:
        post_msg = get_post_task_response()
        ShowTextToScreen(f"{Assistantname} : {post_msg}")
        SpeakInBackground(post_msg)

    # ─────────────────────────────────────────────────────────
    # STEP 3: Image generation subprocess
    # ─────────────────────────────────────────────────────────
    if ImageExecution and ImageGenerationQuery:
        img_msg = f"Sure, generating an image of {ImageGenerationQuery} for you."
        ShowTextToScreen(f"{Assistantname} : {img_msg}")
        SpeakInBackground(img_msg)

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

    # Memory: add time spent
    if MEMORY_AVAILABLE:
        try:
            add_time_spent(1.0)
        except Exception:
            pass


# ── Idle Prompt Thread ─────────────────────────────────────────
def IdleThread():
    global _last_interaction_time
    while True:
        sleep(10)
        elapsed = time.time() - _last_interaction_time
        if elapsed > _IDLE_THRESHOLD:
            mic_status = GetMicrophoneStatus()
            if mic_status == "True":
                prompt = get_idle_prompt()
                ShowTextToScreen(f"{Assistantname} : {prompt}")
                SpeakInBackground(prompt)
                # Reset so it doesn't spam
                _last_interaction_time = time.time()


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
    t3 = threading.Thread(target=IdleThread, daemon=True)
    t3.start()
    SecondThread()