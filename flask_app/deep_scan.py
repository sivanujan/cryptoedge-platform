import os
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.getenv("BINANCE_API_KEY"), os.getenv("BINANCE_SECRET_KEY"))

print("=" * 60)
print("DEEP ACCOUNT SCANNER - LOOKING FOR POST-2023 ACTIVITY")
print("=" * 60)

# Check Spot
try:
    print("Checking Spot (BTCUSDT)...")
    trades = client.get_my_trades(symbol='BTCUSDT')
    if trades:
        print(f"  -> Last Spot BTC Trade: {trades[-1]['time']}")
    else:
        print("  -> No Spot BTC trades")
except Exception as e:
    print(f"Spot error: {e}")

# Check USD-M Futures
try:
    print("Checking USD-M Futures (BTCUSDT)...")
    ftrades = client.futures_account_trades(symbol='BTCUSDT')
    if ftrades:
        print(f"  -> Last USD-M Futures BTC Trade: {ftrades[-1]['time']}")
    else:
        print("  -> No USD-M Futures BTC trades")
except Exception as e:
    print(f"USD-M Futures error: {e}")

# Check COIN-M Futures
try:
    print("Checking COIN-M Futures (BTCUSD_PERP)...")
    # coin-m endpoint
    # cm_trades = client.get_my_trades(...) # python-binance has different methods
except Exception as e:
    pass

# Check Margin
try:
    print("Checking Margin (BTCUSDT)...")
    mtrades = client.get_margin_trades(symbol='BTCUSDT')
    if mtrades:
        print(f"  -> Last Margin BTC Trade: {mtrades[-1]['time']}")
    else:
        print("  -> No Margin BTC trades")
except Exception as e:
    print(f"Margin error: {e}")

# Check Convert Trade History (Over-The-Counter)
try:
    print("Checking Convert/OTC Trades...")
    import time
    end_time = int(time.time() * 1000)
    start_time = end_time - (30 * 24 * 60 * 60 * 1000) # last 30 days
    convert = client.get_convert_trade_history(startTime=start_time, endTime=end_time)
    print(f"  -> Found {len(convert.get('list', []))} Convert trades in last 30 days.")
except Exception as e:
    print(f"Convert error: {e}")

print("=" * 60)
