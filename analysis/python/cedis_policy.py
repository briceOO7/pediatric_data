"""
Single source of truth for how CEDIS 888 / 889 / 891 are treated.

STANDING RULE: CEDIS 888 (Follow-up/Return Visit), 889 (Well visit) and
891 (Planned telehealth) must NEVER exclude an encounter, journey, patient,
count, table row or figure element. A journey whose only complaint is one of
these codes is analysed with that complaint.

What *is* allowed is choosing which complaint on a journey is the "definitive"
primary complaint. That is a selection among complaints of one retained
journey, not an exclusion, and works in tiers (``definitive_rank``):

  rank 0  any real complaint, including 889 and 891 (never demoted)
  rank 1  888 Follow-up/Return Visit (used only when no rank-0 complaint exists)
  None    999 / "Unknown" (a placeholder, not a complaint)

``pick_definitive`` returns the first rank-0 complaint in journey order, else
the first rank-1 complaint, else None. So a journey whose only complaint is
888 resolves to 888 rather than to missing/"Undefined".
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

import pandas as pd

FOLLOW_UP = 888
WELL_VISIT = 889
PLANNED_TELEHEALTH = 891
UNKNOWN = 999

PROTECTED_CODES: dict[int, str] = {
    FOLLOW_UP: "Follow-up visit",
    WELL_VISIT: "Well visit",
    PLANNED_TELEHEALTH: "Planned telehealth",
}

_PROTECTED_TEXT: dict[str, int] = {
    "follow-up visit": FOLLOW_UP,
    "follow-up/return visit": FOLLOW_UP,
    "well visit": WELL_VISIT,
    "planned telehealth": PLANNED_TELEHEALTH,
}

RANK_NORMAL = 0
RANK_FOLLOW_UP = 1


def parse_code(x: object) -> int | None:
    """CEDIS code as int ('888', 888.0, '888.0' -> 888); None if missing/invalid."""
    try:
        if x is None or pd.isna(x):
            return None
        s = str(x).strip()
        return int(float(s)) if s else None
    except (ValueError, TypeError):
        return None


def _text(x: object) -> str:
    if x is None or pd.isna(x):
        return ""
    return str(x).strip()


def protected_code(code: object, complaint: object = None) -> int | None:
    """888/889/891 if the code, or failing that the complaint text, says so."""
    c = parse_code(code)
    if c in PROTECTED_CODES:
        return c
    return _PROTECTED_TEXT.get(_text(complaint).lower())


def is_protected(code: object, complaint: object = None) -> bool:
    return protected_code(code, complaint) is not None


def complaint_label(code: object, complaint: object = None) -> str:
    """Complaint text, falling back to the canonical label for 888/889/891."""
    t = _text(complaint)
    if t:
        return t
    p = protected_code(code, complaint)
    return PROTECTED_CODES[p] if p is not None else ""


def definitive_rank(code: object, complaint: object = None) -> int | None:
    """Selection tier for one complaint (see module docstring); None = ineligible."""
    p = protected_code(code, complaint)
    if p == FOLLOW_UP:
        return RANK_FOLLOW_UP
    if p is not None:
        return RANK_NORMAL
    if parse_code(code) == UNKNOWN or _text(complaint).lower() == "unknown":
        return None
    if not _text(complaint):
        return None
    return RANK_NORMAL


def pick_definitive(pairs: Iterable[tuple[object, object]] | Sequence[tuple[object, object]]) -> int | None:
    """
    Index (in journey order) of the definitive complaint among (code, complaint)
    pairs: first rank-0, else first rank-1 (888), else None.
    """
    first_follow_up: int | None = None
    for i, (code, complaint) in enumerate(pairs):
        r = definitive_rank(code, complaint)
        if r == RANK_NORMAL:
            return i
        if r == RANK_FOLLOW_UP and first_follow_up is None:
            first_follow_up = i
    return first_follow_up
