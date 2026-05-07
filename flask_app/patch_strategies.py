import sys
sys.path.insert(0, '.')
from database.connection import SessionLocal
from database.models import Strategy

KAMA_CODE = """import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class KamaTrendStrategy(BaseStrategy):
    name = 'KAMA Trend Strategy'
    description = 'Trend following using EMA crossover with RSI filter, adapted from KAMA PineScript.'
    default_params = {'fast_len': 21, 'slow_len': 50, 'trend_len': 200, 'maxDrawdownPct': 3.0}

    def generate_signals(self, df):
        df = df.copy()
        df['signal'] = 0
        df['confidence'] = 50.0

        ema_fast = df['ema_21']
        ema_slow = df['ema_50']
        ema_trend = df['ema_200']
        rsi = df['rsi_14']
        close = df['close']

        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        buy_cond  = cross_above & (close > ema_trend) & (rsi > 40) & (rsi < 75)
        sell_cond = cross_below & (close < ema_trend) & (rsi < 60) & (rsi > 25)

        df.loc[buy_cond,  'signal'] = 1
        df.loc[sell_cond, 'signal'] = -1
        df.loc[buy_cond,  'confidence'] = 72.0
        df.loc[sell_cond, 'confidence'] = 72.0
        return df

_STRATEGY_CLASS = KamaTrendStrategy
"""

GOLD_CODE = """import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class TvcGoldIntrabarAutoStrategy(BaseStrategy):
    name = 'TVC:GOLD | G1 Intrabar Auto v6'
    description = 'Intrabar momentum using MACD + Bollinger Bands + RSI, adapted from TVC:GOLD PineScript.'
    default_params = {'maxDrawdownPct': 2.0}

    def generate_signals(self, df):
        df = df.copy()
        df['signal'] = 0
        df['confidence'] = 50.0

        close = df['close']
        macd  = df['macd']
        macd_sig = df['macd_signal']
        rsi = df['rsi_14']
        bb_mid = df['bb_mid']

        macd_up   = (macd > macd_sig) & (macd.shift(1) <= macd_sig.shift(1))
        macd_down = (macd < macd_sig) & (macd.shift(1) >= macd_sig.shift(1))

        buy_cond  = macd_up   & (close > bb_mid) & (rsi > 35) & (rsi < 70)
        sell_cond = macd_down & (close < bb_mid) & (rsi > 30) & (rsi < 65)

        df.loc[buy_cond,  'signal'] = 1
        df.loc[sell_cond, 'signal'] = -1
        df.loc[buy_cond,  'confidence'] = 65.0
        df.loc[sell_cond, 'confidence'] = 65.0
        return df

_STRATEGY_CLASS = TvcGoldIntrabarAutoStrategy
"""

# EMA 200 Trendline Breakout - strategy id 5 (or whatever it is)
EMA200_CODE = """import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class Ema200TrendlineBreakoutStrategy(BaseStrategy):
    name = 'EMA 200 Trendline Breakout Strategy'
    description = 'Breakout strategy using EMA200 trend filter with volume confirmation.'
    default_params = {'maxDrawdownPct': 3.0}

    def generate_signals(self, df):
        df = df.copy()
        df['signal'] = 0
        df['confidence'] = 50.0

        close    = df['close']
        ema_fast = df['ema_21']
        ema_slow = df['ema_50']
        ema_trend = df['ema_200']
        rsi  = df['rsi_14']
        macd = df['macd']
        macd_sig = df['macd_signal']

        # Price breaks above EMA200 with EMA crossover confirmation
        above_trend = close > ema_trend
        below_trend = close < ema_trend

        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        macd_bull = macd > macd_sig
        macd_bear = macd < macd_sig

        buy_cond  = cross_above & above_trend & macd_bull & (rsi > 45) & (rsi < 75)
        sell_cond = cross_below & below_trend & macd_bear & (rsi < 55) & (rsi > 25)

        df.loc[buy_cond,  'signal'] = 1
        df.loc[sell_cond, 'signal'] = -1
        df.loc[buy_cond,  'confidence'] = 75.0
        df.loc[sell_cond, 'confidence'] = 75.0
        return df

_STRATEGY_CLASS = Ema200TrendlineBreakoutStrategy
"""

db = SessionLocal()
patched = 0
for s in db.query(Strategy).filter(Strategy.python_code != None).all():
    if 'KAMA' in s.name or 'kama' in s.name.lower():
        s.python_code = KAMA_CODE
        print(f'Patched KAMA: {s.name} (id={s.id})')
        patched += 1
    elif 'GOLD' in s.name or 'TVC' in s.name:
        s.python_code = GOLD_CODE
        print(f'Patched GOLD: {s.name} (id={s.id})')
        patched += 1
    elif 'EMA 200' in s.name or 'Trendline' in s.name:
        s.python_code = EMA200_CODE
        print(f'Patched EMA200: {s.name} (id={s.id})')
        patched += 1

db.commit()
db.close()
print(f'Done — patched {patched} strategies')
