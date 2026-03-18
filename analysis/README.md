# Medevac analysis outputs

## `data/` (local only)

The whole **`data/`** directory is listed in **`.gitignore`** so patient/study extracts are never committed. After cloning, copy CSVs into `data/` (e.g. `pediatric_medevac_journeys.csv`, `pediatric_patients.csv`, …). The village mapping file lives in **`docs/village_name_codebook.csv`** (tracked in git).

## Quarto report (HTML / PDF)

Install [Quarto](https://quarto.org/docs/get-started/) and Python deps, then from the **project root** (`pediatric_data/`):

```bash
pip install -r requirements.txt
quarto render medevac_report.qmd
```

- HTML (self-contained): `_quarto_output/medevac_report.html`
- PDF (optional): `quarto render medevac_report.qmd --to pdf` (requires a LaTeX distribution)

## Run standalone CSV + PNG export

From the project root:

```bash
pip install -r requirements.txt
python analysis/medevac_summaries.py
```

## Village names

Placeholder `Village_*` labels in the medevac CSVs were replaced with **Maniilaq community names** using rank alignment to reference journey shares. See **`docs/village_name_codebook.md`** and **`docs/village_name_codebook.csv`**. To re-apply after restoring anonymous data: `python scripts/apply_village_names.py`.

## Data sources

| File | Role |
|------|------|
| `data/pediatric_medevac_journeys.csv` | Journey patterns, locations, medevac legs, duration |
| `data/pediatric_medevac_timing.csv` | Activation / flight / ground-time metrics |
| `data/pediatric_outcomes.csv` | Mortality, discharge, length of stay proxies |
| `data/pediatric_patients.csv` | Gender (merged for future stratification) |

## Outputs

- **`outputs/tables/`** — CSV tables for manuscripts or supplements  
- **`outputs/figures/`** — PNG figures (temporal trend, origin mix, duration, timing scatter, medevacs per journey)

- **Table 0** (`table0_medevac_routes.csv`): every distinct medevac leg (origin→destination) with n and % (n); no “Other” bucket.
- **Table 1** (`table1_patient_characteristics.csv`): % (n) by patient (first medevac); age mean (SD); villages at first medevac. Optional columns on `pediatric_patients.csv`: **`AI_AN`** (`1` = yes) or **`RaceDSC`**; **`PrimaryPayorNM`** (insurance / primary payor, one row per patient).

Extend `medevac_summaries.py` to add models, chief-complaint stratification, or facility-level summaries.
