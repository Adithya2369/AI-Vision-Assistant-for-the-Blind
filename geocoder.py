# =============================================================================
# geocoder.py — Geocoding via Nominatim (OpenStreetMap, free, no key)
# =============================================================================
# Converts a destination name → (lat, lon) and checks if it is in the same
# city as the user (Hyderabad by default).
# =============================================================================

import time
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import config

_geolocator = Nominatim(user_agent="vision_assistant_blind_v1")
_last_request_time: float = 0.0


def _rate_limit():
    """Enforce Nominatim's 1 request/second policy."""
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < 1.1:
        time.sleep(1.1 - elapsed)
    _last_request_time = time.time()


def geocode_destination(destination: str) -> dict | None:
    """Geocode a destination string.

    Returns a dict with keys:
        lat       float
        lon       float
        display   str    (full address from Nominatim)
        city      str    (city / town / county extracted from raw address)

    Returns None if geocoding fails.
    """
    # Attempt 1: biased to DEFAULT_CITY
    result = _try_geocode(f"{destination}, {config.DEFAULT_CITY_FULL}")

    # Attempt 2: global fallback (catches out-of-city destinations)
    if result is None:
        result = _try_geocode(destination)

    return result


def _try_geocode(query: str) -> dict | None:
    _rate_limit()
    try:
        location = _geolocator.geocode(query, addressdetails=True, timeout=10)
        if location is None:
            return None

        address = location.raw.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("county")
            or address.get("state")
            or "unknown"
        )

        return {
            "lat":     location.latitude,
            "lon":     location.longitude,
            "display": location.address,
            "city":    city,
        }
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"[Geocoder] Error: {e}")
        return None


def is_same_city(geocoded: dict) -> bool:
    """Return True if the geocoded result is within the configured city.

    Strategy: case-insensitive substring check on the city field.
    Secondary: bounding-box check if the name doesn't match.
    """
    city_name = geocoded.get("city", "").lower()
    if config.DEFAULT_CITY.lower() in city_name:
        return True

    # Bounding-box fallback
    lat, lon = geocoded["lat"], geocoded["lon"]
    bb = config.CITY_BBOX
    return (
        bb["lat_min"] <= lat <= bb["lat_max"]
        and bb["lon_min"] <= lon <= bb["lon_max"]
    )
