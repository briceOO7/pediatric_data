# paper1_figures.R — Figure builders for Paper 1
# Depends on: ggplot2, ggalluvial, dplyr, here, readr

library(ggplot2)
library(ggalluvial)
library(dplyr)
library(here)
library(readr)

# ── Data loading ───────────────────────────────────────────────────────────────

.load_journeys_all_fig <- function() {
  path <- here("outputs", "data", "journeys_all.csv")
  read_csv(path, show_col_types = FALSE)
}

# ── Figure 2: Sankey / alluvial transport route diagram ───────────────────────

#' Build alluvial flow data from journeys_all.csv
#'
#' Returns a data frame with one row per village-originating journey and
#' columns: origin, stop1, final.
.build_sankey_data <- function() {
  ja <- .load_journeys_all_fig()

  village_journeys <- ja |>
    filter(!is.na(village_name), village_name != "")

  classify <- function(route_type, medevac2_to, medevac1_to) {
    is_primary   <- grepl("Primary",   route_type, ignore.case = TRUE)
    is_secondary <- grepl("Secondary", route_type, ignore.case = TRUE)
    is_tertiary  <- grepl("tertiary",  route_type, ignore.case = TRUE)
    is_anmc      <- grepl("ANMC|Alaska Native Medical|Hub_01",
                          ifelse(is.na(medevac2_to), "", medevac2_to),
                          ignore.case = TRUE)

    stop1 <- case_when(
      is_primary   ~ "MHC",
      is_secondary ~ "MHC",
      is_tertiary  ~ "ANMC",
      TRUE         ~ "MHC"
    )

    final <- case_when(
      is_primary   ~ "Managed at MHC",
      is_secondary & is_anmc  ~ "ANMC",
      is_secondary & !is_anmc ~ "Other Tertiary",
      is_tertiary  ~ "ANMC",
      TRUE         ~ "Managed at MHC"
    )

    list(stop1 = stop1, final = final)
  }

  classified <- with(village_journeys,
    classify(route_type,
             if ("medevac2_to" %in% names(village_journeys)) medevac2_to else NA_character_,
             if ("medevac1_to" %in% names(village_journeys)) medevac1_to else NA_character_)
  )

  village_journeys |>
    mutate(
      origin = "Village",
      stop1  = classified$stop1,
      final  = classified$final
    ) |>
    select(origin, stop1, final)
}

#' Publication-ready alluvial/Sankey diagram of pediatric air ambulance routes
#'
#' Shows all village-originating journeys as a three-stage flow:
#'   Village → first stop (MHC or ANMC) → final disposition
#'
#' @return A ggplot2 object
fig2_sankey_routes <- function() {
  df <- .build_sankey_data()
  n_total <- nrow(df)

  # Count journeys per node for labeling
  node_counts <- list(
    village     = n_total,
    mhc         = sum(df$stop1 == "MHC"),
    anmc_direct = sum(df$stop1 == "ANMC"),
    managed_mhc = sum(df$final == "Managed at MHC"),
    anmc_final  = sum(df$final == "ANMC"),
    other_tert  = sum(df$final == "Other Tertiary")
  )

  # Factor ordering for alluvial axes — controls top-to-bottom node stacking
  df <- df |>
    mutate(
      origin = factor(origin, levels = "Village"),
      stop1  = factor(stop1,  levels = c("MHC", "ANMC")),
      final  = factor(final,  levels = c("Managed at MHC", "ANMC", "Other Tertiary"))
    )

  # Summarise to frequency table for geom_alluvium / geom_stratum
  df_freq <- df |>
    count(origin, stop1, final, name = "freq")

  # Color palette: one color per final destination
  palette <- c(
    "Managed at MHC" = "#4E9BB5",   # muted teal/blue
    "ANMC"           = "#E07B39",   # warm amber/orange
    "Other Tertiary" = "#9B7BB5"    # muted purple
  )

  # Build node labels with counts (shown inside strata)
  # geom_text on strata with stage-specific counts
  make_label <- function(name, n) {
    if (n == 0) return(paste0(name, "\nn = 0"))
    paste0(name, "\nn\u00a0=\u00a0", n)
  }

  stratum_labels <- data.frame(
    x = c(1, 2, 2, 3, 3, 3),
    stratum = c(
      make_label("Village",         node_counts$village),
      make_label("MHC",             node_counts$mhc),
      make_label("ANMC\n(direct)",  node_counts$anmc_direct),
      make_label("Managed\nat MHC", node_counts$managed_mhc),
      make_label("ANMC",            node_counts$anmc_final),
      make_label("Other\nTertiary", node_counts$other_tert)
    ),
    stratum_key = c(
      "Village",
      "MHC", "ANMC",
      "Managed at MHC", "ANMC", "Other Tertiary"
    )
  ) |>
    filter(!(stratum_key %in% c("ANMC", "Other Tertiary") & grepl("n\u00a0=\u00a00", stratum) == FALSE |
            (stratum_key == "ANMC" & x == 2 & node_counts$anmc_direct == 0)))

  p <- ggplot(
    df_freq,
    aes(axis1 = origin, axis2 = stop1, axis3 = final, y = freq)
  ) +
    geom_alluvium(
      aes(fill = final),
      width    = 1/4,
      alpha    = 0.75,
      knot.pos = 0.4,
      color    = NA
    ) +
    geom_stratum(
      width     = 1/4,
      fill      = "#F0F0F0",
      color     = "#666666",
      linewidth = 0.4
    ) +
    geom_label(
      stat  = "stratum",
      aes(label = after_stat(stratum)),
      size       = 3.2,
      fontface   = "bold",
      fill       = "white",
      color      = "#333333",
      linewidth  = 0.3,
      label.r    = unit(0.15, "lines"),
      lineheight = 0.9
    ) +
    scale_fill_manual(values = palette, name = "Final Disposition") +
    scale_x_discrete(
      limits = c("origin", "stop1", "final"),
      labels = c("Stage\u00a01\nOrigin", "Stage\u00a02\nFirst Stop", "Stage\u00a03\nFinal Disposition"),
      expand = expansion(add = 0.6)
    ) +
    scale_y_continuous(expand = expansion(mult = 0.02)) +
    labs(
      title    = paste0("Air Ambulance Transport Routes (n\u00a0=\u00a0", n_total,
                        " village-originating journeys)"),
      subtitle = "Flow width proportional to journey volume",
      x        = NULL,
      y        = "Number of Journeys"
    ) +
    theme_void(base_size = 11) +
    theme(
      plot.title      = element_text(size = 12, face = "bold", hjust = 0.5,
                                     margin = margin(b = 4)),
      plot.subtitle   = element_text(size = 10, color = "#555555", hjust = 0.5,
                                     margin = margin(b = 8)),
      axis.text.x     = element_text(size = 10, face = "bold", color = "#333333",
                                     margin = margin(t = 6)),
      legend.position = "none",
      plot.margin     = margin(12, 16, 12, 16)
    )

  p
}

#' Save Figure 2 Sankey to outputs/figures/fig2_sankey_routes.png
#'
#' @param width  inches (default 8)
#' @param height inches (default 5)
#' @param dpi    resolution (default 300)
save_fig2_sankey <- function(width = 8, height = 5, dpi = 300) {
  out_dir <- here("outputs", "figures")
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  out_path <- file.path(out_dir, "fig2_sankey_routes.png")
  p <- fig2_sankey_routes()
  ggsave(out_path, plot = p, width = width, height = height, dpi = dpi,
         bg = "white")
  invisible(out_path)
}
