#!/usr/bin/env python3
"""One-time or repeatable: replace Village_* with codebook names in data CSVs."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CB = ROOT / "docs" / "village_name_codebook.csv"


def load_mapping() -> dict[str, str]:
    cb = pd.read_csv(CB)
    return dict(zip(cb["anonymous_code"], cb["community_name"], strict=True))


def replace_in_file(path: Path, mapping: dict[str, str]) -> int:
    text = path.read_text(encoding="utf-8")
    orig = text
    # Longer codes first (Village_I before Village_I... all same len; order by key desc to be stable)
    for old in sorted(mapping.keys(), key=len, reverse=True):
        text = text.replace(old, mapping[old])
    if text != orig:
        path.write_text(text, encoding="utf-8")
        return 1
    return 0


def main():
    mapping = load_mapping()
    n = 0
    for path in sorted(DATA.glob("*.csv")):
        try:
            if "Village_" in path.read_text(encoding="utf-8"):
                n += replace_in_file(path, mapping)
                print(f"Updated {path.name}")
        except OSError:
            pass
    print(f"Done. Files touched: {n}")


if __name__ == "__main__":
    main()
