import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.connection import init_db, SessionLocal
from database.models import BirthChart, DashaPeriod, TradingSignalLog
from astro.chart import calculate_birth_positions
from astro.dasha import generate_dasha_tree, get_active_dasha_stack
from astro.hora import get_active_hora
from astro.signal_engine import calculate_signal

def main():
    print("1. Initializing database tables...")
    init_db()
    
    db = SessionLocal()
    try:
        user_id = 9999
        dob = "1995-10-15"
        tob = "14:30:00"
        lat = 13.0827   # Chennai
        lon = 80.2707
        tz = "+05:30"
        
        print("\n2. Calculating birth chart positions...")
        birth_data = calculate_birth_positions(dob, tob, lat, lon, tz)
        print("Lagna (Ascendant):", birth_data["ascendant_sign"])
        print("Moon Longitude:", birth_data["planet_positions"]["Moon"]["longitude"])
        print("Moon Nakshatra:", birth_data["nakshatra_data"]["Moon"])
        
        print("\n3. Creating BirthChart DB entry...")
        # Clean existing
        db.query(BirthChart).filter(BirthChart.user_id == user_id).delete()
        db.commit()
        
        chart = BirthChart(
            user_id=user_id,
            dob=dob,
            tob=tob,
            lat=lat,
            long=lon,
            tz=tz,
            ascendant_sign=birth_data["ascendant_sign"],
            planet_positions=birth_data["planet_positions"],
            nakshatra_data=birth_data["nakshatra_data"]
        )
        db.add(chart)
        db.commit()
        print("Stored BirthChart successfully!")
        
        print("\n4. Generating Vimshottari Dasha tree (5 levels deep)...")
        moon_long = birth_data["planet_positions"]["Moon"]["longitude"]
        birth_dt = datetime.strptime(f"{dob} {tob}", "%Y-%m-%d %H:%M:%S")
        generate_dasha_tree(db, user_id, moon_long, birth_dt)
        
        # Verify row counts
        for level in ["maha", "antar", "pratyantar", "sookshma", "prana"]:
            count = db.query(DashaPeriod).filter(DashaPeriod.user_id == user_id, DashaPeriod.level == level).count()
            print(f" - Level {level}: {count} rows")
            
        print("\n5. Testing active Dasha stack lookup for current moment...")
        now = datetime.utcnow()
        stack = get_active_dasha_stack(db, user_id, now)
        print("Active Dasha stack:", stack)
        
        print("\n6. Testing Hora calculation for current moment...")
        hora_info = get_active_hora(now, lat, lon)
        print(f"Hora lord: {hora_info['hora_lord']} (Remaining: {hora_info['time_remaining_seconds']:.1f}s)")
        
        print("\n7. Calculating trading signal score and recommendation...")
        # Clean log first
        db.query(TradingSignalLog).filter(TradingSignalLog.user_id == user_id).delete()
        db.commit()
        
        sig = calculate_signal(db, user_id, now, log_to_db=True)
        print("Score:", sig["score"])
        print("Recommendation:", sig["recommendation"])
        print("Breakdown Keys:", list(sig["breakdown"].keys()))
        
        # Verify log entry
        log_count = db.query(TradingSignalLog).filter(TradingSignalLog.user_id == user_id).count()
        print("Trading Signal Log entries created:", log_count)
        
        print("\nALL ASTROLOGY MODULE TESTS COMPLETED SUCCESSFULLY!")
    finally:
        db.close()

if __name__ == "__main__":
    main()
