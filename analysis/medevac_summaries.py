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
    t = str(place).strip()
    if not t:
        return True
    u = t.upper().replace("_", "")
    if u.startswith("CAH") or u.startswith("HUB") or "OUTSIDEHOSPITAL" in u:
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


def _is_mhc_cah_destination(to_raw: object) -> bool:
    """Medevac destination is Maniilaq Health Center (critical access hospital)."""
    b = str(to_raw).strip()
    return b == "CAH_01" or b.startswith("CAH")


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
            a, b = str(r[fc]).strip(), str(r[tc]).strip()
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
            a, b = str(r[fc]).strip(), str(r[tc]).strip()
            if is_village_medevac_origin(a) and _is_mhc_cah_destination(b):
                return True
        return False

    return df[df.apply(row_qualifies, axis=1)].copy()


def load_data():
    journeys = pd.read_csv(DATA / "pediatric_medevac_journeys.csv")
    timing = pd.read_csv(DATA / "pediatric_medevac_timing.csv")
    outcomes = pd.read_csv(DATA / "pediatric_outcomes.csv")
    patients = pd.read_csv(DATA / "pediatric_patients.csv")

    timing_extra = [c for c in timing.columns if c not in ("journey_id", "MRN", "origin_type")]
    df = journeys.merge(timing[["journey_id"] + timing_extra], on="journey_id", how="left")

    outcome_extra = [
        "death_at_facility",
        "days_to_discharge",
        "days_to_death",
        "24hr_mortality",
        "7d_mortality",
        "30d_mortality",
        "ed_discharge",
        "short_<36h_admission",
    ]
    out_keep = ["journey_id"] + [c for c in outcome_extra if c in outcomes.columns]
    df = df.merge(outcomes[out_keep], on="journey_id", how="left")
    df = df.merge(patients, on="MRN", how="left")
    # Some PHI extracts omit precomputed journey_start_year/month; derive from medevac1_date.
    if (
        ("journey_start_year" not in df.columns or "journey_start_month" not in df.columns)
        and "medevac1_date" in df.columns
    ):
        d = pd.to_datetime(df["medevac1_date"], errors="coerce")
        if "journey_start_year" not in df.columns:
            df["journey_start_year"] = d.dt.year
        if "journey_start_month" not in df.columns:
            df["journey_start_month"] = d.dt.month
    # For de-identified synthetic extracts, decode Village_* placeholders so
    # tables and map use community names consistently.
    if village_origin_mode() == "codebook":
        for c in ("facility_1_name", "medevac1_from", "medevac2_from", "medevac3_from"):
            if c in df.columns:
                df[c] = df[c].map(_decode_village_name)
    return df


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
    uid: set[int] = set()
    for _, r in j.iterrows():
        for i in (1, 2, 3):
            fc, tc = f"medevac{i}_from", f"medevac{i}_to"
            idc = f"medevac{i}_id"
            if fc not in r.index or tc not in r.index:
                continue
            if pd.isna(r[fc]) or pd.isna(r[tc]) or not str(r[fc]).strip():
                continue
            a, b = str(r[fc]).strip(), str(r[tc]).strip()
            if not (is_village_medevac_origin(a) and _is_mhc_cah_destination(b)):
                continue
            if idc in r.index and pd.notna(r[idc]):
                try:
                    uid.add(int(float(r[idc])))
                except (TypeError, ValueError):
                    pass
    rows.append(
        {
            "characteristic": "Village→CAH medevac records (distinct IDs)",
            "value": str(len(uid)),
        }
    )

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

    # Seasonal pattern across study years: month of each patient's first qualifying medevac.
    msrc = pd.Series(pd.NaT, index=p.index, dtype="datetime64[ns]")
    if "journey_start_date" in p.columns:
        msrc = pd.to_datetime(p["journey_start_date"], errors="coerce")
    if msrc.isna().all() and "medevac1_date" in p.columns:
        msrc = pd.to_datetime(p["medevac1_date"], errors="coerce")
    mon = msrc.dt.month
    month_labels = [
        (1, "Jan"),
        (2, "Feb"),
        (3, "Mar"),
        (4, "Apr"),
        (5, "May"),
        (6, "Jun"),
        (7, "Jul"),
        (8, "Aug"),
        (9, "Sep"),
        (10, "Oct"),
        (11, "Nov"),
        (12, "Dec"),
    ]
    rows.append({"characteristic": "Month of Medevac, n(%)", "value": ""})
    for mnum, mlab in month_labels:
        n = int((mon == mnum).sum())
        rows.append({"characteristic": f"  {mlab}", "value": fmt_n_pct(n, N)})
    n_miss_month = int(mon.isna().sum())
    if n_miss_month:
        rows.append({"characteristic": "  Month missing", "value": fmt_n_pct(n_miss_month, N)})

    # Annual pattern across study years: year of each patient's first qualifying medevac.
    rows.append({"characteristic": "Medevac Per Year, n(%)", "value": ""})
    yr = msrc.dt.year
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


