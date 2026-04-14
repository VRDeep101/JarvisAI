# ─────────────────────────────────────────────────────────────
#  Chatbot.py  —  Jarvis AI Brain
#  - Kisi bhi language mein samjhe, English mein reply kare
#  - EQ emotion aware responses
#  - Memory integrated — emotions/facts yaad rehte hain
#  - No random "risky:" lines
#  - Short, smart, natural replies
# ─────────────────────────────────────────────────────────────

from groq import Groq
from json import load, dump
import datetime
import os
import time
from dotenv import dotenv_values

# ── EQ Import ─────────────────────────────────────────────────
try:
    from Backend.Eq import EQProcess, JARVIS_NATURE
    EQ_AVAILABLE = True
except ImportError:
    try:
        from Eq import EQProcess, JARVIS_NATURE
        EQ_AVAILABLE = True
    except ImportError:
        EQProcess      = None
        JARVIS_NATURE  = ""
        EQ_AVAILABLE   = False

# ── Memory Import ─────────────────────────────────────────────
try:
    from Backend.Memory import (
        get_memory_summary, save_fact, add_time_spent,
        upgrade_relationship, start_session, add_important_moment
    )
    MEMORY_AVAILABLE = True
except ImportError:
    try:
        from Memory import (
            get_memory_summary, save_fact, add_time_spent,
            upgrade_relationship, start_session, add_important_moment
        )
        MEMORY_AVAILABLE = True
    except ImportError:
        MEMORY_AVAILABLE = False

# ── ENV Setup ─────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path  = os.path.join(BASE_DIR, ".env")
env_vars  = dotenv_values(env_path)

Username      = env_vars.get("Username", "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")
GroqAPIKey    = env_vars.get("GroqAPIKey")

if not GroqAPIKey:
    raise ValueError("Groq API Key missing — check .env")

client = Groq(api_key=GroqAPIKey.strip())

# ── Base System Prompt ─────────────────────────────────────────
BASE_SYSTEM = f"""You are {Assistantname}, a smart personal AI assistant for {Username}.

LANGUAGE RULE — VERY IMPORTANT:
- The user may speak in Hindi, Hinglish, English, or any mix.
- You ALWAYS reply in English only. Never switch to Hindi.
- But understand EVERYTHING they say regardless of language.

STRICT RULES:
1. NEVER repeat or echo back what the user said.
2. NEVER say things like "You said..." or parrot their words.
3. Keep replies SHORT — 1 to 3 sentences unless detail is asked.
4. Do NOT mention your training data, knowledge cutoff, or limitations.
5. Sound natural — like a calm, mature, helpful friend.
6. If unclear, ask ONE short clarifying question only.
7. NEVER start with "{Username} said" or any similar phrase.
8. NEVER introduce yourself unless directly asked.
9. Do NOT offer "I can help with X, Y, Z" lists unprompted.
10. NEVER add "risky:" or plan-like internal notes in your reply.
11. NEVER roleplay or simulate being a different AI.

{JARVIS_NATURE}
"""

# ── Chat History ──────────────────────────────────────────────
DATA_DIR      = os.path.join(BASE_DIR, "Data")
os.makedirs(DATA_DIR, exist_ok=True)
CHAT_LOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")

try:
    with open(CHAT_LOG_PATH, "r") as f:
        messages = load(f)
    messages = messages[-20:]  # last 20 only — no loops
except Exception:
    messages = []

# Start memory session
if MEMORY_AVAILABLE:
    try:
        start_session()
    except Exception:
        pass

# ── Realtime Info ──────────────────────────────────────────────
def RealtimeInformation() -> str:
    now = datetime.datetime.now()
    return (
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d %B %Y')}\n"
        f"Time: {now.strftime('%H:%M')}\n"
    )

# ── Response Cleaner ───────────────────────────────────────────
def AnswerModifier(answer: str) -> str:
    # Remove any "risky:" or plan-like prefixes the LLM might add
    lines = []
    for line in answer.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # Block internal plan leakage
        if stripped.lower().startswith("risky:"):
            continue
        if stripped.lower().startswith("plan:"):
            continue
        lines.append(stripped)
    return "\n".join(lines)

