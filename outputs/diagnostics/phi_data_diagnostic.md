# PHI Data Diagnostic Report

- Root: `/Users/brianrice/CursorProjects/pediatric_data`
- Data dir: `/Users/brianrice/CursorProjects/pediatric_data/data`

## Pipeline Checks
- **cohort_journeys_n**: `296`
- **cohort_patients_n**: `259`
- **cohort_sample_journey_ids**: 20 entries
- **journeys_columns**: 91 entries
- **journeys_read_ok**: `True`
- **journeys_row_count**: `384`
- **load_data_columns**: 122 entries
- **load_data_row_count**: `384`
- **outcomes_columns**: 24 entries
- **patients_columns**: 3 entries
- **required_files_present**: `{'pediatric_medevac_journeys.csv': True, 'pediatric_medevac_timing.csv': True, 'pediatric_outcomes.csv': True, 'pediatric_patients.csv': True}`
- **timing_overlapping_columns_with_journeys_excluding_keys**: 0 entries
- **top_values__MRN**: 15 entries
- **top_values__facility_1_name**: 12 entries
- **top_values__journey_id**: 15 entries
- **top_values__journey_start_date**: 0 entries
- **top_values__medevac1_date**: 0 entries
- **top_values__medevac1_from**: 12 entries
- **top_values__medevac1_to**: 3 entries
- **top_values__medevac2_from**: 2 entries
- **top_values__medevac2_to**: 4 entries
- **top_values__medevac3_from**: 0 entries
- **top_values__medevac3_to**: 0 entries
- **village_origin_mode_runtime**: `infer`
- **village_to_mhc_legs_count**: `296`

## CSV Inventory
### `pediatric_chiefcomplaints.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_chiefcomplaints.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (109):
  - `journey_id`
  - `MRN`
  - `origin_type`
  - `village_cc_1`
  - `village_cedis_code_1`
  - `village_cedis_complaint_1`
  - `village_cc_2`
  - `village_cedis_code_2`
  - `village_cedis_complaint_2`
  - `village_cc_3`
  - `village_cedis_code_3`
  - `village_cedis_complaint_3`
  - `village_cc_4`
  - `village_cedis_code_4`
  - `village_cedis_complaint_4`
  - `village_cc_5`
  - `village_cedis_code_5`
  - `village_cedis_complaint_5`
  - `village_cc_6`
  - `village_cedis_code_6`
  - `village_cedis_complaint_6`
  - `village_cc_7`
  - `village_cedis_code_7`
  - `village_cedis_complaint_7`
  - `village_cc_8`
  - `village_cedis_code_8`
  - `village_cedis_complaint_8`
  - `village_cc_9`
  - `village_cedis_code_9`
  - `village_cedis_complaint_9`
  - `village_cc_10`
  - `village_cedis_code_10`
  - `village_cedis_complaint_10`
  - `village_cc_11`
  - `village_cedis_code_11`
  - `village_cedis_complaint_11`
  - `village_cc_12`
  - `village_cedis_code_12`
  - `village_cedis_complaint_12`
  - `village_cc_13`
  - `village_cedis_code_13`
  - `village_cedis_complaint_13`
  - `village_cc_14`
  - `village_cedis_code_14`
  - `village_cedis_complaint_14`
  - `village_cc_15`
  - `village_cedis_code_15`
  - `village_cedis_complaint_15`
  - `village_cc_16`
  - `village_cedis_code_16`
  - `village_cedis_complaint_16`
  - `village_cc_17`
  - `village_cedis_code_17`
  - `village_cedis_complaint_17`
  - `village_cc_18`
  - `village_cedis_code_18`
  - `village_cedis_complaint_18`
  - `village_cc_19`
  - `village_cedis_code_19`
  - `village_cedis_complaint_19`
  - `mhc_ed_cc_1`
  - `mhc_ed_cedis_code_1`
  - `mhc_ed_cedis_complaint_1`
  - `mhc_ed_cc_2`
  - `mhc_ed_cedis_code_2`
  - `mhc_ed_cedis_complaint_2`
  - `mhc_ed_cc_3`
  - `mhc_ed_cedis_code_3`
  - `mhc_ed_cedis_complaint_3`
  - `mhc_ed_cc_4`
  - `mhc_ed_cedis_code_4`
  - `mhc_ed_cedis_complaint_4`
  - `mhc_ed_cc_5`
  - `mhc_ed_cedis_code_5`
  - `mhc_ed_cedis_complaint_5`
  - `mhc_ed_cc_6`
  - `mhc_ed_cedis_code_6`
  - `mhc_ed_cedis_complaint_6`
  - `mhc_ed_cc_7`
  - `mhc_ed_cedis_code_7`
  - `mhc_ed_cedis_complaint_7`
  - `mhc_ed_cc_8`
  - `mhc_ed_cedis_code_8`
  - `mhc_ed_cedis_complaint_8`
  - `mhc_inpatient_cc_1`
  - `mhc_inpatient_cedis_code_1`
  - `mhc_inpatient_cedis_complaint_1`
  - `mhc_inpatient_cc_2`
  - `mhc_inpatient_cedis_code_2`
  - `mhc_inpatient_cedis_complaint_2`
  - `mhc_inpatient_cc_3`
  - `mhc_inpatient_cedis_code_3`
  - `mhc_inpatient_cedis_complaint_3`
  - `mhc_inpatient_cc_4`
  - `mhc_inpatient_cedis_code_4`
  - `mhc_inpatient_cedis_complaint_4`
  - `mhc_inpatient_cc_5`
  - `mhc_inpatient_cedis_code_5`
  - `mhc_inpatient_cedis_complaint_5`
  - `anmc_ed_cc_1`
  - `anmc_ed_cedis_code_1`
  - `anmc_ed_cedis_complaint_1`
  - `anmc_ed_cc_2`
  - `anmc_ed_cedis_code_2`
  - `anmc_ed_cedis_complaint_2`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `origin_type` | `str` | 384 | 100.0 | 2 |
