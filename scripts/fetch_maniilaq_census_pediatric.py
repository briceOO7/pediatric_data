#!/usr/bin/env python3
"""
Fetch 2020 Census DHC counts: total pop + under-18 (P12) for Maniilaq-region places.
Writes docs/maniilaq_village_census2020_pediatric.csv (NAME matches facility / map layer).
Run when you want to refresh denominators: python scripts/fetch_maniilaq_census_pediatric.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "maniilaq_village_census2020_pediatric.csv"

# Census place NAME -> short NAME (matches healthcare layer / pop CSV)
CENSUS_NAME_TO_VILLAGE: dict[str, str] = {
    "Kotzebue city, Alaska": "Kotzebue",
    "Selawik city, Alaska": "Selawik",
    "Noorvik city, Alaska": "Noorvik",
    "Buckland city, Alaska": "Buckland",
    "Kiana city, Alaska": "Kiana",
    "Kivalina city, Alaska": "Kivalina",
    "Ambler city, Alaska": "Ambler",
    "Shungnak city, Alaska": "Shungnak",
    "Kobuk city, Alaska": "Kobuk",
    "Deering city, Alaska": "Deering",
    "Noatak CDP, Alaska": "Noatak",
    "Point Hope city, Alaska": "Point Hope",
}

URL = "https://api.census.gov/data/2020/dec/dhc"
VARS = [
    "NAME",
    "P12_001N",  # total population
    "P12_003N",
    "P12_004N",
    "P12_005N",
    "P12_006N",  # male <18
    "P12_027N",
    "P12_028N",
    "P12_029N",
    "P12_030N",  # female <18
]


def main() -> int:
    params = {
        "get": ",".join(VARS),
        "for": "place:*",
        "in": "state:02",
    }
    r = requests.get(URL, params=params, timeout=120)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    num_cols = df.columns.difference(["NAME", "state", "place"])
    df[num_cols] = df[num_cols].astype(int)

    df["pediatric_pop"] = (
        df["P12_003N"]
        + df["P12_004N"]
        + df["P12_005N"]
        + df["P12_006N"]
        + df["P12_027N"]
        + df["P12_028N"]
        + df["P12_029N"]
        + df["P12_030N"]
    )
    df["pct_pediatric"] = df["pediatric_pop"] / df["P12_001N"].replace(0, pd.NA)

    want = list(CENSUS_NAME_TO_VILLAGE.keys())
    sub = df[df["NAME"].isin(want)].copy()
    missing = set(want) - set(sub["NAME"])
    if missing:
        print("Missing Census places:", missing, file=sys.stderr)
        return 1

    sub["NAME"] = sub["NAME"].map(CENSUS_NAME_TO_VILLAGE)
    out = sub[["NAME", "P12_001N", "pediatric_pop", "pct_pediatric"]].rename(
        columns={"P12_001N": "total_pop"}
    )
    out = out.sort_values("NAME")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    print(f"Wrote {OUT} ({len(out)} rows)")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
