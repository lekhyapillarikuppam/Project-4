"""Every constant the dataset rules use, taken from the 001 Spec and Plan.

Nothing else in datatools hard-codes a rule value; it imports from here.
Section numbers refer to the 001 Spec unless marked "Plan".
"""

# --- Cities (Part B §4) ---------------------------------------------------

CITY_CODES = (
    "JAI", "AGR", "HMP", "MUN", "RSH", "DJL", "GOA", "PDY",
    "DEL", "BOM", "BLR", "CCU", "HYD", "VNS", "MAA",
)
CITY_COUNT = 15

TRAFFIC_FACTOR_RANGE = (1.0, 2.0)   # 5.1
FOOD_MULTIPLIER_RANGE = (0.6, 2.2)  # 5.1

# --- Interest tags (section 4) ---------------------------------------------

TAGS = (
    "nature", "adventure", "food", "history", "culture",
    "spiritual", "shopping", "relaxation", "nightlife",
)

# --- Number formats (section 3) --------------------------------------------

COORD_DECIMALS = 5
KM_DECIMALS = 1

# --- Enums -----------------------------------------------------------------

TRANSPORT_MODES = ("train", "bus", "flight")             # 5.2
COMFORT_LEVELS = ("budget", "mid", "premium")            # 5.6, 5.7
HOTEL_TIERS = COMFORT_LEVELS
CROWD_LEVELS = ("low", "medium", "high")                 # 5.5
LOCAL_MODES = ("auto", "cab")                            # 5.8
MATRIX_PROFILE = "driving-car"                           # 5.9

# --- Fare rates (5.4) ------------------------------------------------------

# (mode, class) -> per_km sanity bounds. These catch typos; they are not price claims.
FARE_CLASSES = {
    ("train", "SL"): (0.2, 1.0),
    ("train", "3A"): (0.5, 2.2),
    ("train", "2A"): (0.8, 3.2),
    ("bus", "ACS"): (1.5, 3.5),
    ("flight", "Y"): (2.0, 9.0),
}
# Extra bound on base_fare for these classes.
FARE_BASE_BOUNDS = {
    ("flight", "Y"): (1000, 6000),
}
COMFORT_VALUE_RANGE = (0.0, 1.0)

# --- City pairs (5.3) ------------------------------------------------------

PAIR_COUNT = 105                 # unordered pairs of 15 cities
BUS_MAX_ROAD_KM = 1000           # bus_available needs road_km <= this
FLIGHT_MIN_AIR_KM = 300          # flight_available needs air_km >= this

# Fallback duration formulas: minutes = km / speed_kmh * 60 + extra
TRAIN_FALLBACK = {"speed_kmh": 55, "extra_min": 60}
BUS_FALLBACK = {"speed_kmh": 45, "extra_min": 30}
FLIGHT_FALLBACK = {"speed_kmh": 600, "extra_min": 30}
FLIGHT_ONE_STOP_EXTRA_MIN = 120
FALLBACK_TOLERANCE_MIN = 1       # rounding slack when checking a flagged fallback value

# --- Attractions (5.5) -----------------------------------------------------

ATTRACTIONS_PER_CITY = (25, 40)
ATTRACTION_MAX_KM_FROM_CENTRE = 60
VISIT_MINUTES_RANGE = (20, 480)
TAGS_PER_ATTRACTION = (1, 3)
RATING_RANGE = (1.0, 5.0)
WEEKDAY_RANGE = (0, 6)           # 0 = Monday (section 3)
MIN_FREE_ATTRACTIONS = 5
MIN_ATTRACTIONS_PER_REQUIRED_TAG = 3

