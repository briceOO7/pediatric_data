# paper1_stats.R — Inferential statistics for Paper 1 Table 3 (Route Comparison)
#
# Inputs:  outputs/data/paper1_route_comparison.csv   (written by export_analysis_data.py)
# Outputs: outputs/stats/paper1_table3_pvalues.csv    (read by medevac_summaries._load_pvalues)
#
# Run from project root:
#   Rscript analysis/R/paper1_stats.R
#
# Columns in input CSV:
#   journey_id, route_type, age_at_medevac, age_bucket, cc_definitive_custom_grouping

suppressPackageStartupMessages(library(dplyr))
suppressPackageStartupMessages(library(readr))
suppressPackageStartupMessages(library(here))

# ── Paths ─────────────────────────────────────────────────────────────────────

input_csv  <- here("outputs", "data",  "paper1_route_comparison.csv")
output_csv <- here("outputs", "stats", "paper1_table3_pvalues.csv")

# ── Load data ─────────────────────────────────────────────────────────────────

if (!file.exists(input_csv)) {
  stop(
    "Input not found: ", input_csv, "\n",
    "Run analysis/python/export_analysis_data.py first."
  )
}

routes <- read_csv(input_csv, show_col_types = FALSE)

# Work only with the two groups that appear in Table 3
# (Direct tertiary is excluded from comparative analysis due to small n)
routes <- routes |>
  filter(route_type %in% c("Primary (village \u2192 MHC)", "Secondary transfer")) |>
  mutate(grp = case_when(
    grepl("Primary",   route_type) ~ "Primary only",
    grepl("Secondary", route_type) ~ "Secondary",
    TRUE ~ NA_character_
  )) |>
  filter(!is.na(grp))

cat(sprintf("[paper1_stats] %d journeys: %d Primary only, %d Secondary\n",
    nrow(routes),
    sum(routes$grp == "Primary only"),
    sum(routes$grp == "Secondary")))

# ── Helper: safe p-value formatter ────────────────────────────────────────────

fmt_p <- function(p) {
  if (is.null(p) || is.na(p)) return(NA_real_)
  p
}

# ── Kruskal-Wallis: continuous age across route groups ───────────────────────

kw_p <- tryCatch({
  groups_age <- split(
    as.numeric(routes$age_at_medevac[!is.na(routes$age_at_medevac)]),
    routes$grp[!is.na(routes$age_at_medevac)]
  )
  non_empty  <- groups_age[sapply(groups_age, length) > 0]
  if (length(non_empty) >= 2) {
    kruskal.test(age_at_medevac ~ grp, data = routes)$p.value
  } else {
    NA_real_
  }
}, error = function(e) NA_real_)

# ── Chi-square: age group (categorical) ──────────────────────────────────────

chi_age_p <- tryCatch({
  ct <- table(routes$age_bucket, routes$grp)
  if (all(rowSums(ct) > 0) && ncol(ct) >= 2) {
    suppressWarnings(chisq.test(ct))$p.value
  } else {
    NA_real_
  }
}, error = function(e) NA_real_)

# ── Chi-square: chief complaint (custom grouping) ─────────────────────────────

chi_cc_p <- tryCatch({
  valid_cc <- routes |> filter(!is.na(cc_definitive_custom_grouping))
  # Keep only complaints with ≥10 journeys overall (matches Python logic)
  reported_cc <- valid_cc |>
    count(cc_definitive_custom_grouping, sort = TRUE) |>
    filter(n >= 10) |>
    pull(cc_definitive_custom_grouping)
  valid_cc <- valid_cc |> filter(cc_definitive_custom_grouping %in% reported_cc)
  ct <- table(valid_cc$cc_definitive_custom_grouping, valid_cc$grp)
  if (nrow(ct) >= 2 && ncol(ct) >= 2 && all(colSums(ct) > 0)) {
    suppressWarnings(chisq.test(ct))$p.value
  } else {
    NA_real_
  }
}, error = function(e) NA_real_)

# ── Export ────────────────────────────────────────────────────────────────────

results <- tibble(
  test    = c("kruskal_age", "chi_age_group", "chi_chief_complaint"),
  p_value = c(kw_p,          chi_age_p,       chi_cc_p)
)

dir.create(here("outputs", "stats"), showWarnings = FALSE, recursive = TRUE)
write_csv(results, output_csv)

cat(sprintf("[paper1_stats] Wrote %s\n", output_csv))
print(results)
