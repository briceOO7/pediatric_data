"""
Medevac descriptive summaries: tables (CSV), figures (PNG), and builders for Quarto.
Run from project root: python analysis/medevac_summaries.py
"""

import os
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Paths
ROOT = Path(__file__).resolve().parents[1]

# Pediatric CSV source directory.
# On the PHI machine the medevac_pipeline_project produces all pediatric CSVs in
# data/final/pediatric/.  Point DATA at that directory so no manual copy step is needed.
#
# Resolution order:
#   1. MEDEVAC_PIPELINE_DIR env var  (set this if the two projects are not siblings)
#   2. Sibling directory  ../medevac_pipeline_project/data/final/pediatric/
#   3. Local data/  (fallback for dev machines running synthetic data)
_pipeline_root = Path(
    os.environ.get("MEDEVAC_PIPELINE_DIR",
                   ROOT.parent / "medevac_pipeline_project")
).resolve()
_pipeline_pediatric = _pipeline_root / "data" / "final" / "pediatric"

if _pipeline_pediatric.exists():
    DATA = _pipeline_pediatric
    print(f"[medevac_summaries] Reading data from pipeline: {DATA}", flush=True)
else:
    DATA = ROOT / "data"

VILLAGE_CODEBOOK = ROOT / "docs" / "village_name_codebook.csv"
FACILITY_CODEBOOK = ROOT / "docs" / "facility_name_codebook.csv"
# infer = real PHI CSV community names (default)
# codebook = de-ID + village_name_codebook (set MEDEVAC_VILLAGE_ORIGINS=codebook
# or MEDEVAC_SYNTHETIC=1 on local dev machine).
MEDEVAC_VILLAGE_ORIGINS = os.environ.get("MEDEVAC_VILLAGE_ORIGINS", "").strip().lower()
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_FIGS = ROOT / "outputs" / "figures"

sns.set_theme(style="whitegrid", context="talk", font_scale=0.85)
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["figure.figsize"] = (10, 6)

_VILLAGE_NAMES_CACHE: frozenset[str] | None = None
_FACILITY_DISPLAY_CACHE: dict[str, str] | None = None
_VILLAGE_ORIGIN_MODE_CACHE: str | None = None
_VILLAGE_CODE_TO_NAME_CACHE: dict[str, str] | None = None


def facility_display_map() -> dict[str, str]:
    """Study facility code → display label for tables and figures."""
    global _FACILITY_DISPLAY_CACHE
    if _FACILITY_DISPLAY_CACHE is None:
        cb = pd.read_csv(FACILITY_CODEBOOK)
        _FACILITY_DISPLAY_CACHE = dict(
            zip(cb["code"].astype(str), cb["display_name"].astype(str), strict=True)
        )
    return _FACILITY_DISPLAY_CACHE


def expand_facility_label(text: str) -> str:
    """Replace known facility codes with display names (longest codes first)."""
    out = str(text)
    for code in sorted(facility_display_map().keys(), key=len, reverse=True):
        out = out.replace(code, facility_display_map()[code])
    return out


def maniilaq_village_names() -> frozenset[str]:
    """Communities from docs/village_name_codebook.csv (post–de-ID rename)."""
    global _VILLAGE_NAMES_CACHE
    if _VILLAGE_NAMES_CACHE is None:
        cb = pd.read_csv(VILLAGE_CODEBOOK)
        _VILLAGE_NAMES_CACHE = frozenset(cb["community_name"].astype(str))
    return _VILLAGE_NAMES_CACHE


def village_code_to_name_map() -> dict[str, str]:
    """Anonymous village code -> community name from village codebook."""
    global _VILLAGE_CODE_TO_NAME_CACHE
    if _VILLAGE_CODE_TO_NAME_CACHE is None:
        cb = pd.read_csv(VILLAGE_CODEBOOK)
        _VILLAGE_CODE_TO_NAME_CACHE = dict(
            zip(cb["anonymous_code"].astype(str), cb["community_name"].astype(str), strict=True)
        )
    return _VILLAGE_CODE_TO_NAME_CACHE


def _decode_village_name(x: object) -> object:
    """Map Village_* placeholders to community names when codebook mode is active."""
    s = str(x).strip()
    if not s or village_origin_mode() != "codebook":
        return x
    if not s.startswith("Village_"):
        return x
    return village_code_to_name_map().get(s, x)


def village_origin_mode() -> str:
    """
    Determine village-origin interpretation mode.

    Priority:
    1) MEDEVAC_VILLAGE_ORIGINS env var, if valid ("infer" or "codebook")
    2) MEDEVAC_SYNTHETIC truthy => codebook
    3) Fallback infer (real-data default, e.g. PHI machine)
    """
    global _VILLAGE_ORIGIN_MODE_CACHE
    if MEDEVAC_VILLAGE_ORIGINS in {"infer", "codebook"}:
        return MEDEVAC_VILLAGE_ORIGINS
    if _VILLAGE_ORIGIN_MODE_CACHE is not None:
        return _VILLAGE_ORIGIN_MODE_CACHE
    mode = "infer"
    syn = os.environ.get("MEDEVAC_SYNTHETIC", "").strip().lower()
    if syn in {"1", "true", "yes", "y", "on"}:
        mode = "codebook"
    _VILLAGE_ORIGIN_MODE_CACHE = mode
    return mode


def _is_study_facility_origin(place: object) -> bool:
    """Hub / CAH / outside hospital codes — not a village clinic origin."""
    if pd.isna(place):
        return True
    t = str(place).strip()
    if not t:
        return True
    u = t.upper().replace("_", "")
    if u.startswith("CAH") or u.startswith("HUB") or "OUTSIDEHOSPITAL" in u:
        return True
    # Catch full MHC names that appear in PHI data
    tl = t.lower()
    if "maniilaq" in tl and "health" in tl:
        return True
    if "mhc" == tl:
        return True
    return False


def is_village_medevac_origin(place: object) -> bool:
    """
    Whether *medevac_from* (or first facility) should be treated as a village clinic.

    - codebook: Village_* placeholders or name in village_name_codebook.csv
    - infer: anything that is not a study facility code (use on PHI with real community names)
    """
    s = str(place).strip()
    if not s:
        return False
    if village_origin_mode() == "infer":
        return not _is_study_facility_origin(s)
    if s.startswith("Village_"):
        return True
    return s in maniilaq_village_names()


def _is_village_place(name: object) -> bool:
    return is_village_medevac_origin(name)


def _classify_journey_route(row: pd.Series) -> str:
    """
    Classify a journey row into one of three route types.

    Logic uses the first non-empty leg destination to determine where the patient
    ultimately lands on leg 1, guarding against sparse/null medevac1_to values.

    Returns
    -------
    "Primary (village → MHC)"   — leg 1 ends at MHC, no further transfer leg
    "Secondary transfer"        — leg 1 ends at MHC AND a leg 2 destination exists
    "Direct tertiary"           — first populated leg destination is NOT MHC
                                  (village flew directly to ANMC / UW / Providence)
    """
    # Walk legs in order; use the first leg that has a populated destination.
    first_to = ""
    second_to = ""
    found_first = False
    for i in (1, 2, 3):
        to_val = str(row.get(f"medevac{i}_to", "") or "").strip()
        from_val = str(row.get(f"medevac{i}_from", "") or "").strip()
        if not to_val:
            continue
        if not found_first:
            # Only count this as the "first" leg if it originates from a village
            # OR it is literally leg 1 (covers edge case where medevac1_from is blank).
            if i == 1 or is_village_medevac_origin(from_val):
                first_to = to_val
                found_first = True
        else:
            second_to = to_val
            break

    if not first_to:
        return "Unknown"

    if _is_mhc_cah_destination(first_to):
        if second_to:
            return "Secondary transfer"
        return "Primary (village → MHC)"
    return "Direct tertiary"


def _is_mhc_cah_destination(to_raw: object) -> bool:
    """Medevac destination is Maniilaq Health Center (critical access hospital)."""
    b = str(to_raw).strip()
    bl = b.lower()
    return (
        b == "CAH_01"
        or b.startswith("CAH")
        or b.upper() == "MHC"
        or " mhc" in f" {bl}"
        or "maniilaq health center" in bl
        or (("maniilaq" in bl) and ("health" in bl) and ("center" in bl))
    )


def _origin_for_leg_with_fallback(r: pd.Series, leg_idx: int) -> str:
    """
    Origin used for village logic for a medevac leg.

    PHI extracts can encode first-leg medevac origin as a non-village facility even when
    journey starts in a village clinic. For leg 1 only, fall back to facility_1_name.
    """
    fc = f"medevac{leg_idx}_from"
    a = str(r.get(fc, "")).strip()
    if leg_idx == 1 and (not a or _is_study_facility_origin(a)):
        f1 = str(r.get("facility_1_name", "")).strip()
        if f1:
            return f1
    return a


def count_village_to_mhc_legs(df: pd.DataFrame) -> int:
    """Count legs where origin is a village clinic and destination is MHC (CAH)."""
    n = 0
    for _, r in df.iterrows():
        for i in (1, 2, 3):
            fc, tc = f"medevac{i}_from", f"medevac{i}_to"
            if fc not in r.index or tc not in r.index:
                continue
            if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                continue
            a = _origin_for_leg_with_fallback(r, i)
            b = str(r[tc]).strip()
            if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                n += 1
    return n


def filter_journeys_village_to_mhc(df: pd.DataFrame) -> pd.DataFrame:
    """Journeys with at least one village clinic → MHC medevac leg (Table 1+ cohort)."""

    def row_qualifies(r: pd.Series) -> bool:
        for i in (1, 2, 3):
            fc, tc = f"medevac{i}_from", f"medevac{i}_to"
            if fc not in r.index or tc not in r.index:
                continue
            if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                continue
            a = _origin_for_leg_with_fallback(r, i)
            b = str(r[tc]).strip()
            if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                return True
        return False

    return df[df.apply(row_qualifies, axis=1)].copy()


def load_data():
    journeys = pd.read_csv(DATA / "pediatric_medevac_journeys.csv")
    timing = pd.read_csv(DATA / "pediatric_medevac_timing.csv")
    outcomes = pd.read_csv(DATA / "pediatric_outcomes.csv")
    patients = pd.read_csv(DATA / "pediatric_patients.csv")

    # Avoid merge collisions with journey columns (can hide medevac*_from/to in PHI extracts).
    timing_extra = [
        c
        for c in timing.columns
        if c not in ("journey_id", "MRN", "origin_type") and c not in journeys.columns
    ]
    df = journeys.merge(timing[["journey_id"] + timing_extra], on="journey_id", how="left")

    # Recovery path: if prior merges created suffixes, coalesce back to canonical names.
    for base in [f"medevac{i}_{s}" for i in (1, 2, 3) for s in ("from", "to", "id")] + ["facility_1_name"]:
        if base in df.columns:
            continue
        for cand in (f"{base}_x", f"{base}_y"):
            if cand in df.columns:
                df[base] = df[cand]
                break

    outcome_extra = [
        "death_at_facility",
        "days_to_discharge",
        "days_to_death",
        "24hr_mortality",
        "7d_mortality",
        "30d_mortality",
        "ed_discharge",
        "short_<36h_admission",
        "icu_admission",
        "had_surgery",
    ]
    out_keep = ["journey_id"] + [c for c in outcome_extra if c in outcomes.columns]
    df = df.merge(outcomes[out_keep], on="journey_id", how="left")
    df = df.merge(patients, on="MRN", how="left")
    # For de-identified synthetic extracts, decode Village_* placeholders so
    # tables and map use community names consistently.
    if village_origin_mode() == "codebook":
        for c in ("facility_1_name", "medevac1_from", "medevac2_from", "medevac3_from"):
            if c in df.columns:
                df[c] = df[c].map(_decode_village_name)
    return df


def load_journeys_primary_prepared() -> pd.DataFrame:
    """Village-originating analysis cohort written by medevac_data_prep (n≈309)."""
    path = ROOT / "outputs" / "data" / "journeys_primary.csv"
    if not path.exists():
        return pd.DataFrame()
    j = pd.read_csv(path).drop_duplicates(subset=["journey_id"])
    if village_origin_mode() == "codebook":
        for c in (
            "village_name",
            "facility_1_name",
            "medevac1_from",
            "medevac2_from",
            "medevac3_from",
        ):
            if c in j.columns:
                j[c] = j[c].map(_decode_village_name)
    return j


def write_table(df: pd.DataFrame, name: str):
    OUT_TABLES.mkdir(parents=True, exist_ok=True)
    path = OUT_TABLES / f"{name}.csv"
    df.to_csv(path, index=False)
    print(f"Wrote {path}")


def fmt_pct_n(count: int, denominator: int, digits: int = 1) -> str:
    """Format as 'pct (n)' e.g. 45.2 (151)."""
    if denominator <= 0:
        return "—"
    pct = 100.0 * count / denominator
    return f"{pct:.{digits}f} ({count})"


def fmt_n_pct(count: int, denominator: int, digits: int = 1) -> str:
    """Format as 'n (pct%)' e.g. 151 (45.2%)."""
    if denominator <= 0:
        return "—"
    pct = 100.0 * count / denominator
    return f"{count} ({pct:.{digits}f}%)"


def fmt_pct_n(count: int, denominator: int, digits: int = 1) -> str:
    """Format as 'pct% (n)' e.g. 45.2% (151). Standard for Table 2."""
    if denominator <= 0:
        return "—"
    pct = 100.0 * count / denominator
    return f"{pct:.{digits}f}% ({count})"


def _table0_destination_label(to_raw: str) -> str:
    """Map raw medevac *to* code to display destination (MHC / ANMC / UW / Providence)."""
    b = str(to_raw).strip()
    if b.startswith("CAH") or b == "CAH_01":
        return "Maniilaq Health Center"
    if b.startswith("Hub") or b == "Hub_01":
        return "ANMC"
    if b == "OutsideHospital02":
        return "UW"
    if b == "OutsideHospital03":
        return "Providence"
    return expand_facility_label(b)


