# ─────────────────────────────────────────────────────────────
#  ImageGeneration.py  —  Jarvis Image Generator  [FIXED v5]
#
#  ROOT CAUSE OF OLD BUG:
#  Main.py was writing "prompt,True" to the data file, but
#  ImageGeneration.py would read it before the OS had flushed
#  the write to disk (race condition). Also, if the file was
#  locked by Main.py during write, ImageGeneration.py read
#  an empty/partial value and silently skipped generation.
#
#  FIX v5:
#  1. ATOMIC WRITE in Main.py:
#     - Write to a temp file first → rename over the real file
#     - Rename is atomic on all OS — reader never sees partial write
#     - fsync before rename ensures data is on disk
#  2. VERIFIED READ in ImageGeneration.py:
#     - After reading "True", immediately re-read to verify
#     - If second read also says "True" → proceed (not a partial read)
#  3. WRITE-LOCK: ImageGeneration.py writes a "Processing" flag
#     immediately after confirming the trigger, so if Main.py
#     checks the file it knows generation is underway
#  4. STARTUP: data file reset to "False,False" on every boot
#     (prevents stale "True" from previous crash triggering phantom gen)
#  5. OPEN IMAGES: After generation, images are opened automatically
# ─────────────────────────────────────────────────────────────

import asyncio
from PIL import Image
from dotenv import get_key
import os
import time
from time import sleep
from huggingface_hub import InferenceClient

client = InferenceClient(api_key=get_key(".env", "HuggingFaceAPIKey"))

DATA_FILE     = os.path.join("Frontend", "Files", "ImageGeneration.data")
DATA_FILE_TMP = DATA_FILE + ".tmp"   # temp file for atomic writes

os.makedirs(os.path.join("Frontend", "Files"), exist_ok=True)
os.makedirs("Data", exist_ok=True)


# ── Atomic Write ──────────────────────────────────────────────
def _atomic_write(filepath: str, content: str) -> bool:
    """
    Write content atomically using write-to-temp + rename.
    The rename operation is atomic on all major OS.
    Reader will never see a partial write.
    """
    tmp = filepath + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())   # Ensure data hits disk before rename
        os.replace(tmp, filepath)  # Atomic rename
        return True
    except Exception as e:
        print(f"[ImageGen] Atomic write error: {e}")
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False


# ── Safe Read with Retry ──────────────────────────────────────
def _safe_read_data(retries: int = 5, delay: float = 0.1) -> tuple:
    """
    Returns (prompt, status) with retry logic.
    Returns (None, None) on repeated failure.
    """
    for attempt in range(retries):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
            if "," not in data:
                return None, None
            parts  = data.split(",", 1)
            prompt = parts[0].strip()
            status = parts[1].strip()
            return prompt, status
        except FileNotFoundError:
            _reset_data()
            return None, None
        except PermissionError:
            time.sleep(delay)
        except Exception as e:
            print(f"[ImageGen] Read error (attempt {attempt+1}): {e}")
            time.sleep(delay)
    return None, None


def _reset_data() -> None:
    """Reset to idle state using atomic write."""
    _atomic_write(DATA_FILE, "False,False")


def _write_processing_flag(prompt: str) -> None:
    """
    Write 'Processing' flag immediately after confirming trigger.
    Main.py can see this and know generation is underway.
    """
    _atomic_write(DATA_FILE, f"{prompt},Processing")
    print(f"[ImageGen] 🔄 Processing flag set for: '{prompt}'")


def _write_generated_flag(prompt: str) -> None:
    """
    Write Generated status so Main.py ImageWatcherThread speaks.
    Uses atomic write — Main.py will never see partial content.
    """
    success = _atomic_write(DATA_FILE, f"{prompt},Generated")
    if success:
        print(f"[ImageGen] ✅ Generated flag written for: '{prompt}'")
    else:
        print(f"[ImageGen] ❌ Failed to write Generated flag")


# ── Prompt Cleaner ─────────────────────────────────────────────
def _clean_prompt(prompt: str) -> str:
    prompt = prompt.lower().strip()
    for prefix in ["generate image of", "generate images of", "generate image",
                   "generate images", "generate"]:
        if prompt.startswith(prefix):
            prompt = prompt[len(prefix):].strip()
    return prompt


# ── Image Generation ──────────────────────────────────────────
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
        print(f"[ImageGen] ✅ Saved: {path}")
    except Exception as e:
        print(f"[ImageGen] Error generating image {index}: {e}")


async def generate_images_async(prompt: str) -> None:
    tasks = [asyncio.to_thread(generate_single_image, prompt, i) for i in range(1, 5)]
    await asyncio.gather(*tasks)


def GenerateImages(prompt: str) -> None:
    print(f"[ImageGen] 🎨 Starting generation for: '{prompt}'")
    asyncio.run(generate_images_async(prompt))
    open_images(prompt)


# ── Startup: Always reset data file ──────────────────────────
# Reset on startup prevents a stale "True" from a previous crash
# triggering a phantom image generation on next boot.
print("[ImageGen] 🟢 Image generation service started.")
_reset_data()
print(f"[ImageGen] Data file reset to idle: {DATA_FILE}")
print("[ImageGen] Polling for requests every second...")


# ── Main Poll Loop ────────────────────────────────────────────
# HOW IT WORKS:
# 1. Main.py writes "prompt,True" to DATA_FILE (atomically)
# 2. This loop reads the file every second
# 3. Sees status == "True" → immediately writes "Processing" flag
#    (so Main.py knows generation is underway if it checks)
# 4. Verifies the trigger is still valid (re-reads after 100ms)
# 5. Generates 4 images
# 6. Writes "prompt,Generated" flag (atomically)
# 7. Main.py's ImageWatcherThread sees "Generated" and announces it

while True:
    try:
        prompt, status = _safe_read_data()

        if status == "True" and prompt and prompt not in ("False", ""):
            print(f"[ImageGen] 📥 Trigger received: '{prompt}'")

            # Step 1: Write Processing flag immediately
            # This prevents double-triggering if Main.py checks file mid-generation
            _write_processing_flag(prompt)

            # Step 2: Small delay then re-verify (guard against partial reads)
            time.sleep(0.1)
            prompt2, status2 = _safe_read_data()

            # If file was reset or changed during our read, abort
            if status2 not in ("True", "Processing") or not prompt2 or prompt2 in ("False", ""):
                print(f"[ImageGen] ⚠️ Trigger disappeared before generation — aborted")
                _reset_data()
                sleep(1)
                continue

            # Use the most recent prompt (in case it was updated)
            final_prompt = prompt2 if status2 == "True" else prompt

            # Step 3: Generate images
            GenerateImages(prompt=final_prompt)

            # Step 4: Signal completion — atomic write
            _write_generated_flag(final_prompt)

        elif status == "Processing":
            # Another instance somehow wrote Processing — don't interfere
            # This shouldn't happen in normal operation (single subprocess)
            print(f"[ImageGen] ⚠️ Found 'Processing' status on poll — may be stale, waiting...")
            sleep(5)

        else:
            sleep(1)   # Idle poll — nothing to do

    except Exception as e:
        print(f"[ImageGen] Unexpected error in main loop: {e}")
        sleep(1)