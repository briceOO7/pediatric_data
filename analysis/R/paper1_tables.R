# paper1_tables.R — Table builders for Paper 1: Operations & System-Level Analysis
# All functions return gtsummary or gt objects ready for Quarto rendering.

source(here::here("analysis", "R", "utils.R"))

# ── Shared data loading (cached for single Quarto session) ─────────────────────

.cache <- new.env(parent = emptyenv())

get_journeys_primary <- function() {
  if (!exists("jp", envir = .cache)) .cache$jp <- load_journeys_primary()
  .cache$jp
}
get_journeys_all <- function() {
  if (!exists("ja", envir = .cache)) .cache$ja <- load_journeys_all()
  .cache$ja
}
get_patients_primary <- function() {
  if (!exists("pp", envir = .cache)) .cache$pp <- load_patients_primary()
  .cache$pp
}
get_legs_primary <- function() {
  if (!exists("lp", envir = .cache)) .cache$lp <- load_legs_primary()
  .cache$lp
}
get_village_census <- function() {
  if (!exists("vc", envir = .cache)) {
    vc <- load_village_census()
    # Normalise the village name column regardless of CSV header
    name_col <- intersect(c("village_name", "NAME", "name"), names(vc))[1]
    .cache$vc <- rename(vc, village_name = !!name_col)
  }
  .cache$vc
}

# ── Cohort counts (for inline narrative) ──────────────────────────────────────

cohort_counts <- function() {
  jp <- get_journeys_primary()
  ja <- get_journeys_all()

  village_mask <- ja$village_name != "" & !is.na(ja$village_name) &
                  ja$route_type %in% c("Primary (village → MHC)", "Secondary transfer", "Direct tertiary")

  list(
    n_journeys         = n_distinct(jp$journey_id),
    n_patients         = n_distinct(jp$MRN),
    n_villages         = n_distinct(jp$village_name[jp$village_name != ""]),
    n_village_journeys = sum(village_mask, na.rm = TRUE),
    n_village_patients = n_distinct(ja$MRN[village_mask]),
    n_primary_only     = sum(jp$route_type == "Primary (village → MHC)", na.rm = TRUE),
    n_secondary        = sum(jp$route_type == "Secondary transfer", na.rm = TRUE),
    n_direct_tertiary  = sum(
      ja$route_type == "Direct tertiary" &
      !is.na(ja$village_name) & ja$village_name != "", na.rm = TRUE
    )
  )
}

# ── Table 1: Village characteristics ──────────────────────────────────────────
# One row per village. Custom gt table (gtsummary expects one row per subject).

