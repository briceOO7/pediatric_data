# Manuscript-ready R Sankey/alluvial figures for pediatric medevac routes.
#
# Outputs:
#   figures/figure4_medevac_routes_ggforce.{png,svg,pdf}
#   figures/figure4_medevac_routes_alluvial.{png,svg,pdf}
#
# Package choices:
#   - ggforce: best for reproducing the custom route-map layout in the source
#     figure while staying inside the ggplot2 ecosystem.
#   - ggalluvial: best for a conventional, data-determined static alluvial
#     figure suitable for manuscript workflows.

required <- c("ggplot2", "ggforce", "ggalluvial", "ragg", "svglite")
missing <- required[!vapply(required, requireNamespace, logical(1), quietly = TRUE)]
if (length(missing) > 0) {
  stop(
    "Missing required package(s): ", paste(missing, collapse = ", "),
    "\nRestore the R environment with:\n",
    "renv::restore()",
    call. = FALSE
  )
}

library(ggplot2)
library(ggforce)
library(ggalluvial)

dir.create("figures", showWarnings = FALSE, recursive = TRUE)

theme_medevac <- function(base_size = 9) {
  theme_void(base_size = base_size) +
    theme(
      plot.title = element_text(hjust = 0.5, size = 14, face = "plain", margin = margin(b = 12)),
      plot.margin = margin(14, 22, 10, 22),
      legend.position = "bottom",
      legend.title = element_text(size = 8),
      legend.text = element_text(size = 7),
      text = element_text(family = "Helvetica", colour = "#2f2f2f")
    )
}

default_village_colours <- c(
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8",
  "#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#76b7b2"
)

facility_palette <- c("#f47c2c", "#4472c4", "#8e63c7", "#59a14f", "#e15759", "#76b7b2")

normalise_facility <- function(x) {
  x <- trimws(as.character(x))
  x[x %in% c("", "NA", "N/A", "None", "none", "No secondary transfer")] <- NA_character_
  x
}

normalise_bool <- function(x) {
  if (is.logical(x)) return(x)
  x <- tolower(trimws(as.character(x)))
  ifelse(x %in% c("1", "true", "t", "yes", "y", "mhc", "maniilaq", "maniilaq health center"), TRUE,
         ifelse(x %in% c("0", "false", "f", "no", "n", "direct"), FALSE, NA))
}

count_pairs <- function(data, group_cols) {
  if (nrow(data) == 0) {
    empty <- as.data.frame(setNames(rep(list(character()), length(group_cols)), group_cols))
    empty$n <- integer()
    return(empty)
  }
  counts <- aggregate(rep(1L, nrow(data)), data[group_cols], sum)
  names(counts)[ncol(counts)] <- "n"
  counts
}

sum_pairs <- function(data, group_cols, weight_col) {
  if (nrow(data) == 0) {
    empty <- as.data.frame(setNames(rep(list(character()), length(group_cols)), group_cols))
    empty$n <- integer()
    return(empty)
  }
  counts <- aggregate(data[[weight_col]], data[group_cols], sum)
  names(counts)[ncol(counts)] <- "n"
  counts
}

clean_column_names <- function(data) {
  names(data) <- tolower(gsub("[^a-zA-Z0-9]+", "_", trimws(names(data))))
  names(data) <- gsub("^_|_$", "", names(data))
  names(data)[names(data) == "village_of_origin"] <- "origin"
  names(data)[names(data) == "n_legs"] <- "n_legs"
  data
}

