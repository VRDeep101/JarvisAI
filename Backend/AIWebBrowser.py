# ─────────────────────────────────────────────────────────────
#  Backend/AIWebBrowser.py  —  Jarvis AI Website Automation
#
#  ROUTING:
#    Code/programming  →  Claude.ai
#    Content/images    →  ChatGPT
#    Backup            →  Gemini
#
#  SETUP (ek baar):
#    pip install selenium webdriver-manager
#    Pehli baar chalega toh "JarvisAI" naam ka Chrome profile
#    khulega — usme Claude, ChatGPT, Gemini me login kar lo.
#    Baad me sessions save rahenge.
# ─────────────────────────────────────────────────────────────

from selenium                          import webdriver
from selenium.webdriver.common.by      import By
from selenium.webdriver.support.ui     import WebDriverWait
from selenium.webdriver.support        import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys    import Keys
from selenium.common.exceptions        import (
    TimeoutException, WebDriverException
)
import time
import os

# ── Chrome Profile (Jarvis ka alag profile, daily wale se alag) ──
_CHROME_USER_DATA = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "Google", "Chrome", "User Data"
)
_JARVIS_PROFILE = "JarvisAI"   # First run pe automatically ban jayega

# ── AI Site Configurations ─────────────────────────────────────
_SITES = {
    "claude": {
        "name"      : "Claude",
        "url"       : "https://claude.ai/new",
        "input_css" : [
            "div[contenteditable='true'][data-placeholder]",
            "div.ProseMirror",
            "div[contenteditable='true']",
        ],
        "resp_css"  : [
            ".font-claude-message",
            "[data-testid='chat-message-content']",
            "div.prose",
        ],
        "stop_css"  : [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
        ],
        "login_kw"  : ["login", "onboarding", "signin", "sign-in"],
        "max_wait"  : 90,
    },
    "chatgpt": {
        "name"      : "ChatGPT",
        "url"       : "https://chatgpt.com/",
        "input_css" : [
            "#prompt-textarea",
            "div#prompt-textarea",
            "textarea[placeholder]",
        ],
        "resp_css"  : [
            "[data-message-author-role='assistant'] .markdown",
            ".markdown.prose",
            "[data-message-author-role='assistant']",
        ],
        "stop_css"  : [
            "button[data-testid='stop-button']",
            "button[aria-label*='Stop']",
        ],
        "login_kw"  : ["auth/login", "login", "accounts.openai", "chatgpt.com/auth"],
        "max_wait"  : 90,
    },
    "gemini": {
        "name"      : "Gemini",
        "url"       : "https://gemini.google.com/app",
        "input_css" : [
            ".ql-editor[contenteditable='true']",
            "rich-textarea .ql-editor",
            "div[contenteditable='true']",
        ],
        "resp_css"  : [
            "model-response .response-content",
            ".response-content",
            "message-content",
        ],
        "stop_css"  : [
            "button[aria-label*='Stop']",
            "button[aria-label*='stop']",
        ],
        "login_kw"  : ["accounts.google.com"],
        "max_wait"  : 90,
    },
}

# ── Query Routing Logic ────────────────────────────────────────
_CODE_KW = [
    "code", "program", "script", "function", "class", "algorithm",
    "debug", "fix bug", "python", "javascript", "java", "c++", "cpp",
    "html", "css", "sql", "api", "implement", "create app",
    "write code", "code lekh", "code likho", "code banao",
    "website banao", "app banao", "error fix", "bug fix",
]
_CONTENT_KW = [
    "write", "essay", "article", "blog", "story", "email", "letter",
    "generate image", "create image", "thumbnail", "design",
    "content", "post", "caption", "summary", "paragraph", "report",
    "kuch lekh", "likh do", "image bana",
]

def route_query(query: str) -> str:
    """Returns 'claude', 'chatgpt', or 'gemini' based on intent."""
    q  = query.lower()
    cs = sum(1 for k in _CODE_KW    if k in q)
    ct = sum(1 for k in _CONTENT_KW if k in q)
    if cs > 0 and cs >= ct:
        return "claude"
    if ct > 0:
        return "chatgpt"
    return "chatgpt"   # default

