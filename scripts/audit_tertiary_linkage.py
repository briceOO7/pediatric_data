"""
audit_tertiary_linkage.py
─────────────────────────
Investigates the 75 MHC→ANMC "Direct tertiary" journey records to determine
whether they are linked to village-originating journeys (same patient,
temporally adjacent) or represent locally-presenting MHC patients.

Also flags the specific case(s) where a village→MHC and MHC→ANMC leg were
recorded as two separate journey entries on the same day, and examines why
they may not have been captured as a single two-leg journey.

Run from project root:
    python scripts/audit_tertiary_linkage.py           # PHI / real data
    python scripts/audit_tertiary_linkage.py -synthetic
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis.python.medevac_data_prep import load_raw, compute_derived, _safe_str

# ── Windows (days before MHC→ANMC transfer) to consider "linked" ──────────────
LINK_WINDOWS = [0, 1, 3, 7, 14, 30]


def audit(df: pd.DataFrame) -> None:
    cc: dict = {}
    df2 = compute_derived(df, cc)

    tertiary = df2[df2["route_type"] == "Direct tertiary"].copy()
    village  = df2[df2["route_type"].isin(
        ["Primary (village \u2192 MHC)", "Secondary transfer"]
    )].copy()

    print(f"Total journeys in database  : {len(df2):>6,}")
    print(f"  Village-originating (MHC) : {len(village):>6,}")
    print(f"  MHC→ANMC (\"Direct tertiary\"): {len(tertiary):>6,}")
    print(f"  Other                      : {len(df2) - len(village) - len(tertiary):>6,}")
    print()

    # ── Parse dates ───────────────────────────────────────────────────────────
    for d in (tertiary, village):
        d["_start_dt"] = pd.to_datetime(d["journey_start_date"], errors="coerce")

    # ── Per-patient linkage analysis ───────────────────────────────────────────
    results = []
    for _, trow in tertiary.iterrows():
        mrn      = trow["MRN"]
        jid      = trow["journey_id"]
        t_dt     = trow["_start_dt"]
        t_from   = _safe_str(trow.get("medevac1_from"))
        t_to     = _safe_str(trow.get("medevac1_to"))

        # Village journeys for the same patient
        vj = village[village["MRN"] == mrn].copy()
        vj["_days_before"] = (t_dt - vj["_start_dt"]).dt.total_seconds() / 86400

        # Closest preceding village journey
        preceding = vj[vj["_days_before"] >= 0].sort_values("_days_before")

        rec = {
            "journey_id"        : jid,
            "MRN"               : mrn,
            "t_date"            : t_dt,
            "medevac1_from"     : t_from,
            "medevac1_to"       : t_to,
            "n_village_journeys": len(vj),
        }
        if len(preceding):
            closest = preceding.iloc[0]
            rec["closest_village_jid"]   = closest["journey_id"]
            rec["closest_village_from"]  = _safe_str(closest.get("medevac1_from"))
            rec["closest_village_date"]  = closest["_start_dt"]
            rec["days_since_village"]    = round(closest["_days_before"], 3)
            rec["village_route_type"]    = closest["route_type"]
        else:
            rec["closest_village_jid"]   = None
            rec["closest_village_from"]  = None
            rec["closest_village_date"]  = None
            rec["days_since_village"]    = None
            rec["village_route_type"]    = None

        results.append(rec)

    res = pd.DataFrame(results)

    # ── Summary by linkage window ──────────────────────────────────────────────
    print("Linkage summary (MHC→ANMC journeys with a preceding village journey):")
    print("-" * 60)
    for w in LINK_WINDOWS:
        n = (res["days_since_village"].notna() & (res["days_since_village"] <= w)).sum()
        pct = 100 * n / len(res)
        label = "same day" if w == 0 else f"≤{w:>2} days"
        print(f"  {label}: {n:>3} / {len(res)} ({pct:.0f}%)")

    print()

    # ── Same-day cases (most likely two records for one episode) ──────────────
    same_day = res[res["days_since_village"].notna() & (res["days_since_village"] <= 0.5)]
    print(f"Same-day linkages (within 12 hours): {len(same_day)}")
    print("-" * 60)
    if len(same_day):
        for _, sd in same_day.iterrows():
            print(f"\nMHC→ANMC journey_id  : {sd['journey_id']}")
            print(f"  Date/time           : {sd['t_date']}")
            print(f"  from→to             : {sd['medevac1_from']} → {sd['medevac1_to']}")
            print(f"Village journey_id    : {sd['closest_village_jid']}")
            print(f"  Date/time           : {sd['closest_village_date']}")
            print(f"  from→to             : {sd['closest_village_from']} → MHC")
            hrs = round(sd["days_since_village"] * 24, 1)
            print(f"  Hours between legs  : {hrs}")

            # Show all raw fields for both records
            t_rec = df2[df2["journey_id"] == sd["journey_id"]].iloc[0]
            v_rec = df2[df2["journey_id"] == sd["closest_village_jid"]].iloc[0]

            shared_fields = [c for c in df2.columns if c in t_rec.index and c in v_rec.index]
            print()
            print(f"  {'Field':<35} {'Village→MHC record':<30} {'MHC→ANMC record'}")
            print(f"  {'-'*35} {'-'*30} {'-'*30}")
            for f in shared_fields:
                tv = _safe_str(t_rec.get(f))
                vv = _safe_str(v_rec.get(f))
                if tv or vv:
                    print(f"  {f:<35} {vv:<30} {tv}")

    # ── No village linkage at all ─────────────────────────────────────────────
    unlinked = res[res["n_village_journeys"] == 0]
    print(f"\nPatients with zero village journeys in this DB: {len(unlinked)} / {len(res)}")
    print("  (These are the most likely walk-in / local MHC patients.)")

    # ── Village patients linked within 30 days ────────────────────────────────
    w30 = res[res["days_since_village"].notna() & (res["days_since_village"] <= 30)]
    w30_gt_half = w30[w30["days_since_village"] > 0.5]
    print(f"\nLinked within 1–30 days (separate admissions, not same-day): {len(w30_gt_half)}")
    if len(w30_gt_half):
        cols = ["journey_id", "t_date", "medevac1_from", "medevac1_to",
                "closest_village_from", "closest_village_date", "days_since_village"]
        print(w30_gt_half[[c for c in cols if c in w30_gt_half.columns]].to_string(index=False))

    # ── Full linkage table ─────────────────────────────────────────────────────
    out_path = Path("outputs") / "review" / "tertiary_linkage_audit.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_path, index=False)
    print(f"\nFull per-journey linkage table written to: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("-synthetic", "--synthetic", action="store_true")
    args = parser.parse_args()

    if args.synthetic:
        os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "codebook"

    df = load_raw()
    audit(df)


if __name__ == "__main__":
    main()
