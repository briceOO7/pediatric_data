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
_local_data = ROOT / "data"

if _pipeline_pediatric.exists():
    DATA = _pipeline_pediatric
elif _local_data.exists() and any(_local_data.glob("*.csv")):
    # Explicit warning so it's never silent
    import warnings
    warnings.warn(
        f"Pipeline data not found at {_pipeline_pediatric}. "
        f"Falling back to local data/ — use -synthetic flag and ensure this is intentional.",
        stacklevel=1,
    )
    DATA = _local_data
else:
    raise FileNotFoundError(
        f"No data source found.\n"
        f"  Expected pipeline data at: {_pipeline_pediatric}\n"
        f"  No local data/ CSVs found either.\n"
        f"  On PHI machine: ensure medevac_pipeline_project is a sibling directory.\n"
        f"  On dev machine: place synthetic extract in data/ and use -synthetic flag."
    )

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

def _safe_str(val: object) -> str:
    """Convert a value to string, returning '' for NaN/None."""
    if val is None or (isinstance(val, float) and val != val):  # NaN check
        return ""
    s = str(val).strip()
    return "" if s.lower() == "nan" else s


def classify_route(row: pd.Series) -> str:
    first_to = ""
    second_to = ""
    found_first = False
    for i in (1, 2, 3):
        to_val = _safe_str(row.get(f"medevac{i}_to"))
        from_val = _safe_str(row.get(f"medevac{i}_from"))
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

# CEDIS 3.1 code → category (matches medevac_summaries.py)
_CEDIS_CATEGORY_MAP: dict[int, str] = {
    **{c: "Cardiovascular"    for c in range(1,   13)},
    **{c: "ENT"               for c in range(51,  57)},
    **{c: "ENT"               for c in range(101, 108)},
    **{c: "ENT"               for c in range(151, 156)},
    **{c: "Environmental"     for c in range(201, 207)},
    **{c: "Gastrointestinal"  for c in range(251, 268)},
    **{c: "Genitourinary"     for c in range(301, 311)},
    **{c: "Mental Health"     for c in range(351, 361)},
    **{c: "Neurologic"        for c in range(401, 412)},
    **{c: "OB/GYN"            for c in range(451, 461)},
    **{c: "Ophthalmology"     for c in range(502, 512)},
    **{c: "Orthopedic"        for c in range(551, 560)},
    **{c: "Respiratory"       for c in range(651, 661)},
    **{c: "Skin"              for c in range(701, 718)},
    **{c: "Substance Misuse"  for c in range(751, 754)},
    **{c: "Trauma"            for c in range(801, 807)},
    **{c: "General and Minor" for c in range(851, 891)},
}

# Categories collapsed to a group label in the custom grouping
_CC_GROUPED_CATS: dict[str, str] = {
    "Respiratory":      "Respiratory",
    "Gastrointestinal": "Gastrointestinal",
    "Trauma":           "Trauma/Injury",
    "Orthopedic":       "Trauma/Injury",
}

# Individual complaint text overrides (case-insensitive; take priority over category rule)
_CC_GROUPED_COMPLAINTS: dict[str, str] = {
    "Head injury":       "Trauma/Injury",
    "Facial trauma":     "Trauma/Injury",
    "Neck trauma":       "Trauma/Injury",
    "Genital trauma":    "Trauma/Injury",
    "Eye trauma":        "Trauma/Injury",
    "Trauma/Orthopedic": "Trauma/Injury",
    "URTI complaints":   "Respiratory",
}



def _cc_custom_group(complaint: str, code_int: int) -> str:
    """Apply custom grouping to a (complaint text, CEDIS code) pair."""
    complaint_key = next(
        (k for k in _CC_GROUPED_COMPLAINTS if k.lower() == complaint.lower()), None
    )
    if complaint_key:
        return _CC_GROUPED_COMPLAINTS[complaint_key]
    category = _CEDIS_CATEGORY_MAP.get(code_int, "General and Minor")
    return _CC_GROUPED_CATS.get(category, complaint)


# Facility phase sort priority: village complaints always take precedence,
# then chronological order within each facility so late-entered records at
# an earlier site still override anything from a later site.
_CC_PHASE_ORDER: dict[str, int] = {
    "village":       0,
    "mhc_ed":        1,
    "mhc_inpatient": 2,
    "anmc_ed":       3,
}