def build_table0_medevac_routes(journeys: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Medevac legs: columns Origin, Destination, Medevacs n (%).
    Origins grouped (villages aggregated; MHC hub); destinations MHC, ANMC, UW, Providence.
    """
    if journeys is None:
        journeys = pd.read_csv(DATA / "pediatric_medevac_journeys.csv")
    from collections import Counter

    c: Counter[tuple[str, str]] = Counter()
    for i in range(1, 4):
        fc, tc = f"medevac{i}_from", f"medevac{i}_to"
        for _, r in journeys.iterrows():
            if (
                pd.notna(r[fc])
                and str(r[fc]).strip()
                and pd.notna(r[tc])
                and str(r[tc]).strip()
            ):
                a, b = str(r[fc]).strip(), str(r[tc]).strip()
                if is_village_medevac_origin(a):
                    origin = "Villages (aggregated)"
                elif a.startswith("CAH") or a == "CAH_01":
                    origin = "Maniilaq Health Center"
                else:
                    origin = f"Other origin ({expand_facility_label(a)})"
                dest = _table0_destination_label(b)
                c[(origin, dest)] += 1

    total = sum(c.values())

    def fmt_medevacs_n_pct(count: int, denom: int, digits: int = 1) -> str:
        if denom <= 0:
            return "—"
        pct = 100.0 * count / denom
        return f"{count} ({pct:.{digits}f}%)"

    # Highest medevac count first; ties broken by Origin, Destination
    rows = []
    for (og, dg), n in sorted(c.items(), key=lambda it: (-it[1], it[0][0], it[0][1])):
        rows.append(
            {
                "Origin": og,
                "Destination": dg,
                "Medevacs n (%)": fmt_medevacs_n_pct(n, total),
            }
        )
    rows.append(
        {
            "Origin": "All legs",
            "Destination": "—",
            "Medevacs n (%)": f"{total} (100.0%)",
        }
    )
    return pd.DataFrame(rows)


def build_table3a_primary_routes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 3a: Primary transfers — village-origin legs only.

    Rows = each village of origin, sorted by leg count descending.
    Columns: Village of Origin | Destination | N Legs | % of Primary Legs.

    A 'primary' leg is any medevac leg where the origin is a village clinic
    (regardless of destination — includes village→MHC and village→direct tertiary).
    """
    rows = []
    for _, r in df.iterrows():
        for i in (1, 2, 3):
            raw_frm = r.get(f"medevac{i}_from")
            raw_to  = r.get(f"medevac{i}_to")
            if pd.isna(raw_frm) or pd.isna(raw_to):
                continue
            frm = str(raw_frm).strip()
            to  = str(raw_to).strip()
            if not frm or not to:
                continue
            if is_village_medevac_origin(frm):
                rows.append({"village": frm, "destination": _table0_destination_label(to)})

    if not rows:
        return pd.DataFrame(columns=["Village of Origin", "Destination", "N Legs", "% of Primary Legs"])

    leg_df = pd.DataFrame(rows)
    total = len(leg_df)

    summary = (
        leg_df.groupby(["village", "destination"])
        .size()
        .reset_index(name="N Legs")
        .sort_values(["N Legs"], ascending=False)
    )
    summary["% of Primary Legs"] = (summary["N Legs"] / total * 100).map(lambda x: f"{x:.1f}%")
    summary = summary.rename(columns={"village": "Village of Origin", "destination": "Destination"})

    total_row = pd.DataFrame([{
        "Village of Origin": "All primary legs",
        "Destination": "—",
        "N Legs": total,
        "% of Primary Legs": "100.0%",
    }])
    out = pd.concat([summary, total_row], ignore_index=True)
    out.to_csv(ROOT / "outputs" / "tables" / "table3a_primary_routes.csv", index=False)
    return out


def build_table3b_secondary_routes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 3b: Secondary transfers — MHC-origin legs only.

    Rows = each tertiary destination, sorted by leg count descending.
    Columns: Destination | N Legs | % of Secondary Legs.

    A 'secondary' leg is any medevac leg where the origin is Maniilaq Health Center
    (CAH), i.e. the patient is being transferred onward from MHC.
    """
    rows = []
    for _, r in df.iterrows():
        for i in (1, 2, 3):
            raw_frm = r.get(f"medevac{i}_from")
            raw_to  = r.get(f"medevac{i}_to")
            if pd.isna(raw_frm) or pd.isna(raw_to):
                continue
            frm = str(raw_frm).strip()
            to  = str(raw_to).strip()
            if not frm or not to:
                continue
            if _is_mhc_cah_destination(frm):
                rows.append({"destination": _table0_destination_label(to)})

    if not rows:
        return pd.DataFrame(columns=["Destination", "N Legs", "% of Secondary Legs"])

    leg_df = pd.DataFrame(rows)
    total = len(leg_df)

    summary = (
        leg_df.groupby("destination")
        .size()
        .reset_index(name="N Legs")
        .sort_values("N Legs", ascending=False)
    )
    summary["% of Secondary Legs"] = (summary["N Legs"] / total * 100).map(lambda x: f"{x:.1f}%")
    summary = summary.rename(columns={"destination": "Destination"})

    total_row = pd.DataFrame([{
        "Destination": "All secondary legs",
        "N Legs": total,
        "% of Secondary Legs": "100.0%",
    }])
    out = pd.concat([summary, total_row], ignore_index=True)
    out.to_csv(ROOT / "outputs" / "tables" / "table3b_secondary_routes.csv", index=False)
    return out


def build_table1_patient_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per patient = earliest journey (by medevac1_date) in *df*.
    Expect *df* restricted to journeys with ≥1 village→MHC leg.
    Female, AI/AN, insurance, age, origin village (facility_1_name).
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["medevac1_date"] = pd.to_datetime(j["medevac1_date"], errors="coerce")
    first = j.sort_values("medevac1_date").groupby("MRN", as_index=False).first()
    N = len(first)
    if N == 0:
        return pd.DataFrame(
            [
                {"characteristic": "Cohort", "value": "No journeys with village→MHC legs."},
            ]
        )
    patients = pd.read_csv(DATA / "pediatric_patients.csv")
    extra = [
        c
        for c in ("AI_AN", "RaceDSC", "PrimaryPayorNM")
        if c in patients.columns and c not in first.columns
    ]
    p = first.merge(patients[["MRN"] + extra], on="MRN", how="left") if extra else first.copy()
    if "GenderDSC" not in p.columns and "GenderDSC" in patients.columns:
        p = p.merge(patients[["MRN", "GenderDSC"]], on="MRN", how="left")

    rows: list[dict[str, str]] = []
    n_patients_cohort = int(j["MRN"].nunique())
    rows.append({"characteristic": "Unique patients", "value": str(n_patients_cohort)})
    # Patient-level medevac distribution in 2020-2024.
    j["_year"] = pd.to_numeric(j["journey_start_year"], errors="coerce")
    j_yr = j[j["_year"].between(2020, 2024, inclusive="both")].copy()
    rows.append({"characteristic": "Medevacs per Patient, 2020-2024, n(%)", "value": ""})
    source_for_counts = j_yr
    if len(j_yr) == 0:
        source_for_counts = j
        rows.append({"characteristic": "  (No journeys in 2020-2024; showing all years)", "value": ""})
    if len(source_for_counts) == 0:
        rows.append({"characteristic": "  No cohort journeys available", "value": "—"})
    else:
        per_mrn: dict[object, int] = {}
        for mrn, sub in source_for_counts.groupby("MRN", dropna=False):
            legs = 0
            for _, r in sub.iterrows():
                for i in (1, 2, 3):
                    fc, tc = f"medevac{i}_from", f"medevac{i}_to"
                    if fc not in r.index or tc not in r.index:
                        continue
                    if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                        continue
                    a, b = str(r[fc]).strip(), str(r[tc]).strip()
                    if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                        legs += 1
            per_mrn[mrn] = legs
        vals = pd.Series(list(per_mrn.values()), dtype="int64")
        vals = vals[vals > 0]
        n_den = int(len(vals))
        if n_den == 0:
            rows.append({"characteristic": "  No village→MHC medevacs in 2020-2024", "value": "—"})
        else:
            vc = vals.value_counts().sort_index()
            for n_med, n_pat in vc.items():
                rows.append({"characteristic": f"  {int(n_med)}", "value": fmt_n_pct(int(n_pat), n_den)})

    n_female = int((p["GenderDSC"] == "Female").sum())
    rows.append({"characteristic": "Female sex", "value": fmt_n_pct(n_female, N)})

    if "AI_AN" in p.columns:
        raw = p["AI_AN"]
        known = raw.notna() & (raw.astype(str).str.strip() != "")
        n_known = int(known.sum())
        if n_known == 0:
            rows.append(
                {
                    "characteristic": "American Indian / Alaska Native",
                    "value": "NR (0 coded; set AI_AN=1 for AI/AN in pediatric_patients.csv)",
                }
            )
        else:
            yes = known & raw.apply(
                lambda x: str(x).strip().lower() in ("1", "y", "yes", "true") or x is True
            )
            n_yes = int(yes.sum())
            if n_known == N:
                rows.append(
                    {
                        "characteristic": "American Indian / Alaska Native",
                        "value": fmt_n_pct(n_yes, N),
                    }
                )
            else:
                rows.append(
                    {
                        "characteristic": "American Indian / Alaska Native",
                        "value": (
                            f"{fmt_n_pct(n_yes, n_known)} of patients with AI_AN recorded "
                            f"(n={n_known})"
                        ),
                    },
                )
    elif "RaceDSC" in p.columns:
        ai = p["RaceDSC"].astype(str).str.contains(
            r"indian|alaska\s+native|american\s+indian",
            case=False,
            na=False,
            regex=True,
        )
        rows.append(
            {
                "characteristic": "American Indian / Alaska Native (race text)*",
                "value": fmt_n_pct(int(ai.sum()), N),
            }
        )
    else:
        rows.append(
            {
                "characteristic": "American Indian / Alaska Native",
                "value": "NR — add AI_AN (1=yes) or RaceDSC to pediatric_patients.csv",
            }
        )

    if "PrimaryPayorNM" in p.columns:
        rows.append({"characteristic": "Insurance (primary payor)**", "value": ""})
        pay = p["PrimaryPayorNM"].astype(str).str.strip()
        pay = pay.replace({"": "Missing / unknown", "nan": "Missing / unknown"})
        for payor, cnt in pay.value_counts().sort_values(ascending=False).items():
            rows.append({"characteristic": str(payor), "value": fmt_n_pct(int(cnt), N)})
    else:
        rows.append(
            {
                "characteristic": "Insurance (PrimaryPayorNM)",
                "value": "NR — add PrimaryPayorNM to pediatric_patients.csv (PHI sync)",
            }
        )

    age = pd.to_numeric(p["age_at_medevac"], errors="coerce")
    avalid = age.dropna()
    if len(avalid):
        mu, sd = float(avalid.mean()), float(avalid.std(ddof=1))
        rows.append(
            {
                "characteristic": "Age at first medevac, y, mean (SD)",
                "value": f"{mu:.1f} ({sd:.1f})",
            }
        )
    else:
        rows.append({"characteristic": "Age at first medevac, y, mean (SD)", "value": "—"})

    def age_bucket(a: float) -> str | None:
        if pd.isna(a):
            return None
        if a < 1:
            return "b0"
        if a < 5:
            return "b1"
        if a < 13:
            return "b2"
        if a <= 18:
            return "b3"
        return "other"

    ag = age.map(age_bucket)
    age_rows = [
        ("<1 year", "b0"),
        ("1 to <5 years", "b1"),
        ("5–12 years", "b2"),
        ("13–18 years", "b3"),
    ]
    rows.append({"characteristic": "Age Groups, n(%)", "value": ""})
    for lab, key in age_rows:
        n = int((ag == key).sum())
        rows.append({"characteristic": f"  {lab}", "value": fmt_n_pct(n, N)})
    n_miss = int(ag.isna().sum() + (ag == "other").sum())
    if n_miss:
        rows.append({"characteristic": "  Age missing or >18 y", "value": fmt_n_pct(n_miss, N)})

    # Seasonal and annual pattern using pre-populated journey_start_month/year.
    mon = pd.to_numeric(p["journey_start_month"], errors="coerce")
    yr  = pd.to_numeric(p["journey_start_year"],  errors="coerce")

    month_labels = [
        (1,"Jan"),(2,"Feb"),(3,"Mar"),(4,"Apr"),(5,"May"),(6,"Jun"),
        (7,"Jul"),(8,"Aug"),(9,"Sep"),(10,"Oct"),(11,"Nov"),(12,"Dec"),
    ]
    rows.append({"characteristic": "Month of Medevac, n(%)", "value": ""})
    for mnum, mlab in month_labels:
        n = int((mon == mnum).sum())
        rows.append({"characteristic": f"  {mlab}", "value": fmt_n_pct(n, N)})
    n_miss_month = int(mon.isna().sum())
    if n_miss_month:
        rows.append({"characteristic": "  Month missing", "value": fmt_n_pct(n_miss_month, N)})

    rows.append({"characteristic": "Medevac Per Year, n(%)", "value": ""})
    for y in range(2020, 2025):
        n = int((yr == y).sum())
        rows.append({"characteristic": f"  {y}", "value": fmt_n_pct(n, N)})
    n_other_year = int(yr.notna().sum() - sum(int((yr == y).sum()) for y in range(2020, 2025)))
    if n_other_year > 0:
        rows.append({"characteristic": "  Outside 2020–2024", "value": fmt_n_pct(n_other_year, N)})
    n_miss_year = int(yr.isna().sum())
    if n_miss_year:
        rows.append({"characteristic": "  Year missing", "value": fmt_n_pct(n_miss_year, N)})

    fac = p["facility_1_name"].fillna("").astype(str)
    villages = {v for v in fac.unique() if str(v).strip() and is_village_medevac_origin(v)}
    village_counts = [(v, int((fac == v).sum())) for v in villages if int((fac == v).sum()) > 0]
    village_counts.sort(key=lambda x: (-x[1], x[0]))
    rows.append({"characteristic": "Origin Village, n(%)", "value": ""})
    for v, nv in village_counts:
        rows.append({"characteristic": f"  {v}", "value": fmt_n_pct(nv, N)})

    return pd.DataFrame(rows)


def vitals_csv_path() -> Path:
    """Prefer explicit env, then village-visit file, then journey-level wide vitals."""
    env = os.environ.get("MEDEVAC_VITALS_CSV", "").strip()
    if env:
        return Path(env)
    for name in (
        "pediatric_village_visit_vitals.csv",
        "pediatric_vitals_wide.csv",
    ):
        p = DATA / name
        if p.is_file():
            return p
    return DATA / "pediatric_village_visit_vitals.csv"
CHIEF_COMPLAINTS_WIDE = DATA / "pediatric_chiefcomplaints.csv"
MISSED_OPPORTUNITIES_CSV = DATA / "pediatric_missed_opportunities.csv"

# Aliases for village-visit vitals CSV (first matching column wins)
_VITAL_ALIASES: dict[str, tuple[str, ...]] = {
    "hr": (
        "hr",
        "HR",
        "HR_median",
        "heart_rate",
        "HeartRate",
        "vital_hr",
        "Pulse",
    ),
    "o2": (
        "spo2",
        "SpO2",
        "SpO2_median",
        "o2_sat",
        "O2Sat",
        "O2",
        "vital_o2",
        "oxygen_sat",
    ),
    "bp_sys": (
        "bp_systolic",
        "sbp",
        "SBP",
        "Systolic_median",
        "BPSystolic",
        "vital_bp_systolic",
        "sys_bp",
    ),
    "bp_dia": (
        "bp_diastolic",
        "dbp",
        "DBP",
        "Diastolic_median",
        "BPDiastolic",
        "vital_bp_diastolic",
        "dia_bp",
    ),
    "rr": ("rr", "RR", "RR_median", "respiratory_rate", "RespRate", "vital_rr", "resp_rate"),
    "temp": (
        "temp",
        "Temp",
        "temperature",
        "Temperature",
        "Temperature_median",
        "vital_temp",
    ),
}
_MRN_ALIASES = ("MRN", "mrn", "patient_mrn", "PatientMRN", "Patient_MRN")
_GCS_ALIASES = ("gcs", "GCS", "GCS_median", "gcs_median")


def _mrn_normalize(x: object) -> object:
    if pd.isna(x):
        return None
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return str(x).strip()


def _pick_vitals_col(df: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    cols_lower = {c.lower(): c for c in df.columns}
    for a in aliases:
        if a in df.columns:
            return a
        if a.lower() in cols_lower:
            return cols_lower[a.lower()]
    return None


def _vital_column_map(vitals: pd.DataFrame) -> dict[str, str] | None:
    m: dict[str, str] = {}
    for key, aliases in _VITAL_ALIASES.items():
        col = _pick_vitals_col(vitals, aliases)
        if col:
            m[key] = col
    need = frozenset({"hr", "o2", "bp_sys", "bp_dia", "rr", "temp"})
    if need > frozenset(m.keys()):
        return None
    return m


def _vital_row_complete(row: pd.Series, cm: dict[str, str]) -> bool:
    for key in ("hr", "o2", "bp_sys", "bp_dia", "rr", "temp"):
        v = row[cm[key]]
        if pd.isna(v):
            return False
        if isinstance(v, str) and not str(v).strip():
            return False
    return True


def _mrns_complete_village_vitals(vitals: pd.DataFrame, cm: dict[str, str]) -> set[object]:
    mrn_col = _pick_vitals_col(vitals, _MRN_ALIASES)
    if not mrn_col:
        return set()
    out: set[object] = set()
    for _, row in vitals.iterrows():
        if not _vital_row_complete(row, cm):
            continue
        k = _mrn_normalize(row[mrn_col])
        if k is not None:
            out.add(k)
    return out


def _value_present_series(s: pd.Series) -> pd.Series:
    """True for non-missing/non-blank values."""
    if s.dtype == object:
        return s.notna() & (s.astype(str).str.strip() != "")
    return s.notna()


def _num_or_none(x: object) -> float | None:
    if pd.isna(x):
        return None
    try:
        if isinstance(x, str) and not x.strip():
            return None
        return float(x)
    except (TypeError, ValueError):
        return None


def _pews_proxy_score_row(row: pd.Series, cm: dict[str, str], gcs_col: str | None) -> int | None:
    """
    Approximate PEWS-like score from available vitals.
    Uses RR, HR, SBP, Temp, and consciousness approximated from GCS.
    Returns None when required components are missing.
    """
    rr = _num_or_none(row.get(cm["rr"]))
    hr = _num_or_none(row.get(cm["hr"]))
    sbp = _num_or_none(row.get(cm["bp_sys"]))
    temp = _num_or_none(row.get(cm["temp"]))
    if rr is None or hr is None or sbp is None or temp is None:
        return None
    gcs = _num_or_none(row.get(gcs_col)) if gcs_col else None
    if gcs is None:
        return None

    # Respiratory rate
    if rr < 9:
        s_rr = 2
    elif rr <= 14:
        s_rr = 0
    elif rr <= 20:
        s_rr = 1
    elif rr <= 29:
        s_rr = 2
    else:
        s_rr = 3

    # Heart rate
    if hr <= 40:
        s_hr = 2
    elif hr <= 50:
        s_hr = 1
    elif hr <= 100:
        s_hr = 0
    elif hr <= 110:
        s_hr = 1
    elif hr <= 129:
        s_hr = 2
    else:
        s_hr = 3

    # Systolic blood pressure
    if sbp <= 70:
        s_sbp = 3
    elif sbp <= 80:
        s_sbp = 2
    elif sbp <= 100:
        s_sbp = 1
    elif sbp < 200:
        s_sbp = 0
    else:
        s_sbp = 2

    # Temperature (C)
    s_temp = 0 if 35.0 <= temp <= 38.4 else 2

    # Consciousness proxy from GCS (approximation of AVPU component)
    if gcs >= 15:
        s_cns = 0
    elif gcs >= 13:
        s_cns = 1
    elif gcs >= 9:
        s_cns = 2
    else:
        s_cns = 3

    return int(s_rr + s_hr + s_sbp + s_temp + s_cns)


def _first_cohort_patients(df: pd.DataFrame) -> pd.DataFrame:
    """One row per patient from earliest qualifying journey, with normalized MRN key."""
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["medevac1_date"] = pd.to_datetime(j["medevac1_date"], errors="coerce")
    first = j.sort_values("medevac1_date").groupby("MRN", as_index=False).first()
    first["_mrn_k"] = first["MRN"].map(_mrn_normalize)
    return first[first["_mrn_k"].notna()].copy()


def _load_vitals_for_cohort() -> tuple[pd.DataFrame | None, dict[str, str] | None, str | None]:
    """
    Load vitals file and return (vitals_df, column_map, error_note).
    error_note is None when successful.
    """
    vpath = vitals_csv_path()
    if not vpath.is_file():
        return None, None, "no vitals file"
    vit = pd.read_csv(vpath, low_memory=False)
    cm = _vital_column_map(vit)
    if cm is None:
        return vit, None, "missing required vital columns"
    mrn_col = _pick_vitals_col(vit, _MRN_ALIASES)
    if not mrn_col:
        return vit, cm, "missing MRN column"
    vit["_mrn_k"] = vit[mrn_col].map(_mrn_normalize)
    vit = vit[vit["_mrn_k"].notna()].copy()
    # Prefer village rows when phase metadata exists.
    if "facility_phase" in vit.columns:
        phase = vit["facility_phase"].astype(str).str.lower()
        if phase.str.contains("village", na=False).any():
            vit = vit[phase.str.contains("village", na=False)].copy()
    return vit, cm, None


def _age_bucket_key(a: float) -> str | None:
    if pd.isna(a):
        return None
    if a < 1:
        return "b0"
    if a < 5:
        return "b1"
    if a < 13:
        return "b2"
    if a <= 18:
        return "b3"
    return "other"


def build_table2_patient_characteristics_by_age(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 1, Table 2: Patient characteristics stratified by age group.

    Rows  = # Unique Patients, Female Sex, Race, Insurance Type subcategories.
    Columns = Overall | <1 year | 1 to <5 years | 5–12 years | 13–18 years.

    One row per patient = earliest qualifying journey per MRN.
    Race and Insurance show NR placeholder if PHI columns absent from pediatric_patients.csv.
    """
    AGE_GROUPS = [
        ("<1 year",       "b0"),
        ("1 to <5 years", "b1"),
        ("5–12 years",    "b2"),
        ("13–18 years",   "b3"),
    ]
    INSURANCE_CATS = ["Commercial", "Government", "IHS", "Self-Pay", "Other"]

    patients = pd.read_csv(DATA / "pediatric_patients.csv")

    j = df.drop_duplicates(subset=["journey_id"]).copy()

    # Sort by best available date to pick each patient's earliest journey.
    for src in ("journey_start_year", "medevac1_dts", "medevac1_date"):
        if src in j.columns and not j[src].isna().all():
            j["_sort_key"] = pd.to_numeric(
                pd.to_datetime(j[src], errors="coerce"), errors="coerce"
            ) if "dts" in src or "date" in src else pd.to_numeric(j[src], errors="coerce")
            break
    else:
        j["_sort_key"] = range(len(j))

    first = j.sort_values("_sort_key").groupby("MRN", as_index=False).first()

    # Count village→MHC legs per patient across ALL journeys (not just first).
    leg_counts: dict[str, int] = {}
    for _, row in j.iterrows():
        mrn = row["MRN"]
        for i in (1, 2, 3):
            raw_frm = row.get(f"medevac{i}_from")
            raw_to  = row.get(f"medevac{i}_to")
            if pd.isna(raw_frm) or pd.isna(raw_to):
                continue
            frm, to = str(raw_frm).strip(), str(raw_to).strip()
            if frm and to and is_village_medevac_origin(frm) and _is_mhc_cah_destination(to):
                leg_counts[mrn] = leg_counts.get(mrn, 0) + 1
    first["_n_primary"] = first["MRN"].map(leg_counts).fillna(0).astype(int)
    first["_transport_cat"] = first["_n_primary"].map(
        lambda n: "1" if n == 1 else ("2" if n == 2 else "3+")
    )

    # Merge optional PHI columns only if not already carried in from load_data().
    phi_cols = [
        c for c in ("AI_AN", "RaceDSC", "PrimaryPayorNM", "GenderDSC")
        if c in patients.columns and c not in first.columns
    ]
    if phi_cols:
        first = first.merge(patients[["MRN"] + phi_cols], on="MRN", how="left")

    # Age bucket on first journey.
    age = pd.to_numeric(first["age_at_medevac"], errors="coerce")
    def _bucket(a: float) -> str | None:
        if pd.isna(a): return None
        if a < 1:   return "b0"
        if a < 5:   return "b1"
        if a < 13:  return "b2"
        if a <= 18: return "b3"
        return None
    first["_age_grp"] = age.map(_bucket)

    # Insurance categorisation helper.
    def _ins_cat(raw: str) -> str:
        r = str(raw).lower()
        if any(x in r for x in ("commercial", "private", "blue cross", "aetna", "cigna", "united", "humana")):
            return "Commercial"
        if any(x in r for x in ("medicaid", "medicare", "chip", "government", "tricare", "va ")):
            return "Government"
        if any(x in r for x in ("ihs", "indian health", "tribal")):
            return "IHS"
        if any(x in r for x in ("self", "uninsured", "none", "no insurance")):
            return "Self-Pay"
        if r in ("nan", "", "missing", "unknown"):
            return None
        return "Other"

    def _col_stats(sub: pd.DataFrame) -> dict:
        N = len(sub)
        female = int((sub.get("GenderDSC", pd.Series([])) == "Female").sum()) if "GenderDSC" in sub.columns else None

        # Race
        if "RaceDSC" in sub.columns:
            ai = sub["RaceDSC"].astype(str).str.contains(
                r"indian|alaska\s*native|american\s*indian", case=False, na=False, regex=True
            )
            race_val = fmt_pct_n(int(ai.sum()), N)
        elif "AI_AN" in sub.columns:
            known = sub["AI_AN"].notna() & (sub["AI_AN"].astype(str).str.strip() != "")
            yes = known & sub["AI_AN"].apply(
                lambda x: str(x).strip().lower() in ("1", "y", "yes", "true") or x is True
            )
            race_val = fmt_pct_n(int(yes.sum()), N) if known.any() else None
        else:
            race_val = None

        # Insurance
        if "PrimaryPayorNM" in sub.columns:
            cats = sub["PrimaryPayorNM"].astype(str).map(_ins_cat)
            ins = {c: int((cats == c).sum()) for c in INSURANCE_CATS}
        else:
            ins = None

        # Primary transport count — ordered categorical
        tc = sub["_transport_cat"].value_counts()
        transport = {cat: int(tc.get(cat, 0)) for cat in ("1", "2", "3+")}

        return {"N": N, "female": female, "race": race_val, "ins": ins,
                "transport": transport}

    def _fmt_col(stats: dict) -> list[str]:
        N = stats["N"]
        rows_out = [str(N)]
        rows_out.append(fmt_pct_n(stats["female"], N) if stats["female"] is not None else "NR*")
        rows_out.append(stats["race"] if stats["race"] is not None else "NR*")
        # Insurance header (blank cell)
        rows_out.append("")
        for cat in INSURANCE_CATS:
            if stats["ins"] is not None:
                rows_out.append(fmt_pct_n(stats["ins"][cat], N))
            else:
                rows_out.append("NR*")
        # Primary transports per patient
        rows_out.append("")
        for cat in ("1", "2", "3+"):
            rows_out.append(fmt_pct_n(stats["transport"][cat], N))
        return rows_out

    metric_col = [
        "# Unique Patients",
        "Female Sex",
        "Race (AI/AN)",
        "Insurance Type:",
    ] + [f"  {c}" for c in INSURANCE_CATS] + [
        "Primary transports per patient, n (%):",
        "  1 transport",
        "  2 transports",
        "  3+ transports",
    ]

    result = {"Metric of Interest": metric_col}
    result["Overall"] = _fmt_col(_col_stats(first))
    for label, bucket in AGE_GROUPS:
        sub = first[first["_age_grp"] == bucket]
        result[label] = _fmt_col(_col_stats(sub))

    base = pd.DataFrame(result)

    # ── Append Chief Complaint section (custom grouping, top 20) ─────────────
    # Respiratory, GI, and Trauma/Injury are collapsed to their category;
    # all other complaints keep their individual CEDIS complaint name.
    cc = _definitive_cc_per_journey(df)
    valid_cc = cc[cc["cc_definitive_custom_grouping"] != "Undefined"].copy()

    col_order = ["Metric of Interest", "Overall"] + [lbl for lbl, _ in AGE_GROUPS]
    bucket_totals = {bk: int((cc["age_bucket"] == bk).sum()) for _, bk in AGE_GROUPS}
    n_overall_cc = len(cc)

    top20 = (
        valid_cc.groupby("cc_definitive_custom_grouping", dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(10)
        .index.tolist()
    )

    cc_rows = [["Chief Complaints (CEDIS):"] + [""] * (len(col_order) - 1)]
    for grp in top20:
        n_ov = int((valid_cc["cc_definitive_custom_grouping"] == grp).sum())
        row = [f"  {grp}", fmt_pct_n(n_ov, n_overall_cc)]
        for _, bk in AGE_GROUPS:
            sub_cc = valid_cc[valid_cc["age_bucket"] == bk]
            n_bk = int((sub_cc["cc_definitive_custom_grouping"] == grp).sum())
            row.append(fmt_pct_n(n_bk, bucket_totals[bk]))
        cc_rows.append(row)

    cc_df = pd.DataFrame(cc_rows, columns=col_order)
    out = pd.concat([base, cc_df], ignore_index=True)
    out.to_csv(ROOT / "outputs" / "tables" / "table2_patient_characteristics_by_age.csv", index=False)
    return out


def _compute_timing_qc(df: pd.DataFrame) -> dict:
    """
    Compute timing quality-control statistics for the village→MHC cohort.

    Returns a dict with:
      floors           : {village_name: floor_minutes}  (2 × median one-way flight)
      n_total          : total unique journeys
      --- activate_to_arrive_min (interval 2) ---
      n_ata_raw        : journeys with non-null activate_to_arrive_min
      n_ata_direction  : excluded because destination_datetime < origin_datetime
      n_ata_below_floor: excluded because value < per-village flight-time floor
      n_ata_final      : usable after exclusions
      --- time_to_activate_min (interval 1) ---
      n_tta_raw        : journeys with non-null time_to_activate_min
      n_tta_neg        : excluded because value < 0 (impossible)
      n_tta_final      : usable after exclusions
      --- total travel time (interval 3) ---
      n_total_raw      : journeys with both origin & destination datetimes
      n_total_direction: excluded because destination < origin
      n_total_final    : usable after exclusions
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    vcol = "facility_1_name"

    # ── Per-village floor from reference flight times ─────────────────────────
    # flight_time_min is sourced from a reference CSV (typical flight times by
    # village), NOT measured from individual medevac encounters.  It is used
    # ONLY here to define an impossibility floor for activate_to_arrive_min.
    # Floor = 2 × per-village median reference flight time
    #   (plane must fly TO the village and then back with the patient).
    ft = pd.to_numeric(j.get("flight_time_min", pd.Series(dtype=float, index=j.index)),
                       errors="coerce")
    j["_ft"] = ft
    floors: dict[str, float] = {}
    if ft.notna().any() and vcol in j.columns:
        floors = (
            j[j[vcol].notna()]
            .groupby(vcol)["_ft"]
            .apply(lambda x: x.dropna().median() * 2.0)
            .dropna()
            .to_dict()
        )

    # ── activate_to_arrive_min (interval 2) ───────────────────────────────────
    ata = pd.to_numeric(j.get("activate_to_arrive_min", pd.Series(dtype=float, index=j.index)),
                        errors="coerce")
    orig = pd.to_datetime(j.get("origin_datetime"), errors="coerce")
    dest = pd.to_datetime(j.get("destination_datetime"), errors="coerce")

    # Direction check: any journey where destination precedes origin
    bad_dir_mask = dest.notna() & orig.notna() & (dest < orig)
    n_ata_direction = int(bad_dir_mask.sum())

    # Below-floor check: per-village reference floor
    below_floor_mask = pd.Series(False, index=j.index)
    if floors and vcol in j.columns:
        for v, floor in floors.items():
            v_mask = (j[vcol] == v) & ata.notna() & ~bad_dir_mask
            below_floor_mask |= v_mask & (ata < floor)
    n_ata_below_floor = int(below_floor_mask.sum())

    n_ata_raw   = int(ata.notna().sum())
    n_ata_final = int((ata.notna() & ~bad_dir_mask & ~below_floor_mask).sum())

    # ── time_to_activate_min (interval 1) ─────────────────────────────────────
    tta = pd.to_numeric(j.get("time_to_activate_min", pd.Series(dtype=float, index=j.index)),
                        errors="coerce")
    n_tta_raw   = int(tta.notna().sum())
    n_tta_neg   = int((tta < 0).sum())
    n_tta_final = int((tta >= 0).sum())

    # Journeys with COMPLETE activation timing (both intervals valid)
    orig = pd.to_datetime(j.get("origin_datetime"), errors="coerce")
    dest = pd.to_datetime(j.get("destination_datetime"), errors="coerce")
    total_min_all = (dest - orig).dt.total_seconds() / 60
    valid_tta = tta.notna() & (tta >= 0) & (tta <= total_min_all.fillna(float("inf")))
    valid_ata = ata.notna() & ~bad_dir_mask & ~below_floor_mask
    n_activation_complete = int((valid_tta & valid_ata).sum())

    # ── Total travel (interval 3): origin_datetime → destination_datetime ─────
    total_min = (dest - orig).dt.total_seconds() / 60
    n_miss_origin = int(orig.isna().sum())
    n_miss_dest   = int(dest.isna().sum())
    n_miss_either = int((orig.isna() | dest.isna()).sum())
    n_total_raw       = int((orig.notna() & dest.notna()).sum())
    n_total_direction = int(bad_dir_mask.sum())
    n_total_final     = int((total_min > 0).sum())

    return dict(
        floors=floors,
        n_total=len(j),
        n_ata_raw=n_ata_raw,
        n_ata_direction=n_ata_direction,
        n_ata_below_floor=n_ata_below_floor,
        n_ata_final=n_ata_final,
        n_tta_raw=n_tta_raw,
        n_tta_neg=n_tta_neg,
        n_tta_final=n_tta_final,
        n_activation_complete=n_activation_complete,
        n_total_raw=n_total_raw,
        n_total_direction=n_total_direction,
        n_total_final=n_total_final,
        n_miss_origin=n_miss_origin,
        n_miss_dest=n_miss_dest,
        n_miss_either=n_miss_either,
    )


def export_secondary_excluded_from_mhc_filter(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    Export the secondary (village→MHC→ANMC) journeys that pass the facility-sequence
    route classification but do NOT appear in filter_journeys_village_to_mhc().
    These are likely data quality edge cases worth investigating.
    Saved to outputs/review/secondary_excluded_from_mhc_filter.csv.
    """
    j = df_all.drop_duplicates("journey_id").copy()

    # All secondary journeys by facility sequence
    def _is_secondary(row):
        loc1 = str(row.get("facility_1_name") or "")
        m1to = row.get("medevac1_to")
        m2to = row.get("medevac2_to")
        m1s = "" if pd.isna(m1to) else str(m1to).strip()
        m2s = "" if pd.isna(m2to) else str(m2to).strip()
        return is_village_medevac_origin(loc1) and _is_mhc_cah_destination(m1s) and bool(m2s)

    secondary_ids = set(j[j.apply(_is_secondary, axis=1)]["journey_id"].astype(str))

    # Journeys in the MHC filter
    from medevac_summaries import filter_journeys_village_to_mhc
    df_mhc = filter_journeys_village_to_mhc(df_all)
    mhc_ids = set(df_mhc["journey_id"].astype(str))

    excluded_ids = secondary_ids - mhc_ids
    out = j[j["journey_id"].astype(str).isin(excluded_ids)].copy()

    review_cols = [
        "journey_id", "MRN", "facility_1_name", "facility_2_name", "facility_3_name",
        "journey_start_date", "medevac1_from", "medevac1_to", "medevac2_from", "medevac2_to",
        "journey_pattern", "journey_end_reason",
    ]
    out = out[[c for c in review_cols if c in out.columns]].reset_index(drop=True)

    out_path = ROOT / "outputs" / "review" / "secondary_excluded_from_mhc_filter.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"[export] {len(out)} journeys written to {out_path}")
    return out


def export_missing_destination_datetime(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pull journeys where destination_datetime is missing (MHC arrival timestamp
    not recorded) for hand review.  Saved to outputs/review/missing_destination_datetime.csv.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    orig = pd.to_datetime(j["origin_datetime"], errors="coerce")
    dest = pd.to_datetime(j["destination_datetime"], errors="coerce")

    missing = j[orig.isna() | dest.isna()].copy()

    review_cols = [
        "journey_id", "MRN",
        "facility_1_name",
        "journey_start_date", "journey_end_date",
        "origin_datetime", "origin_datetime_imputed", "origin_imputed",
        "destination_datetime", "destination_imputed",
        "medevac1_date", "medevac1_dts", "medevac1_dts_source",
        "medevac1_from", "medevac1_to",
        "medevac1_from_encounter", "medevac1_to_encounter",
        "medevac2_date", "medevac2_dts", "medevac2_dts_source",
        "medevac2_from", "medevac2_to",
        "journey_duration_hours", "journey_end_reason",
        "num_medevacs", "journey_pattern",
        "missing_origin", "missing_destination",
    ]

    missing["missing_origin"]      = orig[missing.index].isna()
    missing["missing_destination"] = dest[missing.index].isna()

    out_cols = [c for c in review_cols if c in missing.columns]
    out = missing[out_cols].reset_index(drop=True)

    out_path = ROOT / "outputs" / "review" / "missing_destination_datetime.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(out_path, index=False)
    print(f"[export] {len(out)} journeys written to {out_path}")
    return out


def build_timing_overview_text(df: pd.DataFrame) -> str:
    """
    Return a narrative paragraph describing timing data availability and QC
    for use as a 'Timing Overview' block before Table 1 in the manuscript.
    """
    qc = _compute_timing_qc(df)
    N = qc["n_total"]

    def _pct(n, d=N):
        return f"{n/d*100:.1f}%" if d else "—"

    lines = [
        f"**Timing data availability and quality.** "
        f"Of {N} primary medevac journeys included in this analysis, timing data "
        f"were available across three intervals with varying completeness.",

        f"*Interval 1 — Air ambulance decision-making time (village clinic arrival to activation)* "
        f"({qc['n_tta_raw']} of {N} journeys, {_pct(qc['n_tta_raw'])}): "
        f"This interval requires a documented authorization or activation record. "
        + (
            f"{qc['n_tta_neg']} observation(s) with a negative value were excluded as impossible, "
            f"yielding {qc['n_tta_final']} valid measurements."
            if qc["n_tta_neg"] > 0
            else f"No observations with impossible (negative) values were identified; "
                 f"all {qc['n_tta_final']} recorded values were used."
        )
        + f" Of these, {qc['n_activation_complete']} journeys also have a valid "
          f"response-and-transfer time, giving a complete-activation-timing cohort of "
          f"{qc['n_activation_complete']} ({_pct(qc['n_activation_complete'])}). "
          f"Only this subset is used for both activation sub-interval rows in Table 1.",

        f"*Interval 2 — Medevac activation to MHC arrival* "
        f"({qc['n_ata_raw']} of {N} journeys, {_pct(qc['n_ata_raw'])}): "
        f"An impossibility floor was applied using reference flight times (typical "
        f"one-way flight durations by village, not drawn from the medevac encounter "
        f"data). Any activation-to-arrival value shorter than twice the per-village "
        f"reference flight time (the minimum round-trip duration: Kotzebue → village "
        f"→ Kotzebue) was considered a likely timestamp or data-entry error. "
        + (
            f"{qc['n_ata_direction']} observation(s) were also excluded because the "
            f"destination datetime preceded the origin datetime. "
            if qc["n_ata_direction"] > 0
            else ""
        )
        + (
            f"{qc['n_ata_below_floor']} observation(s) fell below this per-village "
            f"round-trip floor and were excluded. "
            if qc["n_ata_below_floor"] > 0
            else "No observations fell below the round-trip reference floor. "
        )
        + f"After these exclusions, {qc['n_ata_final']} valid measurements were used.",

        f"*Interval 3 — Total air-ambulance time (village clinic arrival to MHC arrival)* "
        f"({qc['n_total_raw']} of {N} journeys, {_pct(qc['n_total_raw'])}): "
        f"Derived directly from encounter start (origin_datetime) and end (destination_datetime) timestamps. "
        + (
            f"{qc['n_miss_either']} journey(s) are missing at least one timestamp and cannot "
            f"be included in this interval ("
            + (f"{qc['n_miss_origin']} missing origin_datetime" if qc["n_miss_origin"] else "")
            + (" and " if qc["n_miss_origin"] and qc["n_miss_dest"] else "")
            + (f"{qc['n_miss_dest']} missing destination_datetime" if qc["n_miss_dest"] else "")
            + "); this is a data completeness issue in the source records. "
            if qc["n_miss_either"] > 0
            else "All journeys have both timestamps recorded. "
        )
        + (
            f"{qc['n_total_direction']} observation(s) were additionally excluded due to "
            f"impossible temporal direction (destination before origin), "
            if qc["n_total_direction"] > 0
            else ""
        )
        + f"yielding {qc['n_total_final']} valid measurements.",
    ]
    return "\n\n".join(lines)


def build_table1_village_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 1, Table 1: Medevac characteristics by village of origin.

    Rows (metrics):
      1. Total number of journeys
      2. Number of patients
      3. Mean flights per year
      4. Distance to Kotzebue (miles, straight-line)
      5. Village clinic arrival → activation — Median (IQR); Range  [n=X]
         (requires auth record; lower N)
      6. Activation → MHC arrival — Median (IQR); Range  [n=X]
         (floor = 2 × per-village median one-way flight time)
      7. Total air ambulance time (village arrival → MHC) — Median (IQR); Range  [n=X]
      8. Utilization rate per 1,000 pediatric residents (2020 Census)

    Columns = Overall | each village sorted by total journeys descending.
    """
    from math import radians, cos, sin, asin, sqrt

    census_path = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"
    census = pd.read_csv(census_path) if census_path.exists() else None
    census_map: dict[str, int] = (
        dict(zip(census["NAME"], census["pediatric_pop"].astype(int)))
        if census is not None else {}
    )

    # ── Compute village → Kotzebue distances from shapefile ──────────────────
    FAC_SHP = ROOT / "mapping_data" / "healthcare_facilities_safetynet" / \
              "healthcare_facilities_safetynet.shp"

    dist_map: dict[str, float] = {}
    if FAC_SHP.is_file():
        try:
            import geopandas as gpd

            def _hav_miles(lat1, lon1, lat2, lon2):
                R = 3958.8
                dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
                a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
                return R * 2 * asin(sqrt(a))

            _fac = gpd.read_file(FAC_SHP).to_crs(epsg=4326)
            _man = _fac[_fac["ManagingOr"] == "Maniilaq Association"][
                ["CommunityN", "geometry"]
            ].drop_duplicates("CommunityN")
            _kotz = _man[_man["CommunityN"].str.lower() == "kotzebue"]
            if not _kotz.empty:
                klon = float(_kotz.iloc[0].geometry.x)
                klat = float(_kotz.iloc[0].geometry.y)
                for _, row in _man.iterrows():
                    vname = str(row["CommunityN"]).strip()
                    vlon  = float(row.geometry.x)
                    vlat  = float(row.geometry.y)
                    dist_map[vname] = round(_hav_miles(klat, klon, vlat, vlon))
        except Exception:
            pass  # shapefile unavailable — distances shown as "—"

    # ── Timing QC: floors, exclusion masks ────────────────────────────────────
    qc = _compute_timing_qc(df)
    floors = qc["floors"]          # {village: floor_minutes}

    # ── Study period ──────────────────────────────────────────────────────────
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    village_col = "facility_1_name"
    yr_col = "journey_start_year"
    # Derive year from origin_datetime if the pipeline column isn't present
    if yr_col not in j.columns or j[yr_col].isna().all():
        j[yr_col] = pd.to_datetime(j.get("origin_datetime"), errors="coerce").dt.year
    yr = pd.to_numeric(j[yr_col], errors="coerce").dropna()
    study_years = max(1.0, float(yr.nunique()))

    # Build journey-level exclusion masks (aligned to j.index)
    _ata_all  = pd.to_numeric(j.get("activate_to_arrive_min",
                                     pd.Series(dtype=float, index=j.index)), errors="coerce")
    _orig_all = pd.to_datetime(j.get("origin_datetime"), errors="coerce")
    _dest_all = pd.to_datetime(j.get("destination_datetime"), errors="coerce")
    _bad_dir  = _dest_all.notna() & _orig_all.notna() & (_dest_all < _orig_all)
    # Per-village floor from reference flight times (same logic as _compute_timing_qc)
    _below_floor = pd.Series(False, index=j.index)
    if floors and village_col in j.columns:
        for _v, _flr in floors.items():
            _vm = (j[village_col] == _v) & _ata_all.notna() & ~_bad_dir
            _below_floor |= _vm & (_ata_all < _flr)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _med_iqr_range_n(series: pd.Series) -> tuple[str, int]:
        """Return (formatted string, n) for a series after dropping NaN."""
        s = pd.to_numeric(series, errors="coerce").dropna()
        n = len(s)
        if n == 0:
            return "—", 0
        med = s.median()
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        lo, hi = s.min(), s.max()
        return f"{med:.0f} ({q1:.0f}–{q3:.0f}); {lo:.0f}–{hi:.0f}", n

    def _fmt_n(val_str: str, n: int, total: int) -> str:
        """Append [n=X of Y] to a cell value string."""
        if val_str == "—":
            return "—"
        return f"{val_str} [n={n} of {total}]"

    def _stats(sub: pd.DataFrame, village_name: str | None, pop: int | None) -> list[str]:
        n_journeys = len(sub)
        n_patients = int(sub["MRN"].nunique())

        # Mean (SD) journeys per year — SD across individual calendar years
        if yr_col in sub.columns:
            _yr_series = pd.to_numeric(sub[yr_col], errors="coerce").dropna().astype(int)
            if not _yr_series.empty:
                _yr_counts = _yr_series.value_counts()
                _y0 = int(pd.to_numeric(j[yr_col], errors="coerce").dropna().min())
                _y1 = int(pd.to_numeric(j[yr_col], errors="coerce").dropna().max())
                _annual = pd.Series({y: _yr_counts.get(y, 0) for y in range(_y0, _y1 + 1)})
                _mean = _annual.mean()
                _sd   = _annual.std(ddof=1) if len(_annual) > 1 else 0.0
                mean_yr = f"{_mean:.1f} ({_sd:.1f})"
            else:
                mean_yr = "—"
        else:
            mean_yr = f"{n_journeys / study_years:.1f}"

        dist = f"{dist_map[village_name]:.0f}" if village_name and village_name in dist_map else "—"

        # ── Interval 3: total village arrival → MHC arrival ────────────────
        # (shown immediately after Distance)
        _orig = _orig_all.reindex(sub.index)
        _dest = _dest_all.reindex(sub.index)
        _total_min = (_dest - _orig).dt.total_seconds() / 60
        _bad_sub = _bad_dir.reindex(sub.index, fill_value=False)
        _total_valid = _total_min[~_bad_sub & (_total_min > 0)]
        total_str, _ = _med_iqr_range_n(_total_valid)

        # ── Valid activation subset ─────────────────────────────────────────
        # Requires ALL of:
        #   1. time_to_activate_min non-null, >= 0, falls before MHC arrival
        #   2. activate_to_arrive_min non-null AND above the per-village floor
        # Both intervals must be valid so the header n= equals both sub-rows.
        _tta = pd.to_numeric(
            sub.get("time_to_activate_min", pd.Series(dtype=float, index=sub.index)),
            errors="coerce",
        ).reindex(sub.index)
        _valid_tta = (
            _tta.notna()
            & (_tta >= 0)
            & (_tta <= _total_min.fillna(float("inf")))
        )

        _ata = _ata_all.reindex(sub.index)
        _excl = (
            _bad_dir.reindex(sub.index, fill_value=False)
            | _below_floor.reindex(sub.index, fill_value=False)
        )
        _valid_ata = _ata.notna() & ~_excl

        _valid_act = _valid_tta & _valid_ata
        n_act = int(_valid_act.sum())
        pct_act = f"{n_act / n_journeys * 100:.1f}% (n={n_act})" if n_journeys else "—"

        # Interval 1: decision-making time (activation subset, no n= annotation)
        v_to_act_str, _ = _med_iqr_range_n(_tta[_valid_act])
        v_to_act = v_to_act_str if v_to_act_str != "—" else "—"

        # Interval 2: response and transfer time (activation subset, no n= annotation)
        act_to_arr_str, _ = _med_iqr_range_n(_ata[_valid_act])
        act_to_arr = act_to_arr_str if act_to_arr_str != "—" else "—"

        util = f"{n_journeys / pop * 1_000:.1f}" if pop and pop > 0 else "—"
        return [
            str(n_journeys),    # Total journeys
            str(n_patients),    # Total patients
            mean_yr,            # Mean journeys per year (SD)
            dist,               # Distance to Kotzebue
            total_str,          # Total air ambulance time
            "",                 # ── Air Ambulance Activation header ──
            pct_act,            # % with complete timing data (n=)
            v_to_act,           # Village arrival → activation [n= of activation subset]
            act_to_arr,         # Activation → MHC arrival    [n= of activation subset]
            util,               # Utilization rate
        ]

    metric_labels = [
        "Total journeys",
        "Total patients",
        "Mean journeys per year (SD)",
        "Distance to Kotzebue (miles)",
        "Total air ambulance time (arrival → MHC), min — Median (IQR); Range",
        "Air Ambulance Activation",
        "  % with complete timing data (n)",
        "  Air ambulance decision-making time, min — Median (IQR); Range",
        "  Air ambulance response and transfer time, min — Median (IQR); Rangeᵃ",
        "Utilization rate per 1,000 pediatric residents",
    ]

    villages = (
        j[j[village_col].apply(lambda x: is_village_medevac_origin(str(x or "")))]
        [village_col].value_counts().index.tolist()
    )
    overall_pop = sum(census_map.get(v, 0) for v in villages) or None

    result = {
        "Metric": metric_labels,
        "Overall": _stats(j, None, overall_pop),
    }
    for v in villages:
        sub = j[j[village_col] == v]
        result[v] = _stats(sub, v, census_map.get(v))

    out = pd.DataFrame(result)
    out.to_csv(ROOT / "outputs" / "tables" / "table1_village_characteristics.csv", index=False)
    return out


def build_table4_village_utilization(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 1, Table 4: Village-level utilization summary with age strata.

    Rows = one per village of origin, sorted by utilization rate per 1,000 descending.
    Columns: Village, Pediatric pop (2020), Total journeys, Journeys/year mean (SD),
             Rate per 1,000, then n (%) for each of 4 age groups.

    *df* should be the village→MHC journey cohort from filter_journeys_village_to_mhc().
    Village origin is resolved from facility_1_name, falling back to medevac1_from /
    origin_facility when facility_1_name does not contain village identifiers (e.g.
    on some de-identified synthetic extracts).
    """
    census_path = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"
    census = pd.read_csv(census_path) if census_path.exists() else None
    census_map: dict[str, int] = (
        dict(zip(census["NAME"], census["pediatric_pop"].astype(int)))
        if census is not None else {}
    )

    AGE_GROUPS = [
        ("<1 yr",       "b0"),
        ("1–4 yr",      "b1"),
        ("5–12 yr",     "b2"),
        ("13–18 yr",    "b3"),
    ]

    j = df.drop_duplicates("journey_id").copy()

    # ── Village column resolution ──────────────────────────────────────────────
    village_col = "facility_1_name"
    if not j[village_col].apply(lambda x: is_village_medevac_origin(str(x or ""))).any():
        for alt in ("origin_facility", "medevac1_from"):
            if alt in j.columns and j[alt].apply(
                lambda x: is_village_medevac_origin(str(x or ""))
            ).any():
                village_col = alt
                break

    # ── Study year range ───────────────────────────────────────────────────────
    yr_col = "journey_start_year"
    if yr_col not in j.columns or j[yr_col].isna().all():
        j[yr_col] = pd.to_datetime(j.get("origin_datetime"), errors="coerce").dt.year
    j["_year"] = pd.to_numeric(j[yr_col], errors="coerce")
    yr_vals = j["_year"].dropna()
    y0 = int(yr_vals.min()) if not yr_vals.empty else 0
    y1 = int(yr_vals.max()) if not yr_vals.empty else 0
    study_year_range = range(y0, y1 + 1) if y1 >= y0 else range(y0, y0 + 1)

    # ── Age bucket per journey ─────────────────────────────────────────────────
    j["_ab"] = pd.to_numeric(j.get("age_at_medevac"), errors="coerce").map(_age_bucket_key)

    def _fmt_pct(n_sub: int, n_tot: int) -> str:
        if n_tot == 0:
            return "—"
        return f"{n_sub / n_tot * 100:.1f}% ({n_sub})"

    def _mean_sd_annual(sub: pd.DataFrame) -> str:
        _yr = sub["_year"].dropna().astype(int)
        _counts = _yr.value_counts()
        _annual = pd.Series({y: _counts.get(y, 0) for y in study_year_range})
        mn = _annual.mean()
        sd = _annual.std(ddof=1) if len(_annual) > 1 else 0.0
        return f"{mn:.1f} ({sd:.1f})"

    # ── Per-village rows ───────────────────────────────────────────────────────
    village_mask = j[village_col].apply(lambda x: is_village_medevac_origin(str(x or "")))
    villages_sorted = (
        j[village_mask].groupby(village_col).size()
        .sort_values(ascending=False).index.tolist()
    )

    rows = []
    for village in villages_sorted:
        sub = j[j[village_col] == village]
        n = len(sub)
        pop = census_map.get(village)
        rate = f"{n / pop * 1_000:.1f}" if pop and pop > 0 else "—"
        row: dict[str, str] = {
            "Village":                   village,
            "Pediatric pop (2020)":      str(pop) if pop else "—",
            "Total journeys":            str(n),
            "Journeys/year, mean (SD)":  _mean_sd_annual(sub),
            "Rate per 1,000":            rate,
        }
        for label, bk in AGE_GROUPS:
            n_bk = int((sub["_ab"] == bk).sum())
            row[label] = _fmt_pct(n_bk, n)
        rows.append(row)

    out = pd.DataFrame(rows)

    # Sort by numeric rate descending (villages with "—" go to end)
    _rate_num = pd.to_numeric(out["Rate per 1,000"], errors="coerce")
    out = out.iloc[_rate_num.argsort()[::-1].values].reset_index(drop=True)

    # ── Overall total row ──────────────────────────────────────────────────────
    sub_all = j[village_mask]
    n_all = len(sub_all)
    total_pop = sum(census_map.get(v, 0) for v in villages_sorted) or None
    overall_rate = f"{n_all / total_pop * 1_000:.1f}" if total_pop else "—"
    overall_row: dict[str, str] = {
        "Village":                   "Overall",
        "Pediatric pop (2020)":      str(total_pop) if total_pop else "—",
        "Total journeys":            str(n_all),
        "Journeys/year, mean (SD)":  _mean_sd_annual(sub_all),
        "Rate per 1,000":            overall_rate,
    }
    for label, bk in AGE_GROUPS:
        n_bk = int((sub_all["_ab"] == bk).sum())
        overall_row[label] = _fmt_pct(n_bk, n_all)
    out = pd.concat([out, pd.DataFrame([overall_row])], ignore_index=True)

    out.to_csv(ROOT / "outputs" / "tables" / "table4_village_utilization.csv", index=False)
    return out


# backward-compat alias (tbl-t4 in qmd previously called this name)
def build_table3_village_utilization(df: pd.DataFrame) -> pd.DataFrame:
    return build_table4_village_utilization(df)


def build_table2_village_visit_vitals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2: among village→MHC cohort patients (earliest qualifying journey per MRN),
    how many have ≥1 **complete** vital set at village visit (HR, O2, BP sys+dia, RR, Temp).
    Rows: All patients, then Age Groups (subrows), then Origin Village (subrows, N descending).
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["medevac1_date"] = pd.to_datetime(j["medevac1_date"], errors="coerce")
    first = j.sort_values("medevac1_date").groupby("MRN", as_index=False).first()
    first["_mrn_k"] = first["MRN"].map(_mrn_normalize)
    first = first[first["_mrn_k"].notna()]
    n_pat = len(first)
    if n_pat == 0:
        return pd.DataFrame(
            [{"Group": "—", "Patients (N)": "0", "Complete vitals n (%)": "—"}]
        )

    rows: list[dict[str, str]] = []

    vpath = vitals_csv_path()
    if not vpath.is_file():
        rows.append(
            {
                "Group": "All patients",
                "Patients (N)": str(n_pat),
                "Complete vitals n (%)": "— (no vitals file)",
            }
        )
        rows.append(
            {
                "Group": "Note",
                "Patients (N)": "",
                "Complete vitals n (%)": (
                    f"Add pediatric_village_visit_vitals.csv or pediatric_vitals_wide.csv under data/. "
                    f"See docs/pediatric_village_visit_vitals.md"
                ),
            }
        )
        return pd.DataFrame(rows)

    vit = pd.read_csv(vpath)
    cm = _vital_column_map(vit)
    if cm is None:
        rows.append(
            {
                "Group": "All patients",
                "Patients (N)": str(n_pat),
                "Complete vitals n (%)": "— (missing columns)",
            }
        )
        rows.append(
            {
                "Group": "Note",
                "Patients (N)": "",
                "Complete vitals n (%)": (
                    f"Need MRN plus HR, O2, BP sys/dia, RR, Temp (e.g. *_median in {vpath.name}). "
                    "See docs/pediatric_village_visit_vitals.md"
                ),
            }
        )
        return pd.DataFrame(rows)

    complete_mrns = _mrns_complete_village_vitals(vit, cm)
    first["has_complete"] = first["_mrn_k"].isin(complete_mrns)
    n_comp = int(first["has_complete"].sum())

    rows.append(
        {
            "Group": "All patients",
            "Patients (N)": str(n_pat),
            "Complete vitals n (%)": fmt_n_pct(n_comp, n_pat),
        }
    )
    rows.append(
        {
            "Group": "Definition",
            "Patients (N)": "",
            "Complete vitals n (%)": (
                "≥1 row with HR, O2, BP systolic & diastolic, RR, Temp (village visit)"
            ),
        }
    )

    age = pd.to_numeric(first["age_at_medevac"], errors="coerce")
    ag = age.map(_age_bucket_key)
    age_labels = [
        ("<1 year", "b0"),
        ("1 to <5 years", "b1"),
        ("5–12 years", "b2"),
        ("13–18 years", "b3"),
    ]
    rows.append({"Group": "Age Groups", "Patients (N)": "", "Complete vitals n (%)": ""})
    for lab, key in age_labels:
        sub = first[ag == key]
        nd = len(sub)
        if nd == 0:
            continue
        nc = int(sub["has_complete"].sum())
        rows.append(
            {
                "Group": f"  {lab}",
                "Patients (N)": str(nd),
                "Complete vitals n (%)": fmt_n_pct(nc, nd),
            }
        )
    sub_m = first[ag.isna() | (ag == "other")]
    if len(sub_m) > 0:
        nd, nc = len(sub_m), int(sub_m["has_complete"].sum())
        rows.append(
            {
                "Group": "  Age missing or >18 y",
                "Patients (N)": str(nd),
                "Complete vitals n (%)": fmt_n_pct(nc, nd),
            }
        )

    fac = first["facility_1_name"].fillna("").astype(str)
    villages = {v for v in fac.unique() if str(v).strip() and is_village_medevac_origin(v)}
    vc = [(v, int((fac == v).sum())) for v in villages if int((fac == v).sum()) > 0]
    vc.sort(key=lambda x: (-x[1], x[0]))
    rows.append({"Group": "Origin Village", "Patients (N)": "", "Complete vitals n (%)": ""})
    for v, _nv in vc:
        sub = first[fac == v]
        nd, nc = len(sub), int(sub["has_complete"].sum())
        rows.append(
            {
                "Group": f"  {v}",
                "Patients (N)": str(nd),
                "Complete vitals n (%)": fmt_n_pct(nc, nd),
            }
        )

    return pd.DataFrame(rows)


def build_table2_1_vitals_missingness(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2.1: n(%) of cohort patients missing each vital at village visit.
    Missing = no documented value for that vital in any village-visit row.
    """
    first = _first_cohort_patients(df)
    n_pat = len(first)
    if n_pat == 0:
        return pd.DataFrame([{"Vital": "—", "Missing n(%)": "—"}])
    vit, cm, err = _load_vitals_for_cohort()
    if err is not None or vit is None or cm is None:
        return pd.DataFrame([{"Vital": "Note", "Missing n(%)": f"Unable to compute ({err})"}])

    cohort_mrns = set(first["_mrn_k"])
    vit = vit[vit["_mrn_k"].isin(cohort_mrns)].copy()
    def has_any(col: str) -> set[object]:
        p = _value_present_series(vit[col])
        return set(vit.loc[p, "_mrn_k"])

    present_hr = has_any(cm["hr"])
    present_o2 = has_any(cm["o2"])
    present_rr = has_any(cm["rr"])
    present_temp = has_any(cm["temp"])
    p_sys = _value_present_series(vit[cm["bp_sys"]])
    p_dia = _value_present_series(vit[cm["bp_dia"]])
    present_bp = set(vit.loc[p_sys & p_dia, "_mrn_k"])

    rows: list[dict[str, str]] = []
    for label, present in [
        ("HR", present_hr),
        ("O2 sat", present_o2),
        ("BP (systolic+diastolic)", present_bp),
        ("RR", present_rr),
        ("Temp", present_temp),
    ]:
        n_miss = int(len(cohort_mrns - present))
        rows.append({"Vital": label, "Missing n(%)": fmt_n_pct(n_miss, n_pat)})
    return pd.DataFrame(rows)


_COMPLETENESS_AGE_COLS: list[tuple[str, str | None]] = [
    ("Overall", None),
    ("<1 yr", "b0"),
    ("1–<5 yr", "b1"),
    ("5–12 yr", "b2"),
    ("13–18 yr", "b3"),
]
_COMPLETENESS_VITAL_LABELS = (
    "HR",
    "O2 sat",
    "BP (systolic+diastolic)",
    "RR",
    "Temp",
)


def build_table_completeness_vitals_pews(df: pd.DataFrame) -> pd.DataFrame:
    """
    Combined data completeness: PEWS-ready patients, timing data, and missing vitals,
    columns = Overall + age groups.
    """
    col_names = [label for label, _ in _COMPLETENESS_AGE_COLS]
    empty_cols = {label: "—" for label in col_names}
    age_group_by_key = {
        "b0": "<1 yr",
        "b1": "1–<5 yr",
        "b2": "5–12 yr",
        "b3": "13–18 yr",
    }

    j = df.drop_duplicates(subset=["journey_id"]).copy()
    if j.empty:
        return pd.DataFrame([{"Measure": "—", **empty_cols}])

    def journeys_for(age_key: str | None) -> pd.DataFrame:
        if age_key is None:
            return j
        if "age_group" in j.columns:
            label = age_group_by_key.get(age_key)
            if label:
                return j[j["age_group"] == label]
        age = pd.to_numeric(j.get("age_at_medevac"), errors="coerce")
        ag = age.map(_age_bucket_key)
        return j.loc[ag == age_key]

    def timing_cell(sub: pd.DataFrame) -> str:
        nd = len(sub)
        if nd == 0:
            return "—"
        if "time_to_activate_quality" not in sub.columns:
            return "— (not available)"
        n_ok = int((sub["time_to_activate_quality"] == "real").sum())
        return fmt_n_pct(n_ok, nd)

    first = _first_cohort_patients(df)
    cohort_mrns = set(first["_mrn_k"]) if len(first) else set()

    vit, cm, err = _load_vitals_for_cohort()
    present: dict[str, set[object]] = {}
    ready_mrns: set[object] = set()
    gcs_col: str | None = None
    vitals_note: str | None = None

    if err is not None or vit is None or cm is None:
        vitals_note = f"Unable to compute ({err})"
    elif not cohort_mrns:
        vitals_note = "No cohort patients"
    else:
        gcs_col = _pick_vitals_col(vit, _GCS_ALIASES)
        vit = vit[vit["_mrn_k"].isin(cohort_mrns)].copy()
        present = _vital_present_sets(vit, cm)
        if gcs_col:
            sub = vit.copy()
            sub["_pews_ready"] = sub.apply(
                lambda r: _pews_proxy_score_row(r, cm, gcs_col) is not None,
                axis=1,
            )
            ready_mrns = set(sub.loc[sub["_pews_ready"], "_mrn_k"])

    age = pd.to_numeric(first.get("age_at_medevac"), errors="coerce")
    ag = age.map(_age_bucket_key)

    def patient_set(age_key: str | None) -> set[object]:
        if age_key is None:
            return cohort_mrns
        return set(first.loc[ag == age_key, "_mrn_k"])

    def pews_cell(mrns: set[object]) -> str:
        if vitals_note:
            return vitals_note
        nd = len(mrns)
        if nd == 0:
            return "—"
        if not gcs_col:
            return "— (missing GCS)"
        return fmt_n_pct(len(mrns & ready_mrns), nd)

    def miss_cell(mrns: set[object], vital_label: str) -> str:
        if vitals_note:
            return vitals_note
        nd = len(mrns)
        if nd == 0:
            return "—"
        return fmt_n_pct(len(mrns - present[vital_label]), nd)

    rows: list[dict[str, str]] = [
        {
            "Measure": "Complete PEWS data",
            **{label: pews_cell(patient_set(key)) for label, key in _COMPLETENESS_AGE_COLS},
        },
        {
            "Measure": "Timing data",
            **{label: timing_cell(journeys_for(key)) for label, key in _COMPLETENESS_AGE_COLS},
        },
        {"Measure": "Vital Signs Missing", **{label: "" for label in col_names}},
    ]
    for vital_label in _COMPLETENESS_VITAL_LABELS:
        rows.append(
            {
                "Measure": f"  {vital_label}",
                **{
                    label: miss_cell(patient_set(key), vital_label)
                    for label, key in _COMPLETENESS_AGE_COLS
                },
            }
        )
    return pd.DataFrame(rows)


def build_table2_2_vitals_repeated(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2.2: n(%) of cohort patients with >1 value for each vital at village visit.
    For BP, count repeated paired sets where systolic and diastolic are both present.
    """
    first = _first_cohort_patients(df)
    n_pat = len(first)
    if n_pat == 0:
        return pd.DataFrame([{"Vital": "—", "Patients with >1 value n(%)": "—"}])
    vit, cm, err = _load_vitals_for_cohort()
    if err is not None or vit is None or cm is None:
        return pd.DataFrame(
            [{"Vital": "Note", "Patients with >1 value n(%)": f"Unable to compute ({err})"}]
        )

    cohort_mrns = set(first["_mrn_k"])
    vit = vit[vit["_mrn_k"].isin(cohort_mrns)].copy()

    def repeated_count(col: str) -> int:
        p = _value_present_series(vit[col]).astype(int)
        c = vit.assign(_p=p).groupby("_mrn_k", dropna=False)["_p"].sum()
        return int((c > 1).sum())

    # BP repeated paired rows (both systolic + diastolic present)
    bp_paired = (_value_present_series(vit[cm["bp_sys"]]) & _value_present_series(vit[cm["bp_dia"]])).astype(int)
    bp_counts = vit.assign(_bp=bp_paired).groupby("_mrn_k", dropna=False)["_bp"].sum()
    bp_rep = int((bp_counts > 1).sum())

    rows = [
        {"Vital": "HR", "Patients with >1 value n(%)": fmt_n_pct(repeated_count(cm["hr"]), n_pat)},
        {"Vital": "O2 sat", "Patients with >1 value n(%)": fmt_n_pct(repeated_count(cm["o2"]), n_pat)},
        {"Vital": "BP (paired systolic+diastolic)", "Patients with >1 value n(%)": fmt_n_pct(bp_rep, n_pat)},
        {"Vital": "RR", "Patients with >1 value n(%)": fmt_n_pct(repeated_count(cm["rr"]), n_pat)},
        {"Vital": "Temp", "Patients with >1 value n(%)": fmt_n_pct(repeated_count(cm["temp"]), n_pat)},
    ]
    return pd.DataFrame(rows)


def _vital_present_sets(vit: pd.DataFrame, cm: dict[str, str]) -> dict[str, set[object]]:
    """Patient sets with at least one value for each vital."""
    def _has_any(col: str) -> set[object]:
        p = _value_present_series(vit[col])
        return set(vit.loc[p, "_mrn_k"])

    p_sys = _value_present_series(vit[cm["bp_sys"]])
    p_dia = _value_present_series(vit[cm["bp_dia"]])
    return {
        "HR": _has_any(cm["hr"]),
        "O2 sat": _has_any(cm["o2"]),
        "BP (systolic+diastolic)": set(vit.loc[p_sys & p_dia, "_mrn_k"]),
        "RR": _has_any(cm["rr"]),
        "Temp": _has_any(cm["temp"]),
    }


def _vital_repeated_sets(vit: pd.DataFrame, cm: dict[str, str]) -> dict[str, set[object]]:
    """Patient sets with >1 value for each vital."""
    def _rep(col: str) -> set[object]:
        p = _value_present_series(vit[col]).astype(int)
        c = vit.assign(_p=p).groupby("_mrn_k", dropna=False)["_p"].sum()
        return set(c[c > 1].index)

    bp_paired = (_value_present_series(vit[cm["bp_sys"]]) & _value_present_series(vit[cm["bp_dia"]])).astype(int)
    bp_counts = vit.assign(_bp=bp_paired).groupby("_mrn_k", dropna=False)["_bp"].sum()
    bp_rep = set(bp_counts[bp_counts > 1].index)
    return {
        "HR": _rep(cm["hr"]),
        "O2 sat": _rep(cm["o2"]),
        "BP (paired systolic+diastolic)": bp_rep,
        "RR": _rep(cm["rr"]),
        "Temp": _rep(cm["temp"]),
    }


def build_table2_3_vitals_missingness_by_age(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2.3: patient-level missingness by vital, stratified by age group.
    """
    first = _first_cohort_patients(df)
    if len(first) == 0:
        return pd.DataFrame([{"Group": "—", "Missing n(%)": "—"}])
    vit, cm, err = _load_vitals_for_cohort()
    if err is not None or vit is None or cm is None:
        return pd.DataFrame([{"Group": "Note", "Missing n(%)": f"Unable to compute ({err})"}])

    cohort_mrns = set(first["_mrn_k"])
    vit = vit[vit["_mrn_k"].isin(cohort_mrns)].copy()
    present = _vital_present_sets(vit, cm)

    age = pd.to_numeric(first["age_at_medevac"], errors="coerce")
    ag = age.map(_age_bucket_key)
    rows: list[dict[str, str]] = []
    age_labels = [
        ("<1 year", "b0"),
        ("1 to <5 years", "b1"),
        ("5–12 years", "b2"),
        ("13–18 years", "b3"),
    ]
    for label, key in age_labels:
        sub_mrns = set(first.loc[ag == key, "_mrn_k"])
        nd = len(sub_mrns)
        if nd == 0:
            continue
        rows.append({"Group": f"{label} (N={nd})", "Missing n(%)": ""})
        for vital_label in ("HR", "O2 sat", "BP (systolic+diastolic)", "RR", "Temp"):
            n_miss = int(len(sub_mrns - present[vital_label]))
            rows.append({"Group": f"  {vital_label}", "Missing n(%)": fmt_n_pct(n_miss, nd)})
    sub_other = set(first.loc[ag.isna() | (ag == "other"), "_mrn_k"])
    if len(sub_other) > 0:
        nd = len(sub_other)
        rows.append({"Group": f"Age missing or >18 y (N={nd})", "Missing n(%)": ""})
        for vital_label in ("HR", "O2 sat", "BP (systolic+diastolic)", "RR", "Temp"):
            n_miss = int(len(sub_other - present[vital_label]))
            rows.append({"Group": f"  {vital_label}", "Missing n(%)": fmt_n_pct(n_miss, nd)})
    return pd.DataFrame(rows)


def build_table2_4_vitals_repeated_by_age(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 2.4: patient-level repeated-vitals (>1 value) by measure, stratified by age group.
    """
    first = _first_cohort_patients(df)
    if len(first) == 0:
        return pd.DataFrame([{"Group": "—", "Patients with >1 value n(%)": "—"}])
    vit, cm, err = _load_vitals_for_cohort()
    if err is not None or vit is None or cm is None:
        return pd.DataFrame(
            [{"Group": "Note", "Patients with >1 value n(%)": f"Unable to compute ({err})"}]
        )

    cohort_mrns = set(first["_mrn_k"])
    vit = vit[vit["_mrn_k"].isin(cohort_mrns)].copy()
    repeated = _vital_repeated_sets(vit, cm)

    age = pd.to_numeric(first["age_at_medevac"], errors="coerce")
    ag = age.map(_age_bucket_key)
    rows: list[dict[str, str]] = []
    age_labels = [
        ("<1 year", "b0"),
        ("1 to <5 years", "b1"),
        ("5–12 years", "b2"),
        ("13–18 years", "b3"),
    ]
    for label, key in age_labels:
        sub_mrns = set(first.loc[ag == key, "_mrn_k"])
        nd = len(sub_mrns)
        if nd == 0:
            continue
        rows.append({"Group": f"{label} (N={nd})", "Patients with >1 value n(%)": ""})
        for vital_label in ("HR", "O2 sat", "BP (paired systolic+diastolic)", "RR", "Temp"):
            n_rep = int(len(sub_mrns & repeated[vital_label]))
            rows.append(
                {"Group": f"  {vital_label}", "Patients with >1 value n(%)": fmt_n_pct(n_rep, nd)}
            )
    sub_other = set(first.loc[ag.isna() | (ag == "other"), "_mrn_k"])
    if len(sub_other) > 0:
        nd = len(sub_other)
        rows.append({"Group": f"Age missing or >18 y (N={nd})", "Patients with >1 value n(%)": ""})
        for vital_label in ("HR", "O2 sat", "BP (paired systolic+diastolic)", "RR", "Temp"):
            n_rep = int(len(sub_other & repeated[vital_label]))
            rows.append(
                {"Group": f"  {vital_label}", "Patients with >1 value n(%)": fmt_n_pct(n_rep, nd)}
            )
    return pd.DataFrame(rows)


def build_table3_pews_data_availability_by_age(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table 3: proportion of patients with data needed to calculate PEWS proxy,
    stratified by age group.

    A patient is counted as "has PEWS-required data" if they have >=1 village-vitals
    row with non-missing RR, HR, SBP, Temp, and GCS.
    """
    first = _first_cohort_patients(df)
    if len(first) == 0:
        return pd.DataFrame(
            [{"Age Group": "—", "Patients (N)": "0", "With PEWS-required data n(%)": "—"}]
        )

    vit, cm, err = _load_vitals_for_cohort()
    if vit is None or cm is None:
        note = "— (no vitals file)" if err == "no vitals file" else "— (missing vital columns)"
        return pd.DataFrame(
            [{"Age Group": "All patients", "Patients (N)": str(len(first)), "With PEWS-required data n(%)": note}]
        )

    gcs_col = _pick_vitals_col(vit, _GCS_ALIASES)
    if not gcs_col:
        return pd.DataFrame(
            [
                {
                    "Age Group": "All patients",
                    "Patients (N)": str(len(first)),
                    "With PEWS-required data n(%)": "— (missing GCS column)",
                }
            ]
        )

    in_cohort = set(first["_mrn_k"].tolist())
    sub = vit[vit["_mrn_k"].isin(in_cohort)].copy()
    sub["_pews_ready"] = sub.apply(lambda r: _pews_proxy_score_row(r, cm, gcs_col) is not None, axis=1)
    ready_mrns = set(sub.loc[sub["_pews_ready"], "_mrn_k"])

    rows: list[dict[str, str]] = []
    n_all = len(in_cohort)
    n_ready_all = int(len(in_cohort & ready_mrns))
    rows.append(
        {
            "Age Group": "All patients",
            "Patients (N)": str(n_all),
            "With PEWS-required data n(%)": fmt_n_pct(n_ready_all, n_all),
        }
    )

    age = pd.to_numeric(first["age_at_medevac"], errors="coerce")
    ag = age.map(_age_bucket_key)
    for label, key in (("<1 year", "b0"), ("1 to <5 years", "b1"), ("5–12 years", "b2"), ("13–18 years", "b3")):
        sub_mrns = set(first.loc[ag == key, "_mrn_k"])
        nd = len(sub_mrns)
        n_ready = int(len(sub_mrns & ready_mrns))
        rows.append(
            {
                "Age Group": label,
                "Patients (N)": str(nd),
                "With PEWS-required data n(%)": fmt_n_pct(n_ready, nd) if nd > 0 else "—",
            }
        )
    return pd.DataFrame(rows)


def _format_cedis_code(x: object) -> object:
    """Normalize numeric-like CEDIS codes (e.g., 888.0 -> 888)."""
    if pd.isna(x):
        return pd.NA
    s = str(x).strip()
    if not s:
        return pd.NA
    try:
        f = float(s)
        if f.is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


def _has_value(x: object) -> bool:
    if pd.isna(x):
        return False
    return str(x).strip() != ""


def _first_cc_triplet(row: pd.Series, prefix: str, start: int, end: int) -> tuple[object, object, object] | None:
    """
    Return first non-empty CC triplet (text, cedis_code, cedis_complaint)
    for the given prefix and index range, preferring slots with code present.
    """
    for i in range(start, end + 1):
        txt_col = f"{prefix}_cc_{i}"
        code_col = f"{prefix}_cedis_code_{i}"
        cmp_col = f"{prefix}_cedis_complaint_{i}"
        txt = row[txt_col] if txt_col in row.index else pd.NA
        code = row[code_col] if code_col in row.index else pd.NA
        cmpv = row[cmp_col] if cmp_col in row.index else pd.NA
        if _has_value(code):
            return txt, _format_cedis_code(code), cmpv
    for i in range(start, end + 1):
        txt_col = f"{prefix}_cc_{i}"
        code_col = f"{prefix}_cedis_code_{i}"
        cmp_col = f"{prefix}_cedis_complaint_{i}"
        txt = row[txt_col] if txt_col in row.index else pd.NA
        code = row[code_col] if code_col in row.index else pd.NA
        cmpv = row[cmp_col] if cmp_col in row.index else pd.NA
        if _has_value(txt) or _has_value(cmpv):
            return txt, _format_cedis_code(code), cmpv
    return None


def _all_cc_triplets(row: pd.Series, prefix: str, start: int, end: int) -> list[tuple[int, object, object, object]]:
    """
    Return all non-empty CC triplets (slot, text, cedis_code, cedis_complaint)
    for a location prefix, in slot order.
    """
    out: list[tuple[int, object, object, object]] = []
    for i in range(start, end + 1):
        txt_col = f"{prefix}_cc_{i}"
        code_col = f"{prefix}_cedis_code_{i}"
        cmp_col = f"{prefix}_cedis_complaint_{i}"
        txt = row[txt_col] if txt_col in row.index else pd.NA
        code = row[code_col] if code_col in row.index else pd.NA
        cmpv = row[cmp_col] if cmp_col in row.index else pd.NA
        if _has_value(txt) or _has_value(code) or _has_value(cmpv):
            out.append((i, txt, _format_cedis_code(code), cmpv))
    return out


def _location_anchor_times(jrow: pd.Series) -> dict[str, pd.Timestamp]:
    """
    Best-effort per-location anchor times from facility_#_name/facility_#_time.
    """
    names: list[str] = []
    times: list[pd.Timestamp] = []
    for i in range(1, 5):
        n = str(jrow.get(f"facility_{i}_name", "")).strip()
        t = pd.to_datetime(jrow.get(f"facility_{i}_time", pd.NA), errors="coerce")
        names.append(n)
        times.append(t)

    def _first_idx(pred) -> int | None:
        for k, n in enumerate(names):
            if n and pred(n):
                return k
        return None

    village_i = _first_idx(lambda n: is_village_medevac_origin(n))
    mhc_i = _first_idx(lambda n: _is_mhc_cah_destination(n))
    anmc_i = _first_idx(lambda n: ("anmc" in n.lower()) or n.startswith("Hub") or n == "Hub_01")
    return {
        "village": times[village_i] if village_i is not None else pd.NaT,
        "mhc_ed": times[mhc_i] if mhc_i is not None else pd.NaT,
        "mhc_inpatient": times[mhc_i] if mhc_i is not None else pd.NaT,
        "anmc_ed": times[anmc_i] if anmc_i is not None else pd.NaT,
    }


def build_table4_6_expanded_followup_cc_review(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expanded review table for village follow-up CEDIS 888 journeys.

    Includes ALL documented chief complaint rows in journey order across:
      village, mhc_ed, mhc_inpatient, anmc_ed.
    Adds per-event delta time from previous complaint (hours; when timestamps
    are available), and journey-level expanded follow-up target:
      first non-888/999 CEDIS code in event order.
    """
    if not CHIEF_COMPLAINTS_WIDE.is_file():
        return pd.DataFrame(
            [
                {
                    "journey_id": "—",
                    "MRN": "—",
                    "cc_location": "—",
                    "cc_text": "Chief complaint file missing",
                    "cc_cedis_code": "—",
                    "cc_cedis_complaint": "—",
                    "hours_since_previous_cc": "—",
                    "expanded_cc_code": "—",
                    "expanded_cc_complaint": "—",
                    "expanded_cc_fu": "No",
                }
            ]
        )

    cohort_ids = set(df["journey_id"].astype(str))
    cc = pd.read_csv(CHIEF_COMPLAINTS_WIDE, low_memory=False)
    cc = cc[cc["journey_id"].astype(str).isin(cohort_ids)].copy()

    juniq = df.drop_duplicates("journey_id").copy()
    juniq["_jid"] = juniq["journey_id"].astype(str)
    journey_lookup = juniq.set_index("_jid", drop=False).to_dict(orient="index")

    out_rows: list[dict[str, object]] = []
    for _, r in cc.iterrows():
        jid = str(r.get("journey_id", "")).strip()
        if not jid:
            continue
        village = _first_cc_triplet(r, "village", 1, 19)
        if village is None:
            continue
        v_txt, v_code, v_cmp = village
        v_code_s = "" if pd.isna(v_code) else str(v_code).strip()
        if v_code_s != "888":
            continue

        events: list[dict[str, object]] = []
        for loc, prefix, nmax, loc_rank in (
            ("village", "village", 19, 1),
            ("mhc_ed", "mhc_ed", 8, 2),
            ("mhc_inpatient", "mhc_inpatient", 5, 3),
            ("anmc_ed", "anmc_ed", 2, 4),
        ):
            for slot, txt, code, cmpv in _all_cc_triplets(r, prefix, 1, nmax):
                events.append(
                    {
                        "loc_rank": loc_rank,
                        "slot": slot,
                        "cc_location": loc,
                        "cc_text": txt,
                        "cc_cedis_code": code,
                        "cc_cedis_complaint": cmpv,
                    }
                )
        if not events:
            continue
        events.sort(key=lambda x: (int(x["loc_rank"]), int(x["slot"])))

        expanded_code = v_code
        expanded_cmp = v_cmp
        for e in events:
            c = e["cc_cedis_code"]
            cs = "" if pd.isna(c) else str(c).strip()
            if cs and cs not in {"888", "999"}:
                expanded_code = c
                expanded_cmp = e["cc_cedis_complaint"] if _has_value(e["cc_cedis_complaint"]) else expanded_cmp
                break
        expanded_fu = "Yes" if str(expanded_code).strip() != "888" else "No"

        jrow = journey_lookup.get(jid, {})
        anchors = _location_anchor_times(pd.Series(jrow)) if jrow else {}
        prev_time = pd.NaT
        for idx, e in enumerate(events, start=1):
            et = anchors.get(str(e["cc_location"]), pd.NaT) if anchors else pd.NaT
            if pd.notna(prev_time) and pd.notna(et):
                delta_h = (et - prev_time).total_seconds() / 3600.0
                delta_h = round(float(delta_h), 2)
            else:
                delta_h = pd.NA
            out_rows.append(
                {
                    "journey_id": jid,
                    "MRN": r.get("MRN", pd.NA),
                    "cc_sequence": idx,
                    "cc_location": e["cc_location"],
                    "cc_text": e["cc_text"],
                    "cc_cedis_code": e["cc_cedis_code"],
                    "cc_cedis_complaint": e["cc_cedis_complaint"],
                    "hours_since_previous_cc": delta_h,
                    "expanded_cc_code": expanded_code,
                    "expanded_cc_complaint": expanded_cmp,
                    "expanded_cc_fu": expanded_fu,
                }
            )
            if pd.notna(et):
                prev_time = et
    if not out_rows:
        return pd.DataFrame(
            [
                {
                    "journey_id": "—",
                    "MRN": "—",
                    "cc_sequence": 1,
                    "cc_location": "—",
                    "cc_text": "No village CEDIS 888 rows in cohort",
                    "cc_cedis_code": "—",
                    "cc_cedis_complaint": "—",
                    "hours_since_previous_cc": "—",
                    "expanded_cc_code": "—",
                    "expanded_cc_complaint": "—",
                    "expanded_cc_fu": "No",
                }
            ]
        )
    out = pd.DataFrame(out_rows)
    return out.sort_values(["expanded_cc_fu", "journey_id", "cc_sequence"], ascending=[False, True, True]).reset_index(drop=True)


_SKIP_CC = frozenset({"follow-up visit", "unknown"})

# Official CEDIS code → major category lookup (codes 888/999 excluded as non-clinical)
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


def _definitive_cc_per_journey(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per cohort journey: age bucket + cc_definitive.

    cc_definitive = first non-'Follow-up visit' / non-'Unknown' CEDIS complaint
    found by scanning slots in this order across the full journey:
      village_cedis_complaint_1..19
      mhc_ed_cedis_complaint_1..8
      mhc_inpatient_cedis_complaint_1..5
      anmc_ed_cedis_complaint_1..2

    If every slot is empty, follow-up, or unknown → "Undefined".
    """
    base = df.drop_duplicates("journey_id")[["journey_id", "age_at_medevac"]].copy()
    base["age_years"]   = pd.to_numeric(base["age_at_medevac"], errors="coerce")
    base["age_bucket"]  = base["age_years"].map(_age_bucket_key)
    base["cc_definitive"] = "Undefined"

    if not CHIEF_COMPLAINTS_WIDE.is_file():
        return base

    cc = pd.read_csv(CHIEF_COMPLAINTS_WIDE, low_memory=False)
    cc["journey_id"] = cc["journey_id"].astype(str).str.strip()
    jids = set(base["journey_id"].astype(str).str.strip())
    sub = cc[cc["journey_id"].isin(jids)].drop_duplicates("journey_id").copy()
    if sub.empty:
        return base

    # Ordered list of complaint columns to scan across locations
    _SEARCH_ORDER = (
        [f"village_cedis_complaint_{i}"        for i in range(1, 20)] +
        [f"mhc_ed_cedis_complaint_{i}"         for i in range(1, 9)]  +
        [f"mhc_inpatient_cedis_complaint_{i}"  for i in range(1, 6)]  +
        [f"anmc_ed_cedis_complaint_{i}"        for i in range(1, 3)]
    )
    avail_cols = [c for c in _SEARCH_ORDER if c in sub.columns]

    # Build parallel lists of code columns in the same search order
    _SEARCH_ORDER_CODES = (
        [f"village_cedis_code_{i}"        for i in range(1, 20)] +
        [f"mhc_ed_cedis_code_{i}"         for i in range(1, 9)]  +
        [f"mhc_inpatient_cedis_code_{i}"  for i in range(1, 6)]  +
        [f"anmc_ed_cedis_code_{i}"        for i in range(1, 3)]
    )
    avail_code_cols = [c for c in _SEARCH_ORDER_CODES if c in sub.columns]
    # Align code columns to complaint columns by index
    col_pairs = [(c, k) for c, k in zip(avail_cols, avail_code_cols)
                 if c in sub.columns and k in sub.columns]

    def _first_definitive(row: pd.Series) -> tuple[str, str, str]:
        """Returns (complaint_text, cedis_code_str, category)."""
        for comp_col, code_col in col_pairs:
            val = row[comp_col]
            if pd.isna(val):
                continue
            s = str(val).strip()
            if s and s.lower() not in _SKIP_CC:
                raw_code = row[code_col]
                try:
                    code_int = int(float(raw_code))
                    code_str = str(code_int)
                    category = _CEDIS_CATEGORY_MAP.get(code_int, "General and Minor")
                except (ValueError, TypeError):
                    code_str = ""
                    category = "General and Minor"
                return s, code_str, category
        return "Undefined", "", "Undefined"

    results = sub[
        [c for pair in col_pairs for c in pair]
    ].apply(_first_definitive, axis=1)
    sub = sub.copy()
    sub["_def_complaint"] = [r[0] for r in results]
    sub["_def_code"]      = [r[1] for r in results]
    sub["_def_category"]  = [r[2] for r in results]

    js = base["journey_id"].astype(str).str.strip()
    id_map = sub.set_index(sub["journey_id"].astype(str))
    base["cc_definitive"]          = js.map(id_map["_def_complaint"]).fillna("Undefined")
    base["cc_definitive_code"]     = js.map(id_map["_def_code"]).fillna("")
    base["cc_definitive_category"] = js.map(id_map["_def_category"]).fillna("Undefined")

    # Custom grouping: collapse Respiratory, GI, Trauma/Orthopedic;
    # keep every other complaint at individual level.
    # Complaint-level overrides take priority over category rules.
    _GROUPED_CATS = {
        "Respiratory":      "Respiratory",
        "Gastrointestinal": "Gastrointestinal",
        "Trauma":           "Trauma/Injury",
        "Orthopedic":       "Trauma/Injury",
    }
    _GROUPED_COMPLAINTS = {
        "Head injury":      "Trauma/Injury",
        "Facial trauma":    "Trauma/Injury",
        "Neck trauma":      "Trauma/Injury",
        "Genital trauma":   "Trauma/Injury",
        "Eye trauma":       "Trauma/Injury",
        "URTI complaints":  "Respiratory",
    }

    def _custom_group(row: pd.Series) -> str:
        complaint = row["cc_definitive"]
        if complaint == "Undefined":
            return "Undefined"
        if complaint in _GROUPED_COMPLAINTS:
            return _GROUPED_COMPLAINTS[complaint]
        return _GROUPED_CATS.get(row["cc_definitive_category"], complaint)

    base["cc_definitive_custom_grouping"] = base.apply(_custom_group, axis=1)
    return base


def _chief_complaint_per_journey(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per cohort journey: age bucket + primary village CEDIS code/complaint.

    Source: data/pediatric_chiefcomplaints.csv (village_cedis_code_1..19 and
    village_cedis_complaint_1..19). For each journey, use the first non-missing
    village CEDIS code/complaint in slot order.
    """
    base = df.drop_duplicates("journey_id")[
        ["journey_id", "age_at_medevac"]
    ].copy()
    base["age_years"] = pd.to_numeric(base["age_at_medevac"], errors="coerce")
    base["age_bucket"] = base["age_years"].map(_age_bucket_key)
    base["cedis_code"] = pd.NA
    base["cedis_complaint"] = pd.NA
    if not CHIEF_COMPLAINTS_WIDE.is_file():
        return base
    jids = set(base["journey_id"].astype(str).str.strip())
    cc = pd.read_csv(CHIEF_COMPLAINTS_WIDE, low_memory=False)
    cc["journey_id"] = cc["journey_id"].astype(str).str.strip()
    sub = cc[cc["journey_id"].isin(jids)].drop_duplicates(subset=["journey_id"]).copy()
    if sub.empty:
        return base
    code_cols = [f"village_cedis_code_{i}" for i in range(1, 20) if f"village_cedis_code_{i}" in sub.columns]
    complaint_cols = [
        f"village_cedis_complaint_{i}"
        for i in range(1, 20)
        if f"village_cedis_complaint_{i}" in sub.columns
    ]
    if not code_cols or not complaint_cols:
        return base
    first_code = sub[code_cols].bfill(axis=1).iloc[:, 0].map(_format_cedis_code)
    first_complaint = sub[complaint_cols].bfill(axis=1).iloc[:, 0]
    first_complaint = first_complaint.map(lambda x: pd.NA if pd.isna(x) or not str(x).strip() else str(x).strip())
    first = sub[["journey_id"]].copy()
    first["cedis_code"] = first_code
    first["cedis_complaint"] = first_complaint
    m_code = dict(zip(first["journey_id"].astype(str), first["cedis_code"], strict=True))
    m_complaint = dict(zip(first["journey_id"].astype(str), first["cedis_complaint"], strict=True))
    js = base["journey_id"].astype(str).str.strip()
    base["cedis_code"] = js.map(m_code)
    base["cedis_complaint"] = js.map(m_complaint)
    return base


def _top10_chief_complaints(cc_df: pd.DataFrame, denominator_journeys: int) -> pd.DataFrame:
    """Top 10 CEDIS complaints; output rank, Chief Complaint, n(%)."""
    valid = cc_df[
        cc_df["cedis_code"].notna()
        & (cc_df["cedis_code"].astype(str).str.strip() != "")
        & cc_df["cedis_complaint"].notna()
        & (cc_df["cedis_complaint"].astype(str).str.strip() != "")
    ]
    if denominator_journeys <= 0:
        return pd.DataFrame(
            [
                {
                    "rank": "—",
                    "Chief Complaint": "No journeys in subset",
                    "n(%)": "—",
                }
            ]
        )
    if valid.empty:
        msg = (
            "No village CEDIS code/complaint in this subset"
            if CHIEF_COMPLAINTS_WIDE.is_file()
            else f"Add {CHIEF_COMPLAINTS_WIDE.name}"
        )
        return pd.DataFrame(
            [
                {
                    "rank": "—",
                    "Chief Complaint": msg,
                    "n(%)": "0 (0.0%)",
                }
            ]
        )
    top = (
        valid.groupby(["cedis_code", "cedis_complaint"], dropna=False)
        .size()
        .reset_index(name="n")
        .sort_values(["n", "cedis_code", "cedis_complaint"], ascending=[False, True, True])
        .head(10)
    )
    rows = []
    for i, r in enumerate(top.itertuples(index=False), 1):
        n = int(r.n)
        rows.append(
            {
                "rank": i,
                "Chief Complaint": str(r.cedis_complaint),
                "n(%)": fmt_n_pct(n, denominator_journeys),
            }
        )
    return pd.DataFrame(rows)


def build_table3_route_comparison(df_all: pd.DataFrame) -> pd.DataFrame:
    """
    Table 3: Patient characteristics by transport route type.

    Route groups (columns):
      Primary only   — village → MHC, no secondary transfer
      Secondary      — village → MHC → ANMC or outside facility
      Direct tertiary— village → ANMC/outside (bypasses MHC)

    Rows: Age (median IQR), Age group (%), Chief Complaint top 10 (%)
    Extra column: p-value (Kruskal-Wallis for continuous; chi-square for categorical)
    """
    from scipy import stats as _stats

    j = df_all.drop_duplicates("journey_id").copy()

    # Keep only village-originating journeys (facility_1 = village clinic)
    _vmask = j["facility_1_name"].apply(lambda x: is_village_medevac_origin(str(x or "")))
    j = j[_vmask].copy()

    # Classify using facility_1/2/3 columns directly:
    #   Primary      : loc1=village, loc2=MHC, loc3=null
    #   Secondary    : loc1=village, loc2=MHC, loc3=non-null (ANMC/outside)
    #   Direct tertiary: loc1=village, loc2≠MHC
    def _route_from_legs(row: pd.Series) -> str:
        # Use the actual medevac leg destinations (not facility sequence) so that
        # journeys where MHC appears as a facility encounter but the medevac flew
        # directly to ANMC are correctly classified as Direct tertiary.
        m1to_raw = row.get("medevac1_to")
        m2to_raw = row.get("medevac2_to")
        m1to = "" if pd.isna(m1to_raw) else str(m1to_raw).strip()
        m2to = "" if pd.isna(m2to_raw) else str(m2to_raw).strip()
        if _is_mhc_cah_destination(m1to):
            return "Secondary" if m2to else "Primary only"
        return "Direct tertiary"

    j["_grp"] = j.apply(_route_from_legs, axis=1)
    groups_order = ["Primary only", "Secondary", "Direct tertiary"]
    grp_data = {g: j[j["_grp"] == g] for g in groups_order}
    ns = {g: len(v) for g, v in grp_data.items()}

    # Column headers with n=
    col_labels = [f"{g}\n(n={ns[g]})" for g in groups_order]
    all_cols = ["Metric"] + col_labels + ["p"]

    rows: list[list] = []

    # ── Age (continuous) ──────────────────────────────────────────────────────
    age_series = {g: pd.to_numeric(grp_data[g]["age_at_medevac"], errors="coerce").dropna()
                  for g in groups_order}

    def _med_iqr(s: pd.Series) -> str:
        if s.empty: return "—"
        return f"{s.median():.1f} ({s.quantile(0.25):.1f}–{s.quantile(0.75):.1f})"

    _age_nonempty = [age_series[g] for g in groups_order if len(age_series[g]) > 0]
    try:
        kw = _stats.kruskal(*_age_nonempty) if len(_age_nonempty) >= 2 else None
        kw_p = (f"{kw.pvalue:.3f}" if kw.pvalue >= 0.001 else "<0.001") if kw else "—"
    except Exception:
        kw_p = "—"
    rows.append(
        ["Age, years — Median (IQR)"]
        + [_med_iqr(age_series[g]) for g in groups_order]
        + [kw_p]
    )

    # ── Age group (%) ─────────────────────────────────────────────────────────
    AGE_GROUPS = [("<1 year","b0"),("1 to <5 years","b1"),("5–12 years","b2"),("13–18 years","b3")]

    def _age_bucket(a):
        if pd.isna(a): return None
        if a < 1:   return "b0"
        if a < 5:   return "b1"
        if a < 13:  return "b2"
        if a <= 18: return "b3"
        return None

    for g in groups_order:
        grp_data[g] = grp_data[g].copy()
        grp_data[g]["_ab"] = pd.to_numeric(grp_data[g]["age_at_medevac"], errors="coerce").map(_age_bucket)

    # Chi-square on age group contingency table
    ct = pd.DataFrame(
        {g: grp_data[g]["_ab"].value_counts() for g in groups_order}
    ).fillna(0).reindex(["b0","b1","b2","b3"], fill_value=0)
    try:
        chi2_age, p_age, *_ = _stats.chi2_contingency(ct.values)
        p_age_str = f"{p_age:.3f}" if p_age >= 0.001 else "<0.001"
    except Exception:
        p_age_str = "—"

    rows.append(["Age group, n (%)"] + [""] * len(groups_order) + [p_age_str])
    for lbl, bk in AGE_GROUPS:
        cells = [fmt_pct_n(int((grp_data[g]["_ab"] == bk).sum()), ns[g]) for g in groups_order]
        rows.append([f"  {lbl}"] + cells + [""])

    # ── Chief Complaint (custom grouping, top 10) ─────────────────────────────
    cc_j = _definitive_cc_per_journey(df_all)
    cc_j = cc_j.merge(j[["journey_id","_grp"]], on="journey_id", how="inner")
    valid_cc = cc_j[cc_j["cc_definitive_custom_grouping"] != "Undefined"]

    top10_cc = (
        valid_cc.groupby("cc_definitive_custom_grouping")
        .size().sort_values(ascending=False).head(10).index.tolist()
    )

    # Chi-square across all top-10 categories
    ct_cc = pd.DataFrame(
        {g: valid_cc[valid_cc["_grp"] == g]["cc_definitive_custom_grouping"].value_counts()
         for g in groups_order}
    ).fillna(0).reindex(top10_cc, fill_value=0)
    try:
        _, p_cc, *_ = _stats.chi2_contingency(ct_cc.values)
        p_cc_str = f"{p_cc:.3f}" if p_cc >= 0.001 else "<0.001"
    except Exception:
        p_cc_str = "—"

    rows.append(["Chief Complaint (CEDIS), n (%)"] + [""] * len(groups_order) + [p_cc_str])
    for cc_grp in top10_cc:
        cells = [fmt_pct_n(
            int((valid_cc[valid_cc["_grp"] == g]["cc_definitive_custom_grouping"] == cc_grp).sum()),
            ns[g]
        ) for g in groups_order]
        rows.append([f"  {cc_grp}"] + cells + [""])

    out = pd.DataFrame(rows, columns=all_cols)
    out.to_csv(ROOT / "outputs" / "tables" / "table3_route_comparison.csv", index=False)
    return out


def build_table3_cedis_chief_complaints(
    df: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    """
    Table 3: Top-N CEDIS chief complaints by age group (wide format).

    Rows = top_n complaints ranked by overall frequency.
    Columns = Chief Complaint | Overall | <1 year | 1 to <5 years | 5–12 years | 13–18 years
    Each cell = n (%) where % is out of that column's journey total.

    Saved to outputs/tables/table3_cedis_chief_complaints.csv.
    """
    _BUCKETS = [
        ("Overall",        None),
        ("<1 year",        "b0"),
        ("1 to <5 years",  "b1"),
        ("5–12 years",     "b2"),
        ("13–18 years",    "b3"),
    ]

    cc = _chief_complaint_per_journey(df)
    valid = cc[
        cc["cedis_complaint"].notna()
        & (cc["cedis_complaint"].astype(str).str.strip() != "")
        & cc["cedis_code"].notna()
        & (cc["cedis_code"].astype(str).str.strip() != "")
    ].copy()

    # Determine top_n complaints by overall frequency
    top_complaints = (
        valid.groupby("cedis_complaint", dropna=False)
        .size()
        .sort_values(ascending=False)
        .head(top_n)
        .index.tolist()
    )

    def _cell(sub: pd.DataFrame, complaint: str, denom: int) -> str:
        n = int((sub["cedis_complaint"] == complaint).sum())
        if denom == 0:
            return "—"
        return fmt_n_pct(n, denom)

    rows = []
    for complaint in top_complaints:
        row = {"Chief Complaint (CEDIS)": complaint}
        for col_label, bucket in _BUCKETS:
            sub = valid if bucket is None else valid[valid["age_bucket"] == bucket]
            denom = len(cc) if bucket is None else int((cc["age_bucket"] == bucket).sum())
            row[col_label] = _cell(sub, complaint, denom)
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv(
        ROOT / "outputs" / "tables" / "table3_cedis_chief_complaints.csv", index=False
    )
    return out


def build_table3_chief_complaints_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Top 10 village CEDIS chief complaints across village→MHC journeys."""
    cc = _chief_complaint_per_journey(df)
    return _top10_chief_complaints(cc, len(cc))


def build_table3_chief_complaints_by_age(
    df: pd.DataFrame, bucket_key: str, age_label: str
) -> pd.DataFrame:
    """Tables 3.1–3.4: top 10 village CEDIS complaints within each age bucket."""
    cc = _chief_complaint_per_journey(df)
    sub = cc[cc["age_bucket"] == bucket_key]
    n = len(sub)
    if n == 0:
        return pd.DataFrame(
            [
                {
                    "rank": "—",
                    "Chief Complaint": f"No journeys ({age_label})",
                    "n(%)": "—",
                }
            ]
        )
    out = _top10_chief_complaints(sub, n)
    return out


def build_table3_followup_prior_visit_check(df: pd.DataFrame) -> pd.DataFrame:
    """
    Validation table: do Follow-up visit chief complaints have documented prior visits?

    Prior visit source: pediatric_missed_opportunities.csv with days_until_medevac > 0.
    """
    cc = _chief_complaint_per_journey(df).copy()
    if cc.empty:
        return pd.DataFrame(
            [
                {
                    "group": "No cohort journeys",
                    "journeys_n": 0,
                    "with_prior_visit_n": 0,
                    "with_prior_visit_pct": None,
                }
            ]
        )
    prior_j: set[str] = set()
    if MISSED_OPPORTUNITIES_CSV.is_file():
        mo = pd.read_csv(MISSED_OPPORTUNITIES_CSV, low_memory=False)
        mo["journey_id"] = mo["journey_id"].astype(str).str.strip()
        mo["days_until_medevac"] = pd.to_numeric(mo["days_until_medevac"], errors="coerce")
        cohort_j = set(cc["journey_id"].astype(str).str.strip())
        prior_j = set(
            mo.loc[
                mo["journey_id"].isin(cohort_j) & mo["days_until_medevac"].notna() & (mo["days_until_medevac"] > 0),
                "journey_id",
            ].astype(str)
        )

    cc["journey_id"] = cc["journey_id"].astype(str).str.strip()
    cmp = cc["cedis_complaint"].fillna("").astype(str).str.strip().str.lower()
    follow_mask = (cc["cedis_code"].astype(str) == "888") | (cmp == "follow-up visit")
    has_cedis = cc["cedis_code"].notna() & (cc["cedis_code"].astype(str).str.strip() != "")

    def _row(name: str, sub: pd.DataFrame) -> dict[str, object]:
        n = len(sub)
        w = int(sub["journey_id"].isin(prior_j).sum())
        return {
            "group": name,
            "journeys_n": n,
            "with_prior_visit_n": w,
            "with_prior_visit_pct": round(100 * w / n, 1) if n else None,
        }

    rows = [
        _row("Follow-up visit (CEDIS 888)", cc[follow_mask]),
        _row("All other chief complaints with CEDIS", cc[has_cedis & ~follow_mask]),
        _row("All cohort journeys", cc),
    ]
    return pd.DataFrame(rows)


# --- Table builders (return DataFrames for Quarto / CSV) ---


def build_table1_cohort(df: pd.DataFrame) -> pd.DataFrame:
    n_journeys = len(df)
    n_patients = df["MRN"].nunique()
    return pd.DataFrame(
        [
            {"metric": "Medevac journeys (rows)", "value": n_journeys},
            {"metric": "Unique patients", "value": n_patients},
            {
                "metric": "Journeys with multiple medevacs",
                "value": int((df["num_medevacs"] > 1).sum()),
            },
        ]
    )


def build_table2_by_origin(df: pd.DataFrame) -> pd.DataFrame:
    t = (
        df.groupby("origin_type", dropna=False)
        .agg(
            journeys=("journey_id", "count"),
            patients=("MRN", "nunique"),
            medevacs_mean=("num_medevacs", "mean"),
            journey_hours_median=("journey_duration_hours", "median"),
        )
        .reset_index()
    )
    t["medevacs_mean"] = t["medevacs_mean"].round(2)
    t["journey_hours_median"] = t["journey_hours_median"].round(1)
    return t


def build_table3_by_year(df: pd.DataFrame) -> pd.DataFrame:
    if "journey_start_year" not in df.columns and "medevac1_date" in df.columns:
        x = pd.to_datetime(df["medevac1_date"], errors="coerce").dt.year
        df = df.assign(journey_start_year=x)
    if "journey_start_year" not in df.columns:
        return pd.DataFrame([{"journey_start_year": "Missing", "journeys": len(df), "patients": df["MRN"].nunique()}])
    return (
        df.groupby("journey_start_year", dropna=False)
        .agg(journeys=("journey_id", "count"), patients=("MRN", "nunique"))
        .reset_index()
        .sort_values("journey_start_year")
    )


def build_timing_category_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    out = {}
    for col in ["decision_time_category", "flight_time_category", "flight_time_extended"]:
        if col not in df.columns:
            continue
        c = df[col].fillna("Missing")
        t = c.value_counts(dropna=False).rename_axis(col).reset_index(name="n")
        t["pct"] = (100 * t["n"] / len(df)).round(1)
        out[col] = t
    return out


def build_table5_timing_minutes(df: pd.DataFrame, village_cah_only: bool = True) -> pd.DataFrame:
    """
    Table 5: Time intervals for village → MHC primary transports.

    Three intervals reported:
      1. Village clinic arrival → medevac activation
         Source: time_to_activate_min (requires auth/decision record; lower N).
      2. Medevac activation → MHC arrival
         Source: activate_to_arrive_min.
      3. Village clinic arrival → MHC arrival (total, no activation needed)
         Source: destination_datetime − origin_datetime (highest N).

    Columns: Interval | N | Median (IQR) | Mean
    """
    sub = df.drop_duplicates(subset=["journey_id"]).copy()
    if village_cah_only and "origin_type" in sub.columns:
        sub = sub[sub["origin_type"] == "village_cah"]

    def _stats(s: pd.Series) -> dict:
        s = pd.to_numeric(s, errors="coerce").dropna()
        if len(s) == 0:
            return None
        return {
            "N": len(s),
            "Median (IQR)": (
                f"{s.median():.0f} ({s.quantile(0.25):.0f}–{s.quantile(0.75):.0f})"
            ),
            "Mean": f"{s.mean():.0f}",
        }

    # Interval 1 — village arrival → activation (from auth records)
    s1 = pd.to_numeric(sub.get("time_to_activate_min", pd.Series(dtype=float)),
                       errors="coerce")

    # Interval 2 — activation → MHC arrival (flight time)
    s2 = pd.to_numeric(sub.get("activate_to_arrive_min", pd.Series(dtype=float)),
                       errors="coerce")

    # Interval 3 — village arrival → MHC arrival (direct, highest N)
    _orig = pd.to_datetime(sub.get("origin_datetime"), errors="coerce")
    _dest = pd.to_datetime(sub.get("destination_datetime"), errors="coerce")
    s3 = (_dest - _orig).dt.total_seconds() / 60

    interval_defs = [
        ("Village clinic arrival → medevac activation (auth records; where available)", s1),
        ("Medevac activation → MHC arrival (flight time)", s2),
        ("Village clinic arrival → MHC arrival (total — origin + flight time)", s3),
    ]

    rows = []
    for label, s in interval_defs:
        st = _stats(s)
        if st is None:
            st = {"N": 0, "Median (IQR)": "—", "Mean": "—"}
        rows.append({"Time interval (minutes)": label, **st})

    return pd.DataFrame(rows)


def build_table6_mortality(df: pd.DataFrame) -> pd.DataFrame | None:
    if "24hr_mortality" not in df.columns:
        return None
    if len(df) == 0:
        return pd.DataFrame({"note": ["No journeys in cohort."]})
    t = pd.DataFrame(
        {
            "outcome": ["24hr_mortality", "7d_mortality", "30d_mortality"],
            "n_events": [
                int(df["24hr_mortality"].fillna(0).sum()),
                int(df["7d_mortality"].fillna(0).sum()),
                int(df["30d_mortality"].fillna(0).sum()),
            ],
        }
    )
    t["pct_of_journeys"] = (100 * t["n_events"] / len(df)).round(1)
    return t


# --- Figures (return Figure for Quarto; save via save_all_figures) ---


def plot_fig1_journeys_by_month(df: pd.DataFrame) -> plt.Figure:
    g = (
        df.groupby(["journey_start_year", "journey_start_month"], dropna=False)
        .size()
        .reset_index(name="n")
    )
    g["date"] = pd.to_datetime(
        dict(year=g["journey_start_year"], month=g["journey_start_month"], day=1)
    )
    g = g.sort_values("date")
    fig, ax = plt.subplots()
    ax.bar(g["date"], g["n"], width=20, color="steelblue", edgecolor="none")
    ax.set_xlabel("Month")
    ax.set_ylabel("Medevac journeys")
    ax.set_title("Medevac journeys by month")
    fig.autofmt_xdate()
    fig.tight_layout()
    return fig


def plot_fig2_origin_pie(df: pd.DataFrame) -> plt.Figure:
    counts = df["origin_type"].fillna("Missing").value_counts()
    fig, ax = plt.subplots()
    colors = sns.color_palette("Set2", n_colors=len(counts))
    ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%", colors=colors)
    ax.set_title("Journeys by origin type")
    fig.tight_layout()
    return fig


def plot_fig2_origin_bar(df: pd.DataFrame) -> plt.Figure:
    counts = df["origin_type"].fillna("Missing").value_counts()
    fig, ax = plt.subplots(figsize=(8, 5))
    bar_df = pd.DataFrame({"origin": counts.index, "n": counts.values})
    sns.barplot(data=bar_df, x="n", y="origin", hue="origin", ax=ax, palette="Set2", legend=False)
    ax.set_xlabel("Journeys")
    ax.set_ylabel("Origin type")
    ax.set_title("Medevac journeys by origin type")
    fig.tight_layout()
    return fig


def plot_fig3_journey_duration(df: pd.DataFrame) -> plt.Figure:
    sub = df["journey_duration_hours"].dropna()
    fig, ax = plt.subplots()
    ax.hist(sub.clip(upper=sub.quantile(0.99)), bins=40, color="coral", edgecolor="white")
    ax.set_xlabel("Journey duration (hours, capped at 99th pct for display)")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of journey duration")
    fig.tight_layout()
    return fig


def plot_fig4_activation_vs_arrival_village_cah(df: pd.DataFrame) -> plt.Figure | None:
    sub = df[df["origin_type"] == "village_cah"].copy()
    for c in ["medevac_minutes", "activate_to_arrive_min"]:
        if c not in sub.columns:
            return None
    sub["medevac_hr"] = pd.to_numeric(sub["medevac_minutes"], errors="coerce") / 60
    sub["activate_arrive_hr"] = pd.to_numeric(sub["activate_to_arrive_min"], errors="coerce") / 60
    plot_df = sub[["medevac_hr", "activate_arrive_hr"]].dropna()
    plot_df = plot_df[
        (plot_df["medevac_hr"] <= plot_df["medevac_hr"].quantile(0.98))
        & (plot_df["activate_arrive_hr"] <= plot_df["activate_arrive_hr"].quantile(0.98))
    ]
    fig, ax = plt.subplots()
    ax.scatter(
        plot_df["medevac_hr"],
        plot_df["activate_arrive_hr"],
        alpha=0.5,
        s=30,
        color="teal",
    )
    ax.set_xlabel("Time to medevac activation (hours)")
    ax.set_ylabel("Activation to arrival at Maniilaq Health Center (hours)")
    ax.set_title("Timing (village → Maniilaq Health Center)")
    fig.tight_layout()
    return fig


def plot_fig5_medevacs_per_journey(df: pd.DataFrame) -> plt.Figure:
    c = df["num_medevacs"].value_counts().sort_index()
    fig, ax = plt.subplots()
    ax.bar(c.index.astype(str), c.values, color="slategray", edgecolor="white")
    ax.set_xlabel("Number of medevacs in journey")
    ax.set_ylabel("Journeys")
    ax.set_title("Medevacs per journey")
    fig.tight_layout()
    return fig


def plot_fig1_medevac_activation_map(df: pd.DataFrame) -> plt.Figure:
    """NW Alaska map: village→MHC medevac legs (see manuscript Figure 1 style)."""
    from medevac_map_fig1 import plot_fig1_medevac_map

    j = df.drop_duplicates(subset=["journey_id"])
    infer = village_origin_mode() == "infer"
    vnames = None if infer else set(maniilaq_village_names())
    return plot_fig1_medevac_map(j, vnames, infer=infer)


def plot_fig_cdp_choropleth(df: pd.DataFrame) -> plt.Figure:
    """Choropleth map using actual Census Designated Place (CDP) polygon boundaries."""
    from medevac_map_fig1 import plot_fig_cdp_choropleth as _plot

    j = df.drop_duplicates(subset=["journey_id"])
    infer = village_origin_mode() == "infer"
    vnames = None if infer else set(maniilaq_village_names())
    return _plot(j, vnames, infer=infer)


def plot_fig_voronoi_service_districts(df: pd.DataFrame) -> plt.Figure:
    """
    Choropleth map: NW Arctic Borough divided into Voronoi service zones per
    village, colored by medevac utilization rate (legs per 1,000 residents).
    """
    from medevac_map_fig1 import plot_fig_voronoi_service_districts as _plot

    j = df.drop_duplicates(subset=["journey_id"])
    infer = village_origin_mode() == "infer"
    vnames = None if infer else set(maniilaq_village_names())
    return _plot(j, vnames, infer=infer)


def build_table_primary_transports_per_patient(df: pd.DataFrame) -> pd.DataFrame:
    """
    Table: distribution of village → MHC primary transport legs per unique patient.

    Returns a DataFrame with columns:
        Primary transports | n patients | % of patients
    Categories: 1, 2, 3+
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    leg_counts: dict[object, int] = {}
    for mrn, sub in j.groupby("MRN", dropna=False):
        n_legs = 0
        for _, r in sub.iterrows():
            for i in (1, 2, 3):
                fc, tc = f"medevac{i}_from", f"medevac{i}_to"
                if fc not in r.index or tc not in r.index:
                    continue
                if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                    continue
                a, b = str(r[fc]).strip(), str(r[tc]).strip()
                if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                    n_legs += 1
        if n_legs > 0:
            leg_counts[mrn] = n_legs

    if not leg_counts:
        return pd.DataFrame(
            columns=["Primary transports (village → MHC)", "n patients", "% of patients"]
        )

    counts = pd.Series(leg_counts)
    cats = counts.map(lambda n: "1" if n == 1 else ("2" if n == 2 else "3+"))
    total = len(counts)

    rows = []
    for cat in ("1", "2", "3+"):
        n = int((cats == cat).sum())
        rows.append({
            "Primary transports (village → MHC)": cat,
            "n patients": n,
            "% of patients": f"{100 * n / total:.1f}%" if total else "—",
        })
    rows.append({
        "Primary transports (village → MHC)": "Total",
        "n patients": total,
        "% of patients": "100.0%",
    })

    return pd.DataFrame(rows)


def plot_fig6_medevacs_per_patient(
    df: pd.DataFrame,
    start_year: int | None = None,
    end_year: int | None = None,
    title: str | None = None,
    village_to_mhc_only: bool = False,
) -> plt.Figure:
    """Histogram: medevac legs per patient (all legs or village→MHC only)."""
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    if (start_year is not None or end_year is not None) and "journey_start_year" not in j.columns:
        if "medevac1_date" in j.columns:
            j["journey_start_year"] = pd.to_datetime(j["medevac1_date"], errors="coerce").dt.year
    if "journey_start_year" in j.columns:
        y = pd.to_numeric(j["journey_start_year"], errors="coerce")
        if start_year is not None:
            j = j[y >= int(start_year)]
            y = pd.to_numeric(j["journey_start_year"], errors="coerce")
        if end_year is not None:
            j = j[y <= int(end_year)]
    if j.empty:
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.set_title(title or "Number of medevacs per patient")
        ax.text(0.5, 0.5, "No journeys in selected year range.", ha="center", va="center")
        fig.tight_layout()
        return fig
    if village_to_mhc_only:
        rows: list[dict[str, object]] = []
        for mrn, sub in j.groupby("MRN", dropna=False):
            n_legs = 0
            for _, r in sub.iterrows():
                for i in (1, 2, 3):
                    fc, tc = f"medevac{i}_from", f"medevac{i}_to"
                    if fc not in r.index or tc not in r.index:
                        continue
                    if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                        continue
                    a, b = str(r[fc]).strip(), str(r[tc]).strip()
                    if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                        n_legs += 1
            rows.append({"MRN": mrn, "medevac_legs": n_legs})
        per = pd.DataFrame(rows)
        x = per["medevac_legs"].astype(int)
    else:
        per = j.groupby("MRN", as_index=False)["num_medevacs"].sum()
        x = pd.to_numeric(per["num_medevacs"], errors="coerce").dropna().astype(int)
    if x.empty:
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.set_title(title or "Number of medevacs per patient")
        ax.text(0.5, 0.5, "No medevac counts available.", ha="center", va="center")
        fig.tight_layout()
        return fig
    if village_to_mhc_only:
        x = x[x > 0]
        if x.empty:
            fig, ax = plt.subplots()
            ax.axis("off")
            ax.set_title(title or "Number of medevacs per patient")
            ax.text(0.5, 0.5, "No village→MHC medevac legs in selected year range.", ha="center", va="center")
            fig.tight_layout()
            return fig
    xmax = int(x.max())
    fig, ax = plt.subplots()
    bins = range(1, xmax + 2)
    ax.hist(x, bins=bins, align="left", rwidth=0.85, color="steelblue", edgecolor="white")
    ax.set_xticks(range(1, xmax + 1))
    ax.set_xlabel("Total medevac legs per patient" if not village_to_mhc_only else "Village→MHC medevac legs per patient")
    ax.set_ylabel("Patients")
    if title is None:
        if start_year is not None and end_year is not None:
            ax.set_title(f"Number of Medevacs per Patient, {int(start_year)}-{int(end_year)}")
        else:
            ax.set_title("Distribution of medevacs per patient")
    else:
        ax.set_title(title)
    fig.tight_layout()
    return fig


def plot_fig7_journeys_per_patient(df: pd.DataFrame, title: str | None = None) -> plt.Figure:
    """Histogram: number of journeys per patient (distinct journey_id per MRN)."""
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    per = j.groupby("MRN", as_index=False)["journey_id"].nunique()
    x = pd.to_numeric(per["journey_id"], errors="coerce").dropna().astype(int)
    if x.empty:
        fig, ax = plt.subplots()
        ax.axis("off")
        ax.set_title(title or "Number of journeys per patient")
        ax.text(0.5, 0.5, "No journeys available.", ha="center", va="center")
        fig.tight_layout()
        return fig
    xmax = int(x.max())
    fig, ax = plt.subplots()
    bins = range(1, xmax + 2)
    ax.hist(x, bins=bins, align="left", rwidth=0.85, color="steelblue", edgecolor="white")
    ax.set_xticks(range(1, xmax + 1))
    ax.set_xlabel("Journeys per patient")
    ax.set_ylabel("Patients")
    ax.set_title(title or "Number of journeys per patient")
    fig.tight_layout()
    return fig


def build_p3_table1_disposition(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 3, Table 1: Disposition by route type.
    Rows = disposition categories; columns = Overall | Primary | Secondary | Direct Tertiary.
    Uses icu_admission, ed_discharge, short_<36h_admission, death_at_facility from outcomes.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["_route"] = j.apply(_classify_journey_route, axis=1)
    route_order = ["Primary (village → MHC)", "Secondary transfer", "Direct tertiary"]

    disp_cols = {
        "ED discharge":          "ed_discharge",
        "Short admission (<36h)": "short_<36h_admission",
        "ICU admission":         "icu_admission",
        "Surgery":               "had_surgery",
        "Death at facility":     "death_at_facility",
    }

    def _col_stats(sub: pd.DataFrame) -> list[str]:
        N = len(sub)
        out = [str(N)]
        for label, col in disp_cols.items():
            if col in sub.columns:
                n = int(pd.to_numeric(sub[col], errors="coerce").fillna(0).astype(bool).sum())
                out.append(fmt_n_pct(n, N))
            else:
                out.append("NR")
        return out

    metric_col = ["N journeys"] + list(disp_cols.keys())
    result = {"Disposition": metric_col, "Overall": _col_stats(j)}
    for route in route_order:
        result[route] = _col_stats(j[j["_route"] == route])

    out = pd.DataFrame(result)
    out.to_csv(ROOT / "outputs" / "tables" / "p3_table1_disposition.csv", index=False)
    return out


def build_p3_table2_resource_utilization(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 3, Table 2: Resource utilization — LOS by destination and route type.
    Reports median (IQR) days_to_discharge overall and by route type.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["_route"] = j.apply(_classify_journey_route, axis=1)
    route_order = ["Primary (village → MHC)", "Secondary transfer", "Direct tertiary"]

    def _stats(sub: pd.DataFrame, label: str) -> dict:
        N = len(sub)
        los = pd.to_numeric(sub.get("days_to_discharge", pd.Series([], dtype=float)), errors="coerce").dropna()
        icu = pd.to_numeric(sub.get("icu_admission", pd.Series([], dtype=float)), errors="coerce")
        surg = pd.to_numeric(sub.get("had_surgery", pd.Series([], dtype=float)), errors="coerce")
        return {
            "Group": label,
            "N journeys": N,
            "LOS median (IQR), days": (
                f"{los.median():.1f} ({los.quantile(0.25):.1f}–{los.quantile(0.75):.1f})"
                if len(los) >= 4 else "—"
            ),
            "LOS mean (SD), days": (
                f"{los.mean():.1f} ({los.std(ddof=1):.1f})" if len(los) >= 2 else "—"
            ),
            "ICU admission, n (%)": fmt_n_pct(int(icu.fillna(0).astype(bool).sum()), N) if "icu_admission" in sub.columns else "NR",
            "Surgery, n (%)": fmt_n_pct(int(surg.fillna(0).astype(bool).sum()), N) if "had_surgery" in sub.columns else "NR",
            "LOS n (non-missing)": len(los),
        }

    rows = [_stats(j, "Overall")]
    for route in route_order:
        rows.append(_stats(j[j["_route"] == route], route))

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "tables" / "p3_table2_resource_utilization.csv", index=False)
    return out


def build_p3_table3_outcomes_by_destination(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 3, Table 3: High-acuity outcomes by destination facility.
    Rows = destination; columns = N, ICU %, surgery %, ED discharge %, mortality %.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()

    dest_col = next((c for c in ("destination_facility", "medevac1_to") if c in j.columns), None)
    if dest_col:
        j["_dest"] = j[dest_col].map(lambda x: expand_facility_label(str(x)) if pd.notna(x) else "Unknown")
    else:
        j["_dest"] = "Unknown"

    def _row(sub: pd.DataFrame, label: str) -> dict:
        N = len(sub)
        def _pct(col: str) -> str:
            if col not in sub.columns:
                return "NR"
            n = int(pd.to_numeric(sub[col], errors="coerce").fillna(0).astype(bool).sum())
            return fmt_n_pct(n, N)
        return {
            "Destination": label,
            "N": N,
            "ICU admission":      _pct("icu_admission"),
            "Surgery":            _pct("had_surgery"),
            "ED discharge":       _pct("ed_discharge"),
            "Short admission":    _pct("short_<36h_admission"),
            "Death at facility":  _pct("death_at_facility"),
            "24h mortality":      _pct("24hr_mortality"),
            "7d mortality":       _pct("7d_mortality"),
            "30d mortality":      _pct("30d_mortality"),
        }

    rows = [_row(j, "Overall")]
    for dest in sorted(j["_dest"].unique()):
        rows.append(_row(j[j["_dest"] == dest], dest))

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "tables" / "p3_table3_outcomes_by_destination.csv", index=False)
    return out


def build_p3_table4_high_acuity_predictors(df: pd.DataFrame) -> pd.DataFrame:
    """
    Paper 3, Table 4: Descriptive predictors of high-acuity outcome (ICU or surgery).
    Reports high-acuity rate by age group, sex, route type, and chief complaint category.
    Full logistic regression deferred until sample size confirmed adequate.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()

    if "icu_admission" not in j.columns or "had_surgery" not in j.columns:
        return pd.DataFrame([{"note": "icu_admission or had_surgery not in dataset."}])

    j["_high_acuity"] = (
        pd.to_numeric(j["icu_admission"], errors="coerce").fillna(0).astype(bool)
        | pd.to_numeric(j["had_surgery"],  errors="coerce").fillna(0).astype(bool)
    )

    age = pd.to_numeric(j["age_at_medevac"], errors="coerce")
    j["_age_grp"] = age.map(_age_bucket_label)
    j["_route"] = j.apply(_classify_journey_route, axis=1)

    def _rate(sub: pd.DataFrame) -> str:
        N = len(sub)
        if N == 0: return "—"
        n = int(sub["_high_acuity"].sum())
        return fmt_n_pct(n, N)

    rows = []
    rows.append({"Predictor": "Overall", "N": len(j), "High-acuity outcome, n (%)": _rate(j)})

    rows.append({"Predictor": "Age group", "N": "", "High-acuity outcome, n (%)": ""})
    for grp in ["<1 year", "1–<5 years", "5–12 years", "13–18 years"]:
        sub = j[j["_age_grp"] == grp]
        rows.append({"Predictor": f"  {grp}", "N": len(sub), "High-acuity outcome, n (%)": _rate(sub)})

    rows.append({"Predictor": "Sex", "N": "", "High-acuity outcome, n (%)": ""})
    for sex in ["Female", "Male"]:
        if "GenderDSC" in j.columns:
            sub = j[j["GenderDSC"] == sex]
            rows.append({"Predictor": f"  {sex}", "N": len(sub), "High-acuity outcome, n (%)": _rate(sub)})

    rows.append({"Predictor": "Route type", "N": "", "High-acuity outcome, n (%)": ""})
    for route in ["Primary (village → MHC)", "Secondary transfer", "Direct tertiary"]:
        sub = j[j["_route"] == route]
        rows.append({"Predictor": f"  {route}", "N": len(sub), "High-acuity outcome, n (%)": _rate(sub)})

    out = pd.DataFrame(rows)
    out.to_csv(ROOT / "outputs" / "tables" / "p3_table4_high_acuity_predictors.csv", index=False)
    return out


def _age_bucket_label(age: float) -> str | None:
    if pd.isna(age): return None
    if age < 1:   return "<1 year"
    if age < 5:   return "1–<5 years"
    if age < 13:  return "5–12 years"
    if age <= 18: return "13–18 years"
    return None


# Canonical display names for outside (non-ATHS) receiving facilities.
# Keys are substrings (case-insensitive) found in the raw medevac_to value.
# The first matching entry wins.  Add new entries here as new facilities appear.
_OUTSIDE_FACILITY_NAMES: list[tuple[str, str]] = [
    ("providence",           "Providence"),
    ("alaska regional",      "Alaska Regional"),
    ("alaska reg",           "Alaska Regional"),
    ("arh",                  "Alaska Regional"),
    ("university of washington", "UW Med Ctr"),
    ("uw medical",           "UW Med Ctr"),
    ("uwmc",                 "UW Med Ctr"),
    ("harborview",           "Harborview"),
    ("seattle children",     "Seattle Children's"),
    ("seattle childrens",    "Seattle Children's"),
    ("ucsf",                 "UCSF"),
    ("mayo",                 "Mayo Clinic"),
    ("stanford",             "Stanford"),
    ("nationwide children",  "Nationwide Children's"),
    ("outside",              "Outside Facility"),   # catch-all coded values
]


def _outside_facility_label(raw: object) -> str:
    """Return a clean display name for an outside (non-ATHS) facility."""
    t = str(raw or "").strip()
    tl = t.lower()
    for key, label in _OUTSIDE_FACILITY_NAMES:
        if key in tl:
            return label
    return t   # fall back to the raw value if no match


_VILLAGE_PALETTE = [
    "#1f77b4","#ff7f0e","#2ca02c","#d62728","#9467bd",
    "#8c564b","#e377c2","#7f7f7f","#bcbd22","#17becf","#aec7e8",
]
# Figure 2 route map: left→right care-pathway colors (villages → MHC → tertiary)
_ROUTE_MHC_COLOR = "#158749"
_ROUTE_ANMC_COLOR = "#D94801"
_ROUTE_VILLAGE_CMAP_LO = 0.35
_ROUTE_VILLAGE_CMAP_HI = 0.82
_ROUTE_TERTIARY_OTHER = ["#CB181D", "#A50F15", "#7F2704"]
_AGE_PALETTE = ["#4C72B0","#DD8452","#55A868","#C44E52"]
_AGE_ORDER   = ["<1 year","1–<5 years","5–12 years","13–18 years"]


def _prep_stacked(
    df: pd.DataFrame,
    group_col: str,
    group_order: list[str],
    palette: list[str],
    start_year: int = 2020,
    end_year:   int = 2024,
) -> tuple[pd.DataFrame, dict[str, str]]:
    """Filter to study period and pivot to stacked-bar format."""
    d = df.copy()
    yr = pd.to_numeric(d.get("journey_start_year", pd.Series([], dtype=float)), errors="coerce")
    d = d[yr.between(start_year, end_year, inclusive="both")]
    color_map = {g: palette[i % len(palette)] for i, g in enumerate(group_order)}
    return d, color_map


def _add_total_labels(ax: plt.Axes, totals: pd.Series, x_positions) -> None:
    """Place total-n labels above each bar."""
    for xi, total in zip(x_positions, totals):
        ax.text(
            xi, total + 0.3, str(int(total)),
            ha="center", va="bottom", fontsize=9, fontweight="bold", color="#333333",
        )


def plot_fig1a_monthly_by_village(
    df: pd.DataFrame,
    start_year: int = 2020,
    end_year:   int = 2024,
) -> plt.Figure:
    """Figure 1A: Monthly medevac volume, stacked by village (2020–2024)."""
    village_order = (
        df.groupby("facility_1_name")["journey_id"].count()
        .sort_values(ascending=False).index.tolist()
    )
    d, cmap = _prep_stacked(df, "facility_1_name", village_order, _VILLAGE_PALETTE, start_year, end_year)
    n_total = len(d)

    mon = pd.to_numeric(d["journey_start_month"], errors="coerce")
    d = d[mon.notna()].copy()
    d["_month"] = mon[mon.notna()].astype(int)

    pivot = (
        d.groupby(["_month", "facility_1_name"])
        .size().unstack(fill_value=0)
        .reindex(columns=village_order, fill_value=0)
        .reindex(range(1, 13), fill_value=0)
    )

    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    x = range(12)
    fig, ax = plt.subplots(figsize=(11, 5))

    bottoms = [0] * 12
    for village in village_order:
        vals = pivot[village].values if village in pivot.columns else [0]*12
        ax.bar(x, vals, bottom=bottoms, label=village,
               color=cmap[village], edgecolor="white", linewidth=0.4)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    _add_total_labels(ax, pd.Series(bottoms), x)
    ax.set_xticks(list(x))
    ax.set_xticklabels(month_labels)
    ax.set_xlabel("Month")
    ax.set_ylabel("Num. Medevac Journeys")
    ax.set_title(
        f"Monthly Pediatric Medevac Volume ({start_year}–{end_year}); n = {n_total}",
        fontsize=12, fontweight="bold",
    )
    ax.legend(title="Village", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


def plot_fig1b_monthly_by_age(
    df: pd.DataFrame,
    start_year: int = 2020,
    end_year:   int = 2024,
) -> plt.Figure:
    """Figure 1B: Monthly medevac volume, stacked by age group (2020–2024)."""
    d, cmap = _prep_stacked(df, "_age_grp", _AGE_ORDER, _AGE_PALETTE, start_year, end_year)
    n_total = len(d)

    age = pd.to_numeric(d["age_at_medevac"], errors="coerce")
    d["_age_grp"] = age.map(_age_bucket_label)
    mon = pd.to_numeric(d["journey_start_month"], errors="coerce")
    d = d[mon.notna() & d["_age_grp"].notna()].copy()
    d["_month"] = mon[d.index].astype(int)

    pivot = (
        d.groupby(["_month", "_age_grp"])
        .size().unstack(fill_value=0)
        .reindex(columns=_AGE_ORDER, fill_value=0)
        .reindex(range(1, 13), fill_value=0)
    )

    month_labels = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    x = range(12)
    fig, ax = plt.subplots(figsize=(11, 5))

    bottoms = [0] * 12
    for grp in _AGE_ORDER:
        vals = pivot[grp].values if grp in pivot.columns else [0]*12
        ax.bar(x, vals, bottom=bottoms, label=grp,
               color=cmap[grp], edgecolor="white", linewidth=0.4)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    _add_total_labels(ax, pd.Series(bottoms), x)
    ax.set_xticks(list(x))
    ax.set_xticklabels(month_labels)
    ax.set_xlabel("Month")
    ax.set_ylabel("Num. Medevac Journeys")
    ax.set_title(
        f"Monthly Pediatric Medevac Volume ({start_year}–{end_year}); n = {n_total}",
        fontsize=12, fontweight="bold",
    )
    ax.legend(title="Age Group", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=9)
    fig.tight_layout()
    return fig


def plot_fig2a_annual_by_village(
    df: pd.DataFrame,
    start_year: int = 2020,
    end_year:   int = 2024,
) -> plt.Figure:
    """Figure 2A: Annual medevac volume, stacked by village (2020–2024)."""
    village_order = (
        df.groupby("facility_1_name")["journey_id"].count()
        .sort_values(ascending=False).index.tolist()
    )
    d, cmap = _prep_stacked(df, "facility_1_name", village_order, _VILLAGE_PALETTE, start_year, end_year)
    n_total = len(d)

    yr = pd.to_numeric(d["journey_start_year"], errors="coerce")
    d = d[yr.notna()].copy()
    d["_year"] = yr[yr.notna()].astype(int)

    years = list(range(start_year, end_year + 1))
    pivot = (
        d.groupby(["_year", "facility_1_name"])
        .size().unstack(fill_value=0)
        .reindex(columns=village_order, fill_value=0)
        .reindex(years, fill_value=0)
    )

    x = range(len(years))
    fig, ax = plt.subplots(figsize=(8, 5))

    bottoms = [0] * len(years)
    for village in village_order:
        vals = pivot[village].values if village in pivot.columns else [0]*len(years)
        ax.bar(x, vals, bottom=bottoms, label=village,
               color=cmap[village], edgecolor="white", linewidth=0.4)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    _add_total_labels(ax, pd.Series(bottoms), x)
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(y) for y in years])
    ax.set_xlabel("Year")
    ax.set_ylabel("Num. Medevac Journeys")
    ax.set_title(
        f"Annual Pediatric Medevac Volume ({start_year}–{end_year}); n = {n_total}",
        fontsize=12, fontweight="bold",
    )
    ax.legend(title="Village", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


def plot_fig2b_annual_by_age(
    df: pd.DataFrame,
    start_year: int = 2020,
    end_year:   int = 2024,
) -> plt.Figure:
    """Figure 2B: Annual medevac volume, stacked by age group (2020–2024)."""
    d, cmap = _prep_stacked(df, "_age_grp", _AGE_ORDER, _AGE_PALETTE, start_year, end_year)
    n_total = len(d)

    age = pd.to_numeric(d["age_at_medevac"], errors="coerce")
    d["_age_grp"] = age.map(_age_bucket_label)
    yr = pd.to_numeric(d["journey_start_year"], errors="coerce")
    d = d[yr.notna() & d["_age_grp"].notna()].copy()
    d["_year"] = yr[d.index].astype(int)

    years = list(range(start_year, end_year + 1))
    pivot = (
        d.groupby(["_year", "_age_grp"])
        .size().unstack(fill_value=0)
        .reindex(columns=_AGE_ORDER, fill_value=0)
        .reindex(years, fill_value=0)
    )

    x = range(len(years))
    fig, ax = plt.subplots(figsize=(8, 5))

    bottoms = [0] * len(years)
    for grp in _AGE_ORDER:
        vals = pivot[grp].values if grp in pivot.columns else [0]*len(years)
        ax.bar(x, vals, bottom=bottoms, label=grp,
               color=cmap[grp], edgecolor="white", linewidth=0.4)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    _add_total_labels(ax, pd.Series(bottoms), x)
    ax.set_xticks(list(x))
    ax.set_xticklabels([str(y) for y in years])
    ax.set_xlabel("Year")
    ax.set_ylabel("Num. Medevac Journeys")
    ax.set_title(
        f"Annual Pediatric Medevac Volume ({start_year}–{end_year}); n = {n_total}",
        fontsize=12, fontweight="bold",
    )
    ax.legend(title="Age Group", bbox_to_anchor=(1.01, 1), loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


def plot_fig4_sankey_transport_routes(df_all: pd.DataFrame) -> plt.Figure:
    """
    Figure 2: Network flow diagram — village-level air ambulance routing.

    Layout
    ------
    Left   : Village nodes (one per village, sized by total outbound legs,
             sorted top-to-bottom by volume).
    Center : Maniilaq Health Center (MHC) node.
    Right  : ANMC node (top) + one node per distinct outside facility (below).

    Flows drawn as bezier curves, line width ∝ transfer count, coloured by
    originating village.  MHC → right-column secondary transfers are drawn
    in neutral dark grey.

    ANMC detection covers both PHI encoded values ("Hub_01", values that
    start with "Hub") and the synthetic/plain-text label "ANMC".
    """
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    import matplotlib.patches as mpatches
    from matplotlib.path import Path as MplPath
    import numpy as np

    j = df_all.drop_duplicates(subset=["journey_id"]).copy()
    if j.empty:
        fig, ax = plt.subplots(figsize=(14, 9))
        ax.text(0.5, 0.5, "No journey data.", ha="center", va="center",
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    # ── Destination classifiers ───────────────────────────────────────────────
    def _is_anmc(v: object) -> bool:
        t = str(v or "").strip()
        tl = t.lower()
        return (t.startswith("Hub") or t.upper() in ("HUB_01", "ANMC")
                or "alaska native" in tl and "medical" in tl)

    def _dest_label(v: object) -> str:
        """Return canonical destination label for a medevac_to value."""
        if pd.isna(v) or not str(v).strip():
            return ""
        if _is_mhc_cah_destination(v):
            return "MHC"
        if _is_anmc(v):
            return "ANMC"
        return _outside_facility_label(v)

    # ── Collect journey-level flows ───────────────────────────────────────────
    flow_rows: list[dict] = []
    for _, r in j.iterrows():
        vname = ""
        for field in ("village_name", "facility_1_name", "medevac1_from"):
            raw = str(r.get(field, "") or "").strip()
            if raw and is_village_medevac_origin(raw):
                vname = raw
                break
        if not vname:
            continue
        legs = [_dest_label(r.get(f"medevac{i}_to")) for i in (1, 2, 3)]
        legs = [l for l in legs if l]   # drop blanks

        # Primary leg (first leg from the village)
        prim = legs[0] if legs else ""
        # Secondary legs that originate at MHC (subsequent legs when leg 1 = MHC)
        sec_from_mhc: list[str] = []
        if legs and legs[0] == "MHC" and len(legs) > 1:
            sec_from_mhc = legs[1:]

        flow_rows.append({
            "village": vname,
            "primary": prim,
            "sec_from_mhc": sec_from_mhc,
        })

    if not flow_rows:
        fig, ax = plt.subplots(figsize=(14, 9))
        ax.text(0.5, 0.5, "No village-origin legs found.", ha="center", va="center",
                transform=ax.transAxes)
        ax.axis("off")
        return fig

    # ── Aggregate counts ──────────────────────────────────────────────────────
    from collections import Counter

    # village → primary destination counts
    prim_counts: Counter = Counter()      # (village, dest) → n
    sec_counts:  Counter = Counter()      # dest → n  (MHC-originated secondary legs)
    village_total: Counter = Counter()

    for fr in flow_rows:
        v, prim = fr["village"], fr["primary"]
        if prim:
            prim_counts[(v, prim)] += 1
            village_total[v] += 1
        for s in fr["sec_from_mhc"]:
            sec_counts[s] += 1

    # All right-column destination nodes (sorted: ANMC first, then alphabetical)
    # Exclude "MHC" — it lives in the center node, not the right column.
    all_right_dests = sorted(
        ({d for _, d in prim_counts} | set(sec_counts.keys())) - {"MHC"},
        key=lambda d: (0 if d == "ANMC" else 1, d),
    )

    villages = sorted(village_total, key=lambda v: -village_total[v])

    # ── Colour palettes (village blues → MHC green → tertiary warm) ───────────
    blues = cm.get_cmap("Blues")
    nv = len(villages)
    vcolor: dict[str, str] = {
        v: mcolors.to_hex(
            blues(
                _ROUTE_VILLAGE_CMAP_LO
                + (_ROUTE_VILLAGE_CMAP_HI - _ROUTE_VILLAGE_CMAP_LO)
                * i
                / max(nv - 1, 1)
            )
        )
        for i, v in enumerate(villages)
    }
    right_colors: dict[str, str] = {"ANMC": _ROUTE_ANMC_COLOR}
    for i, d in enumerate(d for d in all_right_dests if d != "ANMC"):
        right_colors[d] = _ROUTE_TERTIARY_OTHER[i % len(_ROUTE_TERTIARY_OTHER)]

    # ── Layout constants ──────────────────────────────────────────────────────
    X_V   = 0.13    # village column x-centre
    X_MHC = 0.48    # MHC node x-centre
    X_R   = 0.73    # right column dot x-centre (ANMC + outside)
    R_LABEL_GAP = 0.032  # horizontal gap between dot edge and label

    # Village y positions (keep top row below multi-line column headers)
    nv = len(villages)
    yv_top, yv_bot = 0.875, 0.07
    v_ys = {v: yv_top - i * (yv_top - yv_bot) / max(nv - 1, 1)
            for i, v in enumerate(villages)}

    # Right-column nodes: evenly spaced, top to bottom
    nr = len(all_right_dests)
    yr_top, yr_bot = 0.855, 0.20
    r_ys = {d: yr_top - i * (yr_top - yr_bot) / max(nr - 1, 1)
            for i, d in enumerate(all_right_dests)}
    Y_MHC = float(np.mean([yr_top, yr_bot]))   # MHC centres vertically

    # Node radii
    all_n = [village_total[v] for v in villages]
    max_vn = max(all_n) if all_n else 1
    MHC_R  = 0.062
    V_R_MAX, V_R_MIN = 0.020, 0.008

    def _vr(n: int) -> float:
        return V_R_MIN + (V_R_MAX - V_R_MIN) * (n / max_vn) ** 0.5

    n_right: Counter = Counter()
    for (_, d), n in prim_counts.items():
        if d != "MHC":
            n_right[d] += n
    for d, n in sec_counts.items():
        if d != "MHC":
            n_right[d] += n

    all_right_max = max(n_right.values()) if n_right else 1
    R_R_MAX, R_R_MIN = 0.032, 0.014   # dot radius for right-column nodes
    X_R_HDR = X_R                 # header centered over tertiary dots (not labels)

    def _rr(n: int) -> float:
        return R_R_MIN + (R_R_MAX - R_R_MIN) * (n / all_right_max) ** 0.5

    # Line widths
    max_flow = max(prim_counts.values()) if prim_counts else 1
    LW_MIN, LW_MAX = 0.6, 9.0

    def _lw(n: int) -> float:
        return LW_MIN + (LW_MAX - LW_MIN) * (n / max_flow) ** 0.5 if n > 0 else 0.0

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(15, 9))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # ── Bezier curve ──────────────────────────────────────────────────────────
    def _curve(x0: float, y0: float, x1: float, y1: float,
               lw: float, color, alpha: float = 0.72,
               bend: float = 0.0, zorder: int = 2) -> None:
        if lw <= 0:
            return
        cx = (x0 + x1) / 2 + bend
        verts = [(x0, y0), (cx, y0), (cx, y1), (x1, y1)]
        codes = [MplPath.MOVETO, MplPath.CURVE4,
                 MplPath.CURVE4, MplPath.CURVE4]
        ax.add_patch(mpatches.PathPatch(
            MplPath(verts, codes),
            facecolor="none", edgecolor=color,
            linewidth=lw, alpha=alpha, zorder=zorder,
        ))

    # ── Draw village → primary destination lines ──────────────────────────────
    for (v, dest), n in sorted(prim_counts.items(),
                                key=lambda x: -x[1]):   # thick first
        vy = v_ys[v]
        col = vcolor[v]
        vr = _vr(village_total[v])
        if dest == "MHC":
            _curve(X_V + vr, vy, X_MHC - MHC_R, Y_MHC,
                   lw=_lw(n), color=col)
        elif dest in r_ys:
            ry = r_ys[dest]
            rr = _rr(n_right.get(dest, 1))
            _curve(X_V + vr, vy, X_R - rr, ry,
                   lw=_lw(n), color=col, bend=0.04)

    # ── Draw MHC → secondary destination lines (grey) ────────────────────────
    for dest, n in sec_counts.items():
        if dest == "MHC" or dest not in r_ys:
            continue
        ry = r_ys[dest]
        rr = _rr(n_right.get(dest, 1))
        dest_col = right_colors.get(dest, "#555555")
        _curve(X_MHC + MHC_R, Y_MHC, X_R - rr, ry,
               lw=_lw(n), color=dest_col, alpha=0.62, zorder=3)

    # ── MHC node ──────────────────────────────────────────────────────────────
    n_mhc_total = sum(n for (_, d), n in prim_counts.items() if d == "MHC")
    ax.add_patch(plt.Circle((X_MHC, Y_MHC), MHC_R,
                             facecolor=_ROUTE_MHC_COLOR, edgecolor="white",
                             linewidth=1.5, zorder=5))
    ax.text(X_MHC, Y_MHC,
            f"Maniilaq\nHealth Center\nn = {n_mhc_total}",
            ha="center", va="center", fontsize=12,
            fontweight="bold", color="white", zorder=6)

    # ── Right-column nodes (dot + right-side label) ───────────────────────────
    for d in all_right_dests:
        ry = r_ys[d]
        rr = _rr(n_right.get(d, 1))
        col = right_colors.get(d, "#7F7F7F")
        ax.add_patch(plt.Circle((X_R, ry), rr,
                                 facecolor=col, edgecolor="white",
                                 linewidth=1.5, zorder=5))
        ax.text(X_R + rr + R_LABEL_GAP, ry,
                f"{d}\nn = {n_right.get(d, 0)}",
                ha="left", va="center", fontsize=12,
                fontweight="bold", color=col, zorder=6)

    # ── Village nodes ─────────────────────────────────────────────────────────
    for v in villages:
        vy = v_ys[v]
        n_v = village_total[v]
        r = _vr(n_v)
        col = vcolor[v]
        ax.add_patch(plt.Circle((X_V, vy), r,
                                 facecolor=col, edgecolor="white",
                                 linewidth=0.8, zorder=5))
        ax.text(X_V - r - 0.012, vy,
                f"{v}  {n_v}",
                ha="right", va="center", fontsize=12, color="#333333", zorder=6)

    # ── Column headers ────────────────────────────────────────────────────────
    for xc, lbl in [(X_V, "Village Clinics"),
                    (X_MHC, "Regional Critical\nAccess Hospital"),
                    (X_R_HDR, "Tertiary Referral\nHospital")]:
        ax.text(xc, 0.985, lbl, ha="center", va="top",
                fontsize=13, fontweight="bold", color="#333333")

    # ── Legend ────────────────────────────────────────────────────────────────
    from matplotlib.lines import Line2D
    legend_ns = sorted({1, max_flow // 2, max_flow} - {0})
    handles = [
        Line2D([0], [0], color="0.35", lw=_lw(n), label=f"n = {n}")
        for n in legend_ns if n > 0
    ]
    ax.legend(handles=handles, loc="lower center", fontsize=11,
              title="Transfer volume", title_fontsize=12,
              framealpha=0.92, handlelength=4, ncol=len(handles))

    total_journeys = sum(village_total.values())
    ax.set_title(
        f"Figure 2. Pediatric Air Ambulance Routes by Village  (n = {total_journeys} journeys)",
        fontsize=14, pad=12,
    )
    fig.subplots_adjust(left=0.18, right=0.97, top=0.96, bottom=0.04)
    return fig


def save_all_figures(df: pd.DataFrame) -> None:
    OUT_FIGS.mkdir(parents=True, exist_ok=True)
    specs = [
        ("fig1_medevac_map.png", plot_fig1_medevac_activation_map(df)),
        ("fig2_journeys_by_month.png", plot_fig1_journeys_by_month(df)),
        ("fig3_origin_type_pie.png", plot_fig2_origin_pie(df)),
        ("fig4_origin_type_bar.png", plot_fig2_origin_bar(df)),
        ("fig4_journey_duration_hist.png", plot_fig3_journey_duration(df)),
        ("fig5_medevacs_per_journey.png", plot_fig5_medevacs_per_journey(df)),
        ("fig6_medevacs_per_patient.png", plot_fig6_medevacs_per_patient(df)),
        ("fig_voronoi_service_districts.png", plot_fig_voronoi_service_districts(df)),
    ]
    for name, fig in specs:
        save_kw: dict = {}
        if name == "fig1_medevac_map.png":
            save_kw = {"bbox_inches": "tight", "pad_inches": 0.1}
        fig.savefig(OUT_FIGS / name, **save_kw)
        plt.close(fig)
        print(f"Wrote {OUT_FIGS / name}")
    f4 = plot_fig4_activation_vs_arrival_village_cah(df)
    if f4 is not None:
        f4.savefig(OUT_FIGS / "fig4_activation_vs_arrival_village_cah.png")
        plt.close(f4)
        print(f"Wrote {OUT_FIGS / 'fig4_activation_vs_arrival_village_cah.png'}")

    jp = load_journeys_primary_prepared()
    if not jp.empty:
        fig_sankey = plot_fig4_sankey_transport_routes(jp)
        fig_sankey.savefig(
            OUT_FIGS / "fig4_sankey_transport_routes.png",
            bbox_inches="tight",
            pad_inches=0.05,
        )
        plt.close(fig_sankey)
        print(f"Wrote {OUT_FIGS / 'fig4_sankey_transport_routes.png'}")


def main():
    df_all = load_data()
    write_table(build_table0_medevac_routes(), "table0_medevac_routes")
    df_vtm = filter_journeys_village_to_mhc(df_all)
    write_table(build_table1_patient_characteristics(df_vtm), "table1_patient_characteristics")
    write_table(build_table2_village_visit_vitals(df_vtm), "table2_village_visit_vitals")
    write_table(build_table2_1_vitals_missingness(df_vtm), "table2_1_vitals_missingness")
    write_table(build_table2_2_vitals_repeated(df_vtm), "table2_2_vitals_repeated")
    write_table(build_table2_3_vitals_missingness_by_age(df_vtm), "table2_3_vitals_missingness_by_age")
    write_table(build_table2_4_vitals_repeated_by_age(df_vtm), "table2_4_vitals_repeated_by_age")
    write_table(build_table3_pews_data_availability_by_age(df_vtm), "table3_pews_data_availability_by_age")
    write_table(build_table1_cohort(df_vtm), "table_cohort_overview")
    write_table(build_table2_by_origin(df_vtm), "table2_by_origin_type")
    write_table(build_table3_chief_complaints_overall(df_vtm), "table4_chief_complaints_overall")
    for bk, lab, subnum in (
        ("b0", "<1 year", "1"),
        ("b1", "1 to <5 years", "2"),
        ("b2", "5–12 years", "3"),
        ("b3", "13–18 years", "4"),
    ):
        write_table(
            build_table3_chief_complaints_by_age(df_vtm, bk, lab),
            f"table4_{subnum}_chief_complaints",
        )
    write_table(
        build_table3_followup_prior_visit_check(df_vtm),
        "table4_followup_prior_visit_check",
    )
    write_table(
        build_table4_6_expanded_followup_cc_review(df_vtm),
        "table4_6_expanded_followup_cc_review",
    )
    write_table(build_table3_by_year(df_vtm), "table5_journeys_by_year")
    for col, t in build_timing_category_tables(df_vtm).items():
        safe = col.replace(" ", "_")
        write_table(t, f"table6_{safe}")
    write_table(
        build_table5_timing_minutes(df_vtm, village_cah_only=True),
        "table7_timing_minutes_village_cah_only",
    )
    write_table(
        build_table5_timing_minutes(df_vtm, village_cah_only=False),
        "table7_timing_minutes_all_origins",
    )
    t6 = build_table6_mortality(df_vtm)
    if t6 is not None:
        write_table(t6, "table8_mortality_counts")
    save_all_figures(df_vtm)
    print("Done.")


if __name__ == "__main__":
    main()
