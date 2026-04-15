# ─────────────────────────────────────────────
#  motion_detector.py  –  frame-to-frame tracking
#  Runs on: LAPTOP (server)
# ─────────────────────────────────────────────

import time
import numpy as np
from dataclasses import dataclass
from typing import Optional
import config


@dataclass
class _Tracked:
    label:     str
    center:    tuple   # (cx, cy) in pixels
    bbox_area: float   # width × height in pixels²
    timestamp: float


@dataclass
class MotionResult:
    label:         str
    distance_m:    float
    position:      str
    confidence:    float
    speed:         str   # "stationary" | "slow" | "fast" | "unknown"
    direction:     str   # "approaching you" | "moving away" | "moving left" |
                         # "moving right" | "stationary" | "unknown"
    is_approaching: bool


class MotionDetector:
    """
    Compares current-frame detections against the previous frame to estimate
    velocity and whether each object is approaching the camera.

    Match strategy: same label + closest Euclidean centre distance within
    MATCH_DISTANCE pixels.  If no match exists (new object) the result is
    tagged "unknown".
    """

    SPEED_SLOW      = 10    # px / s  — below this → stationary
    SPEED_MODERATE  = 40    # px / s  — above this → fast
    APPROACH_THRESH = 0.15  # bbox area must grow > 15 % to count as approaching
    MATCH_DISTANCE  = 120   # px      — max centre-to-centre for same-object match

    def __init__(self):
        self._prev:  list[_Tracked] = []
        self._prev_t: Optional[float] = None

    # ── public ────────────────────────────────────────────────────
    def update(self, detections: list[dict]) -> list[MotionResult]:
        """
        Call once per frame with the list from detector.get_detections().
        Returns a parallel list of MotionResult objects.
        """
        now = time.time()
        dt  = (now - self._prev_t) if self._prev_t else config.CAPTURE_INTERVAL
        dt  = max(dt, 0.1)          # guard against division by zero

        current:  list[_Tracked]    = []
        results:  list[MotionResult] = []

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            cx   = (x1 + x2) / 2.0
            cy   = (y1 + y2) / 2.0
            area = float((x2 - x1) * (y2 - y1))

            tracked = _Tracked(label=det["label"], center=(cx, cy),
                                bbox_area=area, timestamp=now)
            current.append(tracked)

            prev = self._find_match(tracked)

            if prev is None:
                results.append(MotionResult(
                    label=det["label"], distance_m=det["distance_m"],
                    position=det["position"], confidence=det["confidence"],
                    speed="unknown", direction="unknown", is_approaching=False,
                ))
                continue

            # ── velocity ──────────────────────────────────────────
            dx = cx - prev.center[0]
            dy = cy - prev.center[1]
            px_per_sec = np.sqrt(dx**2 + dy**2) / dt

            if px_per_sec < self.SPEED_SLOW:
                speed = "stationary"
            elif px_per_sec < self.SPEED_MODERATE:
                speed = "slow"
            else:
                speed = "fast"

            # ── approach detection ────────────────────────────────
            area_change  = (area - prev.bbox_area) / max(prev.bbox_area, 1.0)
            is_approach  = area_change >  self.APPROACH_THRESH
            is_receding  = area_change < -self.APPROACH_THRESH

            if speed == "stationary":
                direction = "stationary"
            elif is_approach:
                direction = "approaching you"
            elif is_receding:
                direction = "moving away"
            elif abs(dx) >= abs(dy):
                direction = "moving left" if dx < 0 else "moving right"
            else:
                direction = "moving toward you" if dy > 0 else "moving away"

            results.append(MotionResult(
                label=det["label"], distance_m=det["distance_m"],
                position=det["position"], confidence=det["confidence"],
                speed=speed, direction=direction, is_approaching=is_approach,
            ))

        self._prev   = current
        self._prev_t = now
        return results

    # ── private ───────────────────────────────────────────────────
    def _find_match(self, current: _Tracked) -> Optional[_Tracked]:
        best, best_d = None, self.MATCH_DISTANCE
        for prev in self._prev:
            if prev.label != current.label:
                continue
            dx = current.center[0] - prev.center[0]
            dy = current.center[1] - prev.center[1]
            d  = np.sqrt(dx**2 + dy**2)
            if d < best_d:
                best_d, best = d, prev
        return best
