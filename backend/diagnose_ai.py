import os
import sys
import requests
from dotenv import load_dotenv

def diagnose():
    load_dotenv()
    print("--- OpenRouter Diagnostic Tool ---")
    
    key = os.getenv("OPENROUTER_API_KEY")
    model = os.getenv("OPENROUTER_MODEL", "google/gemma-3-27b-it:free")
    
    if not key:
        print("ERROR: OPENROUTER_API_KEY not found in .env")
        return
    
    print(f"API Key found: {key[:10]}...{key[-5:]}")
    print(f"Testing with model: {model}")
    print("-" * 30)

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "HTTP-Referer": "http://localhost:5174",
        "X-Title": "CryptoEdge Diagnostics",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Hello, respond with only the word 'OK'."}],
        "temperature": 0.1,
    }

    try:
        print("Sending request to OpenRouter...")
        resp = requests.post(url, json=payload, headers=headers, timeout=15)
        
        if resp.status_code == 200:
            print("SUCCESS: Connection established!")
            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            print(f"Response: {content}")
        elif resp.status_code == 401:
            print("FAILURE: 401 Unauthorized.")
            print("Reason: Your API key is invalid or rejected by OpenRouter.")
            print("Action: Please check your key at https://openrouter.ai/keys")
        elif resp.status_code == 402:
            print("FAILURE: 402 Payment Required.")
            print("Reason: You likely have 0 credits on your OpenRouter account.")
            print("Action: Add credits or use a free model like 'google/gemini-2.0-flash-exp:free'.")
        else:
            print(f"FAILURE: Status Code {resp.status_code}")
            print(f"Response: {resp.text[:500]}")
            
    except Exception as e:
        print(f"ERROR: Could not connect to OpenRouter: {e}")

if __name__ == "__main__":
    diagnose()
