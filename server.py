# ─────────────────────────────────────────────
#  server.py  –  main processing server
#  Runs on: LAPTOP
#  Start with:  python server.py
# ─────────────────────────────────────────────

import socket
import struct
import pickle

import cv2
import numpy as np

from detector        import get_detections
from motion_detector import MotionDetector
from gemini_narrator import narrate
import config

# MotionDetector persists across requests so it remembers the previous frame
_motion = MotionDetector()


def _recv_all(conn: socket.socket, n: int) -> bytes:
    """Reliably receive exactly n bytes."""
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(min(4096, n - len(buf)))
        if not chunk:
            break
        buf += chunk
    return buf


def handle_client(conn: socket.socket):
    try:
        # 1. Read frame size (4-byte big-endian unsigned long)
        raw_size = _recv_all(conn, 4)
        if len(raw_size) < 4:
            return
        size  = struct.unpack(">L", raw_size)[0]

        # 2. Read the serialised frame
        data  = _recv_all(conn, size)
        frame = pickle.loads(data)   # numpy BGR array

        # 3. Object detection + depth
        detections = get_detections(frame)
        print(f"[server] {len(detections)} object(s) detected")

        # 4. Motion analysis (compares to previous frame)
        motion_results = _motion.update(detections)

        # 5. Merge detection + motion into enriched list
        enriched = []
        for det, mot in zip(detections, motion_results):
            enriched.append({
                **det,
                "speed":          mot.speed,
                "direction":      mot.direction,
                "is_approaching": mot.is_approaching,
            })

        # 6. Generate natural language alert via Gemini
        narration = narrate(enriched)
        print(f"[server] → {narration}")

        # 7. Send narration text back to Pi
        conn.sendall(narration.encode("utf-8"))

    except Exception as e:
        print(f"[server] ERROR: {e}")
        try:
            conn.sendall(b"Processing error, please wait.")
        except Exception:
            pass
    finally:
        conn.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", config.SERVER_PORT))
    server.listen(5)
    print(f"[server] Listening on port {config.SERVER_PORT} …")
    print("[server] Waiting for Raspberry Pi connection …\n")

    while True:
        conn, addr = server.accept()
        print(f"[server] Connection from {addr}")
        handle_client(conn)


if __name__ == "__main__":
    main()
