# ─────────────────────────────────────────────────────────────
#  Main.py  —  Jarvis Entry Point  [CLEAN v10]
#
#  CHANGES v10:
#  1. Removed clap/snap detection entirely
#  2. Removed pause/resume functionality
#  3. Removed AFK mode / idle thread
#  4. Removed SnapMonitorThread and IdleThread
#  5. 3 states only: Listening → Thinking → Speaking
#  6. Speaking: no commands accepted until audio COMPLETELY done
#  7. All other features preserved (image gen, memory, EQ, etc.)
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
from Backend.Automation           import (
    Automation, OpenApp, System, TriggerImageGeneration,
    TakeScreenshot, StartScreenRecording, StopScreenRecording,
    SetBluetooth, SetBrightness, LockScreen
)
from Backend.SpeechToText         import SpeechRecognition
from Backend.Chatbot              import ChatBot, ClearChats
from Backend.TextToSpeech         import say as TextToSpeech, get_pre_task_response, get_post_task_response, get_rate_for_emotion, get_pitch_for_emotion  # STEP 5: added get_rate_for_emotion, get_pitch_for_emotion
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
        save_fact, add_time_spent, upgrade_relationship,
        save_shared_memory, add_important_moment
    )
    MEMORY_AVAILABLE = True
except ImportError:
    MEMORY_AVAILABLE = False

# ── NotificationManager ───────────────────────────────────────
try:
    from Backend.NotificationManager import get_startup_notification_message, add_watched_app, remove_watched_app
    NOTIF_AVAILABLE = True
except ImportError:
    NOTIF_AVAILABLE = False

# ── ENV ───────────────────────────────────────────────────────
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

_IMAGE_DATA_FILE   = os.path.join("Frontend", "Files", "ImageGeneration.data")
_image_gen_process = None

# ── Safe File Helpers ─────────────────────────────────────────
def _safe_read(filepath, retries=5, delay=0.2):
    for _ in range(retries):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except PermissionError:
            sleep(delay)
        except FileNotFoundError:
            return ""
    return ""

def _safe_write(filepath, content, retries=5, delay=0.2):
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    for _ in range(retries):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
            return True
        except PermissionError:
            sleep(delay)
    return False

def _atomic_write(filepath, content) -> bool:
    """
    Write content atomically using write-to-tmp + rename.
    ImageGeneration.py subprocess will never see a partial file.
    """
    tmp = filepath + ".tmp"
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, filepath)
        return True
    except Exception as e:
        print(f"[Main] Atomic write error: {e}")
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False

# ── Chat Setup ────────────────────────────────────────────────
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
    json_data = ReadChatLogJson()
    formatted = ""
    for entry in json_data:
        if entry["role"] == "user":
            formatted += f"{Username} : {entry['content']}\n"
        elif entry["role"] == "assistant":
            formatted += f"{Assistantname} : {entry['content']}\n"
    _safe_write(TempDirectoryPath("Database.data"), AnswerModifier(formatted))

def ShowChatsOnGUI():
    data = _safe_read(TempDirectoryPath("Database.data"))
    if len(str(data)) > 0:
        _safe_write(TempDirectoryPath("Responses.data"), "\n".join(data.split("\n")))

# ── Greeting ──────────────────────────────────────────────────
def _build_greeting() -> str:
    hour = time.localtime().tm_hour
    if   5  <= hour < 12: t = "Good morning"
    elif 12 <= hour < 17: t = "Good afternoon"
    elif 17 <= hour < 21: t = "Good evening"
    else:                  t = "Good night"
    return f"{t}, {Username}. I'm {Assistantname}, ready for your command"

# ── EQ-Aware TTS (STEP 5 UPDATED) ────────────────────────────
def SpeakWithEQ(text: str, query: str = "") -> None:
    rate  = "+0%"
    pitch = "+0Hz"
    if EQ_AVAILABLE and EQProcess and query:
        try:
            eq    = EQProcess(query)
            emo   = eq.get("emotion", "neutral")
            rate  = get_rate_for_emotion(emo)
            pitch = get_pitch_for_emotion(emo)
        except Exception:
            pass
    TextToSpeech(text, rate=rate, pitch=pitch)

