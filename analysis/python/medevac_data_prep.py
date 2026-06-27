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
    _write(build_village_summary(df_primary), "village_summary")
    _write(build_cohort_flow(df, df_primary), "cohort_flow")
    _write(build_leg_breakdown(df_primary), "leg_breakdown")

    print(f"\nDone. {len(df_primary):,} primary journeys, {df_primary['MRN'].nunique():,} unique patients.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-synthetic", "--synthetic", action="store_true")
    args = parser.parse_args()
    main(synthetic=args.synthetic)
