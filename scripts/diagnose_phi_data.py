#!/usr/bin/env python3
"""
PHI data diagnostics for pediatric_data pipeline.

Generates:
1) A markdown report (human-readable)
2) A JSON report (machine-readable)

Focus:
- CSV inventory under data/
- Row counts, line counts, columns, dtypes
- Per-column non-null counts + first non-null row index
- Top value samples for key medevac columns
- Pipeline readiness checks for analysis/medevac_summaries.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd


def _line_count(path: Path) -> int | None:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _col_stats(df: pd.DataFrame) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    n = len(df)
    for c in df.columns:
        s = df[c]
        nn = int(s.notna().sum())
        first_idx = None
        if nn > 0:
            first_idx = int(s.first_valid_index()) if s.first_valid_index() is not None else None
        out.append(
            {
                "column": c,
                "dtype": str(s.dtype),
                "non_null_n": nn,
                "non_null_pct": round((100 * nn / n), 1) if n > 0 else None,
                "first_non_null_row_index0": first_idx,
                "first_non_null_row_number1": (first_idx + 2) if first_idx is not None else None,
            }
        )
    return out


def _safe_read_csv(path: Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        return None


def _inventory_csvs(data_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for p in sorted(data_dir.glob("*.csv")):
        rec: dict[str, Any] = {
            "file": p.name,
            "path": str(p.resolve()),
            "line_count_including_header": _line_count(p),
        }
        df = _safe_read_csv(p)
        if df is None:
            rec["read_ok"] = False
            rows.append(rec)
            continue
        rec["read_ok"] = True
        rec["row_count"] = int(len(df))
        rec["column_count"] = int(len(df.columns))
        rec["columns"] = [str(c) for c in df.columns]
        rec["column_stats"] = _col_stats(df)
        rows.append(rec)
    return rows


def _top_values(df: pd.DataFrame, col: str, n: int = 12) -> list[dict[str, Any]]:
    if col not in df.columns:
        return []
    s = df[col].dropna().astype(str).str.strip()
    s = s[s != ""]
    vc = s.value_counts().head(n)
    return [{"value": k, "n": int(v)} for k, v in vc.items()]


def _pipeline_checks(root: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    data = root / "data"
    journeys_p = data / "pediatric_medevac_journeys.csv"
    timing_p = data / "pediatric_medevac_timing.csv"
    outcomes_p = data / "pediatric_outcomes.csv"
    patients_p = data / "pediatric_patients.csv"

    required = [journeys_p, timing_p, outcomes_p, patients_p]
    out["required_files_present"] = {p.name: p.is_file() for p in required}

    j = _safe_read_csv(journeys_p) if journeys_p.is_file() else None
    t = _safe_read_csv(timing_p) if timing_p.is_file() else None
    o = _safe_read_csv(outcomes_p) if outcomes_p.is_file() else None
    p = _safe_read_csv(patients_p) if patients_p.is_file() else None

    if j is None:
        out["journeys_read_ok"] = False
        return out
    out["journeys_read_ok"] = True
    out["journeys_row_count"] = int(len(j))
    out["journeys_columns"] = [str(c) for c in j.columns]

    for c in [
        "medevac1_from",
        "medevac1_to",
        "medevac2_from",
        "medevac2_to",
        "medevac3_from",
        "medevac3_to",
        "journey_start_date",
        "medevac1_date",
        "MRN",
        "journey_id",
        "facility_1_name",
    ]:
        out[f"top_values__{c}"] = _top_values(j, c, n=15)

    if t is not None:
        overlap = sorted(
            set(j.columns).intersection(set(t.columns)) - {"journey_id", "MRN", "origin_type"}
        )
        out["timing_overlapping_columns_with_journeys_excluding_keys"] = overlap
    else:
        out["timing_overlapping_columns_with_journeys_excluding_keys"] = []

    if o is not None:
        out["outcomes_columns"] = [str(c) for c in o.columns]
    if p is not None:
        out["patients_columns"] = [str(c) for c in p.columns]

    # Import pipeline functions for exact cohort checks.
    try:
        import sys

        sys.path.insert(0, str(root / "analysis"))
        import medevac_summaries as ms  # type: ignore

        df = ms.load_data()
        out["load_data_row_count"] = int(len(df))
        out["load_data_columns"] = [str(c) for c in df.columns]
        out["village_origin_mode_runtime"] = ms.village_origin_mode()
        out["village_to_mhc_legs_count"] = int(ms.count_village_to_mhc_legs(df))
        cohort = ms.filter_journeys_village_to_mhc(df)
        out["cohort_journeys_n"] = int(len(cohort))
        out["cohort_patients_n"] = int(cohort["MRN"].nunique()) if "MRN" in cohort.columns else None
        out["cohort_sample_journey_ids"] = (
            cohort["journey_id"].astype(str).head(20).tolist() if "journey_id" in cohort.columns else []
        )
    except Exception as e:  # pragma: no cover
        out["pipeline_import_or_runtime_error"] = repr(e)

    return out


def _to_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# PHI Data Diagnostic Report")
    lines.append("")
    lines.append(f"- Root: `{report['root']}`")
    lines.append(f"- Data dir: `{report['data_dir']}`")
    lines.append("")
    lines.append("## Pipeline Checks")
    pc = report["pipeline_checks"]
    for k in sorted(pc.keys()):
        v = pc[k]
        if isinstance(v, list):
            lines.append(f"- **{k}**: {len(v)} entries")
        else:
            lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("## CSV Inventory")
    for rec in report["inventory"]:
        lines.append(f"### `{rec['file']}`")
        lines.append(f"- Path: `{rec['path']}`")
        lines.append(f"- Read OK: `{rec.get('read_ok')}`")
        lines.append(f"- Line count (with header): `{rec.get('line_count_including_header')}`")
        if rec.get("read_ok"):
            lines.append(f"- Rows: `{rec.get('row_count')}`")
            lines.append(f"- Columns ({rec.get('column_count')}):")
            for c in rec.get("columns", []):
                lines.append(f"  - `{c}`")
            lines.append("")
            lines.append("| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |")
            lines.append("|---|---:|---:|---:|---:|")
            for cs in rec.get("column_stats", []):
                lines.append(
                    f"| `{cs['column']}` | `{cs['dtype']}` | {cs['non_null_n']} | {cs['non_null_pct']} | {cs['first_non_null_row_number1']} |"
                )
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose PHI CSV layout and pipeline readiness.")
    parser.add_argument("--root", default=None, help="Repo root (defaults to script parent parent).")
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output directory (defaults to outputs/diagnostics).",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    out_dir = Path(args.out_dir).resolve() if args.out_dir else root / "outputs" / "diagnostics"
    out_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "root": str(root),
        "data_dir": str(data_dir),
        "inventory": _inventory_csvs(data_dir),
        "pipeline_checks": _pipeline_checks(root),
    }

    json_path = out_dir / "phi_data_diagnostic.json"
    md_path = out_dir / "phi_data_diagnostic.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_to_markdown(report), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