def build_table3_chief_complaints_overall(df: pd.DataFrame) -> pd.DataFrame:
    """Table 3: top 10 village CEDIS chief complaints across village→MHC journeys."""
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
    sub = df.copy()
    if village_cah_only:
        sub = sub[sub["origin_type"] == "village_cah"]
    cols = [
        "medevac_minutes",
        "destination_minutes",
        "flight_time_minutes",
        "time_to_activate_min",
        "activate_to_arrive_min",
    ]
    rows = []
    for c in cols:
        if c not in sub.columns:
            continue
        s = pd.to_numeric(sub[c], errors="coerce").dropna()
        if len(s) == 0:
            continue
        rows.append(
            {
                "variable": c,
                "n": len(s),
                "median": s.median(),
                "q25": s.quantile(0.25),
                "q75": s.quantile(0.75),
                "mean": s.mean(),
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        for x in ["median", "q25", "q75", "mean"]:
            out[x] = out[x].round(1)
    return out


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


def main():
    df_all = load_data()
    write_table(build_table0_medevac_routes(), "table0_medevac_routes")
    df_vtm = filter_journeys_village_to_mhc(df_all)
    write_table(build_table1_patient_characteristics(df_vtm), "table1_patient_characteristics")
    write_table(build_table2_village_visit_vitals(df_vtm), "table2_village_visit_vitals")
    write_table(build_table1_cohort(df_vtm), "table_cohort_overview")
    write_table(build_table2_by_origin(df_vtm), "table2_by_origin_type")
    write_table(build_table3_chief_complaints_overall(df_vtm), "table3_chief_complaints_overall")
    for bk, lab, num in (
        ("b0", "<1 year", "3_1"),
        ("b1", "1 to <5 years", "3_2"),
        ("b2", "5–12 years", "3_3"),
        ("b3", "13–18 years", "3_4"),
    ):
        write_table(
            build_table3_chief_complaints_by_age(df_vtm, bk, lab),
            f"table{num}_chief_complaints",
        )
    write_table(
        build_table3_followup_prior_visit_check(df_vtm),
        "table3_followup_prior_visit_check",
    )
    write_table(build_table3_by_year(df_vtm), "table3_journeys_by_year")
    for col, t in build_timing_category_tables(df_vtm).items():
        safe = col.replace(" ", "_")
        write_table(t, f"table4_{safe}")
    write_table(
        build_table5_timing_minutes(df_vtm, village_cah_only=True),
        "table5_timing_minutes_village_cah_only",
    )
    write_table(
        build_table5_timing_minutes(df_vtm, village_cah_only=False),
        "table5_timing_minutes_all_origins",
    )
    t6 = build_table6_mortality(df_vtm)
    if t6 is not None:
        write_table(t6, "table6_mortality_counts")
    save_all_figures(df_vtm)
    print("Done.")


if __name__ == "__main__":
    main()
