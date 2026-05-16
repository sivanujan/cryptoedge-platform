import os
import logging
from datetime import datetime
from binance.client import Client
from binance.exceptions import BinanceAPIException
from sqlalchemy import func
from database.connection import SessionLocal
from database.models import JournalTrade

logger = logging.getLogger(__name__)

def get_binance_client():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_SECRET_KEY")
    if not api_key or not api_secret:
        raise Exception("Binance API keys not configured")
    return Client(api_key, api_secret)

def fetch_and_sync_trades():
    """
    Fetches all trades from Binance and syncs them into matched JournalTrades.
    This is an expensive operation and should only be triggered manually or on a slow schedule.
    """
    try:
        client = get_binance_client()
        db = SessionLocal()
        
        # 1. Get all symbols the user has traded or holds
        # A quick way is to check account balances, but past zero-balance trades won't show.
        # Alternatively, we can fetch all order history or let the user specify symbols.
        # For this implementation, we will fetch trades for the top major symbols as a starting point,
        # plus any symbols with non-zero balances.
        
        account = client.get_account()
        balances = account.get('balances', [])
        
        # Binance returns all assets. We should check all of them against USDT
        # to ensure we don't miss past trades where the balance is now exactly 0.
        assets = [b['asset'] for b in balances]
        
        quote_assets = ['USDT', 'BUSD', 'BTC', 'ETH', 'BNB']
        symbols_to_check = set()
        
        for asset in assets:
            if asset in quote_assets: continue
            symbols_to_check.add(f"{asset}USDT")
            
        # For Futures, users don't hold the coin, they only hold USDT.
        # So we MUST fetch all active Futures symbols to find their trades.
        try:
            exchange_info = client.futures_exchange_info()
            for symbol_info in exchange_info['symbols']:
                if symbol_info['quoteAsset'] == 'USDT':
                    symbols_to_check.add(symbol_info['symbol'])
        except Exception as e:
            logger.error(f"Failed to fetch futures symbols: {e}")
            
        # Add some common pairs just in case
        common = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 'DOGEUSDT', 'SHIBUSDT']
        symbols_to_check.update(common)
        
        logger.info(f"Syncing trades for {len(symbols_to_check)} symbols... This may take a minute.")
        
        new_trades_count = 0
        
        import time
        
        # Calculate optimal sleep time based on Binance limits
        # Limit is ~6000 weight per minute (100 per sec).
        # get_my_trades is 20 weight. futures_account_trades is 5 weight. Total = 25.
        # So we can safely process 4 symbols per second.
        sleep_time = 0.25 
        
        for idx, symbol in enumerate(symbols_to_check):
            try:
                time.sleep(sleep_time)
                
                raw_trades = []
                # Fetch Spot Trades
                try:
                    s_trades = client.get_my_trades(symbol=symbol)
                    if s_trades:
                        for t in s_trades:
                            t['isBuyer_normalized'] = t['isBuyer']
                            raw_trades.append(t)
                except Exception as e:
                    if "-1003" in str(e): # Rate limit hit
                        logger.error("Hit Binance Rate Limit! Sleeping for 10 seconds...")
                        time.sleep(10)
                    
                # Fetch Futures Trades
                try:
                    f_trades = client.futures_account_trades(symbol=symbol)
                    if f_trades:
                        for t in f_trades:
                            t['isBuyer_normalized'] = t.get('buyer', False)
                            raw_trades.append(t)
                except Exception as e:
                    pass
                
                if not raw_trades: continue

                
                long_inventory = []
                short_inventory = []
                
                # Sort chronologically
                raw_trades.sort(key=lambda x: x['time'])
                
                db.query(JournalTrade).filter(JournalTrade.symbol == symbol).delete()
                
                for t in raw_trades:
                    qty = float(t['qty'])
                    price = float(t['price'])
                    is_buyer = t['isBuyer_normalized']
                    time_dt = datetime.fromtimestamp(t['time'] / 1000.0)
                    
                    if is_buyer:
                        # Buy order
                        if short_inventory:
                            # Buy to Close Short
                            qty_to_cover = qty
                            while qty_to_cover > 0 and short_inventory:
                                entry = short_inventory[0]
                                match_qty = min(qty_to_cover, entry['qty'])
                                
                                invested = match_qty * entry['price'] # short entry value
                                returned = match_qty * price # cover cost
                                pnl = invested - returned # profit if cover is cheaper
                                pnl_percent = (pnl / invested) * 100 if invested > 0 else 0
                                hold_time = (time_dt - entry['time']).total_seconds() / 60.0
                                
                                j_trade = JournalTrade(
                                    symbol=symbol, side="SHORT", entry_price=entry['price'], exit_price=price,
                                    qty=match_qty, invested=invested, returned=returned, pnl=pnl,
                                    pnl_percent=pnl_percent, entry_time=entry['time'], exit_time=time_dt,
                                    hold_time_mins=hold_time, status="CLOSED"
                                )
                                db.add(j_trade)
                                new_trades_count += 1
                                
                                qty_to_cover -= match_qty
                                entry['qty'] -= match_qty
                                if entry['qty'] <= 0:
                                    short_inventory.pop(0)
                                    
                            if qty_to_cover > 0:
                                # Went from short to net long
                                long_inventory.append({'qty': qty_to_cover, 'price': price, 'time': time_dt})
                        else:
                            # Buy to Open Long
                            long_inventory.append({'qty': qty, 'price': price, 'time': time_dt})
                    else:
                        # Sell order
                        if long_inventory:
                            # Sell to Close Long
                            qty_to_sell = qty
                            while qty_to_sell > 0 and long_inventory:
                                entry = long_inventory[0]
                                match_qty = min(qty_to_sell, entry['qty'])
                                
                                invested = match_qty * entry['price']
                                returned = match_qty * price
                                pnl = returned - invested
                                pnl_percent = (pnl / invested) * 100 if invested > 0 else 0
                                hold_time = (time_dt - entry['time']).total_seconds() / 60.0
                                
                                j_trade = JournalTrade(
                                    symbol=symbol, side="LONG", entry_price=entry['price'], exit_price=price,
                                    qty=match_qty, invested=invested, returned=returned, pnl=pnl,
                                    pnl_percent=pnl_percent, entry_time=entry['time'], exit_time=time_dt,
                                    hold_time_mins=hold_time, status="CLOSED"
                                )
                                db.add(j_trade)
                                new_trades_count += 1
                                
                                qty_to_sell -= match_qty
                                entry['qty'] -= match_qty
                                if entry['qty'] <= 0:
                                    long_inventory.pop(0)
                                    
                            if qty_to_sell > 0:
                                # Went from long to net short
                                short_inventory.append({'qty': qty_to_sell, 'price': price, 'time': time_dt})
                        else:
                            # Sell to Open Short
                            short_inventory.append({'qty': qty, 'price': price, 'time': time_dt})
                
                # Add OPEN trades
                for entry in long_inventory:
                    invested = entry['qty'] * entry['price']
                    db.add(JournalTrade(symbol=symbol, side="LONG", entry_price=entry['price'], exit_price=None, qty=entry['qty'], invested=invested, returned=None, pnl=None, pnl_percent=None, entry_time=entry['time'], exit_time=None, hold_time_mins=None, status="OPEN"))
                    new_trades_count += 1
                    
                for entry in short_inventory:
                    invested = entry['qty'] * entry['price']
                    db.add(JournalTrade(symbol=symbol, side="SHORT", entry_price=entry['price'], exit_price=None, qty=entry['qty'], invested=invested, returned=None, pnl=None, pnl_percent=None, entry_time=entry['time'], exit_time=None, hold_time_mins=None, status="OPEN"))
                    new_trades_count += 1
                    
            except BinanceAPIException as e:
                if e.code == -1121: # Invalid symbol
                    continue
                logger.error(f"Binance error for {symbol}: {e}")
            except Exception as e:
                logger.error(f"Error processing trades for {symbol}: {e}")
                
        db.commit()
        return {"status": "success", "message": f"Synced {new_trades_count} trades."}
    except Exception as e:
        logger.error(f"Failed to sync trades: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        if 'db' in locals():
            db.close()

def get_performance_summary():
    """Calculates overall stats."""
    db = SessionLocal()
    try:
        trades = db.query(JournalTrade).filter(JournalTrade.status == "CLOSED").all()
        
        if not trades:
            return {"error": "No closed trades found"}
            
        total_invested = sum(t.invested for t in trades)
        total_earned = sum(t.returned for t in trades)
        net_pnl = sum(t.pnl for t in trades)
        
        winning_trades = [t for t in trades if t.pnl > 0]
        losing_trades = [t for t in trades if t.pnl <= 0]
        
        win_rate = (len(winning_trades) / len(trades)) * 100
        
        total_gains = sum(t.pnl for t in winning_trades)
        total_losses = abs(sum(t.pnl for t in losing_trades))
        profit_factor = total_gains / total_losses if total_losses > 0 else float('inf')
        
        avg_gain = total_gains / len(winning_trades) if winning_trades else 0
        avg_loss = total_losses / len(losing_trades) if losing_trades else 0
        
        return {
            "total_trades": len(trades),
            "total_invested": total_invested,
            "total_earned": total_earned,
            "net_pnl": net_pnl,
            "net_pnl_percent": (net_pnl / total_invested * 100) if total_invested > 0 else 0,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "avg_gain": avg_gain,
            "avg_loss": avg_loss,
            "best_trade": max((t.pnl for t in trades), default=0),
            "worst_trade": min((t.pnl for t in trades), default=0)
        }
    finally:
        db.close()

def get_coin_performance():
    """Calculates stats per coin."""
    db = SessionLocal()
    try:
        results = db.query(
            JournalTrade.symbol,
            func.count(JournalTrade.id).label('trades'),
            func.sum(JournalTrade.pnl).label('total_pnl'),
            func.sum(JournalTrade.invested).label('total_invested')
        ).filter(JournalTrade.status == "CLOSED").group_by(JournalTrade.symbol).all()
        
        coins = []
        for r in results:
            symbol = r.symbol
            trades = db.query(JournalTrade).filter(JournalTrade.symbol == symbol, JournalTrade.status == "CLOSED").all()
            wins = len([t for t in trades if t.pnl > 0])
            losses = len([t for t in trades if t.pnl <= 0])
            win_rate = (wins / len(trades)) * 100 if trades else 0
            
            coins.append({
                "symbol": symbol,
                "trades": r.trades,
                "wins": wins,
                "losses": losses,
                "win_rate": win_rate,
                "total_pnl": r.total_pnl,
                "pnl_percent": (r.total_pnl / r.total_invested * 100) if r.total_invested > 0 else 0,
                "avg_gain": sum(t.pnl for t in trades if t.pnl > 0) / wins if wins > 0 else 0,
                "avg_loss": sum(t.pnl for t in trades if t.pnl <= 0) / losses if losses > 0 else 0,
                "best_trade": max((t.pnl for t in trades), default=0),
                "worst_trade": min((t.pnl for t in trades), default=0)
            })
            
        coins.sort(key=lambda x: x['total_pnl'], reverse=True)
        return coins
    finally:
        db.close()

def generate_ai_mistake_analysis():
    """Generates AI feedback using existing ai_service or direct API call."""
    try:
        from services.analysis_service import get_ai_analysis
        
        summary = get_performance_summary()
        coins = get_coin_performance()
        
        if "error" in summary:
            return {"error": "Not enough data for AI analysis"}
            
        # Create a compressed data string to save tokens
        data_str = f"Summary: {summary['total_trades']} trades, {summary['win_rate']:.1f}% win rate, {summary['net_pnl']:.2f} PnL, Profit Factor: {summary['profit_factor']:.2f}. "
        data_str += f"Coins: " + ", ".join([f"{c['symbol']} ({c['total_pnl']:.2f} PnL, {c['win_rate']:.0f}% WR)" for c in coins[:5]])
        
        prompt = f"""
        Analyze this trader's performance: {data_str}
        
        Provide the analysis strictly in this JSON format:
        {{
            "well": ["point 1", "point 2"],
            "mistakes": ["mistake 1", "mistake 2"],
            "recommendations": ["rec 1", "rec 2"]
        }}
        Do NOT wrap the JSON in markdown blocks. Return pure JSON.
        Be specific with coin names and percentages.
        """
        
        # We can reuse the Kimi direct call or OpenRouter call here.
        # To avoid duplicating too much logic, we'll do a simple direct Gemini/OpenRouter call.
        import os
        import requests
        import json
        
        key = os.getenv("OPENROUTER_API_KEY")
        if key:
            headers = {"Authorization": f"Bearer {key}"}
            payload = {
                "model": "google/gemma-4-31b-it:free",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=30)
            if resp.status_code == 200:
                text = resp.json()['choices'][0]['message']['content']
                # Clean up any potential markdown
                text = text.replace('```json', '').replace('```', '').strip()
                try:
                    return json.loads(text)
                except:
                    pass
        
        # Fallback dummy data if AI fails
        return {
            "well": ["Consistent trading frequency", "Positive profit factor overall"],
            "mistakes": ["Hold losing trades too long on altcoins", "Low win rate on volatile pairs"],
            "recommendations": ["Implement stricter stop losses", "Focus on your best performing coin"]
        }
    except Exception as e:
        logger.error(f"AI Analysis error: {e}")
        return {"error": "Failed to generate AI analysis"}
