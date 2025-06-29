"""
Astrology Time Windows Module
- Choghadiya
- Raahu Kaal
- Gulika Kaal
- Yamaganda Kaal

All functions use Swiss Ephemeris-based sunrise/sunset logic as in raahu_kaal.py/app.py.
"""
import datetime
import logging
import swisseph as swe
import zoneinfo

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = datetime.timezone.utc

# Traditional Choghadiya tables (fixed for each weekday)
CHOGHADIYA_DAY_TABLE = {
    0: ["Udveg", "Char", "Labh", "Amrit", "Kaal", "Shubh", "Rog"],      # Sunday
    1: ["Amrit", "Rog", "Kaal", "Shubh", "Char", "Labh", "Udveg"],      # Monday
    2: ["Rog", "Labh", "Shubh", "Char", "Amrit", "Kaal", "Udveg"],      # Tuesday
    3: ["Labh", "Shubh", "Char", "Amrit", "Rog", "Kaal", "Udveg"],      # Wednesday
    4: ["Shubh", "Char", "Amrit", "Rog", "Labh", "Kaal", "Udveg"],      # Thursday
    5: ["Char", "Amrit", "Rog", "Labh", "Shubh", "Kaal", "Udveg"],      # Friday
    6: ["Kaal", "Shubh", "Labh", "Amrit", "Char", "Rog", "Udveg"],      # Saturday
}
CHOGHADIYA_NIGHT_TABLE = {
    0: ["Shubh", "Amrit", "Char", "Rog", "Kaal", "Labh", "Udveg"],      # Sunday
    1: ["Rog", "Kaal", "Labh", "Shubh", "Amrit", "Char", "Udveg"],      # Monday
    2: ["Labh", "Shubh", "Amrit", "Char", "Rog", "Kaal", "Udveg"],      # Tuesday
    3: ["Amrit", "Char", "Rog", "Kaal", "Labh", "Shubh", "Udveg"],      # Wednesday
    4: ["Char", "Rog", "Kaal", "Labh", "Shubh", "Amrit", "Udveg"],      # Thursday
    5: ["Kaal", "Labh", "Shubh", "Amrit", "Char", "Rog", "Udveg"],      # Friday
    6: ["Labh", "Shubh", "Amrit", "Char", "Rog", "Kaal", "Udveg"],      # Saturday
}
CHOGHADIYA_QUALITY = {
    "Amrit": "Good",
    "Shubh": "Good",
    "Labh": "Good",
    "Char": "Neutral",
    "Rog": "Bad",
    "Kaal": "Bad",
    "Udveg": "Bad",
}

# Raahu, Gulika, Yamaganda segment indices for each weekday (0=Monday, 6=Sunday)
RAAHU_INDEX = {0: 1, 1: 6, 2: 4, 3: 5, 4: 3, 5: 2, 6: 7}
GULIKA_INDEX = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0, 6: 6}
YAMAGANDA_INDEX = {0: 3, 1: 2, 2: 1, 3: 0, 4: 6, 5: 5, 6: 4}


def jd_to_ist(jd: float) -> datetime.datetime:
    y, m, d, h = swe.revjul(jd)
    hr = int(h)
    mn = int((h - hr) * 60)
    sec = int((((h - hr) * 60) - mn) * 60)
    dt_utc = datetime.datetime(y, m, d, hr, mn, sec, tzinfo=UTC)
    return dt_utc.astimezone(IST)

def get_sunrise_sunset(date_obj, latitude, longitude):
    jd0 = swe.julday(date_obj.year, date_obj.month, date_obj.day, 0.0)
    flags_rise = swe.CALC_RISE | swe.BIT_DISC_CENTER
    flags_set = swe.CALC_SET | swe.BIT_DISC_CENTER
    geopos = (longitude, latitude, 0)
    try:
        _, rise_t = swe.rise_trans(jd0, swe.SUN, flags_rise, geopos=geopos)
        _, set_t = swe.rise_trans(jd0, swe.SUN, flags_set, geopos=geopos)
        sunrise = jd_to_ist(rise_t[0])
        sunset = jd_to_ist(set_t[0])
        if sunset < sunrise:
            jd1 = swe.julday(date_obj.year, date_obj.month, date_obj.day + 1, 0.0)
            _, set_t = swe.rise_trans(jd1, swe.SUN, flags_set, geopos=geopos)
            sunset = jd_to_ist(set_t[0])
        return sunrise, sunset
    except Exception as e:
        logging.error(f"Error in get_sunrise_sunset: {e}")
        return None, None

