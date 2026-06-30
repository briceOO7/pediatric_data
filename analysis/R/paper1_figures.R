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
  view <- st_sfc(
    st_polygon(list(matrix(c(
      xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax, xmin, ymin
    ), ncol = 2, byrow = TRUE))),
    crs = st_crs(bor_sf)
  )
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

# Borough names above/below the NWAB–NSB boundary at horizontal map center.
.borough_border_labels <- function(nwab, ns_bor, xmin, xmax, ymin, ymax) {
  mid_x <- (xmin + xmax) / 2
  map_w <- xmax - xmin
  map_h <- ymax - ymin
  label_x <- mid_x + map_w * 0.075
  y_gap   <- max(26000, map_h * 0.028)
  y_nudge <- max(8000, map_h * 0.008)

  nwab_u <- st_union(nwab)
  ns_u   <- st_union(ns_bor)
  crs    <- st_crs(nwab)

  view <- st_sfc(
    st_polygon(list(matrix(c(
      xmin, ymin, xmax, ymin, xmax, ymax, xmin, ymax, xmin, ymin
    ), ncol = 2, byrow = TRUE))),
    crs = crs
  )

  border <- tryCatch(
    st_intersection(st_boundary(nwab_u), st_boundary(ns_u)),
    error = function(e) NULL
  )
  if (is.null(border) || st_is_empty(border)) {
    return(.borough_border_labels_fallback(nwab, ns_bor, xmin, xmax, ymin, ymax))
  }

  border_view <- tryCatch(st_intersection(border, view), error = function(e) border)
  if (st_is_empty(border_view)) border_view <- border

  # Where the borough dividing line crosses the label column.
  vert <- st_sfc(
    st_linestring(matrix(c(label_x, ymin, label_x, ymax), ncol = 2, byrow = TRUE)),
    crs = crs
  )
  hit <- tryCatch(st_intersection(border_view, vert), error = function(e) NULL)

  border_y <- NA_real_
  if (!is.null(hit) && !st_is_empty(hit)) {
    pts <- tryCatch(st_cast(hit, "POINT"), error = function(e) NULL)
    if (!is.null(pts) && length(pts) > 0L) {
      coords <- st_coordinates(pts)
      border_y <- coords[which.max(coords[, "Y"]), "Y"]
    }
  }

  if (is.na(border_y)) {
    lines <- tryCatch(st_cast(border_view, "LINESTRING"), error = function(e) NULL)
    if (!is.null(lines) && length(lines) > 0L) {
      mid_pt <- st_nearest_points(
        st_sfc(st_point(c(label_x, (ymin + ymax) / 2)), crs = crs),
        lines[which.max(st_length(lines))]
      )[[2]]
      border_y <- st_coordinates(mid_pt)[1, "Y"]
    }
  }

  if (is.na(border_y)) {
    return(.borough_border_labels_fallback(nwab, ns_bor, xmin, xmax, ymin, ymax))
  }

  data.frame(
    x     = c(label_x, label_x),
    y     = c(border_y - y_gap - y_nudge - map_h * 0.05, border_y + y_gap + y_nudge + map_h * 0.02),
    label = c("Northwest Arctic Borough", "North Slope Borough"),
    vjust = c(0.5, 0.5),
    stringsAsFactors = FALSE
  )
}

