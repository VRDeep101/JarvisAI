import cohere
import os
from dotenv import load_dotenv
import time

load_dotenv()

CohereAPIKey = os.getenv("CohereAPIKey")

if not CohereAPIKey:
    raise ValueError("❌ Cohere API Key missing in .env file")

co = cohere.Client(api_key=CohereAPIKey)

preamble = """
You are a Decision-Making Brain (Router System).

Your ONLY job is to classify user input.

DO NOT answer anything.

Return ONLY in this format:
category query

Categories:
general
realtime
open
close
play
generate image
reminder
system
content
google search
youtube search
exit

Rules:
- If multiple tasks exist, separate them with commas.
- If unsure, return: general query
- No explanation, no extra text.
- "search X on chrome" or "search X on google" = google search X
- "open X and search Y" = open X, google search Y
- "search X on claude" or "open claude and search X" = open claude, google search X
- Website names like claude.ai, chatgpt.com are opened with open command
"""

# FIX: Zyada examples add kiye — especially chrome/search ke liye
ChatHistory = [
    {"role": "USER",    "message": "hello how are you"},
    {"role": "CHATBOT", "message": "general hello how are you"},

    {"role": "USER",    "message": "what is net worth of elon musk"},
    {"role": "CHATBOT", "message": "realtime what is net worth of elon musk"},

    {"role": "USER",    "message": "open chrome and instagram"},
    {"role": "CHATBOT", "message": "open chrome, open instagram"},

    {"role": "USER",    "message": "play shape of you"},
    {"role": "CHATBOT", "message": "play shape of you"},

    {"role": "USER",    "message": "close whatsapp and telegram"},
    {"role": "CHATBOT", "message": "close whatsapp, close telegram"},

    # FIX: Chrome search examples
    {"role": "USER",    "message": "search python tutorial on chrome"},
    {"role": "CHATBOT", "message": "google search python tutorial"},

    {"role": "USER",    "message": "open chrome and search claude ai"},
    {"role": "CHATBOT", "message": "open chrome, google search claude ai"},

    {"role": "USER",    "message": "search claude on google"},
    {"role": "CHATBOT", "message": "google search claude"},

    {"role": "USER",    "message": "open claude.ai"},
    {"role": "CHATBOT", "message": "open claude.ai"},

    {"role": "USER",    "message": "search news today on chrome"},
    {"role": "CHATBOT", "message": "google search news today"},

    {"role": "USER",    "message": "generate image of a sunset"},
    {"role": "CHATBOT", "message": "generate image sunset"},

    {"role": "USER",    "message": "generate a picture of a dog"},
    {"role": "CHATBOT", "message": "generate image dog"},
]

def Brain(prompt: str):
    for attempt in range(3):
        try:
            response = co.chat(
                model="command-a-03-2025",
                message=prompt,
                chat_history=ChatHistory,
                preamble=preamble,
                temperature=0.2
            )

            output = response.text.strip().lower()
            tasks  = [t.strip() for t in output.replace("\n", "").split(",") if t.strip()]
            return tasks

        except Exception as e:
            print(f"⚠️ Network error... Scanning ({attempt+1}/3)")
            time.sleep(2)

    return ["error: network issue"]