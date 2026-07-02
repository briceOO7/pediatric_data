# utils.R — shared helpers for all R table scripts
# Sources: outputs/data/*.csv (written by analysis/python/medevac_data_prep.py)

library(dplyr)
library(tidyr)
library(readr)
library(here)
library(gtsummary)
library(gt)
library(flextable)
library(labelled)

# ── Paths ──────────────────────────────────────────────────────────────────────

DATA_DIR <- here("outputs", "data")

pipeline_pediatric_dir <- function() {
  env <- Sys.getenv("MEDEVAC_PIPELINE_DIR", unset = "")
  root <- here()
  pipeline_root <- if (nzchar(env)) env else file.path(dirname(root), "medevac_pipeline_project")
  file.path(pipeline_root, "data", "final", "pediatric")
}

source_data_dir <- function() {
  pipeline_dir <- pipeline_pediatric_dir()
  if (dir.exists(pipeline_dir)) return(pipeline_dir)
  local_dir <- here("data")
  if (dir.exists(local_dir)) return(local_dir)
  NA_character_
}

vitals_csv_path <- function() {
  env <- Sys.getenv("MEDEVAC_VITALS_CSV", unset = "")
  if (nzchar(env)) return(env)
  src <- source_data_dir()
  if (is.na(src)) return(NA_character_)
  for (name in c("pediatric_village_visit_vitals.csv", "pediatric_vitals_wide.csv")) {
    path <- file.path(src, name)
    if (file.exists(path)) return(path)
  }
  file.path(src, "pediatric_village_visit_vitals.csv")
}

mrn_normalize <- function(x) {
  vapply(x, function(val) {
    if (is.na(val) || (is.character(val) && !nzchar(trimws(val)))) return(NA_character_)
    num <- suppressWarnings(as.numeric(val))
    if (!is.na(num)) return(as.character(as.integer(num)))
    trimws(as.character(val))
  }, character(1), USE.NAMES = FALSE)
}

num_or_none <- function(x) {
  if (length(x) == 0) return(NA_real_)
  if (is.na(x)) return(NA_real_)
  if (is.character(x) && !nzchar(trimws(x))) return(NA_real_)
  num <- suppressWarnings(as.numeric(x))
  if (is.na(num)) NA_real_ else num
}

.pick_vitals_col <- function(df, aliases) {
  cols_lower <- tolower(names(df))
  for (alias in aliases) {
    if (alias %in% names(df)) return(alias)
    hit <- which(cols_lower == tolower(alias))
    if (length(hit) == 1) return(names(df)[hit])
  }
  NULL
}

vital_column_map <- function(vitals) {
  aliases <- list(
    hr = c("hr", "HR", "HR_median", "heart_rate", "HeartRate", "vital_hr", "Pulse"),
    o2 = c("spo2", "SpO2", "SpO2_median", "o2_sat", "O2Sat", "O2", "vital_o2", "oxygen_sat"),
    bp_sys = c("bp_systolic", "sbp", "SBP", "Systolic_median", "BPSystolic", "vital_bp_systolic", "sys_bp"),
    bp_dia = c("bp_diastolic", "dbp", "DBP", "Diastolic_median", "BPDiastolic", "vital_bp_diastolic", "dia_bp"),
    rr = c("rr", "RR", "RR_median", "respiratory_rate", "RespRate", "vital_rr", "resp_rate"),
    temp = c("temp", "Temp", "temperature", "Temperature", "Temperature_median", "vital_temp")
  )
  out <- lapply(aliases, function(a) .pick_vitals_col(vitals, a))
  out <- out[!vapply(out, is.null, logical(1))]
  if (length(out) < 6) return(NULL)
  out
}

