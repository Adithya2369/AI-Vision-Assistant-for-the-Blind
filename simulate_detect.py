# =============================================================================
# simulate_detect.py — Object Detection + Distance Simulation
# =============================================================================
# Tests YOLOv8 + Depth Anything V2 on a static image.
# Saves annotated image with bounding boxes and estimated distances.
# No audio output — results are visual + console only.
#
# Usage:
#   python simulate_detect.py                        (uses test.jpg by default)
#   python simulate_detect.py --image my_photo.jpg
#   python simulate_detect.py --image test.jpg --output result.jpg
#   python simulate_detect.py --image test.jpg --model Large --scale 8.0
#   python simulate_detect.py --image test.jpg --yolo-model yolov8s.pt
# =============================================================================

import argparse
import os
import sys
import numpy as np
import cv2
from PIL import Image
import config


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Simulate obstacle detection on a static image."
    )
    parser.add_argument(
        "--image", default="test.jpg",
        help="Path to input image (default: test.jpg)"
    )
    parser.add_argument(
        "--output", default=None,
        help="Output annotated image path (default: <input>_result.<ext>)"
    )
    parser.add_argument(
        "--depth-output", default=None,
        help="Output depth visualisation path (default: <input>_depth.<ext>)"
    )
    parser.add_argument(
        "--model", choices=["Small", "Large"], default=config.DEPTH_MODEL_SIZE,
        help=f"Depth Anything V2 size (default: {config.DEPTH_MODEL_SIZE})"
    )
    parser.add_argument(
        "--scale", type=float, default=config.DEPTH_SCALE_FACTOR,
        help=f"Depth scale factor (default: {config.DEPTH_SCALE_FACTOR}). "
             "Increase for outdoor/large scenes, decrease for indoor/close-up."
    )
    parser.add_argument(
        "--yolo-model", default=config.YOLO_MODEL,
        help=f"YOLOv8 weights file (default: {config.YOLO_MODEL})"
    )
    parser.add_argument(
        "--conf", type=float, default=config.YOLO_CONFIDENCE,
        help=f"YOLO confidence threshold (default: {config.YOLO_CONFIDENCE})"
    )
    return parser.parse_args()


# ── Depth model ───────────────────────────────────────────────────────────────

def load_depth_model(size: str):
    from transformers import pipeline as hf_pipeline
    model_id = f"depth-anything/Depth-Anything-V2-{size}-hf"
    print(f"[Depth] Loading '{model_id}' (first run downloads weights)...")
    pipe = hf_pipeline(
        task="depth-estimation",
        model=model_id,
        device="cpu",   # Change to 0 for CUDA GPU
    )
    print("[Depth] Model ready.")
    return pipe


def estimate_depth(pipe, image_path: str, scale: float) -> np.ndarray:
    pil_image = Image.open(image_path).convert("RGB")
    result    = pipe(pil_image)
    rel_depth = result["predicted_depth"].squeeze().numpy()
    rel_depth = np.clip(rel_depth, 1e-6, None)
    depth_m   = scale / rel_depth
    print(f"[Depth] Map shape : {depth_m.shape}")
    print(f"[Depth] Range     : {depth_m.min():.2f} m – {depth_m.max():.2f} m")
    return depth_m


# ── YOLO detection ────────────────────────────────────────────────────────────

def detect_objects(image_path: str, model_name: str, conf_thresh: float) -> list[dict]:
    from ultralytics import YOLO
    print(f"[YOLO] Loading '{model_name}'...")
    yolo    = YOLO(model_name)
    results = yolo(image_path, conf=conf_thresh, verbose=False)[0]
    detections = []
    for box in results.boxes:
        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
        label = results.names[int(box.cls[0])]
        conf  = float(box.conf[0])
        detections.append(dict(label=label, conf=conf,
                               x1=x1, y1=y1, x2=x2, y2=y2))
    print(f"[YOLO] Detected {len(detections)} object(s).")
    return detections


# ── Per-box distance ──────────────────────────────────────────────────────────

