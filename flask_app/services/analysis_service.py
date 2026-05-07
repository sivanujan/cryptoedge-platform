import logging
import asyncio
import os
import requests
import google.generativeai as genai
from datetime import datetime, timedelta
from typing import Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Strategy, Coin
from services.binance_service import get_ohlcv
from services.indicator_service import (
    add_all_indicators, find_sr_levels, detect_patterns
)
from services.news_service import fetch_news_for_coin, calculate_sentiment
from strategies.golden_cross import STRATEGY_REGISTRY, get_strategy

logger = logging.getLogger(__name__)

# NVIDIA AI configuration
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

# Keep OpenRouter as fallback
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

# Gemini for Vision and Search
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)


async def get_ai_analysis(symbol: str, tf_analysis: dict, sentiment: dict, benchmarks: list, news: list) -> Dict[str, Any]:
    """
    Use NVIDIA AI (primary) or OpenRouter (fallback) to generate intelligent analysis.
    """
    if not NVIDIA_API_KEY and not OPENROUTER_API_KEY:
        return {"error": "AI API key not configured", "insight": "Configure NVIDIA_API_KEY in .env for AI insights"}

    # Prepare technical data summary
    tf_summary = "\n".join([
        f"- {tf}: RSI={data.get('rsi', 'N/A')}, Price=${data.get('price', 0):.4f}, Change={data.get('change_24h', 0):.2f}%, Verdict={data.get('verdict', 'N/A')}"
        for tf, data in tf_analysis.items()
    ])

    bench_summary = "\n".join([
        f"- {b['name']}: Win Rate={b['win_rate']:.1f}%, Return={b['return_pct']:.2f}%, Trades={b['total_trades']}"
        for b in benchmarks[:3]
    ]) if benchmarks else "No strategy benchmarks available"

    news_summary = "\n".join([f"- {n.get('title', 'No title')[:80]}" for n in news[:3]]) if news else "No recent news"

    prompt = f"""You are an expert crypto trading analyst. Analyze {symbol} and provide actionable insights.

CURRENT MARKET DATA:
{symbol} Technical Analysis (multiple timeframes):
{tf_summary}

Strategy Benchmarks (1h backtest):
{bench_summary}

Recent News:
{news_summary}

Market Sentiment: Score={sentiment.get('score', 0)} ({sentiment.get('label', 'Neutral')})

Provide a JSON response with these fields:
{{
  "summary": "2-3 sentence summary of the coin's current state",
  "trend": "BULLISH, BEARISH, or NEUTRAL",
  "key_levels": {{"support": ["price1", "price2"], "resistance": ["price1", "price2"]}},
  "signals": ["list of potential trade signals with reasoning"],
  "risk_assessment": "LOW, MEDIUM, or HIGH with explanation",
  "ai_confidence": 0-100,
  "recommendation": "STRONG BUY, BUY, HOLD, SELL, or STRONG SELL"
}}

Be concise and actionable. Focus on the most important technical levels and signals."""

    # Try NVIDIA first
    if NVIDIA_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Accept": "application/json",
            }
            payload = {
                "model": NVIDIA_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a professional crypto trading analyst with expertise in technical analysis, sentiment analysis, and risk management. Provide clear, actionable insights in JSON format."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.2,
                "max_tokens": 1024,
            }

            logger.info(f"Calling NVIDIA AI for {symbol} analysis...")
            response = requests.post(NVIDIA_URL, json=payload, headers=headers, timeout=45)

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_ai_content(content, symbol)
            else:
                logger.warning(f"NVIDIA API error: {response.status_code}. Falling back to OpenRouter...")
        except Exception as e:
            logger.error(f"NVIDIA analysis failed: {e}. Falling back...")

    # Fallback to OpenRouter
    if OPENROUTER_API_KEY:
        try:
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "http://localhost:5174",
                "X-Title": "CryptoEdge Deep Analysis",
            }
            payload = {
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": "You are a professional crypto trading analyst."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 800,
            }
            logger.info(f"Calling OpenRouter AI for {symbol} analysis...")
            response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=45)
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return _parse_ai_content(content, symbol)
        except Exception as e:
            logger.error(f"OpenRouter fallback failed: {e}")

    return {"error": "AI analysis unavailable", "insight": "All AI providers failed"}

