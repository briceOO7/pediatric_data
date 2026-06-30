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

# Clip each Voronoi cell to the borough containing its village (matches Python
# medevac_map_fig1.py: Point Hope zone stays in NSB only; NWAB villages stay in NWAB).
.clip_voronoi_to_home_borough <- function(zones, pts_sf, nwab, ns_bor) {
  nwab_u <- st_union(nwab)
  ns_u   <- if (!is.null(ns_bor) && nrow(ns_bor) > 0) st_union(ns_bor) else NULL

  new_geoms <- vector("list", nrow(zones))
  for (i in seq_len(nrow(zones))) {
    vname <- zones$village_name[i]
    pt    <- pts_sf[pts_sf$village_name == vname, ]
    home  <- nwab_u
    if (!is.null(ns_u) && nrow(pt) > 0) {
      if (st_intersects(st_geometry(pt)[1], ns_u, sparse = FALSE)[1, 1]) {
        home <- ns_u
      }
    }
    g <- st_intersection(st_geometry(zones)[i], home)
    # st_intersection may return sfc; keep a single sfg for each row
    if (inherits(g, "sfc")) {
      g <- g[[1]]
    }
    if (st_is_empty(g)) {
      g <- st_polygon()
    }
    new_geoms[[i]] <- g
  }
  st_geometry(zones) <- st_sfc(new_geoms, crs = st_crs(zones))
  zones
}

# Label point inside the visible map extent (borough centroids are often off-frame).
.borough_label_in_view <- function(bor_sf, xmin, xmax, ymin, ymax) {
  view <- st_as_sfc(st_polygon(list(matrix(c(
    xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax, xmin, ymin
  ), ncol = 2, byrow = TRUE))), crs = st_crs(bor_sf))
  inter <- st_intersection(st_union(bor_sf), view)
  if (st_is_empty(inter)) return(c(NA_real_, NA_real_))
  parts <- tryCatch(st_cast(inter, "POLYGON"), error = function(e) inter)
  if (inherits(parts, "sf") && nrow(parts) > 0 && "POLYGON" %in% st_geometry_type(parts)) {
    best <- parts[which.max(st_area(parts)), ]
    pt   <- st_point_on_surface(best)
  } else {
    pt <- st_point_on_surface(inter)
  }
  coords <- st_coordinates(pt)
  c(coords[1, "X"], coords[1, "Y"])
}

