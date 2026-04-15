# Blind Assistant – Setup & Run Guide

## Project Structure

```
blind_assistant/
├── config.py              # Shared settings (edit this first)
├── server.py              # ← Run on LAPTOP
├── detector.py            # YOLO + Depth (used by server)
├── motion_detector.py     # Frame-to-frame tracking (used by server)
├── gemini_narrator.py     # Gemini API (used by server)
├── pi_client.py           # ← Run on RASPBERRY PI
├── requirements_laptop.txt
└── requirements_pi.txt
```

---

## Step 1 – Edit config.py

Open `config.py` and change:

| Setting | What to set |
|---|---|
| `SERVER_IP` | Your laptop's local IP (see below how to find it) |
| `GEMINI_API_KEY` | Your Gemini API key from https://aistudio.google.com |

**Find your laptop's local IP:**
- Windows: open Command Prompt → `ipconfig` → look for IPv4 Address
- macOS/Linux: open Terminal → `ifconfig` or `ip a` → look for `inet` under your Wi-Fi interface (e.g. `192.168.1.xxx`)

Both the Pi and the laptop must be on the **same Wi-Fi network**.

---

## Step 2 – Install dependencies on LAPTOP

```bash
# (Recommended) create a virtual environment first
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows

pip install -r requirements_laptop.txt
```

### If you have an NVIDIA GPU (faster depth estimation)
After the above, also run:
```bash
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```
Replace `cu121` with your CUDA version (check with `nvcc --version`).

### macOS Apple Silicon (M1/M2/M3)
```bash
pip install torch torchvision          # MPS backend is auto-detected
```

---

## Step 3 – Install dependencies on RASPBERRY PI

```bash
# Update system packages first
sudo apt update && sudo apt upgrade -y

# Required system libraries for OpenCV and TTS
sudo apt install -y python3-pip python3-venv \
    libespeak1 espeak \
    libgl1 libglib2.0-0

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

pip install -r requirements_pi.txt
```

### Enable the Pi camera (Pi Camera Module only)
```bash
sudo raspi-config
# → Interface Options → Camera → Enable → Reboot
```
If using a USB webcam, no extra steps needed.

---

## Step 4 – Get a Gemini API key

1. Go to https://aistudio.google.com
2. Sign in with a Google account
3. Click "Get API key" → "Create API key"
4. Copy the key into `config.py` → `GEMINI_API_KEY`

The free tier is enough for this project (15 requests/minute).

---

## Step 5 – Run the project

### On the LAPTOP (start this first):
```bash
source venv/bin/activate        # activate virtual environment
python server.py
```
You should see:
```
[detector] Loading models – this takes ~30s on first run …
[detector] Models ready.
[server] Listening on port 5050 …
[server] Waiting for Raspberry Pi connection …
```

### On the RASPBERRY PI (start after the laptop server is ready):
```bash
source venv/bin/activate
python pi_client.py
```
You should hear: **"Vision assistant is ready."**

---

## How it works (quick summary)

```
Every 5 seconds:
  Pi  →  captures frame from camera
  Pi  →  sends frame over Wi-Fi to laptop
  Laptop  →  runs YOLOv8 (detect objects + bounding boxes)
  Laptop  →  runs Depth Anything V2 (estimate distances)
  Laptop  →  runs MotionDetector (compare to previous frame)
  Laptop  →  sends enriched data to Gemini for natural language
  Laptop  →  returns spoken sentence to Pi
  Pi  →  speaks the sentence through earphone/speaker
```

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionRefusedError` on Pi | Make sure `server.py` is running on the laptop first |
| `Camera not found` on Pi | Check `cv2.VideoCapture(0)` index; try `1` for USB cams |
| Very slow inference | Switch to `yolov8n.pt` (nano) and `Depth-Anything-V2-Small-hf` in config |
| Gemini `API key not valid` | Double-check the key in config.py; ensure billing/free tier is active |
| TTS not working on Pi | Run `sudo apt install espeak` and reboot |
| Models download slowly | First run downloads ~500 MB; run on good internet once |

---

## Dependency Reference

### Laptop packages

| Package | Purpose |
|---|---|
| `ultralytics` | YOLOv8 object detection |
| `transformers` | Depth Anything V2 via HuggingFace |
| `torch` + `torchvision` | Deep learning backend |
| `opencv-python` | Image processing |
| `Pillow` | Image format conversion |
| `numpy` | Array math |
| `google-generativeai` | Gemini API client |

### Pi packages

| Package | Purpose |
|---|---|
| `opencv-python-headless` | Camera capture (no GUI needed) |
| `pyttsx3` | Text-to-speech engine |
| `espeak` (system) | TTS voice backend for pyttsx3 |
