import logging
import os
import time
from binance.client import Client

logger = logging.getLogger(__name__)

_time_offset = 0
_time_offset_calculated = False

def get_client():
    global _time_offset, _time_offset_calculated
    
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    if not api_key or not api_secret:
        logger.warning("Binance API keys missing in environment!")
        return None
    if api_key.startswith('"') and api_key.endswith('"'):
        api_key = api_key[1:-1]
    if api_secret.startswith('"') and api_secret.endswith('"'):
        api_secret = api_secret[1:-1]
        
    client = Client(api_key, api_secret)
    
    if not _time_offset_calculated:
        try:
            # Sync time with Binance
            server_time = client.get_server_time()['serverTime']
            local_time = int(time.time() * 1000)
            _time_offset = server_time - local_time
            _time_offset_calculated = True
            logger.info(f"Calculated Binance time offset: {_time_offset}ms")
            
            # Monkey patch Client._get_timestamp
            def patched_get_timestamp(self):
                return int((time.time() * 1000) + _time_offset)
            
            Client._get_timestamp = patched_get_timestamp
            logger.info("Monkey-patched Client._get_timestamp with offset")
        except Exception as e:
            logger.warning(f"Failed to calculate time offset or patch client: {e}")
            
    return client

def set_leverage(symbol, leverage):
    client = get_client()
    if not client: return False
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        return True
    except Exception as e:
        logger.error(f"Error setting leverage for {symbol}: {e}")
        return False

def place_market_order(symbol, side, quantity):
    client = get_client()
    if not client: return None
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity
        )
        return order
    except Exception as e:
        logger.error(f"Error placing market order for {symbol}: {e}")
        return None

def place_stop_market_order(symbol, side, quantity, stop_price):
    client = get_client()
    if not client: return None
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='STOP_MARKET',
            quantity=quantity,
            stopPrice=stop_price,
            closePosition=True
        )
        return order
    except Exception as e:
        logger.error(f"Error placing stop order for {symbol}: {e}")
        return None

def place_take_profit_market_order(symbol, side, quantity, tp_price):
    client = get_client()
    if not client: return None
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=side,
            type='TAKE_PROFIT_MARKET',
            quantity=quantity,
            stopPrice=tp_price,
            closePosition=True
        )
        return order
    except Exception as e:
        logger.error(f"Error placing TP order for {symbol}: {e}")
        return None

def get_open_positions():
    client = get_client()
    if not client: return []
    try:
        positions = client.futures_position_information()
        return [p for p in positions if float(p['positionAmt']) != 0]
    except Exception as e:
        logger.error(f"Error fetching open positions: {e}")
        return []

def get_futures_balance():
    client = get_client()
    if not client: return 0.0, 0.0, 0.0
    try:
        total_balance = 0.0
        available_balance = 0.0
        unrealized_pnl = 0.0
        
        balances = client.futures_account_balance()
        logger.info(f"Futures balances: {balances}")
        for b in balances:
            if b['asset'] == 'USDT':
                total_balance = float(b.get('balance', 0))
                available_balance = float(b.get('withdrawAvailable', 0))
                
        positions = client.futures_position_information()
        for p in positions:
            if p['symbol'].endswith('USDT') and float(p['positionAmt']) != 0:
                unrealized_pnl += float(p.get('unRealizedProfit', 0))
                
        return total_balance, available_balance, unrealized_pnl
    except Exception as e:
        logger.error(f"Error fetching futures balance: {e}")
        return 0.0, 0.0, 0.0

def cancel_existing_orders(symbol):
    client = get_client()
    if not client: return False
    try:
        client.futures_cancel_all_open_orders(symbol=symbol)
        return True
    except Exception as e:
        logger.error(f"Error canceling orders for {symbol}: {e}")
        return False
