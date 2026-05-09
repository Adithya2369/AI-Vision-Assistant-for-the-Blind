# =============================================================================
# nlp.py — Destination Extraction (regex, stdlib only)
# =============================================================================
# Extracts a destination name from a natural-language utterance.
# No external NLP library required — pure Python re.
# =============================================================================

import re

# Ordered list of trigger patterns.
# Each pattern captures everything after the trigger phrase in group 1.
_TRIGGER_PATTERNS = [
    r"take me to\s+(.+)",
    r"navigate to\s+(.+)",
    r"i want to go to\s+(.+)",
    r"i want to go\s+(.+)",
    r"how do i get to\s+(.+)",
    r"directions? to\s+(.+)",
    r"go to\s+(.+)",
    r"head to\s+(.+)",
    r"walk to\s+(.+)",
    r"get me to\s+(.+)",
    r"destination\s+(.+)",
]

# Filler words to strip from the end of a captured destination
_TRAILING_NOISE = re.compile(
    r"\s+(please|now|quickly|fast|asap|thanks|thank you)$", re.I
)


def extract_destination(utterance: str) -> str | None:
    """Extract destination name from a spoken utterance.

    Examples:
        "take me to Charminar"          -> "charminar"
        "navigate to Apollo Hospital"   -> "apollo hospital"
        "Hitech City"                   -> "hitech city"
        "how do I get to LB Nagar"      -> "lb nagar"

    Returns:
        Cleaned destination string (lowercase), or None if nothing found.
    """
    text = utterance.strip().lower()

    for pattern in _TRIGGER_PATTERNS:
        match = re.search(pattern, text)
        if match:
            dest = match.group(1).strip()
            dest = _TRAILING_NOISE.sub("", dest).strip()
            return dest if dest else None

    # No trigger phrase matched.
    # If the utterance is 5 words or fewer, treat the whole thing as the destination.
    words = text.split()
    if 1 <= len(words) <= 5:
        return text

    return None
