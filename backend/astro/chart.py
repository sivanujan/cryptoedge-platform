import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# Check if swisseph is available
try:
    import swisseph as swe
    SWISSEPH_AVAILABLE = True
    logger.info("pyswisseph imported successfully for astronomical calculations.")
except ImportError:
    SWISSEPH_AVAILABLE = False
    logger.warning("pyswisseph not installed or compiler build tools missing. Using fallback astronomical models.")

ZODIAC_SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

NAKSHATRAS = [
    {"name": "Ashwini", "ruler": "Ketu"},
    {"name": "Bharani", "ruler": "Venus"},
    {"name": "Krittika", "ruler": "Sun"},
    {"name": "Rohini", "ruler": "Moon"},
    {"name": "Mrigashira", "ruler": "Mars"},
    {"name": "Ardra", "ruler": "Rahu"},
    {"name": "Punarvasu", "ruler": "Jupiter"},
    {"name": "Pushya", "ruler": "Saturn"},
    {"name": "Ashlesha", "ruler": "Mercury"},
    {"name": "Magha", "ruler": "Ketu"},
    {"name": "Purva Phalguni", "ruler": "Venus"},
    {"name": "Uttara Phalguni", "ruler": "Sun"},
    {"name": "Hasta", "ruler": "Moon"},
    {"name": "Chitra", "ruler": "Mars"},
    {"name": "Swati", "ruler": "Rahu"},
    {"name": "Vishakha", "ruler": "Jupiter"},
    {"name": "Anuradha", "ruler": "Saturn"},
    {"name": "Jyeshtha", "ruler": "Mercury"},
    {"name": "Mula", "ruler": "Ketu"},
    {"name": "Purva Ashadha", "ruler": "Venus"},
    {"name": "Uttara Ashadha", "ruler": "Sun"},
    {"name": "Shravana", "ruler": "Moon"},
    {"name": "Dhanishta", "ruler": "Mars"},
    {"name": "Shatabhisha", "ruler": "Rahu"},
    {"name": "Purva Bhadrapada", "ruler": "Jupiter"},
    {"name": "Uttara Bhadrapada", "ruler": "Saturn"},
    {"name": "Revati", "ruler": "Mercury"}
]


def get_nakshatra_info(longitude: float):
    """
    Returns Nakshatra name, ruler, and Pada (1-4) for a given sidereal longitude.
    """
    long_norm = longitude % 360.0
    nakshatra_size = 360.0 / 27.0  # 13.333333 degrees
    nak_idx = int(long_norm / nakshatra_size)
    if nak_idx >= 27:
        nak_idx = 26
        
    pada_size = nakshatra_size / 4.0  # 3.333333 degrees
    fractional_part = long_norm - (nak_idx * nakshatra_size)
    pada = int(fractional_part / pada_size) + 1
    if pada > 4:
        pada = 4
        
    info = NAKSHATRAS[nak_idx]
    return {
        "nakshatra": info["name"],
        "ruler": info["ruler"],
        "pada": pada,
        "nakshatra_index": nak_idx
    }


def parse_tz_offset(tz_str: str) -> float:
    """
    Parses timezone offset string like '+05:30', '-08:00', or raw float/int string to offset in hours.
    """
    tz_str = tz_str.strip()
    if not tz_str:
        return 0.0
    
    # Check if format is +HH:MM or -HH:MM
    if (tz_str.startswith('+') or tz_str.startswith('-')) and ':' in tz_str:
        sign = 1 if tz_str.startswith('+') else -1
        parts = tz_str[1:].split(':')
        hours = float(parts[0])
        minutes = float(parts[1]) if len(parts) > 1 else 0.0
        return sign * (hours + minutes / 60.0)
    
    try:
        return float(tz_str)
    except ValueError:
        # Check standard common timezones fallback
        if "IST" in tz_str:
            return 5.5
        elif "EST" in tz_str:
            return -5.0
        elif "UTC" in tz_str or "GMT" in tz_str:
            return 0.0
        return 0.0


def calculate_julian_day_utc(dob: str, tob: str, tz_str: str):
    """
    Converts Local DOB, TOB, and TZ to UTC datetime and returns Julian Day.
    """
    dt_local = datetime.strptime(f"{dob} {tob}", "%Y-%m-%d %H:%M:%S")
    offset = parse_tz_offset(tz_str)
    dt_utc = dt_local - timedelta(hours=offset)
    
    # Calculate Julian Day
    year, month, day = dt_utc.year, dt_utc.month, dt_utc.day
    hour_fraction = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    
    if SWISSEPH_AVAILABLE:
        return swe.julday(year, month, day, hour_fraction), dt_utc
    else:
        # Manual Julian Day calculation
        a = (14 - month) // 12
        y = year + 4800 - a
        m = month + 12 * a - 3
        jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045
        jd = jdn + (hour_fraction - 12.0) / 24.0
        return jd, dt_utc