def box_distance(depth_m: np.ndarray, x1, y1, x2, y2,
                 percentile: float = 20.0) -> float:
    h, w = depth_m.shape
    roi  = depth_m[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
    if roi.size == 0:
        return float("nan")
    return float(np.percentile(roi, percentile))


# ── Direction zone ────────────────────────────────────────────────────────────

def direction_zone(cx: int, frame_width: int) -> str:
    third = frame_width * config.CENTRE_ZONE_FRACTION
    if cx < third:
        return "LEFT"
    elif cx > frame_width - third:
        return "RIGHT"
    else:
        return "CENTRE ⚠"


# ── Draw annotated image ──────────────────────────────────────────────────────

def draw_results(image_bgr: np.ndarray, detections: list[dict],
                 depth_m: np.ndarray) -> np.ndarray:
    canvas = image_bgr.copy()
    font   = cv2.FONT_HERSHEY_DUPLEX
    fw     = image_bgr.shape[1]

    # Draw zone lines (visual reference)
    third = int(fw * config.CENTRE_ZONE_FRACTION)
    cv2.line(canvas, (third, 0), (third, canvas.shape[0]), (200, 200, 200), 1)
    cv2.line(canvas, (fw - third, 0), (fw - third, canvas.shape[0]), (200, 200, 200), 1)
    cv2.putText(canvas, "LEFT",   (5, 20),         font, 0.5, (200, 200, 200), 1)
    cv2.putText(canvas, "CENTRE", (third + 5, 20), font, 0.5, (200, 200, 200), 1)
    cv2.putText(canvas, "RIGHT",  (fw - third + 5, 20), font, 0.5, (200, 200, 200), 1)

    for det in detections:
        x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
        cx   = (x1 + x2) // 2
        dist = box_distance(depth_m, x1, y1, x2, y2)
        zone = direction_zone(cx, fw)

        # Colour by distance
        if np.isnan(dist):
            colour = (128, 128, 128)
        elif dist < 3:
            colour = (0, 0, 255)       # Red — danger
        elif dist < 6:
            colour = (0, 140, 255)     # Orange — caution
        elif dist < 10:
            colour = (0, 255, 255)     # Yellow
        elif dist < 20:
            colour = (0, 255, 0)       # Green
        else:
            colour = (255, 255, 0)     # Cyan

        # Thicker box for centre-zone close obstacles
        box_thick = 4 if ("CENTRE" in zone and not np.isnan(dist) and dist < config.OBSTACLE_DISTANCE_THRESHOLD) else 2
        cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, box_thick, cv2.LINE_AA)

        dist_str = f"~{dist:.1f}m" if not np.isnan(dist) else "?"
        text     = f"{det['label']} {det['conf']:.0%} | {dist_str} | {zone}"

        (tw, th), bl = cv2.getTextSize(text, font, 0.65, 1)
        cv2.rectangle(canvas, (x1, y1 - th - bl - 6), (x1 + tw + 6, y1), colour, -1)
        cv2.putText(canvas, text, (x1 + 3, y1 - bl - 2),
                    font, 0.65, (255, 255, 255), 2, cv2.LINE_AA)

    return canvas


# ── Depth visualisation ───────────────────────────────────────────────────────

def save_depth_vis(depth_m: np.ndarray, output_path: str):
    d_norm   = cv2.normalize(depth_m, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    d_colour = cv2.applyColorMap(255 - d_norm, cv2.COLORMAP_INFERNO)
    cv2.imwrite(output_path, d_colour)
    print(f"[Output] Depth visualisation → {output_path}")


# ── Console summary ───────────────────────────────────────────────────────────

def print_summary(detections: list[dict], depth_m: np.ndarray, frame_width: int):
    threshold = config.OBSTACLE_DISTANCE_THRESHOLD
    print("\n── Detection Summary ──────────────────────────────────────────────")
    print(f"  {'#':<4} {'Label':<22} {'Conf':>6}  {'Distance':>10}  {'Zone':<12}  Alert?")
    print(f"  {'─'*4} {'─'*22} {'─'*6}  {'─'*10}  {'─'*12}  {'─'*6}")

    for i, det in enumerate(detections, 1):
        x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
        cx   = (x1 + x2) // 2
        dist = box_distance(depth_m, x1, y1, x2, y2)
        zone = direction_zone(cx, frame_width)
        dist_str = f"~{dist:.2f} m" if not np.isnan(dist) else "unknown"
        is_centre = "CENTRE" in zone
        alert = "YES ⚠" if (is_centre and not np.isnan(dist) and dist <= threshold) else "no"
        print(f"  {i:<4} {det['label']:<22} {det['conf']:>5.0%}  {dist_str:>10}  {zone:<12}  {alert}")

    print("──────────────────────────────────────────────────────────────────\n")

    # Summary of critical obstacles
    critical = [
        det for det in detections
        if "CENTRE" in direction_zone((det["x1"] + det["x2"]) // 2, frame_width)
        and not np.isnan(box_distance(depth_m, det["x1"], det["y1"], det["x2"], det["y2"]))
        and box_distance(depth_m, det["x1"], det["y1"], det["x2"], det["y2"]) <= threshold
    ]
    if critical:
        labels = ", ".join(d["label"] for d in critical)
        print(f"  ⚠  CRITICAL: {labels} directly ahead within {threshold} m — would trigger voice alert.\n")
    else:
        print(f"  ✓  No critical centre-zone obstacles within {threshold} m.\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    args = parse_args()

    if not os.path.isfile(args.image):
        sys.exit(f"[Error] Image not found: '{args.image}'\n"
                 f"  Place a test image named 'test.jpg' in the same folder, or pass --image <path>")

    base, ext    = os.path.splitext(args.image)
    out_path     = args.output      or f"{base}_result{ext}"
    depth_path   = args.depth_output or f"{base}_depth{ext}"

    image_bgr = cv2.imread(args.image)
    if image_bgr is None:
        sys.exit(f"[Error] Could not read image: '{args.image}'")

    h, w = image_bgr.shape[:2]
    print(f"[Info] Image: {args.image}  ({w}×{h})")

    # ── Depth estimation ──────────────────────────────────────────────────
    depth_pipe = load_depth_model(args.model)
    depth_m    = estimate_depth(depth_pipe, args.image, args.scale)

    if depth_m.shape != (h, w):
        depth_m = cv2.resize(depth_m, (w, h), interpolation=cv2.INTER_LINEAR)

    # ── Object detection ──────────────────────────────────────────────────
    detections = detect_objects(args.image, args.yolo_model, args.conf)

    # ── Draw + save ───────────────────────────────────────────────────────
    annotated = draw_results(image_bgr, detections, depth_m)
    cv2.imwrite(out_path, annotated)
    print(f"[Output] Annotated image      → {out_path}")
    save_depth_vis(depth_m, depth_path)

    # ── Console summary ───────────────────────────────────────────────────
    print_summary(detections, depth_m, w)


if __name__ == "__main__":
    main()