def _build_definitive_cc(cc_long: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the definitive chief complaint per journey from the long-format
    CC file (pediatric_chiefcomplaints_alternate_long.csv).

    Sort order: facility phase (village → mhc_ed → mhc_inpatient → anmc_ed),
    then chronologically within each facility (EncounterStartDTS, cc_sequence).
    This ensures a complaint entered late at an earlier site still wins over
    one entered first at a later site (guards against registration-order errors).

    Take the first complaint whose CEDIS code is not 888 or 999.
    Journeys where every complaint is 888/999 → None (excluded from table).

    Returns a DataFrame with columns:
      journey_id, primary_cedis_code, primary_cedis_complaint,
      primary_cedis_category, primary_cedis_custom_group
    """
    df = cc_long.copy()

    def _is_skip_code(x: object) -> bool:
        try:
            return int(float(x)) in (888, 999)
        except (ValueError, TypeError):
            return False

    df["_skip"]      = df["cedis_code"].map(_is_skip_code)
    df["_phase_ord"] = df["facility_phase"].map(_CC_PHASE_ORDER).fillna(99)
    df["_ts"]        = pd.to_datetime(df["EncounterStartDTS"], errors="coerce")

    df = df.sort_values(["journey_id", "_phase_ord", "_ts", "cc_sequence"])

    # Take first non-skipped complaint per journey
    valid = df[~df["_skip"] & df["cedis_complaint"].notna() & (df["cedis_complaint"].str.strip() != "")]
    first = valid.groupby("journey_id", sort=False).first().reset_index()

    def _safe_code(x: object) -> int | None:
        try:
            return int(float(x))
        except (ValueError, TypeError):
            return None

    first["_code_int"]  = first["cedis_code"].map(_safe_code)
    first["_category"]  = first["_code_int"].map(lambda c: _CEDIS_CATEGORY_MAP.get(c, "General and Minor") if c else None)
    first["_cg"]        = first.apply(
        lambda r: _cc_custom_group(str(r["cedis_complaint"]).strip(), r["_code_int"] or 0)
        if pd.notna(r["cedis_complaint"]) else None,
        axis=1,
    )

    return first[["journey_id"]].assign(
        primary_cedis_code         = first["_code_int"],
        primary_cedis_complaint    = first["cedis_complaint"].str.strip(),
        primary_cedis_category     = first["_category"],
        primary_cedis_custom_group = first["_cg"],
    )


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
    """First village-origin location found across facility_1 and all medevac legs.

    Checks all three medevac legs so journeys where the village leg is leg 2 or 3
    (e.g. secondary transfers where facility_1 is MHC) still get the correct village
    name rather than falling back to 'MHC'.  Returns '' if no village is found.
    """
    f1 = str(row.get("facility_1_name", "")).strip()
    if f1 and is_village_origin(f1):
        return f1
    for i in (1, 2, 3):
        m = str(row.get(f"medevac{i}_from", "")).strip()
        if m and is_village_origin(m):
            return m
    return ""


# ── Derived variable computation ───────────────────────────────────────────────

def compute_derived(df: pd.DataFrame, cc: pd.DataFrame | None = None) -> pd.DataFrame:
    """Add route_type, village_name, age_group, CEDIS columns to journey DataFrame."""
    df = df.copy()

    df["route_type"] = df.apply(classify_route, axis=1)
    df["village_name"] = df.apply(_village_name_for_journey, axis=1)

    df["age_at_medevac_num"] = pd.to_numeric(df.get("age_at_medevac"), errors="coerce")
    df["age_group"] = df["age_at_medevac_num"].map(age_group)
    df["age_group"] = pd.Categorical(df["age_group"], categories=AGE_GROUPS, ordered=True)

    # Primary CEDIS per journey — prefer long-format alternate file (has is_follow_up flag)
    _cc_long_path = DATA / "pediatric_chiefcomplaints_alternate_long.csv"
    if _cc_long_path.exists():
        cc_long = pd.read_csv(_cc_long_path, low_memory=False)
        cc_long["journey_id"] = cc_long["journey_id"].astype(str).str.strip()
        cc_def = _build_definitive_cc(cc_long)
        cc_def = cc_def.set_index("journey_id")
        for col in ("primary_cedis_code", "primary_cedis_complaint",
                    "primary_cedis_category", "primary_cedis_custom_group"):
            df[col] = df["journey_id"].map(cc_def[col] if col in cc_def.columns else pd.Series(dtype="object"))

    return df


# ── Export helpers ─────────────────────────────────────────────────────────────

def _write(df: pd.DataFrame, name: str) -> None:
    OUT_DATA.mkdir(parents=True, exist_ok=True)
    path = OUT_DATA / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"  wrote {path.relative_to(ROOT)}  ({len(df):,} rows)")


def _insurance_category(raw: object) -> str | None:
    """Classify PrimaryPayorNM into 5 standard groups (matches medevac_summaries.py)."""
    r = str(raw).lower().strip()
    if r in ("nan", "", "missing", "unknown", "none"):
        return None
    if any(x in r for x in ("commercial", "private", "blue cross", "aetna", "cigna", "united", "humana")):
        return "Commercial"
    if any(x in r for x in ("medicaid", "medicare", "chip", "government", "tricare", "va ")):
        return "Government"
    if any(x in r for x in ("ihs", "indian health", "tribal")):
        return "IHS"
    if any(x in r for x in ("self", "uninsured", "none", "no insurance")):
        return "Self-Pay"
    return "Other"


def build_patients_primary(df_primary: pd.DataFrame) -> pd.DataFrame:
    """One row per patient: earliest qualifying journey. Patient-level demographics."""
    df_sorted = df_primary.sort_values("age_at_medevac_num")
    first = df_sorted.groupby("MRN", sort=False).first().reset_index()

    journey_counts = df_primary.groupby("MRN")["journey_id"].nunique().rename("n_journeys_primary")
    first = first.merge(journey_counts, on="MRN", how="left")

    # Insurance category (PHI column; None if absent)
    if "PrimaryPayorNM" in first.columns:
        first["insurance_cat"] = first["PrimaryPayorNM"].map(_insurance_category)

    keep = [
        "MRN", "village_name", "age_at_medevac_num", "age_group",
        "n_journeys_primary",
        "primary_cedis_code", "primary_cedis_complaint",
        "primary_cedis_category", "primary_cedis_custom_group",
    ]
    for phi_col in ("GenderDSC", "AI_AN", "RaceDSC", "PrimaryPayorNM", "insurance_cat"):
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


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import radians, cos, sin, asin, sqrt
    R = 3958.8
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * asin(sqrt(a))


def _village_distances() -> dict[str, float]:
    """Village → Kotzebue straight-line distance in miles from shapefile."""
    shp = ROOT / "mapping_data" / "healthcare_facilities_safetynet" / \
          "healthcare_facilities_safetynet.shp"
    if not shp.is_file():
        return {}
    try:
        import geopandas as gpd
        fac = gpd.read_file(shp).to_crs(epsg=4326)
        man = fac[fac["ManagingOr"] == "Maniilaq Association"][
            ["CommunityN", "geometry"]
        ].drop_duplicates("CommunityN")
        kotz = man[man["CommunityN"].str.lower() == "kotzebue"]
        if kotz.empty:
            return {}
        klon, klat = float(kotz.iloc[0].geometry.x), float(kotz.iloc[0].geometry.y)
        return {
            str(r["CommunityN"]).strip(): round(_haversine_miles(klat, klon, float(r.geometry.y), float(r.geometry.x)))
            for _, r in man.iterrows()
        }
    except Exception:
        return {}


def _med_iqr_range(series: pd.Series) -> dict:
    """Return dict of median, q1, q3, min, max, n for a numeric series."""
    s = pd.to_numeric(series, errors="coerce").dropna()
    n = len(s)
    if n == 0:
        return dict(median=None, q1=None, q3=None, lo=None, hi=None, n=0)
    return dict(
        median=round(float(s.median()), 1),
        q1=round(float(s.quantile(0.25)), 1),
        q3=round(float(s.quantile(0.75)), 1),
        lo=round(float(s.min()), 1),
        hi=round(float(s.max()), 1),
        n=n,
    )


def build_village_summary(df_primary: pd.DataFrame) -> pd.DataFrame:
    """
    Per-village (+ Overall) summary statistics for Table 1.

    Timing QC:
      - Total ATA: origin_datetime → destination_datetime (direction check applied)
      - Activation subset: both time_to_activate_min and activate_to_arrive_min valid
        - Excludes: direction errors, values below per-village 2× reference flight floor
    """
    j = df_primary.drop_duplicates("journey_id").copy()
    vcol = "village_name"   # computed by medevac_data_prep, always correct

    # Load census
    census = pd.read_csv(CENSUS_CSV) if CENSUS_CSV.exists() else pd.DataFrame()
    name_col = next((c for c in ("NAME", "name", "village_name") if c in census.columns), None)
    pop_map: dict[str, int] = {}
    if name_col and "pediatric_pop" in census.columns:
        pop_map = dict(zip(census[name_col].astype(str), census["pediatric_pop"].astype(int)))

    dist_map = _village_distances()

    # ── Timing QC setup ────────────────────────────────────────────────────────
    ft = pd.to_numeric(j.get("flight_time_min", pd.Series(dtype=float, index=j.index)), errors="coerce")
    j["_ft"] = ft
    floors: dict[str, float] = {}
    if ft.notna().any() and vcol in j.columns:
        floors = (
            j[j[vcol].notna()].groupby(vcol)["_ft"]
            .apply(lambda x: x.dropna().median() * 2.0)
            .dropna().to_dict()
        )

    ata  = pd.to_numeric(j.get("activate_to_arrive_min", pd.Series(dtype=float, index=j.index)), errors="coerce")
    tta  = pd.to_numeric(j.get("time_to_activate_min",   pd.Series(dtype=float, index=j.index)), errors="coerce")
    orig = pd.to_datetime(j.get("origin_datetime"), errors="coerce")
    dest = pd.to_datetime(j.get("destination_datetime"), errors="coerce")
    total_min = (dest - orig).dt.total_seconds() / 60

    bad_dir = dest.notna() & orig.notna() & (dest < orig)
    below_floor = pd.Series(False, index=j.index)
    if floors and vcol in j.columns:
        for v, floor in floors.items():
            vmask = (j[vcol] == v) & ata.notna() & ~bad_dir
            below_floor |= vmask & (ata < floor)

    valid_ata = ata.notna() & ~bad_dir & ~below_floor
    valid_tta = tta.notna() & (tta >= 0) & (tta <= total_min.fillna(float("inf")))
    valid_act = valid_tta & valid_ata
    total_valid = total_min[(total_min > 0) & ~bad_dir]

    # ── Study period ───────────────────────────────────────────────────────────
    yr = pd.to_numeric(j.get("journey_start_year"), errors="coerce")
    yr_range = range(int(yr.min()), int(yr.max()) + 1) if yr.notna().any() else range(1, 2)

    def _stats_for(mask: pd.Series) -> dict:
        sub = j[mask]
        n_j = len(sub)
        n_p = sub["MRN"].nunique()
        # Mean (SD) per year
        yr_sub = pd.to_numeric(sub.get("journey_start_year"), errors="coerce")
        if yr_sub.notna().any():
            yr_counts = yr_sub.value_counts()
            annual = pd.Series({y: yr_counts.get(y, 0) for y in yr_range})
            mean_yr, sd_yr = float(annual.mean()), float(annual.std(ddof=1)) if len(annual) > 1 else 0.0
        else:
            mean_yr, sd_yr = n_j / max(len(yr_range), 1), 0.0

        total_stats = _med_iqr_range(total_min[mask & (total_min > 0) & ~bad_dir])
        act_total   = int(valid_act[mask].sum())
        pct_act     = round(100 * act_total / n_j, 1) if n_j else None
        dec_stats   = _med_iqr_range(tta[mask & valid_act])
        res_stats   = _med_iqr_range(ata[mask & valid_act])

        return dict(
            n_journeys=n_j, n_patients=n_p,
            mean_per_year=round(mean_yr, 1), sd_per_year=round(sd_yr, 1),
            total_ata_median=total_stats["median"], total_ata_q1=total_stats["q1"],
            total_ata_q3=total_stats["q3"],         total_ata_lo=total_stats["lo"],
            total_ata_hi=total_stats["hi"],          total_ata_n=total_stats["n"],
            pct_complete_timing=pct_act,             n_complete_timing=act_total,
            decision_median=dec_stats["median"],     decision_q1=dec_stats["q1"],
            decision_q3=dec_stats["q3"],             decision_lo=dec_stats["lo"],
            decision_hi=dec_stats["hi"],             decision_n=dec_stats["n"],
            response_median=res_stats["median"],     response_q1=res_stats["q1"],
            response_q3=res_stats["q3"],             response_lo=res_stats["lo"],
            response_hi=res_stats["hi"],             response_n=res_stats["n"],
        )

    villages = (
        j[j[vcol].notna() & (j[vcol] != "")]
        [vcol].value_counts().index.tolist()
    )

    rows = []
    for v in villages:
        vmask = j[vcol] == v
        s = _stats_for(vmask)
        s["village_name"] = v
        s["distance_miles"] = dist_map.get(v)
        s["pediatric_pop"] = pop_map.get(v)
        s["util_rate"] = round(s["n_journeys"] / pop_map[v] * 1000, 1) if pop_map.get(v) else None
        rows.append(s)

    # Overall row (all primary cohort journeys)
    village_mask = j[vcol].notna() & (j[vcol] != "") if vcol in j.columns else pd.Series(True, index=j.index)
    overall = _stats_for(village_mask)
    overall_pop = sum(pop_map.get(v, 0) for v in villages) or None
    overall.update(
        village_name="Overall",
        distance_miles=None,
        pediatric_pop=overall_pop,
        util_rate=round(overall["n_journeys"] / overall_pop * 1000, 1) if overall_pop else None,
    )
    rows.append(overall)

    col_order = [
        "village_name", "n_journeys", "n_patients", "mean_per_year", "sd_per_year",
        "distance_miles", "pediatric_pop", "util_rate",
        "total_ata_median", "total_ata_q1", "total_ata_q3", "total_ata_lo", "total_ata_hi", "total_ata_n",
        "pct_complete_timing", "n_complete_timing",
        "decision_median", "decision_q1", "decision_q3", "decision_lo", "decision_hi", "decision_n",
        "response_median", "response_q1", "response_q3", "response_lo", "response_hi", "response_n",
    ]
    return pd.DataFrame(rows)[[c for c in col_order if c in pd.DataFrame(rows).columns]]


# ── Cohort flow (PRISMA nodes) ─────────────────────────────────────────────────

def build_cohort_flow(df: pd.DataFrame, df_primary: pd.DataFrame) -> pd.DataFrame:
    """
    Cohort flow for the PRISMA diagram.

    Stages (rows):
      "All records in database"      – every journey record in the extract
      "MHC-presenting (excluded)"    – records whose first leg starts at MHC,
                                       not village-originating air ambulance
      "Village-originating (cohort)" – primary cohort: village → MHC journeys
    """

    def _complete_dest(subset: pd.DataFrame) -> int:
        """Journeys where every non-empty leg slot has a destination."""
        def _row_ok(r: pd.Series) -> bool:
            for i in (1, 2, 3):
                if _safe_str(r.get(f"medevac{i}_from")) and not _safe_str(r.get(f"medevac{i}_to")):
                    return False
            return True
        return int(subset.apply(_row_ok, axis=1).sum())

    def _complete_timing(subset: pd.DataFrame) -> int:
        """Journeys with genuinely measured timing (quality == 'real')."""
        if "time_to_activate_quality" not in subset.columns:
            return 0
        return int((subset["time_to_activate_quality"] == "real").sum())

    def _stage(subset: pd.DataFrame, label: str) -> dict:
        return dict(
            stage=label,
            n_journeys=int(subset["journey_id"].nunique()),
            n_patients=int(subset["MRN"].nunique()),
            n_complete_dest=_complete_dest(subset),
            n_complete_timing=_complete_timing(subset),
        )

    n_all  = int(df["journey_id"].nunique())
    n_prim = int(df_primary["journey_id"].nunique())

    s_all  = _stage(df, "All records in database")
    s_prim = _stage(df_primary, "Village-originating (cohort)")
    s_excl: dict = dict(
        stage="MHC-presenting (excluded)",
        n_journeys=n_all - n_prim,
        n_patients=None,
        n_complete_dest=None,
        n_complete_timing=None,
    )
    return pd.DataFrame([s_all, s_excl, s_prim])


# ── Leg breakdown ───────────────────────────────────────────────────────────────

def build_leg_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    """Count flight legs by origin-type × destination-type (village-originating journeys only)."""
    rows = []
    for _, r in df.iterrows():
        for i in (1, 2, 3):
            frm = _safe_str(r.get(f"medevac{i}_from"))
            to  = _safe_str(r.get(f"medevac{i}_to"))
            if not frm or not to:
                continue
            from_cat = "Village" if is_village_origin(frm) else _dest_label(frm)
            to_cat   = _dest_label(to)
            rows.append({"from_type": from_cat, "to_type": to_cat})

    if not rows:
        return pd.DataFrame(columns=["from_type", "to_type", "n_legs"])

    return (
        pd.DataFrame(rows)
        .groupby(["from_type", "to_type"])
        .size()
        .reset_index(name="n_legs")
    )


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

    print("Computing derived variables...")
    df = compute_derived(df_raw)

    print("Filtering primary cohort (village → MHC)...")
    mask = df.apply(_qualifies_for_primary_cohort, axis=1)
    df_primary = df[mask].copy()

    print("Exporting analysis-ready CSVs:")
    _write(df, "journeys_all")
    _write(df_primary, "journeys_primary")
    _write(build_patients_primary(df_primary), "patients_primary")
    _write(build_legs_primary(df_primary), "legs_primary")
    _write(build_village_census(), "village_census")
    _write(build_village_summary(df_primary), "village_summary")
    _write(build_cohort_flow(df, df_primary), "cohort_flow")
    _write(build_leg_breakdown(df_primary), "leg_breakdown")

    print(f"\nDone. {len(df_primary):,} primary journeys, {df_primary['MRN'].nunique():,} unique patients.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-synthetic", "--synthetic", action="store_true")
    args = parser.parse_args()
    main(synthetic=args.synthetic)