def get_sidereal_ayanamsa(jd: float, year: int) -> float:
    """
    Returns Lahiri Ayanamsa value for JDay.
    """
    if SWISSEPH_AVAILABLE:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        return swe.get_ayanamsa(jd)
    else:
        # Lahiri ayanamsa approximation:
        # J2000.0 (Jan 1, 2000 12:00) ayanamsa was approx 23.85 degrees.
        # It changes by approx 50.3 arcseconds (0.01397 degrees) per year.
        return 23.85 + (year - 2000) * 0.01397


def calculate_birth_positions(dob: str, tob: str, lat: float, long: float, tz_str: str):
    """
    Calculates sidereal planetary longitudes, Ascendant, Nakshatras, and Padas.
    """
    jd, dt_utc = calculate_julian_day_utc(dob, tob, tz_str)
    ayanamsa = get_sidereal_ayanamsa(jd, dt_utc.year)
    
    planet_positions = {}
    nakshatra_data = {}
    
    if SWISSEPH_AVAILABLE:
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        
        # Define planets to fetch
        planets_map = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mercury": swe.MERCURY,
            "Venus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE
        }
        
        for name, pid in planets_map.items():
            res = swe.calc_ut(jd, pid, swe.FLG_SIDEREAL)
            longitude = res[0] % 360.0
            
            sign_idx = int(longitude / 30.0)
            sign_deg = longitude % 30.0
            
            planet_positions[name] = {
                "longitude": longitude,
                "sign": ZODIAC_SIGNS[sign_idx],
                "degrees": sign_deg
            }
            
            nakshatra_data[name] = get_nakshatra_info(longitude)
            
        # Ketu is exactly 180 degrees opposite of Rahu
        rahu_long = planet_positions["Rahu"]["longitude"]
        ketu_long = (rahu_long + 180.0) % 360.0
        sign_idx = int(ketu_long / 30.0)
        planet_positions["Ketu"] = {
            "longitude": ketu_long,
            "sign": ZODIAC_SIGNS[sign_idx],
            "degrees": ketu_long % 30.0
        }
        nakshatra_data["Ketu"] = get_nakshatra_info(ketu_long)
        
        # Calculate Ascendant (Lagna)
        cusps, ascmc = swe.houses(jd, lat, long, b'A')
        # swe.houses returns tropical cusps, we must subtract ayanamsa to get sidereal
        asc_sidereal = (ascmc[0] - ayanamsa) % 360.0
        
    else:
        # Fallback Keplerian Kepler orbit approximate model
        d = jd - 2451545.0  # Days since J2000.0
        
        # Planetary orbital values at J2000 (mean longitude + daily motion)
        # Note: These values approximate sidereal placements after ayanamsa correction
        mean_elements = {
            "Sun": {"L": 280.46, "d": 0.9856474},
            "Moon": {"L": 218.316, "d": 13.176396},
            "Mercury": {"L": 252.25, "d": 4.092334},
            "Venus": {"L": 181.98, "d": 1.602130},
            "Mars": {"L": 355.17, "d": 0.524021},
            "Jupiter": {"L": 34.35, "d": 0.083085},
            "Saturn": {"L": 50.07, "d": 0.033444},
            "Rahu": {"L": 125.12, "d": -0.052953}  # Mean Node moves retrograde
        }
        
        for name, el in mean_elements.items():
            long_tropical = (el["L"] + el["d"] * d) % 360.0
            longitude = (long_tropical - ayanamsa) % 360.0
            
            sign_idx = int(longitude / 30.0)
            sign_deg = longitude % 30.0
            
            planet_positions[name] = {
                "longitude": longitude,
                "sign": ZODIAC_SIGNS[sign_idx],
                "degrees": sign_deg
            }
            
            nakshatra_data[name] = get_nakshatra_info(longitude)
            
        # Ketu opposite of Rahu
        rahu_long = planet_positions["Rahu"]["longitude"]
        ketu_long = (rahu_long + 180.0) % 360.0
        sign_idx = int(ketu_long / 30.0)
        planet_positions["Ketu"] = {
            "longitude": ketu_long,
            "sign": ZODIAC_SIGNS[sign_idx],
            "degrees": ketu_long % 30.0
        }
        nakshatra_data["Ketu"] = get_nakshatra_info(ketu_long)
        
        # Lagna calculation
        # GMST Sidereal Time at Greenwich
        gmst = (18.697374558 + 24.06570982441908 * d) % 24.0
        lst = (gmst + long / 15.0) % 24.0
        asc_tropical = (lst * 15.0 + 90.0) % 360.0
        asc_sidereal = (asc_tropical - ayanamsa) % 360.0

    ascendant_sign = ZODIAC_SIGNS[int(asc_sidereal / 30.0)]
    planet_positions["Ascendant"] = {
        "longitude": asc_sidereal,
        "sign": ascendant_sign,
        "degrees": asc_sidereal % 30.0
    }
    
    return {
        "ascendant_sign": ascendant_sign,
        "planet_positions": planet_positions,
        "nakshatra_data": nakshatra_data
    }