| `village_cc_1` | `str` | 327 | 85.2 | 2 |
| `village_cedis_code_1` | `float64` | 327 | 85.2 | 2 |
| `village_cedis_complaint_1` | `str` | 327 | 85.2 | 2 |
| `village_cc_2` | `str` | 246 | 64.1 | 2 |
| `village_cedis_code_2` | `float64` | 246 | 64.1 | 2 |
| `village_cedis_complaint_2` | `str` | 246 | 64.1 | 2 |
| `village_cc_3` | `str` | 162 | 42.2 | 3 |
| `village_cedis_code_3` | `float64` | 162 | 42.2 | 3 |
| `village_cedis_complaint_3` | `str` | 162 | 42.2 | 3 |
| `village_cc_4` | `str` | 102 | 26.6 | 4 |
| `village_cedis_code_4` | `float64` | 102 | 26.6 | 4 |
| `village_cedis_complaint_4` | `str` | 102 | 26.6 | 4 |
| `village_cc_5` | `str` | 49 | 12.8 | 5 |
| `village_cedis_code_5` | `float64` | 49 | 12.8 | 5 |
| `village_cedis_complaint_5` | `str` | 49 | 12.8 | 5 |
| `village_cc_6` | `str` | 30 | 7.8 | 6 |
| `village_cedis_code_6` | `float64` | 30 | 7.8 | 6 |
| `village_cedis_complaint_6` | `str` | 30 | 7.8 | 6 |
| `village_cc_7` | `str` | 16 | 4.2 | 6 |
| `village_cedis_code_7` | `float64` | 16 | 4.2 | 6 |
| `village_cedis_complaint_7` | `str` | 16 | 4.2 | 6 |
| `village_cc_8` | `str` | 10 | 2.6 | 6 |
| `village_cedis_code_8` | `float64` | 10 | 2.6 | 6 |
| `village_cedis_complaint_8` | `str` | 10 | 2.6 | 6 |
| `village_cc_9` | `str` | 6 | 1.6 | 37 |
| `village_cedis_code_9` | `float64` | 6 | 1.6 | 37 |
| `village_cedis_complaint_9` | `str` | 6 | 1.6 | 37 |
| `village_cc_10` | `str` | 1 | 0.3 | 194 |
| `village_cedis_code_10` | `float64` | 1 | 0.3 | 194 |
| `village_cedis_complaint_10` | `str` | 1 | 0.3 | 194 |
| `village_cc_11` | `str` | 1 | 0.3 | 194 |
| `village_cedis_code_11` | `float64` | 1 | 0.3 | 194 |
| `village_cedis_complaint_11` | `str` | 1 | 0.3 | 194 |
| `village_cc_12` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_12` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_12` | `float64` | 0 | 0.0 | None |
| `village_cc_13` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_13` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_13` | `float64` | 0 | 0.0 | None |
| `village_cc_14` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_14` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_14` | `float64` | 0 | 0.0 | None |
| `village_cc_15` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_15` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_15` | `float64` | 0 | 0.0 | None |
| `village_cc_16` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_16` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_16` | `float64` | 0 | 0.0 | None |
| `village_cc_17` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_17` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_17` | `float64` | 0 | 0.0 | None |
| `village_cc_18` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_18` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_18` | `float64` | 0 | 0.0 | None |
| `village_cc_19` | `float64` | 0 | 0.0 | None |
| `village_cedis_code_19` | `float64` | 0 | 0.0 | None |
| `village_cedis_complaint_19` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cc_1` | `str` | 230 | 59.9 | 2 |
| `mhc_ed_cedis_code_1` | `float64` | 230 | 59.9 | 2 |
| `mhc_ed_cedis_complaint_1` | `str` | 230 | 59.9 | 2 |
| `mhc_ed_cc_2` | `str` | 81 | 21.1 | 5 |
| `mhc_ed_cedis_code_2` | `float64` | 81 | 21.1 | 5 |
| `mhc_ed_cedis_complaint_2` | `str` | 81 | 21.1 | 5 |
| `mhc_ed_cc_3` | `str` | 20 | 5.2 | 8 |
| `mhc_ed_cedis_code_3` | `float64` | 20 | 5.2 | 8 |
| `mhc_ed_cedis_complaint_3` | `str` | 20 | 5.2 | 8 |
| `mhc_ed_cc_4` | `str` | 4 | 1.0 | 74 |
| `mhc_ed_cedis_code_4` | `float64` | 4 | 1.0 | 74 |
| `mhc_ed_cedis_complaint_4` | `str` | 4 | 1.0 | 74 |
| `mhc_ed_cc_5` | `str` | 3 | 0.8 | 74 |
| `mhc_ed_cedis_code_5` | `float64` | 3 | 0.8 | 74 |
| `mhc_ed_cedis_complaint_5` | `str` | 3 | 0.8 | 74 |
| `mhc_ed_cc_6` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_code_6` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_complaint_6` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cc_7` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_code_7` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_complaint_7` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cc_8` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_code_8` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cedis_complaint_8` | `float64` | 0 | 0.0 | None |
| `mhc_inpatient_cc_1` | `str` | 140 | 36.5 | 2 |
| `mhc_inpatient_cedis_code_1` | `float64` | 140 | 36.5 | 2 |
| `mhc_inpatient_cedis_complaint_1` | `str` | 140 | 36.5 | 2 |
| `mhc_inpatient_cc_2` | `str` | 25 | 6.5 | 27 |
| `mhc_inpatient_cedis_code_2` | `float64` | 25 | 6.5 | 27 |
| `mhc_inpatient_cedis_complaint_2` | `str` | 25 | 6.5 | 27 |
| `mhc_inpatient_cc_3` | `str` | 3 | 0.8 | 140 |
| `mhc_inpatient_cedis_code_3` | `float64` | 3 | 0.8 | 140 |
| `mhc_inpatient_cedis_complaint_3` | `str` | 3 | 0.8 | 140 |
| `mhc_inpatient_cc_4` | `str` | 2 | 0.5 | 140 |
| `mhc_inpatient_cedis_code_4` | `float64` | 2 | 0.5 | 140 |
| `mhc_inpatient_cedis_complaint_4` | `str` | 2 | 0.5 | 140 |
| `mhc_inpatient_cc_5` | `float64` | 0 | 0.0 | None |
| `mhc_inpatient_cedis_code_5` | `float64` | 0 | 0.0 | None |
| `mhc_inpatient_cedis_complaint_5` | `float64` | 0 | 0.0 | None |
| `anmc_ed_cc_1` | `str` | 3 | 0.8 | 149 |
| `anmc_ed_cedis_code_1` | `float64` | 3 | 0.8 | 149 |
| `anmc_ed_cedis_complaint_1` | `str` | 3 | 0.8 | 149 |
| `anmc_ed_cc_2` | `float64` | 0 | 0.0 | None |
| `anmc_ed_cedis_code_2` | `float64` | 0 | 0.0 | None |
| `anmc_ed_cedis_complaint_2` | `float64` | 0 | 0.0 | None |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_chiefcomplaints_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_chiefcomplaints_long.csv`
- Read OK: `True`
- Line count (with header): `1`
- Rows: `0`
- Columns (16):
  - `journey_id`
  - `MRN`
  - `medevac_cc`
  - `medevac_cc_category`
  - `village_cc_category`
  - `mhc_ed_cc_category`
  - `mhc_inpatient_cc_category`
  - `anmc_ed_cc_category`
  - `anmc_inpatient_cc_category`
  - `origin_type`
  - `facility_phase`
  - `cc_text`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `object` | 0 | None | None |