make_summary <- function(routes) {
  required_cols <- c("village", "mhc", "receiving_facility")
  missing_cols <- setdiff(required_cols, names(routes))
  if (length(missing_cols) > 0) {
    stop(
      "Input CSV is missing required column(s): ", paste(missing_cols, collapse = ", "),
      "\nExpected columns: village,mhc,receiving_facility",
      call. = FALSE
    )
  }

  routes <- routes[required_cols]
  routes$village <- trimws(as.character(routes$village))
  routes$mhc <- normalise_bool(routes$mhc)
  routes$receiving_facility <- normalise_facility(routes$receiving_facility)
  routes <- routes[!is.na(routes$village) & routes$village != "" & !is.na(routes$mhc), ]
  if (nrow(routes) == 0) {
    stop("No usable route rows after dropping blank villages or unparseable mhc values.", call. = FALSE)
  }

  village_counts <- count_pairs(routes, "village")
  names(village_counts)[names(village_counts) == "n"] <- "total"
  mhc_counts <- count_pairs(routes[routes$mhc, ], "village")
  names(mhc_counts)[names(mhc_counts) == "n"] <- "to_mhc"
  villages <- merge(village_counts, mhc_counts, by = "village", all.x = TRUE)
  villages$to_mhc[is.na(villages$to_mhc)] <- 0L
  villages <- villages[order(-villages$total, villages$village), ]
  names(villages)[names(villages) == "total"] <- "n"
  villages$colour <- rep(default_village_colours, length.out = nrow(villages))

  direct_routes <- routes[!routes$mhc & !is.na(routes$receiving_facility), c("village", "receiving_facility")]
  direct_counts <- if (nrow(direct_routes) > 0) count_pairs(direct_routes, c("village", "receiving_facility")) else
    data.frame(village = character(), receiving_facility = character(), n = integer())

  secondary_routes <- routes[routes$mhc & !is.na(routes$receiving_facility), "receiving_facility", drop = FALSE]
  secondary_counts <- if (nrow(secondary_routes) > 0) count_pairs(secondary_routes, "receiving_facility") else
    data.frame(receiving_facility = character(), n = integer())

  receiving_routes <- routes[!is.na(routes$receiving_facility), "receiving_facility", drop = FALSE]
  facility_counts <- if (nrow(receiving_routes) > 0) count_pairs(receiving_routes, "receiving_facility") else
    data.frame(receiving_facility = character(), n = integer())

  total_n <- nrow(routes)
  mhc_n <- sum(routes$mhc)
  secondary_n <- sum(routes$mhc & !is.na(routes$receiving_facility))

  list(
    villages = villages,
    direct_counts = direct_counts,
    secondary_counts = secondary_counts,
    facility_counts = facility_counts,
    total_n = total_n,
    mhc_n = mhc_n,
    secondary_n = secondary_n,
    mhc_only_n = mhc_n - secondary_n
  )
}

make_summary_from_aggregate <- function(legs) {
  required_cols <- c("leg_type", "origin", "destination", "n_legs")
  missing_cols <- setdiff(required_cols, names(legs))
  if (length(missing_cols) > 0) {
    stop(
      "Aggregate CSV is missing required column(s): ", paste(missing_cols, collapse = ", "),
      "\nExpected columns: leg_type,origin,destination,n_legs",
      call. = FALSE
    )
  }

  legs <- legs[required_cols]
  legs$leg_type <- tolower(trimws(as.character(legs$leg_type)))
  legs$origin <- trimws(as.character(legs$origin))
  legs$destination <- normalise_facility(legs$destination)
  legs$n_legs <- as.integer(legs$n_legs)
  legs <- legs[!is.na(legs$origin) & legs$origin != "" & !is.na(legs$n_legs) & legs$n_legs > 0, ]
  if (nrow(legs) == 0) {
    stop("No usable aggregate leg rows after parsing origin and n_legs.", call. = FALSE)
  }

  primary <- legs[legs$leg_type == "primary", ]
  secondary <- legs[legs$leg_type == "secondary", ]
  direct <- legs[legs$leg_type == "direct", ]
  if (nrow(primary) == 0) {
    stop("Aggregate input must include at least one primary leg row.", call. = FALSE)
  }

  primary_counts <- sum_pairs(primary, "origin", "n_legs")
  direct_village_counts <- sum_pairs(direct, "origin", "n_legs")
  village_counts <- merge(primary_counts, direct_village_counts, by = "origin", all = TRUE, suffixes = c("_primary", "_direct"))
  village_counts$n_primary[is.na(village_counts$n_primary)] <- 0L
  village_counts$n_direct[is.na(village_counts$n_direct)] <- 0L

  villages <- data.frame(
    village = village_counts$origin,
    n = village_counts$n_primary + village_counts$n_direct,
    to_mhc = village_counts$n_primary,
    stringsAsFactors = FALSE
  )
  villages <- villages[order(-villages$n, villages$village), ]
  villages$colour <- rep(default_village_colours, length.out = nrow(villages))

  direct_counts <- if (nrow(direct) > 0) {
    names(direct)[names(direct) == "origin"] <- "village"
    names(direct)[names(direct) == "destination"] <- "receiving_facility"
    sum_pairs(direct, c("village", "receiving_facility"), "n_legs")
  } else {
    data.frame(village = character(), receiving_facility = character(), n = integer())
  }

  secondary_counts <- if (nrow(secondary) > 0) {
    names(secondary)[names(secondary) == "destination"] <- "receiving_facility"
    sum_pairs(secondary, "receiving_facility", "n_legs")
  } else {
    data.frame(receiving_facility = character(), n = integer())
  }

  facility_counts <- rbind(
    if (nrow(direct_counts) > 0) aggregate(n ~ receiving_facility, direct_counts, sum),
    secondary_counts
  )
  facility_counts <- if (nrow(facility_counts) > 0) {
    aggregate(n ~ receiving_facility, facility_counts, sum)
  } else {
    data.frame(receiving_facility = character(), n = integer())
  }

  mhc_n <- sum(primary$n_legs)
  secondary_n <- sum(secondary$n_legs)

  list(
    villages = villages,
    direct_counts = direct_counts,
    secondary_counts = secondary_counts,
    facility_counts = facility_counts,
    total_n = sum(villages$n),
    mhc_n = mhc_n,
    secondary_n = secondary_n,
    mhc_only_n = mhc_n - secondary_n
  )
}