# Fallback when shared-border geometry is unavailable.
.borough_border_labels_fallback <- function(nwab, ns_bor, xmin, xmax, ymin, ymax) {
  mid_x <- (xmin + xmax) / 2
  mid_y <- (ymin + ymax) / 2
  map_w <- xmax - xmin
  map_h <- ymax - ymin
  label_x <- mid_x + map_w * 0.075
  y_gap   <- max(26000, map_h * 0.028)
  y_nudge <- max(8000, map_h * 0.008)
  data.frame(
    x     = c(label_x, label_x),
    y     = c(mid_y - y_gap - y_nudge - map_h * 0.05, mid_y + y_gap + y_nudge + map_h * 0.02),
    label = c("Northwest Arctic Borough", "North Slope Borough"),
    vjust = c(0.5, 0.5),
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
    borough_labels <- tryCatch(
      .borough_border_labels(nwab, ns_bor, xmin, xmax, ymin, ymax),
      error = function(e) {
        message("Borough labels skipped: ", e$message)
        NULL
      }
    )
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

  # Borough name labels on the NWAB–NSB dividing line (plain text, no box)
  if (!is.null(borough_labels) && nrow(borough_labels) > 0) {
    p <- p +
      geom_text(
        data         = borough_labels,
        aes(x = x, y = y, label = label, vjust = vjust),
        size         = 4.5,
        fontface     = "bold.italic",
        color        = "#1a1a1a",
        alpha        = 0.5,
        lineheight   = 0.95,
        hjust        = 0.5
      )
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
             label = "H", color = "white", size = 3.4, fontface = "bold")

  # Kotzebue city label + MHC sub-label
  kotz_label <- data.frame(
    cx = hub_cx, cy = hub_cy,
    label = "Kotzebue\nManiilaq Health Center"
  )
  p <- p +
    geom_label_repel(
      data        = kotz_label,
      aes(x = cx, y = cy, label = label),
      size          = 3.6,
      fontface      = "bold",
      box.padding   = 0.55,
      point.padding = 0.45,
      label.padding = 0.32,
      label.size    = 0.3,
      fill          = "white",
      color         = "#111111",
      alpha         = 0.95,
      seed          = 42,
      min.segment.length = 0,
      segment.color = "#111111",
      segment.size  = 0.3,
      nudge_x       = -80000,
      nudge_y       = 0
    )

  # ── Color scale ───────────────────────────────────────────────────────────
  p <- p +
    scale_fill_viridis_c(
      option  = "plasma",
      name    = "Journeys per 1000\npediatric residents",
      limits  = c(0, rate_max),
      na.value = "#787878",
      guide   = guide_colorbar(
        barwidth  = 0.4,
        barheight = 4.2,
        title.position = "top",
        title.hjust    = 0.5,
        title.theme    = element_text(
          size = 9, face = "bold",
          margin = margin(t = 3, r = 4, b = 5, l = 4, unit = "pt")
        ),
        label.theme    = element_text(
          size = 8,
          margin = margin(t = 2, b = 2, r = 3, l = 2, unit = "pt")
        )
      )
    )

  # ── Village name labels (ggrepel for non-overlap) ────────────────────────
  p <- p +
    geom_label_repel(
      data = label_data,
      aes(x = cx, y = cy, label = village_name),
      size          = 3.6,
      fontface      = "plain",
      box.padding   = 0.45,
      point.padding = 0.35,
      label.padding = 0.28,
      label.size    = 0.25,
      fill          = "white",
      color         = "#222222",
      alpha         = 0.92,
      max.overlaps  = 30,
      seed          = 42,
      min.segment.length = 0,
      segment.color = "#222222",
      segment.size  = 0.25
    )

  # ── North arrow & scale bar ───────────────────────────────────────────────
  p <- p +
    annotation_north_arrow(
      location = "tr",
      which_north = "true",
      pad_x = unit(0.08, "npc"),
      pad_y = unit(0.04, "npc"),
      height = unit(0.9, "cm"),
      width  = unit(0.65, "cm"),
      style  = north_arrow_fancy_orienteering(
        fill      = c("white", "#333333"),
        line_col  = "#333333",
        text_col  = "#333333",
        text_size = 9
      )
    ) +
    annotation_scale(
      location   = "br",
      width_hint = 0.18,
      text_cex   = 0.85,
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
      legend.position         = c(0.975, 0.79),
      legend.justification    = c(1, 1),
      legend.background       = element_rect(fill = "white", color = NA),
      legend.box.background   = element_rect(fill = "white", color = NA),
      legend.margin           = margin(7, 8, 7, 8, unit = "pt"),
      legend.box.margin       = margin(1, 3, 1, 3, unit = "pt"),
      legend.spacing.y        = unit(4, "pt"),
      legend.title            = element_text(size = 9, face = "bold"),
      legend.text             = element_text(size = 8),
      plot.margin             = margin(6, 10, 6, 6, unit = "pt"),
      plot.background         = element_rect(fill = "white", color = NA)
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
  readr::read_csv(here("outputs", "data", "journeys_primary.csv"),
                  show_col_types = FALSE) |>
    distinct(journey_id, .keep_all = TRUE)
}

source(here("analysis", "R", "medevac_route_export.R"), local = TRUE)

.CODEX_SANKEY_DIR <- here("vendor", "pediatric_medevac_sankey")
.CODEX_SANKEY_SCRIPT <- file.path(.CODEX_SANKEY_DIR, "scripts", "medevac_sankey_manuscript.R")
.CODEX_SANKEY_FIG_DIR <- file.path(.CODEX_SANKEY_DIR, "figures")
.CODEX_SANKEY_PNG <- file.path(.CODEX_SANKEY_FIG_DIR, "figure4_medevac_routes_ggforce.png")

.fig2_codex_available <- function() {
  file.exists(.CODEX_SANKEY_SCRIPT)
}

.fig2_render_via_codex <- function(csv_path, out_png = NULL) {
  if (!.fig2_codex_available()) return(invisible(NULL))

  if (!dir.exists(.CODEX_SANKEY_FIG_DIR)) {
    dir.create(.CODEX_SANKEY_FIG_DIR, recursive = TRUE)
  }

  rel_csv <- tryCatch(
    normalizePath(csv_path, winslash = "/", mustWork = TRUE),
    error = function(e) csv_path
  )

  cmd <- sprintf(
    "cd %s && RENV_PROJECT=%s Rscript scripts/medevac_sankey_manuscript.R %s",
    shQuote(.CODEX_SANKEY_DIR),
    shQuote(here()),
    shQuote(rel_csv)
  )
  status <- system(cmd)
  if (!identical(status, 0L)) {
    warning("Codex Sankey script failed (exit ", status, "). Falling back to built-in Figure 2.")
    return(invisible(NULL))
  }

  if (!file.exists(.CODEX_SANKEY_PNG)) {
    warning("Codex Sankey script did not write ", .CODEX_SANKEY_PNG,
            ". Falling back to built-in Figure 2.")
    return(invisible(NULL))
  }

  if (!is.null(out_png)) {
    file.copy(.CODEX_SANKEY_PNG, out_png, overwrite = TRUE)
    message("Saved (Codex): ", out_png)
    return(invisible(out_png))
  }
  invisible(.CODEX_SANKEY_PNG)
}

.fig2_grob_from_png <- function(png_path) {
  img <- png::readPNG(png_path)
  grid::rasterGrob(img, interpolate = TRUE)
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

.fig2_flow_lwd <- function(n, max_flow) {
  if (n <= 0L) return(0)
  1.2 + (8.5 - 1.2) * (n / max(max_flow, 1L))^0.5
}

.fig2_draw_link <- function(x0, y0, x1, y1, color, n, max_flow,
                             curvature = 0, alpha = 0.72, lwd = NULL,
                             lty = 1) {
  if (is.null(lwd)) lwd <- .fig2_flow_lwd(n, max_flow)
  if (lwd <= 0) return(invisible(NULL))
  mx <- (x0 + x1) / 2
  my <- (y0 + y1) / 2 + curvature
  t  <- seq(0, 1, length.out = 80)
  bx <- (1 - t)^2 * x0 + 2 * (1 - t) * t * mx + t^2 * x1
  by <- (1 - t)^2 * y0 + 2 * (1 - t) * t * my + t^2 * y1
  grid::grid.lines(
    x = grid::unit(bx, "npc"), y = grid::unit(by, "npc"),
    gp = grid::gpar(
      col = grDevices::adjustcolor(color, alpha.f = alpha),
      lwd = lwd, lty = lty, lineend = "round"
    )
  )
}

.fig2_draw_ellipse <- function(x, y, w, h, fill,
                               label = NULL, label_gp = NULL) {
  t  <- seq(0, 2 * pi, length.out = 100)
  ex <- x + w * cos(t)
  ey <- y + h * sin(t)
  grid::grid.polygon(
    x = grid::unit(ex, "npc"), y = grid::unit(ey, "npc"),
    gp = grid::gpar(fill = fill, col = "white", lwd = 1)
  )
  if (!is.null(label)) {
    grid::grid.text(
      label, x = grid::unit(x, "npc"), y = grid::unit(y, "npc"),
      gp = label_gp
    )
  }
}

.fig2_draw_label_box <- function(text, x, y) {
  grid::grid.roundrect(
    x = grid::unit(x, "npc"), y = grid::unit(y, "npc"),
    width = grid::unit(0.065, "npc"), height = grid::unit(0.038, "npc"),
    r = grid::unit(0.003, "npc"),
    gp = grid::gpar(fill = "#ffffff", col = "#cccccc", lwd = 0.8)
  )
  grid::grid.text(
    text, x = grid::unit(x, "npc"), y = grid::unit(y, "npc"),
    gp = grid::gpar(fontsize = 7.5, col = "#555555")
  )
}

.build_fig2_layout <- function(dat) {
  villages      <- dat$villages
  prim_df       <- dat$prim_df
  sec_counts    <- dat$sec_counts
  village_total <- dat$village_total
  all_right_dests <- dat$all_right_dests

  if (length(villages) == 0L) return(NULL)

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
  y_top <- 0.88; y_bot <- 0.12
  ys <- seq(y_top, y_bot, length.out = nv)

  to_mhc <- vapply(villages, function(v) {
    if (nrow(prim_df) == 0L) return(0L)
    sum(prim_df$n[prim_df$village == v & prim_df$dest == "MHC"], na.rm = TRUE)
  }, integer(1))
  direct_anmc <- vapply(villages, function(v) {
    if (nrow(prim_df) == 0L) return(0L)
    sum(prim_df$n[prim_df$village == v & prim_df$dest == "ANMC"], na.rm = TRUE)
  }, integer(1))

  villages_df <- data.frame(
    village = villages,
    x = 0.10,
    y = ys,
    color = unname(vcolor[villages]),
    n = vapply(villages, function(v) village_total[[v]], integer(1)),
    to_mhc = to_mhc,
    direct_to_anmc = direct_anmc,
    stringsAsFactors = FALSE
  )

  mhc <- data.frame(
    x = 0.49,
    y = mean(c(y_top, y_bot)),
    color = "#70AD47",
    n = sum(to_mhc),
    stringsAsFactors = FALSE
  )

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

  nr <- length(all_right_dests)
  if (nr == 0L) {
    right_nodes <- data.frame(
      facility = character(0), x = numeric(0), y = numeric(0),
      color = character(0), n = integer(0), stringsAsFactors = FALSE
    )
  } else {
    ry <- if (nr == 1L) 0.50 else seq(0.82, 0.18, length.out = nr)
    right_nodes <- data.frame(
      facility = all_right_dests,
      x = ifelse(all_right_dests == "ANMC", 0.69, 0.708),
      y = ry,
      color = unname(right_colors[all_right_dests]),
      n = vapply(all_right_dests, function(d) n_right[[d]] %||% 0L, integer(1)),
      stringsAsFactors = FALSE
    )
  }

  flow_ns <- c(
    villages_df$to_mhc,
    villages_df$direct_to_anmc,
    unlist(sec_counts, use.names = FALSE)
  )
  flow_ns <- flow_ns[flow_ns > 0L]
  max_flow <- if (length(flow_ns) > 0L) max(flow_ns) else 1L

  list(
    villages = villages_df,
    mhc = mhc,
    right_nodes = right_nodes,
    sec_counts = sec_counts,
    max_flow = max_flow,
    total_journeys = sum(unlist(village_total))
  )
}

.fig2_draw_grid <- function(layout) {
  grid::grid.newpage()
  grid::pushViewport(grid::viewport(width = 0.96, height = 0.94))

  villages    <- layout$villages
  mhc         <- layout$mhc
  right_nodes <- layout$right_nodes
  max_flow    <- layout$max_flow

  grid::grid.text(
    sprintf(
      "Figure 2. Pediatric Medevac Routes by Village  (n = %d journeys)",
      layout$total_journeys
    ),
    x = grid::unit(0.5, "npc"), y = grid::unit(0.975, "npc"),
    gp = grid::gpar(fontsize = 15.5, col = "#2b2b2b")
  )

  grid::grid.text(
    "Village Clinics", x = grid::unit(0.14, "npc"), y = grid::unit(0.915, "npc"),
    gp = grid::gpar(fontsize = 10.5, fontface = "bold", col = "#333333")
  )
  grid::grid.text(
    "Maniilaq\nHealth Center", x = grid::unit(0.49, "npc"), y = grid::unit(0.915, "npc"),
    gp = grid::gpar(fontsize = 10.5, fontface = "bold", col = "#333333")
  )
  grid::grid.text(
    "Receiving Facilities", x = grid::unit(0.78, "npc"), y = grid::unit(0.915, "npc"),
    gp = grid::gpar(fontsize = 10.5, fontface = "bold", col = "#333333")
  )

  # Links first so nodes sit on top.
  for (i in seq_len(nrow(villages))) {
    .fig2_draw_link(
      villages$x[i] + 0.017, villages$y[i],
      mhc$x - 0.06, mhc$y,
      villages$color[i], villages$to_mhc[i], max_flow,
      curvature = ifelse(villages$y[i] > mhc$y, -0.20, 0.20),
      alpha = 0.72
    )
    if (villages$direct_to_anmc[i] > 0L) {
      anmc_y <- right_nodes$y[right_nodes$facility == "ANMC"]
      if (length(anmc_y) == 1L) {
        .fig2_draw_link(
          villages$x[i] + 0.017, villages$y[i],
          0.69, anmc_y,
          villages$color[i], villages$direct_to_anmc[i], max_flow,
          curvature = ifelse(villages$y[i] > 0.835, -0.10, 0.16),
          alpha = 0.70,
          lwd = 1.2 + 0.8 * villages$direct_to_anmc[i]
        )
      }
    }
  }

  for (dest in names(layout$sec_counts)) {
    n <- layout$sec_counts[[dest]]
    if (dest == "MHC" || n <= 0L) next
    row <- right_nodes[right_nodes$facility == dest, , drop = FALSE]
    if (nrow(row) == 0L) next
    rx <- if (dest == "ANMC") 0.69 else 0.708
    curv <- if (row$y > mhc$y) 0.28 else if (abs(row$y - mhc$y) < 0.05) 0.00 else -0.26
    .fig2_draw_link(
      mhc$x + 0.06, mhc$y, rx, row$y,
      "#8b8b8b", n, max_flow,
      curvature = curv, alpha = 0.82,
      lwd = .fig2_flow_lwd(n, max_flow)
    )
    .fig2_draw_label_box(
      paste0("2\u00b0 n=", n),
      (mhc$x + rx) / 2 + 0.04,
      (mhc$y + row$y) / 2
    )
  }

  for (i in seq_len(nrow(villages))) {
    .fig2_draw_ellipse(villages$x[i], villages$y[i], 0.039, 0.038, villages$color[i])
    grid::grid.text(
      sprintf("%s  %d", villages$village[i], villages$n[i]),
      x = grid::unit(villages$x[i] - 0.028, "npc"),
      y = grid::unit(villages$y[i], "npc"),
      just = "right",
      gp = grid::gpar(fontsize = 8.3, col = "#333333")
    )
  }

  .fig2_draw_ellipse(
    mhc$x, mhc$y, 0.11, 0.105, mhc$color,
    label = sprintf("Maniilaq\nHealth Center\nn = %d", mhc$n),
    label_gp = grid::gpar(col = "white", fontsize = 8.7, fontface = "bold", lineheight = 0.88)
  )

  for (i in seq_len(nrow(right_nodes))) {
    w <- if (right_nodes$facility[i] == "ANMC") 0.066 else 0.033
    h <- if (right_nodes$facility[i] == "ANMC") 0.060 else 0.030
    .fig2_draw_ellipse(right_nodes$x[i], right_nodes$y[i], w, h, right_nodes$color[i])
    grid::grid.text(
      sprintf("%s\nn = %d", right_nodes$facility[i], right_nodes$n[i]),
      x = grid::unit(right_nodes$x[i] + 0.031, "npc"),
      y = grid::unit(right_nodes$y[i], "npc"),
      just = "left",
      gp = grid::gpar(
        fontsize = 8.2, fontface = "bold", col = right_nodes$color[i],
        lineheight = 0.88
      )
    )
  }

  legend_ns <- sort(unique(c(1L, max(1L, max_flow %/% 2L), max_flow)))
  legend_ns <- legend_ns[legend_ns > 0L]
  legend_lwd <- vapply(legend_ns, .fig2_flow_lwd, numeric(1), max_flow = max_flow)
  legend_labels <- c(paste0("n = ", legend_ns), "MHC \u2192 facility\n(secondary)")
  legend_x <- c(0.37, 0.45, 0.535, 0.625)[seq_along(legend_labels)]
  legend_lwd_all <- c(legend_lwd, 2.2)
  legend_y <- 0.035

  grid::grid.roundrect(
    x = grid::unit(0.51, "npc"), y = grid::unit(0.018, "npc"),
    width = grid::unit(0.36, "npc"), height = grid::unit(0.055, "npc"),
    just = c("center", "bottom"),
    r = grid::unit(0.004, "npc"),
    gp = grid::gpar(fill = "#fbfbfb", col = "#cfcfcf", lwd = 1.2)
  )
  grid::grid.text(
    "Transfer volume", x = grid::unit(0.51, "npc"), y = grid::unit(0.055, "npc"),
    gp = grid::gpar(fontsize = 8.5, col = "#222222")
  )

  for (i in seq_along(legend_ns)) {
    grid::grid.lines(
      x = grid::unit(c(legend_x[i] - 0.03, legend_x[i] + 0.01), "npc"),
      y = grid::unit(c(legend_y, legend_y), "npc"),
      gp = grid::gpar(col = "#5c5c5c", lwd = legend_lwd_all[i], lineend = "round")
    )
    grid::grid.text(
      legend_labels[i], x = grid::unit(legend_x[i] + 0.025, "npc"),
      y = grid::unit(legend_y, "npc"), just = "left",
      gp = grid::gpar(fontsize = 7.2, col = "#222222")
    )
  }
  i <- length(legend_ns) + 1L
  grid::grid.lines(
    x = grid::unit(c(legend_x[i] - 0.03, legend_x[i] + 0.01), "npc"),
    y = grid::unit(c(legend_y, legend_y), "npc"),
    gp = grid::gpar(col = "#5c5c5c", lwd = legend_lwd_all[i], lty = 2, lineend = "butt")
  )
  grid::grid.text(
    legend_labels[i], x = grid::unit(legend_x[i] + 0.025, "npc"),
    y = grid::unit(legend_y, "npc"), just = "left",
    gp = grid::gpar(fontsize = 7.2, col = "#222222", lineheight = 0.88)
  )

  grid::popViewport()
}

#' Village-level network flow diagram of pediatric medevac routes.
#'
#' Grid-based layout matching Codex/Python `plot_fig4_sankey_transport_routes()`.
#'
#' @return A ggplot2 object wrapping the grid drawing (for knitr display)
fig2_sankey_routes <- function() {
  empty_plot <- function(msg) {
    ggplot() +
      annotate("text", x = 0.5, y = 0.5, label = msg, size = 4.5) +
      coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE) +
      theme_void()
  }

  csv_path <- export_fig2_medevac_routes(format = "aggregate")
  if (.fig2_codex_available()) {
    codex_png <- .fig2_render_via_codex(csv_path)
    if (!is.null(codex_png) && nzchar(codex_png) && file.exists(codex_png)) {
      grob <- .fig2_grob_from_png(codex_png)
      return(
        ggplot() +
          annotation_custom(grob, xmin = 0, xmax = 1, ymin = 0, ymax = 1) +
          coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE, clip = "off") +
          theme_void() +
          theme(plot.margin = margin(0, 0, 0, 0))
      )
    }
  }

  dat <- .build_sankey_data()
  if (length(dat$villages) == 0L) return(empty_plot("No village-origin legs found."))

  layout <- .build_fig2_layout(dat)
  if (is.null(layout)) return(empty_plot("No village-origin legs found."))

  grob <- grid::grid.grabExpr(.fig2_draw_grid(layout))
  ggplot() +
    annotation_custom(grob, xmin = 0, xmax = 1, ymin = 0, ymax = 1) +
    coord_cartesian(xlim = c(0, 1), ylim = c(0, 1), expand = FALSE, clip = "off") +
    theme_void() +
    theme(plot.margin = margin(0, 0, 0, 0))
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

  csv_path <- export_fig2_medevac_routes(format = "aggregate")
  if (.fig2_codex_available()) {
    codex_out <- .fig2_render_via_codex(csv_path, out_png = out_path)
    if (!is.null(codex_out)) return(invisible(codex_out))
  }

  dat <- .build_sankey_data()
  if (length(dat$villages) == 0L) {
    warning("No village-origin legs found; skipping Figure 2 save.")
    return(invisible(NULL))
  }
  layout <- .build_fig2_layout(dat)

  grDevices::png(out_path, width = width, height = height, units = "in", res = dpi, bg = "white")
  .fig2_draw_grid(layout)
  grDevices::dev.off()
  message("Saved: ", out_path)
}
