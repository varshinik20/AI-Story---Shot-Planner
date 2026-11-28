"""Shared shot-planning rules: one camera setup (framing + angle) per shot.

A "camera setup" is a single framing seen from a single angle. Whenever the
framing or the angle changes, a new shot must begin. LLMs frequently violate
this by packing several setups into one shot (e.g. framing
``"Wide Shot (WS) to Close-Up (CU)"`` or movement ``"Static, then cut to a low
angle"``). The helpers here are pure, deterministic and side-effect free so
they can be reused by every shot-producing pipeline and unit tested in
isolation.
"""

from __future__ import annotations

import re

CAMERA_SETUP_RULE_PROMPT = """**ONE CAMERA SETUP PER SHOT (ABSOLUTE RULE)**:
  - A shot is exactly ONE camera setup: ONE framing seen from ONE camera angle, one subject, one action, one location and one moment.
  - Whenever the camera ANGLE changes (eye level -> low angle -> high angle -> overhead -> ground level -> dutch, or a reverse / over-the-shoulder flip), it MUST become a NEW shot with its own shot ID, duration and description.
  - Whenever the FRAMING changes (WS -> MS -> CU -> ECU -> insert/detail), it MUST become a NEW shot.
  - Whenever the subject, action, location, lighting, insert detail or reaction changes, a new shot begins.
  - Write any non-eye-level angle INSIDE the framing value, e.g. "Low-Angle Wide Shot (WS)", "High-Angle Wide Shot (WS)", "Ground-Level Tracking Shot", "Overhead Close-Up (CU)". Eye-level shots use the plain framing, e.g. "Medium Shot (MS)".
  - The framing value must name exactly ONE framing. NEVER write "WS to CU", "MS / CU", "Wide then Close-Up" or similar.
  - Camera movement describes motion WITHIN that single setup only (static, slow push-in, crane up, pan with eyeline, rack focus, tracking). NEVER write "cut to", "switch to", "reverse angle" or "new angle" inside a movement or description; that is a new shot."""

# Framing / angle vocabulary used to decide whether a fragment names a camera setup.
_SETUP_TERM_RE = re.compile(
    r"\b(?:extreme\s+wide|wide|medium|close[- ]?up|establishing|insert|detail|"
    r"two[- ]shot|over[- ]the[- ]shoulder|point\s+of\s+view|pov|ots|ews|ws|mws|ms|mcu|cu|ecu|"
    r"low[- ]angle|high[- ]angle|eye[- ]level|ground[- ]level|overhead|bird'?s[- ]eye|"
    r"worm'?s[- ]eye|dutch|aerial|top[- ]down|tracking\s+shot)\b",
    re.IGNORECASE,
)

_ANGLE_TERM_RE = re.compile(
    r"\b(?:low|high|eye|ground|overhead|bird'?s|worm'?s|dutch|aerial|top[- ]down|canted|"
    r"oblique|reverse|front|side|profile|rear|three[- ]quarter|pov|over[- ]the[- ]shoulder)\b",
    re.IGNORECASE,
)

# Separators that join two setups inside one framing/angle field.
_SETUP_SEPARATOR_RE = re.compile(
    r"\s*(?:/|\||→|->|=>|;|,\s*then\s+|\s+and\s+then\s+|\s+then\s+|\s+to\s+|\s+into\s+|\s+followed\s+by\s+)\s*",
    re.IGNORECASE,
)

# A continuous lens/camera move legitimately travels between framings in one setup
# (e.g. framing "Wide to Close-Up" with movement "Slow push-in").
_CONTINUOUS_MOVE_RE = re.compile(
    r"\b(?:push|pull|dolly|zoom|crane|boom|jib|track|truck|follow|arc|orbit)\w*\b",
    re.IGNORECASE,
)

