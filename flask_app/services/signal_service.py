import os
import json
import logging
import requests
from database.connection import SessionLocal
from database.models import Strategy, CoinResult, SignalHistory
from services.confidence_service import calculate_confidence_score

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Use a capable model for complex JSON generation
SIGNAL_MODEL = "meta-llama/llama-3.3-70b-instruct:free" 

PROMPT_TEMPLATE = """
You are a professional crypto futures trade planner. Analyze this setup and 
return a structured JSON trade signal.

STRATEGY: {strategy_name}
COIN: {coin}
TIMEFRAME: {timeframe}
WIN RATE AT TF: {win_rate}% ({trades} backtested trades)
RETURN% HISTORICAL: {return_pct}%
DRAWDOWN: {drawdown}%
CONFIDENCE SCORE: {score}/100 (Grade: {grade})
COINS TESTED: {coins_tested} | COINS ABOVE 65%: {coins_above_65}
DIRECTION: {direction}
RISK:REWARD: 1:{rr_ratio}
SL METHOD: {sl_method}
ACCOUNT SIZE: ${account_size} | RISK PER TRADE: {risk_pct}%
EXTRA CONTEXT: {extra_context}

Return ONLY valid JSON with this exact structure:
{{
  "validity_score": 0-10,
  "validity_reason": "string",
  "entry": {{
    "zone_low": float,
    "zone_high": float,
    "trigger": "string - exact entry condition",
    "best_session": "Asian|London|NY",
    "invalidation": "string - when to not enter"
  }},
  "stop_loss": {{
    "price": float,
    "pct_from_entry": float,
    "logic": "string"
  }},
  "take_profit": {{
    "tp1_price": float,
    "tp1_pct": float,
    "tp1_exit_size_pct": 50,
    "tp2_price": float,
    "tp2_pct": float,
    "trailing_stop": "string"
  }},
  "position_size": {{
    "risk_amount_usd": float,
    "position_size_usd": float,
    "recommended_leverage": int,
    "contracts": float
  }},
  "confluence": {{
    "btc_strength": true|false|null,
    "volume_above_avg": true|false|null,
    "htf_aligned": true|false|null,
    "near_key_level": true|false|null,
    "session_quality": "high|medium|low"
  }},
  "trade_management": {{
    "move_sl_to_be_at": "string",
    "add_condition": "string or null",
    "early_exit": "string",
    "max_hold_candles": int
  }},
  "risk_flags": ["string array of warnings"],
  "low_sample_warning": true|false,
  "verdict": "TAKE|SKIP|WAIT",
  "verdict_reason": "string - 2-3 sentences"
}}

Rules:
- If trades < 5, set low_sample_warning: true and reduce validity_score by 2
- If win_rate < 60, verdict must be SKIP unless strong confluence
- Be precise with numbers, no vague ranges
- All price fields: use realistic current market prices for the coin
"""

def generate_signal_stream(db, strategy_id, coin, timeframe, direction, rr_ratio, sl_method, account_size, risk_pct, extra_context, entry_price, sl_price, tp_price):
    """
    Generate a signal using AI and stream the response.
    """
    # 1. Fetch data
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    coin_result = db.query(CoinResult).filter_by(strategy_id=strategy_id, coin=coin).first()
    
    if not strategy:
        yield "Error: Strategy not found"
        return
        
    # Get results for specific timeframe
    tf_data = {}
    if coin_result and coin_result.tf_results:
        tf_data = coin_result.tf_results.get(timeframe, {})
        
    win_rate = tf_data.get("win_rate", 0.0)
    trades = tf_data.get("trades", 0)
    
    # 2. Calculate confidence score
    score_data = calculate_confidence_score(
        win_rate=win_rate,
        trades=trades,
        coins_tested=strategy.coins_tested or 0,
        coins_above_65=strategy.coins_above_65 or 0,
        return_pct=coin_result.return_pct if coin_result else 0.0,
        drawdown=coin_result.drawdown if coin_result else 0.0
    )
    
    # 3. Build prompt
    prompt = PROMPT_TEMPLATE.format(
        strategy_name=strategy.name,
        coin=coin,
        timeframe=timeframe,
        win_rate=win_rate,
        trades=trades,
        return_pct=coin_result.return_pct if coin_result else 0.0,
        drawdown=coin_result.drawdown if coin_result else 0.0,
        score=score_data["score"],
        grade=score_data["grade"],
        coins_tested=strategy.coins_tested or 0,
        coins_above_65=strategy.coins_above_65 or 0,
        direction=direction,
        rr_ratio=rr_ratio,
        sl_method=sl_method,
        account_size=account_size,
        risk_pct=risk_pct,
        extra_context=extra_context
    )
    
    # 4. Call OpenRouter with streaming
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5174",
        "X-Title": "CryptoEdge Signal Generator",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": SIGNAL_MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise JSON generator. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "stream": True
    }
    
    try:
        resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, stream=True, timeout=180)
        
        full_content = ""
        for line in resp.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data["choices"][0]["delta"].get("content", "")
                        full_content += content
                        yield content
                    except:
                        pass
                        
        # 5. Save to history after stream completes
        try:
            if not full_content:
                logger.error(f"OpenRouter returned empty content. Response status: {resp.status_code}")
                try:
                    logger.error(f"Raw response text: {resp.text}")
                except:
                    pass
            
            # Try to parse the full content to extract verdict and score
            try:
                signal_json = json.loads(full_content)
                verdict = signal_json.get("verdict", "WAIT")
                validity_score = signal_json.get("validity_score")
            except Exception as json_err:
                logger.warning(f"Failed to parse AI JSON: {json_err}. Using rule-based fallback for execution.")
                
                # Calculate quantity based on risk
                risk_amount = account_size * risk_pct / 100.0
                risk_per_unit = abs(entry_price - sl_price)
                qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
                
                signal_json = {
                    "verdict": "TAKE",
                    "entry": {"zone_low": entry_price, "zone_high": entry_price},
                    "stop_loss": {"price": sl_price},
                    "take_profit": {"tp1_price": tp_price},
                    "position_size": {"contracts": qty, "position_size_usd": risk_amount}
                }
                verdict = "TAKE"
                validity_score = 5
            
            history = SignalHistory(
                strategy_id=strategy_id,
                coin=coin,
                timeframe=timeframe,
                verdict=verdict,
                validity_score=validity_score,
                full_signal=signal_json,
                outcome="Pending"
            )
            db.add(history)
            db.commit()
            logger.info(f"Saved signal history for {coin}")
            
            # 6. Execute AI signal if AutoTrader is enabled and verdict is TAKE
            if verdict == "TAKE":
                execute_ai_signal(db, signal_json, coin)
            
        except Exception as e:
            logger.error(f"Failed to save signal history or execute trade: {e}")
            logger.error(f"Full content was: {full_content}")
            
    except Exception as e:
        logger.exception(f"Error in generate_signal_stream: {e}")
        yield f"Error: {e}"


