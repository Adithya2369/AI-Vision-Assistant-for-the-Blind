# =============================================================================
# config.py — Central Configuration
# AI Vision Assistant for the Blind
# =============================================================================
# Edit this file to customise all system behaviour.
# No other file hardcodes values.
# =============================================================================

# -----------------------------------------------------------------------------
# GEMINI API
# -----------------------------------------------------------------------------
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE"   # <-- Paste your Gemini API key

# -----------------------------------------------------------------------------
# CITY / LOCATION SETTINGS
# -----------------------------------------------------------------------------
DEFAULT_CITY        = "Hyderabad"              # Used for geocoding bias & city check
DEFAULT_CITY_FULL   = "Hyderabad, India"       # Full name for Nominatim queries
FALLBACK_LAT        = 17.3850                  # Hyderabad fallback latitude
FALLBACK_LON        = 78.4867                  # Hyderabad fallback longitude

# Hyderabad bounding box (used as secondary city-boundary check)
CITY_BBOX = {
    "lat_min": 17.20,
    "lat_max": 17.60,
    "lon_min": 78.25,
    "lon_max": 78.70,
}

# -----------------------------------------------------------------------------
# ROUTING (OSRM — fully free, no key needed)
# -----------------------------------------------------------------------------
OSRM_BASE_URL       = "http://router.project-osrm.org"
OSRM_PROFILE        = "foot"                   # "foot" = walking routes

# -----------------------------------------------------------------------------
# NAVIGATION THRESHOLDS (metres)
# -----------------------------------------------------------------------------
TURN_ANNOUNCE_DISTANCE  = 20    # Speak turn instruction when this close to waypoint
ARRIVAL_DISTANCE        = 15    # Announce arrival when this close to destination
REROUTE_THRESHOLD       = 80    # Re-route if this far off any remaining waypoint
MAX_REROUTES            = 3     # Maximum re-routes per journey
GPS_POLL_INTERVAL       = 2     # Seconds between GPS position reads

# -----------------------------------------------------------------------------
# OBSTACLE DETECTION THRESHOLDS
# -----------------------------------------------------------------------------
OBSTACLE_DISTANCE_THRESHOLD = 3.0   # Metres — alert if object closer than this
OBSTACLE_CHECK_INTERVAL     = 5     # Seconds between camera captures
DEPTH_SCALE_FACTOR          = 10.0  # Scale for Depth Anything V2 → metres
YOLO_CONFIDENCE             = 0.4   # YOLO detection confidence threshold
YOLO_MODEL                  = "yolov8n.pt"   # nano = fastest; s/m/l/x = more accurate
DEPTH_MODEL_SIZE            = "Small"         # "Small" or "Large"

# Frame zone split for direction (left / centre / right thirds)
# Obstacle in centre zone = "straight ahead" → triggers priority alert
CENTRE_ZONE_FRACTION = 1 / 3     # middle third of frame width

# -----------------------------------------------------------------------------
# SPEECH / VOICE
# -----------------------------------------------------------------------------
# TTS: gTTS (online, natural-sounding)
TTS_LANG            = "en"
TTS_SLOW            = False

# STT: SpeechRecognition + Google STT
RECORD_TIMEOUT      = 5          # Max seconds to wait for speech start
PHRASE_TIME_LIMIT   = 10         # Max seconds for a single utterance
STT_LANGUAGE        = "en-US"

# -----------------------------------------------------------------------------
# GPS SOURCE
# -----------------------------------------------------------------------------
# LAPTOP  : uses system/USB GPS; falls back to Hyderabad if none found
# PI      : expects USB GPS dongle at the path below

# ── RASPBERRY PI only ──────────────────────────────────────────────────────
# GPS_SERIAL_PORT  = "/dev/ttyUSB0"   # Uncomment for Pi USB GPS dongle
# GPS_BAUD_RATE    = 9600             # Uncomment for Pi USB GPS dongle
# ── END PI SECTION ─────────────────────────────────────────────────────────

# -----------------------------------------------------------------------------
# CAMERA SOURCE
# -----------------------------------------------------------------------------
# Both laptop and Pi use USB webcam.
# 0 = first USB camera. Change to 1, 2… if your webcam is on a different index.
CAMERA_INDEX        = 0

# -----------------------------------------------------------------------------
# SIMULATION FLAGS (for testing without hardware)
# -----------------------------------------------------------------------------
# Run  `python simulate_nav.py`          for navigation console simulation
# Run  `python simulate_detect.py --image test.jpg`  for detection simulation
SIM_NAV_PRINT_ONLY  = True       # simulate_nav: print directions, no GPS/voice