| `MRN` | `object` | 0 | None | None |
| `medevac_cc` | `object` | 0 | None | None |
| `medevac_cc_category` | `object` | 0 | None | None |
| `village_cc_category` | `object` | 0 | None | None |
| `mhc_ed_cc_category` | `object` | 0 | None | None |
| `mhc_inpatient_cc_category` | `object` | 0 | None | None |
| `anmc_ed_cc_category` | `object` | 0 | None | None |
| `anmc_inpatient_cc_category` | `object` | 0 | None | None |
| `origin_type` | `object` | 0 | None | None |
| `facility_phase` | `object` | 0 | None | None |
| `cc_text` | `object` | 0 | None | None |
| `age_at_medevac` | `object` | 0 | None | None |
| `age_at_death` | `object` | 0 | None | None |
| `journey_start_month` | `object` | 0 | None | None |
| `journey_start_year` | `object` | 0 | None | None |

### `pediatric_chiefcomplaints_wide.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_chiefcomplaints_wide.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (19):
  - `journey_id`
  - `MRN`
  - `medevac_cc`
  - `village_cc`
  - `mhc_ed_cc`
  - `mhc_inpatient_cc`
  - `anmc_ed_cc`
  - `anmc_inpatient_cc`
  - `medevac_cc_category`
  - `village_cc_category`
  - `mhc_ed_cc_category`
  - `mhc_inpatient_cc_category`
  - `anmc_ed_cc_category`
  - `anmc_inpatient_cc_category`
  - `origin_type`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `medevac_cc` | `float64` | 0 | 0.0 | None |
| `village_cc` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cc` | `float64` | 0 | 0.0 | None |
| `mhc_inpatient_cc` | `float64` | 0 | 0.0 | None |
| `anmc_ed_cc` | `float64` | 0 | 0.0 | None |
| `anmc_inpatient_cc` | `float64` | 0 | 0.0 | None |
| `medevac_cc_category` | `float64` | 0 | 0.0 | None |
| `village_cc_category` | `float64` | 0 | 0.0 | None |
| `mhc_ed_cc_category` | `float64` | 0 | 0.0 | None |
| `mhc_inpatient_cc_category` | `float64` | 0 | 0.0 | None |
| `anmc_ed_cc_category` | `float64` | 0 | 0.0 | None |
| `anmc_inpatient_cc_category` | `float64` | 0 | 0.0 | None |
| `origin_type` | `str` | 384 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_diagnoses.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_diagnoses.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (2):
  - `journey_id`
  - `MRN`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |

### `pediatric_diagnoses_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_diagnoses_long.csv`
- Read OK: `True`
- Line count (with header): `2608`
- Rows: `2607`
- Columns (13):
  - `journey_id`
  - `MRN`
  - `DiagnosisCD`
  - `DiagnosisDSC`
  - `DiagnosisType`
  - `diagnosis_category`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `journey_end_date_hours_from_start`
  - `DiagnosisStartDTS_hours_from_start`
  - `DiagnosisEndDTS_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 2607 | 100.0 | 2 |
| `MRN` | `str` | 2607 | 100.0 | 2 |
| `DiagnosisCD` | `str` | 2607 | 100.0 | 2 |
| `DiagnosisDSC` | `str` | 2607 | 100.0 | 2 |
| `DiagnosisType` | `str` | 2607 | 100.0 | 2 |
| `diagnosis_category` | `str` | 2607 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 2607 | 100.0 | 2 |
| `age_at_death` | `float64` | 39 | 1.5 | 1045 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `journey_end_date_hours_from_start` | `float64` | 2607 | 100.0 | 2 |
| `DiagnosisStartDTS_hours_from_start` | `float64` | 2607 | 100.0 | 2 |
| `DiagnosisEndDTS_hours_from_start` | `float64` | 2607 | 100.0 | 2 |

