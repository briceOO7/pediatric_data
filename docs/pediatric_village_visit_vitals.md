# Village visit vitals (Table 2)

**Table 2** loads the first file found among:

1. `data/pediatric_village_visit_vitals.csv` (preferred label)
2. `data/pediatric_vitals_wide.csv` (journey-level medians: `HR_median`, `SpO2_median`, `Systolic_median`, `Diastolic_median`, `RR_median`, `Temperature_median`)

Override path: `MEDEVAC_VITALS_CSV=/path/to/file.csv`.

## Complete vital set

A row counts as **complete** if **all** of the following are non-missing on that row:

| Vital | Role | Example column names |
|-------|------|----------------------|
| HR | Heart rate | `hr`, `HR`, `heart_rate`, `vital_hr`, `Pulse` |
| O2 | Oxygen saturation | `spo2`, `SpO2`, `o2_sat`, `O2`, `vital_o2` |
| BP (systolic) | SBP | `bp_systolic`, `sbp`, `SBP`, `vital_bp_systolic` |
| BP (diastolic) | DBP | `bp_diastolic`, `dbp`, `DBP`, `vital_bp_diastolic` |
| RR | Respiratory rate | `rr`, `RR`, `respiratory_rate`, `vital_rr` |
| Temp | Temperature | `temp`, `Temp`, `temperature`, `vital_temp` |

**Patient-level rule:** a patient is counted as having complete vitals if **at least one row** for their `MRN` is complete (e.g. one encounter with all six values).

## Required column

- **`MRN`** (or `mrn`, `patient_mrn`) — must match `MRN` on the medevac cohort.

## Rows

- One row per vital **set** / **time point** (wide format), **or** multiple rows per visit if each row still has all six measures (e.g. duplicate rows are fine; any qualifying row suffices).

## PHI extract

Export vitals documented at the **village / clinic visit** associated with the medevac journey (same patient, visit before transfer to MHC). Align `MRN` with `pediatric_medevac_journeys.csv`.
