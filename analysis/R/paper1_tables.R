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

  n_primary_only    <- sum(jp$route_type == "Primary (village \u2192 MHC)", na.rm = TRUE)
  n_secondary       <- sum(jp$route_type == "Secondary transfer", na.rm = TRUE)
  n_direct_tertiary <- sum(grepl("tertiary", jp$route_type, ignore.case = TRUE), na.rm = TRUE)
  n_journeys_coh    <- n_distinct(jp$journey_id)
  n_village_to_mhc  <- n_primary_only + n_secondary
  n_managed_at_mhc  <- n_primary_only
  pct_managed_at_mhc <- if (n_village_to_mhc > 0) {
    round(100 * n_managed_at_mhc / n_village_to_mhc)
  } else {
    NA_integer_
  }

  list(
    # Primary cohort
    n_journeys           = n_journeys_coh,
    n_patients           = n_distinct(jp$MRN),
    n_villages           = n_distinct(jp$village_name[!is.na(jp$village_name) & jp$village_name != ""]),
    # DB totals (for PRISMA context)
    n_db_total           = as.integer(all_row$n_journeys),
    n_mhc_presenting     = as.integer(excl_row$n_journeys),
    # Route breakdown within cohort
    n_primary_only       = n_primary_only,
    n_secondary          = n_secondary,
    n_direct_tertiary    = n_direct_tertiary,
    n_village_to_mhc   = n_village_to_mhc,
    n_managed_at_mhc     = n_managed_at_mhc,
    pct_managed_at_mhc   = pct_managed_at_mhc,
    route_village_mhc_str      = fmt_pct_of_n(n_primary_only, n_journeys_coh),
    route_mhc_tertiary_str     = fmt_pct_of_n(n_secondary, n_journeys_coh),
    route_direct_tertiary_str  = fmt_pct_of_n(n_direct_tertiary, n_journeys_coh),
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

# ── Shared infrastructure for transposed village tables ────────────────────────

.fmt_mir <- function(median, q1, q3, lo, hi) {
  ifelse(
    is.na(median), "\u2014",
    sprintf("%.0f (%.0f\u2013%.0f); %.0f\u2013%.0f", median, q1, q3, lo, hi)
  )
}

# Build the shared vs_fmt / transport_fmt / col_order objects used by both
# village tables. Returns a list so each table function can call it once.
.village_table_data <- function() {
  vs <- get_village_summary()
  pp <- get_patients_primary()

  villages_order <- vs |>
    filter(village_name != "Overall") |>
    arrange(desc(util_rate)) |>
    pull(village_name)
  col_order <- c("Overall", villages_order)

  .tfmt <- function(df) {
    total <- nrow(df)
    if (total == 0) return(tibble(t1_str = "\u2014", t2_str = "\u2014", t3p_str = "\u2014"))
    n1  <- sum(df$n_journeys_primary == 1,  na.rm = TRUE)
    n2  <- sum(df$n_journeys_primary == 2,  na.rm = TRUE)
    n3p <- sum(df$n_journeys_primary >= 3,  na.rm = TRUE)
    tibble(
      t1_str  = fmt_pct_n(n1,  total),
      t2_str  = fmt_pct_n(n2,  total),
      t3p_str = fmt_pct_n(n3p, total)
    )
  }
  transport_fmt <- bind_rows(
    .tfmt(pp) |> mutate(village_name = "Overall"),
    pp |> filter(!is.na(village_name), village_name != "") |>
      group_by(village_name) |> group_modify(~ .tfmt(.x)) |> ungroup()
  )

  vs_fmt <- vs |> mutate(
    mean_yr_str   = sprintf("%.1f (%.1f)", mean_per_year, sd_per_year),
      dist_str      = ifelse(!is.na(distance_miles), sprintf("%.1f", distance_miles), "\u2014"),
    total_ata_str = .fmt_mir(total_ata_median, total_ata_q1, total_ata_q3,
                              total_ata_lo, total_ata_hi),
    pct_act_str   = ifelse(!is.na(n_complete_timing) & !is.na(n_journeys) & n_journeys > 0,
                            fmt_pct_n(n_complete_timing, n_journeys),
                            "\u2014"),
    decision_str  = .fmt_mir(decision_median, decision_q1, decision_q3,
                              decision_lo, decision_hi),
    response_str  = .fmt_mir(response_median, response_q1, response_q3,
                              response_lo, response_hi),
      util_str      = ifelse(!is.na(util_rate), sprintf("%.1f", util_rate), "\u2014")
  )

  list(vs_fmt = vs_fmt, transport_fmt = transport_fmt, col_order = col_order)
}

.village_column_labels <- function(vs_fmt, col_order) {
  labels <- lapply(col_order, function(vname) {
    row <- vs_fmt |> filter(village_name == vname)
    n <- if (nrow(row) == 0 || is.na(row$n_journeys[1])) 0L else as.integer(row$n_journeys[1])
    label <- if (vname == "Overall") "Overall" else vname
    md(sprintf("**%s**  \nN = %d", label, n))
  })
  setNames(labels, col_order)
}

# Render a transposed village gt table from a metric_rows tibble + data list
.paper1_gt_theme <- function(tbl) {
  tbl |>
    opt_row_striping() |>
    opt_table_font(
      font = c(
        "system-ui", "Segoe UI", "Roboto", "Helvetica", "Arial",
        "sans-serif"
      )
    ) |>
    tab_options(
      table.border.top.color         = "#A8A8A8",
      table.border.top.width         = px(2),
      table.border.bottom.color      = "#A8A8A8",
      table.border.bottom.width      = px(2),
      column_labels.background.color = "#FFFFFF",
      column_labels.border.bottom.color = "#D3D3D3",
      column_labels.border.bottom.width = px(2),
      table_body.border.top.color    = "#D3D3D3",
      table_body.border.top.width    = px(2),
      table_body.border.bottom.color = "#D3D3D3",
      table_body.border.bottom.width = px(2),
      stub.background.color          = "#FFFFFF",
      row_group.background.color     = "#FFFFFF",
      table.font.size                = px(14)
    )
}

.render_village_gt <- function(metric_rows, dat, bold_header_rows = character(0),
                               shaded_rows = character(0), footnotes = list()) {
  vs_fmt        <- dat$vs_fmt
  transport_fmt <- dat$transport_fmt
  col_order     <- dat$col_order

  get_val <- function(vname, mid) {
    if (startsWith(mid, "_header")) return("")
    if (mid %in% c("t1_str", "t2_str", "t3p_str")) {
      trow <- transport_fmt |> filter(village_name == vname)
      if (nrow(trow) == 0) return("\u2014")
      return(as.character(trow[[mid]]))
    }
    row <- vs_fmt |> filter(village_name == vname)
    if (nrow(row) == 0) return("\u2014")
    val <- row[[mid]]
    if (is.null(val) || length(val) == 0) return("\u2014")
    ifelse(is.na(val), "\u2014", as.character(val))
  }

  tbl_wide <- metric_rows
  for (cn in col_order) {
    tbl_wide[[cn]] <- sapply(metric_rows$metric_id, function(m) get_val(cn, m))
  }
  tbl_wide <- tbl_wide |> select(-metric_id)
  col_labels <- .village_column_labels(vs_fmt, col_order)

  tbl <- tbl_wide |>
    gt(rowname_col = "Metric") |>
    cols_label(!!!col_labels) |>
    tab_stubhead(label = "Metric") |>
    # Section header rows: bold, light gray background
    tab_style(
      style = list(cell_text(weight = "bold", color = "#000000"),
                   cell_fill(color = "#EBEBEB")),
      locations = cells_stub(rows = Metric %in% bold_header_rows)
    ) |>
    tab_style(
      style = cell_fill(color = "#EBEBEB"),
      locations = cells_body(rows = Metric %in% bold_header_rows)
    ) |>
    # Section header shaded rows (sub-group dividers)
    tab_style(
      style = cell_fill(color = "#F5F5F5"),
      locations = cells_body(rows = Metric %in% shaded_rows)
    ) |>
    tab_style(
      style = cell_fill(color = "#F5F5F5"),
      locations = cells_stub(rows = Metric %in% shaded_rows)
    ) |>
    # Column labels: bold black
    tab_style(style = cell_text(weight = "bold", color = "#000000"),
              locations = cells_column_labels()) |>
    # Overall column: bold
    tab_style(style = cell_text(weight = "bold"),
              locations = cells_body(columns = "Overall")) |>
    tab_style(style = cell_text(weight = "bold"),
              locations = cells_stub()) |>
    # Indented sub-rows: slightly smaller, gray
    tab_style(style = cell_text(color = "#444444", size = "small",
                                weight = "normal"),
              locations = cells_stub(rows = startsWith(Metric, "  "))) |>
    tab_style(style = cell_text(color = "#444444", size = "small"),
              locations = cells_body(rows = startsWith(Metric, "  "))) |>
    .paper1_gt_theme()

  for (fn in footnotes) {
    tbl <- tbl |> tab_footnote(footnote = fn$footnote,
                               locations = fn$locations)
  }
  tbl
}

# ── Table 1: Village summary (population, journeys, transport counts) ──────────

tbl1_village_characteristics <- function() {
  dat <- .village_table_data()

  metric_rows <- tribble(
    ~metric_id,          ~Metric,
    "pediatric_pop",     "Pediatric population (under 18)",
    "mean_yr_str",       "Journeys per year, mean (SD)",
    "n_patients",        "Total patients",
    "_header_transport", "Air ambulance transports per patient",
    "t1_str",            "  1 transport",
    "t2_str",            "  2 transports",
    "t3p_str",           "  3+ transports"
  )

  .render_village_gt(
    metric_rows, dat,
    bold_header_rows = c("Pediatric population (under 18)",
                         "Air ambulance transports per patient"),
    shaded_rows      = "Air ambulance transports per patient"
  )
}

# ── Table 4: Air ambulance timing by village ───────────────────────────────────

tbl4_timing_by_village <- function() {
  dat <- .village_table_data()

  metric_rows <- tribble(
    ~metric_id,      ~Metric,
    "dist_str",      "Distance to Kotzebue (miles)",
    "total_ata_str", "Total air ambulance time, min \u2014 Median (IQR); Range",
    "_header_act",   "Air Ambulance Activation",
    "pct_act_str",   "  % with complete timing data (n)",
    "decision_str",  "  Decision-making time, min \u2014 Median (IQR); Range",
    "response_str",  "  Response and transfer time, min \u2014 Median (IQR); Range",
    "util_str",      "Utilization rate per 1,000 pediatric residents"
  )

  .render_village_gt(
    metric_rows, dat,
    bold_header_rows = "Air Ambulance Activation",
    shaded_rows      = "Air Ambulance Activation",
    footnotes = list(
      list(
        footnote  = html("Total air ambulance time = village activation \u2192 MHC arrival."),
        locations = cells_stub(rows = Metric == "Total air ambulance time, min \u2014 Median (IQR); Range")
      ),
      list(
        footnote  = "Utilization rate = village \u2192 MHC journeys per 1,000 pediatric residents under 18 (2020 Census).",
        locations = cells_stub(rows = Metric == "Utilization rate per 1,000 pediatric residents")
      )
    )
  )
}

# ── Table 2: Journey characteristics by age group (n = 309 journeys) ──────────

tbl2_patient_characteristics <- function() {
  jp <- get_journeys_primary()
  pp <- get_patients_primary()

  # Join patient-level demographics (RaceDSC, insurance_cat) that may not be
  # present on the journey file
  demo_extra <- intersect(c("RaceDSC", "insurance_cat"), names(pp))
  if (length(demo_extra) > 0) {
    jp <- jp |> left_join(
      pp |> select(MRN, all_of(demo_extra)),
      by = "MRN"
    )
  }

  # Sex
  if ("GenderDSC" %in% names(jp)) {
    jp <- jp |> mutate(
      female = factor(
        case_when(GenderDSC == "Female" ~ "Female", GenderDSC == "Male" ~ "Male",
                  TRUE ~ NA_character_),
        levels = c("Female", "Male")
      )
    )
  }

  # Race: prefer RaceDSC (text match), fall back to AI_AN flag
  if ("RaceDSC" %in% names(jp)) {
    jp <- jp |> mutate(
      ai_an = factor(
        case_when(
          grepl("indian|alaska.?native|american.?indian", RaceDSC, ignore.case = TRUE) ~ "AI/AN",
          !is.na(RaceDSC) & RaceDSC != "" ~ "Non-AI/AN",
          TRUE ~ NA_character_
        ),
        levels = c("AI/AN", "Non-AI/AN")
      )
    )
  } else if ("AI_AN" %in% names(jp)) {
    jp <- jp |> mutate(
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

  # Insurance categories: overall frequency high → low; Other always last
  if ("insurance_cat" %in% names(jp)) {
    ins_order <- jp |>
      filter(!is.na(insurance_cat)) |>
      count(insurance_cat, sort = TRUE) |>
      pull(insurance_cat)
    ins_order <- c(setdiff(ins_order, "Other"), intersect("Other", ins_order))

    jp <- jp |> mutate(
      insurance_cat = factor(insurance_cat, levels = ins_order)
    )
  }

  # Chief complaint: groups with ≥10 journeys overall, sorted high → low
  if ("primary_cedis_custom_group" %in% names(jp)) {
    reported_cc <- jp |>
      filter(!is.na(primary_cedis_custom_group)) |>
      count(primary_cedis_custom_group, sort = TRUE) |>
      filter(n >= 10) |>
      pull(primary_cedis_custom_group)

    jp <- jp |> mutate(
      primary_cedis_custom_group = factor(
        ifelse(primary_cedis_custom_group %in% reported_cc,
               primary_cedis_custom_group, NA_character_),
        levels = reported_cc
      )
    )
  }

  # Ordered variable list
  ordered_vars <- c(
    "age_at_medevac_num",
    if ("female"        %in% names(jp)) "female",
    if ("ai_an"         %in% names(jp)) "ai_an",
    if ("insurance_cat" %in% names(jp)) "insurance_cat",
    "primary_cedis_custom_group"
  )
  include_vars <- intersect(ordered_vars, names(jp))
  jp_sel <- jp |> select(all_of(c(include_vars, "age_group")))

  all_labels <- list(
    age_at_medevac_num         ~ "Age, years - Median (IQR)",
    female                     ~ "Sex",
    ai_an                      ~ "Race",
    insurance_cat              ~ "Insurance type",
    primary_cedis_custom_group ~ "Chief Complaint"
  )
  label_vars    <- lapply(all_labels, function(x) as.character(x[[2]]))
  active_labels <- all_labels[unlist(label_vars) %in% include_vars]

  jp_sel |>
    tbl_summary(
      by      = age_group,
      include = include_vars,
      label   = active_labels,
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}\u2013{p75})",
        all_categorical()  ~ "{p}% ({n})"
      ),
      digits = list(
        age_at_medevac_num ~ 1,
        all_categorical()  ~ c(1, 0)
      ),
      missing = "no"
    ) |>
    add_overall(last = FALSE) |>
    bold_labels() |>
    modify_header(label ~ "**Characteristic**") |>
    modify_caption("**Table 2.** Air ambulance patient characteristics by age group (n = 309 village-originating journeys). % (n) within each age-group column.") |>
    as_gt() |>
    .paper1_gt_theme()
}