### `pediatric_diagnoses_wide.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_diagnoses_wide.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (14):
  - `journey_id`
  - `MRN`
  - `primary_admit`
  - `primary_discharge`
  - `secondary_admit`
  - `secondary_discharge`
  - `journey_old_diagnoses`
  - `old_diagnosis_count`
  - `new_diagnosis_count`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `journey_end_date_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `primary_admit` | `str` | 284 | 74.0 | 2 |
| `primary_discharge` | `str` | 379 | 98.7 | 2 |
| `secondary_admit` | `str` | 9 | 2.3 | 16 |
| `secondary_discharge` | `str` | 361 | 94.0 | 2 |
| `journey_old_diagnoses` | `str` | 160 | 41.7 | 3 |
| `old_diagnosis_count` | `int64` | 384 | 100.0 | 2 |
| `new_diagnosis_count` | `int64` | 384 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `journey_end_date_hours_from_start` | `float64` | 384 | 100.0 | 2 |

### `pediatric_facility_times.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_facility_times.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (16):
  - `journey_id`
  - `MRN`
  - `facility_1_name`
  - `facility_1_time`
  - `facility_2_name`
  - `facility_2_time`
  - `facility_3_name`
  - `facility_3_time`
  - `facility_4_name`
  - `facility_4_time`
  - `death_at_facility`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `journey_end_date_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `facility_1_name` | `str` | 384 | 100.0 | 2 |
| `facility_1_time` | `float64` | 0 | 0.0 | None |
| `facility_2_name` | `str` | 380 | 99.0 | 2 |
| `facility_2_time` | `float64` | 0 | 0.0 | None |
| `facility_3_name` | `str` | 50 | 13.0 | 7 |
| `facility_3_time` | `float64` | 0 | 0.0 | None |
| `facility_4_name` | `float64` | 0 | 0.0 | None |
| `facility_4_time` | `float64` | 0 | 0.0 | None |
| `death_at_facility` | `str` | 3 | 0.8 | 168 |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `journey_end_date_hours_from_start` | `float64` | 384 | 100.0 | 2 |

### `pediatric_medevac_journeys.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_medevac_journeys.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (91):
  - `journey_id`
  - `MRN`
  - `journey_duration_hours`
  - `journey_end_reason`
  - `num_medevacs`
  - `num_encounters`
  - `journey_pattern`
  - `loc1`
  - `loc1_dept`
  - `loc1_encounter_id`
  - `loc1_medevac_id`
  - `loc2`
  - `loc2_dept`
  - `loc2_encounter_id`
  - `loc2_medevac_id`
  - `loc3`
  - `loc3_dept`
  - `loc3_encounter_id`
  - `loc3_medevac_id`
  - `loc4`
  - `loc4_dept`
  - `loc4_encounter_id`
  - `loc4_medevac_id`
  - `loc5`
  - `loc5_dept`
  - `loc5_encounter_id`
  - `loc5_medevac_id`
  - `loc6`
  - `loc6_dept`
  - `loc6_start`
  - `loc6_end`
  - `loc6_encounter_id`
  - `loc6_medevac_id`
  - `facility_1_name`
  - `facility_1_time`
  - `facility_2_name`
  - `facility_2_time`
  - `facility_3_name`
  - `facility_3_time`
  - `facility_4_name`
  - `facility_4_time`
  - `medevac1_id`
  - `medevac1_date`
  - `medevac1_dts`
  - `medevac1_dts_source`
  - `medevac1_from`
  - `medevac1_to`
  - `medevac1_from_encounter`
  - `medevac1_to_encounter`
  - `medevac1_match_score`
  - `medevac1_exclusion_category`
  - `medevac2_id`
  - `medevac2_date`
  - `medevac2_dts`
  - `medevac2_dts_source`
  - `medevac2_from`
  - `medevac2_to`
  - `medevac2_from_encounter`
  - `medevac2_to_encounter`
  - `medevac2_match_score`
  - `medevac2_exclusion_category`
  - `medevac3_id`
  - `medevac3_date`
  - `medevac3_dts`
  - `medevac3_dts_source`
  - `medevac3_from`
  - `medevac3_to`
  - `medevac3_from_encounter`
  - `medevac3_to_encounter`
  - `medevac3_match_score`
  - `medevac3_exclusion_category`
  - `total_locations`
  - `has_village_start`
  - `has_hub_end`
  - `has_outside_end`
  - `age_at_medevac`
  - `age_at_death`
  - `origin_type`
  - `journey_start_month`
  - `journey_start_year`
  - `journey_end_date_hours_from_start`
  - `loc1_start_hours_from_start`
  - `loc1_end_hours_from_start`
  - `loc2_start_hours_from_start`
  - `loc2_end_hours_from_start`
  - `loc3_start_hours_from_start`
  - `loc3_end_hours_from_start`
  - `loc4_start_hours_from_start`
  - `loc4_end_hours_from_start`
  - `loc5_start_hours_from_start`
  - `loc5_end_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `journey_duration_hours` | `float64` | 384 | 100.0 | 2 |
| `journey_end_reason` | `float64` | 0 | 0.0 | None |
| `num_medevacs` | `int64` | 384 | 100.0 | 2 |
| `num_encounters` | `int64` | 384 | 100.0 | 2 |
| `journey_pattern` | `str` | 384 | 100.0 | 2 |
| `loc1` | `str` | 384 | 100.0 | 2 |
| `loc1_dept` | `str` | 384 | 100.0 | 2 |
| `loc1_encounter_id` | `str` | 384 | 100.0 | 2 |
| `loc1_medevac_id` | `float64` | 0 | 0.0 | None |
| `loc2` | `str` | 380 | 99.0 | 2 |
| `loc2_dept` | `str` | 380 | 99.0 | 2 |
| `loc2_encounter_id` | `str` | 380 | 99.0 | 2 |
| `loc2_medevac_id` | `float64` | 0 | 0.0 | None |
| `loc3` | `str` | 189 | 49.2 | 3 |
| `loc3_dept` | `str` | 189 | 49.2 | 3 |
| `loc3_encounter_id` | `str` | 187 | 48.7 | 3 |
| `loc3_medevac_id` | `float64` | 0 | 0.0 | None |
| `loc4` | `str` | 12 | 3.1 | 48 |
| `loc4_dept` | `str` | 12 | 3.1 | 48 |
| `loc4_encounter_id` | `str` | 10 | 2.6 | 48 |
| `loc4_medevac_id` | `float64` | 0 | 0.0 | None |
| `loc5` | `str` | 1 | 0.3 | 187 |
| `loc5_dept` | `str` | 1 | 0.3 | 187 |
| `loc5_encounter_id` | `str` | 1 | 0.3 | 187 |
| `loc5_medevac_id` | `float64` | 0 | 0.0 | None |
| `loc6` | `float64` | 0 | 0.0 | None |
| `loc6_dept` | `float64` | 0 | 0.0 | None |
| `loc6_start` | `float64` | 0 | 0.0 | None |
| `loc6_end` | `float64` | 0 | 0.0 | None |
| `loc6_encounter_id` | `float64` | 0 | 0.0 | None |
| `loc6_medevac_id` | `float64` | 0 | 0.0 | None |
| `facility_1_name` | `str` | 384 | 100.0 | 2 |
| `facility_1_time` | `float64` | 0 | 0.0 | None |
| `facility_2_name` | `str` | 380 | 99.0 | 2 |
| `facility_2_time` | `float64` | 0 | 0.0 | None |
| `facility_3_name` | `str` | 50 | 13.0 | 7 |
| `facility_3_time` | `float64` | 0 | 0.0 | None |
| `facility_4_name` | `float64` | 0 | 0.0 | None |
| `facility_4_time` | `float64` | 0 | 0.0 | None |
| `medevac1_id` | `int64` | 384 | 100.0 | 2 |
| `medevac1_date` | `float64` | 0 | 0.0 | None |
| `medevac1_dts` | `str` | 384 | 100.0 | 2 |
| `medevac1_dts_source` | `str` | 384 | 100.0 | 2 |
| `medevac1_from` | `str` | 384 | 100.0 | 2 |
| `medevac1_to` | `str` | 384 | 100.0 | 2 |
| `medevac1_from_encounter` | `str` | 384 | 100.0 | 2 |
| `medevac1_to_encounter` | `str` | 380 | 99.0 | 2 |
| `medevac1_match_score` | `float64` | 384 | 100.0 | 2 |
| `medevac1_exclusion_category` | `float64` | 0 | 0.0 | None |
| `medevac2_id` | `float64` | 34 | 8.9 | 17 |
| `medevac2_date` | `float64` | 0 | 0.0 | None |
| `medevac2_dts` | `str` | 34 | 8.9 | 17 |
| `medevac2_dts_source` | `str` | 34 | 8.9 | 17 |
| `medevac2_from` | `str` | 34 | 8.9 | 17 |
| `medevac2_to` | `str` | 34 | 8.9 | 17 |
| `medevac2_from_encounter` | `str` | 34 | 8.9 | 17 |
| `medevac2_to_encounter` | `str` | 30 | 7.8 | 17 |
| `medevac2_match_score` | `float64` | 34 | 8.9 | 17 |
| `medevac2_exclusion_category` | `float64` | 0 | 0.0 | None |
| `medevac3_id` | `float64` | 0 | 0.0 | None |
| `medevac3_date` | `float64` | 0 | 0.0 | None |
| `medevac3_dts` | `float64` | 0 | 0.0 | None |
| `medevac3_dts_source` | `float64` | 0 | 0.0 | None |
| `medevac3_from` | `float64` | 0 | 0.0 | None |
| `medevac3_to` | `float64` | 0 | 0.0 | None |
| `medevac3_from_encounter` | `float64` | 0 | 0.0 | None |
| `medevac3_to_encounter` | `float64` | 0 | 0.0 | None |
| `medevac3_match_score` | `float64` | 0 | 0.0 | None |
| `medevac3_exclusion_category` | `float64` | 0 | 0.0 | None |
| `total_locations` | `int64` | 384 | 100.0 | 2 |
| `has_village_start` | `float64` | 0 | 0.0 | None |
| `has_hub_end` | `float64` | 0 | 0.0 | None |
| `has_outside_end` | `float64` | 0 | 0.0 | None |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `origin_type` | `str` | 384 | 100.0 | 2 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `journey_end_date_hours_from_start` | `float64` | 384 | 100.0 | 2 |
| `loc1_start_hours_from_start` | `float64` | 384 | 100.0 | 2 |
| `loc1_end_hours_from_start` | `float64` | 384 | 100.0 | 2 |
| `loc2_start_hours_from_start` | `float64` | 380 | 99.0 | 2 |
| `loc2_end_hours_from_start` | `float64` | 380 | 99.0 | 2 |
| `loc3_start_hours_from_start` | `float64` | 189 | 49.2 | 3 |
| `loc3_end_hours_from_start` | `float64` | 189 | 49.2 | 3 |
| `loc4_start_hours_from_start` | `float64` | 12 | 3.1 | 48 |
| `loc4_end_hours_from_start` | `float64` | 12 | 3.1 | 48 |
| `loc5_start_hours_from_start` | `float64` | 1 | 0.3 | 187 |
| `loc5_end_hours_from_start` | `float64` | 1 | 0.3 | 187 |

### `pediatric_medevac_timing.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_medevac_timing.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (24):
  - `journey_id`
  - `MRN`
  - `origin_type`
  - `origin_imputed`
  - `origin_datetime_imputed`
  - `medevac_minutes`
  - `medevac_datetime`
  - `medevac_imputed`
  - `destination_minutes`
  - `destination_datetime`
  - `destination_imputed`
  - `imputed_data`
  - `flight_time_minutes`
  - `origin_facility`
  - `destination_facility`
  - `time_to_activate_min`
  - `activate_to_arrive_min`
  - `flight_time_min`
  - `medevac_time_minutes`
  - `activate_to_flight_minutes`
  - `decision_time_category`
  - `flight_time_category`
  - `flight_time_extended`
  - `decision_time_bin`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `origin_type` | `str` | 384 | 100.0 | 2 |
