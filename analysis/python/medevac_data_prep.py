"""
Medevac data engineering: load, filter, compute derived variables, export
analysis-ready CSVs to outputs/data/ for R analysis.

Run from project root:
  python analysis/python/medevac_data_prep.py              # real data (PHI)
  python analysis/python/medevac_data_prep.py -synthetic   # de-ID + codebook

Outputs (outputs/data/):
  journeys_all.csv      — all journeys, route-classified, all computed columns
  journeys_primary.csv  — village→MHC cohort only
  patients_primary.csv  — one row per patient (earliest qualifying journey)
  legs_primary.csv      — one row per medevac leg in primary cohort
  village_census.csv    — village → 2020 pediatric population
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[2]

_pipeline_root = Path(
    os.environ.get("MEDEVAC_PIPELINE_DIR", ROOT.parent / "medevac_pipeline_project")
).resolve()
_pipeline_pediatric = _pipeline_root / "data" / "final" / "pediatric"
DATA = _pipeline_pediatric if _pipeline_pediatric.exists() else ROOT / "data"

VILLAGE_CODEBOOK  = ROOT / "docs" / "village_name_codebook.csv"
FACILITY_CODEBOOK = ROOT / "docs" / "facility_name_codebook.csv"
CENSUS_CSV        = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"
OUT_DATA          = ROOT / "outputs" / "data"

# Age group labels (ordered for display)
AGE_GROUPS = ["<1 yr", "1–<5 yr", "5–12 yr", "13–18 yr"]
AGE_GROUP_ORDER = {v: i for i, v in enumerate(AGE_GROUPS)}

# ── Village / facility resolution ──────────────────────────────────────────────

_VILLAGE_NAMES_CACHE: frozenset[str] | None = None
_VILLAGE_CODE_MAP_CACHE: dict[str, str] | None = None
_FACILITY_DISPLAY_CACHE: dict[str, str] | None = None
_ORIGIN_MODE_CACHE: str | None = None


def _origin_mode() -> str:
    global _ORIGIN_MODE_CACHE
    if _ORIGIN_MODE_CACHE:
        return _ORIGIN_MODE_CACHE
    env = os.environ.get("MEDEVAC_VILLAGE_ORIGINS", "").strip().lower()
    if env in {"infer", "codebook"}:
        _ORIGIN_MODE_CACHE = env
        return env
    if os.environ.get("MEDEVAC_SYNTHETIC", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        _ORIGIN_MODE_CACHE = "codebook"
    else:
        _ORIGIN_MODE_CACHE = "infer"
    return _ORIGIN_MODE_CACHE


def _village_names() -> frozenset[str]:
    global _VILLAGE_NAMES_CACHE
    if _VILLAGE_NAMES_CACHE is None:
        cb = pd.read_csv(VILLAGE_CODEBOOK)
        _VILLAGE_NAMES_CACHE = frozenset(cb["community_name"].astype(str))
    return _VILLAGE_NAMES_CACHE


def _village_code_map() -> dict[str, str]:
    global _VILLAGE_CODE_MAP_CACHE
    if _VILLAGE_CODE_MAP_CACHE is None:
        cb = pd.read_csv(VILLAGE_CODEBOOK)
        _VILLAGE_CODE_MAP_CACHE = dict(
            zip(cb["anonymous_code"].astype(str), cb["community_name"].astype(str), strict=True)
        )
    return _VILLAGE_CODE_MAP_CACHE


def _facility_display_map() -> dict[str, str]:
    global _FACILITY_DISPLAY_CACHE
    if _FACILITY_DISPLAY_CACHE is None:
        cb = pd.read_csv(FACILITY_CODEBOOK)
        _FACILITY_DISPLAY_CACHE = dict(
            zip(cb["code"].astype(str), cb["display_name"].astype(str), strict=True)
        )
    return _FACILITY_DISPLAY_CACHE


def _decode_village(x: object) -> object:
    s = str(x).strip()
    if _origin_mode() != "codebook" or not s.startswith("Village_"):
        return x
    return _village_code_map().get(s, x)


def _is_study_facility(place: object) -> bool:
    """Hub / CAH / outside hospital — not a village clinic."""
    if pd.isna(place):
        return True
    t = str(place).strip()
    if not t:
        return True
    u = t.upper().replace("_", "")
    if u.startswith("CAH") or u.startswith("HUB") or "OUTSIDEHOSPITAL" in u:
        return True
    tl = t.lower()
    if "maniilaq" in tl and "health" in tl:
        return True
    return tl == "mhc"


def is_village_origin(place: object) -> bool:
    s = str(place).strip()
    if not s:
        return False
    if _origin_mode() == "infer":
        return not _is_study_facility(s)
    return s.startswith("Village_") or s in _village_names()


def _is_mhc_dest(to_raw: object) -> bool:
    b = str(to_raw).strip()
    bl = b.lower()
    return (
        b == "CAH_01"
        or b.startswith("CAH")
        or b.upper() == "MHC"
        or " mhc" in f" {bl}"
        or "maniilaq health center" in bl
    )


def _dest_label(to_raw: str) -> str:
    b = str(to_raw).strip()
    if b.startswith("CAH") or b == "CAH_01":
        return "Maniilaq Health Center"
    if b.startswith("Hub") or b.upper() in ("HUB_01", "ANMC"):
        return "ANMC"
    if b == "OutsideHospital02":
        return "UW"
    if b == "OutsideHospital03":
        return "Providence"
    fdm = _facility_display_map()
    return fdm.get(b, b)


def _origin_with_fallback(row: pd.Series, leg_idx: int) -> str:
    fc = f"medevac{leg_idx}_from"
    a = str(row.get(fc, "")).strip()
    if leg_idx == 1 and (not a or _is_study_facility(a)):
        f1 = str(row.get("facility_1_name", "")).strip()
        if f1:
            return f1
    return a


# ── Route classification ───────────────────────────────────────────────────────

def classify_route(row: pd.Series) -> str:
    first_to = ""
    second_to = ""
    found_first = False
    for i in (1, 2, 3):
        to_val = str(row.get(f"medevac{i}_to", "") or "").strip()
        from_val = str(row.get(f"medevac{i}_from", "") or "").strip()
        if not to_val:
            continue
        if not found_first:
            if i == 1 or is_village_origin(from_val):
                first_to = to_val
                found_first = True
        else:
            second_to = to_val
            break
    if not first_to:
        return "Unknown"
    if _is_mhc_dest(first_to):
        return "Secondary transfer" if second_to else "Primary (village → MHC)"
    return "Direct tertiary"


def _qualifies_for_primary_cohort(row: pd.Series) -> bool:
    """At least one village clinic → MHC leg."""
    for i in (1, 2, 3):
        fc, tc = f"medevac{i}_from", f"medevac{i}_to"
        if fc not in row.index or tc not in row.index:
            continue
        if pd.isna(row[fc]) or pd.isna(row[tc]) or not str(row[fc]).strip():
            continue
        a = _origin_with_fallback(row, i)
        b = str(row[tc]).strip()
        if is_village_origin(a) and _is_mhc_dest(b):
            return True
    return False


# ── Age grouping ───────────────────────────────────────────────────────────────

def age_group(age_years: float | None) -> str | None:
    if pd.isna(age_years):
        return None
    a = float(age_years)
    if a < 1:
        return "<1 yr"
    if a < 5:
        return "1–<5 yr"
    if a <= 12:
        return "5–12 yr"
    if a <= 18:
        return "13–18 yr"
    return None


# ── CEDIS primary complaint ────────────────────────────────────────────────────

_CEDIS_CATEGORY_MAP: dict[int, str] = {
    100: "Cardiac/Vascular", 101: "Cardiac/Vascular", 102: "Cardiac/Vascular",
    103: "Cardiac/Vascular", 104: "Cardiac/Vascular", 105: "Cardiac/Vascular",
    106: "Cardiac/Vascular", 107: "Cardiac/Vascular", 108: "Cardiac/Vascular",
    109: "Cardiac/Vascular", 110: "Cardiac/Vascular",
    200: "Respiratory", 201: "Respiratory", 202: "Respiratory", 203: "Respiratory",
    204: "Respiratory", 205: "Respiratory", 206: "Respiratory", 207: "Respiratory",
    208: "Respiratory", 209: "Respiratory", 210: "Respiratory", 211: "Respiratory",
    212: "Respiratory", 213: "Respiratory", 214: "Respiratory",
    251: "Abdominal/GI", 252: "Abdominal/GI", 253: "Abdominal/GI", 254: "Abdominal/GI",
    255: "Abdominal/GI", 256: "Abdominal/GI", 257: "Abdominal/GI", 258: "Abdominal/GI",
    259: "Abdominal/GI", 260: "Abdominal/GI", 261: "Abdominal/GI",
    300: "Neurological", 301: "Neurological", 302: "Neurological", 303: "Neurological",
    304: "Neurological", 305: "Neurological", 306: "Neurological",
    350: "Psychiatric", 351: "Psychiatric", 352: "Psychiatric", 353: "Psychiatric",
    400: "Trauma/MSK", 401: "Trauma/MSK", 402: "Trauma/MSK", 403: "Trauma/MSK",
    404: "Trauma/MSK", 405: "Trauma/MSK", 406: "Trauma/MSK", 407: "Trauma/MSK",
    408: "Trauma/MSK", 409: "Trauma/MSK", 410: "Trauma/MSK", 411: "Trauma/MSK",
    412: "Trauma/MSK", 413: "Trauma/MSK", 414: "Trauma/MSK", 415: "Trauma/MSK",
    416: "Trauma/MSK", 417: "Trauma/MSK",
    500: "Genitourinary/GYN", 501: "Genitourinary/GYN", 502: "Genitourinary/GYN",
    503: "Genitourinary/GYN", 504: "Genitourinary/GYN",
    600: "ENT/Eyes", 601: "ENT/Eyes", 602: "ENT/Eyes", 603: "ENT/Eyes",
    604: "ENT/Eyes", 605: "ENT/Eyes", 606: "ENT/Eyes",
    650: "Respiratory", 651: "Respiratory", 652: "Respiratory", 653: "Respiratory",
    654: "Respiratory", 655: "Respiratory",
    700: "General/Minor", 701: "General/Minor", 702: "General/Minor", 703: "General/Minor",
    704: "General/Minor", 705: "General/Minor", 706: "General/Minor", 707: "General/Minor",
    708: "General/Minor", 709: "General/Minor", 710: "General/Minor", 711: "General/Minor",
    712: "General/Minor", 713: "General/Minor", 714: "General/Minor",
    750: "Toxicology", 751: "Toxicology", 752: "Toxicology", 753: "Toxicology",
    800: "Metabolic/Endocrine", 801: "Metabolic/Endocrine", 802: "Metabolic/Endocrine",
    803: "Metabolic/Endocrine", 804: "Metabolic/Endocrine", 850: "Metabolic/Endocrine",
    851: "Metabolic/Endocrine", 852: "Metabolic/Endocrine", 853: "Metabolic/Endocrine",
    854: "Metabolic/Endocrine",
}


def _primary_cedis(cc_row: pd.Series) -> tuple[int | None, str | None, str | None]:
    """
    Extract the primary CEDIS code/complaint for a journey.
    Priority: first non-888/999 village slot; if none, use 888 if present.
    Returns (code, complaint, category).
    """
    follow_up_code = None
    for slot in range(1, 20):
        code_col = f"village_cedis_code_{slot}"
        complaint_col = f"village_cedis_complaint_{slot}"
        if code_col not in cc_row.index:
            break
        raw_code = cc_row.get(code_col)
        raw_complaint = cc_row.get(complaint_col)
        if pd.isna(raw_code):
            continue
        try:
            code_int = int(float(raw_code))
        except (ValueError, TypeError):
            continue
        complaint = str(raw_complaint).strip() if pd.notna(raw_complaint) else None
        if code_int in (888, 999):
            if follow_up_code is None:
                follow_up_code = (code_int, complaint, "Follow-up/Unknown")
            continue
        category = _CEDIS_CATEGORY_MAP.get(code_int, "General/Minor")
        return code_int, complaint, category
    if follow_up_code:
        return follow_up_code
    return None, None, None


# ── Data loading ───────────────────────────────────────────────────────────────

def load_raw() -> pd.DataFrame:
    """Load and merge all source files into a journey-level DataFrame."""
    journeys = pd.read_csv(DATA / "pediatric_medevac_journeys.csv")
    timing   = pd.read_csv(DATA / "pediatric_medevac_timing.csv")
    outcomes = pd.read_csv(DATA / "pediatric_outcomes.csv")
    patients = pd.read_csv(DATA / "pediatric_patients.csv")

    timing_extra = [
        c for c in timing.columns
        if c not in ("journey_id", "MRN", "origin_type") and c not in journeys.columns
    ]
    df = journeys.merge(timing[["journey_id"] + timing_extra], on="journey_id", how="left")

    for base in [f"medevac{i}_{s}" for i in (1, 2, 3) for s in ("from", "to", "id")] + ["facility_1_name"]:
        if base in df.columns:
            continue
        for cand in (f"{base}_x", f"{base}_y"):
            if cand in df.columns:
                df[base] = df[cand]
                break

    outcome_cols = [
        "death_at_facility", "days_to_discharge", "days_to_death",
        "24hr_mortality", "7d_mortality", "30d_mortality",
        "ed_discharge", "short_<36h_admission", "icu_admission", "had_surgery",
    ]
    out_keep = ["journey_id"] + [c for c in outcome_cols if c in outcomes.columns]
    df = df.merge(outcomes[out_keep], on="journey_id", how="left")
    df = df.merge(patients, on="MRN", how="left")

    if _origin_mode() == "codebook":
        for c in ("facility_1_name", "medevac1_from", "medevac2_from", "medevac3_from"):
            if c in df.columns:
                df[c] = df[c].map(_decode_village)

    return df


def _village_name_for_journey(row: pd.Series) -> str:
    """Best village name: facility_1_name if it's a village, else medevac1_from."""
    f1 = str(row.get("facility_1_name", "")).strip()
    if f1 and is_village_origin(f1):
        return f1
    m1 = str(row.get("medevac1_from", "")).strip()
    if m1 and is_village_origin(m1):
        return m1
    return f1 or m1 or ""


