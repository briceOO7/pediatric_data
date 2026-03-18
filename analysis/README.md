# Medevac analysis outputs

## One-shot pipeline (PHI / Linux / local)

From the **project root**, after placing `data/*.csv` (+ `mapping_data/` for the map):

```bash
bash scripts/run_full_pipeline.sh               # auto-creates/uses .venv, installs deps, PHI default real-data
bash scripts/run_full_pipeline.sh -synthetic    # local de-ID + village codebook
```

This runs **`analysis/medevac_summaries.py`** (all `outputs/tables/*.csv` and `outputs/figures/*.png`, including Figure 1 map) then **`quarto render medevac_report.qmd --to html`**. Uses **headless Matplotlib** (`MPLBACKEND=Agg`) if no display.

If you prefer manual activation instead of the wrapper:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/run_full_pipeline.py
```

| Flag | Meaning |
|------|--------|
| `--skip-quarto` | Only rebuild tables + figures |
| `--skip-analysis` | Only Quarto (reuse existing outputs) |
| `--fetch-census` | Refresh pediatric denominators (network) before analysis |
| `--quarto-to pdf` | PDF instead of HTML (needs LaTeX) |
| `--quarto-to default` | Use all formats in the `.qmd` YAML |
| `-synthetic` / `--synthetic` | Local de-ID run: village logic from `village_name_codebook.csv`. **Omit on PHI** (default is real-data infer mode). |

Shell wrapper notes:
- Uses active `VIRTUAL_ENV` if already set.
- Otherwise uses `MEDEVAC_VENV_DIR` or defaults to `.venv` in repo root.

### PHI extract (full data — default)

On the PHI machine, run **`run_full_pipeline.py` without `-synthetic`**. The pipeline is built to use a normal clinical extract when those columns exist:

| Area | Where | Columns / behavior |
|------|--------|---------------------|
| **Villages** | `pediatric_medevac_journeys.csv` | Real community names in `medevac*_from` / `facility_1_name` (matched to census/GIS for the map). |
| **Dates** | Journeys + timing CSVs | e.g. `medevac1_date`, journey timing fields — used for cohort (first medevac per patient), trends, timing tables/figures. |
| **Insurance** | `pediatric_patients.csv` | **`PrimaryPayorNM`** (one row per patient, merged on `MRN`) → Table 1 payor breakdown. |
| **Race / AIAN** | `pediatric_patients.csv` | **`AI_AN`** (`1` = yes) preferred, or **`RaceDSC`** text for AI/AN row. |
| **Demographics** | Patients + journeys | **`GenderDSC`**, **`age_at_medevac`** (or derived), etc., as in your extract. |

Use **`-synthetic`** only for the stripped, de-identified copy (missing many columns, `Village_*` or codebook-mapped names).

## Figure 1 map (`plot_fig1_medevac_activation_map`)

Requires **`mapping_data/`** shapefiles (boroughs + Maniilaq healthcare facilities; PC-safe names, see `docs/mapping_data_layout.md`). Counts **village → MHC (CAH_01)** medevac legs. Rates use **residents under 18** from **`docs/maniilaq_village_census2020_pediatric.csv`** (2020 Census DHC). Refresh: `python scripts/fetch_maniilaq_census_pediatric.py`. Needs **`geopandas`**.

## Facility display names

`docs/facility_name_codebook.csv`: CAH → Maniilaq Health Center, Hub → ANMC, outside hospitals → UW / Providence. Applied in Table 0 routes and selected figure labels.

## `data/` (local only)

The whole **`data/`** directory is listed in **`.gitignore`** so patient/study extracts are never committed. After cloning, copy CSVs into `data/` (e.g. `pediatric_medevac_journeys.csv`, `pediatric_patients.csv`, …). The village mapping file lives in **`docs/village_name_codebook.csv`** (tracked in git).

**Table 2 (vitals):** **`data/pediatric_village_visit_vitals.csv`** or **`data/pediatric_vitals_wide.csv`** (journey medians + `MRN`); see **`docs/pediatric_village_visit_vitals.md`**.

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

## PHI diagnostics (schema + pipeline readiness)

If a PHI run behaves unexpectedly (e.g., empty Table 1 cohort), generate a full data inventory:

```bash
python scripts/diagnose_phi_data.py
```

Outputs:
- `outputs/diagnostics/phi_data_diagnostic.md` (human-readable)
- `outputs/diagnostics/phi_data_diagnostic.json` (machine-readable)

## Village names

Placeholder `Village_*` labels in the medevac CSVs were replaced with **Maniilaq community names** using rank alignment to reference journey shares. See **`docs/village_name_codebook.md`** and **`docs/village_name_codebook.csv`**. To re-apply after restoring anonymous data: `python scripts/apply_village_names.py`.

## Data sources

| File | Role |
|------|------|
| `data/pediatric_medevac_journeys.csv` | Journey patterns, locations, medevac legs, duration |
| `data/pediatric_medevac_timing.csv` | Activation / flight / ground-time metrics |
| `data/pediatric_outcomes.csv` | Mortality, discharge, length of stay proxies |
| `data/pediatric_patients.csv` | Gender (merged for future stratification) |
| `data/pediatric_chiefcomplaints.csv` | Journey chief-complaint extract; **Table 3** uses village **CEDIS code + complaint** |

## Outputs

- **`outputs/tables/`** — CSV tables for manuscripts or supplements  
- **`outputs/figures/`** — PNG figures (temporal trend, origin mix, duration, timing scatter, medevacs per journey)

- **Table 0** (`table0_medevac_routes.csv`): **Origin**, **Destination**, **Medevacs n (%)**; sorted by count descending; **All legs** last.
- **Table 1+** (and figures except the map): cohort = journeys with ≥1 **village→MHC (CAH)** leg; *n* in Table 1 title = leg count.
- **Table 1** (`table1_patient_characteristics.csv`): **n (%)** by patient; **Age Groups, n(%)** + subrows; **Origin Village, n(%)** + subrows (by n descending); no non-village row. Optional: **`AI_AN`**, **`RaceDSC`**, **`PrimaryPayorNM`**.
- **Table 2** (`table2_village_visit_vitals.csv`): complete-vitals rate (HR, O2, BP sys+dia, RR, Temp) by cohort/age/village.
- **Table 2.1** (`table2_1_vitals_missingness.csv`): patient-level missingness `n(%)` for each vital measure.
- **Table 2.2** (`table2_2_vitals_repeated.csv`): patient-level repeat rate `n(%)` with >1 value for each vital measure.
- **Table 3** (`table3_chief_complaints_overall.csv`): top 10 village **CEDIS code + complaint** pairs per journey (first non-missing village CEDIS slot); **%** of cohort journeys. **Tables 3.1–3.4** (`table3_1` … `table3_4_chief_complaints.csv`): same within age bucket; **%** of journeys in that age group.
- **Table 3.5** (`table3_followup_prior_visit_check.csv`): validation for **Follow-up visit (CEDIS 888)** showing how often the journey has a prior encounter in `pediatric_missed_opportunities.csv` (`days_until_medevac > 0`).

Extend `medevac_summaries.py` to add models, chief-complaint stratification, or facility-level summaries.