args <- commandArgs(trailingOnly = TRUE)
input_csv <- if (length(args) >= 1) args[[1]] else Sys.getenv("MEDEVAC_ROUTES_CSV", unset = "")
if (!nzchar(input_csv)) {
  stop(
    "No input CSV supplied. Run:\n",
    "  Rscript scripts/medevac_sankey_manuscript.R /secure/path/medevac_routes.csv\n",
    "or set MEDEVAC_ROUTES_CSV=/secure/path/medevac_routes.csv",
    call. = FALSE
  )
}
route_rows <- read.csv(input_csv, stringsAsFactors = FALSE, na.strings = c("", "NA", "N/A"), check.names = FALSE)
route_rows <- clean_column_names(route_rows)
if (all(c("village", "mhc", "receiving_facility") %in% names(route_rows))) {
  route_summary <- make_summary(route_rows)
} else if (all(c("leg_type", "origin", "destination", "n_legs") %in% names(route_rows))) {
  route_summary <- make_summary_from_aggregate(route_rows)
} else {
  stop(
    "Input CSV must be either row-level columns village,mhc,receiving_facility ",
    "or aggregate columns leg_type,origin,destination,n_legs.",
    call. = FALSE
  )
}
message("Loaded route data from ", normalizePath(input_csv))

villages <- route_summary$villages
direct_counts <- route_summary$direct_counts
secondary_counts <- route_summary$secondary_counts

facility_names <- unique(route_summary$facility_counts$receiving_facility)
facility_names <- facility_names[!is.na(facility_names)]
if (length(facility_names) == 0) {
  stop("No receiving facilities found in the input data.", call. = FALSE)
}
facility_counts <- merge(
  data.frame(receiving_facility = facility_names, stringsAsFactors = FALSE),
  route_summary$facility_counts,
  by = "receiving_facility",
  all.x = TRUE
)
facility_counts$n[is.na(facility_counts$n)] <- 0L
facility_counts <- facility_counts[facility_counts$n > 0, ]
facility_counts <- facility_counts[order(-facility_counts$n, facility_counts$receiving_facility), ]

facility_y <- if (nrow(facility_counts) == 1) {
  8.2
} else {
  seq(8.2, 1.8, length.out = nrow(facility_counts))
}
names(facility_y) <- facility_counts$receiving_facility

