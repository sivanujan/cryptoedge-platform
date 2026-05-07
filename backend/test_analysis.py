import asyncio
import os
from database.connection import SessionLocal
from services.analysis_service import analyze_coin_deep
from dotenv import load_dotenv

load_dotenv()

async def test():
    db = SessionLocal()
    try:
        print("Testing Deep Analysis for BTC/USDT...")
        result = await analyze_coin_deep("BTC/USDT", db)
        if "error" in result:
            print(f"Error: {result['error']}")
        else:
            print(f"Recommendation: {result['recommendation']}")
            print(f"Confidence: {result['confidence']}%")
            print(f"Sentiment: {result['sentiment']['label']} ({result['sentiment']['score']})")
            print(f"Benchmarks found: {len(result['benchmarks'])}")
            if result['benchmarks']:
                print(f"Top Strategy: {result['benchmarks'][0]['name']} ({result['benchmarks'][0]['return_pct']}%)")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test())