# Borough names straddling the shared border; falls back to in-view centroids.
.borough_border_labels <- function(nwab, ns_bor, xmin, xmax, ymin, ymax) {
  nwab_u <- st_union(nwab)
  ns_u   <- st_union(ns_bor)

  mx <- my <- NA_real_
  border <- tryCatch(
    st_intersection(st_boundary(nwab_u), st_boundary(ns_u)),
    error = function(e) NULL
  )
  if (!is.null(border) && !st_is_empty(border)) {
    lines <- tryCatch(st_cast(border, "LINESTRING"), error = function(e) NULL)
    if (!is.null(lines) && nrow(lines) > 0) {
      longest <- lines[which.max(st_length(lines)), ]
      mid     <- st_line_sample(longest, sample = 0.5)
      if (!st_is_empty(mid)) {
        mc <- st_coordinates(mid)
        mx <- mc[1, "X"]
        my <- mc[1, "Y"]
      }
    }
  }

  if (!is.na(mx)) {
    return(data.frame(
      x     = c(mx, mx),
      y     = c(my - 45000, my + 45000),
      label = c("Northwest Arctic Borough", "North Slope Borough"),
      stringsAsFactors = FALSE
    ))
  }

  nw_pt <- .borough_label_in_view(nwab, xmin, xmax, ymin, ymax)
  ns_pt <- .borough_label_in_view(ns_bor, xmin, xmax, ymin, ymax)
  data.frame(
    x     = c(nw_pt[1], ns_pt[1]),
    y     = c(nw_pt[2], ns_pt[2]),
    label = c("Northwest Arctic Borough", "North Slope Borough"),
    stringsAsFactors = FALSE
  )
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
    # Kotzebue hub: grey zone, not utilization-colored
    zones$util_rate[grepl("^Kotzebue$", zones$village_name, ignore.case = TRUE)] <- NA_real_
    # Clip each zone to its village's home borough (prevents NWAB colors in NSB)
    if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
      zones <- .clip_voronoi_to_home_borough(zones, all_pts, nwab, ns_bor)
    }
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

  # ── Borough boundary labels (computed after map extent is set) ───────────────
  borough_labels <- NULL
  if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
    borough_labels <- .borough_border_labels(nwab, ns_bor, xmin, xmax, ymin, ymax)
  }

  # Villages whose clinic falls in North Slope Borough (Point Hope only)
  ns_villages <- character(0)
  if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
    ns_u <- st_union(ns_bor)
    ns_villages <- all_pts$village_name[
      st_intersects(all_pts, ns_u, sparse = FALSE)[, 1]
    ]
  }

  zones_nwab <- zones_nsb <- NULL
  if (!is.null(zones)) {
    zones_nwab <- zones[!zones$village_name %in% ns_villages, ]
    zones_nsb  <- zones[zones$village_name %in% ns_villages, ]
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

  # North Slope Borough — light grey fill (everything except Point Hope's zone)
  if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
    p <- p +
      geom_sf(data = ns_bor,
              fill = "#E2E2E2", color = "#888888", linewidth = 0.5)
  }

  # Colored Voronoi zones: NWAB villages only (home-borough clipped)
  if (!is.null(zones_nwab) && nrow(zones_nwab) > 0) {
    p <- p +
      geom_sf(
        data = zones_nwab,
        aes(fill = util_rate),
        color = "white", linewidth = 0.5, alpha = 0.9
      )
  }

  # Point Hope service district only in North Slope (over grey NSB background)
  if (!is.null(zones_nsb) && nrow(zones_nsb) > 0) {
    p <- p +
      geom_sf(
        data = zones_nsb,
        aes(fill = util_rate),
        color = "white", linewidth = 0.5, alpha = 0.9
      )
  }

  if (is.null(zones)) {
    p <- p +
      geom_sf(data = nwab, fill = "#e8e8e8", color = "#555555", linewidth = 0.8)
  }

  # Borough outlines on top of zones
  p <- p +
    geom_sf(data = nwab, fill = NA, color = "#333333", linewidth = 0.8)

  if (!is.null(ns_bor) && nrow(ns_bor) > 0) {
    p <- p +
      geom_sf(data = ns_bor, fill = NA, color = "#333333", linewidth = 0.8)
  }

  # Borough name labels
  if (!is.null(borough_labels) && nrow(borough_labels) > 0) {
    p <- p +
      annotate("text",
               x        = borough_labels$x,
               y        = borough_labels$y,
               label    = borough_labels$label,
               size     = 3.2,
               fontface = "italic",
               color    = "#333333",
               hjust    = 0.5,
               vjust    = 0.5)
  }

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
      nudge_x       = -80000,
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

# ── Figure 2: Village-level network flow diagram (matches Python fig4) ────────

library(readr)

# Null-coalesce helper (mirrors Python `or` for empty strings)
`%||%` <- function(x, y) {
  if (length(x) == 0L) return(y)
  if (is.na(x) || (is.character(x) && !nzchar(trimws(x)))) y else x
}

.VILLAGE_PALETTE <- c(
  "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
  "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf", "#aec7e8"
)

.OUTSIDE_FACILITY_NAMES <- list(
  c("providence",           "Providence"),
  c("alaska regional",      "Alaska Regional"),
  c("alaska reg",           "Alaska Regional"),
  c("arh",                  "Alaska Regional"),
  c("university of washington", "UW Med Ctr"),
  c("uw medical",           "UW Med Ctr"),
  c("uwmc",                 "UW Med Ctr"),
  c("harborview",           "Harborview"),
  c("seattle children",     "Seattle Children's"),
  c("seattle childrens",    "Seattle Children's"),
  c("ucsf",                 "UCSF"),
  c("mayo",                 "Mayo Clinic"),
  c("stanford",             "Stanford"),
  c("nationwide children",  "Nationwide Children's"),
  c("outside",              "Outside Facility")
)

