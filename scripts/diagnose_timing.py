"""
Timing diagnostic: identify journeys with suspect activate_to_arrive_min values.

Flags three categories of data quality issues:
  1. same_timestamp   — medevac_datetime == destination_datetime (arrival = activation, impossible)
  2. below_flight_time — activate_to_arrive_min < flight_time_min (faster than the flight itself)
  3. short_< 120min   — activate_to_arrive_min < 120 min (plausible floor given flight + ground time)

Outputs:
  outputs/diagnostics/timing_suspect_journeys.csv   — full row detail
  outputs/diagnostics/timing_suspect_summary.csv    — count by village and flag type
  outputs/diagnostics/timing_distribution.csv       — percentile table for all village→MHC journeys

Run from project root:
    python scripts/diagnose_timing.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analysis"))

import pandas as pd
from medevac_summaries import load_data, filter_journeys_village_to_mhc

OUT = ROOT / "outputs" / "diagnostics"
OUT.mkdir(parents=True, exist_ok=True)

# ── Load data ──────────────────────────────────────────────────────────────────
print("Loading data...")
df = filter_journeys_village_to_mhc(load_data())
print(f"  Village→MHC journeys: {len(df)}")

# Ensure datetime columns are parsed
for col in ("medevac_datetime", "destination_datetime"):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")

act  = pd.to_numeric(df["activate_to_arrive_min"], errors="coerce")
flt  = pd.to_numeric(df["flight_time_min"],         errors="coerce")

# ── Flag conditions ────────────────────────────────────────────────────────────
df["flag_same_timestamp"] = (
    df["medevac_datetime"].notna()
    & df["destination_datetime"].notna()
    & (df["medevac_datetime"] == df["destination_datetime"])
)

df["flag_below_flight_time"] = (
    act.notna() & flt.notna() & (act < flt)
)

df["flag_short_lt120"] = act.notna() & (act < 120)

df["flag_any"] = (
    df["flag_same_timestamp"]
    | df["flag_below_flight_time"]
    | df["flag_short_lt120"]
)

# ── Detail report ──────────────────────────────────────────────────────────────
detail_cols = [
    "journey_id", "MRN", "facility_1_name", "journey_start_year",
    "medevac1_dts",
    "activate_to_arrive_min", "time_to_activate_min", "flight_time_min",
    "medevac_datetime", "destination_datetime",
    "origin_imputed", "destination_imputed", "medevac_imputed",
    "flag_same_timestamp", "flag_below_flight_time", "flag_short_lt120",
]
detail_cols = [c for c in detail_cols if c in df.columns]

suspect = (
    df[df["flag_any"]][detail_cols]
    .sort_values("activate_to_arrive_min")
    .reset_index(drop=True)
)

suspect.to_csv(OUT / "timing_suspect_journeys.csv", index=False)
print(f"\n  Suspect journeys: {len(suspect)}")
print(f"    same_timestamp:    {df['flag_same_timestamp'].sum()}")
print(f"    below_flight_time: {df['flag_below_flight_time'].sum()}")
print(f"    short_lt120:       {df['flag_short_lt120'].sum()}")

# ── Summary by village ─────────────────────────────────────────────────────────
summary = (
    df[df["flag_any"]]
    .groupby("facility_1_name", dropna=False)
    .agg(
        n_suspect        = ("journey_id", "count"),
        n_same_timestamp = ("flag_same_timestamp", "sum"),
        n_below_flight   = ("flag_below_flight_time", "sum"),
        n_short_lt120    = ("flag_short_lt120", "sum"),
        min_activate_to_arrive = ("activate_to_arrive_min", "min"),
        median_activate_to_arrive = ("activate_to_arrive_min", "median"),
    )
    .reset_index()
    .rename(columns={"facility_1_name": "village"})
    .sort_values("n_suspect", ascending=False)
)

# Add total village journeys for context
total_by_village = df.groupby("facility_1_name")["journey_id"].count().rename("n_total")
summary = summary.merge(total_by_village, left_on="village", right_index=True, how="left")
summary["pct_suspect"] = (summary["n_suspect"] / summary["n_total"] * 100).round(1)

summary.to_csv(OUT / "timing_suspect_summary.csv", index=False)

# ── Percentile distribution for all journeys ───────────────────────────────────
pcts = [1, 5, 10, 25, 50, 75, 90, 95, 99]
dist_rows = []
for village, grp in [("Overall", df)] + list(df.groupby("facility_1_name")):
    vals = pd.to_numeric(grp["activate_to_arrive_min"], errors="coerce").dropna()
    row = {"village": village, "n": len(vals)}
    for p in pcts:
        row[f"p{p}"] = round(vals.quantile(p / 100), 1) if len(vals) else None
    row["mean"] = round(vals.mean(), 1) if len(vals) else None
    row["sd"]   = round(vals.std(ddof=1), 1) if len(vals) >= 2 else None
    row["min"]  = round(vals.min(), 1) if len(vals) else None
    row["max"]  = round(vals.max(), 1) if len(vals) else None
    dist_rows.append(row)

dist = pd.DataFrame(dist_rows)
dist.to_csv(OUT / "timing_distribution.csv", index=False)

# ── Console summary ────────────────────────────────────────────────────────────
print("\n── By village ────────────────────────────────────────────")
print(summary[["village","n_total","n_suspect","pct_suspect",
               "n_same_timestamp","n_below_flight","n_short_lt120",
               "min_activate_to_arrive","median_activate_to_arrive"]].to_string(index=False))

print("\n── Overall distribution of activate_to_arrive_min (minutes) ──")
print(dist[dist["village"] == "Overall"][["n","min","p1","p5","p10","p25","p50","p75","p90","p95","p99","max"]].to_string(index=False))

print(f"\nOutputs written to {OUT}/")
print("  timing_suspect_journeys.csv  — full row detail")
print("  timing_suspect_summary.csv   — counts by village")
print("  timing_distribution.csv      — percentile table")