# ── Derived variable computation ───────────────────────────────────────────────

def compute_derived(df: pd.DataFrame, cc: pd.DataFrame) -> pd.DataFrame:
    """Add route_type, village_name, age_group, CEDIS columns to journey DataFrame."""
    df = df.copy()

    df["route_type"] = df.apply(classify_route, axis=1)
    df["village_name"] = df.apply(_village_name_for_journey, axis=1)

    df["age_at_medevac_num"] = pd.to_numeric(df.get("age_at_medevac"), errors="coerce")
    df["age_group"] = df["age_at_medevac_num"].map(age_group)
    df["age_group"] = pd.Categorical(df["age_group"], categories=AGE_GROUPS, ordered=True)

    # Primary CEDIS per journey
    if cc is not None and len(cc):
        cc_indexed = cc.set_index("journey_id")
        cedis_rows = df["journey_id"].map(
            lambda jid: _primary_cedis(cc_indexed.loc[jid]) if jid in cc_indexed.index else (None, None, None)
        )
        df["primary_cedis_code"]      = [r[0] for r in cedis_rows]
        df["primary_cedis_complaint"] = [r[1] for r in cedis_rows]
        df["primary_cedis_category"]  = [r[2] for r in cedis_rows]

    return df


# ── Export helpers ─────────────────────────────────────────────────────────────