facilities <- data.frame(
  facility = facility_counts$receiving_facility,
  n = facility_counts$n,
  colour = rep(facility_palette, length.out = nrow(facility_counts)),
  x = 7.25,
  y = unname(facility_y[facility_counts$receiving_facility]),
  stringsAsFactors = FALSE
)

villages$x <- 1.35
villages$y <- seq(8.6, 0.55, length.out = nrow(villages))
mhc <- data.frame(node = sprintf("Maniilaq\nHealth Center\nn = %d", route_summary$mhc_n), x = 4.9, y = 5.0)

make_curve <- function(id, x0, y0, x1, y1, value, colour, kind,
                       c1x = NULL, c2x = NULL, c1y = NULL, c2y = NULL) {
  if (is.null(c1x)) c1x <- x0 + (x1 - x0) * 0.55
  if (is.null(c2x)) c2x <- x0 + (x1 - x0) * 0.45
  if (is.null(c1y)) c1y <- y0
  if (is.null(c2y)) c2y <- y1
  data.frame(
    id = id,
    x = c(x0, c1x, c2x, x1),
    y = c(y0, c1y, c2y, y1),
    value = value,
    colour = colour,
    kind = kind,
    stringsAsFactors = FALSE
  )
}

village_to_mhc <- do.call(
  rbind,
  lapply(seq_len(nrow(villages)), function(i) {
    make_curve(
      id = paste0("village_mhc_", i),
      x0 = villages$x[i] + 0.18,
      y0 = villages$y[i],
      x1 = mhc$x - 0.62,
      y1 = mhc$y,
      value = villages$to_mhc[i],
      colour = villages$colour[i],
      kind = "Village to MHC",
      c1x = 2.55,
      c2x = 3.7,
      c1y = villages$y[i],
      c2y = mhc$y
    )
  })
)

direct_to_facility <- if (nrow(direct_counts) > 0) do.call(
  rbind,
  lapply(seq_len(nrow(direct_counts)), function(i) {
    village_i <- match(direct_counts$village[i], villages$village)
    facility_i <- match(direct_counts$receiving_facility[i], facilities$facility)
    make_curve(
      id = paste0("direct_", i),
      x0 = villages$x[village_i] + 0.18,
      y0 = villages$y[village_i],
      x1 = 6.86,
      y1 = facilities$y[facility_i],
      value = direct_counts$n[i],
      colour = villages$colour[village_i],
      kind = "Direct to facility",
      c1x = 3.4,
      c2x = 5.8,
      c1y = villages$y[village_i],
      c2y = facilities$y[facility_i]
    )
  })
) else NULL

mhc_to_facility <- if (nrow(secondary_counts) > 0) do.call(
  rbind,
  lapply(seq_len(nrow(secondary_counts)), function(i) {
    facility_i <- match(secondary_counts$receiving_facility[i], facilities$facility)
    make_curve(
      id = paste0("mhc_facility_", i),
      x0 = 5.52,
      y0 = 5.0,
      x1 = 7.03,
      y1 = facilities$y[facility_i],
      value = secondary_counts$n[i],
      colour = "#8c8c8c",
      kind = "MHC to facility",
      c1x = 6.2,
      c2x = 6.85,
      c1y = 5.0,
      c2y = facilities$y[facility_i]
    )
  })
) else NULL

curves <- do.call(rbind, Filter(Negate(is.null), list(village_to_mhc, direct_to_facility, mhc_to_facility)))
curves$curve_group <- curves$id
curves$secondary <- curves$kind == "MHC to facility"

village_nodes <- transform(
  villages,
  label = sprintf("%s  %d", village, n),
  a = 0.19,
  b = 0.18
)
facility_nodes <- transform(
  facilities,
  label = sprintf("%s\nn = %d", facility, n),
  a = 0.18 + 0.16 * sqrt(n / max(n)),
  b = 0.15 + 0.13 * sqrt(n / max(n))
)

secondary_label_data <- if (nrow(secondary_counts) > 0) {
  label_facilities <- merge(
    secondary_counts,
    facilities[, c("facility", "y")],
    by.x = "receiving_facility",
    by.y = "facility",
    all.x = TRUE
  )
  transform(
    label_facilities,
    x = 6.15,
    y = (5.0 + y) / 2,
    label = sprintf("2 deg n=%d", n)
  )
} else {
  data.frame(x = numeric(), y = numeric(), label = character())
}

