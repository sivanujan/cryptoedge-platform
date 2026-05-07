import httpx
import asyncio

async def test_url():
    token = "591dc4f71c956374797e5a621b90bb2513c09d4b"
    # Try multiple variants
    urls = [
        "https://cryptopanic.com/api/v1/posts/",
        "https://cryptopanic.com/api/v1/posts",
    ]
    
    for url in urls:
        print(f"Testing {url}...")
        params = {"auth_token": token, "currencies": "BTC"}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                print(f"Status: {resp.status_code}")
                if resp.status_code == 200:
                    print("Success!")
                    break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_url())
