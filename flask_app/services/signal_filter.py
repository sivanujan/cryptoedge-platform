from datetime import datetime, timezone
from collections import defaultdict

def filter_signals_python(signals_list: list) -> dict:
    """
    Pure Python implementation of the CryptoEdge Signal Filter & Validator.
    Replicates the AI prompt rules without needing an LLM.
    """
    if not signals_list:
        return {"valid_signals": [], "discarded": []}
        
    discarded = []
    
    # ═══════════════════════════════════════
    # STEP 1 — DEDUPLICATION
    # ═══════════════════════════════════════
    # Group by symbol + direction + timeframe
    grouped = defaultdict(list)
    for sig in signals_list:
        # STEP 4: WAIT STATUS HANDLING
        if str(sig.get("status", "")).lower() == "wait":
            # Roughly estimate candles passed. We keep it pending unless it explicitly has an expired flag.
            sig["status"] = "pending"
            
        key = f"{sig.get('symbol')}_{str(sig.get('direction')).upper()}_{sig.get('timeframe')}"
        grouped[key].append(sig)
        
    deduped_signals = []
    for key, group in grouped.items():
        if len(group) > 1:
            # Sort by score descending
            group.sort(key=lambda x: float(x.get("final_score", x.get("score", x.get("confidence", 0)))), reverse=True)
            kept = group[0]
            kept["dedup_action"] = f"merged_from_{len(group)}_duplicates"
            deduped_signals.append(kept)
            for duplicate in group[1:]:
                discarded.append({
                    "symbol": duplicate.get("symbol"),
                    "reason": "duplicate — lower score kept",
                    "score": float(duplicate.get("final_score", duplicate.get("score", duplicate.get("confidence", 0))))
                })
        else:
            group[0]["dedup_action"] = "kept"
            deduped_signals.append(group[0])

    # ═══════════════════════════════════════
    # STEP 2 — CONFLICT RESOLUTION
    # ═══════════════════════════════════════
    # Group by symbol to check for Long and Short simultaneously
    by_symbol = defaultdict(list)
    for sig in deduped_signals:
        by_symbol[sig.get("symbol")].append(sig)
        
    conflict_resolved = []
    for symbol, group in by_symbol.items():
        longs = [s for s in group if str(s.get("direction")).upper() in ["LONG", "BUY"]]
        shorts = [s for s in group if str(s.get("direction")).upper() in ["SHORT", "SELL"]]
        
        if longs and shorts:
            best_long = max(longs, key=lambda x: float(x.get("final_score", x.get("score", x.get("confidence", 0)))))
            best_short = max(shorts, key=lambda x: float(x.get("final_score", x.get("score", x.get("confidence", 0)))))
            
            # Rule C: Same strategy fires LONG and SHORT
            long_strategies = set(s.get("strategy") for s in longs)
            short_strategies = set(s.get("strategy") for s in shorts)
            if long_strategies.intersection(short_strategies):
                for s in group:
                    discarded.append({
                        "symbol": s.get("symbol"),
                        "reason": "Strategy conflict detected — both directions fired from same strategy",
                        "score": float(s.get("final_score", s.get("score", s.get("confidence", 0))))
                    })
                continue
                
            long_score = float(best_long.get("final_score", best_long.get("score", best_long.get("confidence", 0))))
            short_score = float(best_short.get("final_score", best_short.get("score", best_short.get("confidence", 0))))
            
            diff = abs(long_score - short_score)
            
            if diff >= 15:
                # Rule A
                winner = best_long if long_score > short_score else best_short
                loser = best_short if long_score > short_score else best_long
                
                winner["conflict_action"] = f"opposite_discarded (gap {diff} pts)"
                conflict_resolved.append(winner)
                
                discarded.append({
                    "symbol": loser.get("symbol"),
                    "reason": f"conflict — opposite signal discarded (gap {diff} pts)",
                    "score": loser.get("final_score", loser.get("score", loser.get("confidence", 0)))
                })
            else:
                # Rule B
                for s in group:
                    discarded.append({
                        "symbol": s.get("symbol"),
                        "reason": f"conflict — scores too close (long:{long_score} short:{short_score})",
                        "score": float(s.get("final_score", s.get("score", s.get("confidence", 0))))
                    })
        else:
            # No conflict
            for s in group:
                s["conflict_action"] = "none"
                conflict_resolved.append(s)

    # ═══════════════════════════════════════
    # STEP 3 — QUALITY GATE
    # ═══════════════════════════════════════
    valid_signals = []
    
    for sig in conflict_resolved:
        score = float(sig.get("final_score", sig.get("score", sig.get("confidence", 0))))
        
        # Additional quality checks (if metrics available)
        metrics = sig.get("metrics", {})
        
        vol_ratio = metrics.get("volume_ratio")
        if vol_ratio is not None and vol_ratio != "N/A" and float(vol_ratio) < 1.0:
            score -= 10
            
        # Time check (Asian session: 00:00 - 03:00 UTC)
        now = datetime.now(timezone.utc)
        if 0 <= now.hour < 3:
            score -= 5
            
        ema_200 = metrics.get("ema_200")
        price = sig.get("price", sig.get("entry_price"))
        if ema_200 is not None and ema_200 != "N/A" and price is not None:
            direction = str(sig.get("direction")).upper()
            if direction in ["LONG", "BUY"] and float(price) < float(ema_200):
                score -= 8
            elif direction in ["SHORT", "SELL"] and float(price) > float(ema_200):
                score -= 8
                
        sig["final_score"] = score
        
        if score >= 86:
            sig["grade"] = "PREMIUM"
        elif score >= 71:
            sig["grade"] = "GOOD"
        elif score >= 51:
            sig["grade"] = "WEAK"
        else:
            sig["grade"] = "NOISE"
            
        if score >= 71:
            valid_signals.append(sig)
        else:
            discarded.append({
                "symbol": sig.get("symbol"),
                "reason": f"quality gate failed — final score {score} ({sig['grade']})",
                "score": score
            })

    # ═══════════════════════════════════════
    # STEP 5 — FINAL OUTPUT RULES
    # ═══════════════════════════════════════
    valid_signals.sort(key=lambda x: float(x.get("final_score", 0)), reverse=True)
    
    # Keep only top 5
    if len(valid_signals) > 5:
        for sig in valid_signals[5:]:
            discarded.append({
                "symbol": sig.get("symbol"),
                "reason": "batch limit exceeded — not in top 5",
                "score": sig.get("final_score")
            })
        valid_signals = valid_signals[:5]
        
    return {
        "valid_signals": valid_signals,
        "discarded": discarded
    }
