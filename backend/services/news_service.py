import os
import httpx
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
BASE_URL = "https://newsdata.io/api/1/latest"

async def fetch_news_for_coin(symbol: str) -> List[Dict[str, Any]]:
    """Fetch recent news for a specific coin from NewsData.io."""
    if not NEWSDATA_API_KEY:
        logger.warning("NEWSDATA_API_KEY not found in environment.")
        return []

    # Clean symbol (e.g., BTC/USDT -> BTC)
    clean_symbol = symbol.split("/")[0].split(":")[0].lower()
    
    # We'll search for the coin name/symbol in the "q" parameter
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": f"{clean_symbol} crypto",
        "language": "en",
        "category": "technology,business"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("results", [])
            
            # Reformat to match what we expect in analysis_service (or update analysis_service)
            formatted_news = []
            for item in results[:10]:
                formatted_news.append({
                    "title": item.get("title", ""),
                    "url": item.get("link", ""),
                    "domain": item.get("source_id", "news"),
                    "created_at": item.get("pubDate", ""),
                    "description": item.get("description", ""),
                    "sentiment": item.get("sentiment", "neutral") # NewsData.io sometimes provides sentiment
                })
            
            return formatted_news
    except Exception as e:
        logger.error(f"Error fetching news from NewsData.io for {clean_symbol}: {e}")
        return []

def calculate_sentiment(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate sentiment score based on headlines and NewsData sentiment fields."""
    score = 0
    total = len(posts)
    
    if total == 0:
        return {"score": 0, "label": "Neutral", "total_mentions": 0}

    # Bullish/Bearish keywords if API sentiment is missing
    bull_keys = ["bullish", "surge", "gain", "breakout", "rally", "growth", "high", "success", "buy"]
    bear_keys = ["bearish", "crash", "drop", "plunge", "down", "dip", "fall", "sell", "risk", "loss"]

    for post in posts:
        # 1. Use API sentiment if available
        api_sentiment = post.get("sentiment", "neutral")
        if api_sentiment == "positive":
            score += 40
        elif api_sentiment == "negative":
            score -= 40
        else:
            # 2. Text-based fallback
            text = (post.get("title", "") + " " + post.get("description", "")).lower()
            post_score = 0
            for k in bull_keys:
                if k in text: post_score += 15
            for k in bear_keys:
                if k in text: post_score -= 15
            
            score += min(max(post_score, -30), 30) # Capped at 30 per article

    # Normalize roughly
    norm_score = min(max(score / (total * 0.4), -100), 100)

    label = "Neutral"
    if norm_score > 15: label = "Bullish"
    if norm_score > 40: label = "Very Bullish"
    if norm_score < -15: label = "Bearish"
    if norm_score < -40: label = "Very Bearish"

    return {
        "score": round(norm_score, 1),
        "label": label,
        "total_mentions": total
    }
