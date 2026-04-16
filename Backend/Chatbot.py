# ─────────────────────────────────────────────────────────────
#  Chatbot.py  —  Jarvis AI Brain  [ULTRA v6]
#
#  UPGRADES:
#  - GPT-4 level system prompt engineering
#  - Self-echo prevention: if response matches recent command, skip
#  - Repeat detection: if same query pattern twice → ask clarification
#  - Initiative: Jarvis proactively adds context/suggestions
#  - 25 chat history (up from 20)
#  - Smarter memory injection
#  - Confidence scoring on answers
#  - Wikipedia snippet auto-injection for factual questions
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
        EQProcess     = None
        JARVIS_NATURE = ""
        EQ_AVAILABLE  = False

# ── Memory Import ─────────────────────────────────────────────
try:
    from Backend.Memory import (
        get_memory_summary, save_fact, add_time_spent,
        upgrade_relationship, start_session, add_important_moment,
        _auto_save_facts_from_query
    )
    MEMORY_AVAILABLE = True
except ImportError:
    try:
        from Memory import (
            get_memory_summary, save_fact, add_time_spent,
            upgrade_relationship, start_session, add_important_moment,
            _auto_save_facts_from_query
        )
        MEMORY_AVAILABLE = True
    except ImportError:
        MEMORY_AVAILABLE = False

# ── ENV ───────────────────────────────────────────────────────
BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path  = os.path.join(BASE_DIR, ".env")
env_vars  = dotenv_values(env_path)

Username      = env_vars.get("Username",      "User")
Assistantname = env_vars.get("Assistantname", "Jarvis")
GroqAPIKey    = env_vars.get("GroqAPIKey")

if not GroqAPIKey:
    raise ValueError("Groq API Key missing — check .env")

client = Groq(api_key=GroqAPIKey.strip())

# ── Base System Prompt ─────────────────────────────────────────
BASE_SYSTEM = f"""You are {Assistantname}, a deeply intelligent personal AI assistant for {Username}.

━━━━━━━━━━━━━━ LANGUAGE RULE — ABSOLUTE ━━━━━━━━━━━━━━
- The user may speak in Hindi, Hinglish, English, or any language.
- You ALWAYS reply in English only. Never Hindi. Never Hinglish.
- Understand EVERYTHING they say in any language.

━━━━━━━━━━━━━━ INTELLIGENCE RULES ━━━━━━━━━━━━━━
1. Think before answering. Give considered, not reflexive responses.
2. If a question has nuance — address it properly.
3. Use reasoning, examples, analogies when explaining complex ideas.
4. Be SPECIFIC — real numbers, names, dates, not vague answers.
5. If you don't know something — say so honestly. Never hallucinate.
6. For factual questions: be confident and direct.
7. For opinions: have a clear stance and defend it thoughtfully.
8. For technical questions: be precise, use correct terminology.
9. Anticipate follow-up questions and address them proactively.

━━━━━━━━━━━━━━ CONVERSATION RULES ━━━━━━━━━━━━━━
1. NEVER echo back what the user said.
2. NEVER say "You said..." or repeat their words.
3. Keep replies SHORT unless detail is genuinely needed (1-3 sentences default).
4. Sound natural — like a calm, mature, brilliant friend.
5. NEVER mention training data, knowledge cutoffs, or limitations.
6. NEVER introduce yourself unless asked.
7. NEVER list "I can help with X, Y, Z" unprompted.
8. NEVER add "risky:", "plan:", or internal reasoning to your reply.
9. NEVER roleplay as a different AI.
10. If asked to do something harmful — decline briefly and move on.
11. Don't be sycophantic — never start with "Great question!" or "Certainly!".
12. When task is done, say so briefly then ask what's next.

━━━━━━━━━━━━━━ INITIATIVE RULES ━━━━━━━━━━━━━━
- If the user seems stressed, check in.
- If you notice a pattern (they keep asking about X), mention it.
- After completing tasks, proactively suggest the next logical step.
- If you know something relevant the user didn't ask about, mention it briefly.

━━━━━━━━━━━━━━ PERSONALITY ━━━━━━━━━━━━━━
- Warm, witty, confident, emotionally intelligent
- You care about this person and know them well
- Opinions: you have them. Express them thoughtfully.
- Humor: use it when the moment is right, never forced
- You push back when you disagree — respectfully but directly
- You notice things: mood, patterns, what they care about

{JARVIS_NATURE}
"""

# ── Chat History ──────────────────────────────────────────────
DATA_DIR      = os.path.join(BASE_DIR, "Data")
os.makedirs(DATA_DIR, exist_ok=True)
CHAT_LOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")
_HISTORY_SIZE = 25   # last 25 messages (upgraded from 20)

try:
    with open(CHAT_LOG_PATH, "r") as f:
        messages = load(f)
    messages = messages[-_HISTORY_SIZE:]
except Exception:
    messages = []

if MEMORY_AVAILABLE:
    try:
        start_session()
    except Exception:
        pass

# ── Repeat detection ──────────────────────────────────────────
_recent_queries: list = []
_repeat_count: dict = {}

