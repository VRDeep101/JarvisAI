import datetime
import json
from pathlib import Path
from googlesearch import search
from groq import Groq
from dotenv import dotenv_values

# ── Config ──────────────────────────────────────────────────────────────────
cfg = dotenv_values(".env")

USERNAME       = cfg.get("Username", "User")
ASSISTANT_NAME = cfg.get("Assistantname", "Assistant")
GROQ_API_KEY   = cfg.get("GroqAPIKey")
CHAT_LOG       = Path("Data/ChatLog.json")
MODEL          = "llama-3.3-70b-versatile"

client = Groq(api_key=GROQ_API_KEY)

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = (
    f"Hello, I am {USERNAME}. "
    f"You are {ASSISTANT_NAME}, a highly accurate AI with real-time internet access. "
    "Answer every question professionally — use proper grammar, punctuation, and full sentences. "
    "Base your answers only on the data provided to you."
)

BASE_CONTEXT = [
    {"role": "system",    "content": SYSTEM_PROMPT},
    {"role": "user",      "content": "Hi"},
    {"role": "assistant", "content": "Hello! How can I help you today?"},
]

# ── Chat log helpers ─────────────────────────────────────────────────────────
def load_history() -> list:
    try:
        return json.loads(CHAT_LOG.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        CHAT_LOG.write_text("[]", encoding="utf-8")
        return []

def save_history(history: list) -> None:
    CHAT_LOG.write_text(
        json.dumps(history, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

# ── Utilities ────────────────────────────────────────────────────────────────
def web_search(query: str) -> str:
    results = list(search(query, advanced=True, num_results=5))
    lines = [f"Search results for '{query}':\n"]
    for r in results:
        lines.append(f"Title: {r.title}\nDescription: {r.description}\n")
    return "\n".join(lines)

def current_datetime() -> str:
    now = datetime.datetime.now()
    return (
        f"Day: {now:%A}\n"
        f"Date: {now:%d}\n"
        f"Month: {now:%B}\n"
        f"Year: {now:%Y}\n"
        f"Time: {now:%H:%M:%S}"
    )

def clean_response(text: str) -> str:
    return "\n".join(
        line for line in text.strip().replace("</s>", "").split("\n")
        if line.strip()
    )

# ── Core engine ──────────────────────────────────────────────────────────────
def ask(user_input: str) -> str:
    history = load_history()
    history.append({"role": "user", "content": user_input})

    messages = BASE_CONTEXT + [
        {"role": "system", "content": web_search(user_input)},
        {"role": "system", "content": current_datetime()},
    ] + history

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        top_p=1,
        stream=True,
    )

    reply = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            reply += delta.content

    reply = clean_response(reply)
    history.append({"role": "assistant", "content": reply})
    save_history(history)
    return reply

# ── CLI entry point ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    print(f"{ASSISTANT_NAME} ready. Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input(":) ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                print("Goodbye!")
                break
            print(f"\n{ASSISTANT_NAME}: {ask(user_input)}\n")
        except KeyboardInterrupt:
            continue
        except EOFError:
            continue