# ─────────────────────────────────────────────────────────────
#  ImageGeneration.py  —  Jarvis Image Generator
#  - HuggingFace FLUX model
#  - Prompt clean karo automatically
#  - Images Data folder mein save
# ─────────────────────────────────────────────────────────────

import asyncio
from PIL import Image
from dotenv import get_key
import os
from time import sleep
from huggingface_hub import InferenceClient

client = InferenceClient(api_key=get_key(".env", "HuggingFaceAPIKey"))

DATA_FILE = os.path.join("Frontend", "Files", "ImageGeneration.data")
os.makedirs(os.path.join("Frontend", "Files"), exist_ok=True)
os.makedirs("Data", exist_ok=True)


def _clean_prompt(prompt: str) -> str:
    prompt = prompt.lower().strip()
    for prefix in ["generate image", "generate images", "generate"]:
        if prompt.startswith(prefix):
            prompt = prompt[len(prefix):].strip()
    return prompt


def open_images(prompt: str) -> None:
    safe_prompt = _clean_prompt(prompt).replace(" ", "_")
    for i in range(1, 5):
        image_path = os.path.join("Data", f"{safe_prompt}{i}.jpg")
        if os.path.exists(image_path):
            print(f"[ImageGen] Opening: {image_path}")
            try:
                os.startfile(os.path.abspath(image_path))
                sleep(0.5)
            except Exception:
                try:
                    img = Image.open(image_path)
                    img.show()
                    sleep(1)
                except Exception as e:
                    print(f"[ImageGen] Could not open {image_path}: {e}")
        else:
            print(f"[ImageGen] File not found: {image_path}")


def generate_single_image(prompt: str, index: int) -> None:
    try:
        clean = _clean_prompt(prompt)
        image = client.text_to_image(
            prompt=f"{clean}, quality-4K, ultra detailed, high resolution, photorealistic",
            model="black-forest-labs/FLUX.1-schnell"
        )
        safe  = clean.replace(" ", "_")
        path  = os.path.join("Data", f"{safe}{index}.jpg")
        image.save(path)
        print(f"[ImageGen] Saved: {path}")
    except Exception as e:
        print(f"[ImageGen] Error image {index}: {e}")


async def generate_images(prompt: str) -> None:
    tasks = [asyncio.to_thread(generate_single_image, prompt, i) for i in range(1, 5)]
    await asyncio.gather(*tasks)


def GenerateImages(prompt: str) -> None:
    asyncio.run(generate_images(prompt))
    open_images(prompt)


def _safe_read_data() -> tuple:
    try:
        with open(DATA_FILE, "r") as f:
            data = f.read().strip()
        if "," not in data:
            return None, None
        parts  = data.split(",", 1)
        prompt = parts[0].strip()
        status = parts[1].strip()
        return prompt, status
    except FileNotFoundError:
        with open(DATA_FILE, "w") as f:
            f.write("False,False")
        return None, None
    except Exception as e:
        print(f"[ImageGen] Read error: {e}")
        return None, None


def _reset_data() -> None:
    try:
        with open(DATA_FILE, "w") as f:
            f.write("False,False")
    except Exception:
        pass


# ── Main Loop ─────────────────────────────────────────────────
while True:
    try:
        prompt, status = _safe_read_data()

        if status == "True" and prompt and prompt != "False":
            print(f"[ImageGen] Generating: {prompt}")
            GenerateImages(prompt=prompt)
            _reset_data()
        else:
            sleep(1)

    except Exception as e:
        print(f"[ImageGen] Unexpected error: {e}")
        sleep(1)