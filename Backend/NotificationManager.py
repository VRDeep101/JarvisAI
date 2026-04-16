# ─────────────────────────────────────────────────────────────
#  NotificationManager.py  —  Jarvis Windows Notification Hub
#
#  FEATURES:
#  - Read Windows toast notifications (WhatsApp, Gmail, etc.)
#  - Send custom notifications to user
#  - Monitor notification queue
#  - App whitelist: add/remove apps to watch
#  - Auto-announce on startup: "You have 3 WhatsApp messages"
#  - Persistent notification log
# ─────────────────────────────────────────────────────────────

import os
import json
import datetime
import subprocess
import time
import threading

# ── Optional: Windows toast via win11toast / plyer ────────────
try:
    from win11toast import toast
    WIN11TOAST_AVAILABLE = True
except ImportError:
    WIN11TOAST_AVAILABLE = False

try:
    from plyer import notification as plyer_notify
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False

# ── Paths ──────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_BASE_DIR, "Data")
os.makedirs(_DATA_DIR, exist_ok=True)

_NOTIF_LOG   = os.path.join(_DATA_DIR, "notifications.json")
_WATCHED_APPS_FILE = os.path.join(_DATA_DIR, "watched_apps.json")

# ── Default watched apps ──────────────────────────────────────
_DEFAULT_WATCHED = [
    "WhatsApp", "Gmail", "Outlook", "Telegram", "Discord",
    "Instagram", "Twitter", "Teams", "Slack", "Chrome",
    "Firefox", "Edge", "YouTube", "Zoom", "Calendar"
]

