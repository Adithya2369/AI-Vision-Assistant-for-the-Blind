# ─────────────────────────────────────────────
#  config.py  –  shared settings for both sides
# ─────────────────────────────────────────────

# --- Network ---
SERVER_IP   = "192.168.1.100"   # <-- change to your laptop's local IP
SERVER_PORT = 5050

# --- Capture ---
CAPTURE_INTERVAL = 5            # seconds between frames

# --- Models ---
YOLO_MODEL  = "yolov8n.pt"      # yolov8s.pt / yolov8m.pt for better accuracy
DEPTH_MODEL = "depth-anything/Depth-Anything-V2-Small-hf"  # or Large

# --- Detection thresholds ---
MIN_CONFIDENCE    = 0.40        # ignore detections below this
MAX_DISTANCE_ALERT = 20         # metres  – ignore objects beyond this

# --- Gemini ---
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"   # <-- paste your key here
GEMINI_MODEL   = "gemini-1.5-flash"

# --- TTS ---
TTS_RATE = 160                  # words per minute
