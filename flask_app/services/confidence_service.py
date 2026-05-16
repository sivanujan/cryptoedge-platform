def calculate_confidence_score(win_rate, trades, coins_tested, coins_above_65, return_pct, drawdown):
    """
    Calculate a 0-100 confidence score for a strategy setup.
    Returns: (score, grade, verdict_text)
    """
    score = 0.0
    
    # 1. Win rate component (max 35 pts)
    if win_rate:
        score += (win_rate / 100.0) * 35.0
        
    # 2. Sample size component (max 25 pts)
    if trades >= 20:
        score += 25
    elif trades >= 10:
        score += 18
    elif trades >= 5:
        score += 10
    elif trades >= 3:
        score += 5
        
    # 3. Coverage component (max 20 pts)
    if coins_tested and coins_tested > 0:
        coverage_ratio = coins_above_65 / coins_tested
        score += coverage_ratio * 20.0
        
    # 4. Return vs drawdown (max 20 pts)
    if drawdown and drawdown > 0 and return_pct:
        rd_ratio = return_pct / drawdown
        score += min(rd_ratio * 5.0, 20.0)
        
    # Determine Grade
    grade = "F"
    if score >= 80:
        grade = "A"
    elif score >= 65:
        grade = "B"
    elif score >= 50:
        grade = "C"
    elif score >= 35:
        grade = "D"
        
    # Determine Verdict Text
    verdict = "WAIT"
    if score >= 65 and win_rate >= 60:
        verdict = "TAKE"
    elif win_rate < 60:
        verdict = "SKIP"
        
    return {
        "score": round(score, 1),
        "grade": grade,
        "verdict": verdict
    }