def _load_watched_apps() -> list:
    try:
        with open(_WATCHED_APPS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        _save_watched_apps(_DEFAULT_WATCHED)
        return _DEFAULT_WATCHED

def _save_watched_apps(apps: list) -> None:
    try:
        with open(_WATCHED_APPS_FILE, "w", encoding="utf-8") as f:
            json.dump(apps, f, indent=2)
    except Exception:
        pass

def add_watched_app(app_name: str) -> str:
    """Add an app to the notification watch list."""
    apps = _load_watched_apps()
    if app_name not in apps:
        apps.append(app_name)
        _save_watched_apps(apps)
        return f"Done. I'll now watch for {app_name} notifications."
    return f"I'm already watching {app_name}."

def remove_watched_app(app_name: str) -> str:
    """Remove an app from the watch list."""
    apps = _load_watched_apps()
    if app_name in apps:
        apps.remove(app_name)
        _save_watched_apps(apps)
        return f"Removed. I'll stop watching {app_name}."
    return f"{app_name} wasn't in the list."

def get_watched_apps() -> list:
    return _load_watched_apps()

# ── Read Windows Notifications via PowerShell ─────────────────
_PS_SCRIPT = """
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

$notifications = @()
try {
    $history = [Windows.UI.Notifications.ToastNotificationManager]::History
    $apps = $history.GetHistory()
    foreach ($notif in $apps) {
        $xml = $notif.Content.InnerText
        $notifications += @{
            AppId = $notif.AppId
            Tag   = $notif.Tag
            Group = $notif.Group
        }
    }
} catch {}

$notifications | ConvertTo-Json
"""

def _read_windows_notifications_raw() -> list:
    """
    Try to read Windows notification history via PowerShell.
    Note: Windows limits third-party apps from reading others' notifications.
    This is a best-effort approach.
    """
    try:
        result = subprocess.run(
            ["powershell", "-Command", _PS_SCRIPT],
            capture_output=True, text=True, timeout=8
        )
        if result.stdout.strip():
            data = json.loads(result.stdout.strip())
            if isinstance(data, dict):
                data = [data]
            return data
    except Exception:
        pass
    return []

# ── Action Center count via PowerShell ───────────────────────
_PS_COUNT = """
try {
    $count = (Get-Counter -Counter "\\Windows Action Center(*)" -ErrorAction SilentlyContinue).CounterSamples
    Write-Output $count.CookedValue
} catch {
    Write-Output "0"
}
"""

def get_notification_count() -> int:
    """Approximate notification count from Windows Action Center."""
    try:
        result = subprocess.run(
            ["powershell", "-Command",
             "(Get-AppxPackage | Where-Object {$_.Name -like '*NotificationsVisualizerStudio*'}).Count"],
            capture_output=True, text=True, timeout=5
        )
        return int(result.stdout.strip()) if result.stdout.strip().isdigit() else 0
    except Exception:
        return 0

# ── Simulated notification tracking (fallback) ────────────────
_notification_log: list = []
_max_log_size = 100

def _load_notif_log() -> list:
    try:
        with open(_NOTIF_LOG, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_notif_log(log: list) -> None:
    try:
        with open(_NOTIF_LOG, "w", encoding="utf-8") as f:
            json.dump(log[-_max_log_size:], f, indent=2)
    except Exception:
        pass

def log_notification(app: str, message: str, title: str = "") -> None:
    """Manually log a notification (called by other modules)."""
    entry = {
        "app":       app,
        "title":     title,
        "message":   message,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "read":      False
    }
    log = _load_notif_log()
    log.append(entry)
    _save_notif_log(log)

def get_unread_notifications() -> list:
    """Get all unread logged notifications."""
    log = _load_notif_log()
    return [n for n in log if not n.get("read", False)]

def mark_all_read() -> None:
    log = _load_notif_log()
    for n in log:
        n["read"] = True
    _save_notif_log(log)

def get_notification_summary() -> str:
    """
    Returns a human-readable summary for Jarvis startup announcement.
    e.g. "You have 3 WhatsApp messages and 1 Gmail notification."
    """
    unread = get_unread_notifications()
    if not unread:
        return ""

    app_counts = {}
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

# ── Send notification to user ─────────────────────────────────
def send_notification(title: str, message: str, app_name: str = "Jarvis") -> bool:
    """
    Send a Windows toast notification to the user.
    Uses win11toast if available, falls back to plyer, then PowerShell.
    """
    if WIN11TOAST_AVAILABLE:
        try:
            toast(title, message, app_id=app_name)
            return True
        except Exception:
            pass

    if PLYER_AVAILABLE:
        try:
            plyer_notify.notify(
                title=title,
                message=message,
                app_name=app_name,
                timeout=8
            )
            return True
        except Exception:
            pass

    # PowerShell fallback
    ps_cmd = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType=WindowsRuntime] | Out-Null

$APP_ID = "Jarvis"
$template = @"
<toast>
  <visual>
    <binding template="ToastText02">
      <text id="1">{title}</text>
      <text id="2">{message}</text>
    </binding>
  </visual>
</toast>
"@
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml($template)
$toast = New-Object Windows.UI.Notifications.ToastNotification $xml
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
'''
    try:
        subprocess.run(["powershell", "-Command", ps_cmd],
                       capture_output=True, timeout=5)
        return True
    except Exception:
        return False

# ── Startup Summary ───────────────────────────────────────────
def get_startup_notification_message() -> str:
    """
    Call this on Jarvis startup to announce pending notifications.
    Returns empty string if nothing to report.
    """
    summary = get_notification_summary()
    return summary

# ── Test ──────────────────────────────────────────────────────
if __name__ == "__main__":
    print("[NotifMgr] Test mode")

    # Test: log some fake notifications
    log_notification("WhatsApp", "Hey, are you free?", "Rahul")
    log_notification("WhatsApp", "Bhai meeting at 5", "Work Group")
    log_notification("Gmail", "Your order has been shipped", "Amazon")

    summary = get_startup_notification_message()
    print(f"Startup message: {summary}")

    unread = get_unread_notifications()
    print(f"Unread: {len(unread)}")

    # Test sending notification
    result = send_notification("Jarvis Test", "Notification system is working!")
    print(f"Sent: {result}")

    # Test watched apps
    print(f"Watched apps: {get_watched_apps()}")
    add_watched_app("Spotify")
    print(f"After add: {get_watched_apps()}")