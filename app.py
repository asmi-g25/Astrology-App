import os
import logging
import swisseph as swe
import datetime
import zoneinfo
from collections import defaultdict
import calendar


from flask import Flask, render_template, request, redirect, url_for, flash, make_response, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from werkzeug.middleware.proxy_fix import ProxyFix

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO

# For PNG generation
from PIL import Image, ImageDraw, ImageFont

# For automatic timezone detection
from timezonefinder import TimezoneFinder

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# === CONFIGURATION ===
# Use relative path from your project root
ephe_path = os.path.join(os.path.dirname(__file__), "ephe")
swe.set_ephe_path(ephe_path)
swe.set_sid_mode(swe.SIDM_LAHIRI)  # Lahiri (Sidereal) zodiac

# === TIMEZONE ===
delhi_tz = zoneinfo.ZoneInfo("Asia/Kolkata")

# Initialize TimezoneFinder
tf = TimezoneFinder()

# ─── SANITY CHECK ───
# Compute Moon's sidereal longitude at 2025-06-01 00:00 UTC and log it:
jd_test = swe.julday(2025, 6, 1, 0.0)
moon_long = swe.calc_ut(jd_test, swe.MOON, swe.FLG_SIDEREAL)[0][0]
logging.info(f"[SANITY] Moon sidereal longitude on 2025-06-01 00:00 UTC = {moon_long:.6f}°")
# ─────────────────────

# === NAMES & TABLES ===
nakshatras = [
    "Ashwini", "Bharani", "Krittika", "Rohini", "Mrigashirsha", "Ardra",
    "Punarvasu", "Pushya", "Ashlesha", "Magha", "Purva Phalguni", "Uttara Phalguni",
    "Hasta", "Chitra", "Swati", "Vishakha", "Anuradha", "Jyeshtha",
    "Mula", "Purva Ashadha", "Uttara Ashadha", "Shravana", "Dhanishta",
    "Shatabhisha", "Purva Bhadrapada", "Uttara Bhadrapada", "Revati"
]

tithi_names = [
    "Pratipada", "Dvitiya", "Tritiya", "Chaturthi", "Panchami", "Shashthi",
    "Saptami", "Ashtami", "Navami", "Dashami", "Ekadashi", "Dwadashi",
    "Trayodashi", "Chaturdashi", "Purnima"
]

rashis = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"
]

tara_names = [
    "Janma Tara", "Sampat Tara", "Vipat Tara", "Kshema Tara", "Pratyari Tara",
    "Sadhaka Tara", "Vadha Tara", "Mitra Tara", "Atimitra Tara"
]

tara_meanings = {
    "Janma Tara": "Sensitive / Neutral",
    "Sampat Tara": "Wealth / Favorable",
    "Vipat Tara": "Obstacles / Caution",
    "Kshema Tara": "Welfare / Good",
    "Pratyari Tara": "Obstruction / Avoid",
    "Sadhaka Tara": "Success / Best",
    "Vadha Tara": "Destructive / Avoid",
    "Mitra Tara": "Friendly / Supportive",
    "Atimitra Tara": "Very Auspicious"
}

# === NUMEROLOGY MAPPINGS ===
pytha_map = {
    "A": 1, "J": 1, "S": 1,
    "B": 2, "K": 2, "T": 2,
    "C": 3, "L": 3, "U": 3,
    "D": 4, "M": 4, "V": 4,
    "E": 5, "N": 5, "W": 5,
    "F": 6, "O": 6, "X": 6,
    "G": 7, "P": 7, "Y": 7,
    "H": 8, "Q": 8, "Z": 8,
    "I": 9, "R": 9
}

chaldean_map = {
    "A": 1, "I": 1, "J": 1, "Q": 1, "Y": 1,
    "B": 2, "K": 2, "R": 2,
    "C": 3, "G": 3, "L": 3, "S": 3,
    "D": 4, "M": 4, "T": 4,
    "E": 5, "H": 5, "N": 5, "X": 5,
    "U": 6, "V": 6, "W": 6,
    "O": 7, "Z": 7,
    "F": 8, "P": 8
}

# === DATABASE SETUP ===
class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

# Create the app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "fallback-secret-key-for-development")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///astrology.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Initialize the app with the extension
db.init_app(app)

# === DATABASE MODELS ===
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    birth_date = db.Column(db.DateTime, nullable=False)
    birth_time = db.Column(db.String(20), nullable=False)  # Store as HH:MM:SS
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    
    # Location data
    birth_city = db.Column(db.String(100), default="Delhi")
    birth_country = db.Column(db.String(100), default="India")
    birth_latitude = db.Column(db.Float, default=28.6139)
    birth_longitude = db.Column(db.Float, default=77.2090)
    birth_timezone = db.Column(db.String(50), default="Asia/Kolkata")
    
    # Numerology data
    pythagorean_expression = db.Column(db.Integer)
    chaldean_expression = db.Column(db.Integer)
    driver_number = db.Column(db.Integer)
    conductor_number = db.Column(db.Integer)
    
    # Birth chart data
    sun_longitude = db.Column(db.Float)
    moon_longitude = db.Column(db.Float)
    ascendant = db.Column(db.Float)
    birth_nakshatra = db.Column(db.String(50))
    birth_tithi = db.Column(db.String(50))
    
    # Remarks field
    remarks = db.Column(db.Text)
    
    def __repr__(self):
        return f'<User {self.full_name}>'
    
    def get_birth_datetime_local(self):
        """Return birth datetime in user's birth timezone"""
        birth_dt = datetime.datetime.combine(self.birth_date.date(), 
                                          datetime.datetime.strptime(self.birth_time, "%H:%M:%S").time())
        user_tz = zoneinfo.ZoneInfo(self.birth_timezone)
        return birth_dt.replace(tzinfo=user_tz)

