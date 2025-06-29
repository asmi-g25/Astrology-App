import swisseph as swe
import datetime, zoneinfo

# Point to your exact ephe folder (the one with se1…se9)
ephe_dir = r"C:\Users\asmi0\Downloads\swisseph-master\swisseph-master\ephe"
swe.set_ephe_path(ephe_dir)
swe.set_sid_mode(swe.SIDM_LAHIRI)

# Helper exactly as in both scripts:
def get_nakshatra(jd):
    moon_long = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0]
    return int(moon_long // (360 / 27))

def find_transition_jd(jd_start, get_value_func):
    current_val = get_value_func(jd_start)
    lower = jd_start
    upper = jd_start + 2
    while upper - lower > 1/86400:
        mid = (lower + upper) / 2
        if get_value_func(mid) != current_val:
            upper = mid
        else:
            lower = mid
    return upper

# Pick any date you know is near a nakṣatra boundary. E.g. June 5, 2025 00:00 UTC:
tz = zoneinfo.ZoneInfo("Asia/Kolkata")
start_date = datetime.datetime(2025, 6, 5, 0, 0, tzinfo=tz)
jd_start = swe.julday(start_date.year, start_date.month, start_date.day, 0)

# Step forward until nakṣatra changes:
jd0 = start_date.hour/24  + start_date.minute/(24*60)
curr_jd = swe.julday(2025, 6, 5, 0.0)
initial_index = get_nakshatra(curr_jd)
next_change_jd = find_transition_jd(curr_jd + 1e-6, get_nakshatra)
boundary_dt = datetime.datetime(*swe.revjul(next_change_jd)[:3], tzinfo=zoneinfo.ZoneInfo("UTC")).astimezone(tz)

print("June 05 2025, JD start:", curr_jd, "nakṣatra index:", initial_index)
print("Next boundary at (Kolkata time):", boundary_dt.strftime("%b %d %I:%M %p"))
