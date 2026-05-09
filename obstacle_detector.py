# =============================================================================
# obstacle_detector.py — Obstacle Detection
# =============================================================================
# Every OBSTACLE_CHECK_INTERVAL seconds:
#   1. Captures a frame from the USB webcam
#   2. Runs YOLOv8 to detect objects + bounding boxes
#   3. Runs Depth Anything V2 to estimate distances (metres)
#   4. Checks if any object is in the centre zone AND closer than threshold
#   5. If yes → calls Gemini to produce a natural-language alert sentence
#   6. Speaks the alert BEFORE the next navigation instruction
#
# Direction zones (horizontal thirds of frame):
#   Left third   → "to your left"
#   Centre third → "straight ahead"  ← triggers priority alert
#   Right third  → "to your right"
# =============================================================================

import cv2
import numpy as np
import time
from PIL import Image
import config


class ObstacleDetector:
    """Manages camera capture, detection, depth, and alert generation."""

    def __init__(self):
        self._depth_pipe   = None
        self._yolo         = None
        self._gemini       = None
        self._last_capture = 0.0
        self._pending_alert: str | None = None   # Set when a centre obstacle found
        self._models_loaded = False

    # ── Public API ───────────────────────────────────────────────────────────

    def load_models(self):
        """Load YOLO and Depth models once at startup (can be slow first run)."""
        print("[Obstacle] Loading YOLOv8 model...")
        from ultralytics import YOLO
        self._yolo = YOLO(config.YOLO_MODEL)

        print("[Obstacle] Loading Depth Anything V2 model...")
        from transformers import pipeline as hf_pipeline
        model_id = f"depth-anything/Depth-Anything-V2-{config.DEPTH_MODEL_SIZE}-hf"
        self._depth_pipe = hf_pipeline(
            task="depth-estimation",
            model=model_id,
            device="cpu",   # change to 0 for CUDA GPU
        )

        print("[Obstacle] Loading Gemini client...")
        import google.generativeai as genai
        genai.configure(api_key=config.GEMINI_API_KEY)
        self._gemini = genai.GenerativeModel("gemini-1.5-flash")

        self._models_loaded = True
        print("[Obstacle] All models ready.")

    def tick(self) -> str | None:
        """Call this in the main loop at any frequency.

        Returns:
            A spoken alert string if a centre-zone obstacle is detected,
            otherwise None.
        """
        if not self._models_loaded:
            return None

        now = time.time()
        if now - self._last_capture < config.OBSTACLE_CHECK_INTERVAL:
            return None
        self._last_capture = now

        frame_bgr = self._capture_frame()
        if frame_bgr is None:
            return None

        detections   = self._run_yolo(frame_bgr)
        if not detections:
            return None

        depth_map    = self._run_depth(frame_bgr)
        annotated    = self._annotate_frame(frame_bgr, detections, depth_map)
        alert        = self._check_centre_obstacles(detections, depth_map, frame_bgr.shape[1])

        # Optionally save annotated frame for debugging
        # cv2.imwrite("last_obstacle_frame.jpg", annotated)

        return alert   # None if no critical obstacle

    # ── Camera ───────────────────────────────────────────────────────────────

    def _capture_frame(self) -> np.ndarray | None:
        # ── LAPTOP / PI (USB webcam): identical for both ──────────────────
        cap = cv2.VideoCapture(config.CAMERA_INDEX)
        if not cap.isOpened():
            print("[Obstacle] Cannot open camera.")
            return None
        ret, frame = cap.read()
        cap.release()
        return frame if ret else None

    # ── YOLO ─────────────────────────────────────────────────────────────────

    def _run_yolo(self, frame_bgr: np.ndarray) -> list[dict]:
        results = self._yolo(frame_bgr, conf=config.YOLO_CONFIDENCE, verbose=False)[0]
        detections = []
        for box in results.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            label = results.names[int(box.cls[0])]
            conf  = float(box.conf[0])
            detections.append(dict(label=label, conf=conf,
                                   x1=x1, y1=y1, x2=x2, y2=y2))
        return detections

    # ── Depth Anything V2 ────────────────────────────────────────────────────

    def _run_depth(self, frame_bgr: np.ndarray) -> np.ndarray:
        pil_image = Image.fromarray(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        result    = self._depth_pipe(pil_image)
        rel_depth = result["predicted_depth"].squeeze().numpy()
        rel_depth = np.clip(rel_depth, 1e-6, None)
        depth_m   = config.DEPTH_SCALE_FACTOR / rel_depth

        # Resize to match frame
        h, w = frame_bgr.shape[:2]
        if depth_m.shape != (h, w):
            depth_m = cv2.resize(depth_m, (w, h), interpolation=cv2.INTER_LINEAR)
        return depth_m

    # ── Distance per bounding box ─────────────────────────────────────────────

    @staticmethod
    def _box_distance(depth_m: np.ndarray, x1, y1, x2, y2,
                      percentile: float = 20.0) -> float:
        h, w = depth_m.shape
        roi  = depth_m[max(0, y1):min(h, y2), max(0, x1):min(w, x2)]
        if roi.size == 0:
            return float("nan")
        return float(np.percentile(roi, percentile))

    # ── Direction zone classification ─────────────────────────────────────────

    @staticmethod
    def _direction(cx: int, frame_width: int) -> str:
        third = frame_width * config.CENTRE_ZONE_FRACTION
        if cx < third:
            return "left"
        elif cx > frame_width - third:
            return "right"
        else:
            return "centre"

    # ── Centre obstacle check ─────────────────────────────────────────────────

    def _check_centre_obstacles(
        self,
        detections: list[dict],
        depth_m:    np.ndarray,
        frame_width: int,
    ) -> str | None:
        """Return a Gemini-generated alert if a centre obstacle is within threshold."""

        close_centre = []
        all_context  = []

        for det in detections:
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
            cx   = (x1 + x2) // 2
            dist = self._box_distance(depth_m, x1, y1, x2, y2)
            dirn = self._direction(cx, frame_width)

            all_context.append({
                "label":     det["label"],
                "distance":  round(dist, 1),
                "direction": dirn,
            })

            if (
                dirn == "centre"
                and not np.isnan(dist)
                and dist <= config.OBSTACLE_DISTANCE_THRESHOLD
            ):
                close_centre.append({
                    "label":    det["label"],
                    "distance": round(dist, 1),
                })

        if not close_centre:
            return None

        return self._gemini_alert(close_centre, all_context)

    # ── Gemini NL alert ───────────────────────────────────────────────────────

    def _gemini_alert(
        self,
        centre_obstacles: list[dict],
        all_objects:      list[dict],
    ) -> str:
        """Ask Gemini to generate a concise spoken alert for a blind user."""

        centre_desc = ", ".join(
            f"{o['label']} at {o['distance']} metres"
            for o in centre_obstacles
        )
        all_desc = "; ".join(
            f"{o['label']} {o['distance']}m to your {o['direction']}"
            for o in all_objects
        )

        prompt = (
            "You are an AI assistant helping a blind person navigate safely. "
            "Generate a single short spoken warning (max 2 sentences) that is "
            "calm, clear, and actionable. "
            "The following obstacle(s) are directly ahead and very close: "
            f"{centre_desc}. "
            f"Full scene context: {all_desc}. "
            "Tell the user to stop or slow down and what is in their path. "
            "Do not add any preamble, greetings, or asterisks."
        )

        try:
            response = self._gemini.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"[Obstacle] Gemini error: {e}")
            # Fallback plain alert
            labels = ", ".join(o["label"] for o in centre_obstacles)
            dists  = ", ".join(str(o["distance"]) for o in centre_obstacles)
            return f"Warning! {labels} directly ahead, approximately {dists} metres away. Please slow down."

    # ── Annotated frame (for debugging / simulation) ──────────────────────────

    def _annotate_frame(
        self,
        frame_bgr:  np.ndarray,
        detections: list[dict],
        depth_m:    np.ndarray,
    ) -> np.ndarray:
        canvas    = frame_bgr.copy()
        font      = cv2.FONT_HERSHEY_DUPLEX
        fscale    = 0.75
        thickness = 2
        fw        = frame_bgr.shape[1]

        for det in detections:
            x1, y1, x2, y2 = det["x1"], det["y1"], det["x2"], det["y2"]
            dist = self._box_distance(depth_m, x1, y1, x2, y2)
            dirn = self._direction((x1 + x2) // 2, fw)

            # Colour by distance
            if dist < 3:
                colour = (0, 0, 255)
            elif dist < 6:
                colour = (0, 140, 255)
            elif dist < 10:
                colour = (0, 255, 255)
            elif dist < 20:
                colour = (0, 255, 0)
            else:
                colour = (255, 255, 0)

            cv2.rectangle(canvas, (x1, y1), (x2, y2), colour, 2, cv2.LINE_AA)

            dist_str = f"~{dist:.1f}m | {dirn}" if not np.isnan(dist) else "? | " + dirn
            text     = f"{det['label']} {det['conf']:.0%} | {dist_str}"
            (tw, th), bl = cv2.getTextSize(text, font, fscale, 1)
            cv2.rectangle(canvas, (x1, y1 - th - bl - 6), (x1 + tw + 6, y1), colour, -1)
            cv2.putText(canvas, text, (x1 + 3, y1 - bl - 2),
                        font, fscale, (255, 255, 255), thickness, cv2.LINE_AA)

        return canvas