route_plot <- ggplot() +
  geom_bezier(
    data = curves,
    aes(x = x, y = y, group = curve_group, colour = colour, linewidth = value, linetype = secondary),
    alpha = 0.72,
    lineend = "round",
    show.legend = c(colour = FALSE, linewidth = TRUE, linetype = TRUE),
    n = 120
  ) +
  geom_ellipse(
    data = village_nodes,
    aes(x0 = x, y0 = y, a = a, b = b, angle = 0, fill = colour),
    colour = NA,
    show.legend = FALSE
  ) +
  geom_ellipse(
    data = facility_nodes,
    aes(x0 = x, y0 = y, a = a, b = b, angle = 0, fill = colour),
    colour = NA,
    show.legend = FALSE
  ) +
  geom_ellipse(
    data = data.frame(x = mhc$x, y = mhc$y, a = 0.62, b = 0.52),
    aes(x0 = x, y0 = y, a = a, b = b, angle = 0),
    fill = "#6cad3d",
    colour = NA
  ) +
  geom_text(
    data = village_nodes,
    aes(x = x - 0.28, y = y, label = label),
    hjust = 1,
    size = 2.65
  ) +
  geom_text(
    data = mhc,
    aes(x = x, y = y, label = node),
    colour = "white",
    fontface = "bold",
    lineheight = 0.86,
    size = 3
  ) +
  geom_text(
    data = facility_nodes,
    aes(x = x + 0.32, y = y, label = label, colour = colour),
    hjust = 0,
    fontface = "bold",
    lineheight = 0.86,
    size = 2.75,
    show.legend = FALSE
  ) +
  annotate("text", x = 1.35, y = 9.22, label = "Village Clinics", fontface = "bold", size = 3.4) +
  annotate("text", x = 4.9, y = 9.25, label = "Maniilaq\nHealth Center", fontface = "bold", size = 3.4, lineheight = 0.9) +
  annotate("text", x = 7.75, y = 9.22, label = "Receiving Facilities", fontface = "bold", size = 3.4) +
  geom_label(
    data = secondary_label_data,
    aes(x = x, y = y, label = label),
    size = 2.1,
    linewidth = 0.16,
    label.r = unit(0.04, "lines"),
    fill = "#f7f7f7",
    colour = "#666666"
  ) +
  scale_colour_identity() +
  scale_fill_identity() +
  scale_linetype_manual(
    name = NULL,
    values = c("FALSE" = "solid", "TRUE" = "longdash"),
    labels = c("FALSE" = "primary or direct", "TRUE" = "MHC to facility (secondary)")
  ) +
  scale_linewidth(
    name = "Transfer volume",
    range = c(0.35, 7.2),
    breaks = c(1, 35, 71)
  ) +
  coord_cartesian(xlim = c(0.2, 8.5), ylim = c(0.0, 9.55), clip = "off", expand = FALSE) +
  labs(title = sprintf("Figure 2. Pediatric Medevac Routes by Village  (n = %d journeys)", route_summary$total_n)) +
  guides(
    linewidth = guide_legend(order = 1, override.aes = list(colour = "#595959")),
    linetype = guide_legend(order = 2, override.aes = list(colour = "#595959", linewidth = 0.8))
  ) +
  theme_medevac()

ggsave(
  "figures/figure4_medevac_routes_ggforce.png",
  route_plot,
  width = 11.5,
  height = 7.6,
  dpi = 450,
  device = ragg::agg_png,
  bg = "white"
)
ggsave("figures/figure4_medevac_routes_ggforce.svg", route_plot, width = 11.5, height = 7.6, device = svglite::svglite, bg = "white")
ggsave("figures/figure4_medevac_routes_ggforce.pdf", route_plot, width = 11.5, height = 7.6, device = grDevices::pdf, bg = "white")

direct_by_facility <- if (nrow(direct_counts) > 0) {
  aggregate(n ~ receiving_facility, direct_counts, sum)
} else {
  data.frame(receiving_facility = character(), n = integer())
}