def get_pre_message(ai_key: str, query: str = "") -> str:
    """Jarvis kya bolega browser kholne se pehle."""
    n = _SITES[ai_key]["name"]
    q = query.lower()
    if ai_key == "claude":
        return (
            f"Opening {n} for the best output. "
            f"Sir, tell me exactly what you need coded."
        )
    if any(k in q for k in ["image", "thumbnail", "design", "generate"]):
        return f"Searching {n} for the best image generation. Please wait."
    return f"Opening {n} for the best output. Please wait."

def get_fallback_message(from_key: str, to_key: str) -> str:
    return (
        f"Searching {_SITES[to_key]['name']} as there was a "
        f"connection problem with {_SITES[from_key]['name']}."
    )

# ── Chrome Driver ──────────────────────────────────────────────
def _make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument(f"--user-data-dir={_CHROME_USER_DATA}")
    opts.add_argument(f"--profile-directory={_JARVIS_PROFILE}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_argument("--start-maximized")

    try:
        drv = webdriver.Chrome(options=opts)
    except Exception:
        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service
            drv = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()),
                options=opts
            )
        except Exception as e:
            raise RuntimeError(
                f"ChromeDriver nahi mila. Run karo: "
                f"pip install selenium webdriver-manager\nError: {e}"
            )

    drv.execute_script(
        "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
    )
    return drv

# ── Internal Helpers ───────────────────────────────────────────
def _is_login_page(driver, cfg: dict) -> bool:
    url = driver.current_url.lower()
    return any(kw in url for kw in cfg["login_kw"])

def _find_input(driver, selectors: list, timeout: int = 12):
    for sel in selectors:
        try:
            return WebDriverWait(driver, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
            )
        except Exception:
            pass
    # JS fallback
    for sel in selectors:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.is_displayed():
                return el
        except Exception:
            pass
    return None

def _type_query(driver, el, query: str):
    """Textarea aur contenteditable dono ke liye robust typing."""
    el.click()
    time.sleep(0.3)
    try:
        # contenteditable (Claude, Gemini)
        driver.execute_script("""
            arguments[0].focus();
            document.execCommand('selectAll', false, null);
            document.execCommand('insertText', false, arguments[1]);
        """, el, query)
    except Exception:
        # Regular textarea (ChatGPT fallback)
        el.clear()
        el.send_keys(query)
    time.sleep(0.4)
    el.send_keys(Keys.RETURN)

def _wait_for_response(driver, cfg: dict) -> str:
    """AI ka response complete hone tak wait karo, phir extract karo."""
    stop_sels = cfg["stop_css"]
    resp_sels = cfg["resp_css"]
    max_w     = cfg["max_wait"]

    # Phase 1: Stop button appear hone tak wait (AI shuru hua)
    appeared = False
    t0 = time.time()
    while time.time() - t0 < 15:
        for s in stop_sels:
            try:
                b = driver.find_elements(By.CSS_SELECTOR, s)
                if b and b[0].is_displayed():
                    appeared = True
                    break
            except Exception:
                pass
        if appeared:
            break
        time.sleep(0.5)

    # Phase 2: Stop button gayab hone tak wait (AI done)
    if appeared:
        t0 = time.time()
        while time.time() - t0 < max_w:
            try:
                all_gone = all(
                    not any(
                        e.is_displayed()
                        for e in driver.find_elements(By.CSS_SELECTOR, s)
                    )
                    for s in stop_sels
                )
                if all_gone:
                    break
            except Exception:
                pass
            time.sleep(1)
    else:
        # Fallback: text stability check
        prev   = ""
        stable = 0
        t0     = time.time()
        while time.time() - t0 < max_w:
            for s in resp_sels:
                try:
                    els = driver.find_elements(By.CSS_SELECTOR, s)
                    if els:
                        curr = els[-1].text.strip()
                        if curr and curr == prev:
                            stable += 1
                            if stable >= 3:
                                return curr
                        elif curr:
                            prev   = curr
                            stable = 0
                        break
                except Exception:
                    pass
            time.sleep(2)

    time.sleep(1.2)   # Buffer

    # Final extraction
    for s in resp_sels:
        try:
            els = driver.find_elements(By.CSS_SELECTOR, s)
            if els:
                txt = els[-1].text.strip()
                if txt:
                    return txt
        except Exception:
            pass
    return ""

