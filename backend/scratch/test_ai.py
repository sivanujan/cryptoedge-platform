import os
import requests
from dotenv import load_dotenv

load_dotenv()

def test_openrouter():
    url = "https://openrouter.ai/api/v1/chat/completions"
    key = os.getenv("OPENROUTER_API_KEY")
    models = [
        os.getenv("OPENROUTER_MODEL"),
        "google/gemma-4-31b-it:free",
        "meta-llama/llama-3.3-70b-instruct:free",
        "qwen/qwen3-coder:free"
    ]

    
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:5174",
        "X-Title": "Test",
    }
    
    for model in models:
        print(f"Testing OR model: {model}")
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10
        }
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            print(f"  Status: {resp.status_code}")
            if resp.status_code != 200:
                print(f"  Error: {resp.text}")
        except Exception as e:
            print(f"  Exception: {e}")

def test_nvidia():
    url = "https://integrate.api.nvidia.com/v1/chat/completions"
    key = os.getenv("NVIDIA_API_KEY")
    model = os.getenv("NVIDIA_MODEL")
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    
    print(f"Testing NVIDIA model: {model}")
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 10
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"  Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"  Error: {resp.text}")
    except Exception as e:
        print(f"  Exception: {e}")

if __name__ == "__main__":
    test_nvidia()
    test_openrouter()