.village_origin_mode <- function() {
  env_mode <- Sys.getenv("MEDEVAC_VILLAGE_ORIGINS", "")
  if (env_mode %in% c("infer", "codebook")) return(env_mode)
  syn <- tolower(trimws(Sys.getenv("MEDEVAC_SYNTHETIC", "")))
  if (syn %in% c("1", "true", "yes", "y", "on")) "codebook" else "infer"
}

.maniilaq_village_names <- function() {
  cb_path <- here("docs", "village_name_codebook.csv")
  if (!file.exists(cb_path)) return(character(0))
  unique(trimws(read.csv(cb_path, stringsAsFactors = FALSE)$community_name))
}

.is_study_facility_origin <- function(place) {
  if (is.na(place)) return(TRUE)
  t <- trimws(as.character(place))
  if (!nzchar(t)) return(TRUE)
  u <- toupper(gsub("_", "", t))
  if (startsWith(u, "CAH") || startsWith(u, "HUB") || grepl("OUTSIDEHOSPITAL", u, fixed = TRUE)) {
    return(TRUE)
  }
  tl <- tolower(t)
  if (grepl("maniilaq", tl, fixed = TRUE) && grepl("health", tl, fixed = TRUE)) return(TRUE)
  if (tl == "mhc") return(TRUE)
  FALSE
}

.is_village_medevac_origin <- function(place) {
  s <- trimws(as.character(place %||% ""))
  if (!nzchar(s)) return(FALSE)
  mode <- .village_origin_mode()
  if (mode == "infer") return(!.is_study_facility_origin(s))
  if (startsWith(s, "Village_")) return(TRUE)
  s %in% .maniilaq_village_names()
}

.is_anmc <- function(v) {
  t <- trimws(as.character(v %||% ""))
  tl <- tolower(t)
  startsWith(t, "Hub") ||
    toupper(t) %in% c("HUB_01", "ANMC") ||
    (grepl("alaska native", tl, fixed = TRUE) && grepl("medical", tl, fixed = TRUE))
}

.is_mhc_cah_destination <- function(to_raw) {
  b <- trimws(as.character(to_raw %||% ""))
  bl <- tolower(b)
  b == "CAH_01" ||
    startsWith(b, "CAH") ||
    toupper(b) == "MHC" ||
    grepl(" mhc", paste0(" ", bl), fixed = TRUE) ||
    grepl("maniilaq health center", bl, fixed = TRUE) ||
    (grepl("maniilaq", bl, fixed = TRUE) &&
       grepl("health", bl, fixed = TRUE) &&
       grepl("center", bl, fixed = TRUE))
}

.outside_facility_label <- function(raw) {
  t <- trimws(as.character(raw %||% ""))
  tl <- tolower(t)
  for (pair in .OUTSIDE_FACILITY_NAMES) {
    if (grepl(pair[[1]], tl, fixed = TRUE)) return(pair[[2]])
  }
  t
}

.dest_label <- function(v) {
  if (is.na(v) || !nzchar(trimws(as.character(v)))) return("")
  if (.is_mhc_cah_destination(v)) return("MHC")
  if (.is_anmc(v)) return("ANMC")
  .outside_facility_label(v)
}

.resolve_village_origin <- function(r) {
  for (field in c("village_name", "medevac1_from", "facility_1_name")) {
    if (!field %in% names(r)) next
    s <- trimws(as.character(r[[field]] %||% ""))
    if (nzchar(s) && .is_village_medevac_origin(s)) return(s)
  }
  ""
}

.load_journeys_all_fig <- function() {
  readr::read_csv(here("outputs", "data", "journeys_all.csv"),
                  show_col_types = FALSE) |>
    distinct(journey_id, .keep_all = TRUE)
}