def _write(df: pd.DataFrame, name: str) -> None:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    path = OUT_DATA / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(df):,} rows)")


def build_patients_primary(df_primary: pd.DataFrame) -> pd.DataFrame:
    """One row per patient: earliest qualifying journey. Patient-level demographics."""
    df_sorted = df_primary.sort_values("age_at_medevac_num")
    first = df_sorted.groupby("MRN", sort=False).first().reset_index()

    journey_counts = df_primary.groupby("MRN")["journey_id"].nunique().rename("n_journeys_primary")
    first = first.merge(journey_counts, on="MRN", how="left")

    keep = [
        "MRN", "village_name", "age_at_medevac_num", "age_group",
        "n_journeys_primary",
        "primary_cedis_code", "primary_cedis_complaint", "primary_cedis_category",
    ]
    for phi_col in ("GenderDSC", "AI_AN", "RaceDSC", "PrimaryPayorNM"):
        if phi_col in first.columns:
            keep.append(phi_col)

    return first[[c for c in keep if c in first.columns]]


def build_legs_primary(df_primary: pd.DataFrame) -> pd.DataFrame:
    """One row per medevac leg in the primary cohort (for route tables)."""
    rows = []
    for _, r in df_primary.iterrows():
        for i in (1, 2, 3):
            frm_raw = r.get(f"medevac{i}_from")
            to_raw  = r.get(f"medevac{i}_to")
            if pd.isna(frm_raw) or pd.isna(to_raw):
                continue
            frm = str(frm_raw).strip()
            to  = str(to_raw).strip()
            if not frm or not to:
                continue
            rows.append({
                "journey_id": r["journey_id"],
                "MRN": r["MRN"],
                "leg_num": i,
                "origin": frm,
                "destination_raw": to,
                "destination_label": _dest_label(to),
                "is_village_origin": is_village_origin(frm),
                "is_mhc_dest": _is_mhc_dest(to),
                "route_type": r["route_type"],
            })
    return pd.DataFrame(rows)


