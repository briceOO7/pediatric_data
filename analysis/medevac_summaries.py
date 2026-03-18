"""
Medevac descriptive summaries: tables (CSV), figures (PNG), and builders for Quarto.
Run from project root: python analysis/medevac_summaries.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

# Paths
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VILLAGE_CODEBOOK = ROOT / "docs" / "village_name_codebook.csv"
OUT_TABLES = ROOT / "outputs" / "tables"
OUT_FIGS = ROOT / "outputs" / "figures"

sns.set_theme(style="whitegrid", context="talk", font_scale=0.85)
plt.rcParams["figure.dpi"] = 120
plt.rcParams["savefig.dpi"] = 150
plt.rcParams["figure.figsize"] = (10, 6)

_VILLAGE_NAMES_CACHE: frozenset[str] | None = None


def maniilaq_village_names() -> frozenset[str]:
    """Communities from docs/village_name_codebook.csv (post–de-ID rename)."""
    global _VILLAGE_NAMES_CACHE
    if _VILLAGE_NAMES_CACHE is None:
        cb = pd.read_csv(VILLAGE_CODEBOOK)
        _VILLAGE_NAMES_CACHE = frozenset(cb["community_name"].astype(str))
    return _VILLAGE_NAMES_CACHE


def _is_village_place(name: object) -> bool:
    s = str(name).strip()
    if s.startswith("Village_"):
        return True
    return s in maniilaq_village_names()


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


def build_table0_medevac_routes(journeys: pd.DataFrame | None = None) -> pd.DataFrame:
    """Each row = one explicit origin→destination leg (medevac1/2/3); no aggregate Other."""
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
                c[(a, b)] += 1
    total = sum(c.values())
    rows = []
    for (frm, to), n in sorted(c.items(), key=lambda x: (-x[1], x[0][0].lower(), x[0][1].lower())):
        rows.append(
            {
                "route": f"{frm} → {to}",
                "n_legs": n,
                "pct_n": fmt_pct_n(n, total),
            }
        )
    rows.append(
        {
            "route": "Total",
            "n_legs": total,
            "pct_n": f"100.0 ({total})",
        }
    )
    return pd.DataFrame(rows)


def build_table1_patient_characteristics(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per patient = earliest medevac (medevac1_date) among their journeys.
    Female, AI/AN, insurance (PrimaryPayorNM), age mean (SD), age groups, origin village.
    """
    j = df.drop_duplicates(subset=["journey_id"]).copy()
    j["medevac1_date"] = pd.to_datetime(j["medevac1_date"], errors="coerce")
    first = j.sort_values("medevac1_date").groupby("MRN", as_index=False).first()
    N = len(first)
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
    uid: set[int] = set()
    for col in ("medevac1_id", "medevac2_id", "medevac3_id"):
        if col in j.columns:
            for x in j[col].dropna():
                uid.add(int(float(x)))
    rows.append({"characteristic": "Unique patients", "value": str(n_patients_cohort)})
    rows.append({"characteristic": "Unique medevac records (distinct IDs)", "value": str(len(uid))})

    n_female = int((p["GenderDSC"] == "Female").sum())
    rows.append({"characteristic": "Female sex", "value": fmt_pct_n(n_female, N)})

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
                        "value": fmt_pct_n(n_yes, N),
                    }
                )
            else:
                rows.append(
                    {
                        "characteristic": "American Indian / Alaska Native",
                        "value": f"{fmt_pct_n(n_yes, n_known)} of patients with AI_AN recorded (n={n_known})",
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
                "value": fmt_pct_n(int(ai.sum()), N),
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
            rows.append({"characteristic": str(payor), "value": fmt_pct_n(int(cnt), N)})
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
    for lab, key in age_rows:
        n = int((ag == key).sum())
        rows.append({"characteristic": lab, "value": fmt_pct_n(n, N)})
    n_miss = int(ag.isna().sum() + (ag == "other").sum())
    if n_miss:
        rows.append({"characteristic": "Age missing or >18 y", "value": fmt_pct_n(n_miss, N)})

    rows.append({"characteristic": "Origin village at first medevac***", "value": ""})
    fac = p["facility_1_name"].fillna("").astype(str)
    vset = maniilaq_village_names()
    villages = sorted({v for v in fac.unique() if str(v).strip() in vset})
    for v in villages:
        n = int((fac == v).sum())
        if n:
            rows.append({"characteristic": v, "value": fmt_pct_n(n, N)})
    n_non = int((~fac.isin(vset)).sum())
    rows.append(
        {
            "characteristic": "Non-village first site (e.g. CAH)",
            "value": fmt_pct_n(n_non, N),
        }
    )

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
    t["pct_of_journeys"] = (100 * t["n_events"] / len(df)).round(2)
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
    ax.set_ylabel("Activation to arrival at CAH (hours)")
    ax.set_title("Timing (village → CAH journeys)")
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


def plot_fig6_medevacs_per_patient(df: pd.DataFrame) -> plt.Figure:
    """Histogram: total medevac legs per patient (sum of num_medevacs over journeys)."""
    j = df.drop_duplicates(subset=["journey_id"])
    per = j.groupby("MRN", as_index=False)["num_medevacs"].sum()
    x = per["num_medevacs"].astype(int)
    xmax = int(x.max())
    fig, ax = plt.subplots()
    bins = range(1, xmax + 2)
    ax.hist(x, bins=bins, align="left", rwidth=0.85, color="steelblue", edgecolor="white")
    ax.set_xticks(range(1, xmax + 1))
    ax.set_xlabel("Total medevac legs per patient (all journeys)")
    ax.set_ylabel("Patients")
    ax.set_title("Distribution of medevacs per patient")
    fig.tight_layout()
    return fig


def save_all_figures(df: pd.DataFrame) -> None:
    OUT_FIGS.mkdir(parents=True, exist_ok=True)
    specs = [
        ("fig1_journeys_by_month.png", plot_fig1_journeys_by_month(df)),
        ("fig2_origin_type_pie.png", plot_fig2_origin_pie(df)),
        ("fig2_origin_type_bar.png", plot_fig2_origin_bar(df)),
        ("fig3_journey_duration_hist.png", plot_fig3_journey_duration(df)),
        ("fig5_medevacs_per_journey.png", plot_fig5_medevacs_per_journey(df)),
        ("fig6_medevacs_per_patient.png", plot_fig6_medevacs_per_patient(df)),
    ]
    for name, fig in specs:
        fig.savefig(OUT_FIGS / name)
        plt.close(fig)
        print(f"Wrote {OUT_FIGS / name}")
    f4 = plot_fig4_activation_vs_arrival_village_cah(df)
    if f4 is not None:
        f4.savefig(OUT_FIGS / "fig4_activation_vs_arrival_village_cah.png")
        plt.close(f4)
        print(f"Wrote {OUT_FIGS / 'fig4_activation_vs_arrival_village_cah.png'}")


def main():
    df = load_data()
    write_table(build_table0_medevac_routes(), "table0_medevac_routes")
    write_table(build_table1_patient_characteristics(df), "table1_patient_characteristics")
    write_table(build_table1_cohort(df), "table_cohort_overview")
    write_table(build_table2_by_origin(df), "table2_by_origin_type")
    write_table(build_table3_by_year(df), "table3_journeys_by_year")
    for col, t in build_timing_category_tables(df).items():
        safe = col.replace(" ", "_")
        write_table(t, f"table4_{safe}")
    write_table(
        build_table5_timing_minutes(df, village_cah_only=True),
        "table5_timing_minutes_village_cah_only",
    )
    write_table(
        build_table5_timing_minutes(df, village_cah_only=False),
        "table5_timing_minutes_all_origins",
    )
    t6 = build_table6_mortality(df)
    if t6 is not None:
        write_table(t6, "table6_mortality_counts")
    save_all_figures(df)
    print("Done.")


if __name__ == "__main__":
    main()