def get_raahu_kaal(date_obj, latitude=28.6139, longitude=77.2090):
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    if not sunrise or not sunset:
        return None, None
    part = (sunset - sunrise) / 8
    idx = RAAHU_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part
    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

def get_gulika_kaal(date_obj, latitude=28.6139, longitude=77.2090):
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    if not sunrise or not sunset:
        return None, None
    part = (sunset - sunrise) / 8
    idx = GULIKA_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part
    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

def get_yamaganda_kaal(date_obj, latitude=28.6139, longitude=77.2090):
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    if not sunrise or not sunset:
        return None, None
    part = (sunset - sunrise) / 8
    idx = YAMAGANDA_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part
    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

def get_choghadiya(date_obj, latitude=28.6139, longitude=77.2090):
    """Return Choghadiya periods for day and night using traditional fixed table, with correct weekday mapping."""
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    if not sunrise or not sunset:
        return []
    next_sunrise, _ = get_sunrise_sunset(date_obj + datetime.timedelta(days=1), latitude, longitude)
    day_len = (sunset - sunrise).total_seconds()
    night_len = (next_sunrise - sunset).total_seconds()
    choghadiya = []
    # Map Python weekday (Mon=0..Sun=6) to Choghadiya table (Sun=0..Sat=6)
    weekday = (date_obj.weekday() + 1) % 7
    # Day Choghadiya (fixed sequence)
    for i in range(7):
        start = sunrise + datetime.timedelta(seconds=i * day_len / 7)
        end = sunrise + datetime.timedelta(seconds=(i + 1) * day_len / 7)
        name = CHOGHADIYA_DAY_TABLE[weekday][i]
        quality = CHOGHADIYA_QUALITY[name]
        choghadiya.append({
            "type": "Day",
            "index": i + 1,
            "name": name,
            "quality": quality,
            "start": start,
            "end": end
        })
    # Night Choghadiya (fixed sequence)
    for i in range(7):
        start = sunset + datetime.timedelta(seconds=i * night_len / 7)
        end = sunset + datetime.timedelta(seconds=(i + 1) * night_len / 7)
        name = CHOGHADIYA_NIGHT_TABLE[weekday][i]
        quality = CHOGHADIYA_QUALITY[name]
        choghadiya.append({
            "type": "Night",
            "index": i + 1,
            "name": name,
            "quality": quality,
            "start": start,
            "end": end
        })
    return choghadiya

def print_kaal(label, start, end):
    if start is None or end is None:
        print(f"{label}: Not found or does not occur after sunset.")
    else:
        print(f"{label}: {start.strftime('%I:%M:%S %p')} → {end.strftime('%I:%M:%S %p')}")

def print_choghadiya(choghadiya):
    print("--- Choghadiya ---")
    for c in choghadiya:
        start = c['start'].strftime('%H:%M:%S')
        end = c['end'].strftime('%H:%M:%S')
        print(f"{c['type']:4s} {c['index']:2d}. {c['name']} ({c['quality']}): {start} - {end}")

# Example usage (for testing):
if __name__ == "__main__":
    test_date = datetime.date(2025, 6, 29)
    lat, lon = 28.5355, 77.3910
    choghadiya = get_choghadiya(test_date, lat, lon)
    raahu_start, raahu_end = get_raahu_kaal(test_date, lat, lon)
    gulika_start, gulika_end = get_gulika_kaal(test_date, lat, lon)
    yamaganda_start, yamaganda_end = get_yamaganda_kaal(test_date, lat, lon)
    print_choghadiya(choghadiya)
    print()
    print_kaal("Raahu Kaal", raahu_start, raahu_end)
    print_kaal("Gulika Kaal", gulika_start, gulika_end)
    print_kaal("Yamaganda Kaal", yamaganda_start, yamaganda_end)