#' Build aggregated village-level flow counts (mirrors Python fig4 logic).
.build_sankey_data <- function() {
  j <- .load_journeys_all_fig()
  if (nrow(j) == 0) {
    return(list(
      prim_df = data.frame(village = character(0), dest = character(0), n = integer(0),
                           stringsAsFactors = FALSE),
      sec_counts = list(), village_total = list(),
      villages = character(0), all_right_dests = character(0)
    ))
  }

  flow_rows <- vector("list", nrow(j))
  for (i in seq_len(nrow(j))) {
    r <- j[i, ]
    vname <- .resolve_village_origin(r)
    if (!nzchar(vname)) next

    legs <- c(
      .dest_label(r$medevac1_to),
      .dest_label(r$medevac2_to),
      .dest_label(r$medevac3_to)
    )
    legs <- legs[nzchar(legs)]

    prim <- if (length(legs) >= 1L) legs[[1L]] else ""
    sec_from_mhc <- if (length(legs) >= 1L && legs[[1L]] == "MHC" && length(legs) >= 2L) {
      legs[-1L]
    } else {
      character(0)
    }

    flow_rows[[i]] <- list(village = vname, primary = prim, sec_from_mhc = sec_from_mhc)
  }
  flow_rows <- Filter(Negate(is.null), flow_rows)

  prim_rows <- list()
  sec_counts <- list()
  village_total <- list()

  for (fr in flow_rows) {
    v <- fr$village
    prim <- fr$primary
    if (nzchar(prim)) {
      prim_rows[[length(prim_rows) + 1L]] <- data.frame(
        village = v, dest = prim, stringsAsFactors = FALSE
      )
      village_total[[v]] <- (village_total[[v]] %||% 0L) + 1L
    }
    for (s in fr$sec_from_mhc) {
      sec_counts[[s]] <- (sec_counts[[s]] %||% 0L) + 1L
    }
  }

  prim_df <- if (length(prim_rows) > 0L) {
    prim_rows <- do.call(rbind, prim_rows)
    prim_rows |>
      group_by(village, dest) |>
      summarise(n = n(), .groups = "drop")
  } else {
    data.frame(village = character(0), dest = character(0), n = integer(0),
               stringsAsFactors = FALSE)
  }

  all_dests <- unique(c(prim_df$dest, names(sec_counts)))
  all_right_dests <- sort(
    setdiff(all_dests, "MHC"),
    decreasing = FALSE
  )
  all_right_dests <- all_right_dests[order(
    ifelse(all_right_dests == "ANMC", 0L, 1L),
    all_right_dests
  )]

  villages <- names(village_total)
  villages <- villages[order(-vapply(villages, function(v) village_total[[v]], integer(1)))]

  list(
    prim_df = prim_df,
    sec_counts = sec_counts,
    village_total = village_total,
    villages = villages,
    all_right_dests = all_right_dests
  )
}

.bezier_curve_df <- function(x0, y0, x1, y1, bend = 0, n = 60, ...) {
  cx <- (x0 + x1) / 2 + bend
  t <- seq(0, 1, length.out = n)
  data.frame(
    x = (1 - t)^3 * x0 + 3 * (1 - t)^2 * t * cx + 3 * (1 - t) * t^2 * cx + t^3 * x1,
    y = (1 - t)^3 * y0 + 3 * (1 - t)^2 * t * y0 + 3 * (1 - t) * t^2 * y1 + t^3 * y1,
    ...
  )
}

.circle_df <- function(xc, yc, r, n = 72L) {
  t <- seq(0, 2 * pi, length.out = n + 1L)
  data.frame(x = xc + r * cos(t), y = yc + r * sin(t))
}