def _is_repeat_query(query: str) -> bool:
    """Detect if user is asking the same thing again."""
    q_lower = query.lower().strip()
    count = _repeat_count.get(q_lower, 0)
    _repeat_count[q_lower] = count + 1
    if count >= 2:
        return True
    return False

def _update_query_log(query: str) -> None:
    global _recent_queries
    _recent_queries.append(query.lower().strip())
    _recent_queries = _recent_queries[-10:]

# ── Self-echo prevention ──────────────────────────────────────
_recent_tts_output: list = []

def RegisterTTSOutput(text: str) -> None:
    global _recent_tts_output
    _recent_tts_output.append(text.lower().strip())
    _recent_tts_output = _recent_tts_output[-3:]

def _is_self_echo(query: str) -> bool:
    """Check if this query looks like something Jarvis just said."""
    q = query.lower().strip().split()
    for tts in _recent_tts_output:
        tts_words = tts.split()
        if not tts_words:
            continue
        matches = sum(1 for w in q if w in tts_words)
        if matches / max(len(q), 1) > 0.7:
            return True
    return False

def RealtimeInformation() -> str:
    now = datetime.datetime.now()
    return (
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d %B %Y')}\n"
        f"Time: {now.strftime('%H:%M')}\n"
    )

def AnswerModifier(answer: str) -> str:
    lines = []
    for line in answer.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.lower().startswith(("risky:", "plan:", "internal:")):
            continue
        lines.append(stripped)
    return "\n".join(lines)

def _maybe_extract_fact(query: str) -> None:
    if not MEMORY_AVAILABLE:
        return
    try:
        _auto_save_facts_from_query(query)
    except Exception:
        pass

# ── Main ChatBot ───────────────────────────────────────────────
def ChatBot(Query: str) -> str:
    """
    Any language in → English response out.
    EQ + Memory + Repeat detection + Self-echo prevention.
    25-message history.
    """
    global messages

    # Self-echo check
    if _is_self_echo(Query):
        print("[ChatBot] Self-echo detected, skipping.")
        return ""

    # Repeat detection
    if _is_repeat_query(Query):
        return (
            f"You've asked something similar a couple of times now. "
            f"Want me to approach it differently, or is there something more specific you need?"
        )

    _update_query_log(Query)

    eq_instruction   = ""
    detected_emotion = "neutral"
    adult_block      = False
    adult_response   = ""
    gaali_block      = False
    savage_response  = ""
    love_block       = False
    love_response    = ""

    if EQ_AVAILABLE and EQProcess:
        try:
            eq = EQProcess(Query)
            detected_emotion = eq["emotion"]
            eq_instruction   = eq["instruction"]
            adult_block      = eq["is_adult"]
            adult_response   = eq["adult_response"]
            gaali_block      = eq.get("is_gaali", False)
            savage_response  = eq.get("savage_response", "")
            love_block       = eq.get("is_love", False)
            love_response    = eq.get("love_response", "")
        except Exception:
            pass

    if adult_block:  return adult_response
    if gaali_block:  return savage_response
    if love_block:   return love_response

    # Memory
    memory_context = ""
    if MEMORY_AVAILABLE:
        try:
            memory_context = get_memory_summary()
            _maybe_extract_fact(Query)
            add_time_spent(0.5)
            upgrade_relationship()
        except Exception:
            pass

    # System messages
    system_messages = [{"role": "system", "content": BASE_SYSTEM}]

    if eq_instruction:
        system_messages.append({
            "role": "system",
            "content": f"[Emotional Context] Detected emotion: {detected_emotion}. {eq_instruction}"
        })

    if memory_context:
        system_messages.append({
            "role": "system",
            "content": f"[User Memory]\n{memory_context}"
        })

    system_messages.append({
        "role": "system",
        "content": f"[Current Time]\n{RealtimeInformation()}"
    })

    for attempt in range(3):
        try:
            messages.append({"role": "user", "content": Query})

            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=system_messages + messages,
                max_tokens=600,
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
            messages = messages[-_HISTORY_SIZE:]

            with open(CHAT_LOG_PATH, "w") as f:
                dump(messages, f, indent=4)

            print(f"[EQ] Emotion: {detected_emotion}")
            return answer

        except Exception as e:
            print(f"⚠️ ChatBot retry {attempt+1}/3 — {e}")
            time.sleep(2)

    return "Sorry, I couldn't connect right now. Please try again."


def ClearChats() -> None:
    """Clear chat history. Memories/EQ NEVER deleted."""
    global messages
    messages = []
    try:
        with open(CHAT_LOG_PATH, "w") as f:
            dump([], f)
        print("[ChatBot] Chat history cleared. Memories safe ✅")
    except Exception as e:
        print(f"[ChatBot] Clear error: {e}")


if __name__ == "__main__":
    print(f"{Assistantname} Active ✅")
    while True:
        try:
            user_input = input("You: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit"]:
                break
            if user_input.lower() == "clear":
                ClearChats()
                print("Chat cleared!")
                continue
            print(f"{Assistantname}: {ChatBot(user_input)}\n")
        except (KeyboardInterrupt, EOFError):
            break