# ── Table 3: Primary vs. Secondary comparison ──────────────────────────────────

tbl3_route_comparison <- function() {
  ja <- get_journeys_all()

  # Village-originating primary and secondary journeys only.
  # Direct tertiary excluded (too few for comparative analysis; noted in footnote).
  village_journeys <- ja |>
    filter(
      !is.na(village_name), village_name != "",
      !grepl("tertiary", route_type, ignore.case = TRUE)
    ) |>
    mutate(
      route_label = factor(
        case_when(
          grepl("Primary",   route_type, ignore.case = TRUE) ~ "Primary only",
          grepl("Secondary", route_type, ignore.case = TRUE) ~ "Secondary",
          TRUE ~ NA_character_
        ),
        levels = c("Primary only", "Secondary")
      )
    ) |>
    filter(!is.na(route_label))

  if (nrow(village_journeys) == 0) {
    return(gt(tibble(Note = "No data available.")) |> .paper1_gt_theme())
  }

  # Sex
  if ("GenderDSC" %in% names(village_journeys)) {
    village_journeys <- village_journeys |> mutate(
      female = factor(
        case_when(GenderDSC == "Female" ~ "Female", GenderDSC == "Male" ~ "Male",
                  TRUE ~ NA_character_),
        levels = c("Female", "Male")
      )
    )
  }

  # Chief complaints with ≥10 journeys overall, sorted high → low
  reported_cc <- village_journeys |>
    filter(!is.na(primary_cedis_custom_group)) |>
    count(primary_cedis_custom_group, sort = TRUE) |>
    filter(n >= 10) |>
    pull(primary_cedis_custom_group)

  village_journeys <- village_journeys |>
    mutate(
      age_group = factor(age_group,
        levels = c("<1 yr", "1\u2013<5 yr", "5\u201312 yr", "13\u201318 yr")),
      primary_cedis_custom_group = factor(
        ifelse(primary_cedis_custom_group %in% reported_cc,
               primary_cedis_custom_group, NA_character_),
        levels = reported_cc
      )
    )

  include_vars <- intersect(
    c("age_at_medevac_num", "age_group",
      if ("female" %in% names(village_journeys)) "female",
      "primary_cedis_custom_group"),
    names(village_journeys)
  )

  all_labels <- list(
    age_at_medevac_num         ~ "Age, years \u2014 Median (IQR)",
    age_group                  ~ "Age group",
    female                     ~ "Sex",
    primary_cedis_custom_group ~ "Chief Complaint (CEDIS)"
  )
  active_labels <- all_labels[
    sapply(all_labels, function(x) as.character(x[[2]]) %in% include_vars)
  ]

  cat_test_vars <- intersect(
    c("age_group", "female", "primary_cedis_custom_group"),
    include_vars
  )
  test_spec <- lapply(
    cat_test_vars,
    function(v) stats::as.formula(paste0(v, ' ~ "chisq.test"'))
  )
  if ("age_at_medevac_num" %in% include_vars) {
    test_spec <- c(list(age_at_medevac_num ~ "wilcox.test"), test_spec)
  }

  village_journeys |>
    select(route_label, all_of(include_vars)) |>
    tbl_summary(
      by      = route_label,
      include = all_of(include_vars),
      label   = active_labels,
      statistic = list(
        age_at_medevac_num ~ "{median} ({p25}\u2013{p75})",
        all_categorical()  ~ "{p}% ({n})"
      ),
      digits  = list(all_categorical() ~ c(1, 0)),
      missing = "no"
    ) |>
    add_overall(last = FALSE) |>
    add_p(
      test = test_spec,
      pvalue_fun = ~style_pvalue(.x, digits = 3)
    ) |>
    bold_labels() |>
    modify_header(
      label   ~ "**Characteristic**",
      p.value ~ "**p-value**"
    ) |>
    modify_caption(paste0(
      "**Table 3.** Patient characteristics by transport route type ",
      "(n\u00a0=\u00a0", nrow(village_journeys), " journeys)."
    )) |>
    as_gt() |>
    tab_footnote(
      footnote = "Primary only: village \u2192 MHC, no further transfer.",
      locations = cells_column_labels(columns = stat_1)
    ) |>
    tab_footnote(
      footnote = "Secondary: village \u2192 MHC \u2192 ANMC or outside facility.",
      locations = cells_column_labels(columns = stat_2)
    ) |>
    tab_footnote(
      footnote = "% (n) within each route column.",
      locations = cells_column_labels(columns = label)
    ) |>
    tab_footnote(
      footnote = "p-values: Wilcoxon rank-sum (age); chi-square (categorical).",
      locations = cells_column_labels(columns = p.value)
    ) |>
    .paper1_gt_theme()
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
    .paper1_gt_theme()
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
    return(gt(tibble(Note = "No secondary (MHC-origin) legs found.")) |> .paper1_gt_theme())
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
    .paper1_gt_theme()
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
    .paper1_gt_theme()
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
    modify_caption("**Table 5.** Time intervals (minutes), village → MHC primary transports. Median (IQR).") |>
    as_gt() |>
    .paper1_gt_theme()
}

