# =============================================================================
# main.py — AI Vision Assistant for the Blind
# =============================================================================
# Wires all modules together:
#   1. Asks user for destination (voice)
#   2. Checks if destination is in the same city
#   3. Fetches walking route via OSRM
#   4. Starts GPS tracker + obstacle detector (background)
#   5. Navigation loop: checks obstacles → speaks instruction → navigates
#
# Run:
#   python main.py
# =============================================================================

import time
import sys

from tts import speaker
from stt import listen_and_transcribe
from nlp import extract_destination
from geocoder import geocode_destination, is_same_city
from router import fetch_route
from gps_tracker import GPSTracker
from navigator import navigate
from obstacle_detector import ObstacleDetector
import config


def ask_destination() -> tuple[str, dict] | None:
    """Loop until the user provides a valid, geocoded destination.

    Returns:
        (destination_name, geocoded_result) or None if user quits.
    """
    attempts = 0
    while attempts < 3:
        speaker.speak("Where would you like to go?")
        utterance = listen_and_transcribe()

        if not utterance:
            speaker.speak("I did not catch that. Please try again.")
            attempts += 1
            continue

        destination = extract_destination(utterance)
        if not destination:
            speaker.speak("I could not understand the destination. Please say it clearly.")
            attempts += 1
            continue

        speaker.speak(f"Looking up {destination}. Please wait.")
        geocoded = geocode_destination(destination)

        if geocoded is None:
            speaker.speak(f"I could not find {destination} on the map. Please try again.")
            attempts += 1
            continue

        return destination, geocoded

    speaker.speak("Too many failed attempts. Exiting.")
    return None


def main():
    print("=" * 60)
    print("  AI Vision Assistant for the Blind")
    print("=" * 60)

    # ── Step 1: Load obstacle detection models early ──────────────────────
    print("\n[Startup] Loading obstacle detection models (may take a moment)...")
    detector = ObstacleDetector()
    try:
        detector.load_models()
    except Exception as e:
        print(f"[Startup] Warning: obstacle models failed to load ({e}).")
        print("[Startup] Obstacle detection will be disabled.")
        detector = None

    # ── Step 2: Start GPS tracker ─────────────────────────────────────────
    tracker = GPSTracker()
    tracker.start()

    # Wait briefly for GPS to settle
    speaker.speak("System ready. Waiting for GPS signal.")
    time.sleep(3)
    pos = tracker.position
    if not pos.has_fix:
        print("[GPS] No fix yet — using fallback Hyderabad position.")
        speaker.speak("GPS signal not found. Using default location in Hyderabad.")

    # ── Step 3: Ask for destination ───────────────────────────────────────
    result = ask_destination()
    if result is None:
        tracker.stop()
        sys.exit(0)

    destination_name, geocoded = result

    # ── Step 4: Same-city check ───────────────────────────────────────────
    if not is_same_city(geocoded):
        speaker.speak(
            f"{destination_name} appears to be outside {config.DEFAULT_CITY}. "
            "It would be better to take a ride rather than walk. "
            "Please contact a friend or use a ride-hailing service."
        )
        print(f"[Main] Destination out of city: {geocoded['display']}")
        tracker.stop()
        sys.exit(0)

    speaker.speak(f"Destination confirmed: {destination_name}. Fetching your route.")

    # ── Step 5: Fetch route ───────────────────────────────────────────────
    origin = tracker.position
    steps  = fetch_route(
        origin.lat, origin.lon,
        geocoded["lat"], geocoded["lon"],
    )

    if steps is None:
        speaker.speak("Could not fetch a route. Please check your internet connection.")
        tracker.stop()
        sys.exit(1)

    print(f"[Main] Route fetched: {len(steps)} steps.")

    # ── Step 6: Navigation + obstacle loop ───────────────────────────────
    reroute_count = 0

    def on_reroute():
        nonlocal steps, reroute_count
        reroute_count += 1
        if reroute_count > config.MAX_REROUTES:
            speaker.speak("Maximum re-routes reached. Please ask for help.")
            return

        pos   = tracker.position
        new_s = fetch_route(pos.lat, pos.lon, geocoded["lat"], geocoded["lon"])
        if new_s:
            steps = new_s
        else:
            speaker.speak("Re-routing failed. Please continue straight ahead.")

    print("[Main] Starting navigation. Obstacle detection active.")

    # Integrated navigation + obstacle check loop
    step_index       = 0
    announced        = set()
    navigation_done  = False

    while not navigation_done:
        # ── Obstacle check (non-blocking, time-gated inside tick()) ──────
        if detector:
            alert = detector.tick()
            if alert:
                print(f"[Obstacle] ALERT: {alert}")
                speaker.speak(alert)
                # Brief pause after obstacle warning before nav instruction
                time.sleep(0.5)

        # ── Navigation step ───────────────────────────────────────────────
        pos = tracker.position
        if not pos.has_fix and reroute_count == 0:
            time.sleep(1)
            continue

        from gps_tracker import haversine_distance

        if step_index >= len(steps):
            speaker.speak("You have arrived at your destination.")
            navigation_done = True
            break

        current_step = steps[step_index]
        dist = haversine_distance(
            pos.lat, pos.lon,
            current_step.lat, current_step.lon,
        )

        # Final arrival
        if step_index == len(steps) - 1 and dist <= config.ARRIVAL_DISTANCE:
            speaker.speak("You have arrived at your destination.")
            navigation_done = True
            break

        # Turn announcement
        if dist <= config.TURN_ANNOUNCE_DISTANCE and step_index not in announced:
            announced.add(step_index)
            print(f"[Nav] Step {step_index + 1}/{len(steps)}: {current_step.instruction} (~{int(dist)}m)")
            speaker.speak(current_step.instruction)

        # Advance step
        if dist < 15:
            step_index += 1
            if step_index < len(steps):
                speaker.speak(f"Next: {steps[step_index].instruction}")
            continue

        # Off-route check
        remaining = steps[step_index:]
        min_dist  = min(haversine_distance(pos.lat, pos.lon, s.lat, s.lon) for s in remaining)
        if min_dist > config.REROUTE_THRESHOLD:
            print("[Nav] Off-route — re-routing...")
            speaker.speak("Re-calculating route.")
            on_reroute()
            step_index = 0
            announced  = set()

        time.sleep(config.GPS_POLL_INTERVAL)

    tracker.stop()
    print("[Main] Session complete.")


if __name__ == "__main__":
    main()
