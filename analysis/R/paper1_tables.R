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
    name_col <- intersect(c("village_name", "NAME", "name"), names(vc))[1]
    .cache$vc <- rename(vc, village_name = !!name_col)
  }
  .cache$vc
}
get_village_summary <- function() {
  if (!exists("vs", envir = .cache)) .cache$vs <- load_village_summary()
  .cache$vs
}
get_cohort_flow <- function() {
  if (!exists("cf", envir = .cache)) .cache$cf <- load_cohort_flow()
  .cache$cf
}
get_leg_breakdown <- function() {
  if (!exists("lb", envir = .cache)) .cache$lb <- load_leg_breakdown()
  .cache$lb
}

# ── Cohort counts (for inline narrative) ──────────────────────────────────────

cohort_counts <- function() {
  jp <- get_journeys_primary()
  cf <- get_cohort_flow()
  lb <- get_leg_breakdown()

  all_row  <- cf[cf$stage == "All records in database", ]
  coh_row  <- cf[cf$stage == "Village-originating (cohort)", ]
  excl_row <- cf[cf$stage == "MHC-presenting (excluded)", ]

  # Leg counts by route segment (village-originating journeys only)
  is_mhc_from  <- grepl("MHC|Maniilaq", lb$from_type)
  is_vill_from <- lb$from_type == "Village"
  is_anmc_to   <- grepl("ANMC|Alaska Native", lb$to_type)
  is_mhc_to    <- grepl("MHC|Maniilaq", lb$to_type)

  n_legs_village_mhc   <- sum(lb$n_legs[is_vill_from &  is_mhc_to])
  n_legs_village_anmc  <- sum(lb$n_legs[is_vill_from &  is_anmc_to])
  n_legs_village_other <- sum(lb$n_legs[is_vill_from & !is_mhc_to & !is_anmc_to])
  n_legs_mhc_anmc      <- sum(lb$n_legs[is_mhc_from &  is_anmc_to])
  n_legs_mhc_other     <- sum(lb$n_legs[is_mhc_from & !is_anmc_to])

  list(
    # Primary cohort
    n_journeys           = n_distinct(jp$journey_id),
    n_patients           = n_distinct(jp$MRN),
    n_villages           = n_distinct(jp$village_name[!is.na(jp$village_name) & jp$village_name != ""]),
    # DB totals (for PRISMA context)
    n_db_total           = as.integer(all_row$n_journeys),
    n_mhc_presenting     = as.integer(excl_row$n_journeys),
    # Route breakdown within cohort
    n_primary_only       = sum(jp$route_type == "Primary (village \u2192 MHC)", na.rm = TRUE),
    n_secondary          = sum(jp$route_type == "Secondary transfer", na.rm = TRUE),
    # Flight leg breakdown (village-originating journeys only)
    n_legs_total         = sum(lb$n_legs),
    n_legs_village_mhc   = n_legs_village_mhc,
    n_legs_mhc_anmc      = n_legs_mhc_anmc,
    n_legs_village_anmc  = n_legs_village_anmc,
    n_legs_mhc_other     = n_legs_mhc_other,
    n_legs_village_other = n_legs_village_other,
    # Completeness (cohort only)
    n_complete_dest_cohort   = as.integer(coh_row$n_complete_dest),
    n_complete_timing_cohort = as.integer(coh_row$n_complete_timing)
  )
}

# ── PRISMA patient flow diagram ────────────────────────────────────────────────