| `origin_imputed` | `bool` | 384 | 100.0 | 2 |
| `origin_datetime_imputed` | `bool` | 384 | 100.0 | 2 |
| `medevac_minutes` | `float64` | 384 | 100.0 | 2 |
| `medevac_datetime` | `str` | 384 | 100.0 | 2 |
| `medevac_imputed` | `bool` | 384 | 100.0 | 2 |
| `destination_minutes` | `float64` | 370 | 96.4 | 2 |
| `destination_datetime` | `str` | 370 | 96.4 | 2 |
| `destination_imputed` | `bool` | 384 | 100.0 | 2 |
| `imputed_data` | `bool` | 384 | 100.0 | 2 |
| `flight_time_minutes` | `float64` | 384 | 100.0 | 2 |
| `origin_facility` | `str` | 384 | 100.0 | 2 |
| `destination_facility` | `str` | 384 | 100.0 | 2 |
| `time_to_activate_min` | `float64` | 232 | 60.4 | 2 |
| `activate_to_arrive_min` | `float64` | 370 | 96.4 | 2 |
| `flight_time_min` | `float64` | 384 | 100.0 | 2 |
| `medevac_time_minutes` | `float64` | 384 | 100.0 | 2 |
| `activate_to_flight_minutes` | `float64` | 370 | 96.4 | 2 |
| `decision_time_category` | `str` | 384 | 100.0 | 2 |
| `flight_time_category` | `str` | 384 | 100.0 | 2 |
| `flight_time_extended` | `str` | 370 | 96.4 | 2 |
| `decision_time_bin` | `str` | 232 | 60.4 | 2 |

