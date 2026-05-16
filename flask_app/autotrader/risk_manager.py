import math
import logging

logger = logging.getLogger(__name__)

def calculate_position_size(balance, percent, price, leverage):
    """Calculate the position size based on available balance and leverage."""
    margin = balance * (percent / 100)
    quantity = (margin * leverage) / price
    return quantity

def calculate_stop_loss(entry_price, side, leverage, max_loss_percent=50):
    """Calculate SL price. Max loss defaults to 50% of the trade margin."""
    sl_distance_percent = max_loss_percent / leverage
    if side == "LONG":
        sl_price = entry_price * (1 - sl_distance_percent/100)
    else:
        sl_price = entry_price * (1 + sl_distance_percent/100)
    return sl_price

def calculate_take_profits(entry_price, side, leverage):
    """Calculate TP1, TP2, TP3 (1R, 2R, 3R where R is SL distance)."""
    sl_distance_percent = 50 / leverage
    tp_distances = [sl_distance_percent, sl_distance_percent * 2, sl_distance_percent * 3]
    
    tps = []
    for dist in tp_distances:
        if side == "LONG":
            tps.append(entry_price * (1 + dist/100))
        else:
            tps.append(entry_price * (1 - dist/100))
    return tps[0], tps[1], tps[2]

def trailing_sl_logic(trade, current_price):
    """
    PHASE 1: Price reaches TP1 -> move SL to breakeven (entry price)
    PHASE 2: Price reaches TP2 -> move SL to TP1 price
    PHASE 3: Price reaches TP3 -> Trade closed via TP3 order
    """
    updated = False
    
    if trade.side == "LONG":
        if not trade.sl_moved_to_be and current_price >= trade.tp1:
            trade.sl_price = trade.entry_price
            trade.sl_moved_to_be = True
            updated = True
        if not trade.sl_moved_to_tp1 and current_price >= trade.tp2:
            trade.sl_price = trade.tp1
            trade.sl_moved_to_tp1 = True
            updated = True
    else: # SHORT
        if not trade.sl_moved_to_be and current_price <= trade.tp1:
            trade.sl_price = trade.entry_price
            trade.sl_moved_to_be = True
            updated = True
        if not trade.sl_moved_to_tp1 and current_price <= trade.tp2:
            trade.sl_price = trade.tp1
            trade.sl_moved_to_tp1 = True
            updated = True
            
    return updated

def check_daily_loss_limit(db, limit_percent, starting_balance):
    from database.models import DailyPnlSummary
    from datetime import datetime
    today = datetime.utcnow().strftime('%Y-%m-%d')
    summary = db.query(DailyPnlSummary).filter_by(date=today).first()
    
    if not summary:
        return False
        
    loss_percent = abs(summary.gross_pnl) / starting_balance * 100 if summary.gross_pnl < 0 else 0
    if loss_percent >= limit_percent:
        return True
    return False
