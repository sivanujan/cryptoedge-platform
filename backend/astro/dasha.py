import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import DashaPeriod

logger = logging.getLogger(__name__)

# Vimshottari planets in exact order and their total years in the 120-year cycle
VIMSHOTTARI_ORDER = [
    ("Ketu", 7),
    ("Venus", 20),
    ("Sun", 6),
    ("Moon", 10),
    ("Mars", 7),
    ("Rahu", 18),
    ("Jupiter", 16),
    ("Saturn", 19),
    ("Mercury", 17)
]

PLANET_YEARS = {name: years for name, years in VIMSHOTTARI_ORDER}


def get_vimshottari_order_from(start_planet: str):
    """
    Returns the Vimshottari planet order starting from a specific planet.
    """
    idx = -1
    for i, (name, _) in enumerate(VIMSHOTTARI_ORDER):
        if name == start_planet:
            idx = i
            break
            
    if idx == -1:
        raise ValueError(f"Unknown planet: {start_planet}")
        
    return VIMSHOTTARI_ORDER[idx:] + VIMSHOTTARI_ORDER[:idx]


def generate_dasha_tree(db: Session, user_id: int, moon_longitude: float, birth_dt: datetime):
    """
    Generates a full 120-year Vimshottari Dasha tree up to 5 levels deep
    and bulk-saves it to the database.
    """
    logger.info(f"Generating Dasha tree for user {user_id}...")
    
    # 1. Determine starting Nakshatra and Dasha Lord
    nakshatra_size = 360.0 / 27.0
    nak_idx = int((moon_longitude % 360.0) / nakshatra_size)
    if nak_idx >= 27:
        nak_idx = 26
        
    # Standard mapping: Ashwini (index 0) is ruled by Ketu, Bharani by Venus, etc.
    # The VIMSHOTTARI_ORDER starting planet corresponds to (nak_idx % 9)
    start_planet, total_years = VIMSHOTTARI_ORDER[nak_idx % 9]
    
    # Calculate fraction of Nakshatra remaining
    nak_start = nak_idx * nakshatra_size
    elapsed = moon_longitude - nak_start
    fraction_elapsed = elapsed / nakshatra_size
    fraction_remaining = 1.0 - fraction_elapsed
    
    # Calculate end of initial Dasha
    first_dasha_duration_days = total_years * fraction_remaining * 365.25
    first_dasha_end = birth_dt + timedelta(days=first_dasha_duration_days)
    
    # 2. Level 1: Generate all Mahadashas for 120 years
    mahadashas = []
    
    # First Mahadasha (partial)
    mahadashas.append({
        "user_id": user_id,
        "level": "maha",
        "planet": start_planet,
        "start_datetime": birth_dt,
        "end_datetime": first_dasha_end,
        "parent_period_id": None
    })
    
    # Subsequent Mahadashas
    current_start = first_dasha_end
    cycle_order = get_vimshottari_order_from(start_planet)[1:] # Skip the first one as we handled it
    
    # Add rest of the planets to complete the cycle
    for name, years in cycle_order:
        current_end = current_start + timedelta(days=years * 365.25)
        mahadashas.append({
            "user_id": user_id,
            "level": "maha",
            "planet": name,
            "start_datetime": current_start,
            "end_datetime": current_end,
            "parent_period_id": None
        })
        current_start = current_end
        
    # Save Level 1 to DB to get IDs
    db.query(DashaPeriod).filter(DashaPeriod.user_id == user_id).delete()
    db.commit()
    
    # Bulk insert Mahadashas
    db.bulk_insert_mappings(DashaPeriod, mahadashas)
    db.commit()
    
    # Retrieve Mahadashas with database IDs
    db_mahadashas = db.query(DashaPeriod).filter(DashaPeriod.user_id == user_id, DashaPeriod.level == "maha").order_by(DashaPeriod.start_datetime).all()
    
    # 3. Recursively generate levels 2, 3, 4, 5
    levels = ["maha", "antar", "pratyantar", "sookshma", "prana"]
    
    parent_periods = db_mahadashas
    for level_idx in range(1, 5):
        child_level = levels[level_idx]
        child_mappings = []
        
        for parent in parent_periods:
            parent_duration = (parent.end_datetime - parent.start_datetime).total_seconds()
            
            # Sub-periods start with the parent planet and follow the cycle
            sub_order = get_vimshottari_order_from(parent.planet)
            
            sub_start = parent.start_datetime
            for name, years in sub_order:
                # Duration is proportional to planet's years out of 120
                sub_duration_secs = parent_duration * (years / 120.0)
                sub_end = sub_start + timedelta(seconds=sub_duration_secs)
                
                # Cap the end date to the parent's end datetime to avoid rounding drifts
                if sub_end > parent.end_datetime:
                    sub_end = parent.end_datetime
                    
                child_mappings.append({
                    "user_id": user_id,
                    "level": child_level,
                    "planet": name,
                    "start_datetime": sub_start,
                    "end_datetime": sub_end,
                    "parent_period_id": parent.id
                })
                sub_start = sub_end
                
        # Bulk insert child periods
        db.bulk_insert_mappings(DashaPeriod, child_mappings)
        db.commit()
        
        # Load the inserted children to serve as the parents for the next level
        parent_periods = db.query(DashaPeriod).filter(
            DashaPeriod.user_id == user_id, 
            DashaPeriod.level == child_level
        ).order_by(DashaPeriod.start_datetime).all()
        
    logger.info(f"Successfully generated full Vimshottari tree (5 levels) for user {user_id}.")


def get_active_dasha_stack(db: Session, user_id: int, timestamp: datetime):
    """
    Returns the active planet at all 5 levels for any given moment.
    Format: {"maha": str, "antar": str, "pratyantar": str, "sookshma": str, "prana": str}
    """
    stack = {"maha": None, "antar": None, "pratyantar": None, "sookshma": None, "prana": None}
    
    # Query the periods overlapping the timestamp
    active_periods = db.query(DashaPeriod).filter(
        DashaPeriod.user_id == user_id,
        DashaPeriod.start_datetime <= timestamp,
        DashaPeriod.end_datetime >= timestamp
    ).all()
    
    for p in active_periods:
        if p.level in stack:
            stack[p.level] = p.planet
            
    return stack
