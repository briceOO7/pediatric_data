.PHONY: all data stats figures render render-html render-pdf render-docx prepare clean help

# ── Tool paths (override in environment if needed) ─────────────────────────────
PYTHON  := python3
RSCRIPT := Rscript
QMD     := manuscripts/paper1/paper1_results.qmd

# ── Synthetic / PHI mode ───────────────────────────────────────────────────────
# Pass SYNTHETIC=1 to use de-identified data + village codebook:
#   make all SYNTHETIC=1
ifdef SYNTHETIC
  MEDEVAC_VILLAGE_ORIGINS := codebook
  export MEDEVAC_VILLAGE_ORIGINS
  MPLBACKEND := Agg
  export MPLBACKEND
  DATA_FLAG  := -synthetic
else
  DATA_FLAG  :=
endif

# ── Default ────────────────────────────────────────────────────────────────────
all: render

# ── Step 1: Python data engineering ───────────────────────────────────────────
# Reads PHI pipeline CSVs (or local data/), writes outputs/data/*.csv
data:
	$(PYTHON) analysis/python/medevac_data_prep.py $(DATA_FLAG)
	$(PYTHON) analysis/python/export_analysis_data.py

# ── Step 2: R statistical analysis ────────────────────────────────────────────
# Reads outputs/data/paper1_route_comparison.csv
# Writes outputs/stats/paper1_table3_pvalues.csv
stats: data
	$(RSCRIPT) analysis/R/paper1_stats.R

# ── Step 3: Python figure generation ──────────────────────────────────────────
# Writes outputs/figures/*.png (embedded by Quarto via knitr::include_graphics)
figures: data
	MPLBACKEND=Agg $(PYTHON) analysis/python/medevac_summaries.py $(DATA_FLAG)

# ── Step 4: Quarto render ──────────────────────────────────────────────────────
# Reads outputs/data/ + outputs/stats/ + outputs/figures/
# Produces manuscripts/paper1/paper1_results_r.html (+ .pdf and .docx)
render: stats figures
	quarto render $(QMD) --to html

# Individual format targets
render-html: stats figures
	quarto render $(QMD) --to html

render-pdf: stats figures
	quarto render $(QMD) --to pdf

render-docx: stats figures
	quarto render $(QMD) --to docx

# ── Convenience: run pipeline without Quarto ──────────────────────────────────
prepare: stats figures

# ── Clean generated outputs ────────────────────────────────────────────────────
clean:
	rm -f outputs/data/*.csv
	rm -f outputs/stats/*.csv
	rm -f outputs/figures/*.png
	rm -f outputs/tables/*.csv

# ── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo "Usage:"
	@echo "  make all              Full pipeline → HTML (real data)"
	@echo "  make all SYNTHETIC=1  Full pipeline → HTML (de-identified synthetic data)"
	@echo "  make render-html      Render HTML only (assumes outputs/ up to date)"
	@echo "  make render-pdf       Render PDF only"
	@echo "  make render-docx      Render Word (.docx) only"
	@echo "  make data             Step 1: Python data engineering → outputs/data/"
	@echo "  make stats            Steps 1–2: data + R stats → outputs/stats/"
	@echo "  make figures          Steps 1+3: data + Python figures → outputs/figures/"
	@echo "  make prepare          Steps 1–3 (all pre-Quarto steps)"
	@echo "  make clean            Remove all generated outputs"
	@echo ""
	@echo "Targets run in order: data → stats → figures → render"
	@echo "PYTHON=$(PYTHON)  RSCRIPT=$(RSCRIPT)  QMD=$(QMD)"
