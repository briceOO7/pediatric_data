"""
Count disambiguation script.

Traces exactly how many journeys fall into each category at each
filtering step, so you can reconcile the numbers across Table 1,
Table 3, and the narrative.

Run from the project root:
    python scripts/count_disambiguate.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))

import pandas as pd
from medevac_summaries import (
    load_data,
    filter_journeys_village_to_mhc,
    is_village_medevac_origin,
    _is_mhc_cah_destination,
    export_secondary_excluded_from_mhc_filter,
)

df_all  = load_data()
df_mhc  = filter_journeys_village_to_mhc(df_all)

j_all  = df_all.drop_duplicates("journey_id").copy()
j_mhc  = df_mhc.drop_duplicates("journey_id").copy()

# ── Step 1: all journeys ──────────────────────────────────────────────────────
print("=" * 60)
print("STEP 1 — All unique journeys in dataset")
print(f"  Total journey_ids : {j_all['journey_id'].nunique()}")
print(f"  Unique MRNs       : {j_all['MRN'].nunique()}")

# ── Step 2: village-originating journeys ─────────────────────────────────────
vmask = j_all["facility_1_name"].apply(lambda x: is_village_medevac_origin(str(x or "")))
j_vill = j_all[vmask]
print()
print("STEP 2 — Village-originating journeys (facility_1 = village clinic)")
print(f"  Total            : {len(j_vill)}")
print(f"  Unique MRNs      : {j_vill['MRN'].nunique()}")

# ── Step 3: by route type (medevac leg destinations) ──────────────────────────
def _route(row):
    m1s = "" if pd.isna(row.get("medevac1_to")) else str(row.get("medevac1_to")).strip()
    m2s = "" if pd.isna(row.get("medevac2_to")) else str(row.get("medevac2_to")).strip()
    if _is_mhc_cah_destination(m1s):
        return "Secondary" if m2s else "Primary only"
    return "Direct tertiary"

j_vill = j_vill.copy()
j_vill["_route"] = j_vill.apply(_route, axis=1)
rc = j_vill["_route"].value_counts()
print()
print("STEP 3 — Village journeys by route type (medevac1_to / medevac2_to legs)")
for r in ["Primary only", "Secondary", "Direct tertiary"]:
    print(f"  {r:<22}: {rc.get(r, 0):>4}")
print(f"  {'TOTAL':<22}: {rc.sum():>4}  ← should equal Step 2")

# ── Step 4: filter_journeys_village_to_mhc (used by Table 1) ─────────────────
print()
print("STEP 4 — filter_journeys_village_to_mhc() output (used by Table 1)")
print(f"  Unique journeys  : {j_mhc['journey_id'].nunique()}")
print(f"  Unique MRNs      : {j_mhc['MRN'].nunique()}")

# Cross-reference: which route types end up in the MHC filter?
merged = j_mhc[["journey_id"]].merge(
    j_vill[["journey_id", "_route"]], on="journey_id", how="left"
)
merged["_route"] = merged["_route"].fillna("non-village-origin")
print(f"  Route breakdown within Table 1 cohort:")
for r in merged["_route"].value_counts().items():
    print(f"    {r[0]:<30}: {r[1]:>4}")

# ── Step 5: journeys in Table 3 but NOT Table 1 ───────────────────────────────
in_t3_not_t1 = set(j_vill["journey_id"].astype(str)) - \
               set(j_mhc["journey_id"].astype(str))
print()
print("STEP 5 — Village journeys in Table 3 scope but NOT in Table 1 scope")
print(f"  N = {len(in_t3_not_t1)}")
if in_t3_not_t1:
    extra = j_vill[j_vill["journey_id"].astype(str).isin(in_t3_not_t1)]
    print("  Route breakdown:")
    print(extra["_route"].value_counts().to_string())
    print()
    print("  facility_1/2/3 sample:")
    print(extra[["journey_id", "facility_1_name", "facility_2_name",
                  "facility_3_name", "_route"]].to_string(index=False))

print()
print("=" * 60)
print("SUMMARY")
print(f"  Village flights total        : {len(j_vill):>4}  (cohort overview headline)")
print(f"  Primary only (no secondary)  : {rc.get('Primary only', 0):>4}")
print(f"  Secondary (→MHC→further)     : {rc.get('Secondary', 0):>4}")
print(f"  Direct tertiary (→ANMC)      : {rc.get('Direct tertiary', 0):>4}")
print(f"  filter_journeys_village_to_mhc: {j_mhc['journey_id'].nunique():>4}  (Table 1 N)")

if in_t3_not_t1:
    print()
    print("Exporting secondary journeys excluded from MHC filter...")
    export_secondary_excluded_from_mhc_filter(df_all)