tbl1_village_characteristics <- function() {
  jp  <- get_journeys_primary()
  vc  <- get_village_census()

  years <- sort(unique(jp$journey_start_year[!is.na(jp$journey_start_year)]))
  n_years <- max(length(years), 1)

  village_stats <- jp |>
    filter(!is.na(village_name), village_name != "") |>
    group_by(village_name) |>
    summarise(
      n_journeys  = n_distinct(journey_id),
      n_patients  = n_distinct(MRN),
      per_year    = round(n_distinct(journey_id) / n_years, 1),
      ata_median  = median(activate_to_arrive_min, na.rm = TRUE),
      ata_q1      = quantile(activate_to_arrive_min, 0.25, na.rm = TRUE),
      ata_q3      = quantile(activate_to_arrive_min, 0.75, na.rm = TRUE),
      ft_median   = median(flight_time_min, na.rm = TRUE),
      ft_q1       = quantile(flight_time_min, 0.25, na.rm = TRUE),
      ft_q3       = quantile(flight_time_min, 0.75, na.rm = TRUE),
      .groups = "drop"
    ) |>
    arrange(desc(n_journeys))

  # Join census
  village_stats <- village_stats |>
    left_join(vc |> select(village_name, pediatric_pop), by = "village_name") |>
    mutate(
      util_rate = ifelse(
        !is.na(pediatric_pop) & pediatric_pop > 0,
        round(n_journeys / pediatric_pop * 1000, 1),
        NA_real_
      ),
      ata_str = ifelse(
        !is.na(ata_median),
        sprintf("%.0f (%.0f–%.0f)", ata_median, ata_q1, ata_q3),
        "—"
      ),
      ft_str = ifelse(
        !is.na(ft_median),
        sprintf("%.0f (%.0f–%.0f)", ft_median, ft_q1, ft_q3),
        "—"
      ),
      util_str = ifelse(!is.na(util_rate), as.character(util_rate), "—")
    )

  # Overall row
  overall <- tibble(
    village_name = "Overall",
    n_journeys   = n_distinct(jp$journey_id),
    n_patients   = n_distinct(jp$MRN),
    per_year     = round(n_distinct(jp$journey_id) / n_years, 1),
    ata_str      = fmt_median_iqr(jp$activate_to_arrive_min),
    ft_str       = fmt_median_iqr(jp$flight_time_min),
    util_str     = "—"
  )

  tbl_data <- bind_rows(
    village_stats |> select(village_name, n_journeys, n_patients, per_year, ata_str, ft_str, util_str),
    overall
  )

  tbl_data |>
    gt() |>
    cols_label(
      village_name = "Village",
      n_journeys   = "Journeys (n)",
      n_patients   = "Patients (n)",
      per_year     = "Journeys/yr",
      ata_str      = "Activation → MHC, min\nMedian (IQR)",
      ft_str       = "Flight time, min\nMedian (IQR)",
      util_str     = "Rate per 1,000\npediatric residents"
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(rows = village_name == "Overall")
    ) |>
    tab_footnote(
      "Utilization rate = village → MHC journeys per 1,000 pediatric residents under 18 (2020 Census)."
    ) |>
    tab_footnote(
      "Activation → MHC excludes timing records flagged as implausible."
    ) |>
    opt_stylize(style = 1) |>
    opt_table_font(font = "Arial")
}

# ── Table 2: Patient characteristics by age group ─────────────────────────────

tbl2_patient_characteristics <- function() {
  pp <- get_patients_primary()

  # Variable labels
  pp <- pp |>
    mutate(
      female = case_when(
        GenderDSC == "Female" ~ "Female",
        GenderDSC == "Male"   ~ "Male",
        TRUE ~ NA_character_
      ) |> factor(levels = c("Female", "Male")),
      ai_an = case_when(
        AI_AN %in% c(TRUE, "True", "true", "TRUE", "1", 1)   ~ "Yes",
        AI_AN %in% c(FALSE, "False", "false", "FALSE", "0", 0) ~ "No",
        TRUE ~ NA_character_
      ) |> factor(levels = c("Yes", "No"))
    )

  var_list <- c("age_at_medevac_num", "age_group", "n_journeys_primary",
                "primary_cedis_category")

  if ("female" %in% names(pp))      var_list <- c(var_list, "female")
  if ("ai_an" %in% names(pp))       var_list <- c(var_list, "ai_an")
  if ("PrimaryPayorNM" %in% names(pp)) var_list <- c(var_list, "PrimaryPayorNM")

  var_list <- intersect(var_list, names(pp))

  include_vars <- setdiff(var_list, "age_group")
  pp_sel <- pp |> select(all_of(c(include_vars, "age_group")))

  all_labels <- list(
    age_at_medevac_num     ~ "Age at first medevac, yr",
    n_journeys_primary     ~ "Primary transports per patient",
    primary_cedis_category ~ "Chief complaint category (CEDIS)",
    female                 ~ "Sex",
    ai_an                  ~ "AI/AN race",
    PrimaryPayorNM         ~ "Insurance"
  )
  label_vars <- lapply(all_labels, function(x) as.character(x[[2]]))
  active_labels <- all_labels[unlist(label_vars) %in% include_vars]

  pp_sel |>
    tbl_summary(
      by = age_group,
      include = include_vars,
      label = active_labels,
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}–{p75})",
        all_categorical()  ~ "{n} ({p}%)"
      ),
      missing = "no"
    ) |>
    add_overall(last = FALSE) |>
    bold_labels() |>
    modify_header(label ~ "**Characteristic**") |>
    modify_caption("**Table 2.** Patient characteristics by age group. One row per patient (earliest qualifying journey). n (%) within each age-group column.")
}