### `pediatric_meds_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_meds_long.csv`
- Read OK: `True`
- Line count (with header): `29127`
- Rows: `29126`
- Columns (22):
  - `observation_type`
  - `MRN`
  - `EncounterLocationDSC`
  - `EncounterDepartmentDSC`
  - `ObservationID`
  - `EncounterID`
  - `ObservationCD`
  - `ObservationDSC`
  - `vital_type`
  - `ValueTXT`
  - `ValueNBR`
  - `UnitOfMeasureCVDSC`
  - `EncounterTypeDSC`
  - `journey_id`
  - `facility_phase`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `EncounterStartDTS_hours_from_start`
  - `EncounterEndDTS_hours_from_start`
  - `EffectiveDTS_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `observation_type` | `str` | 29126 | 100.0 | 2 |
| `MRN` | `str` | 29126 | 100.0 | 2 |
| `EncounterLocationDSC` | `str` | 29126 | 100.0 | 2 |
| `EncounterDepartmentDSC` | `str` | 29126 | 100.0 | 2 |
| `ObservationID` | `float64` | 29126 | 100.0 | 2 |
| `EncounterID` | `str` | 29126 | 100.0 | 2 |
| `ObservationCD` | `float64` | 29126 | 100.0 | 2 |
| `ObservationDSC` | `str` | 29126 | 100.0 | 2 |
| `vital_type` | `float64` | 0 | 0.0 | None |
| `ValueTXT` | `str` | 29126 | 100.0 | 2 |
| `ValueNBR` | `float64` | 26082 | 89.5 | 2 |
| `UnitOfMeasureCVDSC` | `str` | 1198 | 4.1 | 2 |
| `EncounterTypeDSC` | `str` | 29126 | 100.0 | 2 |
| `journey_id` | `str` | 29126 | 100.0 | 2 |
| `facility_phase` | `str` | 29126 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 29126 | 100.0 | 2 |
| `age_at_death` | `float64` | 4734 | 16.3 | 481 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `EncounterStartDTS_hours_from_start` | `float64` | 29126 | 100.0 | 2 |
| `EncounterEndDTS_hours_from_start` | `float64` | 29126 | 100.0 | 2 |
| `EffectiveDTS_hours_from_start` | `float64` | 29126 | 100.0 | 2 |

### `pediatric_meds_wide.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_meds_wide.csv`
- Read OK: `True`
- Line count (with header): `381`
- Rows: `380`
- Columns (23):
  - `journey_id`
  - `MRN`
  - `med_analgesic_non_opioid`
  - `med_antibiotic`
  - `med_anticoagulant`
  - `med_antiviral`
  - `med_cardiac_med`
  - `med_diuretic`
  - `med_endocrine_met`
  - `med_gi_med`
  - `med_iv_fluid`
  - `med_neuro_psych`
  - `med_opioid`
  - `med_other_med`
  - `med_respiratory_med`
  - `med_sedative`
  - `med_steroid`
  - `med_vasopressor`
  - `med_vitamin_supplement`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 380 | 100.0 | 2 |
| `MRN` | `str` | 380 | 100.0 | 2 |
| `med_analgesic_non_opioid` | `float64` | 380 | 100.0 | 2 |
| `med_antibiotic` | `float64` | 380 | 100.0 | 2 |
| `med_anticoagulant` | `float64` | 380 | 100.0 | 2 |
| `med_antiviral` | `float64` | 380 | 100.0 | 2 |
| `med_cardiac_med` | `float64` | 380 | 100.0 | 2 |
| `med_diuretic` | `float64` | 380 | 100.0 | 2 |
| `med_endocrine_met` | `float64` | 0 | 0.0 | None |
| `med_gi_med` | `float64` | 380 | 100.0 | 2 |
| `med_iv_fluid` | `float64` | 380 | 100.0 | 2 |
| `med_neuro_psych` | `float64` | 380 | 100.0 | 2 |
| `med_opioid` | `float64` | 380 | 100.0 | 2 |
| `med_other_med` | `float64` | 380 | 100.0 | 2 |
| `med_respiratory_med` | `float64` | 380 | 100.0 | 2 |
| `med_sedative` | `float64` | 380 | 100.0 | 2 |
| `med_steroid` | `float64` | 380 | 100.0 | 2 |
| `med_vasopressor` | `float64` | 380 | 100.0 | 2 |
| `med_vitamin_supplement` | `float64` | 380 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 380 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 33 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_missed_opportunities.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_missed_opportunities.csv`
- Read OK: `True`
- Line count (with header): `187`
- Rows: `186`
- Columns (11):
  - `EncounterID`
  - `MRN`
  - `EncounterLocationDSC`
  - `EncounterDepartmentDSC`
  - `journey_id`
  - `downstream_journey_start`
  - `journey_duration_hours`
  - `journey_end_reason`
  - `days_until_medevac`
  - `age_at_medevac`
  - `age_at_death`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `EncounterID` | `str` | 186 | 100.0 | 2 |
| `MRN` | `str` | 186 | 100.0 | 2 |
| `EncounterLocationDSC` | `str` | 186 | 100.0 | 2 |
| `EncounterDepartmentDSC` | `str` | 186 | 100.0 | 2 |
| `journey_id` | `str` | 186 | 100.0 | 2 |
| `downstream_journey_start` | `str` | 186 | 100.0 | 2 |
| `journey_duration_hours` | `float64` | 186 | 100.0 | 2 |
| `journey_end_reason` | `str` | 186 | 100.0 | 2 |
| `days_until_medevac` | `float64` | 186 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 186 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 3.8 | 4 |

### `pediatric_observations.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_observations.csv`
- Read OK: `True`
- Line count (with header): `961`
- Rows: `960`
- Columns (2):
  - `EncounterID`
  - `MRN`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `EncounterID` | `str` | 960 | 100.0 | 2 |
| `MRN` | `str` | 960 | 100.0 | 2 |

### `pediatric_outcomes.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_outcomes.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (24):
  - `journey_id`
  - `MRN`
  - `origin_type`
  - `journey_end_reason`
  - `facility_1_name`
  - `facility_1_time`
  - `facility_2_name`
  - `facility_2_time`
  - `facility_3_name`
  - `facility_3_time`
  - `facility_4_name`
  - `facility_4_time`
  - `death_at_facility`
  - `days_to_discharge`
  - `days_to_death`
  - `24hr_mortality`
  - `7d_mortality`
  - `30d_mortality`
  - `ed_discharge`
  - `short_<36h_admission`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `origin_type` | `str` | 384 | 100.0 | 2 |
