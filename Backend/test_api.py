import requests
from dotenv import get_key

headers = {"Authorization": f"Bearer {get_key('.env', 'HuggingFaceAPIKey')}"}
payload = {"inputs": "a cat"}
r = requests.post(
    "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0",
    headers=headers,
    json=payload
)
print("Status:", r.status_code)
print("Response:", r.text[:300])