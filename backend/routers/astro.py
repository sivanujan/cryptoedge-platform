import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from database.connection import get_db
from database.models import BirthChart, DashaPeriod
from astro.chart import calculate_birth_positions
from astro.dasha import generate_dasha_tree
from astro.signal_engine import calculate_signal

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/astro", tags=["astrology"])


class BirthChartRequest(BaseModel):
    user_id: int = Field(..., description="Unique user identifier")
    dob: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    tob: str = Field(..., description="Exact time of birth in HH:MM:SS format")
    lat: float = Field(..., description="Latitude of birth location")
    long: float = Field(..., description="Longitude of birth location")
    tz: str = Field(..., description="Timezone offset or name (e.g. '+05:30', 'Asia/Kolkata')")


@router.post("/chart")
def create_chart(req: BirthChartRequest, db: Session = Depends(get_db)):
    """
    Creates a birth chart calculation and stores it in the database.
    Triggers automatic generation of the full 5-level deep Dasha period tree.
    """
    # 1. Parse dates and calculate planetary coordinates
    try:
        birth_data = calculate_birth_positions(req.dob, req.tob, req.lat, req.long, req.tz)
    except Exception as e:
        logger.error(f"Error calculating birth chart: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to calculate birth positions: {e}")
        
    # 2. Add or update BirthChart record
    db_chart = db.query(BirthChart).filter(BirthChart.user_id == req.user_id).first()
    if db_chart:
        db_chart.dob = req.dob
        db_chart.tob = req.tob
        db_chart.lat = req.lat
        db_chart.long = req.long
        db_chart.tz = req.tz
        db_chart.ascendant_sign = birth_data["ascendant_sign"]
        db_chart.planet_positions = birth_data["planet_positions"]
        db_chart.nakshatra_data = birth_data["nakshatra_data"]
    else:
        db_chart = BirthChart(
            user_id=req.user_id,
            dob=req.dob,
            tob=req.tob,
            lat=req.lat,
            long=req.long,
            tz=req.tz,
            ascendant_sign=birth_data["ascendant_sign"],
            planet_positions=birth_data["planet_positions"],
            nakshatra_data=birth_data["nakshatra_data"]
        )
        db.add(db_chart)
        
    db.commit()
    
    # 3. Generate Dasha periods (120 year cycle, 5 levels deep)
    moon_longitude = birth_data["planet_positions"]["Moon"]["longitude"]
    birth_dt = datetime.strptime(f"{req.dob} {req.tob}", "%Y-%m-%d %H:%M:%S")
    
    try:
        generate_dasha_tree(db, req.user_id, moon_longitude, birth_dt)
    except Exception as e:
        logger.error(f"Error generating dasha periods: {e}")
        raise HTTPException(status_code=500, detail=f"Birth chart created, but Dasha tree generation failed: {e}")
        
    return {
        "status": "success",
        "message": "Birth chart and Dasha tree successfully created/updated",
        "data": {
            "ascendant_sign": birth_data["ascendant_sign"],
            "planet_positions": birth_data["planet_positions"],
            "nakshatra_data": birth_data["nakshatra_data"]
        }
    }


@router.get("/dasha/{user_id}")
def get_dasha_tree(
    user_id: int, 
    start: str = None, 
    end: str = None, 
    db: Session = Depends(get_db)
):
    """
    Returns the user's Vimshottari Dasha tree.
    If 'start' and 'end' ISO datetimes are specified, returns the detailed 5-level stack
    overlapping that window. Otherwise, returns the tree down to the 'pratyantar' (Level 3) level.
    """
    # Verify birth chart exists
    chart = db.query(BirthChart).filter(BirthChart.user_id == user_id).first()
    if not chart:
        raise HTTPException(status_code=404, detail="Birth chart not found for user")
        
    if start or end:
        try:
            start_dt = datetime.fromisoformat(start) if start else datetime.utcnow() - timedelta(days=7)
            end_dt = datetime.fromisoformat(end) if end else start_dt + timedelta(days=7)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)")
            
        # Fetch detailed overlapping periods
        periods = db.query(DashaPeriod).filter(
            DashaPeriod.user_id == user_id,
            DashaPeriod.start_datetime <= end_dt,
            DashaPeriod.end_datetime >= start_dt
        ).order_by(DashaPeriod.level, DashaPeriod.start_datetime).all()
        
        return {
            "user_id": user_id,
            "mode": "time_window",
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "periods": [
                {
                    "id": p.id,
                    "level": p.level,
                    "planet": p.planet,
                    "start": p.start_datetime.isoformat(),
                    "end": p.end_datetime.isoformat(),
                    "parent_id": p.parent_period_id
                } for p in periods
            ]
        }
        
    # Standard: Load up to Level 3 (Pratyantar)
    periods = db.query(DashaPeriod).filter(
        DashaPeriod.user_id == user_id,
        DashaPeriod.level.in_(["maha", "antar", "pratyantar"])
    ).order_by(DashaPeriod.start_datetime).all()
    
    # Group by levels
    maha_periods = [p for p in periods if p.level == "maha"]
    antar_periods = [p for p in periods if p.level == "antar"]
    pratyantar_periods = [p for p in periods if p.level == "pratyantar"]
    
    # Build tree
    tree = []
    for m in maha_periods:
        m_node = {
            "id": m.id,
            "level": "maha",
            "planet": m.planet,
            "start": m.start_datetime.isoformat(),
            "end": m.end_datetime.isoformat(),
            "children": []
        }
        
        # Add Antar
        m_antars = [a for a in antar_periods if a.parent_period_id == m.id]
        for a in m_antars:
            a_node = {
                "id": a.id,
                "level": "antar",
                "planet": a.planet,
                "start": a.start_datetime.isoformat(),
                "end": a.end_datetime.isoformat(),
                "children": []
            }
            
            # Add Pratyantar
            a_prats = [p for p in pratyantar_periods if p.parent_period_id == a.id]
            for p in a_prats:
                p_node = {
                    "id": p.id,
                    "level": "pratyantar",
                    "planet": p.planet,
                    "start": p.start_datetime.isoformat(),
                    "end": p.end_datetime.isoformat()
                }
                a_node["children"].append(p_node)
                
            m_node["children"].append(a_node)
            
        tree.append(m_node)
        
    return {
        "user_id": user_id,
        "mode": "tree_up_to_pratyantar",
        "dasha_tree": tree
    }


@router.get("/signal/{user_id}")
def get_signal(
    user_id: int, 
    timestamp: str = None, 
    db: Session = Depends(get_db)
):
    """
    Returns the real-time Vedic astrology trading signal score.
    """
    if timestamp:
        try:
            if 'T' in timestamp:
                dt = datetime.fromisoformat(timestamp)
            else:
                dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            raise HTTPException(
                status_code=400, 
                detail="Invalid timestamp format. Use ISO format or YYYY-MM-DD HH:MM:SS"
            )
    else:
        dt = datetime.utcnow()
        
    try:
        signal_data = calculate_signal(db, user_id, dt)
        return {"status": "success", "timestamp": dt.isoformat(), **signal_data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Signal calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal signal calculation error: {e}")


@router.get("/signal/{user_id}/live")
def get_live_signal(user_id: int, db: Session = Depends(get_db)):
    """
    Returns the current moment Vedic astrology trading signal.
    """
    dt = datetime.utcnow()
    try:
        signal_data = calculate_signal(db, user_id, dt)
        return {"status": "success", "timestamp": dt.isoformat(), **signal_data}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Live signal calculation error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal signal calculation error: {e}")
