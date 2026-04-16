# ─────────────────────────────────────────────────────────────
#  RealtimeSearchEngine.py  —  Jarvis Real-Time Search  [FIXED v3]
#
#  FIXES:
#  1. STALE RESULTS FIX:
#     - Har query ke saath fresh DDGS search
#     - Cache bilkul nahi — hamesha fresh
#     - Current date/time always included in context
#     - Wikipedia fallback for deep knowledge queries
#  2. LANGUAGE: Always English reply
#  3. SMART ROUTING: Simple facts → direct, complex → search
#  4. Wikipedia API integration for encyclopedic queries
# ─────────────────────────────────────────────────────────────

import datetime
import json
from pathlib import Path
from groq import Groq
from dotenv import dotenv_values
import time
import re

# ── Optional imports ─────────────────────────────────────────
try:
    from ddgs import DDGS
    _DDGS_AVAILABLE = True
except ImportError:
    try:
        from duckduckgo_search import DDGS
        _DDGS_AVAILABLE = True
    except ImportError:
        _DDGS_AVAILABLE = False

try:
    import wikipedia
    wikipedia.set_lang("en")
    _WIKI_AVAILABLE = True
except ImportError:
    _WIKI_AVAILABLE = False

try:
    import requests
    _REQUESTS_AVAILABLE = True
except ImportError:
    _REQUESTS_AVAILABLE = False

cfg = dotenv_values(".env")

USERNAME       = cfg.get("Username", "User")
ASSISTANT_NAME = cfg.get("Assistantname", "Jarvis")
GROQ_API_KEY   = cfg.get("GroqAPIKey")
CHAT_LOG       = Path("Data/ChatLog.json")
MODEL          = "llama-3.3-70b-versatile"

client = Groq(api_key=GROQ_API_KEY)

SYSTEM_PROMPT = f"""You are {ASSISTANT_NAME}, an intelligent AI assistant for {USERNAME}.

CRITICAL LANGUAGE RULE:
- ALWAYS reply in English, regardless of what language the user spoke.
- Understand Hindi, Hinglish, any language — but reply ONLY in English.

CRITICAL ACCURACY RULES:
1. Web search results will be provided inside [WEB SEARCH RESULTS] tags.
2. You MUST use these search results as your PRIMARY source.
3. NEVER say "as of my knowledge" or "I don't have real-time access" — results are provided.
4. Give DIRECT, SPECIFIC answers with real numbers, names, dates from results.
5. If Wikipedia data is provided, use it for factual/encyclopedic questions.
6. Keep answers concise — 2-4 sentences for simple facts, more if complex.
7. Sound like a smart, confident friend — not a search engine readout.
8. NEVER make up data — if search has no answer, say so honestly."""


def load_history() -> list:
    try:
        return json.loads(CHAT_LOG.read_text(encoding="utf-8"))[-10:]
    except Exception:
        CHAT_LOG.parent.mkdir(parents=True, exist_ok=True)
        return []


