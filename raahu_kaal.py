import swisseph as swe
import datetime
import zoneinfo
import calendar

# === CONFIGURATION ===
swe.set_ephe_path(r".")  # adjust to wherever your ephemeris files live

# Location: Delhi
LAT = 28.6139
LON = 77.2090
ELEV = 0  # Elevation in meters

# Timezones
UTC = datetime.timezone.utc
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

# Weekday → which 1/8 of the day is Rahu Kaal (0-based index)
RAAHU_INDEX = {
    0: 1,  # Monday
    1: 6,  # Tuesday
    2: 4,  # Wednesday
    3: 5,  # Thursday
    4: 3,  # Friday
    5: 2,  # Saturday
    6: 7   # Sunday
}

def jd_to_ist(jd: float) -> datetime.datetime:
    y, m, d, h = swe.revjul(jd)
    hr = int(h)
    mn = int((h - hr) * 60)
    sec = int((((h - hr) * 60) - mn) * 60)
    dt_utc = datetime.datetime(y, m, d, hr, mn, sec, tzinfo=UTC)
    return dt_utc.astimezone(IST)

def get_raahu_kaal(date_obj: datetime.date):
    jd0 = swe.julday(date_obj.year, date_obj.month, date_obj.day, 0.0)
    flags_rise = swe.CALC_RISE | swe.BIT_DISC_CENTER
    flags_set = swe.CALC_SET | swe.BIT_DISC_CENTER

    geopos = (LON, LAT, ELEV)

    # Corrected: rsmi as positional, geopos as keyword
    _, rise_t = swe.rise_trans(jd0, swe.SUN, flags_rise, geopos=geopos)
    _, set_t  = swe.rise_trans(jd0, swe.SUN, flags_set, geopos=geopos)
    rise_jd = rise_t[0]
    set_jd = set_t[0]
    sunrise = jd_to_ist(rise_jd)
    sunset = jd_to_ist(set_jd)

    if sunset < sunrise:
        jd1 = swe.julday(date_obj.year, date_obj.month, date_obj.day + 1, 0.0)
        _, set_t = swe.rise_trans(jd1, swe.SUN, flags_set, geopos=geopos)
        set_jd = set_t[0]
        sunset = jd_to_ist(set_jd)

    part = (sunset - sunrise) / 8
    idx = RAAHU_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part

    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

if __name__ == "__main__":
    s = input("Enter date (YYYY-MM-DD), 'all YYYY-MM', or press Enter for today: ").strip()
    if s.startswith('all '):
        _, yyyymm = s.split()
        year, month = map(int, yyyymm.split('-'))
        num_days = calendar.monthrange(year, month)[1]
        for day in range(1, num_days + 1):
            d = datetime.date(year, month, day)
            start_dt, end_dt = get_raahu_kaal(d)
            if start_dt is None or end_dt is None:
                print(f"{d.strftime('%Y-%m-%d')} - Raahu Kaal not found.")
            else:
                print(f"{d.strftime('%A, %d %B %Y')}: {start_dt.strftime('%I:%M %p')} → {end_dt.strftime('%I:%M %p')}")
    else:
        if s:
            try:
                d = datetime.datetime.strptime(s, "%Y-%m-%d").date()
            except ValueError:
                print("Invalid format. Use YYYY-MM-DD.")
                exit(1)
        else:
            d = datetime.date.today()
        start_dt, end_dt = get_raahu_kaal(d)
        if start_dt is None or end_dt is None:
            print("Raahu Kaal does not occur after sunset or could not be calculated.")
        else:
            print(f"Raahu Kaal on {d.strftime('%A, %d %B %Y')} (IST):")
            print(f"  {start_dt.strftime('%I:%M:%S %p')} → {end_dt.strftime('%I:%M:%S %p')}")
