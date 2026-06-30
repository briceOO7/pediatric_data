# paper1_figures.R — Publication-ready figures for Paper 1
#
# Coordinates source: mapping_data/healthcare_facilities_safetynet/
#   (Maniilaq Association facilities, same as Python medevac_map_fig1.py)
# Borough boundary:   mapping_data/Boroughs2020/Boroughs2020.shp
# Utilization data:   outputs/data/village_summary.csv
#                     (fallback: docs/maniilaq_village_census2020_pediatric.csv)
#
# Projection: Alaska Albers Equal Area, EPSG:3338

suppressPackageStartupMessages({
  library(sf)
  library(ggplot2)
  library(ggrepel)
  library(ggspatial)
  library(dplyr)
  library(viridis)
  library(patchwork)
  library(here)
})

# ── Paths ─────────────────────────────────────────────────────────────────────

.FAC_SHP     <- here("mapping_data", "healthcare_facilities_safetynet",
                     "healthcare_facilities_safetynet.shp")
.BOROUGH_SHP <- here("mapping_data", "Boroughs2020", "Boroughs2020.shp")
.CENSUS_CSV  <- here("docs", "maniilaq_village_census2020_pediatric.csv")
.SUMMARY_CSV <- here("outputs", "data", "village_summary.csv")

# ── Data loading helpers ───────────────────────────────────────────────────────

.load_maniilaq_facilities <- function() {
  fac <- st_read(.FAC_SHP, quiet = TRUE)
  man <- fac[fac$ManagingOr == "Maniilaq Association", ]
  man <- man |>
    rename(village_name = CommunityN) |>
    mutate(village_name = trimws(as.character(village_name))) |>
    distinct(village_name, .keep_all = TRUE) |>
    st_transform(crs = 3338)
  man
}

.load_borough_boundary <- function() {
  bor <- st_read(.BOROUGH_SHP, quiet = TRUE)
  ak  <- bor[bor$STATE == "02", ]
  nwab <- ak[grepl("Northwest Arctic", ak$NAME, ignore.case = TRUE), ]
  st_transform(nwab, crs = 3338)
}

# Returns the North Slope Borough (where Point Hope is located)
.load_north_slope <- function() {
  bor <- st_read(.BOROUGH_SHP, quiet = TRUE)
  ak  <- bor[bor$STATE == "02", ]
  ns  <- ak[grepl("North Slope", ak$NAME, ignore.case = TRUE), ]
  if (nrow(ns) == 0) return(NULL)
  st_transform(ns, crs = 3338)
}

.load_utilization <- function() {
  if (file.exists(.SUMMARY_CSV)) {
    df <- read.csv(.SUMMARY_CSV, stringsAsFactors = FALSE)
    # Normalise column names
    if ("village_name" %in% names(df) && "util_rate" %in% names(df)) {
      df <- df[df$village_name != "Overall", ]
      return(df[, intersect(
        c("village_name", "util_rate", "n_journeys", "n_patients", "pediatric_pop"),
        names(df)
      )])
    }
  }
  # Fallback: census only — utilization rates will be NA
  census <- read.csv(.CENSUS_CSV, stringsAsFactors = FALSE)
  kotz   <- grepl("Kotzebue", census$NAME, ignore.case = TRUE)
  census <- census[!kotz, ]
  data.frame(
    village_name  = census$NAME,
    util_rate     = NA_real_,
    n_journeys    = NA_integer_,
    n_patients    = NA_integer_,
    pediatric_pop = census$pediatric_pop,
    stringsAsFactors = FALSE
  )
}

# ── Voronoi computation ────────────────────────────────────────────────────────

.compute_voronoi <- function(pts_sf, clip_geom) {
  # Build a single multipoint, compute voronoi, explode to polygons
  mp    <- st_union(pts_sf)
  env   <- st_convex_hull(st_buffer(clip_geom, dist = 200000))
  voron <- st_voronoi(mp, envelope = env)
  voron_poly <- st_collection_extract(voron, "POLYGON")
  voron_clipped <- st_intersection(voron_poly, clip_geom)

  # Match each clipped polygon back to the nearest input point
  pts_coords <- st_coordinates(pts_sf)
  centroids  <- st_centroid(voron_clipped)
  centroid_coords <- st_coordinates(centroids)

  idx <- apply(centroid_coords, 1, function(c_pt) {
    dists <- sqrt((pts_coords[, 1] - c_pt[1])^2 + (pts_coords[, 2] - c_pt[2])^2)
    which.min(dists)
  })

  # Attach attributes from input points
  result <- pts_sf[idx, ] |>
    st_drop_geometry() |>
    mutate(geometry = st_geometry(voron_clipped)) |>
    st_as_sf()
  result
}