# ── Table 3: Route comparison (Primary / Secondary / Direct tertiary) ──────────

tbl3_route_comparison <- function() {
  ja <- get_journeys_all()

  # Restrict to village-origin journeys (all three route types)
  village_journeys <- ja |>
    filter(
      !is.na(village_name), village_name != "",
      route_type %in% c("Primary (village → MHC)", "Secondary transfer", "Direct tertiary")
    ) |>
    mutate(
      route_type = droplevels(route_type)
    )

  if (nrow(village_journeys) == 0) {
    return(gt(tibble(Note = "No data available.")))
  }

  village_journeys |>
    select(route_type, age_at_medevac_num = age_at_medevac_num,
           primary_cedis_category) |>
    tbl_summary(
      by = route_type,
      include = c(age_at_medevac_num, primary_cedis_category),
      label = list(
        age_at_medevac_num    ~ "Age at medevac, yr",
        primary_cedis_category ~ "Chief complaint category (CEDIS)"
      ),
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}–{p75})",
        all_categorical()  ~ "{n} ({p}%)"
      ),
      missing = "no"
    ) |>
    add_p(
      test = list(
        age_at_medevac_num    ~ "kruskal.test",
        primary_cedis_category ~ "chisq.test"
      )
    ) |>
    add_overall(last = FALSE) |>
    bold_labels() |>
    modify_header(label ~ "**Characteristic**") |>
    modify_caption("**Table 3.** Patient characteristics by transport route type. p-values: Kruskal-Wallis (age); chi-square (categorical).")
}

# ── Table 3a: Primary legs (village → any destination) ────────────────────────

tbl3a_primary_routes <- function() {
  legs <- get_legs_primary()

  village_legs <- legs |>
    filter(is_village_origin) |>
    count(origin, destination_label, name = "n_legs") |>
    arrange(desc(n_legs)) |>
    mutate(pct = sprintf("%.1f%%", 100 * n_legs / sum(n_legs)))

  total_row <- tibble(
    origin = "All primary legs", destination_label = "—",
    n_legs = sum(village_legs$n_legs), pct = "100.0%"
  )

  bind_rows(village_legs, total_row) |>
    gt() |>
    cols_label(
      origin            = "Village of Origin",
      destination_label = "Destination",
      n_legs            = "N Legs",
      pct               = "% of Primary Legs"
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(rows = origin == "All primary legs")
    ) |>
    opt_stylize(style = 1)
}

# ── Table 3b: Secondary legs (MHC → tertiary) ─────────────────────────────────

tbl3b_secondary_routes <- function() {
  legs <- get_legs_primary()

  mhc_legs <- legs |>
    filter(is_mhc_dest == FALSE & leg_num > 1) |>  # legs that leave MHC
    count(destination_label, name = "n_legs") |>
    arrange(desc(n_legs)) |>
    mutate(pct = sprintf("%.1f%%", 100 * n_legs / sum(n_legs)))

  if (nrow(mhc_legs) == 0) {
    return(gt(tibble(Note = "No secondary (MHC-origin) legs found.")))
  }

  total_row <- tibble(destination_label = "All secondary legs",
                      n_legs = sum(mhc_legs$n_legs), pct = "100.0%")

  bind_rows(mhc_legs, total_row) |>
    gt() |>
    cols_label(
      destination_label = "Destination",
      n_legs            = "N Legs",
      pct               = "% of Secondary Legs"
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(rows = destination_label == "All secondary legs")
    ) |>
    opt_stylize(style = 1)
}

# ── Table 4: Village utilization ───────────────────────────────────────────────

