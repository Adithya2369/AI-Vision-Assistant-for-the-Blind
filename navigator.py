# =============================================================================
# navigator.py — Navigation Engine
# =============================================================================
# Watches live GPS position against route steps and speaks turn instructions.
# Returns True on arrival, False if re-routing is needed.
# =============================================================================

import time
from tts import speaker
from gps_tracker import GPSTracker, haversine_distance
from router import RouteStep, total_route_distance
import config


def navigate(
    steps:      list[RouteStep],
    tracker:    GPSTracker,
    on_reroute: callable = None,
) -> bool:
    """Drive the navigation loop.

    Args:
        steps:      List of RouteStep from router.py.
        tracker:    Live GPSTracker instance.
        on_reroute: Callback called when re-route is needed. Receives no args.

    Returns:
        True  — destination reached.
        False — off-route, caller should re-fetch and call navigate() again.
    """
    if not steps:
        speaker.speak("No route steps available.")
        return True

    total_m   = total_route_distance(steps)
    total_str = _fmt_dist(total_m)

    # Announce journey start
    speaker.speak(
        f"Route found. Total distance approximately {total_str}. "
        f"First instruction: {steps[0].instruction}."
    )

    step_index    = 0
    announced     = set()   # indices of steps whose instruction has been spoken

    while step_index < len(steps):
        pos = tracker.position

        if not pos.has_fix:
            print("[Nav] Waiting for GPS fix...")
            time.sleep(2)
            continue

        current_step = steps[step_index]

        # Distance to current waypoint
        dist = haversine_distance(
            pos.lat, pos.lon,
            current_step.lat, current_step.lon,
        )

        # ── Arrival check (final step) ───────────────────────────────────────
        if step_index == len(steps) - 1:
            if dist <= config.ARRIVAL_DISTANCE:
                speaker.speak("You have arrived at your destination.")
                return True

        # ── Turn announcement ────────────────────────────────────────────────
        if (
            dist <= config.TURN_ANNOUNCE_DISTANCE
            and step_index not in announced
        ):
            announced.add(step_index)
            print(f"[Nav] Step {step_index + 1}: {current_step.instruction}  ({_fmt_dist(dist)} away)")
            speaker.speak(current_step.instruction)

        # ── Step advance (passed the waypoint) ──────────────────────────────
        if dist < 15 and step_index not in announced:
            announced.add(step_index)

        if dist < 15:
            step_index += 1
            if step_index < len(steps):
                next_step = steps[step_index]
                print(f"[Nav] Next: {next_step.instruction}")
                speaker.speak(f"Next: {next_step.instruction}")
            continue

        # ── Off-route check ──────────────────────────────────────────────────
        remaining_steps = steps[step_index:]
        min_dist_to_route = min(
            haversine_distance(pos.lat, pos.lon, s.lat, s.lon)
            for s in remaining_steps
        )
        if min_dist_to_route > config.REROUTE_THRESHOLD:
            print("[Nav] Off route — re-routing...")
            speaker.speak("You appear to be off route. Re-calculating.")
            if on_reroute:
                on_reroute()
            return False

        time.sleep(config.GPS_POLL_INTERVAL)

    speaker.speak("You have arrived at your destination.")
    return True


def _fmt_dist(metres: float) -> str:
    if metres >= 1000:
        return f"{metres / 1000:.1f} kilometres"
    return f"{int(metres)} metres"
