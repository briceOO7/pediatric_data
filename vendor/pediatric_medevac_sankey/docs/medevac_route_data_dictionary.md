# Medevac Route Figure Input

`scripts/medevac_sankey_manuscript.R` can run on a PHI-bearing machine without copying row-level data into this repository.

## Reproducible R Setup

This repository uses `renv`. After cloning or copying the repository to the PHI-bearing machine, restore the R environment once:

```r
install.packages("renv")
renv::restore()
```

`renv::restore()` reads `renv.lock` and installs the exact plotting package versions used by the figure script into the project-local `renv/library/` folder. Do not commit `renv/library/`; it is intentionally ignored.

## Run Figure Generation

Run with either:

```bash
Rscript scripts/medevac_sankey_manuscript.R /secure/path/medevac_routes.csv
```

or:

```bash
MEDEVAC_ROUTES_CSV=/secure/path/medevac_routes.csv Rscript scripts/medevac_sankey_manuscript.R
```

## Accepted CSV Formats

The script accepts either row-level route data or aggregate leg-count data.

### Row-Level Route Data

The script only needs these three route-defining columns:

| column | type | description |
| --- | --- | --- |
| `village` | string | Origin village or village clinic name. |
| `mhc` | boolean-ish | Whether the journey stopped at Maniilaq Health Center. Accepted true values include `TRUE`, `1`, `yes`, `MHC`, `Maniilaq`, and `Maniilaq Health Center`. Accepted false values include `FALSE`, `0`, `no`, and `direct`. |
| `receiving_facility` | string or blank | Final receiving facility if the patient was transferred beyond the village clinic/MHC path. Leave blank for journeys ending at MHC without secondary transfer. |

Do not include names, MRNs, DOBs, addresses, dates, notes, diagnoses, or other PHI in the CSV used for figure generation.

Direct village-to-receiving-facility journeys should be encoded only as rows where `mhc` is false and `receiving_facility` is populated. If the final dataset has only one village with direct transfers, only that village should have such rows; the script will draw only those direct links.

Example row-level format:

```csv
village,mhc,receiving_facility
Village A,TRUE,
Village A,TRUE,Facility X
Village A,FALSE,Facility X
Village B,TRUE,
Village C,TRUE,Facility Y
```

### Aggregate Leg-Count Data

Use this format when you have already summarized the data into leg counts:

| column | type | description |
| --- | --- | --- |
| `leg_type` | string | `primary`, `secondary`, or `direct`. Primary rows are village-to-MHC legs. Secondary rows are MHC-to-receiving-facility escalation legs. Direct rows are village-to-receiving-facility legs that bypass MHC. |
| `origin` | string | Village name for primary/direct rows; MHC or another transfer point for secondary rows. |
| `destination` | string | Destination for that leg. |
| `n_legs` | integer | Count of legs for that origin-destination pair. |
| `percent` | optional string | Optional reporting percent. The script ignores this and recomputes figures from `n_legs`. |

Example aggregate format:

```csv
leg_type,origin,destination,n_legs,percent
primary,Buckland,MHC,75,24.3%
secondary,MHC,ANMC,30,90.9%
```

## Privacy Behavior

The script reads the local CSV, immediately aggregates to village and facility counts, and writes only de-identified figure files to `figures/`. It prints the input file path but does not print row-level records.
