import requests

def get_free_models():
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models")
        if resp.status_code == 200:
            data = resp.json()
            free_models = [m['id'] for m in data['data'] if m.get('pricing', {}).get('prompt') == '0']
            for m in free_models:
                print(m)
        else:
            print(f"Error: {resp.status_code}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    get_free_models()
