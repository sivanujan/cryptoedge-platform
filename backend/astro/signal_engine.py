import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database.models import BirthChart, TradingSignalLog
from astro.dasha import get_active_dasha_stack
from astro.hora import get_active_hora
from astro.chart import ZODIAC_SIGNS

logger = logging.getLogger(__name__)

# Configurable Weights
MAHA_WEIGHT = 1.0
ANTAR_WEIGHT = 1.5
PRATYANTAR_WEIGHT = 2.0
SOOKSHMA_WEIGHT = 3.0
PRANA_WEIGHT = 4.0
HORA_WEIGHT = 1.5

# Karaka Overlays
RAHU_CRYPTO_BOOST = 0.3      # Rahu represents crypto/intraday speculative technology
MERCURY_ANALYSIS_BOOST = 0.2  # Mercury represents analytics, calculations, and execution
MOON_STABILITY_BOOST = 0.2    # Moon represents psychological balance/mind control

# House Lordship Overlays
FIFTH_HOUSE_SPECULATION = 0.5 # 5th house rules speculation, trading, past good deeds (Purvapunya)
EIGHTH_HOUSE_VOLATILITY = 0.8  # 8th house rules sudden gains/losses, hidden wealth, and extreme volatility

# Functional Benefic/Malefic planet mappings per Ascendant sign (Lagna)
# Benefic = 1.0, Malefic = -1.0, Neutral = 0.0
ASCENDANT_PLANET_NATURE = {
    "Aries": {
        "Sun": 1.0, "Moon": 1.0, "Mars": 1.0, "Jupiter": 1.0,
        "Mercury": -1.0, "Venus": -1.0, "Saturn": -1.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Taurus": {
        "Sun": 1.0, "Mercury": 1.0, "Venus": 1.0, "Saturn": 1.0,
        "Moon": -1.0, "Mars": -1.0, "Jupiter": -1.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Gemini": {
        "Mercury": 1.0, "Venus": 1.0, "Saturn": 1.0,
        "Sun": -1.0, "Mars": -1.0, "Jupiter": -1.0,
        "Moon": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Cancer": {
        "Moon": 1.0, "Mars": 1.0, "Jupiter": 1.0,
        "Mercury": -1.0, "Venus": -1.0, "Saturn": -1.0,
        "Sun": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Leo": {
        "Sun": 1.0, "Mars": 1.0, "Jupiter": 1.0,
        "Moon": -1.0, "Venus": -1.0, "Saturn": -1.0,
        "Mercury": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Virgo": {
        "Mercury": 1.0, "Venus": 1.0,
        "Moon": -1.0, "Mars": -1.0, "Jupiter": -1.0,
        "Sun": 0.0, "Saturn": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Libra": {
        "Venus": 1.0, "Mercury": 1.0, "Saturn": 1.0,
        "Sun": -1.0, "Moon": -1.0, "Mars": -1.0, "Jupiter": -1.0,
        "Rahu": 0.0, "Ketu": 0.0
    },
    "Scorpio": {
        "Mars": 1.0, "Moon": 1.0, "Jupiter": 1.0, "Sun": 1.0,
        "Mercury": -1.0, "Venus": -1.0, "Saturn": -1.0,
        "Rahu": 0.0, "Ketu": 0.0
    },
    "Sagittarius": {
        "Jupiter": 1.0, "Mars": 1.0, "Sun": 1.0,
        "Mercury": -1.0, "Venus": -1.0, "Saturn": -1.0,
        "Moon": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Capricorn": {
        "Venus": 1.0, "Mercury": 1.0, "Saturn": 1.0,
        "Sun": -1.0, "Moon": -1.0, "Mars": -1.0, "Jupiter": -1.0,
        "Rahu": 0.0, "Ketu": 0.0
    },
    "Aquarius": {
        "Saturn": 1.0, "Venus": 1.0, "Sun": 1.0,
        "Moon": -1.0, "Mars": -1.0, "Jupiter": -1.0,
        "Mercury": 0.0, "Rahu": 0.0, "Ketu": 0.0
    },
    "Pisces": {
        "Jupiter": 1.0, "Moon": 1.0, "Mars": 1.0,
        "Mercury": -1.0, "Venus": -1.0, "Saturn": -1.0,
        "Sun": 0.0, "Rahu": 0.0, "Ketu": 0.0
    }
}


def get_planet_house(planet_sign: str, lagna_sign: str) -> int:
    """
    Calculates the house (1-12) of a planet relative to the Ascendant (Lagna) sign.
    """
    try:
        p_idx = ZODIAC_SIGNS.index(planet_sign)
        l_idx = ZODIAC_SIGNS.index(lagna_sign)
        return (p_idx - l_idx) % 12 + 1
    except ValueError:
        return 1


