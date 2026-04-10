from groq import Groq
from json import load, dump
import datetime
import os
import sys
import time
from dotenv import dotenv_values

# ---------------- ENV SETUP ----------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")

env_vars = dotenv_values(env_path)

Username = env_vars.get("Username")
Assistantname = env_vars.get("Assistantname")
GroqAPIKey = env_vars.get("GroqAPIKey")

if not GroqAPIKey:
    raise ValueError("Groq API Key missing — check .env location")

client = Groq(api_key=GroqAPIKey.strip())

# ---------------- SYSTEM PROMPT ----------------
System = f"""Hello, I am {Username}. You are a very accurate and advanced AI chatbot named {Assistantname}.
Do not tell time unless asked. Keep replies short and to the point.
Reply only in English, even if the question is in Hindi.
Do not mention training data or limitations.
"""

SystemChatBot = [{"role": "system", "content": System}]

# ---------------- CHAT HISTORY ----------------
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Data")
os.makedirs(DATA_DIR, exist_ok=True)
CHAT_LOG_PATH = os.path.join(DATA_DIR, "ChatLog.json")

try:
    with open(CHAT_LOG_PATH, "r") as f:
        messages = load(f)
except Exception:
    messages = []

# ---------------- REALTIME INFO ----------------
def RealtimeInformation():
    now = datetime.datetime.now()
    return (
        f"Day: {now.strftime('%A')}\n"
        f"Date: {now.strftime('%d')}\n"
        f"Month: {now.strftime('%B')}\n"
        f"Year: {now.strftime('%Y')}\n"
        f"Time: {now.strftime('%H:%M:%S')}\n"
    )

# ---------------- RESPONSE CLEANER ----------------
def AnswerModifier(Answer):
    return "\n".join(line for line in Answer.split("\n") if line.strip())

# ---------------- CHATBOT ----------------
def ChatBot(Query):
    for attempt in range(3):
        try:
            messages.append({"role": "user", "content": Query})

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=SystemChatBot + [
                    {"role": "system", "content": RealtimeInformation()}
                ] + messages,
                max_tokens=1024,
                temperature=0.7,
                top_p=1,
                stream=True,
            )

            Answer = ""
            for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    Answer += chunk.choices[0].delta.content

            Answer = Answer.replace("</s>", "").strip()

            messages.append({"role": "assistant", "content": Answer})

            with open(CHAT_LOG_PATH, "w") as f:
                dump(messages, f, indent=4)

            return AnswerModifier(Answer)

        except Exception as e:
            print(f"⚠️ Network error... Retrying ({attempt+1}/3)")
            time.sleep(2)

    return "Error: Could not connect."

# ---------------- MAIN ----------------
if __name__ == "__main__":
    print(f"{Assistantname} Activated ✅")

    while True:
        try:
            user_input = input(":) ").strip()

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye 👋")
                break

            print(ChatBot(user_input))

        except KeyboardInterrupt:
            print("\nLoading Modules...")
            continue

        except EOFError:
            continue