#!/usr/bin/env python3
"""
Full pipeline (Python data engineering → R stats → Python figures → Quarto/R tables).

Architecture:
  Step 1 (data):    analysis/python/medevac_data_prep.py
                    → outputs/data/*.csv  (analysis-ready CSVs)
  Step 1b (export): analysis/python/export_analysis_data.py
                    → outputs/data/paper1_route_comparison.csv  (for R stats)
  Step 2 (figures): analysis/python/medevac_summaries.py
                    → outputs/figures/*.png
  Step 2b (stats):  analysis/R/paper1_stats.R  (optional; skips if Rscript not found)
                    → outputs/stats/paper1_table3_pvalues.csv
  Step 3 (quarto):  quarto render  (R reads outputs/data/, builds gtsummary tables)

Usage (from repo root or anywhere):
  python scripts/run_full_pipeline.py              # default: real data (infer)
  python scripts/run_full_pipeline.py -synthetic   # local: de-ID extract + village codebook
  MEDEVAC_SYNTHETIC=1 python scripts/run_full_pipeline.py   # same as -synthetic
  python scripts/run_full_pipeline.py --skip-quarto
  python scripts/run_full_pipeline.py --skip-analysis --quarto-to html
  python scripts/run_full_pipeline.py --fetch-census   # refresh Census denominators

Requires: Python deps (requirements.txt), R + renv packages, quarto on PATH.
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
    # -synthetic or MEDEVAC_SYNTHETIC truthy -> codebook mode.
    # otherwise default to infer mode (real-data behavior).
    if args.synthetic:
        os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "codebook"
        mode = "synthetic (village codebook)"
    else:
        syn = os.environ.get("MEDEVAC_SYNTHETIC", "").strip().lower()
        if syn in {"1", "true", "yes", "y", "on"}:
            os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "codebook"
            mode = "synthetic (via MEDEVAC_SYNTHETIC)"
        else:
            cur = os.environ.get("MEDEVAC_VILLAGE_ORIGINS", "").strip().lower()
            if cur in {"infer", "codebook"}:
                mode = f"env override ({cur})"
            else:
                os.environ["MEDEVAC_VILLAGE_ORIGINS"] = "infer"
                mode = "real data (infer default)"
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
        print("==> Step 1: Data engineering (analysis/python/medevac_data_prep.py → outputs/data/)")
        r = subprocess.run(
            [py, str(root / "analysis" / "python" / "medevac_data_prep.py")],
            cwd=root,
        )
        if r.returncode != 0:
            return r.returncode

        print("==> Step 1b: Export analysis inputs for R (export_analysis_data.py)")
        r = subprocess.run(
            [py, str(root / "analysis" / "python" / "export_analysis_data.py")],
            cwd=root,
        )
        if r.returncode != 0:
            return r.returncode

        print("==> Step 2: Figures (analysis/python/medevac_summaries.py → outputs/figures/)")
        r = subprocess.run([py, str(root / "analysis" / "python" / "medevac_summaries.py")], cwd=root)
        if r.returncode != 0:
            return r.returncode

        # Step 2b: R statistical analysis (optional — skips gracefully if Rscript unavailable)
        rscript = which("Rscript")
        if rscript:
            print("==> Step 2b: R stats (analysis/R/paper1_stats.R → outputs/stats/)")
            r = subprocess.run(
                [rscript, str(root / "analysis" / "R" / "paper1_stats.R")],
                cwd=root,
            )
            if r.returncode != 0:
                print("WARNING: R stats failed (p-values will show as '—' in tables).", file=sys.stderr)
        else:
            print("WARNING: Rscript not on PATH — skipping R stats (p-values will show as '—').")

    if not args.skip_quarto:
        quarto = which("quarto")
        if not quarto:
            print("ERROR: quarto not found on PATH. Install Quarto or use --skip-quarto.", file=sys.stderr)
            return 127
        print("==> Step 3: Quarto render (R builds tables via gtsummary)")
        cmd = [quarto, "render", str(root / "manuscripts" / "paper1" / "paper1_results.qmd")]
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