def build_village_census() -> pd.DataFrame:
    census = pd.read_csv(CENSUS_CSV)
    keep = [c for c in ("NAME", "name", "village_name", "total_pop", "pediatric_pop", "pct_pediatric") if c in census.columns]
    return census[keep]


# ── Main ───────────────────────────────────────────────────────────────────────

def main(synthetic: bool = False) -> None:
    if synthetic:
        os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "codebook"
    try:
        data_display = DATA.relative_to(ROOT)
    except ValueError:
        data_display = DATA
    print(f"[data_prep] mode={_origin_mode()}  data={data_display}")

    print("Loading source data...")
    df_raw = load_raw()

    cc = pd.read_csv(DATA / "pediatric_chiefcomplaints.csv") if (DATA / "pediatric_chiefcomplaints.csv").exists() else pd.DataFrame()

    print("Computing derived variables...")
    df = compute_derived(df_raw, cc)

    print("Filtering primary cohort (village → MHC)...")
    mask = df.apply(_qualifies_for_primary_cohort, axis=1)
    df_primary = df[mask].copy()

    print("Exporting analysis-ready CSVs:")
    _write(df, "journeys_all")
    _write(df_primary, "journeys_primary")
    _write(build_patients_primary(df_primary), "patients_primary")
    _write(build_legs_primary(df_primary), "legs_primary")
    _write(build_village_census(), "village_census")

    print(f"\nDone. {len(df_primary):,} primary journeys, {df_primary['MRN'].nunique():,} unique patients.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-synthetic", "--synthetic", action="store_true")
    args = parser.parse_args()
    main(synthetic=args.synthetic)
