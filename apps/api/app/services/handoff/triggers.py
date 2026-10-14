"""Heuristic handoff triggers and keyword detection."""

import re

HANDOFF_PATTERNS = [
    r"\b(talk|speak|connect)(\s+me)?\s+(to|with)\s+(an?\s+)?(human|agent|person|representative|executive|someone)\b",
    r"\b(human|live)\s+(agent|support|executive|representative|operator|advisor)\b",
    r"\b(need|want)\s+(an?\s+)?(human|agent|representative|executive)\b",
    r"\b(customer\s+care|support\s+executive|helpdesk)\b",
    r"\b(insan\s+se\s+baat|kisi\s+se\s+baat|real\s+person)\b",
    r"^/(human|agent|operator)$",
]

_COMPILED_REGEX = [re.compile(p, re.IGNORECASE) for p in HANDOFF_PATTERNS]


def detect_handoff_intent(text: str) -> bool:
    """Return True if message content explicitly indicates desire for human assistance."""
    cleaned = text.strip()
    if not cleaned:
        return False
    return any(p.search(cleaned) for p in _COMPILED_REGEX)