def execute_ai_signal(db, signal_json, coin):
    """
    Execute the AI signal if AutoTrader is enabled.
    """
    from autotrader.engine import get_settings
    from autotrader import binance_executor
    from database.models import AutoTrade
    
    settings = get_settings(db)
    if not settings.is_enabled:
        logger.info("AutoTrader is disabled. Skipping execution.")
        return
        
    try:
        verdict = signal_json.get("verdict")
        if verdict != "TAKE":
            logger.info(f"Verdict is {verdict}. Skipping execution.")
            return
            
        # Extract data from signal
        entry = signal_json.get("entry", {})
        stop_loss = signal_json.get("stop_loss", {})
        take_profit = signal_json.get("take_profit", {})
        position_size = signal_json.get("position_size", {})
        
        # Infer direction
        zone_low = entry.get("zone_low")
        zone_high = entry.get("zone_high")
        tp1_price = take_profit.get("tp1_price")
        
        if not zone_low or not zone_high or not tp1_price:
            logger.warning("Missing price levels in signal. Cannot execute.")
            return
            
        entry_price = (zone_low + zone_high) / 2
        is_long = tp1_price > entry_price
        
        side = "LONG" if is_long else "SHORT"
        binance_side = "BUY" if is_long else "SELL"
        stop_side = "SELL" if is_long else "BUY"
        
        qty = position_size.get("contracts")
        leverage = position_size.get("recommended_leverage", settings.leverage)
        
        if not qty:
            logger.warning("No contracts quantity in signal. Cannot execute.")
            return
            
        symbol_base = coin.replace('/', '').replace(':USDT', '')
        
        # Set leverage
        binance_executor.set_leverage(symbol_base, leverage)
        
        # Place Market Order
        logger.info(f"Placing AI signal order: {binance_side} {qty} {symbol_base} at {entry_price}")
        order_result = binance_executor.place_market_order(symbol_base, binance_side, qty)
        
        if order_result:
            logger.info(f"Order placed successfully: {order_result.get('orderId')}")
            
            sl_price = stop_loss.get("price")
            # Place SL and TP
            if sl_price:
                binance_executor.place_stop_market_order(symbol_base, stop_side, qty, sl_price)
            if tp1_price:
                binance_executor.place_take_profit_market_order(symbol_base, stop_side, qty, tp1_price)
                
            # Save to AutoTrade table to track it
            new_trade = AutoTrade(
                symbol=coin, side=side, entry_price=entry_price, quantity=qty,
                leverage=leverage, margin_used=position_size.get("position_size_usd", 0),
                strategy_name="AI Signal Engine", sl_price=sl_price or 0, 
                tp1=tp1_price or 0, tp2=take_profit.get("tp2_price") or 0, tp3=0,
                status="OPEN"
            )
            db.add(new_trade)
            db.commit()
            logger.info(f"Saved auto trade for {coin}")
            
    except Exception as e:
        logger.exception(f"Error executing AI signal: {e}")