| `journey_end_reason` | `float64` | 0 | 0.0 | None |
| `facility_1_name` | `str` | 384 | 100.0 | 2 |
| `facility_1_time` | `float64` | 0 | 0.0 | None |
| `facility_2_name` | `str` | 380 | 99.0 | 2 |
| `facility_2_time` | `float64` | 0 | 0.0 | None |
| `facility_3_name` | `str` | 50 | 13.0 | 7 |
| `facility_3_time` | `float64` | 0 | 0.0 | None |
| `facility_4_name` | `float64` | 0 | 0.0 | None |
| `facility_4_time` | `float64` | 0 | 0.0 | None |
| `death_at_facility` | `str` | 3 | 0.8 | 168 |
| `days_to_discharge` | `float64` | 384 | 100.0 | 2 |
| `days_to_death` | `float64` | 7 | 1.8 | 146 |
| `24hr_mortality` | `int64` | 384 | 100.0 | 2 |
| `7d_mortality` | `int64` | 384 | 100.0 | 2 |
| `30d_mortality` | `int64` | 384 | 100.0 | 2 |
| `ed_discharge` | `int64` | 384 | 100.0 | 2 |
| `short_<36h_admission` | `int64` | 384 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_patients.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_patients.csv`
- Read OK: `True`
- Line count (with header): `335`
- Rows: `334`
- Columns (3):
  - `MRN`
  - `GenderDSC`
  - `age_at_death`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `MRN` | `str` | 334 | 100.0 | 2 |
| `GenderDSC` | `str` | 334 | 100.0 | 2 |
| `age_at_death` | `float64` | 5 | 1.5 | 30 |

### `pediatric_pmh.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_pmh.csv`
- Read OK: `True`
- Line count (with header): `381`
- Rows: `380`
- Columns (8):
  - `journey_id`
  - `MRN`
  - `pmh_diagnoses`
  - `pmh_diagnosis_count`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 380 | 100.0 | 2 |
| `MRN` | `str` | 380 | 100.0 | 2 |
| `pmh_diagnoses` | `str` | 66 | 17.4 | 315 |
| `pmh_diagnosis_count` | `int64` | 380 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 380 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_poc_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_poc_long.csv`
- Read OK: `True`
- Line count (with header): `634`
- Rows: `633`
- Columns (22):
  - `observation_type`
  - `MRN`
  - `EncounterLocationDSC`
  - `EncounterDepartmentDSC`
  - `ObservationID`
  - `EncounterID`
  - `ObservationCD`
  - `ObservationDSC`
  - `vital_type`
  - `ValueTXT`
  - `ValueNBR`
  - `UnitOfMeasureCVDSC`
  - `EncounterTypeDSC`
  - `journey_id`
  - `facility_phase`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `EncounterStartDTS_hours_from_start`
  - `EncounterEndDTS_hours_from_start`
  - `EffectiveDTS_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `observation_type` | `str` | 633 | 100.0 | 2 |
| `MRN` | `str` | 633 | 100.0 | 2 |
| `EncounterLocationDSC` | `str` | 633 | 100.0 | 2 |
| `EncounterDepartmentDSC` | `str` | 633 | 100.0 | 2 |
| `ObservationID` | `float64` | 633 | 100.0 | 2 |
| `EncounterID` | `str` | 633 | 100.0 | 2 |
| `ObservationCD` | `float64` | 633 | 100.0 | 2 |
| `ObservationDSC` | `str` | 633 | 100.0 | 2 |
| `vital_type` | `float64` | 0 | 0.0 | None |
| `ValueTXT` | `str` | 633 | 100.0 | 2 |
| `ValueNBR` | `float64` | 152 | 24.0 | 2 |
| `UnitOfMeasureCVDSC` | `str` | 106 | 16.7 | 2 |
| `EncounterTypeDSC` | `str` | 633 | 100.0 | 2 |
| `journey_id` | `str` | 633 | 100.0 | 2 |
| `facility_phase` | `str` | 633 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 633 | 100.0 | 2 |
| `age_at_death` | `float64` | 25 | 3.9 | 54 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `EncounterStartDTS_hours_from_start` | `float64` | 633 | 100.0 | 2 |
| `EncounterEndDTS_hours_from_start` | `float64` | 633 | 100.0 | 2 |
| `EffectiveDTS_hours_from_start` | `float64` | 633 | 100.0 | 2 |

### `pediatric_poc_wide.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_poc_wide.csv`
- Read OK: `True`
- Line count (with header): `381`
- Rows: `380`
- Columns (16):
  - `journey_id`
  - `MRN`
  - `poc_coag`
  - `poc_covid`
  - `poc_flu`
  - `poc_glucose`
  - `poc_hemoglobin`
  - `poc_other_poc`
  - `poc_pocus`
  - `poc_site_meta`
  - `poc_strep`
  - `poc_urine`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 380 | 100.0 | 2 |
| `MRN` | `str` | 380 | 100.0 | 2 |
| `poc_coag` | `float64` | 380 | 100.0 | 2 |
| `poc_covid` | `float64` | 380 | 100.0 | 2 |
| `poc_flu` | `float64` | 380 | 100.0 | 2 |
| `poc_glucose` | `float64` | 380 | 100.0 | 2 |
| `poc_hemoglobin` | `float64` | 380 | 100.0 | 2 |
| `poc_other_poc` | `float64` | 380 | 100.0 | 2 |
| `poc_pocus` | `float64` | 380 | 100.0 | 2 |
| `poc_site_meta` | `float64` | 380 | 100.0 | 2 |
| `poc_strep` | `float64` | 380 | 100.0 | 2 |
| `poc_urine` | `float64` | 380 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 380 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 33 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_problem_list.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_problem_list.csv`
- Read OK: `True`
- Line count (with header): `385`
- Rows: `384`
- Columns (8):
  - `journey_id`
  - `MRN`
  - `problem_list`
  - `problem_list_count`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 384 | 100.0 | 2 |