load_vitals_for_cohort <- function() {
  path <- vitals_csv_path()
  if (is.na(path) || !file.exists(path)) {
    return(list(vitals = NULL, colmap = NULL, gcs_col = NULL, error = "no vitals file"))
  }
  vit <- read_csv(path, show_col_types = FALSE)
  cm <- vital_column_map(vit)
  if (is.null(cm)) {
    return(list(vitals = vit, colmap = NULL, gcs_col = NULL, error = "missing required vital columns"))
  }
  mrn_col <- .pick_vitals_col(vit, c("MRN", "mrn", "patient_mrn", "PatientMRN", "Patient_MRN"))
  if (is.null(mrn_col)) {
    return(list(vitals = vit, colmap = cm, gcs_col = NULL, error = "missing MRN column"))
  }
  vit$mrn_k <- mrn_normalize(vit[[mrn_col]])
  vit <- vit[!is.na(vit$mrn_k), , drop = FALSE]
  if ("facility_phase" %in% names(vit)) {
    phase <- tolower(as.character(vit$facility_phase))
    if (any(grepl("village", phase, fixed = TRUE), na.rm = TRUE)) {
      vit <- vit[grepl("village", phase, fixed = TRUE), , drop = FALSE]
    }
  }
  gcs_col <- .pick_vitals_col(vit, c("gcs", "GCS", "GCS_median", "gcs_median"))
  list(vitals = vit, colmap = cm, gcs_col = gcs_col, error = NULL)
}

first_cohort_patients <- function(jp) {
  jp |>
    distinct(journey_id, .keep_all = TRUE) |>
    mutate(medevac1_date = as.Date(medevac1_date)) |>
    arrange(medevac1_date) |>
    group_by(MRN) |>
    slice(1) |>
    ungroup() |>
    mutate(mrn_k = mrn_normalize(MRN)) |>
    filter(!is.na(mrn_k))
}

.value_present <- function(x) {
  if (is.character(x)) return(!is.na(x) & nzchar(trimws(x)))
  !is.na(x)
}

pews_proxy_score <- function(row, cm, gcs_col) {
  rr <- num_or_none(row[[cm$rr]])
  hr <- num_or_none(row[[cm$hr]])
  sbp <- num_or_none(row[[cm$bp_sys]])
  temp <- num_or_none(row[[cm$temp]])
  gcs <- if (!is.null(gcs_col)) num_or_none(row[[gcs_col]]) else NA_real_
  if (any(is.na(c(rr, hr, sbp, temp, gcs)))) return(NA_integer_)

  s_rr <- if (rr < 9) 2 else if (rr <= 14) 0 else if (rr <= 20) 1 else if (rr <= 29) 2 else 3
  s_hr <- if (hr <= 40) 2 else if (hr <= 50) 1 else if (hr <= 100) 0 else if (hr <= 110) 1 else if (hr <= 129) 2 else 3
  s_sbp <- if (sbp <= 70) 3 else if (sbp <= 80) 2 else if (sbp <= 100) 1 else if (sbp < 200) 0 else 2
  s_temp <- if (temp >= 35.0 && temp <= 38.4) 0 else 2
  s_cns <- if (gcs >= 15) 0 else if (gcs >= 13) 1 else if (gcs >= 9) 2 else 3
  as.integer(s_rr + s_hr + s_sbp + s_temp + s_cns)
}

vital_present_sets <- function(vit, cm, gcs_col = NULL) {
  present_for <- function(col) {
    unique(vit$mrn_k[.value_present(vit[[col]])])
  }
  bp_ok <- .value_present(vit[[cm$bp_sys]]) & .value_present(vit[[cm$bp_dia]])
  out <- list(
    HR = present_for(cm$hr),
    `O2 sat` = present_for(cm$o2),
    `BP (systolic+diastolic)` = unique(vit$mrn_k[bp_ok]),
    RR = present_for(cm$rr),
    Temp = present_for(cm$temp)
  )
  if (!is.null(gcs_col)) {
    out[["GCS/AVPU"]] <- present_for(gcs_col)
  }
  out
}

pews_ready_mrns <- function(vit, cm, gcs_col, cohort_mrns) {
  if (is.null(gcs_col)) return(character(0))
  sub <- vit[vit$mrn_k %in% cohort_mrns, , drop = FALSE]
  if (nrow(sub) == 0) return(character(0))
  scores <- apply(sub, 1, function(row) pews_proxy_score(row, cm, gcs_col))
  unique(sub$mrn_k[!is.na(scores)])
}

