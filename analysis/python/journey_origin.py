"""
Journey-origin restriction, applied when the pediatric journey tables are loaded
(medevac_data_prep.load_raw and medevac_summaries.load_data).

medevac_pipeline_project tags every journey with `journey_origin`
(village / mhc / commercial; IDs prefixed JV- / JH- / JC-). Only the start
locations in JOURNEY_ORIGINS are kept. Override with the JOURNEY_ORIGINS env
var (comma-separated) or `scripts/run_full_pipeline.py --journey-origins`.

Older pipeline outputs have no `journey_origin`; nothing is dropped at load
time then, and the village restriction comes from the existing village → MHC
leg rule (`_qualifies_for_primary_cohort` / `filter_journeys_village_to_mhc`).
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import pandas as pd

JOURNEY_ORIGINS = ["village"]

VALID_JOURNEY_ORIGINS = ("village", "mhc")
ENV_VAR = "JOURNEY_ORIGINS"


def parse_journey_origins(value: str | Iterable[str]) -> list[str]:
    items = value.split(",") if isinstance(value, str) else list(value)
    origins = [str(v).strip().lower() for v in items if str(v).strip()]
    bad = sorted(set(origins) - set(VALID_JOURNEY_ORIGINS))
    if bad or not origins:
        raise ValueError(
            f"{ENV_VAR} must list one or more of {', '.join(VALID_JOURNEY_ORIGINS)}; "
            f"got {value!r}"
        )
    return list(dict.fromkeys(origins))


def journey_origins() -> list[str]:
    env = os.environ.get(ENV_VAR, "").strip()
    return parse_journey_origins(env if env else JOURNEY_ORIGINS)


def split_by_journey_origin(
    journeys: pd.DataFrame, origins: Iterable[str] | None = None, label: str = "journey_origin"
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(kept, dropped) journey rows; prints aggregate kept/dropped counts per origin."""
    origins = parse_journey_origins(origins) if origins is not None else journey_origins()
    if "journey_origin" not in journeys.columns:
        print(f"  [{label}] no journey_origin column (older pipeline output): "
              f"{len(journeys):,} journeys kept; village restriction comes from the "
              f"village → MHC leg rule")
        return journeys, journeys.iloc[0:0].copy()

    start = journeys["journey_origin"].astype("string").str.strip().str.lower()
    start = start.where(start.isin(VALID_JOURNEY_ORIGINS), "other").fillna("other")
    keep = start.isin(origins).to_numpy()
    counts = start.value_counts()
    print(f"  [{label}] keeping {', '.join(origins)}: "
          f"{int(keep.sum()):,} of {len(journeys):,} journeys kept")
    for name in [*VALID_JOURNEY_ORIGINS, "other"]:
        n = int(counts.get(name, 0))
        if n or name != "other":
            print(f"    {name:<8} {n:>7,}  {'kept' if name in origins else 'dropped'}")
    return journeys.loc[keep].copy(), journeys.loc[~keep].copy()
