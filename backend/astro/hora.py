import logging
from datetime import datetime, timedelta, timezone
from astral import Observer
from astral.sun import sun

logger = logging.getLogger(__name__)

# Chaldean planetary sequence
CHALDEAN_ORDER = ["Saturn", "Jupiter", "Mars", "Sun", "Venus", "Mercury", "Moon"]

# Maps Python's weekday() (0=Monday, 6=Sunday) to starting Chaldean planet index
WEEKDAY_TO_CHALDEAN_START = {
    0: 6,  # Monday -> Moon
    1: 2,  # Tuesday -> Mars
    2: 5,  # Wednesday -> Mercury
    3: 1,  # Thursday -> Jupiter
    4: 4,  # Friday -> Venus
    5: 0,  # Saturday -> Saturn
    6: 3   # Sunday -> Sun
}


def get_active_hora(dt: datetime, lat: float, long: float):
    """
    Calculates the active Hora lord and the time remaining (in seconds) in the current Hora.
    Input: dt must be timezone-aware or UTC. If naive, we assume UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
        
    observer = Observer(latitude=lat, longitude=long, elevation=0.0)
    target_date = dt.date()
    
    # 1. Fetch sunrise and sunset for target_date
    try:
        s_today = sun(observer, date=target_date)
        sunrise_today = s_today["sunrise"]
        sunset_today = s_today["sunset"]
    except Exception as e:
        logger.error(f"Error calculating sun times for {target_date}: {e}")
        # Default/Fallback Sunrise/Sunset to 6:00 AM and 6:00 PM UTC
        sunrise_today = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=6)
        sunset_today = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18)
        
    # 2. Check if the time is before sunrise of target_date.
    # In Vedic astrology, the day starts at sunrise, so before sunrise belongs to the previous day's night.
    if dt < sunrise_today:
        target_date = target_date - timedelta(days=1)
        try:
            s_today = sun(observer, date=target_date)
            sunrise_today = s_today["sunrise"]
            sunset_today = s_today["sunset"]
        except Exception as e:
            logger.error(f"Error calculating fallback sun times: {e}")
            sunrise_today = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=6)
            sunset_today = datetime.combine(target_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=18)
            
    # Calculate sunrise for the next day
    next_date = target_date + timedelta(days=1)
    try:
        s_next = sun(observer, date=next_date)
        sunrise_next = s_next["sunrise"]
    except Exception as e:
        sunrise_next = datetime.combine(next_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=6)

    # 3. Determine if Day or Night Hora
    weekday = target_date.weekday()
    start_idx = WEEKDAY_TO_CHALDEAN_START[weekday]
    
    if dt < sunset_today:
        # Day Hora
        day_duration = (sunset_today - sunrise_today).total_seconds()
        seg_duration = day_duration / 12.0
        
        elapsed_sec = (dt - sunrise_today).total_seconds()
        seg_idx = int(elapsed_sec / seg_duration)
        if seg_idx >= 12:
            seg_idx = 11
            
        lord = CHALDEAN_ORDER[(start_idx + seg_idx) % 7]
        remaining = seg_duration - (elapsed_sec % seg_duration)
        
        # Calculate bounds
        start_time = sunrise_today + timedelta(seconds=seg_idx * seg_duration)
        end_time = start_time + timedelta(seconds=seg_duration)
        
    else:
        # Night Hora
        night_duration = (sunrise_next - sunset_today).total_seconds()
        seg_duration = night_duration / 12.0
        
        elapsed_sec = (dt - sunset_today).total_seconds()
        seg_idx = int(elapsed_sec / seg_duration)
        if seg_idx >= 12:
            seg_idx = 11
            
        # Night hours start immediately after the 12th day hour (so we add 12 to the index)
        lord = CHALDEAN_ORDER[(start_idx + 12 + seg_idx) % 7]
        remaining = seg_duration - (elapsed_sec % seg_duration)
        
        # Calculate bounds
        start_time = sunset_today + timedelta(seconds=seg_idx * seg_duration)
        end_time = start_time + timedelta(seconds=seg_duration)

    return {
        "hora_lord": lord,
        "time_remaining_seconds": remaining,
        "start_time": start_time,
        "end_time": end_time
    }