fig_prisma_diagram <- function() {
  library(DiagrammeR)
  cf <- get_cohort_flow()
  jp <- get_journeys_primary()

  all_row  <- cf[cf$stage == "All records in database", ]
  coh_row  <- cf[cf$stage == "Village-originating (cohort)", ]
  excl_row <- cf[cf$stage == "MHC-presenting (excluded)", ]

  n_villages <- n_distinct(jp$village_name[!is.na(jp$village_name) & jp$village_name != ""])
  pct <- function(n, d) paste0(round(100 * as.numeric(n) / as.numeric(d)), "%")

  # Two-branch layout: DB record → [village cohort | excluded MHC-local]
  dot <- sprintf(
    'digraph PRISMA {
      graph [rankdir=TB, splines=ortho, nodesep=1.2, ranksep=0.9]
      node [shape=rectangle, style=filled, fontname="Helvetica", fontsize=12, margin="0.25,0.15"]
      edge [fontsize=11]

      A [fillcolor="#D6EAF8",
         label="All pediatric air ambulance records\\nin database, 2020\\u20132024\\nn = %d journeys"]

      B [fillcolor="#A9DFBF",
         label="Village-originating flights (cohort)\\n%d journeys  \\u00b7  %d unique patients\\n%d communities\\nComplete destination data: %d (%s)\\nComplete timing data: %d (%s)"]

      Ex [fillcolor="#FADBD8",
          label="Excluded: n = %d\\nMHC-presenting patients\\n(not village air ambulance)\\nLocal or ground-transport arrivals\\nrequiring air transfer to ANMC"]

      A -> B
      A -> Ex
      {rank=same; B; Ex}
    }',
    as.integer(all_row$n_journeys),
    as.integer(coh_row$n_journeys), as.integer(coh_row$n_patients),
    n_villages,
    as.integer(coh_row$n_complete_dest),
      pct(coh_row$n_complete_dest, coh_row$n_journeys),
    as.integer(coh_row$n_complete_timing),
      pct(coh_row$n_complete_timing, coh_row$n_journeys),
    as.integer(excl_row$n_journeys)
  )

  grViz(dot)
}

# ── Table 1: Village characteristics (transposed: metrics × villages) ─────────

.fmt_mir <- function(median, q1, q3, lo, hi) {
  # Vectorised: format as "median (q1–q3); lo–hi", NA -> "—"
  ifelse(
    is.na(median), "\u2014",
    sprintf("%.0f (%.0f\u2013%.0f); %.0f\u2013%.0f", median, q1, q3, lo, hi)
  )
}

tbl1_village_characteristics <- function() {
  vs <- get_village_summary()

  # Sort: villages by n_journeys desc, Overall last
  villages_order <- vs |>
    filter(village_name != "Overall") |>
    arrange(desc(n_journeys)) |>
    pull(village_name)
  col_order <- c("Overall", villages_order)

  # Build one cell-value per (metric, village)
  vs_fmt <- vs |>
    mutate(
      mean_yr_str   = sprintf("%.1f (%.1f)", mean_per_year, sd_per_year),
      dist_str      = ifelse(!is.na(distance_miles), as.character(distance_miles), "\u2014"),
      total_ata_str = .fmt_mir(total_ata_median, total_ata_q1, total_ata_q3,
                                total_ata_lo, total_ata_hi),
      pct_act_str   = ifelse(!is.na(pct_complete_timing),
                              sprintf("%.1f%% (n=%d)", pct_complete_timing, n_complete_timing),
                              "\u2014"),
      decision_str  = .fmt_mir(decision_median, decision_q1, decision_q3,
                                decision_lo, decision_hi),
      response_str  = .fmt_mir(response_median, response_q1, response_q3,
                                response_lo, response_hi),
      util_str      = ifelse(!is.na(util_rate), as.character(util_rate), "\u2014")
    )

  # Metric rows in display order
  metric_rows <- tribble(
    ~metric_id,              ~Metric,
    "n_journeys",            "Total journeys",
    "n_patients",            "Total patients",
    "mean_yr_str",           "Mean journeys per year (SD)",
    "dist_str",              "Distance to Kotzebue (miles)",
    "total_ata_str",         "Total air ambulance time (arrival \u2192 MHC), min \u2014 Median (IQR); Range",
    "_header_act",           "Air Ambulance Activation",
    "pct_act_str",           "  % with complete timing data (n)",
    "decision_str",          "  Air ambulance decision-making time, min \u2014 Median (IQR); Range",
    "response_str",          "  Air ambulance response and transfer time, min \u2014 Median (IQR); Range\u1d43",
    "util_str",              "Utilization rate per 1,000 pediatric residents"
  )

  # For each column (village), pull the value for each metric
  get_val <- function(vname, mid) {
    if (mid == "_header_act") return("")
    row <- vs_fmt |> filter(village_name == vname)
    if (nrow(row) == 0) return("\u2014")
    val <- row[[mid]]
    if (is.null(val) || length(val) == 0) return("\u2014")
    ifelse(is.na(val), "\u2014", as.character(val))
  }

  # Build wide table: one column per village/overall
  tbl_wide <- metric_rows
  for (cn in col_order) {
    tbl_wide[[cn]] <- sapply(metric_rows$metric_id, function(m) get_val(cn, m))
  }
  tbl_wide <- tbl_wide |> select(-metric_id)

  # Render with gt
  tbl_wide |>
    gt(rowname_col = "Metric") |>
    tab_stubhead(label = "Metric") |>
    tab_style(
      style = list(cell_text(weight = "bold", color = "#2C3E50"),
                   cell_fill(color = "#EBF5FB")),
      locations = cells_stub(rows = Metric %in% c(
        "Air Ambulance Activation", "Total journeys"
      ))
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_column_labels()
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(columns = "Overall")
    ) |>
    tab_style(
      style = cell_text(color = "#555555", size = "small"),
      locations = cells_body(rows = startsWith(Metric, "  "))
    ) |>
    tab_style(
      style = cell_fill(color = "#F8F9FA"),
      locations = cells_body(rows = Metric == "Air Ambulance Activation")
    ) |>
    tab_footnote(
      footnote = "Utilization rate = village \u2192 MHC journeys per 1,000 pediatric residents under 18 (2020 Census).",
      locations = cells_stub(rows = Metric == "Utilization rate per 1,000 pediatric residents")
    ) |>
    tab_footnote(
      footnote = html("Activation \u2192 MHC arrival excludes observations below the per-village round-trip flight-time floor (2 \u00d7 median one-way flight time)."),
      locations = cells_stub(rows = endsWith(Metric, "\u1d43"))
    ) |>
    opt_stylize(style = 1) |>
    opt_table_font(font = "Arial") |>
    tab_options(
      stub.font.weight = "bold",
      column_labels.font.weight = "bold",
      table.font.size = "small"
    )
}

