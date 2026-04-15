# ─────────────────────────────────────────────
#  detector.py  –  YOLO + Depth Anything V2
#  Runs on: LAPTOP (server)
# ─────────────────────────────────────────────

import cv2
import torch
import numpy as np
from PIL import Image
from ultralytics import YOLO
from transformers import pipeline as hf_pipeline
import config

print("[detector] Loading models – this takes ~30s on first run …")

yolo = YOLO(config.YOLO_MODEL)

depth_pipe = hf_pipeline(
    task="depth-estimation",
    model=config.DEPTH_MODEL,
    device="cuda" if torch.cuda.is_available() else "cpu",
)

print("[detector] Models ready.")


def get_detections(frame_bgr: np.ndarray) -> list[dict]:
    """
    Run YOLO + depth on a single BGR frame.

    Returns a list of dicts:
        label        – YOLO class name
        confidence   – float 0-1
        distance_m   – estimated depth (relative units; treat as ~metres)
        position     – "to your left" | "ahead" | "to your right"
        bbox         – (x1, y1, x2, y2) in pixels
    """
    h, w = frame_bgr.shape[:2]
    image_rgb  = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_image  = Image.fromarray(image_rgb)

    # ── YOLO ──────────────────────────────────────────────────────
    yolo_results = yolo(frame_bgr, verbose=False)[0]

    # ── Depth ─────────────────────────────────────────────────────
    depth_output = depth_pipe(pil_image)
    depth_map    = np.array(depth_output["depth"], dtype=np.float32)

    detections = []
    for box in yolo_results.boxes:
        conf  = float(box.conf[0])
        if conf < config.MIN_CONFIDENCE:
            continue

        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        label = yolo.names[int(box.cls[0])]

        # Sample depth from inner 50 % of bounding box (avoids edge noise)
        cx1 = x1 + (x2 - x1) // 4
        cy1 = y1 + (y2 - y1) // 4
        cx2 = x2 - (x2 - x1) // 4
        cy2 = y2 - (y2 - y1) // 4
        roi        = depth_map[cy1:cy2, cx1:cx2]
        dist       = float(np.median(roi))

        if dist > config.MAX_DISTANCE_ALERT:
            continue

        # Horizontal position bucket
        center_x = (x1 + x2) / 2
        if center_x < w * 0.35:
            position = "to your left"
        elif center_x > w * 0.65:
            position = "to your right"
        else:
            position = "ahead"

        detections.append({
            "label":      label,
            "confidence": round(conf, 2),
            "distance_m": round(dist, 1),
            "position":   position,
            "bbox":       (x1, y1, x2, y2),
        })

    # Closest objects first
    detections.sort(key=lambda d: d["distance_m"])
    return detections