class BirthChart(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Planetary positions (in degrees)
    sun_position = db.Column(db.Float)
    moon_position = db.Column(db.Float)
    mercury_position = db.Column(db.Float)
    venus_position = db.Column(db.Float)
    mars_position = db.Column(db.Float)
    jupiter_position = db.Column(db.Float)
    saturn_position = db.Column(db.Float)
    rahu_position = db.Column(db.Float)
    ketu_position = db.Column(db.Float)
    
    # House placements
    sun_house = db.Column(db.Integer)
    moon_house = db.Column(db.Integer)
    mercury_house = db.Column(db.Integer)
    venus_house = db.Column(db.Integer)
    mars_house = db.Column(db.Integer)
    jupiter_house = db.Column(db.Integer)
    saturn_house = db.Column(db.Integer)
    rahu_house = db.Column(db.Integer)
    ketu_house = db.Column(db.Integer)
    
    # Ascendant and house information
    ascendant_degree = db.Column(db.Float)
    ascendant_sign = db.Column(db.String(20))
    house2_sign = db.Column(db.String(20))
    house11_sign = db.Column(db.String(20))
    
    user = db.relationship('User', backref=db.backref('birth_charts', lazy=True))

# === UTILITY FUNCTIONS ===
def digital_root(n: int) -> int:
    """Repeatedly sum the digits of n until a single digit remains (1–9)."""
    while n > 9:
        n = sum(int(d) for d in str(n))
    return n

def numerology_name_number(name: str, mapping: dict) -> int:
    """Calculate numerology number from name using given mapping."""
    total = 0
    for ch in name.upper():
        if ch in mapping:
            total += mapping[ch]
    return digital_root(total)

def life_path_number_from_date(dt: datetime.datetime) -> int:
    """Calculate life path number from birth date."""
    s = dt.strftime("%Y%m%d")
    total = sum(int(ch) for ch in s)
    return digital_root(total)

def get_tara_relation(birth_nak_index, day_nak_index):
    """Get Tara relation between birth nakshatra and daily nakshatra."""
    offset = (day_nak_index - birth_nak_index) % 9
    tara = tara_names[offset]
    return tara, tara_meanings[tara]

def jd_to_datetime(jd):
    """Convert Julian Day to timezone-aware datetime in Asia/Kolkata."""
    y, m, d, h = swe.revjul(jd)
    minute = (h % 1) * 60
    second = (minute % 1) * 60
    dt = datetime.datetime(
        int(y), int(m), int(d),
        int(h), int(minute), int(second),
        tzinfo=zoneinfo.ZoneInfo("UTC")
    )
    return dt.astimezone(delhi_tz)

def get_tithi(jd):
    """Return the 0-based tithi index at a given Julian Day."""
    sun_long = swe.calc_ut(jd, swe.SUN, swe.FLG_SIDEREAL)[0][0]
    moon_long = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0]
    angle = (moon_long - sun_long) % 360
    return int(angle // 12)

def get_tithi_name(tithi_index):
    """Get proper tithi name with paksha."""
    if tithi_index < 15:
        paksha = "Shukla Paksha"
        if tithi_index == 14:  # 15th tithi in Shukla Paksha
            tithi_name = "Purnima"
        else:
            tithi_name = tithi_names[tithi_index]
    else:
        paksha = "Krishna Paksha"
        adjusted_index = tithi_index - 15
        if adjusted_index == 14:  # 15th tithi in Krishna Paksha
            tithi_name = "Amavasya"
        elif adjusted_index < 14:
            tithi_name = tithi_names[adjusted_index]
        else:
            tithi_name = "Amavasya"
    
    return f"{paksha} {tithi_name}"

def get_nakshatra(jd):
    """Return the 0-based nakshatra index (0..26) at a given Julian Day."""
    moon_long = swe.calc_ut(jd, swe.MOON, swe.FLG_SIDEREAL)[0][0]
    return int(moon_long // (360 / 27))

def find_transition_jd(jd_start, get_value_func):
    """Binary-search for JD when get_value_func transitions to new value."""
    current_val = get_value_func(jd_start)
    lower = jd_start
    upper = jd_start + 2  # search window of up to 2 days
    while upper - lower > 1 / 86400:  # precision of 1 second
        mid = (lower + upper) / 2
        if get_value_func(mid) != current_val:
            upper = mid
        else:
            lower = mid
    return upper

def get_timezone_from_coordinates(latitude, longitude):
    """Get timezone string from latitude and longitude coordinates."""
    try:
        timezone_str = tf.timezone_at(lat=latitude, lng=longitude)
        if timezone_str:
            return timezone_str
        else:
            # Fallback to UTC if timezone not found
            logging.warning(f"Timezone not found for coordinates {latitude}, {longitude}. Using UTC.")
            return "UTC"
    except Exception as e:
        logging.error(f"Error getting timezone for coordinates {latitude}, {longitude}: {str(e)}")
        return "UTC"

def generate_kundali_png(birth_chart_data, user_name=""):
    """Generate PNG image of South Indian style Kundali chart and return as BytesIO."""
    
    planet_abbr = {'Sun': 'Su', 'Moon': 'Mo', 'Mercury': 'Me', 'Venus': 'Ve', 'Mars': 'Ma', 'Jupiter': 'Ju', 'Saturn': 'Sa', 'Rahu': 'Ra', 'Ketu': 'Ke'}
    
    # Image dimensions
    width = 600
    height = 650
    cell_size = 120
    start_x = 60
    start_y = 100
    
    # Create image
    img = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a default font, fallback to basic if not available
    try:
        title_font = ImageFont.truetype("arial.ttf", 20)
        house_font = ImageFont.truetype("arial.ttf", 12)
        sign_font = ImageFont.truetype("arial.ttf", 14)
        planet_font = ImageFont.truetype("arial.ttf", 16)
    except:
        title_font = ImageFont.load_default()
        house_font = ImageFont.load_default()
        sign_font = ImageFont.load_default()
        planet_font = ImageFont.load_default()
    
    # Title
    title_text = f"Kundali Chart (South Indian Style)"
    try:
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_width = title_bbox[2] - title_bbox[0]
    except:
        title_width = len(title_text) * 10  # Fallback estimation
    draw.text(((width - title_width) // 2, 20), title_text, fill='black', font=title_font)
    
    # User name
    if user_name:
        try:
            name_bbox = draw.textbbox((0, 0), user_name, font=house_font)
            name_width = name_bbox[2] - name_bbox[0]
        except:
            name_width = len(user_name) * 8  # Fallback estimation
        draw.text(((width - name_width) // 2, 50), user_name, fill='gray', font=house_font)
    
    # Define the 4x4 grid layout
    house_layout = [
        [12, 1, 2, 3],      # Row 1
        [11, -1, -1, 4],    # Row 2 (-1 means empty center cell)
        [10, -1, -1, 5],    # Row 3
        [9, 8, 7, 6]        # Row 4
    ]
    
    # Group planets by house
    houses_with_planets = {}
    for planet, house_num in birth_chart_data['planet_houses'].items():
        if house_num not in houses_with_planets:
            houses_with_planets[house_num] = []
        houses_with_planets[house_num].append(planet)
    
    # Draw the 4x4 grid
    for row in range(4):
        for col in range(4):
            x = start_x + col * cell_size
            y = start_y + row * cell_size
            house_num = house_layout[row][col]
            
            if house_num == -1:  # Center empty cells
                # Light gray background for center
                draw.rectangle([x, y, x + cell_size, y + cell_size], outline='black', fill='#e9ecef', width=2)
                continue
            
            # Draw house cell
            draw.rectangle([x, y, x + cell_size, y + cell_size], outline='black', fill='#f8f9fa', width=2)
            
            # House number (top-left, lighter)
            draw.text((x + 5, y + 5), str(house_num), fill='#aaa', font=house_font)
            
            # Sign number (top-right, blue)
            sign_num = (birth_chart_data['ascendant_sign_index'] + house_num - 1) % 12 + 1
            sign_text = str(sign_num)
            try:
                sign_bbox = draw.textbbox((0, 0), sign_text, font=sign_font)
                sign_width = sign_bbox[2] - sign_bbox[0]
            except:
                sign_width = len(sign_text) * 10  # Fallback estimation
            draw.text((x + cell_size - sign_width - 5, y + 5), sign_text, fill='#0066cc', font=sign_font)
            
            # Planets (center, red)
            if house_num in houses_with_planets:
                planets = houses_with_planets[house_num]
                planet_texts = [planet_abbr.get(p, p[:2]) for p in planets]
                
                if len(planet_texts) == 1:
                    planet_text = planet_texts[0]
                    try:
                        planet_bbox = draw.textbbox((0, 0), planet_text, font=planet_font)
                        planet_width = planet_bbox[2] - planet_bbox[0]
                        planet_height = planet_bbox[3] - planet_bbox[1]
                    except:
                        planet_width = len(planet_text) * 12
                        planet_height = 16
                    draw.text((x + (cell_size - planet_width) // 2, y + (cell_size - planet_height) // 2), 
                             planet_text, fill='#d63384', font=planet_font)
                elif len(planet_texts) == 2:
                    # Two planets - stack vertically
                    for i, planet_text in enumerate(planet_texts):
                        try:
                            planet_bbox = draw.textbbox((0, 0), planet_text, font=planet_font)
                            planet_width = planet_bbox[2] - planet_bbox[0]
                        except:
                            planet_width = len(planet_text) * 12
                        y_offset = y + 35 + (i * 25)
                        draw.text((x + (cell_size - planet_width) // 2, y_offset), 
                                 planet_text, fill='#d63384', font=planet_font)
                else:
                    # Multiple planets - stack them
                    for i, planet_text in enumerate(planet_texts[:3]):
                        try:
                            planet_bbox = draw.textbbox((0, 0), planet_text, font=planet_font)
                            planet_width = planet_bbox[2] - planet_bbox[0]
                        except:
                            planet_width = len(planet_text) * 12
                        y_offset = y + 25 + (i * 20)
                        draw.text((x + (cell_size - planet_width) // 2, y_offset), 
                                 planet_text, fill='#d63384', font=planet_font)
    
    # Add legend
    legend_y = start_y + 4 * cell_size + 20
    legend_texts = [
        "Chart Layout: House numbers (light gray) in top-left, Sign numbers (blue) in top-right, Planets (red) in center",
        "Sign Numbers: 1=Aries, 2=Taurus, 3=Gemini, 4=Cancer, 5=Leo, 6=Virgo, 7=Libra, 8=Scorpio, 9=Sagittarius, 10=Capricorn, 11=Aquarius, 12=Pisces",
        f"Lagna (Ascendant): House 1 = Sign {(birth_chart_data['ascendant_sign_index'] + 1)} ({birth_chart_data['ascendant_sign']})"
    ]
    
    for i, legend_text in enumerate(legend_texts):
        draw.text((10, legend_y + i * 15), legend_text, fill='gray', font=house_font)
    
    # Convert to BytesIO
    img_buffer = BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    return img_buffer

# === ASTROLOGY ENGINE ===
class AstrologyEngine:
    def __init__(self):
        # Default location is Delhi, but can be overridden
        self.default_lat = 28.6139   # Delhi latitude
        self.default_lon = 77.2090   # Delhi longitude

    def calculate_numerology(self, full_name, birth_date):
        """Calculate all numerology numbers."""
        pythagorean = numerology_name_number(full_name, pytha_map)
        chaldean = numerology_name_number(full_name, chaldean_map)
        driver = digital_root(birth_date.day)
        conductor = life_path_number_from_date(birth_date)

        return {
            'pythagorean_expression': pythagorean,
            'chaldean_expression': chaldean,
            'driver_number': driver,
            'conductor_number': conductor
        }

    def calculate_birth_chart(self, birth_datetime_local, lat=None, lon=None):
        """Calculate complete birth chart."""
        lat_birth = lat if lat is not None else self.default_lat
        lon_birth = lon if lon is not None else self.default_lon

        birth_utc = birth_datetime_local.astimezone(zoneinfo.ZoneInfo("UTC"))

        jd_birth = swe.julday(
            birth_utc.year, birth_utc.month, birth_utc.day,
            birth_utc.hour + birth_utc.minute / 60 + birth_utc.second / 3600
        )

        planet_ids = {
            "Sun": swe.SUN,
            "Moon": swe.MOON,
            "Mercury": swe.MERCURY,
            "Venus": swe.VENUS,
            "Mars": swe.MARS,
            "Jupiter": swe.JUPITER,
            "Saturn": swe.SATURN,
            "Rahu": swe.MEAN_NODE,
            "Ketu": swe.MEAN_NODE
        }

        planet_positions = {}
        for name, pid in planet_ids.items():
            pl_long = swe.calc_ut(jd_birth, pid, swe.FLG_SIDEREAL)[0][0]
            if name == "Ketu":
                pl_long = (pl_long + 180) % 360
            planet_positions[name] = pl_long

        asc_birth = swe.houses_ex(jd_birth, lat_birth, lon_birth, b'P', swe.FLG_SIDEREAL)[1][0]
        asc_sign_index = int(asc_birth // 30)

        house_starts = [(asc_sign_index * 30 + i * 30) % 360 for i in range(12)]
        planet_houses = {}

        for name, pl_long in planet_positions.items():
            for i in range(12):
                start = house_starts[i]
                end = house_starts[(i + 1) % 12]
                if start < end:
                    if start <= pl_long < end:
                        planet_houses[name] = i + 1
                        break
                else:
                    if pl_long >= start or pl_long < end:
                        planet_houses[name] = i + 1
                        break

        moon_long = planet_positions["Moon"]
        sun_long = planet_positions["Sun"]
        nak_index_birth = int(moon_long // (360 / 27))
        phase_angle_birth = (moon_long - sun_long) % 360
        tithi_index_birth = int(phase_angle_birth // 12)

        # Get proper tithi name
        birth_tithi_name = get_tithi_name(tithi_index_birth)

        house2_sign_index = (asc_sign_index + 1) % 12
        house11_sign_index = (asc_sign_index + 10) % 12

        return {
            'jd_birth': jd_birth,
            'planet_positions': planet_positions,
            'planet_houses': planet_houses,
            'ascendant': asc_birth,
            'ascendant_sign': rashis[asc_sign_index],
            'ascendant_sign_index': asc_sign_index,
            'birth_nakshatra': nakshatras[nak_index_birth],
            'birth_nakshatra_index': nak_index_birth,
            'birth_tithi_index': tithi_index_birth,
            'birth_tithi_name': birth_tithi_name,
            'house2_sign': rashis[house2_sign_index],
            'house2_sign_num': house2_sign_index + 1,
            'house11_sign': rashis[house11_sign_index],
            'house11_sign_num': house11_sign_index + 1,
            'phase_angle': phase_angle_birth,
            'latitude': lat_birth,
            'longitude': lon_birth
        }

    def generate_monthly_calendar(self, year, month, birth_nakshatra_index):
        """Generate monthly calendar with Tithi, Nakshatra and Tara."""

        ephe_path = os.path.join(os.path.dirname(__file__), "ephe")
        swe.set_ephe_path(ephe_path)
        swe.set_sid_mode(swe.SIDM_LAHIRI)  # Lahiri (Sidereal) zodiac
        start_dt = datetime.datetime(year, month, 1, 0, 0, tzinfo=delhi_tz)
        jd_start = swe.julday(start_dt.year, start_dt.month, start_dt.day, 0)

        next_month = (start_dt + datetime.timedelta(days=32)).replace(day=1)
        jd_end = swe.julday(next_month.year, next_month.month, next_month.day, 0)

        # === TITHI ===
        tithi_transitions = []
        curr_jd = jd_start
        while curr_jd < jd_end:
            t_index = get_tithi(curr_jd)
            t_name = get_tithi_name(t_index)  # Use the proper function
            next_change = find_transition_jd(curr_jd + 1e-6, get_tithi)
            tithi_start_dt = jd_to_datetime(curr_jd)
            tithi_end_dt = jd_to_datetime(next_change)
            tithi_transitions.append((tithi_start_dt, tithi_end_dt, t_name))
            curr_jd = next_change + 1e-6

        # === NAKSHATRA ===
        nakshatra_transitions = []
        curr_jd = jd_start
        while curr_jd < jd_end:
            n_index = get_nakshatra(curr_jd)
            n_name = nakshatras[n_index]
            next_change = find_transition_jd(curr_jd + 1e-6, get_nakshatra)
            nak_start_dt = jd_to_datetime(curr_jd)
            nak_end_dt = jd_to_datetime(next_change)
            nakshatra_transitions.append((nak_start_dt, nak_end_dt, n_name, n_index))
            curr_jd = next_change + 1e-6

        # === ORGANIZE BY DATE ===
        calendar_data = defaultdict(lambda: {"tithi": [], "nakshatra": [], "raahu_kaal": None})

        for start_dt_obj, end_dt_obj, name in tithi_transitions:
            current = start_dt_obj
            recorded = set()
            while current.date() <= end_dt_obj.date():
                day = current.date()
                if day not in recorded:
                    calendar_data[day]["tithi"].append((start_dt_obj, end_dt_obj, name))
                    recorded.add(day)
                current += datetime.timedelta(days=1)

        for start_dt_obj, end_dt_obj, name, n_index in nakshatra_transitions:
            current = start_dt_obj
            recorded = set()
            while current.date() <= end_dt_obj.date():
                day = current.date()
                if day not in recorded:
                    tara_name, tara_meaning = get_tara_relation(birth_nakshatra_index, n_index)
                    calendar_data[day]["nakshatra"].append((
                        start_dt_obj, end_dt_obj, name, tara_name, tara_meaning
                    ))
                    recorded.add(day)
                current += datetime.timedelta(days=1)

        # --- RAAHU KAAL ---
        for day in calendar_data:
            raahu_start, raahu_end = get_raahu_kaal(day)
            if raahu_start and raahu_end:
                calendar_data[day]["raahu_kaal"] = {
                    'start': raahu_start,
                    'end': raahu_end,
                    'weekday': day.strftime('%A')
                }
            else:
                calendar_data[day]["raahu_kaal"] = None

        return dict(calendar_data)

    def check_auspicious_matches(self, numerology, house2_sign_num, house11_sign_num):
        """Check for auspicious numerology matches with houses."""
        matches = []
        checks = [
            (numerology['driver_number'], "Driver"),
            (numerology['conductor_number'], "Conductor"),
            (numerology['chaldean_expression'], "Chaldean Expression"),
            (numerology['pythagorean_expression'], "Pythagorean Expression")
        ]

        for num, label in checks:
            if num == house2_sign_num:
                matches.append(f"{label} number {num} matches House 2 sign #{house2_sign_num}")
            if num == house11_sign_num:
                matches.append(f"{label} number {num} matches House 11 sign #{house11_sign_num}")

        return matches
    
    # Helper: Julian Day to IST datetime
UTC = datetime.timezone.utc
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
def jd_to_ist(jd: float) -> datetime.datetime:
    y, m, d, h = swe.revjul(jd)
    hr = int(h)
    mn = int((h - hr) * 60)
    sec = int((((h - hr) * 60) - mn) * 60)
    dt_utc = datetime.datetime(y, m, d, hr, mn, sec, tzinfo=UTC)
    return dt_utc.astimezone(IST)

# Raahu Kaal constants
RAAHU_INDEX = {
    0: 1,  # Mon → 2nd segment (index 1)
    1: 6,  # Tue → 7th segment (index 6)
    2: 4,  # Wed → 5th segment (index 4)
    3: 5,  # Thu → 6th segment (index 5)
    4: 3,  # Fri → 4th segment (index 3)
    5: 2,  # Sat → 3rd segment (index 2)
    6: 7   # Sun → 8th segment (index 7)
}
def get_raahu_kaal(date_obj: datetime.date, latitude=28.6139, longitude=77.2090):
    """
    Calculate Raahu Kaal timing for a given date and location.
    Default location is Delhi.
    """
    jd0 = swe.julday(date_obj.year, date_obj.month, date_obj.day, 0.0)
    flags_rise = swe.CALC_RISE | swe.BIT_DISC_CENTER
    flags_set = swe.CALC_SET | swe.BIT_DISC_CENTER
    geopos = (longitude, latitude, 0)
    try:
        # Find sunrise and sunset for the IST civil date
        _, rise_t = swe.rise_trans(jd0, swe.SUN, flags_rise, geopos=geopos)
        _, set_t = swe.rise_trans(jd0, swe.SUN, flags_set, geopos=geopos)
        rise_jd = rise_t[0]
        set_jd = set_t[0]
        sunrise = jd_to_ist(rise_jd)
        sunset = jd_to_ist(set_jd)
        # If sunset is before sunrise, get sunset for next day
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
    except Exception as e:
        logging.error(f"Error calculating Raahu Kaal for {date_obj}: {e}")
        return None, None

def get_gulika_kaal(date_obj, latitude=28.6139, longitude=77.2090):
    """
    Calculate Gulika Kaal timing for a given date and location.
    Default location is Delhi.
    """
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    logging.debug(f"[GULIKA] For {date_obj}: sunrise={sunrise}, sunset={sunset}")
    if not sunrise or not sunset:
        return None, None
    part = (sunset - sunrise) / 8
    GULIKA_INDEX = {0: 5, 1: 4, 2: 3, 3: 2, 4: 1, 5: 0, 6: 6}
    idx = GULIKA_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part
    logging.debug(f"[GULIKA] idx={idx}, start={start}, end={end}")
    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

def get_yamaganda_kaal(date_obj, latitude=28.6139, longitude=77.2090):
    """
    Calculate Yamaganda Kaal timing for a given date and location.
    Default location is Delhi.
    """
    sunrise, sunset = get_sunrise_sunset(date_obj, latitude, longitude)
    logging.debug(f"[YAMAGANDA] For {date_obj}: sunrise={sunrise}, sunset={sunset}")
    if not sunrise or not sunset:
        return None, None
    part = (sunset - sunrise) / 8
    YAMAGANDA_INDEX = {0: 3, 1: 2, 2: 1, 3: 0, 4: 6, 5: 5, 6: 4}
    idx = YAMAGANDA_INDEX[date_obj.weekday()]
    start = sunrise + idx * part
    end = start + part
    logging.debug(f"[YAMAGANDA] idx={idx}, start={start}, end={end}")
    if end > sunset:
        end = sunset
    if end <= start:
        return None, None
    return start, end

def get_sunrise_sunset(date_obj: datetime.date, latitude=28.6139, longitude=77.2090):
    """
    Get sunrise and sunset times for a given date and location.
    Returns IST datetime objects for the same civil date.
    """
    jd = swe.julday(date_obj.year, date_obj.month, date_obj.day, 0.0)
    flags = swe.CALC_RISE | swe.BIT_DISC_CENTER
    geopos = (longitude, latitude, 0)
    try:
        # Find sunrise for the given date
        _, rise_t = swe.rise_trans(jd, swe.SUN, flags, geopos=geopos)
        sunrise = jd_to_ist(rise_t[0])
        # If sunrise is not on the same civil date, try previous/next day
        if sunrise.date() != date_obj:
            # Try previous day
            jd_prev = swe.julday(date_obj.year, date_obj.month, date_obj.day - 1, 0.0)
            _, rise_t_prev = swe.rise_trans(jd_prev, swe.SUN, flags, geopos=geopos)
            sunrise_prev = jd_to_ist(rise_t_prev[0])
            if sunrise_prev.date() == date_obj:
                sunrise = sunrise_prev
            else:
                # Try next day
                jd_next = swe.julday(date_obj.year, date_obj.month, date_obj.day + 1, 0.0)
                _, rise_t_next = swe.rise_trans(jd_next, swe.SUN, flags, geopos=geopos)
                sunrise_next = jd_to_ist(rise_t_next[0])
                if sunrise_next.date() == date_obj:
                    sunrise = sunrise_next
        # Find sunset for the given date
        _, set_t = swe.rise_trans(jd, swe.SUN, flags | swe.CALC_SET, geopos=geopos)
        sunset = jd_to_ist(set_t[0])
        if sunset.date() != date_obj:
            # Try previous day
            jd_prev = swe.julday(date_obj.year, date_obj.month, date_obj.day - 1, 0.0)
            _, set_t_prev = swe.rise_trans(jd_prev, swe.SUN, flags | swe.CALC_SET, geopos=geopos)
            sunset_prev = jd_to_ist(set_t_prev[0])
            if sunset_prev.date() == date_obj:
                sunset = sunset_prev
            else:
                # Try next day
                jd_next = swe.julday(date_obj.year, date_obj.month, date_obj.day + 1, 0.0)
                _, set_t_next = swe.rise_trans(jd_next, swe.SUN, flags | swe.CALC_SET, geopos=geopos)
                sunset_next = jd_to_ist(set_t_next[0])
                if sunset_next.date() == date_obj:
                    sunset = sunset_next
        # Final check: both must be on the same date
        if sunrise.date() == sunset.date() == date_obj:
            return sunrise, sunset
        else:
            logging.error(f"Sunrise or sunset not found for {date_obj} at {latitude},{longitude}")
            return None, None
    except Exception as e:
        logging.error(f"Error getting sunrise/sunset for {date_obj}: {e}")
        return None, None

# === INITIALIZE INSTANCES ===
astro_engine = AstrologyEngine()

class AstrologyPDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self.setup_custom_styles()
    
    def setup_custom_styles(self):
        """Setup custom styles for the PDF."""
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=18,
            alignment=TA_CENTER,
            spaceAfter=30,
            textColor=colors.darkblue
        )
        
        self.section_style = ParagraphStyle(
            'SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            alignment=TA_LEFT,
            spaceAfter=12,
            textColor=colors.darkgreen
        )
        
        self.normal_style = ParagraphStyle(
            'CustomNormal',
            parent=self.styles['Normal'],
            fontSize=10,
            spaceAfter=6
        )
    
    def generate_birth_chart_pdf(self, user, numerology, birth_chart_data, auspicious_matches):
        """Generate birth chart PDF report with embedded PNG chart."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch)
        story = []
        
        # Title
        title = Paragraph(f"Vedic Birth Chart Report", self.title_style)
        story.append(title)
        story.append(Spacer(1, 20))
        
        # Personal Information
        story.append(Paragraph("Personal Information", self.section_style))
        personal_info = [
            ['Full Name:', user.full_name],
            ['Birth Date:', user.birth_date.strftime('%B %d, %Y')],
            ['Birth Time:', user.birth_time],
            ['Birth Place:', f"{user.birth_city}, {user.birth_country}"],
            ['Coordinates:', f"{user.birth_latitude:.4f}°, {user.birth_longitude:.4f}°"],
            ['Timezone:', user.birth_timezone]
        ]
        personal_table = Table(personal_info, colWidths=[2*inch, 4*inch])
        personal_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(personal_table)
        story.append(Spacer(1, 20))
        
        # Add Kundali Chart PNG
        try:
            story.append(Paragraph("Kundali Chart", self.section_style))
            chart_img_buffer = generate_kundali_png(birth_chart_data, user.full_name)
            chart_image = ReportLabImage(chart_img_buffer, width=4*inch, height=4.3*inch)
            story.append(chart_image)
        except Exception as e:
            logging.error(f"Error adding PNG chart to PDF: {str(e)}")
            story.append(Paragraph("Chart visualization not available", self.normal_style))
        
        story.append(Spacer(1, 20))
        
        # Numerology Section
        story.append(Paragraph("Numerology Analysis", self.section_style))
        numerology_info = [
            ['Pythagorean Expression Number:', str(numerology['pythagorean_expression'])],
            ['Chaldean Expression Number:', str(numerology['chaldean_expression'])],
            ['Driver Number:', str(numerology['driver_number'])],
            ['Conductor Number (Life Path):', str(numerology['conductor_number'])]
        ]
        numerology_table = Table(numerology_info, colWidths=[3*inch, 1*inch])
        numerology_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(numerology_table)
        story.append(Spacer(1, 20))
        
        # Auspicious Matches
        if auspicious_matches:
            story.append(Paragraph("🚩 Auspicious Signals Detected", self.section_style))
            for match in auspicious_matches:
                story.append(Paragraph(f"• {match}", self.normal_style))
            story.append(Spacer(1, 20))
        
        # Birth Chart Data
        story.append(Paragraph("Birth Chart Details", self.section_style))
        chart_info = [
            ['Birth Nakshatra:', birth_chart_data['birth_nakshatra']],
            ['Birth Tithi:', birth_chart_data['birth_tithi_name']],
            ['Ascendant Sign:', birth_chart_data['ascendant_sign']],
            ['Ascendant Degree:', f"{birth_chart_data['ascendant']:.2f}°"],
            ['House 2 Sign:', birth_chart_data['house2_sign']],
            ['House 11 Sign:', birth_chart_data['house11_sign']]
        ]
        chart_table = Table(chart_info, colWidths=[2.5*inch, 2.5*inch])
        chart_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(chart_table)
        story.append(Spacer(1, 20))
        
        # Planetary Positions
        story.append(Paragraph("Planetary Positions", self.section_style))
        planet_data = [['Planet', 'Longitude', 'Sign', 'House']]
        for planet, longitude in birth_chart_data['planet_positions'].items():
            sign_name = rashis[int(longitude // 30)]
            house_no = birth_chart_data['planet_houses'][planet]
            planet_data.append([
                planet,
                f"{longitude:.2f}°",
                sign_name,
                str(house_no)
            ])
        planet_table = Table(planet_data, colWidths=[1.2*inch, 1.5*inch, 1.5*inch, 0.8*inch])
        planet_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(planet_table)
        story.append(Spacer(1, 20))
        
        # Houses and Their Ruling Signs
        story.append(Paragraph("Houses and Their Ruling Signs", self.section_style))
        house_data = [['House', 'Sign', 'Sign Number']]
        for i in range(12):
            sign_idx = (birth_chart_data['ascendant_sign_index'] + i) % 12
            sign_name = rashis[sign_idx]
            house_data.append([
                f"House {i + 1}",
                sign_name,
                str(sign_idx + 1)
            ])
        house_table = Table(house_data, colWidths=[1.5*inch, 2*inch, 1.5*inch])
        house_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(house_table)
        story.append(Spacer(1, 20))
        
        # Add Remarks section if exists
        if user.remarks and user.remarks.strip():
            story.append(Paragraph("Observations & Remarks", self.section_style))
            remarks_text = user.remarks.replace('\n', '<br/>')
            story.append(Paragraph(remarks_text, self.normal_style))
            story.append(Spacer(1, 20))
        
        # Footer
        footer = Paragraph(
            f"Report generated on {datetime.datetime.now().strftime('%B %d, %Y at %I:%M %p')}",
            ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=8, alignment=TA_CENTER)
        )
        story.append(footer)
        
        doc.build(story)
        buffer.seek(0)
        return buffer

# === INITIALIZE PDF GENERATOR ===
pdf_generator = AstrologyPDFGenerator()

# === FLASK ROUTES ===
@app.route('/')
def index():
    """Home page with user selection and new user form."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('index.html', users=users)

@app.route('/create_user', methods=['POST'])
def create_user():
    """Create a new user with birth chart calculation."""
    try:
        app.logger.info("Starting user creation process")
        
        full_name = request.form['full_name'].strip()
        birth_date_str = request.form['birth_date']
        birth_time_str = request.form['birth_time']
        birth_city = request.form.get('birth_city', 'Delhi').strip()
        birth_country = request.form.get('birth_country', 'India').strip()
        birth_latitude = float(request.form.get('birth_latitude', 28.6139))
        birth_longitude = float(request.form.get('birth_longitude', 77.2090))
        birth_timezone = request.form.get('birth_timezone', 'Asia/Kolkata')
        
        app.logger.info(f"Form data received: {full_name}, {birth_date_str}, {birth_time_str}")
        
        if not all([full_name, birth_date_str, birth_time_str]):
            flash('All required fields must be filled.', 'error')
            return redirect(url_for('index'))
        
        # Auto-detect timezone from coordinates if not manually set
        if birth_latitude and birth_longitude:
            auto_timezone = get_timezone_from_coordinates(birth_latitude, birth_longitude)
            if auto_timezone and auto_timezone != 'UTC':
                birth_timezone = auto_timezone
                app.logger.info(f"Auto-detected timezone: {birth_timezone}")
        
        # Parse birth date and time
        birth_date = datetime.datetime.strptime(birth_date_str, '%Y-%m-%d').date()
        birth_time = datetime.datetime.strptime(birth_time_str, '%H:%M').time()
        
        # Create birth datetime in specified timezone
        birth_datetime = datetime.datetime.combine(birth_date, birth_time)
        local_tz = zoneinfo.ZoneInfo(birth_timezone)
        birth_datetime_local = birth_datetime.replace(tzinfo=local_tz)
        
        app.logger.info("Calculating numerology")
        # Calculate numerology
        numerology = astro_engine.calculate_numerology(full_name, birth_datetime_local)
        
        app.logger.info("Calculating birth chart")
        # Calculate birth chart with location
        birth_chart_data = astro_engine.calculate_birth_chart(
            birth_datetime_local, lat=birth_latitude, lon=birth_longitude
        )
        
        # Create user
        user = User()
        user.full_name = full_name
        user.birth_date = birth_date
        user.birth_time = birth_time_str + ":00"
        user.birth_city = birth_city
        user.birth_country = birth_country
        user.birth_latitude = birth_latitude
        user.birth_longitude = birth_longitude
        user.birth_timezone = birth_timezone
        user.pythagorean_expression = numerology['pythagorean_expression']
        user.chaldean_expression = numerology['chaldean_expression']
        user.driver_number = numerology['driver_number']
        user.conductor_number = numerology['conductor_number']
        user.sun_longitude = birth_chart_data['planet_positions']['Sun']
        user.moon_longitude = birth_chart_data['planet_positions']['Moon']
        user.ascendant = birth_chart_data['ascendant']
        user.birth_nakshatra = birth_chart_data['birth_nakshatra']
        user.birth_tithi = birth_chart_data['birth_tithi_name']  # Use proper name
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create birth chart record
        birth_chart = BirthChart()
        birth_chart.user_id = user.id
        birth_chart.sun_position = birth_chart_data['planet_positions']['Sun']
        birth_chart.moon_position = birth_chart_data['planet_positions']['Moon']
        birth_chart.mercury_position = birth_chart_data['planet_positions']['Mercury']
        birth_chart.venus_position = birth_chart_data['planet_positions']['Venus']
        birth_chart.mars_position = birth_chart_data['planet_positions']['Mars']
        birth_chart.jupiter_position = birth_chart_data['planet_positions']['Jupiter']
        birth_chart.saturn_position = birth_chart_data['planet_positions']['Saturn']
        birth_chart.rahu_position = birth_chart_data['planet_positions']['Rahu']
        birth_chart.ketu_position = birth_chart_data['planet_positions']['Ketu']
        birth_chart.sun_house = birth_chart_data['planet_houses']['Sun']
        birth_chart.moon_house = birth_chart_data['planet_houses']['Moon']
        birth_chart.mercury_house = birth_chart_data['planet_houses']['Mercury']
        birth_chart.venus_house = birth_chart_data['planet_houses']['Venus']
        birth_chart.mars_house = birth_chart_data['planet_houses']['Mars']
        birth_chart.jupiter_house = birth_chart_data['planet_houses']['Jupiter']
        birth_chart.saturn_house = birth_chart_data['planet_houses']['Saturn']
        birth_chart.rahu_house = birth_chart_data['planet_houses']['Rahu']
        birth_chart.ketu_house = birth_chart_data['planet_houses']['Ketu']
        birth_chart.ascendant_degree = birth_chart_data['ascendant']
        birth_chart.ascendant_sign = birth_chart_data['ascendant_sign']
        birth_chart.house2_sign = birth_chart_data['house2_sign']
        birth_chart.house11_sign = birth_chart_data['house11_sign']
        
        db.session.add(birth_chart)
        db.session.commit()
        
        flash(f'User {full_name} created successfully!', 'success')
        return redirect(url_for('birth_chart', user_id=user.id))
        
    except ValueError as e:
        flash('Invalid date or time format.', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating user: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/user/<int:user_id>')
def user_profile(user_id):
    """Display user profile with quick actions."""
    user = User.query.get_or_404(user_id)
    return render_template('user_profile.html', user=user)

@app.route('/birth_chart/<int:user_id>')
def birth_chart(user_id):
    """Display detailed birth chart for user."""
    try:
        user = User.query.get_or_404(user_id)
        birth_chart_record = BirthChart.query.filter_by(user_id=user_id).first()
        
        if not birth_chart_record:
            flash('Birth chart not found. Please recalculate.', 'error')
            return redirect(url_for('index'))
        
        # Recalculate for display
        birth_datetime_local = user.get_birth_datetime_local()
        numerology = astro_engine.calculate_numerology(user.full_name, birth_datetime_local)
        birth_chart_data = astro_engine.calculate_birth_chart(
            birth_datetime_local, lat=user.birth_latitude, lon=user.birth_longitude
        )
        
        # Check auspicious matches
        auspicious_matches = astro_engine.check_auspicious_matches(
            numerology, 
            birth_chart_data['house2_sign_num'], 
            birth_chart_data['house11_sign_num']
        )
        
        return render_template('birth_chart.html', 
                             user=user, 
                             numerology=numerology,
                             birth_chart_data=birth_chart_data,
                             auspicious_matches=auspicious_matches,
                             birth_chart_record=birth_chart_record)
    except Exception as e:
        app.logger.error(f"Birth chart error for user {user_id}: {str(e)}")
        flash(f'Error generating birth chart: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/download_chart_png/<int:user_id>')
def download_chart_png(user_id):
    """Download Kundali chart as PNG image."""
    try:
        user = User.query.get_or_404(user_id)
        
        # Recalculate birth chart data
        birth_datetime_local = user.get_birth_datetime_local()
        birth_chart_data = astro_engine.calculate_birth_chart(
            birth_datetime_local, lat=user.birth_latitude, lon=user.birth_longitude
        )
        
        # Generate PNG image
        chart_img_buffer = generate_kundali_png(birth_chart_data, user.full_name)
        
        response = make_response(chart_img_buffer.read())
        response.headers['Content-Type'] = 'image/png'
        response.headers['Content-Disposition'] = f'attachment; filename=kundali_chart_{user.full_name.replace(" ", "_")}.png'
        
        return response
        
    except Exception as e:
        app.logger.error(f"PNG generation error for user {user_id}: {str(e)}")
        flash(f'Error generating PNG chart: {str(e)}', 'error')
        return redirect(url_for('birth_chart', user_id=user_id))

@app.route('/calendar/<int:user_id>')
def calendar_view(user_id):
    user = User.query.get_or_404(user_id)

    # Fetch raw query‐string values (may be None)
    year_arg = request.args.get("year")
    month_arg = request.args.get("month")
    logging.info(f"[DEBUG] Received raw query params: year={year_arg}, month={month_arg}")

    # Fall back to current year/month if not provided
    now = datetime.datetime.now()
    try:
        year = int(year_arg) if year_arg is not None else now.year
        month = int(month_arg) if month_arg is not None else now.month
    except ValueError:
        # If someone passed non‐numeric values, default to "now"
        logging.warning("[DEBUG] Invalid year/month; defaulting to current.")
        year = now.year
        month = now.month

    logging.info(f"[DEBUG] Using year={year}, month={month} for calendar generation")

    # Add month name for template
    month_name = datetime.datetime(year, month, 1).strftime('%B')

    birth_nakshatra_index = nakshatras.index(user.birth_nakshatra)
    calendar_data = astro_engine.generate_monthly_calendar(year, month, birth_nakshatra_index)

    # Now log exactly what's in calendar_data for June 06, 2025
    test_day = datetime.date(2025, 6, 6)
    nak_list = calendar_data.get(test_day, {}).get("nakshatra", [])
    print(f"[DEBUG-PRINT] calendar_data for {year}-{month}, June 06: {nak_list}")

    return render_template(
        "calendar.html",
        user=user,
        year=year,
        month=month,
        month_name=month_name,  # Add this line
        calendar_data=calendar_data,
        today=datetime.date.today(),
    )

@app.route('/update_remarks/<int:user_id>', methods=['POST'])
def update_remarks(user_id):
    """Update remarks for a user."""
    user = User.query.get_or_404(user_id)
    remarks = request.form.get('remarks', '').strip()
    
    user.remarks = remarks
    db.session.commit()
    
    flash('Remarks updated successfully!', 'success')
    return redirect(url_for('birth_chart', user_id=user_id))

@app.route('/download_birth_chart/<int:user_id>')
def download_birth_chart(user_id):
    """Download birth chart as PDF."""
    user = User.query.get_or_404(user_id)
    birth_chart_record = BirthChart.query.filter_by(user_id=user_id).first()
    
    if not birth_chart_record:
        flash('Birth chart not found.', 'error')
        return redirect(url_for('index'))
    
    # Recalculate data for PDF
    birth_datetime_local = user.get_birth_datetime_local()
    numerology = astro_engine.calculate_numerology(user.full_name, birth_datetime_local)
    birth_chart_data = astro_engine.calculate_birth_chart(
        birth_datetime_local, lat=user.birth_latitude, lon=user.birth_longitude
    )
    
    auspicious_matches = astro_engine.check_auspicious_matches(
        numerology, 
        birth_chart_data['house2_sign_num'], 
        birth_chart_data['house11_sign_num']
    )
    
    # Generate PDF
    pdf_buffer = pdf_generator.generate_birth_chart_pdf(
        user, numerology, birth_chart_data, auspicious_matches
    )
    
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=birth_chart_{user.full_name.replace(" ", "_")}.pdf'
    
    return response

@app.route('/download_calendar/<int:user_id>')
def download_calendar(user_id):
    """Download monthly calendar as PDF."""
    user = User.query.get_or_404(user_id)
    # Get year and month from query params, default to current
    year = request.args.get('year', type=int) or datetime.datetime.now().year
    month = request.args.get('month', type=int) or datetime.datetime.now().month
    birth_nakshatra_index = nakshatras.index(user.birth_nakshatra)
    calendar_data = astro_engine.generate_monthly_calendar(year, month, birth_nakshatra_index)
    pdf_buffer = pdf_generator.generate_calendar_pdf(user, year, month, calendar_data)
    response = make_response(pdf_buffer.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=calendar_{user.full_name.replace(" ", "_")}_{year}_{month}.pdf'
    return response

@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    """Delete a user and their birth chart."""
    user = User.query.get_or_404(user_id)
    # Delete associated birth chart(s)
    BirthChart.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/api/timezone')
def api_timezone():
    """Return timezone for given coordinates as JSON."""
    lat = request.args.get('lat', type=float)
    lon = request.args.get('lon', type=float)
    if lat is None or lon is None:
        return jsonify({'error': 'Missing lat/lon'}), 400
    tz = get_timezone_from_coordinates(lat, lon)
    return jsonify({'timezone': tz})

@app.route('/timings')
def timings():
    """Show Raahu Kaal, Gulika Kaal, and Yamaganda Kaal for a given date and location (default: today, Delhi)."""
    # Get date from query params, default to today
    date_str = request.args.get('date')
    lat = request.args.get('lat', type=float, default=28.6139)
    lon = request.args.get('lon', type=float, default=77.2090)
    if date_str:
        try:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD.', 'error')
            date_obj = datetime.date.today()
    else:
        date_obj = datetime.date.today()

    raahu_start, raahu_end = get_raahu_kaal(date_obj, lat, lon)
    gulika_start, gulika_end = get_gulika_kaal(date_obj, lat, lon)
    yamaganda_start, yamaganda_end = get_yamaganda_kaal(date_obj, lat, lon)

    # Debug logging for diagnosis
    logging.debug(f"[TIMINGS] Date: {date_obj}, Lat: {lat}, Lon: {lon}")
    logging.debug(f"[TIMINGS] Raahu: {raahu_start} - {raahu_end}")
    logging.debug(f"[TIMINGS] Gulika: {gulika_start} - {gulika_end}")
    logging.debug(f"[TIMINGS] Yamaganda: {yamaganda_start} - {yamaganda_end}")

    return render_template(
        'timings.html',
        date=date_obj,
        lat=lat,
        lon=lon,
        raahu_start=raahu_start,
        raahu_end=raahu_end,
        gulika_start=gulika_start,
        gulika_end=gulika_end,
        yamaganda_start=yamaganda_start,
        yamaganda_end=yamaganda_end
    )

@app.route('/choghadiya')
def choghadiya_page():
    """Show Choghadiya periods for a given date and location (default: today, Delhi)."""
    from astro_time_windows import get_choghadiya
    date_str = request.args.get('date')
    lat = request.args.get('lat', type=float, default=28.6139)
    lon = request.args.get('lon', type=float, default=77.2090)
    if date_str:
        try:
            date_obj = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid date format. Use YYYY-MM-DD.', 'error')
            date_obj = datetime.date.today()
    else:
        date_obj = datetime.date.today()

    choghadiya_periods = get_choghadiya(date_obj, lat, lon)
    return render_template(
        'choghadiya.html',
        date=date_obj,
        lat=lat,
        lon=lon,
        choghadiya_periods=choghadiya_periods
    )

@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(e):
    db.session.rollback()
    return render_template('500.html'), 500

# === INITIALIZE DATABASE ===
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)