def _parse_ai_content(content: str, symbol: str) -> dict:
    """Helper to parse JSON from AI response."""
    import json
    import re
    try:
        # Find JSON in response
        json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
        if json_match:
            ai_result = json.loads(json_match.group())
            return {
                "insight": ai_result.get("summary", "Analysis complete"),
                "trend": ai_result.get("trend", "NEUTRAL"),
                "key_levels": ai_result.get("key_levels", {"support": [], "resistance": []}),
                "signals": ai_result.get("signals", []),
                "risk_assessment": ai_result.get("risk_assessment", "MEDIUM"),
                "ai_confidence": ai_result.get("ai_confidence", 50),
                "recommendation": ai_result.get("recommendation", "HOLD"),
                "raw_analysis": content[:500]
            }
    except Exception:
        pass

    # Return as text if JSON parsing fails
    return {
        "insight": content[:300] + "..." if len(content) > 300 else content,
        "trend": "NEUTRAL",
        "risk_assessment": "MEDIUM",
        "ai_confidence": 50,
        "recommendation": "HOLD",
        "raw_analysis": content[:500]
    }


def analyze_technical_framework(df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    """
    Implements the 10 core prompts for deep technical analysis.
    """
    if df is None or len(df) < 50:
        return {"error": "Insufficient data"}

    last = df.iloc[-1]
    prev = df.iloc[-2]
    price = last["close"]
    
    # 1. RSI Analysis
    rsi = last["rsi_14"]
    rsi_prev = prev["rsi_14"]
    rsi_status = "WAIT"
    rsi_dir = "UP" if rsi > rsi_prev else "DOWN"
    if rsi_prev < 50 and rsi >= 50 and 50 <= rsi <= 65:
        rsi_status = "ENTRY ZONE (LONG)"
    elif rsi_prev > 50 and rsi <= 50 and 35 <= rsi <= 50:
        rsi_status = "ENTRY ZONE (SHORT)"
    elif rsi > 75: rsi_status = "REJECT (OVERBOUGHT)"
    elif rsi < 25: rsi_status = "REJECT (OVERSOLD)"
    
    # 2. EMA Trend Filter
    ema21 = last["ema_21"]
    ema50 = last["ema_50"]
    stack = "MIXED"
    if price > ema21 and ema21 > ema50: stack = "BULLISH"
    elif price < ema21 and ema21 < ema50: stack = "BEARISH"
    ema_dist = ((price - ema21) / ema21) * 100
    
    # 3. BB Breakout
    upper = last["bb_upper"]
    lower = last["bb_lower"]
    mid = last["bb_mid"]
    width = last["bb_width"]
    bb_signal = "RANGING"
    if last["close"] > upper and last["open"] > upper: bb_signal = "BREAKOUT"
    elif last["close"] < lower and last["open"] < lower: bb_signal = "BREAKDOWN"
    elif width < 4.0: bb_signal = "SQUEEZE"
    
    # 4. Volume Confirmation
    vol = last["volume"]
    vol_sma = last["volume_sma"]
    vol_ratio = vol / vol_sma if vol_sma > 0 else 0
    vol_status = "NO SIGNAL"
    if vol_ratio > 1.5: vol_status = "CONFIRMED"
    elif vol_ratio >= 1.0: vol_status = "WEAK"
    
    # 5. ATR Stop/TP
    atr = last["atr_14"]
    direction = "LONG" if bullish_momentum_check(last) else "SHORT" # simple internal biased
    if direction == "LONG":
        sl = price - (atr * 1.5)
        tp1, tp2, tp3 = price + (atr * 2), price + (atr * 3.5), price + (atr * 5)
    else:
        sl = price + (atr * 1.5)
        tp1, tp2, tp3 = price - (atr * 2), price - (atr * 3.5), price - (atr * 5)
    
    # 6. Support & Resistance
    sr = find_sr_levels(df)
    
    # 7. VWAP Position
    vwap = last["vwap"]
    vwap_dist = ((price - vwap) / vwap) * 100
    vwap_signal = "NEUTRAL"
    if abs(vwap_dist) < 0.3: vwap_signal = "AT VWAP RETEST"
    elif price > vwap: vwap_signal = "LONG BIAS"
    else: vwap_signal = "SHORT BIAS"
    
    # 8. Candle Patterns
    pattern = detect_patterns(df)
    
    # 9. Confluence Score
    score = 0
    reasons = []
    if "ENTRY ZONE" in rsi_status: 
        score += 20
        reasons.append(f"RSI in {rsi_status}")
    if stack in ["BULLISH", "BEARISH"]: 
        score += 20
        reasons.append(f"EMA stack {stack}")
    if bb_signal in ["BREAKOUT", "BREAKDOWN"]: 
        score += 20
        reasons.append(f"BB {bb_signal}")
    if vol_status == "CONFIRMED": 
        score += 20
        reasons.append("Volume confirmed (>1.5x)")
    if pattern: 
        score += 10
        reasons.append(f"Pattern: {pattern['name']}")
    if sr['support'] and (price - sr['support'][0])/price < 0.01:
        score += 10
        reasons.append("Near support")
    elif sr['resistance'] and (sr['resistance'][0] - price)/price < 0.01:
        score += 10
        reasons.append("Near resistance")
        
    verdict = "WAIT"
    if score >= 80: verdict = "STRONG ENTRY"
    elif score >= 60: verdict = "MODERATE ENTRY"
    
    # Determine final direction based on score components
    final_dir = "WAIT"
    if score >= 40:
        long_count = sum(1 for r in reasons if "BULLISH" in r or "LONG" in r or "BREAKOUT" in r or "support" in r)
        short_count = sum(1 for r in reasons if "BEARISH" in r or "SHORT" in r or "BREAKDOWN" in r or "resistance" in r)
        final_dir = "LONG" if long_count >= short_count else "SHORT"

    return {
        "direction": final_dir,
        "score": score,
        "verdict": verdict,
        "reasons": reasons,
        "summary": " + ".join(reasons) if reasons else "No significant technical confluence found.",
        "metrics": {
            "rsi": {"value": round(rsi, 2), "dir": rsi_dir, "status": rsi_status},
            "ema": {"ema21": round(ema21, 6), "ema50": round(ema50, 6), "stack": stack, "dist": round(ema_dist, 2)},
            "bb": {"upper": round(upper, 6), "lower": round(lower, 6), "width": round(width, 2), "signal": bb_signal},
            "volume": {"current": round(vol, 2), "avg": round(vol_sma, 2), "ratio": round(vol_ratio, 2), "status": vol_status},
            "targets": {"sl": round(sl, 6), "tp1": round(tp1, 6), "tp2": round(tp2, 6), "tp3": round(tp3, 6)},
            "sr": sr,
            "vwap": {"value": round(vwap, 6), "signal": vwap_signal, "dist": round(vwap_dist, 2)},
            "pattern": pattern
        }
    }


def bullish_momentum_check(last: pd.Series) -> bool:
    """Internal helper to guess bias for ATR targets."""
    return last["close"] > last["ema_21"]


async def chat_with_ai(query: str, history: List[Dict] = None, image_data: bytes = None) -> Dict[str, Any]:
    """
    General AI chat that can handle text queries and/or images.
    If image is provided, it analyzes the chart.
    """
    if not GOOGLE_API_KEY:
        return {"error": "Google API Key not configured for chat/vision."}

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        content = []
        if image_data:
            content.append({
                "mime_type": "image/jpeg",
                "data": image_data
            })
            
        system_instruction = """You are CryptoEdge AI, a professional trading analyst. 
        If an image is provided, it is a trading chart. Analyze it for:
        1. Trend (Bullish/Bearish)
        2. Key Support and Resistance levels
        3. Potential Entry and Exit points
        4. Technical patterns (Head & Shoulders, Wedges, etc.)
        
        Provide clear, actionable advice. If no image is provided, answer the user's query about crypto markets or specific coins using your knowledge."""
        
        full_query = f"{system_instruction}\n\nUser Question: {query}" if query else f"{system_instruction}\n\nPlease analyze this chart image."
        
        content.append(full_query)
        
        # Simple history handling (just last few messages for now)
        # Note: Gemini 1.5 Flash handles multi-modal well
        response = await asyncio.to_thread(model.generate_content, content)
        
        return {
            "response": response.text,
            "type": "image_analysis" if image_data else "chat"
        }
    except Exception as e:
        logger.error(f"Gemini Chat error: {e}")
        return {"error": str(e)}

async def analyze_coin_deep(symbol: str, db: Session) -> Dict[str, Any]:
    """
    Perform a deep analysis of a single coin:
    1. Fetch recent news and sentiment.
    2. Analyze technical patterns across multiple TFs.
    3. Benchmark all available strategies.
    4. Provide final recommendation.
    """
    try:
        # 1. News Analysis (Fault Tolerant)
        news_posts = []
        sentiment = {"score": 0, "label": "Neutral", "total_mentions": 0}
        try:
            news_posts = await fetch_news_for_coin(symbol)
            if news_posts:
                sentiment = calculate_sentiment(news_posts)
        except Exception as news_err:
            logger.warning(f"News fetching failed for {symbol}: {news_err}")

        # 2. Multi-TF Technical Analysis
        timeframes = ["15m", "1h", "4h"]
        tf_analysis = {}
        
        for tf in timeframes:
            try:
                df = get_ohlcv(symbol, tf, limit=500)
                if df is not None and len(df) >= 100:
                    df = add_all_indicators(df)
                    df = df.dropna()
                    if df.empty: continue
                    
                    last = df.iloc[-1]
                    # Simple logic for TF verdict
                    rsi = last.get("rsi_14", 50)
                    ema_fast = last.get("ema_21", 0)
                    ema_slow = last.get("ema_50", 0)
                    trend = "BULLISH" if ema_fast > ema_slow else "BEARISH"
                    if rsi > 70: trend = "OVERBOUGHT"
                    if rsi < 30: trend = "OVERSOLD"
                    
                    tf_analysis[tf] = {
                        "verdict": trend,
                        "rsi": round(rsi, 2),
                        "price": round(last["close"], 6),
                        "change_24h": round(((last["close"] - df.iloc[0]["close"]) / df.iloc[0]["close"]) * 100, 2)
                    }
            except Exception as tf_err:
                logger.warning(f"TF analysis failed for {symbol} {tf}: {tf_err}")

        # 3. Strategy Benchmarking
        strategies = db.query(Strategy).filter_by(is_active=True).all()
        benchmarks = []
        
        # We'll use a 1h timeframe for benchmarking by default
        df_bench = get_ohlcv(symbol, "1h", limit=1000)
        if df_bench is not None and len(df_bench) > 200:
            df_bench = add_all_indicators(df_bench)
            df_bench = df_bench.reset_index(drop=True)
            for strat_db in strategies:
                try:
                    logger.info(f"Checking strategy {strat_db.name} for benchmark...")
                    strat_inst = get_strategy(strat_db.name, strat_db.parameters)
                    # Vectorized backtest simulation (simplified)
                    df_sig = strat_inst.generate_signals(df_bench.copy())
                    
                    # Log if any signals found
                    sig_counts = df_sig["signal"].value_counts().to_dict()
                    logger.info(f"Signal counts for {strat_db.name}: {sig_counts}")

                    # Ensure we have signals
                    if "signal" in df_sig.columns and (df_sig["signal"] != 0).any():
                        from services.backtest_service import _simulate_trades
                        metrics = _simulate_trades(df_sig, strat_inst)
                        
                        benchmarks.append({
                            "name": strat_db.name,
                            "win_rate": metrics.get("win_rate", 0),
                            "total_trades": metrics.get("total_trades", 0),
                            "return_pct": metrics.get("total_return", 0),
                        })
                    else:
                        logger.info(f"No signals generated for {strat_db.name} on {symbol}")
                except Exception as e:
                    logger.warning(f"Strategy {strat_db.name} failed during benchmarking: {e}")

        benchmarks.sort(key=lambda x: x["return_pct"], reverse=True)

        # 4. Final Verdict Logic
        bullish_score = 0
        weight_sentiment = 0.2
        weight_technical = 0.5
        weight_strategy = 0.3

        # Sentiment contribution
        bullish_score += (sentiment["score"] / 100) * weight_sentiment
        
        # Technical contribution (average of TFs)
        if tf_analysis:
            tf_contrib = 0
            for tf, data in tf_analysis.items():
                if data["verdict"] == "BULLISH": tf_contrib += 1
                if data["verdict"] == "OVERSOLD": tf_contrib += 0.8
                if data["verdict"] == "BEARISH": tf_contrib -= 1
                if data["verdict"] == "OVERBOUGHT": tf_contrib -= 0.8
            bullish_score += (tf_contrib / len(tf_analysis)) * weight_technical
        
        # Strategy contribution
        if benchmarks:
            best_strat = benchmarks[0]
            if best_strat["return_pct"] > 0:
                bullish_score += 0.2 * weight_strategy
            elif best_strat["return_pct"] < 0:
                bullish_score -= 0.1 * weight_strategy

        recommendation = "NEUTRAL"
        confidence = abs(bullish_score) * 100
        if bullish_score > 0.05: recommendation = "LONG"
        if bullish_score > 0.25: recommendation = "STRONG LONG"
        if bullish_score < -0.05: recommendation = "SHORT"
        if bullish_score < -0.25: recommendation = "STRONG SHORT"

        # 5. AI-Powered Analysis using OpenRouter
        ai_analysis = await get_ai_analysis(symbol, tf_analysis, sentiment, benchmarks, news_posts)

        # 6. Comprehensive Technical Framework (New)
        df_1h = get_ohlcv(symbol, "1h", limit=500)
        tech_framework = {}
        if df_1h is not None:
            df_1h = add_all_indicators(df_1h)
            tech_framework = analyze_technical_framework(df_1h, symbol)

        return {
            "symbol": symbol,
            "sentiment": sentiment,
            "news": news_posts,
            "timeframe_analysis": tf_analysis,
            "benchmarks": benchmarks[:5],
            "recommendation": tech_framework.get("verdict", recommendation),
            "confidence": tech_framework.get("score", round(min(confidence + 50, 95), 1)),
            "ai_analysis": ai_analysis,
            "technical_framework": tech_framework,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(f"Deep analysis failed for {symbol}: {e}", exc_info=True)
        return {"error": str(e)}
