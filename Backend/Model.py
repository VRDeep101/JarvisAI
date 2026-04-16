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
- "screenshot" or "take screenshot" = system screenshot
- "screen recording" or "record screen" = system start screen recording
- "stop recording" = system stop screen recording
- "bluetooth on/off" = system bluetooth on / system bluetooth off
- "brightness up/down" = system brightness up / system brightness down
- "lock screen" = system lock screen
- "clear chats" or "clear old chats" = general clear old chats
- "volume up/down/mute" = system volume up / system volume down / system mute
- Website names like claude.ai, chatgpt.com are opened with open command
"""

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

    {"role": "USER",    "message": "search python tutorial on chrome"},
    {"role": "CHATBOT", "message": "google search python tutorial"},

    {"role": "USER",    "message": "take a screenshot"},
    {"role": "CHATBOT", "message": "system screenshot"},

    {"role": "USER",    "message": "start screen recording"},
    {"role": "CHATBOT", "message": "system start screen recording"},

    {"role": "USER",    "message": "stop screen recording"},
    {"role": "CHATBOT", "message": "system stop screen recording"},

    {"role": "USER",    "message": "bluetooth on karo"},
    {"role": "CHATBOT", "message": "system bluetooth on"},

    {"role": "USER",    "message": "bluetooth band karo"},
    {"role": "CHATBOT", "message": "system bluetooth off"},

    {"role": "USER",    "message": "brightness badhao"},
    {"role": "CHATBOT", "message": "system brightness up"},

    {"role": "USER",    "message": "brightness kam karo"},
    {"role": "CHATBOT", "message": "system brightness down"},

    {"role": "USER",    "message": "lock the screen"},
    {"role": "CHATBOT", "message": "system lock screen"},

    {"role": "USER",    "message": "volume up karo"},
    {"role": "CHATBOT", "message": "system volume up"},

    {"role": "USER",    "message": "volume down karo"},
    {"role": "CHATBOT", "message": "system volume down"},

    {"role": "USER",    "message": "mute karo"},
    {"role": "CHATBOT", "message": "system mute"},

    {"role": "USER",    "message": "generate image of a sunset"},
    {"role": "CHATBOT", "message": "generate image sunset"},

    {"role": "USER",    "message": "clear old chats"},
    {"role": "CHATBOT", "message": "general clear old chats"},

    {"role": "USER",    "message": "open claude.ai"},
    {"role": "CHATBOT", "message": "open claude.ai"},

    {"role": "USER",    "message": "search news today on chrome"},
    {"role": "CHATBOT", "message": "google search news today"},
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