# Place types (5.5): default visit minutes, hours and closed weekdays when no source gives them.
PLACE_TYPES = {
    "monument": {"visit": 90, "open": "09:00", "close": "17:00", "closed": []},
    "museum": {"visit": 120, "open": "10:00", "close": "17:00", "closed": [0]},
    "temple": {"visit": 45, "open": "06:00", "close": "20:00", "closed": []},
    "viewpoint": {"visit": 30, "open": "06:00", "close": "18:00", "closed": []},
    "market": {"visit": 90, "open": "10:00", "close": "21:00", "closed": []},
    "beach": {"visit": 120, "open": "06:00", "close": "19:00", "closed": []},
    "activity": {"visit": 180, "open": "09:00", "close": "17:00", "closed": []},
}
# Other kinds map onto the seven types (5.5).
PLACE_TYPE_ALIASES = {
    "fort": "monument", "palace": "monument", "tomb": "monument", "ruins": "monument",
    "gallery": "museum", "zoo": "museum",
    "mosque": "temple", "church": "temple", "gurudwara": "temple", "ghat": "temple",
    "lake": "viewpoint", "garden": "viewpoint", "park": "viewpoint", "waterfall": "viewpoint",
    "mall": "market", "bazaar": "market",
    "trek": "activity", "rafting": "activity", "safari": "activity", "show": "activity",
}
FREE_BY_DEFAULT = ("temple", "viewpoint", "market", "beach")   # fee 0 when no source (5.5)
# Rating (5.5): OpenTripMap rate -> rating when there is no Wikipedia article.
OTM_RATE_TO_RATING = {1: 2.0, 2: 3.0, 3: 4.0}
RATING_SAME_PAGEVIEWS = 3.0

# City character -> tags that need >= MIN_ATTRACTIONS_PER_REQUIRED_TAG attractions (Plan §4)
REQUIRED_TAGS = {
    "JAI": ("history", "culture"),
    "AGR": ("history", "culture"),
    "HMP": ("history", "culture"),
    "MUN": ("nature", "relaxation"),
    "DJL": ("nature", "relaxation"),
    "RSH": ("nature", "adventure", "spiritual"),
    "GOA": ("relaxation", "nightlife", "nature"),
    "PDY": ("relaxation", "culture"),
    "DEL": ("history", "food", "shopping"),
    "BOM": ("food", "nightlife", "culture"),
    "BLR": ("food", "nightlife", "culture"),
    "CCU": ("food", "culture"),
    "HYD": ("food", "history"),
    "VNS": ("spiritual", "culture"),
    "MAA": ("food", "culture", "relaxation"),
}

# --- Hotels (5.6) ----------------------------------------------------------

HOTELS_PER_TIER = (2, 4)
HOTEL_MAX_KM_FROM_CENTRE = 25
PRICE_BANDS = {                  # per room per night, rupees
    "budget": (600, 2500),
    "mid": (2000, 6000),
    "premium": (5000, 20000),
}
# Warning (not error) when every hotel in a city lies within this distance of every other (Plan §4).
HOTEL_SPREAD_WARN_KM = 2.0

# --- Food (5.7) and local transport (5.8) ----------------------------------

FOOD_ROWS = COMFORT_LEVELS
LOCAL_CAPACITY = {"auto": 3, "cab": 4}

# --- IDs (section 3) -------------------------------------------------------

ATTRACTION_ID_PATTERN = r"^(?P<city>[A-Z]{3})-A-\d{2}$"
HOTEL_ID_PATTERN = r"^(?P<city>[A-Z]{3})-H-\d{2}$"
HUB_NODE_FORMAT = "{city}-HUB-{mode}"   # matrix node name for a hub (Plan §4)
HUB_NODE_PATTERN = r"^(?P<city>[A-Z]{3})-HUB-(train|bus|flight)$"

# --- Files (Plan §2.1) -----------------------------------------------------

VERSION_FILE = "VERSION"
CITIES_FILE = "cities.csv"
HUBS_FILE = "hubs.csv"
PAIRS_FILE = "city_pairs.csv"
FARES_FILE = "fare_rates.csv"
HOTELS_FILE = "hotels.csv"
FOOD_FILE = "food.csv"
LOCAL_FILE = "local_transport.csv"
ATTRACTIONS_DIR = "attractions"
MATRICES_DIR = "matrices"

VERSION_PATTERN = r"^\d+\.\d+$"
COMPILED_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
