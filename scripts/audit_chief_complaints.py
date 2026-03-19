#!/usr/bin/env python3
"""
Audit chief complaints for pediatric medevac cohort.

Outputs review CSVs in separate folders for:
  1) Pregnancy-related complaints (by age bin)
  2) Village primary CEDIS 888 journeys

Run from repo root:
  python scripts/audit_chief_complaints.py

PHI timing: prefer ``data/pediatric_chiefcomplaints_long.csv`` (override with
``MEDEVAC_CHIEF_COMPLAINTS_LONG`` or ``--chief-complaints-long``), which should
include ``EncounterStartDTS`` per row plus a location/phase column (e.g.
``facility_phase``). Wide file per-slot ``*_EncounterStartDTS_*`` columns are
still used when present.

Populates ``hours_since_previous_cc`` when consecutive rows parse as datetimes.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CHIEF_COMPLAINTS_LONG = REPO / "data" / "pediatric_chiefcomplaints_long.csv"
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


def _pick_ci_col(lookup: dict[str, str], *names: str) -> str | None:
    for n in names:
        c = lookup.get(n.lower())
        if c:
            return c
    return None


def _find_encounter_start_dts_column(columns: pd.Index) -> str | None:
    lk = _ci_column_lookup(columns)
    for key in ("encounterstartdts", "encounter_start_dts", "encounterstart_dt"):
        if key in lk:
            return lk[key]
    for c in columns:
        cl = str(c).lower()
        if "encounterstart" in cl.replace("_", "") and "dts" in cl:
            return str(c)
    return None


def _normalize_long_cc_location(phase_raw: object) -> str | None:
    """Map long-file phase/location text to audit cc_location codes."""
    if pd.isna(phase_raw):
        return None
    s = str(phase_raw).strip().lower().replace(" ", "_").replace("-", "_")
    if not s:
        return None
    if s in {"village", "village_clinic", "clinic", "chs"}:
        return "village"
    if "anmc" in s and "inpatient" in s:
        return "anmc_inpatient"
    if "anmc" in s and ("ed" in s or "er" in s or "emergency" in s):
        return "anmc_ed"
    if "anmc" in s:
        return "anmc_ed"
    if "mhc" in s and ("inpatient" in s or "_ip" == s[-3:] or s.endswith("ip")):
        return "mhc_inpatient"
    if "mhc" in s and ("ed" in s or "er" in s or "emergency" in s):
        return "mhc_ed"
    if "mhc" in s:
        return "mhc_ed"
    if "village" in s:
        return "village"
    return None


def _norm_cc_text(x: object) -> str:
    if not _has_value(x):
        return ""
    return " ".join(str(x).lower().split())


def _prepare_chief_complaints_long(
    lg: pd.DataFrame,
) -> pd.DataFrame | None:
    """
    Return long extract with journey_id, cc_location, cc_slot, EncounterStartDTS,
    plus optional _code_n, _cmp_n, _txt for fallback matching.
    """
    if lg.empty:
        return None
    lk = _ci_column_lookup(lg.columns)
    jid_c = _pick_ci_col(lk, "journey_id")
    dts_c = _find_encounter_start_dts_column(lg.columns)
    phase_c = _pick_ci_col(
        lk,
        "facility_phase",
        "cc_location",
        "location",
        "encounter_location",
        "phase",
        "cc_facility_phase",
    )
    if not jid_c or not dts_c or not phase_c:
        return None

    code_c = _pick_ci_col(lk, "cedis_code", "village_cedis_code", "mhc_ed_cedis_code", "cediscode")
    cmp_c = _pick_ci_col(
        lk,
        "cedis_complaint",
        "chief_complaint",
        "cediscomplaint",
        "cc_complaint",
    )
    txt_c = _pick_ci_col(lk, "cc_text", "chief_complaint_text", "complaint_text", "free_text_cc")

    out = lg[[jid_c, phase_c, dts_c]].copy()
    out.columns = ["journey_id", "_phase_raw", "EncounterStartDTS"]
    out["journey_id"] = out["journey_id"].astype(str)
    out["cc_location"] = out["_phase_raw"].map(_normalize_long_cc_location)
    out = out[out["cc_location"].notna()].copy()
    if out.empty:
        return None

    out["_dts_sort"] = pd.to_datetime(out["EncounterStartDTS"], errors="coerce")
    out = out.sort_values(["journey_id", "cc_location", "_dts_sort"], na_position="last")
    out["cc_slot"] = out.groupby(["journey_id", "cc_location"], sort=False).cumcount() + 1

    if code_c and code_c in lg.columns:
        out["_code_n"] = lg.loc[out.index, code_c].map(_format_cedis_code).astype(str)
    else:
        out["_code_n"] = ""
    if cmp_c and cmp_c in lg.columns:
        out["_cmp_n"] = lg.loc[out.index, cmp_c].fillna("").astype(str).str.strip().str.lower()
    else:
        out["_cmp_n"] = ""
    if txt_c and txt_c in lg.columns:
        out["_txt"] = lg.loc[out.index, txt_c].map(_norm_cc_text)
    else:
        out["_txt"] = ""

    out = out.drop(columns=["_phase_raw", "_dts_sort"])
    out = out.drop_duplicates(subset=["journey_id", "cc_location", "cc_slot"], keep="first")
    return out


def _dts_missing(s: pd.Series) -> pd.Series:
    return s.isna() | (s.astype(str).str.strip() == "") | (s.astype(str).str.lower() == "nan")


def merge_encounter_dts_from_long(
    events: pd.DataFrame,
    long_path: Path,
    cohort_journey_ids: set[str],
) -> pd.DataFrame:
    """Fill EncounterStartDTS / source from pediatric_chiefcomplaints_long.csv when missing."""
    if events.empty:
        return events
    if not long_path.is_file():
        return _add_hours_since_previous_cc(events)
    lg = pd.read_csv(long_path, low_memory=False)
    lg = lg[lg["journey_id"].astype(str).isin(cohort_journey_ids)].copy()
    long_idx = _prepare_chief_complaints_long(lg)
    if long_idx is None or long_idx.empty:
        return events

    m = events.copy()
    m["journey_id"] = m["journey_id"].astype(str)
    tag = long_path.name

    slot_tbl = long_idx[["journey_id", "cc_location", "cc_slot", "EncounterStartDTS"]].rename(
        columns={"EncounterStartDTS": "_dts_slot"}
    )
    m = m.merge(slot_tbl, on=["journey_id", "cc_location", "cc_slot"], how="left")
    slot_ok = m["_dts_slot"].notna() & (m["_dts_slot"].astype(str).str.strip() != "")
    wide_miss = _dts_missing(m["EncounterStartDTS"])
    fill = wide_miss & slot_ok
    m.loc[fill, "EncounterStartDTS"] = m.loc[fill, "_dts_slot"]
    m.loc[fill, "EncounterStartDTS_source_col"] = f"{tag}(journey+location+slot)"
    m = m.drop(columns=["_dts_slot"])

    still = _dts_missing(m["EncounterStartDTS"])
    if still.any() and "_code_n" in long_idx.columns:
        key_long = long_idx[
            (long_idx["_code_n"].astype(str).str.strip() != "")
            | (long_idx["_cmp_n"].astype(str).str.strip() != "")
        ][["journey_id", "cc_location", "_code_n", "_cmp_n", "EncounterStartDTS"]].copy()
        key_long = key_long.drop_duplicates(
            ["journey_id", "cc_location", "_code_n", "_cmp_n"], keep="first"
        ).rename(columns={"EncounterStartDTS": "_dts_k"})
        if not key_long.empty:
            sub = m.loc[still].copy()
            sub["_audit_row_id"] = sub.index
            sub["_code_n"] = sub["cc_cedis_code"].map(_format_cedis_code).astype(str)
            sub["_cmp_n"] = sub["cc_cedis_complaint"].fillna("").astype(str).str.strip().str.lower()
            merged = sub.merge(key_long, on=["journey_id", "cc_location", "_code_n", "_cmp_n"], how="left")
            ok = merged["_dts_k"].notna() & (merged["_dts_k"].astype(str).str.strip() != "")
            rid = merged.loc[ok, "_audit_row_id"].values
            m.loc[rid, "EncounterStartDTS"] = merged.loc[ok, "_dts_k"].values
            m.loc[rid, "EncounterStartDTS_source_col"] = f"{tag}(cedis_code+complaint)"

    still = _dts_missing(m["EncounterStartDTS"])
    if still.any() and long_idx["_txt"].astype(str).str.strip().ne("").any():
        key_t = long_idx[long_idx["_txt"].astype(str).str.strip() != ""][
            ["journey_id", "cc_location", "_txt", "EncounterStartDTS"]
        ].copy()
        key_t = key_t.drop_duplicates(["journey_id", "cc_location", "_txt"], keep="first").rename(
            columns={"EncounterStartDTS": "_dts_t"}
        )
        sub = m.loc[still].copy()
        sub["_audit_row_id"] = sub.index
        sub["_txt"] = sub["cc_text"].map(_norm_cc_text)
        sub = sub[sub["_txt"].astype(str).str.strip() != ""]
        if not sub.empty:
            merged = sub.merge(key_t, on=["journey_id", "cc_location", "_txt"], how="left")
            ok = merged["_dts_t"].notna() & (merged["_dts_t"].astype(str).str.strip() != "")
            rid = merged.loc[ok, "_audit_row_id"].values
            m.loc[rid, "EncounterStartDTS"] = merged.loc[ok, "_dts_t"].values
            m.loc[rid, "EncounterStartDTS_source_col"] = f"{tag}(cc_text)"

    return _add_hours_since_previous_cc(m)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=str(REPO / "outputs" / "review_cc_audit"),
        help="Output directory for review CSVs.",
    )
    parser.add_argument(
        "--chief-complaints-long",
        default=None,
        help="Path to pediatric_chiefcomplaints_long.csv (default: env MEDEVAC_CHIEF_COMPLAINTS_LONG or data/pediatric_chiefcomplaints_long.csv).",
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
    long_path = Path(
        args.chief_complaints_long
        or os.environ.get("MEDEVAC_CHIEF_COMPLAINTS_LONG", str(DEFAULT_CHIEF_COMPLAINTS_LONG))
    ).resolve()
    all_events = merge_encounter_dts_from_long(all_events, long_path, set(cc["journey_id"]))
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
