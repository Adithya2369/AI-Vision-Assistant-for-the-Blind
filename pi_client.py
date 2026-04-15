# ─────────────────────────────────────────────
#  pi_client.py  –  capture + send + speak
#  Runs on: RASPBERRY PI
#  Start with:  python pi_client.py
# ─────────────────────────────────────────────

import cv2
import socket
import struct
import pickle
import time
import sys

import pyttsx3
import config


# ── TTS setup ─────────────────────────────────────────────────────
_tts = pyttsx3.init()
_tts.setProperty("rate", config.TTS_RATE)

def speak(text: str):
    print(f"[pi] Speaking: {text}")
    _tts.say(text)
    _tts.runAndWait()


# ── Socket helpers ─────────────────────────────────────────────────
def send_frame_get_narration(frame) -> str:
    """Serialise frame, send to laptop, return narration string."""
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.settimeout(30)           # seconds — adjust if inference is slow
    client.connect((config.SERVER_IP, config.SERVER_PORT))

    data = pickle.dumps(frame)
    size = struct.pack(">L", len(data))
    client.sendall(size + data)

    # Read response until server closes connection
    response = b""
    while True:
        try:
            chunk = client.recv(4096)
            if not chunk:
                break
            response += chunk
        except socket.timeout:
            break

    client.close()
    return response.decode("utf-8").strip()


# ── Main loop ──────────────────────────────────────────────────────
def main():
    # Use 0 for the default/Pi camera; change to 1 if you have a USB cam
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        speak("Camera not found. Please check the connection.")
        sys.exit(1)

    # Optional: set resolution (lower = faster transfer)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    speak("Vision assistant is ready.")
    print(f"[pi] Sending frames to {config.SERVER_IP}:{config.SERVER_PORT} "
          f"every {config.CAPTURE_INTERVAL}s")

    while True:
        ret, frame = cap.read()
        if not ret:
            speak("Camera read error.")
            time.sleep(2)
            continue

        try:
            narration = send_frame_get_narration(frame)
            if narration:
                speak(narration)
        except ConnectionRefusedError:
            speak("Cannot reach processing server. Retrying.")
            print("[pi] Connection refused – is server.py running on the laptop?")
        except Exception as e:
            print(f"[pi] ERROR: {e}")
            speak("Processing error. Retrying.")

        time.sleep(config.CAPTURE_INTERVAL)

    cap.release()


if __name__ == "__main__":
    main()