# ── Auto Fact Extraction ───────────────────────────────────────
def _maybe_extract_fact(query: str) -> None:
    """Agar user ne koi personal fact share kiya — save karo."""
    if not MEMORY_AVAILABLE:
        return
    q = query.lower()
    triggers = [
        ("i am a ", "User is a "),
        ("i'm a ", "User is a "),
        ("i work as", "User works as"),
        ("i love ", "User loves "),
        ("i hate ", "User hates "),
        ("i like ", "User likes "),
        ("mera naam", "User's name mentioned"),
        ("i study ", "User studies "),
        ("mujhe pasand", "User likes something"),
    ]
    for trigger, label in triggers:
        if trigger in q:
            snippet = query[query.lower().find(trigger):query.lower().find(trigger)+60]
            try:
                save_fact(f"{label}: {snippet}")
            except Exception:
                pass
            break

# ── Main ChatBot ───────────────────────────────────────────────
def ChatBot(Query: str) -> str:
    """
    Takes user query (any language) → returns English response.
    EQ + Memory aware.
    """
    global messages

    # ── EQ Processing ──
    eq_instruction   = ""
    detected_emotion = "neutral"
    adult_block      = False
    adult_response   = ""

    if EQ_AVAILABLE and EQProcess:
        eq = EQProcess(Query)
        detected_emotion = eq["emotion"]
        eq_instruction   = eq["instruction"]
        adult_block      = eq["is_adult"]
        adult_response   = eq["adult_response"]

    # Block adult content immediately
    if adult_block:
        return adult_response

    # ── Memory ──
    memory_context = ""
    if MEMORY_AVAILABLE:
        try:
            memory_context = get_memory_summary()
            _maybe_extract_fact(Query)
            add_time_spent(0.5)
            upgrade_relationship()
        except Exception:
            pass

    # ── Build System Messages ──
    system_messages = [{"role": "system", "content": BASE_SYSTEM}]

    if eq_instruction:
        system_messages.append({
            "role": "system",
            "content": f"[Emotional Context] {eq_instruction}"
        })

    if memory_context:
        system_messages.append({
            "role": "system",
            "content": f"[What you know about this user]\n{memory_context}"
        })

    system_messages.append({
        "role": "system",
        "content": f"[Current Time]\n{RealtimeInformation()}"
    })

    # ── API Call with Retry ──
    for attempt in range(3):
        try:
            messages.append({"role": "user", "content": Query})

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=system_messages + messages,
                max_tokens=512,
                temperature=0.65,
                top_p=1,
                stream=True,
            )

            answer = ""
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    answer += chunk.choices[0].delta.content

            answer = answer.replace("</s>", "").strip()
            answer = AnswerModifier(answer)

            messages.append({"role": "assistant", "content": answer})

            # Keep last 20 messages
            messages = messages[-20:]

            with open(CHAT_LOG_PATH, "w") as f:
                dump(messages, f, indent=4)

            print(f"[EQ] Emotion: {detected_emotion}")
            return answer

        except Exception as e:
            print(f"⚠️ ChatBot retry {attempt+1}/3 — {e}")
            time.sleep(2)

    return "Sorry, I couldn't connect right now. Please try again."


# ── Clear Old Chats (NOT memories) ────────────────────────────
def ClearChats() -> None:
    """
    Chat history clear karo — emotions aur memories safe rehti hain.
    """
    global messages
    messages = []
    try:
        with open(CHAT_LOG_PATH, "w") as f:
            dump([], f)
        print("[ChatBot] Chat history cleared. Memories safe ✅")
    except Exception as e:
        print(f"[ChatBot] Clear error: {e}")


# ── Entry Point ────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"{Assistantname} Active ✅ (type 'exit' to quit, 'clear' to reset chat)")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                print("Later! 👋")
                break
            if user_input.lower() == "clear":
                ClearChats()
                print("Chat cleared!")
                continue
            print(f"{Assistantname}: {ChatBot(user_input)}\n")
        except KeyboardInterrupt:
            break
        except EOFError:
            continue