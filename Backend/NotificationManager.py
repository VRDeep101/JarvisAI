# ─────────────────────────────────────────────────────────────
#  NotificationManager.py  —  Jarvis Windows Notification Hub  [FIXED]
#
#  KYA FIX KIA:
#  - get_notification_count() ab log-based hai (PowerShell wala kaam nahi karta)
#  - send_notification() ke 4 reliable fallbacks
#  - Windows notification reading ka limitation clearly handled
#  - Startup message reliable hai
# ─────────────────────────────────────────────────────────────

import os
import json
import datetime
import subprocess
import threading

# ── Optional toast libraries ───────────────────────────────────
try:
    from win11toast import toast as _win11_toast
    WIN11TOAST_AVAILABLE = True
except ImportError:
    WIN11TOAST_AVAILABLE = False

try:
    from plyer import notification as _plyer
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

# ── Paths ──────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "Data")
os.makedirs(_DATA_DIR, exist_ok=True)

_NOTIF_LOG         = os.path.join(_DATA_DIR, "notifications.json")
_WATCHED_APPS_FILE = os.path.join(_DATA_DIR, "watched_apps.json")
_MAX_LOG           = 100

_DEFAULT_WATCHED = [
    "WhatsApp", "Gmail", "Outlook", "Telegram", "Discord",
    "Instagram", "Twitter", "Teams", "Slack", "Zoom",
]

# ── Watched Apps ───────────────────────────────────────────────
def _load_watched() -> list:
    try:
        with open(_WATCHED_APPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        _save_watched(_DEFAULT_WATCHED)
        return _DEFAULT_WATCHED

def _save_watched(apps: list) -> None:
    try:
        with open(_WATCHED_APPS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
    except Exception:
        pass

def get_watched_apps() -> list:
    return _load_watched()

def add_watched_app(app_name: str) -> str:
    apps = _load_watched()
    if app_name not in apps:
        apps.append(app_name)
        _save_watched(apps)
        return f"Done. I'll now watch for {app_name} notifications."
    return f"I'm already watching {app_name}."

def remove_watched_app(app_name: str) -> str:
    apps = _load_watched()
    if app_name in apps:
        apps.remove(app_name)
        _save_watched(apps)
        return f"Removed. I'll stop watching {app_name}."
    return f"{app_name} wasn't in the list."

# ── Notification Log (Jarvis ka apna system) ───────────────────
def _load_log() -> list:
    try:
        with open(_NOTIF_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_log(log: list) -> None:
    try:
        with open(_NOTIF_LOG, "w", encoding="utf-8") as f:
            json.dump(log[-_MAX_LOG:], f, indent=2)
    except Exception:
        pass

def log_notification(app: str, message: str, title: str = "") -> None:
    """Manually ek notification log karo (doosre modules se call karo)."""
    entry = {
        "app"      : app,
        "title"    : title,
        "message"  : message,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "read"     : False,
    }
    log = _load_log()
    log.append(entry)
    _save_log(log)

def get_unread_notifications() -> list:
    return [n for n in _load_log() if not n.get("read", False)]

def mark_all_read() -> None:
    log = _load_log()
    for n in log:
        n["read"] = True
    _save_log(log)

def get_notification_count() -> int:
    """
    Unread notifications ka count.
    NOTE: Ye sirf Jarvis-logged notifications count karta hai.
    Windows dusre apps ki notifications padhne nahi deta easily.
    """
    return len(get_unread_notifications())

def get_notification_summary() -> str:
    """
    Human-readable summary for startup.
    Example: "You have 3 WhatsApp messages and 1 Gmail notification."
    """
    unread = get_unread_notifications()
    if not unread:
        return ""

    app_counts: dict = {}
    for n in unread:
        app = n.get("app", "Unknown")
        app_counts[app] = app_counts.get(app, 0) + 1

    parts = []
    for app, count in app_counts.items():
        word = "message" if count == 1 else "messages"
        parts.append(f"{count} {app} {word}")

    if not parts:
        return ""
    return "By the way, you have " + " and ".join(parts) + "."

# ── Send Notification (4 reliable fallbacks) ──────────────────
def send_notification(title: str, message: str, app_name: str = "Jarvis") -> bool:
    """
    Windows desktop notification bhejo.
    4 methods try karta hai — pehla jo kaam kare woh use karta hai.
    """
    # Method 1: win11toast (best, modern Windows)
    if WIN11TOAST_AVAILABLE:
        try:
            _win11_toast(title, message, app_id=app_name)
            return True
        except Exception:
            pass

    # Method 2: plyer
    if PLYER_AVAILABLE:
        try:
            _plyer.notify(
                title   = title,
                message = message,
                app_name= app_name,
                timeout = 8,
            )
            return True
        except Exception:
            pass

    # Method 3: PowerShell BurntToast module (agar installed ho)
    try:
        ps = (
            f"if (Get-Module -ListAvailable -Name BurntToast) {{"
            f"  New-BurntToastNotification -Text '{title}', '{message}'"
            f"}}"
        )
        r = subprocess.run(
            ["powershell", "-Command", ps],
            capture_output=True, timeout=6
        )
        if r.returncode == 0 and not r.stderr:
            return True
    except Exception:
        pass

    # Method 4: PowerShell Windows.UI.Notifications (Windows 10/11)
    try:
        ps = f"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml('<toast><visual><binding template="ToastText02"><text id="1">{title}</text><text id="2">{message}</text></binding></visual></toast>')
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_name}").Show($toast)
"""
        subprocess.run(
            ["powershell", "-Command", ps],
            capture_output=True, timeout=8
        )
        return True
    except Exception:
        pass

    print(f"[NotifMgr] Notification send nahi ho saka: {title} — {message}")
    return False

# ── Windows Notification Reading (Best-effort) ────────────────
def _read_windows_notifications_raw() -> list:
    """
    Windows dusre apps ki notifications easily padhne nahi deta.
    Ye function best-effort hai — mostly empty return karega.
    Reliable way hai log_notification() se manually log karna.
    """
    _PS = """
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null
    $history = [Windows.UI.Notifications.ToastNotificationManager]::History
    $apps = $history.GetHistory()
    $apps | Select-Object AppId,Tag,Group | ConvertTo-Json -Compress
} catch { Write-Output "[]" }
"""
    try:
        r = subprocess.run(
            ["powershell", "-Command", _PS],
            capture_output=True, text=True, timeout=8
        )
        raw = r.stdout.strip()
        if raw and raw != "[]":
            data = json.loads(raw)
            return [data] if isinstance(data, dict) else data
    except Exception:
        pass
    return []

# ── Startup Summary ────────────────────────────────────────────
def get_startup_notification_message() -> str:
    """
    Jarvis startup pe call karo — pending notifications announce karta hai.
    Sirf tab kuch return karega jab pehle log_notification() se kuch log hua ho.
    """
    return get_notification_summary()

# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[NotifMgr] Test mode")

    log_notification("WhatsApp", "Hey bhai free ho?", "Rahul")
    log_notification("WhatsApp", "Meeting at 5", "Work Group")
    log_notification("Gmail", "Your order shipped", "Amazon")

    print(f"Startup: {get_startup_notification_message()}")
    print(f"Unread : {get_notification_count()}")
    print(f"Watched: {get_watched_apps()}")

    ok = send_notification("Jarvis Test", "Notification system working!")
    print(f"Sent   : {ok}")

    mark_all_read()
    print(f"After mark_all_read: {get_notification_count()} unread")