def save_history(history: list) -> None:
    try:
        CHAT_LOG.write_text(
            json.dumps(history[-20:], indent=4, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception:
        pass


def current_datetime() -> str:
    now = datetime.datetime.now()
    return f"{now:%A}, {now:%d %B %Y}, {now:%H:%M:%S}"


def web_search(query: str, max_results: int = 6) -> str:
    """Always fresh search — no caching."""
    if not _DDGS_AVAILABLE:
        return "Search engine not available. (pip install duckduckgo-search)"

    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(
                    query,
                    max_results=max_results,
                    region="in-en",   # India-English for relevance
                    safesearch="off",
                ))

            if not results:
                return "No search results found."

            lines = []
            for i, r in enumerate(results, 1):
                title  = r.get('title', '').strip()
                body   = r.get('body', '').strip()
                source = r.get('href', '').strip()
                if title or body:
                    lines.append(f"[{i}] {title}\n{body}\nSource: {source}")

            return "\n\n".join(lines)

        except Exception as e:
            if attempt < 2:
                time.sleep(1)
            else:
                return f"Search failed after 3 attempts: {e}"

    return "Search unavailable."


def wikipedia_search(query: str) -> str:
    """Wikipedia se encyclopedic info lo."""
    if not _WIKI_AVAILABLE:
        # Fallback: Wikipedia API directly
        if _REQUESTS_AVAILABLE:
            try:
                url = "https://en.wikipedia.org/w/api.php"
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 1,
                }
                r = requests.get(url, params=params, timeout=5)
                data = r.json()
                hits = data.get("query", {}).get("search", [])
                if hits:
                    snippet = hits[0].get("snippet", "")
                    # Clean HTML tags
                    snippet = re.sub(r'<[^>]+>', '', snippet)
                    return f"Wikipedia: {snippet}"
            except Exception:
                pass
        return ""

    try:
        results = wikipedia.search(query, results=1)
        if not results:
            return ""
        summary = wikipedia.summary(results[0], sentences=3, auto_suggest=False)
        return f"Wikipedia ({results[0]}): {summary}"
    except Exception:
        return ""


def _should_use_wikipedia(query: str) -> bool:
    """Detect encyclopedic queries that benefit from Wikipedia."""
    wiki_triggers = [
        "who is", "who was", "what is", "what are", "history of",
        "born in", "biography", "founder of", "invented", "discovered",
        "capital of", "population of", "located in", "meaning of",
        "definition of", "explain", "how does", "why does",
        "kaun hai", "kya hai", "batao", "bata", "explain karo"
    ]
    q_lower = query.lower()
    return any(t in q_lower for t in wiki_triggers)


def clean_response(text: str) -> str:
    return "\n".join(
        line for line in text.strip().replace("</s>", "").split("\n")
        if line.strip()
    )


def ask(user_input: str) -> str:
    """
    Main entry. Always searches fresh. Always returns English.
    """
    history = load_history()
    now     = current_datetime()

    # ── Web Search (always fresh) ──────────────────────────────
    print(f"[RTS] Searching: {user_input[:60]}")
    search_results = web_search(user_input)

    # ── Wikipedia supplement (for knowledge queries) ───────────
    wiki_data = ""
    if _should_use_wikipedia(user_input):
        print(f"[RTS] Wikipedia lookup: {user_input[:40]}")
        wiki_data = wikipedia_search(user_input)

    # ── Build augmented message ────────────────────────────────
    wiki_section = f"\n[WIKIPEDIA DATA]\n{wiki_data}" if wiki_data else ""

    augmented_message = f"""[CURRENT DATE & TIME]
{now}

[WEB SEARCH RESULTS — FRESH AS OF NOW]
{search_results}{wiki_section}

[USER QUERY]
{user_input}

Instructions:
- Use the search results above as your primary source.
- Give a direct, specific answer with real facts/numbers from results.
- Reply in English only.
- Do NOT say you lack real-time access — you have search results right here.
- Be concise and natural."""

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append(msg)
    messages.append({"role": "user", "content": augmented_message})

    for attempt in range(3):
        try:
            stream = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                temperature=0.4,
                max_tokens=800,
                top_p=1,
                stream=True,
            )

            reply = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    reply += delta.content

            reply = clean_response(reply)

            history.append({"role": "user",      "content": user_input})
            history.append({"role": "assistant",  "content": reply})
            save_history(history)
            return reply

        except Exception as e:
            print(f"[RTS] Error attempt {attempt+1}: {e}")
            if attempt < 2:
                time.sleep(1)

    return "I couldn't fetch results right now. Please try again."


if __name__ == "__main__":
    print(f"{ASSISTANT_NAME} Realtime Search ready. Type 'exit' to quit.\n")
    while True:
        try:
            user_input = input(":) ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("exit", "quit"):
                break
            result = ask(user_input)
            print(f"\n{ASSISTANT_NAME}: {result}\n")
        except KeyboardInterrupt:
            break