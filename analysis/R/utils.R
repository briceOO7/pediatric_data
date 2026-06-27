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

# ── gtsummary theme ────────────────────────────────────────────────────────────

#' Apply a consistent clinical research theme to gtsummary tables
set_gtsummary_theme_clinical <- function() {
  theme_gtsummary_journal(journal = "jama")
  theme_gtsummary_compact()
}
