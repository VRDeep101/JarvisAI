import datetime
import json
from pathlib import Path
from ddgs import DDGS
from groq import Groq
from dotenv import dotenv_values

cfg = dotenv_values(".env")

USERNAME       = cfg.get("Username", "User")
ASSISTANT_NAME = cfg.get("Assistantname", "Assistant")
GROQ_API_KEY   = cfg.get("GroqAPIKey")
CHAT_LOG       = Path("Data/ChatLog.json")
MODEL          = "llama-3.3-70b-versatile"

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an AI assistant for {USERNAME}.

CRITICAL RULES:
1. Web search results will be provided inside [WEB SEARCH RESULTS] tags.
2. You MUST use these search results as your PRIMARY and MOST TRUSTED source.
3. NEVER say you don't have real-time access — search results are always provided.
4. NEVER say "as of my knowledge cutoff" — always use the search results.
5. Give direct, confident, specific answers with actual numbers and facts from the results.
6. If the user speaks in Hindi or Hinglish, reply in the same language.
7. Keep answers concise and professional."""


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


def web_search(query: str) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))

        if not results:
            return "No search results found."

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"Result {i}:\n"
                f"Title: {r.get('title', '')}\n"
                f"Info: {r.get('body', '')}\n"
                f"Source: {r.get('href', '')}\n"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"Search failed: {e}"


def current_datetime() -> str:
    now = datetime.datetime.now()
    return f"{now:%A}, {now:%d %B %Y}, {now:%H:%M:%S}"


def clean_response(text: str) -> str:
    return "\n".join(
        line for line in text.strip().replace("</s>", "").split("\n")
        if line.strip()
    )


def ask(user_input: str) -> str:
    history = load_history()

    search_results = web_search(user_input)
    now = current_datetime()

    augmented_message = f"""[CURRENT DATE & TIME]
{now}

[WEB SEARCH RESULTS]
{search_results}

[USER QUESTION]
{user_input}

Instructions: Answer using the web search results above as your primary source. Be direct, specific, and include real numbers/facts from the results. Do not say you lack real-time access."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    for msg in history:
        messages.append(msg)

    messages.append({"role": "user", "content": augmented_message})

    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.5,
        max_tokens=1024,
        top_p=1,
        stream=True,
    )

    reply = ""
    for chunk in stream:
        delta = chunk.choices[0].delta
        if delta and delta.content:
            reply += delta.content
            print(delta.content, end="", flush=True)

    print()
    reply = clean_response(reply)

    history.append({"role": "user", "content": user_input})
    history.append({"role": "assistant", "content": reply})
    save_history(history)
    return reply


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
            print(f"\n{ASSISTANT_NAME}: ", end="")
            ask(user_input)
            print()
        except KeyboardInterrupt:
            print("\n(Interrupted)")
            continue
        except EOFError:
            break