# ── Alaska context inset ───────────────────────────────────────────────────────

.make_alaska_inset <- function(highlight_geom) {
  # Use local borough shapefile to build Alaska context inset
  bor <- tryCatch(
    {
      b <- st_read(.BOROUGH_SHP, quiet = TRUE)
      b[b$STATE == "02", ] |> st_transform(crs = 3338)
    },
    error = function(e) NULL
  )
  if (is.null(bor)) return(NULL)

  # Dissolve all boroughs to Alaska outline
  ak_outline <- st_union(bor)

  nwab_highlight <- highlight_geom |> st_union()

  inset <- ggplot() +
    geom_sf(data = ak_outline,
            fill = "#d4d4d4", color = "white", linewidth = 0.2) +
    geom_sf(data = nwab_highlight,
            fill = "#C8102E", color = "#900000", linewidth = 0.5, alpha = 0.85) +
    theme_void() +
    theme(
      panel.background = element_rect(fill = "#e8f4f8", color = "#aaaaaa", linewidth = 0.5),
      plot.margin = margin(2, 2, 2, 2)
    )
  inset
}

# ── Main figure function ───────────────────────────────────────────────────────

#' Build a publication-ready Voronoi choropleth map of pediatric air ambulance
#' utilization by village for the Northwest Arctic Borough.
#'
#' @return A ggplot2 object (main map with inset).
fig1_choropleth_map <- function() {

  # ── Load data ───────────────────────────────────────────────────────────────
  facilities <- .load_maniilaq_facilities()
  nwab       <- .load_borough_boundary()
  ns_bor     <- .load_north_slope()
  util       <- .load_utilization()

  # Separate Kotzebue (hub) from village clinics
  is_kotzebue <- grepl("^Kotzebue$", facilities$village_name, ignore.case = TRUE)
  hub      <- facilities[is_kotzebue, ]
  villages <- facilities[!is_kotzebue, ]

  # ── Voronoi clip geometry ────────────────────────────────────────────────────
  # Use NW Arctic Borough + North Slope Borough so Point Hope (in NSB) gets a
  # proper zone rather than clipping to empty.
  if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
    clip_geom <- st_union(st_union(nwab), st_union(ns_bor))
  } else {
    clip_geom <- st_union(nwab)
  }
  clip_geom_single <- st_union(clip_geom)

  # ── Compute Voronoi ─────────────────────────────────────────────────────────
  # Include hub (Kotzebue) so its zone competes correctly; we'll color it separately
  all_pts <- rbind(hub, villages)
  zones   <- tryCatch(
    .compute_voronoi(all_pts, clip_geom_single),
    error = function(e) {
      message("Voronoi failed: ", e$message, " — falling back to point map")
      NULL
    }
  )

  # ── Join utilization rates ───────────────────────────────────────────────────
  if (!is.null(zones)) {
    zones <- zones |>
      left_join(util, by = "village_name")
  }

  # ── Colour scale setup ────────────────────────────────────────────────────────
  # Plasma palette, colorblind-safe. NA (Kotzebue hub + missing) shown in gray.
  rate_max <- if (!is.null(zones) && any(!is.na(zones$util_rate))) {
    max(zones$util_rate, na.rm = TRUE) * 1.05
  } else {
    100
  }

  # ── Map extent (EPSG:3338, meters) ──────────────────────────────────────────
  # Mirroring the Python map_bounds_manuscript(): derived from village extents
  fac_bbox  <- st_bbox(all_pts)
  ph_pts    <- all_pts[grepl("Point Hope", all_pts$village_name, ignore.case = TRUE), ]
  kob_pts   <- all_pts[grepl("^Kobuk$", all_pts$village_name, ignore.case = TRUE), ]
  buc_pts   <- all_pts[grepl("Buckland", all_pts$village_name, ignore.case = TRUE), ]

  if (nrow(ph_pts) > 0 && nrow(kob_pts) > 0 && nrow(buc_pts) > 0) {
    ph_bbox   <- st_bbox(ph_pts)
    kob_coord <- st_coordinates(kob_pts)[1, ]
    buc_coord <- st_coordinates(buc_pts)[1, ]
    non_kot_pts <- all_pts[!grepl("^Kotzebue$", all_pts$village_name, ignore.case = TRUE), ]
    non_kot_coords <- st_coordinates(non_kot_pts)
    xmin <- ph_bbox["xmin"] - 50000
    xmax <- kob_coord[1]    + 60000
    ymin <- buc_coord[2]    - 10000
    ymax <- max(non_kot_coords[, 2]) + 20000
  } else {
    xmin <- fac_bbox["xmin"] - 80000
    xmax <- fac_bbox["xmax"] + 80000
    ymin <- fac_bbox["ymin"] - 80000
    ymax <- fac_bbox["ymax"] + 80000
  }

  # ── Full Alaska boroughs for background ───────────────────────────────────
  all_ak_bor <- tryCatch(
    {
      b <- st_read(.BOROUGH_SHP, quiet = TRUE)
      b[b$STATE == "02", ] |> st_transform(crs = 3338)
    },
    error = function(e) NULL
  )

  # ── Build label data ─────────────────────────────────────────────────────────
  if (!is.null(zones)) {
    label_data <- zones |>
      st_drop_geometry() |>
      left_join(
        all_pts |>
          st_drop_geometry() |>
          bind_cols(as.data.frame(st_coordinates(all_pts))) |>
          rename(cx = X, cy = Y),
        by = "village_name"
      ) |>
      filter(!grepl("^Kotzebue$", village_name, ignore.case = TRUE))
  } else {
    label_data <- villages |>
      st_drop_geometry() |>
      bind_cols(as.data.frame(st_coordinates(villages))) |>
      rename(cx = X, cy = Y) |>
      left_join(util, by = "village_name")
  }

  # ── Village point markers ────────────────────────────────────────────────────
  village_pts <- villages |>
    bind_cols(as.data.frame(st_coordinates(villages))) |>
    rename(cx = X, cy = Y)

  hub_pt <- hub |>
    bind_cols(as.data.frame(st_coordinates(hub))) |>
    rename(cx = X, cy = Y)

  hub_coords <- st_coordinates(hub)
  hub_cx <- hub_coords[1, 1]
  hub_cy <- hub_coords[1, 2]

  # ── Assemble main map ────────────────────────────────────────────────────────
  p <- ggplot()

  # Background: all Alaska boroughs
  if (!is.null(all_ak_bor)) {
    p <- p +
      geom_sf(data = all_ak_bor,
              fill = "#f0f0f0", color = "#bbbbbb", linewidth = 0.2)
  }

  # Voronoi zones colored by utilization (or fallback to borough fill)
  if (!is.null(zones)) {
    # Clip zones to just the NW Arctic Borough for display
    zones_nwab <- tryCatch(
      st_intersection(zones, st_union(nwab)),
      error = function(e) zones
    )
    p <- p +
      geom_sf(
        data = zones_nwab,
        aes(fill = util_rate),
        color = "white", linewidth = 0.5, alpha = 0.9
      )
  } else {
    p <- p +
      geom_sf(data = nwab, fill = "#e8e8e8", color = "#555555", linewidth = 0.8)
  }

  # NW Arctic Borough outline (over zones)
  p <- p +
    geom_sf(data = nwab, fill = NA, color = "#333333", linewidth = 0.8)

  # Village clinic points
  p <- p +
    geom_sf(data = villages,
            shape = 21, size = 2.5,
            fill = "white", color = "#1a1a1a", stroke = 1.0)

  # Kotzebue / MHC — hospital icon: dark grey filled square with white "H"
  p <- p +
    annotate("point",
             x = hub_cx, y = hub_cy,
             shape = 22, size = 7,
             fill = "#606060", color = "#222222", stroke = 1.2) +
    annotate("text",
             x = hub_cx, y = hub_cy,
             label = "H", color = "white", size = 2.8, fontface = "bold")

  # Kotzebue city label + MHC sub-label
  kotz_label <- data.frame(
    cx = hub_cx, cy = hub_cy,
    label = "Kotzebue\nManiilaq Health Center"
  )
  p <- p +
    geom_label_repel(
      data        = kotz_label,
      aes(x = cx, y = cy, label = label),
      size          = 2.8,
      fontface      = "bold",
      box.padding   = 0.5,
      point.padding = 0.4,
      label.padding = 0.25,
      label.size    = 0.3,
      fill          = "white",
      color         = "#111111",
      alpha         = 0.95,
      seed          = 42,
      min.segment.length = 0,
      segment.color = "#444444",
      segment.size  = 0.4,
      nudge_x       = 80000,
      nudge_y       = 0
    )

  # ── Color scale ───────────────────────────────────────────────────────────
  p <- p +
    scale_fill_viridis_c(
      option  = "plasma",
      name    = "Journeys per\n1,000 residents",
      limits  = c(0, rate_max),
      na.value = "#787878",
      guide   = guide_colorbar(
        barwidth  = 0.8,
        barheight = 8,
        title.position = "top",
        title.hjust    = 0.5
      )
    )

  # ── Village name labels (ggrepel for non-overlap) ────────────────────────
  p <- p +
    geom_label_repel(
      data = label_data,
      aes(x = cx, y = cy, label = village_name),
      size          = 2.8,
      fontface      = "plain",
      box.padding   = 0.4,
      point.padding = 0.3,
      label.padding = 0.2,
      label.size    = 0.25,
      fill          = "white",
      color         = "#222222",
      alpha         = 0.92,
      max.overlaps  = 30,
      seed          = 42,
      min.segment.length = 0,
      segment.color = "#666666",
      segment.size  = 0.35
    )

  # ── North arrow & scale bar ───────────────────────────────────────────────
  p <- p +
    annotation_north_arrow(
      location = "tr",
      which_north = "true",
      height = unit(1.0, "cm"),
      width  = unit(0.7, "cm"),
      style  = north_arrow_fancy_orienteering(
        fill      = c("white", "#333333"),
        line_col  = "#333333",
        text_col  = "#333333",
        text_size = 8
      )
    ) +
    annotation_scale(
      location   = "br",
      width_hint = 0.18,
      text_cex   = 0.7,
      line_col   = "#333333",
      text_col   = "#333333",
      bar_cols   = c("#333333", "white")
    )

  # ── Coordinates, theme, and viewport ─────────────────────────────────────
  p <- p +
    coord_sf(
      crs   = 3338,
      xlim  = c(xmin, xmax),
      ylim  = c(ymin, ymax),
      expand = FALSE
    ) +
    theme_void() +
    theme(
      legend.position   = c(0.97, 0.55),
      legend.justification = c(1, 0.5),
      legend.background = element_rect(fill = "white", color = NA),
      legend.title      = element_text(size = 8, face = "bold"),
      legend.text       = element_text(size = 7),
      plot.margin       = margin(4, 4, 4, 4),
      plot.background   = element_rect(fill = "white", color = NA)
    )

  # ── Alaska context inset ─────────────────────────────────────────────────
  inset <- tryCatch(
    .make_alaska_inset(nwab),
    error = function(e) NULL
  )

  if (!is.null(inset)) {
    # Combine main map with inset using patchwork inset_element
    final <- p +
      inset_element(
        inset,
        left   = 0.0,
        bottom = 0.0,
        right  = 0.24,
        top    = 0.26
      )
  } else {
    final <- p
  }

  final
}

# ── Save helper ───────────────────────────────────────────────────────────────

#' Save Figure 1 choropleth map to outputs/figures/
#'
#' @param width  Width in inches (default 8.5)
#' @param height Height in inches (default 6.5)
#' @param dpi    Resolution (default 300)
save_fig1_choropleth <- function(width = 8.5, height = 6.5, dpi = 300) {
  out_dir <- here("outputs", "figures")
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  out_path <- file.path(out_dir, "fig_voronoi_service_districts.png")
  p <- fig1_choropleth_map()
  ggsave(
    filename = out_path,
    plot     = p,
    width    = width,
    height   = height,
    dpi      = dpi,
    bg       = "white"
  )
  message("Saved: ", out_path)
}

# ── Figure 2: Sankey / alluvial transport route diagram ─────────────────────

library(ggalluvial)
library(readr)

.load_journeys_all_fig <- function() {
  readr::read_csv(here::here("outputs", "data", "journeys_all.csv"),
                  show_col_types = FALSE)
}

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
  message("Saved: ", out_path)
}