#' Village-level network flow diagram of pediatric medevac routes.
#'
#' Matches Python `plot_fig4_sankey_transport_routes()` layout:
#' village clinics (left) → MHC (center) → receiving facilities (right).
#'
#' @return A ggplot2 object
fig2_sankey_routes <- function() {
  # Layout constants (normalized 0–1 coordinates)
  X_V     <- 0.13
  X_MHC   <- 0.48
  X_R     <- 0.73
  X_R_LBL <- 0.76
  MHC_R   <- 0.055
  LW_MIN  <- 0.6
  LW_MAX  <- 9.0

  empty_plot <- function(msg) {
    ggplot() +
      annotate("text", x = 0.5, y = 0.5, label = msg, size = 4.5) +
      coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE) +
      theme_void()
  }

  dat <- .build_sankey_data()
  villages <- dat$villages
  if (length(villages) == 0) return(empty_plot("No village-origin legs found."))

  prim_df       <- dat$prim_df
  sec_counts    <- dat$sec_counts
  village_total <- dat$village_total
  all_right_dests <- dat$all_right_dests

  vcolor <- setNames(
    .VILLAGE_PALETTE[seq_along(villages) %% length(.VILLAGE_PALETTE) + 1L],
    villages
  )
  right_colors <- c(ANMC = "#ED7D31", MHC = "#70AD47")
  outside_palette <- c("#4472C4", "#9467BD", "#8C564B", "#E377C2",
                       "#17BECF", "#BCBD22", "#7F7F7F")
  outside_dests <- setdiff(all_right_dests, names(right_colors))
  for (i in seq_along(outside_dests)) {
    right_colors[outside_dests[[i]]] <- outside_palette[[((i - 1L) %% length(outside_palette)) + 1L]]
  }

  nv <- length(villages)
  yv_top <- 0.93; yv_bot <- 0.07
  v_ys <- setNames(
    yv_top - seq(0, nv - 1L) * (yv_top - yv_bot) / max(nv - 1L, 1L),
    villages
  )

  nr <- length(all_right_dests)
  yr_top <- 0.88; yr_bot <- 0.20
  r_ys <- if (nr > 0L) {
    setNames(
      yr_top - seq(0, nr - 1L) * (yr_top - yr_bot) / max(nr - 1L, 1L),
      all_right_dests
    )
  } else {
    numeric(0)
  }
  Y_MHC <- mean(c(yr_top, yr_bot))

  max_vn <- max(vapply(villages, function(v) village_total[[v]], integer(1)))
  V_R_MAX <- 0.020; V_R_MIN <- 0.008
  vr <- function(n) V_R_MIN + (V_R_MAX - V_R_MIN) * (n / max_vn)^0.5

  n_right <- list()
  if (nrow(prim_df) > 0L) {
    for (i in seq_len(nrow(prim_df))) {
      d <- prim_df$dest[[i]]; n <- prim_df$n[[i]]
      if (d != "MHC") n_right[[d]] <- (n_right[[d]] %||% 0L) + n
    }
  }
  for (d in names(sec_counts)) {
    if (d != "MHC") n_right[[d]] <- (n_right[[d]] %||% 0L) + sec_counts[[d]]
  }
  all_right_max <- if (length(n_right) > 0L) max(unlist(n_right)) else 1L
  R_R_MAX <- 0.032; R_R_MIN <- 0.014
  rr <- function(n) R_R_MIN + (R_R_MAX - R_R_MIN) * (n / all_right_max)^0.5

  max_flow <- if (nrow(prim_df) > 0L) max(prim_df$n) else 1L
  lw <- function(n) if (n > 0L) LW_MIN + (LW_MAX - LW_MIN) * (n / max_flow)^0.5 else 0

  # Primary flow curves (thick first for layering)
  prim_items <- if (nrow(prim_df) > 0L) {
    lapply(seq_len(nrow(prim_df)), function(i) {
      list(v = prim_df$village[[i]], dest = prim_df$dest[[i]], n = prim_df$n[[i]])
    })
  } else {
    list()
  }
  prim_items <- prim_items[order(-vapply(prim_items, `[[`, numeric(1), "n"))]

  flow_dfs <- list()
  fi <- 0L
  for (item in prim_items) {
    v <- item$v; dest <- item$dest; n <- item$n
    vy <- v_ys[[v]]; col <- vcolor[[v]]
    vr_v <- vr(village_total[[v]])
    if (dest == "MHC") {
      fi <- fi + 1L
      flow_dfs[[fi]] <- .bezier_curve_df(
        X_V + vr_v, vy, X_MHC - MHC_R, Y_MHC,
        group = fi, color = col, lw = lw(n), alpha = 0.72
      )
    } else if (dest %in% names(r_ys)) {
      ry <- r_ys[[dest]]
      rr_d <- rr(n_right[[dest]] %||% 1L)
      fi <- fi + 1L
      flow_dfs[[fi]] <- .bezier_curve_df(
        X_V + vr_v, vy, X_R - rr_d, ry,
        bend = 0.04, group = fi, color = col, lw = lw(n), alpha = 0.72
      )
    }
  }

  # Secondary MHC → facility flows (grey)
  sec_labels <- list()
  for (dest in names(sec_counts)) {
    n <- sec_counts[[dest]]
    if (dest == "MHC" || !(dest %in% names(r_ys))) next
    ry <- r_ys[[dest]]
    rr_d <- rr(n_right[[dest]] %||% 1L)
    fi <- fi + 1L
    flow_dfs[[fi]] <- .bezier_curve_df(
      X_MHC + MHC_R, Y_MHC, X_R - rr_d, ry,
      group = fi, color = "#555555", lw = lw(n), alpha = 0.55
    )
    sec_labels[[length(sec_labels) + 1L]] <- data.frame(
      x = (X_MHC + MHC_R + X_R - rr_d) / 2,
      y = (Y_MHC + ry) / 2 + 0.03,
      label = paste0("2\u00b0 n=", n),
      stringsAsFactors = FALSE
    )
  }
  flows_all <- if (length(flow_dfs) > 0L) do.call(rbind, flow_dfs) else NULL
  sec_label_df <- if (length(sec_labels) > 0L) do.call(rbind, sec_labels) else NULL

  # Node circles
  village_circles <- do.call(rbind, lapply(villages, function(v) {
    n_v <- village_total[[v]]
    r <- vr(n_v)
    .circle_df(X_V, v_ys[[v]], r) |>
      mutate(node = v, fill = vcolor[[v]], r = r, n = n_v)
  }))

  mhc_prim <- sum(vapply(prim_items, function(it) if (it$dest == "MHC") it$n else 0L, integer(1)))
  mhc_circle <- .circle_df(X_MHC, Y_MHC, MHC_R) |>
    mutate(node = "MHC", fill = "#70AD47", r = MHC_R, n = mhc_prim)

  right_circles <- if (nr > 0L) {
    do.call(rbind, lapply(all_right_dests, function(d) {
      .circle_df(X_R, r_ys[[d]], rr(n_right[[d]] %||% 1L)) |>
        mutate(
          node = d, fill = right_colors[[d]], r = rr(n_right[[d]] %||% 1L),
          n = n_right[[d]] %||% 0L
        )
    }))
  } else {
    NULL
  }

  # Column headers
  headers <- data.frame(
    x = c(X_V, X_MHC, (X_R + X_R_LBL + 0.10) / 2),
    y = 0.97,
    label = c("Village Clinics", "Maniilaq\nHealth Center", "Receiving Facilities"),
    stringsAsFactors = FALSE
  )

  village_labels <- data.frame(
    x = X_V - vapply(villages, function(v) vr(village_total[[v]]), numeric(1)) - 0.010,
    y = unname(v_ys[villages]),
    label = vapply(villages, function(v) paste0(v, "  ", village_total[[v]]), character(1)),
    stringsAsFactors = FALSE
  )

  right_labels <- if (nr > 0L) {
    data.frame(
      x = X_R_LBL,
      y = unname(r_ys[all_right_dests]),
      label = vapply(all_right_dests, function(d) {
        paste0(d, "\nn = ", n_right[[d]] %||% 0L)
      }, character(1)),
      color = unname(right_colors[all_right_dests]),
      stringsAsFactors = FALSE
    )
  } else {
    NULL
  }

  total_journeys <- sum(unlist(village_total))

  # Legend (lower center)
  legend_ns <- sort(unique(c(1L, max_flow %/% 2L, max_flow)))
  legend_ns <- legend_ns[legend_ns > 0L]
  legend_x0 <- 0.28
  legend_dx <- 0.12
  legend_df <- data.frame(
    x = legend_x0 + (seq_along(legend_ns) - 1L) * legend_dx,
    y = 0.04,
    xend = legend_x0 + (seq_along(legend_ns) - 1L) * legend_dx + 0.05,
    yend = 0.04,
    lw = vapply(legend_ns, lw, numeric(1)),
    label = paste0("n = ", legend_ns),
    stringsAsFactors = FALSE
  )
  sec_legend_x <- legend_x0 + length(legend_ns) * legend_dx + 0.02

  p <- ggplot() +
    coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE, clip = "off") +
    theme_void(base_size = 11) +
    theme(
      plot.title = element_text(size = 12, face = "plain", hjust = 0.5,
                                margin = margin(t = 4, b = 8)),
      plot.margin = margin(8, 12, 8, 12)
    ) +
    labs(
      title = paste0(
        "Figure 4. Pediatric Medevac Routes by Village  (n = ",
        total_journeys, " journeys)"
      )
    )

  if (!is.null(flows_all)) {
    p <- p + geom_path(
      data = flows_all,
      aes(x = x, y = y, group = group, linewidth = lw, color = I(color), alpha = I(alpha)),
      lineend = "round"
    )
  }

  p <- p +
    geom_polygon(data = village_circles, aes(x = x, y = y, group = node),
                 fill = village_circles$fill, color = "white", linewidth = 0.4) +
    geom_polygon(data = mhc_circle, aes(x = x, y = y), fill = "#70AD47",
                 color = "white", linewidth = 0.6)

  if (!is.null(right_circles)) {
    p <- p + geom_polygon(
      data = right_circles, aes(x = x, y = y, group = node),
      fill = right_circles$fill, color = "white", linewidth = 0.6
    )
  }

  p <- p +
    geom_text(data = headers, aes(x = x, y = y, label = label),
              fontface = "bold", size = 3.3, color = "#333333", vjust = 1) +
    geom_text(data = village_labels, aes(x = x, y = y, label = label),
              hjust = 1, size = 3.0, color = "#333333") +
    annotate("text", x = X_MHC, y = Y_MHC,
             label = paste0("Maniilaq\nHealth Center\nn = ", mhc_prim),
             size = 3.0, fontface = "bold", color = "white", lineheight = 0.9)

  if (!is.null(right_labels)) {
    p <- p + geom_text(
      data = right_labels,
      aes(x = x, y = y, label = label, color = I(color)),
      hjust = 0, size = 3.0, fontface = "bold", lineheight = 0.9
    )
  }

  if (!is.null(sec_label_df)) {
    p <- p + geom_label(
      data = sec_label_df, aes(x = x, y = y, label = label),
      size = 2.3, color = "#555555", fill = alpha("white", 0.85),
      linewidth = 0.25, label.padding = unit(0.12, "lines")
    )
  }

  # Legend lines and labels
  p <- p +
    geom_segment(
      data = legend_df,
      aes(x = x, xend = xend, y = y, yend = yend, linewidth = lw),
      color = "#595959", lineend = "round"
    ) +
    geom_text(
      data = legend_df, aes(x = (x + xend) / 2, y = y - 0.025, label = label),
      size = 2.3, color = "#333333"
    ) +
    geom_segment(
      aes(x = sec_legend_x, xend = sec_legend_x + 0.05, y = 0.04, yend = 0.04),
      color = "#555555", linewidth = 0.8, linetype = "dashed", lineend = "round"
    ) +
    annotate("text", x = sec_legend_x + 0.025, y = 0.015,
             label = "MHC \u2192 facility\n(secondary)",
             size = 2.3, color = "#333333", lineheight = 0.85) +
    annotate("text",
             x = mean(c(legend_x0, sec_legend_x + 0.08)), y = 0.075,
             label = "Transfer volume", fontface = "bold", size = 2.6, color = "#333333") +
    scale_linewidth_identity()

  p
}

#' Save Figure 2 network flow diagram to outputs/figures/fig2_sankey_routes.png
#'
#' @param width  inches (default 15, matches Python figsize)
#' @param height inches (default 9)
#' @param dpi    resolution (default 300)
save_fig2_sankey <- function(width = 15, height = 9, dpi = 300) {
  out_dir <- here("outputs", "figures")
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)
  out_path <- file.path(out_dir, "fig2_sankey_routes.png")
  p <- fig2_sankey_routes()
  ggsave(out_path, plot = p, width = width, height = height, dpi = dpi,
         bg = "white")
  message("Saved: ", out_path)
}