def calculate_signal(db: Session, user_id: int, timestamp: datetime, log_to_db: bool = True):
    """
    Main Vedic astrology trading signal scoring engine.
    Calculates active Dasha levels, active Hora, applies weights/overlays, normalizes,
    and logs outcomes for backtesting.
    """
    # 1. Fetch user's birth chart
    chart = db.query(BirthChart).filter(BirthChart.user_id == user_id).first()
    if not chart:
        raise ValueError(f"No birth chart found for user {user_id}. Generate birth chart first.")
        
    lagna_sign = chart.ascendant_sign
    planet_positions = chart.planet_positions
    if isinstance(planet_positions, str):
        planet_positions = json.loads(planet_positions)
        
    # Get planet natures for this Lagna
    natures = ASCENDANT_PLANET_NATURE.get(lagna_sign, ASCENDANT_PLANET_NATURE["Leo"])
    
    # 2. Get active Dasha stack (5 levels)
    dasha_stack = get_active_dasha_stack(db, user_id, timestamp)
    
    # 3. Get active Hora lord
    lat, long = chart.lat, chart.long
    hora_data = get_active_hora(timestamp, lat, long)
    hora_lord = hora_data["hora_lord"]
    
    # 4. Score each active level
    levels_data = [
        ("maha", dasha_stack["maha"], MAHA_WEIGHT),
        ("antar", dasha_stack["antar"], ANTAR_WEIGHT),
        ("pratyantar", dasha_stack["pratyantar"], PRATYANTAR_WEIGHT),
        ("sookshma", dasha_stack["sookshma"], SOOKSHMA_WEIGHT),
        ("prana", dasha_stack["prana"], PRANA_WEIGHT)
    ]
    
    breakdown = {}
    raw_score = 0.0
    
    # Check if Sookshma and Prana are both malefic
    sookshma_planet = dasha_stack["sookshma"]
    prana_planet = dasha_stack["prana"]
    sookshma_is_malefic = (natures.get(sookshma_planet, 0.0) == -1.0) if sookshma_planet else False
    prana_is_malefic = (natures.get(prana_planet, 0.0) == -1.0) if prana_planet else False
    force_avoid = sookshma_is_malefic and prana_is_malefic
    
    # Process Dasha Levels
    for level_name, planet, weight in levels_data:
        if not planet:
            breakdown[level_name] = {"planet": None, "score": 0.0}
            continue
            
        nature = natures.get(planet, 0.0)
        
        # Calculate overlays
        overlay_bonus = 0.0
        
        # House placement overlay
        planet_pos = planet_positions.get(planet)
        if planet_pos:
            sign = planet_pos.get("sign")
            house = get_planet_house(sign, lagna_sign)
            
            if house == 5:
                overlay_bonus += FIFTH_HOUSE_SPECULATION
            elif house == 8:
                overlay_bonus += EIGHTH_HOUSE_VOLATILITY
                
        # Karaka overlay
        if planet == "Rahu":
            overlay_bonus += RAHU_CRYPTO_BOOST
        elif planet == "Mercury":
            overlay_bonus += MERCURY_ANALYSIS_BOOST
        elif planet == "Moon":
            overlay_bonus += MOON_STABILITY_BOOST
            
        net_score = (nature + overlay_bonus) * weight
        raw_score += net_score
        
        breakdown[level_name] = {
            "planet": planet,
            "nature": "benefic" if nature > 0 else ("malefic" if nature < 0 else "neutral"),
            "overlay_bonus": overlay_bonus,
            "weighted_score": net_score
        }
        
    # Process Hora Level
    hora_nature = natures.get(hora_lord, 0.0)
    # Check Hora house placement
    hora_pos = planet_positions.get(hora_lord)
    hora_overlay = 0.0
    if hora_pos:
        sign = hora_pos.get("sign")
        house = get_planet_house(sign, lagna_sign)
        if house == 5:
            hora_overlay += FIFTH_HOUSE_SPECULATION
        elif house == 8:
            hora_overlay += EIGHTH_HOUSE_VOLATILITY
            
    # Karaka overlays for Hora
    if hora_lord == "Rahu":
        hora_overlay += RAHU_CRYPTO_BOOST
    elif hora_lord == "Mercury":
        hora_overlay += MERCURY_ANALYSIS_BOOST
    elif hora_lord == "Moon":
        hora_overlay += MOON_STABILITY_BOOST
        
    hora_score = (hora_nature + hora_overlay) * HORA_WEIGHT
    raw_score += hora_score
    
    breakdown["hora"] = {
        "planet": hora_lord,
        "nature": "benefic" if hora_nature > 0 else ("malefic" if hora_nature < 0 else "neutral"),
        "overlay_bonus": hora_overlay,
        "weighted_score": hora_score
    }
    
    # 5. Normalize raw score to 0 - 100
    # Standard max possible raw score limit is around 15.0
    max_raw_limit = 15.0
    normalized = 50.0 + (raw_score / max_raw_limit) * 50.0
    normalized = max(0.0, min(100.0, normalized))
    
    # 6. Apply hard constraints
    if force_avoid:
        recommendation = "AVOID"
        # Force score below 40.0 threshold
        if normalized >= 40.0:
            normalized = 39.0
        breakdown["hard_rule_triggered"] = "Sookshma & Prana are both malefic -> Forced AVOID"
    else:
        if normalized >= 65.0:
            recommendation = "ENTER"
        elif normalized >= 40.0:
            recommendation = "CAUTION"
        else:
            recommendation = "AVOID"
            
    # 7. Log to database for backtesting audits
    if log_to_db:
        log_entry = TradingSignalLog(
            user_id=user_id,
            timestamp=timestamp,
            dasha_stack=dasha_stack,
            hora_lord=hora_lord,
            score=normalized,
            recommendation=recommendation,
            actual_trade_taken=False,
            actual_result="na"
        )
        db.add(log_entry)
        db.commit()
        
    return {
        "score": round(normalized, 2),
        "recommendation": recommendation,
        "breakdown": breakdown
    }
