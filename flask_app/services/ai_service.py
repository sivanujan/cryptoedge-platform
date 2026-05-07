"""
AI Service — converts Pine Script to Python BaseStrategy class
using OpenRouter (Paid Models) to avoid free-tier rate limits.
"""
import os
import re
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# NVIDIA AI configuration
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_URL = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MODEL = os.getenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")

# OpenRouter fallback configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

# Fallback models prioritized if the default fails or is exhausted
MODEL_FALLBACKS = [
    DEFAULT_MODEL,
    "google/gemma-4-31b-it:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-coder:free"
]
# Ensure no duplicates while preserving order
MODEL_FALLBACKS = list(dict.fromkeys(MODEL_FALLBACKS))

_SYSTEM_PROMPT = """You are an expert algorithmic trading developer.
Your job is to convert TradingView Pine Script strategies into Python classes
that extend the BaseStrategy interface shown below.

──────────── BaseStrategy interface ────────────
class BaseStrategy(ABC):
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        # df already has these columns (use them directly, no need to recompute):
        # OHLCV: open, high, low, close, volume
        # EMAs:  ema_21, ema_50, ema_200
        # RSI:   rsi_14
        # MACD:  macd, macd_signal, macd_hist
        # Bollinger: bb_upper, bb_mid, bb_lower, bb_width
        # ATR:   atr_14
        # Volume: volume_sma, volume_ratio
        # Stochastic: stoch_k, stoch_d (if available)
        # Must add: df['signal'] = 1/0/-1  and  df['confidence'] = 0-100 float
        pass
──────────── End of interface ────────────

CRITICAL RULES:
1. Output ONLY valid Python code with NO markdown fences or explanation text.
2. Start file with:
   import pandas as pd
   import numpy as np
   from strategies.base_strategy import BaseStrategy
3. Class MUST have `name`, `description`, and `default_params` class attributes.
4. ONLY use columns listed in the df column list above. DO NOT compute custom
   indicators (like KAMA, HullMA, SuperTrend) inside generate_signals —
   they require iterative loops that produce all-NaN or break on index resets.
5. The signal column must only contain INTEGER values: 1 (BUY), -1 (SELL), 0 (HOLD).
   Use: df['signal'] = 0 first, then assign 1/-1 with df.loc[condition, 'signal'] = 1
6. Confidence column must be a float between 0 and 100.
7. Your signal conditions MUST be able to evaluate to True on real OHLCV data.
   Use crossover helpers like: cross_above = (ema_21 > ema_50) & (ema_21.shift(1) <= ema_50.shift(1))
8. NEVER use for-loops to compute signals — use vectorized pandas operations only.
9. End the file with exactly:  _STRATEGY_CLASS = <YourClassName>

WORKING EXAMPLE of correct generate_signals:

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df['signal'] = 0
        df['confidence'] = 50.0

        ema_fast = df['ema_21']
        ema_slow = df['ema_50']
        rsi = df['rsi_14']

        # Crossover conditions (vectorized, never loop)
        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        buy_cond  = cross_above & (rsi > 40) & (rsi < 70)
        sell_cond = cross_below & (rsi < 60) & (rsi > 30)

        df.loc[buy_cond,  'signal'] = 1
        df.loc[sell_cond, 'signal'] = -1
        df.loc[buy_cond,  'confidence'] = 70.0
        df.loc[sell_cond, 'confidence'] = 70.0
        return df
"""

_USER_TEMPLATE = """Convert the following Pine Script strategy to a Python BaseStrategy class.
The class name should be a PascalCase version of the strategy name.
Only use the indicator columns listed in the system prompt — do NOT compute any custom indicators.
Use simple, vectorized crossover/threshold conditions on ema_21, ema_50, ema_200, rsi_14, macd, bb_upper, bb_lower, atr_14.

Pine Script:
{pine_script}

Output only the Python class code (no markdown text before or after):"""


def convert_pine_to_python(pine_script: str, strategy_name: str = "") -> str:
    """
    Call NVIDIA AI (primary) or OpenRouter (fallback) to convert Pine Script to Python.
    """
    if not NVIDIA_API_KEY and not OPENROUTER_API_KEY:
        raise RuntimeError("AI API key is missing. Set NVIDIA_API_KEY or OPENROUTER_API_KEY in .env")

    user_msg = _USER_TEMPLATE.format(pine_script=pine_script.strip())
    
    payload = {
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_msg}
        ],
        "temperature": 0.1,
    }

    # Try OpenRouter FIRST (User requested for timeout troubleshooting)
    if OPENROUTER_API_KEY:
        fallback_models = [OPENROUTER_MODEL, "meta-llama/llama-3.3-70b-instruct:free", "google/gemma-4-31b-it:free"]
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "HTTP-Referer": "http://localhost:5174",
            "X-Title": "CryptoEdge Pine Converter",
        }
        
        last_error = None
        for model in fallback_models:
            payload["model"] = model
            logger.info(f"Trying OpenRouter model: {model}...")
            try:
                resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=180)
                if resp.status_code == 200:
                    data = resp.json()
                    code = data["choices"][0]["message"]["content"]
                    logger.info(f"Successfully converted with OpenRouter model: {model}")
                    return _strip_code_fences(code).strip()
                else:
                    last_error = f"OR Status {resp.status_code}: {resp.text}"
                    logger.error(f"OpenRouter model {model} failed: {last_error}")
            except Exception as e:
                last_error = str(e)
                logger.exception(f"OpenRouter exception for model {model}: {e}")
                continue

    # Fallback to NVIDIA
    if NVIDIA_API_KEY:
        try:
            payload["model"] = DEFAULT_MODEL
            headers = {
                "Authorization": f"Bearer {NVIDIA_API_KEY}",
                "Accept": "application/json",
            }
            logger.info(f"Trying NVIDIA fallback model: {DEFAULT_MODEL}...")
            resp = requests.post(NVIDIA_URL, json=payload, headers=headers, timeout=180)
            
            if resp.status_code == 200:
                data = resp.json()
                code = data["choices"][0]["message"]["content"]
                logger.info("Successfully converted with NVIDIA AI")
                return _strip_code_fences(code).strip()
            else:
                last_error = f"NVIDIA Status {resp.status_code}: {resp.text}"
                logger.warning(f"NVIDIA API error: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"NVIDIA conversion failed: {e}")

    raise RuntimeError(f"All AI providers failed. Last error: {last_error if (OPENROUTER_API_KEY or NVIDIA_API_KEY) else 'No keys'}")

    # Strip any markdown code fences the model may have added
    code = _strip_code_fences(code)

    logger.info("Pine Script successfully converted to Python.")
    return code.strip()


def _strip_code_fences(text: str) -> str:
    """Remove markdown ```python ... ``` fences if present."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    return text.strip()


def validate_strategy_code(code: str) -> tuple[bool, str]:
    """Validate that the generated code compiles and extends BaseStrategy."""
    try:
        compile(code, "<string>", "exec")
    except SyntaxError as e:
        return False, f"Syntax error in generated code: {e}"

    if "generate_signals" not in code:
        return False, "Generated code does not contain generate_signals method"

    if "_STRATEGY_CLASS" not in code:
        return False, "Generated code is missing _STRATEGY_CLASS marker at the end"

    return True, ""