# ── Table 2: Patient characteristics by age group ─────────────────────────────

tbl2_patient_characteristics <- function() {
  pp <- get_patients_primary()

  # Sex
  if ("GenderDSC" %in% names(pp)) {
    pp <- pp |> mutate(
      female = factor(
        case_when(GenderDSC == "Female" ~ "Female", GenderDSC == "Male" ~ "Male",
                  TRUE ~ NA_character_),
        levels = c("Female", "Male")
      )
    )
  }

  # Race: prefer RaceDSC (text match), fall back to AI_AN flag
  if ("RaceDSC" %in% names(pp)) {
    pp <- pp |> mutate(
      ai_an = factor(
        case_when(
          grepl("indian|alaska.?native|american.?indian", RaceDSC, ignore.case = TRUE) ~ "AI/AN",
          !is.na(RaceDSC) & RaceDSC != "" ~ "Non-AI/AN",
          TRUE ~ NA_character_
        ),
        levels = c("AI/AN", "Non-AI/AN")
      )
    )
  } else if ("AI_AN" %in% names(pp)) {
    pp <- pp |> mutate(
      ai_an = factor(
        case_when(
          AI_AN %in% c(TRUE, "True", "true", "TRUE", "1", 1)    ~ "AI/AN",
          AI_AN %in% c(FALSE, "False", "false", "FALSE", "0", 0) ~ "Non-AI/AN",
          TRUE ~ NA_character_
        ),
        levels = c("AI/AN", "Non-AI/AN")
      )
    )
  }

  # Insurance categories (Commercial / Government / IHS / Self-Pay / Other)
  if ("insurance_cat" %in% names(pp)) {
    pp <- pp |> mutate(
      insurance_cat = factor(insurance_cat,
        levels = c("Commercial", "Government", "IHS", "Self-Pay", "Other"))
    )
  }

  # Transport count capped at 3+
  pp <- pp |> mutate(
    n_transports = factor(
      case_when(n_journeys_primary >= 3 ~ "3+", TRUE ~ as.character(n_journeys_primary)),
      levels = c("1", "2", "3+")
    )
  )

  # Chief complaint: keep top 10 by overall frequency, sorted high → low
  if ("primary_cedis_custom_group" %in% names(pp)) {
    top10_cc <- pp |>
      filter(!is.na(primary_cedis_custom_group)) |>
      count(primary_cedis_custom_group, sort = TRUE) |>
      slice_head(n = 10) |>
      pull(primary_cedis_custom_group)

    pp <- pp |> mutate(
      primary_cedis_custom_group = factor(
        ifelse(primary_cedis_custom_group %in% top10_cc,
               primary_cedis_custom_group, NA_character_),
        levels = top10_cc
      )
    )
  }

  # Ordered variable list (determines row order in table)
  ordered_vars <- c(
    "age_at_medevac_num",
    if ("female"        %in% names(pp)) "female",
    if ("ai_an"         %in% names(pp)) "ai_an",
    if ("insurance_cat" %in% names(pp)) "insurance_cat",
    "n_transports",
    "primary_cedis_custom_group"
  )
  include_vars <- intersect(ordered_vars, names(pp))
  pp_sel <- pp |> select(all_of(c(include_vars, "age_group")))

  all_labels <- list(
    age_at_medevac_num         ~ "Age at first transport, yr",
    female                     ~ "Sex",
    ai_an                      ~ "Race",
    insurance_cat              ~ "Insurance type",
    n_transports               ~ "Number of air ambulance transports per patient",
    primary_cedis_custom_group ~ "Chief Complaint"
  )
  label_vars   <- lapply(all_labels, function(x) as.character(x[[2]]))
  active_labels <- all_labels[unlist(label_vars) %in% include_vars]

  pp_sel |>
    tbl_summary(
      by      = age_group,
      include = include_vars,
      label   = active_labels,
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}–{p75})",
        all_categorical()  ~ "{n} ({p}%)"
      ),
      missing = "no"
    ) |>
    add_overall(last = FALSE) |>
    bold_labels() |>
    modify_header(label ~ "**Characteristic**") |>
    modify_caption("**Table 2.** Patient characteristics by age group. One row per patient (earliest qualifying journey). n (%) within each age-group column. Transports capped at 3+.")
}

