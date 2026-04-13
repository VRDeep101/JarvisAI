import asyncio
from PIL import Image
from dotenv import get_key
import os
from time import sleep
from huggingface_hub import InferenceClient

def open_images(prompt):
    folder_path = r"Data"
    prompt = prompt.replace(" ", "_")
    Files = [f"{prompt}{i}.jpg" for i in range(1, 5)]
    for jpg_file in Files:
        image_path = os.path.join(folder_path, jpg_file)
        try:
            img = Image.open(image_path)
            print(f"Opening image: {image_path}")
            img.show()
            sleep(1)
        except IOError:
            print(f"Unable to open {image_path}")

client = InferenceClient(api_key=get_key(".env", "HuggingFaceAPIKey"))

def generate_single_image(prompt, index):
    try:
        image = client.text_to_image(
            prompt=f"{prompt}, quality-4K, ultra detailed, high resolution",
            model="black-forest-labs/FLUX.1-schnell"
        )
        os.makedirs("Data", exist_ok=True)
        file_path = f"Data/{prompt.replace(' ', '_')}{index}.jpg"
        image.save(file_path)
        print(f"Saved: {file_path}")
    except Exception as e:
        print(f"Image {index} error: {e}")

async def generate_images(prompt: str):
    tasks = []
    for i in range(1, 5):
        task = asyncio.to_thread(generate_single_image, prompt, i)
        tasks.append(task)
    await asyncio.gather(*tasks)

def GenerateImages(prompt: str):
    asyncio.run(generate_images(prompt))
    open_images(prompt)

while True:
    try:
        with open(r"Frontend\Files\ImageGeneration.data", "r") as f:
            Data: str = f.read()
        Prompt, Status = Data.split(",")
        Prompt = Prompt.strip()
        Status = Status.strip()
        if Status == "True":
            print(f"Generating Images for: {Prompt} ...")
            GenerateImages(prompt=Prompt)
            with open(r"Frontend\Files\ImageGeneration.data", "w") as f:
                f.write("False,False")
        else:
            sleep(1)
    except Exception as e:
        print(f"Error: {e}")
        sleep(1)