def _truncate_for_speech(text: str, max_words: int = 80) -> str:
    """Long response ko TTS ke liye chhota karo."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + "... Full response is visible on screen."

# ── Main Public Function ───────────────────────────────────────
def ask_ai_website(
    query        : str,
    preferred_ai : str      = None,
    on_status    : callable = None,
) -> dict:
    """
    AI website khole, query bheje, response return kare.

    Parameters:
        query        : User ki query
        preferred_ai : "claude" | "chatgpt" | "gemini"  (optional)
        on_status    : callback fn(message: str) intermediate updates ke liye

    Returns dict:
        pre_message  – browser kholne se PEHLE bolne wala message
        response     – full AI response text
        speech_text  – TTS ke liye chhota version
        ai_used      – "Claude" / "ChatGPT" / "Gemini"
        error        – agar sab fail ho gaye
    """
    _say = on_status or (lambda m: print(f"[AIWeb] {m}"))

    if preferred_ai and preferred_ai.lower() in _SITES:
        p      = preferred_ai.lower()
        others = [k for k in _SITES if k != p]
        order  = [p] + others
    else:
        p      = route_query(query)
        others = [k for k in _SITES if k != p]
        order  = [p] + others

    result = {
        "pre_message" : get_pre_message(order[0], query),
        "response"    : "",
        "speech_text" : "",
        "ai_used"     : "",
        "error"       : "",
    }

    driver = None

    for idx, ai_key in enumerate(order):
        cfg = _SITES[ai_key]

        if idx > 0:
            _say(get_fallback_message(order[idx - 1], ai_key))

        try:
            if driver is None:
                driver = _make_driver()

            driver.get(cfg["url"])
            time.sleep(3)

            # ── Login check ──────────────────────────────────
            if _is_login_page(driver, cfg):
                _say(
                    f"Sir, {cfg['name']} mein sign-in required hai. "
                    f"Browser mein login kar lo — main 60 seconds wait karunga."
                )
                t0 = time.time()
                while time.time() - t0 < 60 and _is_login_page(driver, cfg):
                    time.sleep(2)
                if _is_login_page(driver, cfg):
                    _say(f"{cfg['name']} login timeout. Next AI try kar raha hoon.")
                    continue
                driver.get(cfg["url"])
                time.sleep(3)

            # ── Input dhundo aur type karo ───────────────────
            inp = _find_input(driver, cfg["input_css"], timeout=15)
            if inp is None:
                _say(f"{cfg['name']} pe input box nahi mila. Next try kar raha hoon.")
                continue

            _type_query(driver, inp, query)
            _say(f"{cfg['name']} process kar raha hai. Please wait.")

            # ── Response wait karo ───────────────────────────
            resp = _wait_for_response(driver, cfg)

            if resp and len(resp) > 15:
                result["response"]    = resp
                result["speech_text"] = _truncate_for_speech(resp)
                result["ai_used"]     = cfg["name"]
                return result
            else:
                _say(f"{cfg['name']} se valid response nahi aaya. Next try.")
                continue

        except RuntimeError as e:
            result["error"] = str(e)
            _say(f"Critical error: {e}")
            break

        except WebDriverException:
            _say(f"{cfg['name']} pe browser error. Next AI try kar raha hoon.")
            try:
                driver.quit()
            except Exception:
                pass
            driver = None

        except Exception as e:
            _say(f"{cfg['name']} error: {e}. Next try.")

    if not result["ai_used"]:
        result["error"] = (
            "Sabhi AI websites fail ho gayi. "
            "Internet check karo aur JarvisAI profile mein login verify karo."
        )

    return result