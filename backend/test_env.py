import os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv("OPENROUTER_API_KEY")
if key:
    print(f"Key found: {key[:10]}...")
else:
    print("Key not found!")