# ── Table 3: Route comparison (Primary / Secondary / Direct tertiary) ──────────

tbl3_route_comparison <- function() {
  ja <- get_journeys_all()

  # Village-originating journeys across all three route types.
  # Direct tertiary (village → ANMC) are excluded from journeys_primary because
  # they lack a village→MHC leg, so we pull from journeys_all here.
  village_journeys <- ja |>
    filter(!is.na(village_name), village_name != "") |>
    mutate(
      route_label = factor(
        case_when(
          grepl("Primary",   route_type, ignore.case = TRUE) ~ "Primary only",
          grepl("Secondary", route_type, ignore.case = TRUE) ~ "Secondary",
          grepl("tertiary",  route_type, ignore.case = TRUE) ~ "Direct tertiary",
          TRUE ~ NA_character_
        ),
        levels = c("Primary only", "Secondary", "Direct tertiary")
      )
    ) |>
    filter(!is.na(route_label))

  if (nrow(village_journeys) == 0) {
    return(gt(tibble(Note = "No data available.")))
  }

  # Top 10 chief complaints by overall frequency, sorted high → low
  top10_cc <- village_journeys |>
    filter(!is.na(primary_cedis_custom_group)) |>
    count(primary_cedis_custom_group, sort = TRUE) |>
    slice_head(n = 10) |>
    pull(primary_cedis_custom_group)

  village_journeys <- village_journeys |>
    mutate(
      age_group = factor(age_group,
        levels = c("<1 yr", "1–<5 yr", "5–12 yr", "13–18 yr")),
      primary_cedis_custom_group = factor(
        ifelse(primary_cedis_custom_group %in% top10_cc,
               primary_cedis_custom_group, NA_character_),
        levels = top10_cc
      )
    )

  village_journeys |>
    select(route_label, age_at_medevac_num, age_group, primary_cedis_custom_group) |>
    tbl_summary(
      by      = route_label,
      include = c(age_at_medevac_num, age_group, primary_cedis_custom_group),
      label   = list(
        age_at_medevac_num         ~ "Age, years \u2014 Median (IQR)",
        age_group                  ~ "Age group",
        primary_cedis_custom_group ~ "Chief Complaint (CEDIS)"
      ),
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}\u2013{p75})",
        all_categorical()  ~ "{p}% ({n})"
      ),
      missing = "no"
    ) |>
    add_p(
      test = list(
        age_at_medevac_num         ~ "kruskal.test",
        age_group                  ~ "chisq.test",
        primary_cedis_custom_group ~ "chisq.test"
      )
    ) |>
    add_overall(last = FALSE) |>
    bold_labels() |>
    modify_header(label ~ "**Metric**") |>
    modify_caption("**Table 3.** Patient characteristics by transport route type. Primary only = village \u2192 MHC with no secondary transfer. Secondary = village \u2192 MHC \u2192 ANMC or outside facility. Direct tertiary = village \u2192 ANMC (bypassing MHC). p-values: Kruskal-Wallis (age); chi-square (categorical).")
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