alluvial_data <- rbind(
  data.frame(
    step1 = "Village clinics",
    step2 = "Maniilaq Health Center",
    step3 = "No secondary transfer",
    n = route_summary$mhc_only_n,
    route_type = "MHC only",
    stringsAsFactors = FALSE
  ),
  if (nrow(secondary_counts) > 0) {
    data.frame(
      step1 = "Village clinics",
      step2 = "Maniilaq Health Center",
      step3 = paste0(secondary_counts$receiving_facility, " secondary"),
      n = secondary_counts$n,
      route_type = "Secondary transfer",
      stringsAsFactors = FALSE
    )
  },
  if (nrow(direct_by_facility) > 0) {
    data.frame(
      step1 = "Village clinics",
      step2 = "Direct to facility",
      step3 = paste0(direct_by_facility$receiving_facility, " direct"),
      n = direct_by_facility$n,
      route_type = "Direct transfer",
      stringsAsFactors = FALSE
    )
  }
)
alluvial_data <- alluvial_data[alluvial_data$n > 0, ]

alluvial_data$step1 <- factor(alluvial_data$step1, levels = "Village clinics")
alluvial_data$step2 <- factor(alluvial_data$step2, levels = c("Maniilaq Health Center", "Direct to facility"))
alluvial_data$step3 <- factor(alluvial_data$step3, levels = unique(alluvial_data$step3))

small_secondary <- secondary_counts[secondary_counts$n < 10, , drop = FALSE]
small_secondary_label <- if (nrow(small_secondary) > 0) {
  paste(
    c(
      "Small secondary outcomes:",
      sprintf("%s n = %d", small_secondary$receiving_facility, small_secondary$n)
    ),
    collapse = "\n"
  )
} else {
  ""
}

alluvial_plot <- ggplot(
  alluvial_data,
  aes(axis1 = step1, axis2 = step2, axis3 = step3, y = n)
) +
  geom_alluvium(aes(fill = route_type), width = 0.13, alpha = 0.78, knot.pos = 0.42) +
  geom_stratum(width = 0.13, fill = "#f7f7f7", colour = "#666666", linewidth = 0.24) +
  geom_text(
    stat = "stratum",
    aes(label = after_stat(ifelse(count >= 10, as.character(stratum), ""))),
    size = 2.75,
    lineheight = 0.88
  ) +
  annotate(
    "text",
    x = 2.62,
    y = max(16, route_summary$secondary_n + 22),
    label = small_secondary_label,
    hjust = 0,
    size = 2.45,
    lineheight = 0.9,
    colour = "#4f4f4f"
  ) +
  scale_x_discrete(limits = c("Origin", "First destination", "Final disposition"), expand = c(0.08, 0.04)) +
  scale_fill_manual(values = c("MHC only" = "#5a9bd4", "Secondary transfer" = "#8c8c8c", "Direct transfer" = "#f47c2c")) +
  labs(
    title = "Aggregate Pediatric Medevac Transfer Disposition",
    x = NULL,
    y = "Journeys",
    fill = NULL
  ) +
  theme_minimal(base_size = 9) +
  theme(
    panel.grid.major.x = element_blank(),
    panel.grid.minor = element_blank(),
    axis.text.y = element_blank(),
    axis.title.y = element_text(size = 8),
    plot.title = element_text(hjust = 0.5, size = 13),
    legend.position = "bottom"
  )

ggsave(
  "figures/figure4_medevac_routes_alluvial.png",
  alluvial_plot,
  width = 9.0,
  height = 6.2,
  dpi = 450,
  device = ragg::agg_png,
  bg = "white"
)
ggsave("figures/figure4_medevac_routes_alluvial.svg", alluvial_plot, width = 9.0, height = 6.2, device = svglite::svglite, bg = "white")
ggsave("figures/figure4_medevac_routes_alluvial.pdf", alluvial_plot, width = 9.0, height = 6.2, device = grDevices::pdf, bg = "white")

message("Wrote manuscript figures to ", normalizePath("figures"))