tbl4_village_utilization <- function() {
  jp <- get_journeys_primary()
  vc <- get_village_census()

  util <- jp |>
    filter(!is.na(village_name), village_name != "") |>
    group_by(village_name) |>
    summarise(
      n_journeys = n_distinct(journey_id),
      n_lt1      = sum(age_group == "<1 yr", na.rm = TRUE),
      n_1to5     = sum(age_group == "1–<5 yr", na.rm = TRUE),
      n_5to12    = sum(age_group == "5–12 yr", na.rm = TRUE),
      n_13to18   = sum(age_group == "13–18 yr", na.rm = TRUE),
      .groups = "drop"
    ) |>
    left_join(vc |> select(village_name, pediatric_pop), by = "village_name") |>
    mutate(
      rate = ifelse(
        !is.na(pediatric_pop) & pediatric_pop > 0,
        round(n_journeys / pediatric_pop * 1000, 1),
        NA_real_
      ),
      pct_lt1   = sprintf("%d (%.1f%%)", n_lt1,   100 * n_lt1   / n_journeys),
      pct_1to5  = sprintf("%d (%.1f%%)", n_1to5,  100 * n_1to5  / n_journeys),
      pct_5to12 = sprintf("%d (%.1f%%)", n_5to12, 100 * n_5to12 / n_journeys),
      pct_13to18= sprintf("%d (%.1f%%)", n_13to18,100 * n_13to18/ n_journeys)
    ) |>
    arrange(desc(rate))

  n_total <- n_distinct(jp$journey_id)

  overall <- tibble(
    village_name = "Overall",
    n_journeys   = n_total,
    rate         = NA_real_,
    pct_lt1      = sprintf("%d (%.1f%%)", sum(util$n_lt1),    100 * sum(util$n_lt1)    / n_total),
    pct_1to5     = sprintf("%d (%.1f%%)", sum(util$n_1to5),   100 * sum(util$n_1to5)   / n_total),
    pct_5to12    = sprintf("%d (%.1f%%)", sum(util$n_5to12),  100 * sum(util$n_5to12)  / n_total),
    pct_13to18   = sprintf("%d (%.1f%%)", sum(util$n_13to18), 100 * sum(util$n_13to18) / n_total)
  )

  bind_rows(
    util |> select(village_name, n_journeys, rate, pct_lt1, pct_1to5, pct_5to12, pct_13to18),
    overall |> mutate(rate = NA_real_) |>
      select(village_name, n_journeys, rate, pct_lt1, pct_1to5, pct_5to12, pct_13to18)
  ) |>
    gt() |>
    cols_label(
      village_name = "Village",
      n_journeys   = "Total journeys",
      rate         = "Rate per 1,000",
      pct_lt1      = "<1 yr",
      pct_1to5     = "1–<5 yr",
      pct_5to12    = "5–12 yr",
      pct_13to18   = "13–18 yr"
    ) |>
    tab_spanner(label = "Age group, n (%)", columns = c(pct_lt1, pct_1to5, pct_5to12, pct_13to18)) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(rows = village_name == "Overall")
    ) |>
    fmt_missing(columns = "rate", missing_text = "—") |>
    tab_footnote("Rate = village → MHC journeys per 1,000 pediatric residents under 18 (2020 Census).") |>
    opt_stylize(style = 1)
}

# ── Table 5: Timing (continuous, minutes) ─────────────────────────────────────

tbl5_timing_minutes <- function() {
  jp <- get_journeys_primary()

  timing_vars <- jp |>
    select(
      any_of(c("time_to_activate_min", "activate_to_arrive_min", "flight_time_min"))
    )

  var_labels <- list(
    time_to_activate_min  ~ "Time to activate, min",
    activate_to_arrive_min ~ "Activation → MHC arrival, min",
    flight_time_min        ~ "Flight time, min"
  )
  var_labels <- var_labels[sapply(var_labels, function(x) as.character(x[[2]]) %in% names(timing_vars))]

  timing_vars |>
    tbl_summary(
      label     = var_labels,
      statistic = all_continuous() ~ "{median} ({p25}–{p75})",
      missing   = "ifany",
      missing_text = "(missing)"
    ) |>
    bold_labels() |>
    modify_header(label ~ "**Time interval**") |>
    modify_caption("**Table 5.** Time intervals (minutes), village → MHC primary transports. Median (IQR).")
}
