#!/usr/bin/env python3
"""
Full pipeline: write CSV tables, all PNG figures (including Figure 1 map), then render Quarto.

Designed for headless servers (PHI/Linux): MPLBACKEND=Agg, Quarto HTML by default.

Usage (from repo root or anywhere):
  python scripts/run_full_pipeline.py              # auto mode (infer vs codebook by data / env)
  python scripts/run_full_pipeline.py -synthetic   # local: de-ID extract + village_name_codebook
  python scripts/run_full_pipeline.py --skip-quarto
  python scripts/run_full_pipeline.py --skip-analysis --quarto-to html
  python scripts/run_full_pipeline.py --fetch-census   # needs network; updates pediatric denominators

Requires: Python deps (requirements.txt), `quarto` on PATH, `data/*.csv`, `mapping_data/` shapefiles for the map.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from shutil import which


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build outputs/tables, outputs/figures, then medevac_report (Quarto)."
    )
    parser.add_argument(
        "--skip-analysis",
        action="store_true",
        help="Only run Quarto (assumes tables/figures already built).",
    )
    parser.add_argument(
        "--skip-quarto",
        action="store_true",
        help="Only run Python analysis (tables + figures).",
    )
    parser.add_argument(
        "--fetch-census",
        action="store_true",
        help="Refresh docs/maniilaq_village_census2020_pediatric.csv (Census API; requires requests).",
    )
    parser.add_argument(
        "--quarto-to",
        default="html",
        choices=("html", "pdf", "default"),
        help="'html' (recommended on PHI), 'pdf' (needs LaTeX), or 'default' (all formats in .qmd YAML).",
    )
    parser.add_argument(
        "-synthetic",
        "--synthetic",
        action="store_true",
        help="Local de-identified data: use village_name_codebook.csv (not infer). Omit on PHI.",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    os.chdir(root)

    # Headless map/figures on servers without a display
    os.environ.setdefault("MPLBACKEND", "Agg")
    # Mode selection:
    # -synthetic -> force codebook mode.
    # otherwise preserve explicit env var; if not set, analysis auto-detects mode from data.
    if args.synthetic:
        os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "codebook"
        mode = "synthetic (village codebook)"
    else:
        cur = os.environ.get("MEDEVAC_VILLAGE_ORIGINS", "").strip().lower()
        if cur in {"infer", "codebook"}:
            mode = f"env override ({cur})"
        else:
            mode = "auto detect (infer/codebook)"
    print(f"==> Pipeline mode: {mode}")

    py = sys.executable

    if args.fetch_census:
        print("==> Census pediatric denominators")
        r = subprocess.run(
            [py, str(root / "scripts" / "fetch_maniilaq_census_pediatric.py")],
            cwd=root,
        )
        if r.returncode != 0:
            return r.returncode

    if not args.skip_analysis:
        print("==> Tables + figures (analysis/medevac_summaries.py)")
        r = subprocess.run([py, str(root / "analysis" / "medevac_summaries.py")], cwd=root)
        if r.returncode != 0:
            return r.returncode

    if not args.skip_quarto:
        quarto = which("quarto")
        if not quarto:
            print("ERROR: quarto not found on PATH. Install Quarto or use --skip-quarto.", file=sys.stderr)
            return 127
        cmd = [quarto, "render", str(root / "medevac_report.qmd")]
        if args.quarto_to == "html":
            cmd.extend(["--to", "html"])
        elif args.quarto_to == "pdf":
            cmd.extend(["--to", "pdf"])
        # default: no --to → Quarto uses medevac_report.qmd format list (html + pdf)
        print("==> Quarto:", " ".join(cmd))
        r = subprocess.run(cmd, cwd=root)
        if r.returncode != 0:
            return r.returncode

    print("Pipeline finished OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
