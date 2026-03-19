#!/usr/bin/env python3
"""
Audit chief complaints for pediatric medevac cohort.

Outputs review CSVs in separate folders for:
  1) Pregnancy-related complaints (by age bin)
  2) Village primary CEDIS 888 journeys

Run from repo root:
  python scripts/audit_chief_complaints.py

PHI: expects per-slot columns like ``village_EncounterStartDTS_1``,
``mhc_ed_EncounterStartDTS_1`` (case-insensitive; see
``_resolve_encounter_start_dts_col`` for alternates). Populates
``hours_since_previous_cc`` when consecutive rows parse as datetimes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "analysis"))

from medevac_summaries import (  # noqa: E402
    CHIEF_COMPLAINTS_WIDE,
    _age_bucket_key,
    _format_cedis_code,
    filter_journeys_village_to_mhc,
    load_data,
)


def _has_value(x: object) -> bool:
    if pd.isna(x):
        return False
    return str(x).strip() != ""


def _ci_column_lookup(columns: pd.Index) -> dict[str, str]:
    """Map lowercase column name -> actual column name (first wins)."""
    return {str(c).lower(): str(c) for c in columns}


def _resolve_encounter_start_dts_col(prefix: str, slot: int, lookup: dict[str, str]) -> str | None:
    """
    PHI export: per-slot encounter start DTS, e.g. village_EncounterStartDTS_1,
    mhc_ed_EncounterStartDTS_1. Tries several suffix patterns (case-insensitive).
    """
    candidates = [
        f"{prefix}_EncounterStartDTS_{slot}",
        f"{prefix}_cc_EncounterStartDTS_{slot}",
        f"{prefix}_cedis_EncounterStartDTS_{slot}",
    ]
    if prefix == "village":
        candidates.insert(0, f"village_cc_EncounterStartDTS_{slot}")
    for cand in candidates:
        actual = lookup.get(cand.lower())
        if actual:
            return actual
    return None


def _age_label(a: object) -> str:
    key = _age_bucket_key(pd.to_numeric(a, errors="coerce"))
    m = {
        "b0": "<1 year",
        "b1": "1 to <5 years",
        "b2": "5-12 years",
        "b3": "13-18 years",
    }
    return m.get(key, "Age missing or >18")


def _first_village_triplet(row: pd.Series) -> tuple[object, object, object] | None:
    for i in range(1, 20):
        t = row.get(f"village_cc_{i}", pd.NA)
        c = _format_cedis_code(row.get(f"village_cedis_code_{i}", pd.NA))
        k = row.get(f"village_cedis_complaint_{i}", pd.NA)
        if _has_value(c):
            return t, c, k
    for i in range(1, 20):
        t = row.get(f"village_cc_{i}", pd.NA)
        c = _format_cedis_code(row.get(f"village_cedis_code_{i}", pd.NA))
        k = row.get(f"village_cedis_complaint_{i}", pd.NA)
        if _has_value(t) or _has_value(k):
            return t, c, k
    return None


def _all_events_for_row(row: pd.Series, col_lookup: dict[str, str]) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for loc, prefix, nmax, loc_rank in (
        ("village", "village", 19, 1),
        ("mhc_ed", "mhc_ed", 8, 2),
        ("mhc_inpatient", "mhc_inpatient", 5, 3),
        ("anmc_ed", "anmc_ed", 2, 4),
    ):
        for i in range(1, nmax + 1):
            txt = row.get(f"{prefix}_cc_{i}", pd.NA)
            code = _format_cedis_code(row.get(f"{prefix}_cedis_code_{i}", pd.NA))
            complaint = row.get(f"{prefix}_cedis_complaint_{i}", pd.NA)
            if _has_value(txt) or _has_value(code) or _has_value(complaint):
                dts_col = _resolve_encounter_start_dts_col(prefix, i, col_lookup)
                dts_val = row.get(dts_col, pd.NA) if dts_col else pd.NA
                events.append(
                    {
                        "loc_rank": loc_rank,
                        "slot": i,
                        "cc_location": loc,
                        "cc_text": txt,
                        "cc_cedis_code": code,
                        "cc_cedis_complaint": complaint,
                        "EncounterStartDTS": dts_val,
                        "EncounterStartDTS_source_col": dts_col if dts_col else pd.NA,
                    }
                )
    events.sort(key=lambda x: (int(x["loc_rank"]), int(x["slot"])))
    return events


def _add_hours_since_previous_cc(df: pd.DataFrame) -> pd.DataFrame:
    """Within each journey, hours from previous row's EncounterStartDTS when both parse."""
    if df.empty or "EncounterStartDTS" not in df.columns:
        return df
    out = df.copy()
    out["_dts_parsed"] = pd.to_datetime(out["EncounterStartDTS"], errors="coerce")
    out = out.sort_values(["journey_id", "cc_sequence"])
    delta = out.groupby("journey_id", sort=False)["_dts_parsed"].diff()
    out["hours_since_previous_cc"] = (delta.dt.total_seconds() / 3600.0).round(2)
    out = out.drop(columns=["_dts_parsed"])
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(REPO / "outputs" / "review_cc_audit"),
        help="Output directory for review CSVs.",
    )
    args = parser.parse_args()
    out_root = Path(args.output_dir).resolve()
    preg_dir = out_root / "pregnancy_cc_review"
    fu888_dir = out_root / "followup_888_review"
    preg_dir.mkdir(parents=True, exist_ok=True)
    fu888_dir.mkdir(parents=True, exist_ok=True)

    if not CHIEF_COMPLAINTS_WIDE.is_file():
        raise FileNotFoundError(f"Missing chief complaints file: {CHIEF_COMPLAINTS_WIDE}")

    cohort = filter_journeys_village_to_mhc(load_data()).drop_duplicates("journey_id").copy()
    cohort["journey_id"] = cohort["journey_id"].astype(str)
    cohort["age_at_medevac"] = pd.to_numeric(cohort["age_at_medevac"], errors="coerce")
    cohort["age_bin"] = cohort["age_at_medevac"].map(_age_label)
    cohort_min = cohort[["journey_id", "MRN", "age_at_medevac", "age_bin"]].copy()

    cc = pd.read_csv(CHIEF_COMPLAINTS_WIDE, low_memory=False)
    cc["journey_id"] = cc["journey_id"].astype(str)
    cc = cc[cc["journey_id"].isin(set(cohort["journey_id"]))].copy()
    cc = cc.merge(cohort_min, on=["journey_id", "MRN"], how="left")
    col_lookup = _ci_column_lookup(cc.columns)

    all_events_rows: list[dict[str, object]] = []
    village_primary_rows: list[dict[str, object]] = []
    for _, r in cc.iterrows():
        first_v = _first_village_triplet(r)
        v_txt, v_code, v_cmp = (pd.NA, pd.NA, pd.NA) if first_v is None else first_v
        village_primary_rows.append(
            {
                "journey_id": r["journey_id"],
                "MRN": r["MRN"],
                "age_at_medevac": r.get("age_at_medevac", pd.NA),
                "age_bin": r.get("age_bin", pd.NA),
                "village_primary_cc_text": v_txt,
                "village_primary_cedis_code": v_code,
                "village_primary_cedis_complaint": v_cmp,
            }
        )
        seq = 0
        for e in _all_events_for_row(r, col_lookup):
            seq += 1
            all_events_rows.append(
                {
                    "journey_id": r["journey_id"],
                    "MRN": r["MRN"],
                    "age_at_medevac": r.get("age_at_medevac", pd.NA),
                    "age_bin": r.get("age_bin", pd.NA),
                    "cc_sequence": seq,
                    "cc_location": e["cc_location"],
                    "cc_slot": e["slot"],
                    "cc_text": e["cc_text"],
                    "cc_cedis_code": e["cc_cedis_code"],
                    "cc_cedis_complaint": e["cc_cedis_complaint"],
                    "EncounterStartDTS": e["EncounterStartDTS"],
                    "EncounterStartDTS_source_col": e["EncounterStartDTS_source_col"],
                }
            )

    all_events = pd.DataFrame(all_events_rows)
    all_events = _add_hours_since_previous_cc(all_events)
    village_primary = pd.DataFrame(village_primary_rows)

    # ---- Pregnancy review ----
    preg_mask = (
        all_events["cc_cedis_complaint"].astype(str).str.contains("pregnancy", case=False, na=False)
        | all_events["cc_cedis_code"].astype(str).isin({"457", "458"})
    )
    preg_events = all_events[preg_mask].copy()
    preg_events.to_csv(preg_dir / "pregnancy_complaints_all_events.csv", index=False)

    preg_journeys = (
        preg_events[["journey_id", "MRN", "age_at_medevac", "age_bin"]].drop_duplicates().sort_values("journey_id")
    )
    preg_journeys.to_csv(preg_dir / "pregnancy_complaints_unique_journeys.csv", index=False)

    for age_bin, g in preg_events.groupby("age_bin", dropna=False):
        safe = str(age_bin).replace(" ", "_").replace("<", "lt").replace(">", "gt").replace("/", "_")
        g.sort_values(["journey_id", "cc_sequence"]).to_csv(
            preg_dir / f"pregnancy_events_{safe}.csv",
            index=False,
        )

    age_den = cohort_min[["MRN", "age_bin"]].drop_duplicates()
    age_num = preg_events[["MRN", "age_bin"]].drop_duplicates()
    den = age_den.groupby("age_bin").size().rename("patients_in_cohort")
    num = age_num.groupby("age_bin").size().rename("patients_with_pregnancy_cc")
    summ = pd.concat([den, num], axis=1).fillna(0).reset_index()
    summ["patients_in_cohort"] = summ["patients_in_cohort"].astype(int)
    summ["patients_with_pregnancy_cc"] = summ["patients_with_pregnancy_cc"].astype(int)
    summ["pct_of_age_bin_patients"] = (
        100.0 * summ["patients_with_pregnancy_cc"] / summ["patients_in_cohort"].clip(lower=1)
    ).round(1)
    summ.sort_values("age_bin").to_csv(preg_dir / "pregnancy_by_age_bin_summary.csv", index=False)

    # ---- Village primary 888 review ----
    fu888 = village_primary[village_primary["village_primary_cedis_code"].astype(str) == "888"].copy()
    fu888.to_csv(fu888_dir / "village_primary_888_journeys.csv", index=False)

    fu888_ids = set(fu888["journey_id"].astype(str))
    fu888_events = all_events[all_events["journey_id"].astype(str).isin(fu888_ids)].copy()
    fu888_events.to_csv(fu888_dir / "village_primary_888_all_events.csv", index=False)

    for age_bin, g in fu888_events.groupby("age_bin", dropna=False):
        safe = str(age_bin).replace(" ", "_").replace("<", "lt").replace(">", "gt").replace("/", "_")
        g.sort_values(["journey_id", "cc_sequence"]).to_csv(
            fu888_dir / f"village_primary_888_events_{safe}.csv",
            index=False,
        )

    # Reconstruct expanded target for each 888 journey (first non-888/999 code in order)
    expanded_rows: list[dict[str, object]] = []
    for jid, g in fu888_events.sort_values(["journey_id", "cc_sequence"]).groupby("journey_id", as_index=False):
        code = pd.NA
        complaint = pd.NA
        for _, r in g.iterrows():
            c = str(r.get("cc_cedis_code", "")).strip()
            if c and c not in {"888", "999"}:
                code = r.get("cc_cedis_code", pd.NA)
                complaint = r.get("cc_cedis_complaint", pd.NA)
                break
        expanded_rows.append(
            {
                "journey_id": jid,
                "MRN": g["MRN"].iloc[0],
                "age_at_medevac": g["age_at_medevac"].iloc[0],
                "age_bin": g["age_bin"].iloc[0],
                "expanded_cc_code": code,
                "expanded_cc_complaint": complaint,
                "expanded_cc_fu": "Yes" if _has_value(code) else "No",
            }
        )
    pd.DataFrame(expanded_rows).sort_values("journey_id").to_csv(
        fu888_dir / "village_primary_888_expanded_target_by_journey.csv",
        index=False,
    )

    print(f"Wrote review folders:\n- {preg_dir}\n- {fu888_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