| `MRN` | `str` | 384 | 100.0 | 2 |
| `problem_list` | `str` | 362 | 94.3 | 3 |
| `problem_list_count` | `int64` | 384 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 384 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 146 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `pediatric_problem_list_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_problem_list_long.csv`
- Read OK: `True`
- Line count (with header): `5722`
- Rows: `5721`
- Columns (12):
  - `journey_id`
  - `MRN`
  - `DiagnosisCD`
  - `DiagnosisDSC`
  - `DiagnosisType`
  - `days_prior`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `DiagnosisStartDTS_hours_from_start`
  - `DiagnosisEndDTS_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 5721 | 100.0 | 2 |
| `MRN` | `str` | 5721 | 100.0 | 2 |
| `DiagnosisCD` | `str` | 5721 | 100.0 | 2 |
| `DiagnosisDSC` | `str` | 5720 | 100.0 | 2 |
| `DiagnosisType` | `str` | 5721 | 100.0 | 2 |
| `days_prior` | `float64` | 5721 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 5721 | 100.0 | 2 |
| `age_at_death` | `float64` | 116 | 2.0 | 119 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `DiagnosisStartDTS_hours_from_start` | `float64` | 5721 | 100.0 | 2 |
| `DiagnosisEndDTS_hours_from_start` | `float64` | 5721 | 100.0 | 2 |

### `pediatric_vitals_long.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_vitals_long.csv`
- Read OK: `True`
- Line count (with header): `11862`
- Rows: `11861`
- Columns (22):
  - `observation_type`
  - `MRN`
  - `EncounterLocationDSC`
  - `EncounterDepartmentDSC`
  - `ObservationID`
  - `EncounterID`
  - `ObservationCD`
  - `ObservationDSC`
  - `vital_type`
  - `ValueTXT`
  - `ValueNBR`
  - `UnitOfMeasureCVDSC`
  - `EncounterTypeDSC`
  - `journey_id`
  - `facility_phase`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`
  - `EncounterStartDTS_hours_from_start`
  - `EncounterEndDTS_hours_from_start`
  - `EffectiveDTS_hours_from_start`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `observation_type` | `str` | 11861 | 100.0 | 2 |
| `MRN` | `str` | 11861 | 100.0 | 2 |
| `EncounterLocationDSC` | `str` | 11861 | 100.0 | 2 |
| `EncounterDepartmentDSC` | `str` | 11861 | 100.0 | 2 |
| `ObservationID` | `float64` | 11861 | 100.0 | 2 |
| `EncounterID` | `str` | 11861 | 100.0 | 2 |
| `ObservationCD` | `float64` | 11861 | 100.0 | 2 |
| `ObservationDSC` | `str` | 11861 | 100.0 | 2 |
| `vital_type` | `str` | 11861 | 100.0 | 2 |
| `ValueTXT` | `str` | 11861 | 100.0 | 2 |
| `ValueNBR` | `float64` | 9670 | 81.5 | 2 |
| `UnitOfMeasureCVDSC` | `str` | 6055 | 51.0 | 2 |
| `EncounterTypeDSC` | `str` | 11861 | 100.0 | 2 |
| `journey_id` | `str` | 11861 | 100.0 | 2 |
| `facility_phase` | `str` | 11861 | 100.0 | 2 |
| `age_at_medevac` | `float64` | 11861 | 100.0 | 2 |
| `age_at_death` | `float64` | 200 | 1.7 | 840 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |
| `EncounterStartDTS_hours_from_start` | `float64` | 11861 | 100.0 | 2 |
| `EncounterEndDTS_hours_from_start` | `float64` | 11861 | 100.0 | 2 |
| `EffectiveDTS_hours_from_start` | `float64` | 11861 | 100.0 | 2 |

### `pediatric_vitals_wide.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/pediatric_vitals_wide.csv`
- Read OK: `True`
- Line count (with header): `381`
- Rows: `380`
- Columns (20):
  - `journey_id`
  - `MRN`
  - `BMI_median`
  - `BSA_median`
  - `Diastolic_median`
  - `GCS_median`
  - `Glucose_median`
  - `HR_median`
  - `Height_median`
  - `MAP_median`
  - `Pain_median`
  - `RR_median`
  - `SpO2_median`
  - `Systolic_median`
  - `Temperature_median`
  - `Weight_median`
  - `age_at_medevac`
  - `age_at_death`
  - `journey_start_month`
  - `journey_start_year`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `journey_id` | `str` | 380 | 100.0 | 2 |
| `MRN` | `str` | 380 | 100.0 | 2 |
| `BMI_median` | `float64` | 221 | 58.2 | 3 |
| `BSA_median` | `float64` | 88 | 23.2 | 7 |
| `Diastolic_median` | `float64` | 252 | 66.3 | 2 |
| `GCS_median` | `float64` | 95 | 25.0 | 4 |
| `Glucose_median` | `float64` | 12 | 3.2 | 7 |
| `HR_median` | `float64` | 377 | 99.2 | 2 |
| `Height_median` | `float64` | 301 | 79.2 | 3 |
| `MAP_median` | `float64` | 122 | 32.1 | 6 |
| `Pain_median` | `float64` | 3 | 0.8 | 34 |
| `RR_median` | `float64` | 378 | 99.5 | 2 |
| `SpO2_median` | `float64` | 376 | 98.9 | 2 |
| `Systolic_median` | `float64` | 252 | 66.3 | 2 |
| `Temperature_median` | `float64` | 372 | 97.9 | 2 |
| `Weight_median` | `float64` | 368 | 96.8 | 2 |
| `age_at_medevac` | `float64` | 380 | 100.0 | 2 |
| `age_at_death` | `float64` | 7 | 1.8 | 33 |
| `journey_start_month` | `float64` | 0 | 0.0 | None |
| `journey_start_year` | `float64` | 0 | 0.0 | None |

### `village_name_codebook.csv`
- Path: `/Users/brianrice/CursorProjects/pediatric_data/data/village_name_codebook.csv`
- Read OK: `True`
- Line count (with header): `12`
- Rows: `11`
- Columns (5):
  - `anonymous_code`
  - `community_name`
  - `rank_by_journey_count`
  - `n_journeys_this_extract`
  - `reference_share_pct`

| Column | Dtype | Non-null n | Non-null % | First non-null row# (1-based csv) |
|---|---:|---:|---:|---:|
| `anonymous_code` | `str` | 11 | 100.0 | 2 |
| `community_name` | `str` | 11 | 100.0 | 2 |
| `rank_by_journey_count` | `int64` | 11 | 100.0 | 2 |
| `n_journeys_this_extract` | `int64` | 11 | 100.0 | 2 |
| `reference_share_pct` | `float64` | 11 | 100.0 | 2 |