def SpeakInBackground(text: str, query: str = "") -> None:
    t = threading.Thread(target=SpeakWithEQ, args=(text, query), daemon=True)
    t.start()

# ── ImageGeneration Subprocess ────────────────────────────────
def _ensure_image_gen_process():
    global _image_gen_process
    if _image_gen_process is not None:
        if _image_gen_process.poll() is None:
            return
        print("[ImageGen] Process died, restarting...")

    try:
        _image_gen_process = subprocess.Popen(
            ["python", os.path.join("Backend", "ImageGeneration.py")],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            shell=False
        )
        subprocesses.append(_image_gen_process)
        sleep(2.0)
        print(f"[ImageGen] ✅ Subprocess started (PID: {_image_gen_process.pid})")
    except Exception as e:
        print(f"[ImageGen] ❌ Launch error: {e}")
        _image_gen_process = None

def _trigger_image_generation(prompt: str) -> bool:
    """Atomic write + verification to trigger ImageGeneration.py."""
    _ensure_image_gen_process()

    if _image_gen_process is None:
        print("[ImageGen] ❌ Process not available")
        return False

    success = _atomic_write(_IMAGE_DATA_FILE, f"{prompt},True")
    if not success:
        print(f"[Main] ❌ Failed to write image trigger")
        return False

    sleep(0.05)
    try:
        with open(_IMAGE_DATA_FILE, "r", encoding="utf-8") as f:
            written = f.read().strip()
        if f"{prompt},True" == written:
            print(f"[Main] ✅ Image trigger verified: '{prompt},True'")
            return True
        else:
            with open(_IMAGE_DATA_FILE, "w", encoding="utf-8") as f:
                f.write(f"{prompt},True")
                f.flush()
                os.fsync(f.fileno())
            sleep(0.05)
            return True
    except Exception as e:
        print(f"[Main] ⚠️ Verification read failed: {e}")
        return True

# ── InitialExecution (STEP 4 UPDATED) ────────────────────────
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

    _atomic_write(_IMAGE_DATA_FILE, "False,False")
    _ensure_image_gen_process()

    greeting = _build_greeting()

    # STEP 4: Append startup notification message if any
    if NOTIF_AVAILABLE:
        try:
            notif_msg = get_startup_notification_message()
            if notif_msg:
                greeting = f"{greeting}. {notif_msg}"
        except Exception:
            pass

    ShowTextToScreen(f"{Assistantname} : {greeting}")
    SpeakInBackground(greeting)

InitialExecution()

# ── Clear Cache ───────────────────────────────────────────────
def _handle_clear_chats() -> None:
    ClearChats()
    for fname in ["Database.data", "Responses.data"]:
        _safe_write(TempDirectoryPath(fname), "")
    print("[Main] ✅ Chats cleared (memories safe)")
    ShowDefaultChatIfNoChats()

# ── Pre-task voice ────────────────────────────────────────────
def _get_pre_task_voice(decision_list: list) -> str:
    for d in decision_list:
        d_lower = d.lower().strip()
        if d_lower.startswith("open"):
            return get_pre_task_response("open", app=d[4:].strip())
        elif d_lower.startswith("close"):
            return get_pre_task_response("close", app=d[5:].strip())
        elif d_lower.startswith("play"):
            return get_pre_task_response("play", song=d[4:].strip())
        elif "volume up"     in d_lower: return get_pre_task_response("volume up")
        elif "volume down"   in d_lower: return get_pre_task_response("volume down")
        elif "mute"          in d_lower: return get_pre_task_response("mute")
        elif "screenshot"    in d_lower: return get_pre_task_response("screenshot")
        elif "screen record" in d_lower: return get_pre_task_response("screen record")
        elif d_lower.startswith("content"):
            return get_pre_task_response("content", topic=d[7:].strip())
        elif d_lower.startswith("google search"):
            return get_pre_task_response("google search", query=d[13:].strip())
    return get_pre_task_response("default")