# Explicit edit points inside a camera-movement field. "match cut from" describes
# the transition INTO this shot and is not an edit point inside it.
_CUT_MARKER_RE = re.compile(
    r"\s*[,;.]?\s*(?:and\s+)?(?:then\s+)?(?:"
    r"(?:hard\s+|smash\s+|jump\s+)?cuts?\s+(?:back\s+)?to"
    r"|switch(?:es|ing)?\s+to"
    r"|reverse\s+angle(?:\s+(?:on|of|to))?"
    r"|(?:new|second|another)\s+angle(?:\s+(?:on|of|to))?"
    r"|angle\s+(?:changes|shifts|switches)\s+to"
    r")\s*[:,]?\s*",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip()).strip(" ,;.")
    return cleaned[:1].upper() + cleaned[1:] if cleaned else ""


def _split_on_separators(value: str, term_re: re.Pattern[str]) -> list[str]:
    parts = [_clean(p) for p in _SETUP_SEPARATOR_RE.split(value or "")]
    parts = [p for p in parts if p]
    # Only treat it as multiple setups if EVERY fragment names a setup term;
    # otherwise the separator was ordinary prose (e.g. "Close-Up on hand to mouth").
    if len(parts) >= 2 and all(term_re.search(p) for p in parts):
        return parts
    single = _clean(value)
    return [single] if single else []


def split_framing_setups(framing: str, movement: str = "") -> list[str]:
    """Return one framing per camera setup named in ``framing``.

    ``"Wide Shot (WS) to Close-Up (CU)"`` -> ``["Wide Shot (WS)", "Close-Up (CU)"]``
    unless ``movement`` is a continuous move (push-in, dolly, crane...), in which
    case the framing range is one setup and is returned unchanged.
    """
    parts = _split_on_separators(framing, _SETUP_TERM_RE)
    if len(parts) > 1 and _CONTINUOUS_MOVE_RE.search(movement or "") and not _CUT_MARKER_RE.search(movement or ""):
        return [_clean(framing)]
    return parts


def split_angle_setups(angle: str) -> list[str]:
    """Return one angle per camera setup named in a dedicated angle field."""
    return _split_on_separators(angle, _ANGLE_TERM_RE)


def split_movement_on_cuts(movement: str) -> list[str]:
    """Split a camera-movement value at explicit edit points ("cut to", "reverse angle"...)."""
    parts = [_clean(p) for p in _CUT_MARKER_RE.split(movement or "")]
    parts = [p for p in parts if p]
    return parts or ([_clean(movement)] if _clean(movement) else [])


def framing_from_movement_fragment(fragment: str, fallback_framing: str) -> tuple[str, str]:
    """For a fragment after a cut marker, derive (framing, movement) for the new setup.

    ``"low-angle wide shot, slow crane up"`` -> ``("Low-angle wide shot", "Slow crane up")``.
    A fragment that names no framing keeps the previous framing.
    """
    pieces = [_clean(p) for p in re.split(r"\s*,\s*|\s+with\s+(?:a\s+)?", fragment, maxsplit=1)]
    pieces = [p for p in pieces if p]
    if pieces and _SETUP_TERM_RE.search(pieces[0]):
        return pieces[0], (pieces[1] if len(pieces) > 1 else "Static")
    return fallback_framing, _clean(fragment) or "Static"


def assign_frames_to_setups(frames: list[str], setup_count: int, fallback: str) -> list[str]:
    """Pair visual frames with setups in order.

    Extra frames are appended to the last setup (a later frame-splitter breaks
    them out again under that setup); missing frames reuse the last frame,
    i.e. the same moment covered from another angle.
    """
    if setup_count <= 0:
        return []
    usable = [f for f in frames if f.strip()] or ([fallback] if fallback.strip() else [""])
    assigned: list[str] = []
    for idx in range(setup_count):
        if idx < setup_count - 1:
            assigned.append(usable[min(idx, len(usable) - 1)])
        else:
            assigned.append(" ".join(usable[idx:]) if idx < len(usable) else usable[-1])
    return assigned


def split_duration(total_seconds: int, parts: int, minimum: int = 2) -> list[int]:
    """Split a parent duration across ``parts`` setups, each at least ``minimum`` seconds."""
    if parts <= 1:
        return [max(1, int(total_seconds))]
    base = max(minimum, int(total_seconds) // parts)
    return [base] * parts