# ── Temporal pattern stats (inline narrative) ─────────────────────────────────

temporal_stats <- function() {
  jp <- get_journeys_primary() |>
    filter(
      journey_start_year >= 2020L,
      journey_start_year <= 2024L
    )
  yr <- jp$journey_start_year
  mo <- jp$journey_start_month
  mo <- mo[!is.na(mo) & mo >= 1L & mo <= 12L]

  yr_ct <- as.integer(table(yr))
  mo_ct <- as.integer(table(mo))
  mo_names <- c(
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
  )
  mo_idx <- function(which_fn) {
    as.integer(names(mo_ct)[which_fn(mo_ct)])
  }

  list(
    peak_yr  = as.integer(names(yr_ct)[which.max(yr_ct)]),
    peak_n   = max(yr_ct),
    high_mo  = mo_names[mo_idx(which.max)],
    high_n   = max(mo_ct),
    low_mo   = mo_names[mo_idx(which.min)],
    low_n    = min(mo_ct)
  )
}

# ── Table: Clinical data completeness (PEWS, timing, vitals) ───────────────────

.completeness_age_cols <- list(
  c("Overall", NA_character_),
  c("<1 yr", "<1 yr"),
  c("1–<5 yr", "1–<5 yr"),
  c("5–12 yr", "5–12 yr"),
  c("13–18 yr", "13–18 yr")
)