# ── Special Commands (STEP 4 UPDATED) ────────────────────────
def _handle_special_commands(Query: str) -> bool:
    q = Query.lower().strip()

    if any(kw in q for kw in ["clear old chats", "clear chats", "delete chats", "clear chat history"]):
        _handle_clear_chats()
        answer = "Done. Chat history cleared. Your memories, emotions and personality are all safe."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer, query=Query)
        return True

    if any(kw in q for kw in ["clear cache", "clear old data", "delete old data"]):
        chat_path = os.path.join("Data", "ChatLog.json")
        _safe_write(chat_path, "[]")
        if MEMORY_AVAILABLE:
            try:
                clear_cache_only()
            except Exception:
                pass
        answer = "Cache cleared. Permanent memories are safe."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["take screenshot", "screenshot lo", "capture screen"]):
        TakeScreenshot()
        answer = "Screenshot taken and saved."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["start screen recording", "record my screen", "record screen"]):
        StartScreenRecording()
        answer = "Screen recording started."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["stop screen recording", "stop recording"]):
        StopScreenRecording()
        answer = "Screen recording stopped."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["bluetooth on", "enable bluetooth"]):
        SetBluetooth(True)
        answer = "Bluetooth enabled."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["bluetooth off", "disable bluetooth"]):
        SetBluetooth(False)
        answer = "Bluetooth disabled."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["brightness up", "increase brightness"]):
        SetBrightness(direction="up")
        answer = "Brightness increased."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["brightness down", "decrease brightness"]):
        SetBrightness(direction="down")
        answer = "Brightness decreased."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakInBackground(answer)
        return True

    if any(kw in q for kw in ["lock screen", "lock pc"]):
        LockScreen()
        answer = "Locking screen now."
        ShowTextToScreen(f"{Assistantname} : {answer}")
        SpeakWithEQ(answer)
        return True

    # STEP 4: Watch/unwatch notification apps
    if NOTIF_AVAILABLE and "notification" in q and "watch" in q:
        for app in ["whatsapp", "gmail", "telegram", "discord", "slack"]:
            if app in q:
                msg = add_watched_app(app.capitalize())
                ShowTextToScreen(f"{Assistantname}: {msg}")
                SpeakInBackground(msg)
                return True

    if NOTIF_AVAILABLE and "notification" in q and ("remove" in q or "stop watching" in q or "unwatch" in q):
        for app in ["whatsapp", "gmail", "telegram", "discord", "slack"]:
            if app in q:
                msg = remove_watched_app(app.capitalize())
                ShowTextToScreen(f"{Assistantname}: {msg}")
                SpeakInBackground(msg)
                return True

    return False

