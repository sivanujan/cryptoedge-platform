from database.connection import SessionLocal
from database.models import BacktestResult, Coin, Strategy
import json

db = SessionLocal()
target_coins = ["TRB/USDT:USDT", "MANTA/USDT:USDT", "GLM/USDT:USDT", "VANRY/USDT:USDT"]
results = db.query(BacktestResult).join(Coin).filter(Coin.symbol.in_(target_coins)).limit(20).all()

print(f"Checking results for {target_coins}...")

for r in results:
    coin = r.coin
    strategy = r.strategy
    print(f"Coin: {coin.symbol}, Strategy: {strategy.name}, TF: {r.timeframe}")
    print(f"  Win Rate: {r.win_rate}, Trades: {r.total_trades}, Return: {r.total_return}")
    print(f"  Drawdown: {r.max_drawdown}, Sharpe: {r.sharpe_ratio}")
    print("-" * 20)

db.close()
