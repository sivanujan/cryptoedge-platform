import logging
from sqlalchemy.orm import Session
from database.models import CoinResult, StrategyRanking, Strategy

logger = logging.getLogger(__name__)

def calculate_and_store_rankings(db: Session, strategy_id: int):
    """
    Calculate and store rankings for a specific strategy based on user's 7-step plan.
    Reads data from CoinResult table (populated via bulk import).
    """
    logger.info(f"Calculating rankings for strategy {strategy_id}")
    
    # 1. Fetch all coin results for this strategy
    results = db.query(CoinResult).filter_by(strategy_id=strategy_id).all()
    
    if not results:
        logger.info(f"No coin results found for strategy {strategy_id}")
        return
        
    coin_data = {} # coin -> [list of results with scores]
    
    for r in results:
        coin_symbol = r.coin
        tf_results = r.tf_results or {}
        return_pct = r.return_pct or 0.0
        
        for tf, data in tf_results.items():
            win_rate = data.get("win_rate", 0.0)
            trades = data.get("trades", 0)
            
            # Step 1 — Hard Filter (Lowered to match frontend)
            if win_rate < 50 or trades < 5 or return_pct <= 0:
                continue
                
            # Step 2 — Confidence Weight
            weight = 0.0
            if trades >= 100:
                weight = 1.00
            elif trades >= 50:
                weight = 0.90
            elif trades >= 30:
                weight = 0.75
            elif trades >= 20:
                weight = 0.60
            elif trades >= 5:
                weight = 0.40
                
            # Step 3 — Effective Win Rate
            effective_win = win_rate * weight
            
            # Step 4 — Return Score
            return_score = min(return_pct / 40.0, 1.0) * 20.0
            
            # Step 5 — Final Score
            final_score = effective_win + return_score
            
            if coin_symbol not in coin_data:
                coin_data[coin_symbol] = []
                
            coin_data[coin_symbol].append({
                "timeframe": tf,
                "win_rate": win_rate,
                "trades": trades,
                "confidence": weight,
                "final_score": final_score
            })
            
    # Step 6 — Find Valid Timeframes Per Coin and Prepare for Insert
    all_rankings = []
    
    for coin_symbol, tfs in coin_data.items():
        if not tfs:
            continue
            
        # Find best score for this coin
        best_score = max(tf["final_score"] for tf in tfs)
        threshold = best_score * 0.70
        
        for tf in tfs:
            if tf["final_score"] >= threshold:
                all_rankings.append({
                    "strategy_id": strategy_id,
                    "coin": coin_symbol,
                    "timeframe": tf["timeframe"],
                    "win_rate": tf["win_rate"],
                    "trades": tf["trades"],
                    "confidence": tf["confidence"],
                    "final_score": tf["final_score"]
                })
                
    # Step 7 — Rank and Store Top 15 coins per strategy
    # Sort all rankings by final_score desc
    all_rankings.sort(key=lambda x: x["final_score"], reverse=True)
    
    # Take top 15
    top_15 = all_rankings[:15]
    
    # Clear old rankings for this strategy
    db.query(StrategyRanking).filter_by(strategy_id=strategy_id).delete()
    
    # Insert new rankings
    for r in top_15:
        ranking = StrategyRanking(
            strategy_id=r["strategy_id"],
            coin=r["coin"],
            timeframe=r["timeframe"],
            win_rate=r["win_rate"],
            trades=r["trades"],
            confidence=r["confidence"],
            final_score=r["final_score"]
        )
        db.add(ranking)
        
    db.commit()
    logger.info(f"Stored {len(top_15)} rankings for strategy {strategy_id}")