load_journeys_primary <- function() {
  df <- read_csv(file.path(DATA_DIR, "journeys_primary.csv"), show_col_types = FALSE)
  df <- df |>
    mutate(
      age_group = factor(
        age_group,
        levels = c("<1 yr", "1–<5 yr", "5–12 yr", "13–18 yr"),
        ordered = TRUE
      ),
      route_type = factor(
        route_type,
        levels = c("Primary (village → MHC)", "Secondary transfer", "Direct tertiary", "Unknown")
      ),
      journey_start_year = as.integer(journey_start_year)
    )
  df
}

load_journeys_all <- function() {
  read_csv(file.path(DATA_DIR, "journeys_all.csv"), show_col_types = FALSE) |>
    mutate(
      age_group = factor(
        age_group,
        levels = c("<1 yr", "1–<5 yr", "5–12 yr", "13–18 yr"),
        ordered = TRUE
      ),
      route_type = factor(
        route_type,
        levels = c("Primary (village → MHC)", "Secondary transfer", "Direct tertiary", "Unknown")
      )
    )
}

load_patients_primary <- function() {
  df <- read_csv(file.path(DATA_DIR, "patients_primary.csv"), show_col_types = FALSE)
  df <- df |>
    mutate(
      age_group = factor(
        age_group,
        levels = c("<1 yr", "1–<5 yr", "5–12 yr", "13–18 yr"),
        ordered = TRUE
      )
    )
  df
}

load_legs_primary <- function() {
  read_csv(file.path(DATA_DIR, "legs_primary.csv"), show_col_types = FALSE)
}

load_village_census <- function() {
  read_csv(file.path(DATA_DIR, "village_census.csv"), show_col_types = FALSE)
}

load_village_summary <- function() {
  read_csv(file.path(DATA_DIR, "village_summary.csv"), show_col_types = FALSE)
}

load_cohort_flow <- function() {
  read_csv(file.path(DATA_DIR, "cohort_flow.csv"), show_col_types = FALSE)
}

load_leg_breakdown <- function() {
  read_csv(file.path(DATA_DIR, "leg_breakdown.csv"), show_col_types = FALSE)
}

# ── Formatting helpers ─────────────────────────────────────────────────────────

#' Format median (IQR) for a numeric vector
fmt_median_iqr <- function(x, digits = 1) {
  x <- x[!is.na(x)]
  if (length(x) == 0) return("—")
  sprintf(
    "%s (%s–%s)",
    round(median(x), digits),
    round(quantile(x, 0.25), digits),
    round(quantile(x, 0.75), digits)
  )
}

#' Format mean ± SD
fmt_mean_sd <- function(x, digits = 1) {
  x <- x[!is.na(x)]
  if (length(x) == 0) return("—")
  sprintf("%s ± %s", round(mean(x), digits), round(sd(x), digits))
}

#' Format n (%) 
fmt_n_pct <- function(n, denom, digits = 1) {
  if (is.na(denom) || denom == 0) return("—")
  sprintf("%d (%s%%)", n, formatC(100 * n / denom, digits = digits, format = "f"))
}

#' Format % (n) — matches Paper 1 gtsummary tables (e.g. Table 3)
fmt_pct_n <- function(n, denom, digits = 1) {
  n <- as.integer(n)
  denom <- as.integer(denom)
  out <- rep("\u2014", length(n))
  ok <- !is.na(n) & !is.na(denom) & denom > 0L
  if (any(ok)) {
    out[ok] <- sprintf(
      "%s%% (%d)",
      formatC(100 * n[ok] / denom[ok], digits = digits, format = "f"),
      n[ok]
    )
  }
  out
}

# ── gtsummary theme ────────────────────────────────────────────────────────────

#' Apply a consistent clinical research theme to gtsummary tables
set_gtsummary_theme_clinical <- function() {
  theme_gtsummary_journal(journal = "jama")
  theme_gtsummary_compact()
}
