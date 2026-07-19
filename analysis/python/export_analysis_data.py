"""
Export analysis-ready datasets for R statistical analysis.

Called as Step 2b in the pipeline (after medevac_data_prep.py):
  python analysis/python/export_analysis_data.py

Inputs (outputs/data/):
  journeys_all.csv  — written by medevac_data_prep.py

Outputs (outputs/data/):
  paper1_route_comparison.csv  — route-classified journeys with age and CC
                                  (read by analysis/R/paper1_stats.R)
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "outputs" / "data"


def export_paper1_route_comparison() -> Path:
    """
    Select and rename the columns needed by paper1_stats.R for inferential tests.

    Columns exported:
      journey_id, route_type, age_at_medevac, age_bucket,
      cc_definitive_custom_grouping, has_village_start
    """
    src = DATA_DIR / "journeys_all.csv"
    if not src.exists():
        raise FileNotFoundError(
            f"Expected {src}\n"
            "Run analysis/python/medevac_data_prep.py first."
        )

    df = pd.read_csv(src)

    # Village-originating journeys — same filter as tbl3_route_comparison() in R:
    # village_name is populated only for the village-originating cohort.
    village_orig = df[
        df["village_name"].notna() & (df["village_name"].str.strip() != "")
    ].copy()

    out = village_orig[[
        "journey_id",
        "route_type",
        "age_at_medevac",
        "age_group",
        "primary_cedis_custom_group",
    ]].rename(columns={
        "age_group":                  "age_bucket",
        "primary_cedis_custom_group": "cc_definitive_custom_grouping",
    })

    dest = DATA_DIR / "paper1_route_comparison.csv"
    out.to_csv(dest, index=False)
    print(f"  paper1_route_comparison.csv  ({len(out):,} rows → {dest})")
    return dest


def main() -> None:
    print("[export_analysis_data] Exporting analysis inputs for R...")
    export_paper1_route_comparison()
    print("Done.")


if __name__ == "__main__":
    main()