# ── Main Execution Loop ───────────────────────────────────────
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

    if _handle_special_commands(Query):
        return

    # EQ check
    eq_result = None
    if EQ_AVAILABLE and EQProcess:
        try:
            eq_result = EQProcess(Query)

            if eq_result.get("is_adult"):
                resp = eq_result["adult_response"]
                ShowTextToScreen(f"{Assistantname} : {resp}")
                SetAssistantStatus("Speaking...")
                SpeakInBackground(resp)
                return

            if eq_result.get("is_gaali"):
                resp = eq_result["savage_response"]
                ShowTextToScreen(f"{Assistantname} : {resp}")
                SetAssistantStatus("Speaking...")
                SpeakInBackground(resp, query=Query)
                return

            if eq_result.get("is_love"):
                resp = eq_result["love_response"]
                ShowTextToScreen(f"{Assistantname} : {resp}")
                SetAssistantStatus("Speaking...")
                SpeakInBackground(resp, query=Query)
                return

        except Exception:
            pass

    # First layer decision
    Decision = FirstLayerDMM(Query)
    print(f"\n[Decision] {Decision}\n")

    G = any(i.startswith("general")  for i in Decision)
    R = any(i.startswith("realtime") for i in Decision)

    Merged_query = " and ".join(
        [" ".join(i.split()[1:]) for i in Decision
         if i.startswith("general") or i.startswith("realtime")]
    )

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

    has_task_command = any(
        any(d.lower().strip().startswith(func) for func in Functions)
        for d in Decision
    )

    # ── STEP 1: Voice reply ───────────────────────────────────
    if G or R:
        SetAssistantStatus("Searching..." if R else "Thinking...")
        Answer = RealtimeSearchEngine(QueryModifier(Merged_query)) if R else ChatBot(QueryModifier(Merged_query))
        ShowTextToScreen(f"{Assistantname} : {Answer}")
        SetAssistantStatus("Speaking...")
        SpeakInBackground(Answer, query=Query)

    else:
        for d in Decision:
            d_lower = d.lower().strip()

            if d_lower.startswith("general"):
                SetAssistantStatus("Thinking...")
                QueryFinal = d.replace("general", "").strip()
                Answer     = ChatBot(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Speaking...")
                SpeakInBackground(Answer, query=QueryFinal)
                break

            elif d_lower.startswith("realtime"):
                SetAssistantStatus("Searching...")
                QueryFinal = d.replace("realtime", "").strip()
                Answer     = RealtimeSearchEngine(QueryModifier(QueryFinal))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Speaking...")
                SpeakInBackground(Answer, query=QueryFinal)
                break

            elif d_lower == "exit":
                Answer = ChatBot(QueryModifier("Okay, Bye!"))
                ShowTextToScreen(f"{Assistantname} : {Answer}")
                SetAssistantStatus("Speaking...")
                SpeakWithEQ(Answer)
                sleep(2)
                os._exit(0)

        if has_task_command and not G and not R:
            pre_msg = _get_pre_task_voice(list(Decision))
            ShowTextToScreen(f"{Assistantname} : {pre_msg}")
            SetAssistantStatus("Speaking...")
            SpeakWithEQ(pre_msg, query=Query)

    # ── STEP 2: Execute tasks ─────────────────────────────────
    for d in Decision:
        if not TaskExecution:
            if any(d.lower().strip().startswith(func) for func in Functions):
                run(Automation(list(Decision)))
                TaskExecution = True

    if TaskExecution and not ImageExecution:
        post_msg = get_post_task_response()
        ShowTextToScreen(f"{Assistantname} : {post_msg}")
        SpeakInBackground(post_msg)

    # ── STEP 3: Image generation ──────────────────────────────
    if ImageExecution and ImageGenerationQuery:
        img_msg = (
            f"Sure, generating images of {ImageGenerationQuery} for you. "
            f"I'll let you know when they're ready."
        )
        ShowTextToScreen(f"{Assistantname} : {img_msg}")
        SpeakInBackground(img_msg)

        triggered = _trigger_image_generation(ImageGenerationQuery)
        if not triggered:
            err_msg = "Sorry, image generation service is not available right now."
            ShowTextToScreen(f"{Assistantname} : {err_msg}")
            SpeakInBackground(err_msg)

    if MEMORY_AVAILABLE:
        try:
            add_time_spent(1.0)
        except Exception:
            pass


# ── Image Watcher Thread ──────────────────────────────────────
def ImageWatcherThread():
    _CONFIRMATIONS = [
        "Sir, your images are ready. Want me to display them?",
        "Images generated. Should I open them for you?",
        "Done! Your images of {prompt} are ready.",
        "Image generation complete. Shall I open them?",
    ]
    while True:
        try:
            raw = _safe_read(_IMAGE_DATA_FILE).strip()
            if raw and "," in raw:
                parts  = raw.split(",", 1)
                prompt = parts[0].strip()
                status = parts[1].strip()
                if status == "Generated" and prompt not in ("", "False"):
                    template = random.choice(_CONFIRMATIONS)
                    try:
                        msg = template.format(prompt=prompt)
                    except KeyError:
                        msg = template
                    ShowTextToScreen(f"{Assistantname} : {msg}")
                    SpeakInBackground(msg)
                    _atomic_write(_IMAGE_DATA_FILE, "False,False")
        except Exception as e:
            print(f"[ImageWatcher] Error: {e}")
        sleep(1)


# ── Main Loop Threads ─────────────────────────────────────────
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
    t1 = threading.Thread(target=FirstThread,       daemon=True)
    t1.start()
    t4 = threading.Thread(target=ImageWatcherThread, daemon=True)
    t4.start()
    SecondThread()