# =============================================================================
# gps_tracker.py — GPS Position Reader
# =============================================================================
# LAPTOP : Tries gpsd → fallback to Hyderabad coordinates if unavailable.
# PI     : Uses USB GPS dongle via gpsd or serial (see Pi section below).
#
# The GPSTracker exposes a simple .position property (thread-safe).
# =============================================================================

import threading
import time
from dataclasses import dataclass
import config


@dataclass
class GPSPosition:
    lat:     float
    lon:     float
    speed:   float   = 0.0
    altitude:float   = 0.0
    has_fix: bool    = False


def haversine_distance(lat1: float, lon1: float,
                       lat2: float, lon2: float) -> float:
    """Straight-line distance in metres between two GPS coordinates.
    Accurate to within 0.5% for distances under 10 km.
    """
    import math
    R = 6_371_000  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi      = math.radians(lat2 - lat1)
    d_lam      = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# =============================================================================
# GPSTracker
# =============================================================================

class GPSTracker:
    """Continuously reads GPS position in a background thread.

    Usage:
        tracker = GPSTracker()
        tracker.start()
        pos = tracker.position
        tracker.stop()
    """

    def __init__(self):
        self._position  = GPSPosition(
            lat=config.FALLBACK_LAT,
            lon=config.FALLBACK_LON,
            has_fix=False,
        )
        self._lock      = threading.Lock()
        self._stop_flag = threading.Event()
        self._thread    = None
        self._source    = "fallback"   # "gpsd" | "serial" | "fallback"

    # ── Public API ───────────────────────────────────────────────────────────

    def start(self):
        """Start the background GPS reading thread."""
        self._source = self._detect_source()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="GPSThread"
        )
        self._thread.start()
        print(f"[GPS] Started using source: {self._source}")

    def stop(self):
        self._stop_flag.set()

    @property
    def position(self) -> GPSPosition:
        with self._lock:
            import copy
            return copy.copy(self._position)

    def _set_position(self, pos: GPSPosition):
        with self._lock:
            self._position = pos

    # ── Source detection ─────────────────────────────────────────────────────

    def _detect_source(self) -> str:
        # 1. Try gpsd (works on both laptop and Pi if gpsd is running)
        try:
            import gpsd
            gpsd.connect()
            _ = gpsd.get_current()
            return "gpsd"
        except Exception:
            pass

        # ── RASPBERRY PI: USB serial GPS ────────────────────────────────────
        # Uncomment the block below to enable serial GPS on Pi.
        # Comment it out when running on a laptop.
        #
        # try:
        #     import serial
        #     test_port = serial.Serial(config.GPS_SERIAL_PORT,
        #                               baudrate=config.GPS_BAUD_RATE,
        #                               timeout=1)
        #     test_port.close()
        #     return "serial"
        # except Exception:
        #     pass
        # ── END PI SERIAL SECTION ────────────────────────────────────────────

        print("[GPS] No GPS hardware found. Using Hyderabad fallback position.")
        return "fallback"

    # ── Background thread ────────────────────────────────────────────────────

    def _run(self):
        if self._source == "gpsd":
            self._run_gpsd()
        elif self._source == "serial":
            self._run_serial()
        else:
            self._run_fallback()

    def _run_gpsd(self):
        import gpsd
        while not self._stop_flag.is_set():
            try:
                packet = gpsd.get_current()
                if packet.mode >= 2:
                    self._set_position(GPSPosition(
                        lat=packet.lat,
                        lon=packet.lon,
                        speed=getattr(packet, "hspeed", 0.0) or 0.0,
                        altitude=getattr(packet, "alt", 0.0) or 0.0,
                        has_fix=True,
                    ))
                else:
                    # No satellite fix yet
                    pos = self.position
                    self._set_position(GPSPosition(
                        lat=pos.lat, lon=pos.lon,
                        has_fix=False,
                    ))
            except Exception:
                pass
            time.sleep(config.GPS_POLL_INTERVAL)

    # ── RASPBERRY PI: Serial GPS (NMEA) ──────────────────────────────────────
    # Uncomment this entire method to enable serial GPS on Pi.
    # Comment it out when running on a laptop.
    #
    # def _run_serial(self):
    #     import serial
    #     import pynmea2
    #     ser = serial.Serial(config.GPS_SERIAL_PORT,
    #                         baudrate=config.GPS_BAUD_RATE,
    #                         timeout=1)
    #     while not self._stop_flag.is_set():
    #         try:
    #             line = ser.readline().decode("ascii", errors="replace").strip()
    #             if line.startswith("$GPRMC") or line.startswith("$GNRMC"):
    #                 msg = pynmea2.parse(line)
    #                 if msg.status == "A":   # Active = valid fix
    #                     self._set_position(GPSPosition(
    #                         lat=msg.latitude,
    #                         lon=msg.longitude,
    #                         speed=float(msg.spd_over_grnd or 0) * 0.514444,
    #                         has_fix=True,
    #                     ))
    #         except Exception:
    #             pass
    # ── END PI SERIAL SECTION ────────────────────────────────────────────────

    def _run_fallback(self):
        """Static Hyderabad fallback — position never changes."""
        while not self._stop_flag.is_set():
            time.sleep(5)
        # Position stays at Hyderabad fallback values from __init__
