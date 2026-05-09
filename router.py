# =============================================================================
# router.py — Route Fetching via OSRM (fully free, no API key)
# =============================================================================
# Fetches a walking route between two GPS coordinate pairs.
# Returns a list of RouteStep objects with human-readable instructions.
# =============================================================================

import requests
from dataclasses import dataclass
import config


@dataclass
class RouteStep:
    instruction: str    # e.g. "Turn left onto MG Road"
    distance:    float  # metres to travel before this instruction
    duration:    float  # estimated seconds at walking pace
    lat:         float  # waypoint latitude
    lon:         float  # waypoint longitude
    maneuver:    str    # raw maneuver type string (e.g. "turn", "depart")


def fetch_route(
    origin_lat: float, origin_lon: float,
    dest_lat:   float, dest_lon:   float,
) -> list[RouteStep] | None:
    """Fetch a walking route from OSRM.

    Returns:
        List of RouteStep, or None on failure.
    """
    url = (
        f"{config.OSRM_BASE_URL}/route/v1/{config.OSRM_PROFILE}/"
        f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
        f"?steps=true&annotations=false&geometries=geojson&overview=full"
    )

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        print(f"[Router] OSRM request failed: {e}")
        return None

    if data.get("code") != "Ok" or not data.get("routes"):
        print(f"[Router] OSRM returned no routes. Code: {data.get('code')}")
        return None

    legs = data["routes"][0].get("legs", [])
    steps: list[RouteStep] = []

    for leg in legs:
        for step in leg.get("steps", []):
            instruction = _build_instruction(step)
            if not instruction:
                continue

            # Waypoint coordinate: end location of this step
            maneuver = step.get("maneuver", {})
            loc = maneuver.get("location", [0, 0])  # [lon, lat] in GeoJSON
            lon_wp, lat_wp = loc[0], loc[1]

            steps.append(RouteStep(
                instruction=instruction,
                distance=step.get("distance", 0.0),
                duration=step.get("duration", 0.0),
                lat=lat_wp,
                lon=lon_wp,
                maneuver=maneuver.get("type", ""),
            ))

    if not steps:
        print("[Router] Route parsed but contained no usable steps.")
        return None

    return steps


def total_route_distance(steps: list[RouteStep]) -> float:
    """Return total route distance in metres."""
    return sum(s.distance for s in steps)


# ── Internal helpers ──────────────────────────────────────────────────────────

_MANEUVER_PHRASES = {
    "turn":         "Turn",
    "new name":     "Continue",
    "depart":       "Head",
    "arrive":       "Arrive at",
    "merge":        "Merge onto",
    "on ramp":      "Take the ramp onto",
    "off ramp":     "Take the exit onto",
    "fork":         "Keep",
    "end of road":  "Turn",
    "use lane":     "Use the lane",
    "continue":     "Continue",
    "roundabout":   "Enter the roundabout",
    "rotary":       "Enter the rotary",
    "roundabout turn": "Turn at the roundabout",
    "notification": "Note",
}

_MODIFIER_PHRASES = {
    "uturn":        "and make a U-turn",
    "sharp right":  "sharp right",
    "right":        "right",
    "slight right": "slightly right",
    "straight":     "straight",
    "slight left":  "slightly left",
    "left":         "left",
    "sharp left":   "sharp left",
}


def _build_instruction(step: dict) -> str:
    """Convert an OSRM step dict into a natural-language sentence."""
    maneuver   = step.get("maneuver", {})
    m_type     = maneuver.get("type", "")
    modifier   = maneuver.get("modifier", "")
    road_name  = step.get("name", "")
    distance   = step.get("distance", 0.0)

    verb = _MANEUVER_PHRASES.get(m_type, "Continue")
    mod  = _MODIFIER_PHRASES.get(modifier, "")

    # Build sentence
    parts = [verb]
    if mod:
        parts.append(mod)
    if road_name:
        parts.append(f"onto {road_name}" if m_type not in ("depart", "arrive") else road_name)
    if distance > 0 and m_type not in ("arrive",):
        parts.append(f"for {_fmt_dist(distance)}")

    sentence = " ".join(parts).strip()
    # Capitalise first letter
    return sentence[:1].upper() + sentence[1:] if sentence else ""


def _fmt_dist(metres: float) -> str:
    if metres >= 1000:
        return f"{metres / 1000:.1f} kilometres"
    return f"{int(metres)} metres"
