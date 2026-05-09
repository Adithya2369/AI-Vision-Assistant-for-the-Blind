# =============================================================================
# simulate_nav.py — Navigation Console Simulation
# =============================================================================
# Simulates the full navigation flow WITHOUT GPS hardware or voice output.
# The system asks "Where would you like to go?" via text input,
# geocodes the destination, fetches the route, and prints all turn-by-turn
# directions to the console.
#
# Useful for:
#   • Testing the geocoder + OSRM router pipeline
#   • Demoing directions without hardware
#   • Verifying route quality for a destination
#
# Run:
#   python simulate_nav.py
# =============================================================================

from geocoder import geocode_destination, is_same_city
from router   import fetch_route, total_route_distance, RouteStep
from nlp      import extract_destination
import config


# ── Formatting helpers ────────────────────────────────────────────────────────

def fmt_dist(metres: float) -> str:
    if metres >= 1000:
        return f"{metres / 1000:.2f} km"
    return f"{int(metres)} m"

def fmt_time(seconds: float) -> str:
    minutes = int(seconds / 60)
    if minutes < 1:
        return "< 1 min"
    return f"{minutes} min"

SEPARATOR  = "─" * 65
SEPARATOR2 = "═" * 65


# ── Banner ────────────────────────────────────────────────────────────────────

def print_banner():
    print("\n" + SEPARATOR2)
    print("  AI Vision Assistant — Navigation Simulation")
    print(f"  City: {config.DEFAULT_CITY}")
    print(SEPARATOR2)


# ── Ask destination via text ──────────────────────────────────────────────────

def ask_destination_text() -> tuple[str, dict] | None:
    """Text-input version of the destination prompt (no mic required)."""
    for attempt in range(3):
        print("\n[System] Where would you like to go?")
        utterance = input("  >> You: ").strip()

        if not utterance:
            print("[System] I did not catch that. Please try again.")
            continue

        destination = extract_destination(utterance.lower())
        if not destination:
            print("[System] Could not extract a destination. Try: 'take me to Charminar'")
            continue

        print(f"[System] Looking up \"{destination}\"...")
        geocoded = geocode_destination(destination)

        if geocoded is None:
            print(f"[System] Could not find \"{destination}\" on the map. Try again.")
            continue

        return destination, geocoded

    print("[System] Too many failed attempts.")
    return None


# ── Print route ───────────────────────────────────────────────────────────────

def print_route(steps: list[RouteStep], destination_name: str, dest_info: dict):
    total_m   = total_route_distance(steps)
    total_s   = sum(s.duration for s in steps)

    print("\n" + SEPARATOR2)
    print(f"  Route to: {destination_name}")
    print(f"  Address : {dest_info['display'][:70]}...")
    print(f"  Distance: {fmt_dist(total_m)}   |   Est. walk time: {fmt_time(total_s)}")
    print(SEPARATOR2)
    print()

    for i, step in enumerate(steps, 1):
        # Marker for last step (arrival)
        is_last = i == len(steps)
        marker  = "🏁" if is_last else f"{i:>2}."

        dist_str = fmt_dist(step.distance) if step.distance > 0 else ""
        time_str = fmt_time(step.duration) if step.duration > 0 else ""
        meta     = " | ".join(filter(None, [dist_str, time_str]))

        print(f"  {marker}  {step.instruction}")
        if meta:
            print(f"       ({meta})")
        print()

    print(SEPARATOR)
    print(f"  Total: {fmt_dist(total_m)}  (~{fmt_time(total_s)} walking)")
    print(SEPARATOR + "\n")


# ── Highlight warnings ────────────────────────────────────────────────────────

def print_out_of_city_warning(destination_name: str, dest_info: dict):
    print("\n" + SEPARATOR)
    print(f"  ⚠  DESTINATION OUT OF CITY")
    print(f"  '{destination_name}' is in: {dest_info.get('city', 'unknown location')}")
    print(f"  ({dest_info['display'][:70]}...)")
    print()
    print(f"  This destination is outside {config.DEFAULT_CITY}.")
    print("  It would be better to take a ride rather than walk.")
    print("  Please contact a friend or use a ride-hailing service.")
    print(SEPARATOR + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print_banner()

    result = ask_destination_text()
    if result is None:
        return

    destination_name, geocoded = result

    print(f"\n[Geocoded] {geocoded['display']}")
    print(f"[Geocoded] Coordinates: {geocoded['lat']:.5f}, {geocoded['lon']:.5f}")
    print(f"[Geocoded] City field : {geocoded['city']}")

    # City check
    if not is_same_city(geocoded):
        print_out_of_city_warning(destination_name, geocoded)
        return

    print(f"\n[System] Destination is within {config.DEFAULT_CITY}. Fetching route...")

    # Use Hyderabad fallback as origin for simulation
    origin_lat = config.FALLBACK_LAT
    origin_lon = config.FALLBACK_LON
    print(f"[Sim]    Origin (fallback): {origin_lat}, {origin_lon}  ({config.DEFAULT_CITY} city centre)")

    steps = fetch_route(
        origin_lat, origin_lon,
        geocoded["lat"], geocoded["lon"],
    )

    if steps is None:
        print("\n[Error] Could not fetch route. Check your internet connection.")
        return

    print(f"[Router] {len(steps)} steps fetched from OSRM.")

    # Print formatted route
    print_route(steps, destination_name, geocoded)

    # Offer to run again
    while True:
        again = input("Try another destination? (y/n): ").strip().lower()
        if again == "y":
            print()
            main()
            return
        elif again in ("n", ""):
            print("\n[System] Goodbye!\n")
            return


if __name__ == "__main__":
    main()
