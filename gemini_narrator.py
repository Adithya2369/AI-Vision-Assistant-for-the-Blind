# ─────────────────────────────────────────────
#  gemini_narrator.py  –  natural language alerts
#  Runs on: LAPTOP (server)
# ─────────────────────────────────────────────

import google.generativeai as genai
import config

genai.configure(api_key=config.GEMINI_API_KEY)
_model = genai.GenerativeModel(config.GEMINI_MODEL)


def narrate(enriched: list[dict]) -> str:
    """
    enriched  –  list of dicts combining detector + motion output:
        label, distance_m, position, confidence,
        speed, direction, is_approaching
    Returns a short spoken alert string.
    """
    if not enriched:
        return "The path ahead appears clear."

    # Priority: fast-approaching first, then by distance
    def _priority(d: dict):
        a = 0 if d.get("is_approaching") else 1
        s = {"fast": 0, "slow": 1, "stationary": 2,
             "unknown": 1}.get(d.get("speed", "unknown"), 1)
        return (a, s, d["distance_m"])

    enriched = sorted(enriched, key=_priority)

    items = "\n".join(
        f"- {d['label']} | {d['distance_m']} m | {d['position']} | "
        f"{d.get('direction','unknown')} | speed: {d.get('speed','unknown')}"
        for d in enriched
    )

    prompt = f"""You are an AI navigation assistant speaking directly to a blind person.

Given the list of detected objects below, produce a SHORT spoken alert (2–3 sentences MAX).

Rules:
1. Lead with the most dangerous / closest / fastest-approaching object.
2. Use "Caution" or "Warning" only when something is fast-approaching or very close (< 3 m).
3. Mention direction (left, right, ahead) and distance in metres.
4. Keep language calm, simple, and natural – no technical terms.
5. If everything is stationary and far away, say the path looks clear.

Detected objects:
{items}

Spoken alert:"""

    try:
        response = _model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        # Fall back to a simple rule-based message so TTS always has something
        closest = enriched[0]
        return (
            f"{'Warning – ' if closest.get('is_approaching') else ''}"
            f"A {closest['label']} is {closest['position']}, "
            f"about {closest['distance_m']} metres away."
        )