.completeness_vital_labels <- c(
  "HR", "O2 sat", "BP (systolic+diastolic)", "RR", "Temp", "GCS/AVPU"
)

.completeness_column_labels <- function(jp) {
  col_names <- vapply(.completeness_age_cols, `[[`, character(1), 1)
  labels <- lapply(seq_along(.completeness_age_cols), function(i) {
    x <- .completeness_age_cols[[i]]
    age_label <- x[[2]]
    sub <- if (is.na(age_label)) jp else jp[jp$age_group == age_label, , drop = FALSE]
    md(sprintf("**%s**  \nN = %d", x[[1]], nrow(sub)))
  })
  setNames(labels, col_names)
}

.completeness_gt <- function(df, col_labels = NULL) {
  tbl <- gt(df) |> cols_label(Measure = "Measure", !!!col_labels)

  tbl |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(
        columns = Measure,
        rows = Measure == "Vital Signs Missing"
      )
    ) |>
    tab_style(
      style = cell_text(weight = "bold"),
      locations = cells_body(
        columns = Measure,
        rows = Measure %in% c("Complete PEWS data", "Timing data")
      )
    ) |>
    .paper1_gt_theme()
}

tbl_completeness_vitals_pews <- function() {
  col_names <- vapply(.completeness_age_cols, `[[`, character(1), 1)
  empty_row <- function(label = "—") {
    as.list(setNames(rep(label, length(col_names)), col_names)) |>
      c(Measure = "—", .)
  }

  jp <- get_journeys_primary()
  col_labels <- .completeness_column_labels(jp)
  if (nrow(jp) == 0) {
    return(.completeness_gt(as_tibble(empty_row()), col_labels))
  }

  journeys_for <- function(age_label) {
    if (is.na(age_label)) return(jp)
    jp |> filter(age_group == age_label)
  }

  timing_cell <- function(sub) {
    nd <- nrow(sub)
    if (nd == 0) return("—")
    if (!"time_to_activate_quality" %in% names(sub)) return("— (not available)")
    n_ok <- sum(sub$time_to_activate_quality == "real", na.rm = TRUE)
    fmt_pct_n(n_ok, nd)
  }

  first <- first_cohort_patients(jp)
  cohort_mrns <- first$mrn_k
  vitals <- load_vitals_for_cohort()

  present <- list()
  ready_mrns <- character(0)
  vitals_note <- vitals$error

  if (is.null(vitals_note)) {
    vit <- vitals$vitals
    cm <- vitals$colmap
    vit <- vit[vit$mrn_k %in% cohort_mrns, , drop = FALSE]
    present <- vital_present_sets(vit, cm, vitals$gcs_col)
    ready_mrns <- pews_ready_mrns(vit, cm, vitals$gcs_col, cohort_mrns)
  }

  patient_set <- function(age_label) {
    if (is.na(age_label)) return(cohort_mrns)
    first$mrn_k[first$age_group == age_label]
  }

  pews_cell <- function(mrns) {
    if (!is.null(vitals$error)) return(sprintf("Unable to compute (%s)", vitals$error))
    nd <- length(mrns)
    if (nd == 0) return("—")
    if (is.null(vitals$gcs_col)) return("— (missing GCS)")
    fmt_pct_n(length(intersect(mrns, ready_mrns)), nd)
  }

  miss_cell <- function(mrns, vital_label) {
    if (!is.null(vitals$error)) return(sprintf("Unable to compute (%s)", vitals$error))
    nd <- length(mrns)
    if (nd == 0) return("—")
    if (vital_label == "GCS/AVPU" && is.null(vitals$gcs_col)) return("— (not available)")
    if (is.null(present[[vital_label]])) return("— (not available)")
    n_miss <- nd - length(intersect(mrns, present[[vital_label]]))
    fmt_pct_n(n_miss, nd)
  }

  row_from_values <- function(measure, values) {
    tibble(Measure = measure, !!!setNames(values, col_names))
  }

  pews_vals <- vapply(.completeness_age_cols, function(x) pews_cell(patient_set(x[[2]])), character(1))
  timing_vals <- vapply(.completeness_age_cols, function(x) timing_cell(journeys_for(x[[2]])), character(1))

  df <- bind_rows(
    row_from_values("Timing data", timing_vals),
    row_from_values("Complete PEWS data", pews_vals),
    row_from_values("Vital Signs Missing", rep("", length(col_names)))
  )

  for (vital_label in .completeness_vital_labels) {
    miss_vals <- vapply(
      .completeness_age_cols,
      function(x) miss_cell(patient_set(x[[2]]), vital_label),
      character(1)
    )
    df <- bind_rows(df, row_from_values(paste0("  ", vital_label), miss_vals))
  }

  .completeness_gt(df, col_labels)
}
