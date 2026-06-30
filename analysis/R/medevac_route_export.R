# medevac_route_export.R — Export Figure 2 route data for Codex Sankey script
#
# Writes CSV in either schema accepted by scripts/medevac_sankey_manuscript.R:
#   1. row-level:  village, mhc, receiving_facility
#   2. aggregate:  leg_type, origin, destination, n_legs

suppressPackageStartupMessages({
  library(here)
  library(dplyr)
})

#' Export village-originating medevac routes for the Codex Sankey script.
#'
#' @param format `"aggregate"` (default) or `"row"`.
#' @param out_path Output CSV path. Defaults to outputs/data/fig2_medevac_routes.csv.
#' @param journeys Data frame of journeys (defaults to journeys_primary.csv).
#' @return Path to the written CSV (invisibly).
export_fig2_medevac_routes <- function(
    format = c("aggregate", "row"),
    out_path = here("outputs", "data", "fig2_medevac_routes.csv"),
    journeys = NULL) {
  format <- match.arg(format)

  if (is.null(journeys)) {
    journeys <- readr::read_csv(
      here("outputs", "data", "journeys_primary.csv"),
      show_col_types = FALSE
    )
  }

  dat <- build_fig2_route_flows(journeys)

  out_dir <- dirname(out_path)
  if (!dir.exists(out_dir)) dir.create(out_dir, recursive = TRUE)

  if (format == "aggregate") {
    df <- build_fig2_aggregate_routes(dat)
  } else {
    df <- build_fig2_row_routes(dat)
  }

  readr::write_csv(df, out_path)
  message("Exported Figure 2 routes (", format, "): ", out_path)
  invisible(out_path)
}

#' @rdname export_fig2_medevac_routes
build_fig2_route_flows <- function(journeys) {
  `%||%` <- function(x, y) {
    if (length(x) == 0L) return(y)
    if (is.na(x) || (is.character(x) && !nzchar(trimws(x)))) y else x
  }

  is_study_facility_origin <- function(place) {
    if (is.na(place)) return(TRUE)
    t <- trimws(as.character(place))
    if (!nzchar(t)) return(TRUE)
    u <- toupper(gsub("_", "", t))
    if (startsWith(u, "CAH") || startsWith(u, "HUB") ||
        grepl("OUTSIDEHOSPITAL", u, fixed = TRUE)) {
      return(TRUE)
    }
    tl <- tolower(t)
    if (grepl("maniilaq", tl, fixed = TRUE) && grepl("health", tl, fixed = TRUE)) {
      return(TRUE)
    }
    if (tl == "mhc") return(TRUE)
    FALSE
  }

  village_origin_mode <- function() {
    syn <- tolower(Sys.getenv("MEDEVAC_SYNTHETIC", "0"))
    if (syn %in% c("1", "true", "yes", "y", "on")) "codebook" else "infer"
  }

  maniilaq_village_names <- function() {
    cb_path <- here("docs", "village_name_codebook.csv")
    if (!file.exists(cb_path)) return(character(0))
    unique(trimws(read.csv(cb_path, stringsAsFactors = FALSE)$community_name))
  }

  is_village_medevac_origin <- function(place) {
    s <- trimws(as.character(place %||% ""))
    if (!nzchar(s)) return(FALSE)
    mode <- village_origin_mode()
    if (mode == "infer") return(!is_study_facility_origin(s))
    if (startsWith(s, "Village_")) return(TRUE)
    s %in% maniilaq_village_names()
  }

  is_anmc <- function(v) {
    t <- trimws(as.character(v %||% ""))
    tl <- tolower(t)
    startsWith(t, "Hub") ||
      toupper(t) %in% c("HUB_01", "ANMC") ||
      (grepl("alaska native", tl, fixed = TRUE) && grepl("medical", tl, fixed = TRUE))
  }

  is_mhc_cah_destination <- function(to_raw) {
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

  outside_facility_names <- list(
    c("providence", "Providence"),
    c("alaska regional", "Alaska Regional"),
    c("alaska reg", "Alaska Regional"),
    c("arh", "Alaska Regional")
  )

  outside_facility_label <- function(raw) {
    t <- trimws(as.character(raw %||% ""))
    tl <- tolower(t)
    for (pair in outside_facility_names) {
      if (grepl(pair[[1]], tl, fixed = TRUE)) return(pair[[2]])
    }
    t
  }

  dest_label <- function(v) {
    if (is.na(v) || !nzchar(trimws(as.character(v)))) return("")
    if (is_mhc_cah_destination(v)) return("MHC")
    if (is_anmc(v)) return("ANMC")
    outside_facility_label(v)
  }

  resolve_village_origin <- function(r) {
    for (field in c("village_name", "medevac1_from", "facility_1_name")) {
      if (!field %in% names(r)) next
      s <- trimws(as.character(r[[field]] %||% ""))
      if (nzchar(s) && is_village_medevac_origin(s)) return(s)
    }
    ""
  }

  flow_rows <- vector("list", nrow(journeys))
  for (i in seq_len(nrow(journeys))) {
    r <- journeys[i, ]
    vname <- resolve_village_origin(r)
    if (!nzchar(vname)) next

    legs <- c(
      dest_label(r$medevac1_to),
      dest_label(r$medevac2_to),
      dest_label(r$medevac3_to)
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
      dplyr::group_by(village, dest) |>
      dplyr::summarise(n = dplyr::n(), .groups = "drop")
  } else {
    data.frame(village = character(0), dest = character(0), n = integer(0),
               stringsAsFactors = FALSE)
  }

  list(
    prim_df = prim_df,
    sec_counts = sec_counts,
    village_total = village_total,
    flow_rows = flow_rows
  )
}

#' @rdname export_fig2_medevac_routes
build_fig2_aggregate_routes <- function(dat) {
  prim_df <- dat$prim_df
  sec_counts <- dat$sec_counts

  rows <- list()
  if (nrow(prim_df) > 0L) {
    for (i in seq_len(nrow(prim_df))) {
      dest <- prim_df$dest[[i]]
      leg_type <- if (identical(dest, "MHC")) "primary" else "direct"
      rows[[length(rows) + 1L]] <- data.frame(
        leg_type = leg_type,
        origin = prim_df$village[[i]],
        destination = dest,
        n_legs = prim_df$n[[i]],
        stringsAsFactors = FALSE
      )
    }
  }

  for (dest in names(sec_counts)) {
    n <- sec_counts[[dest]]
    if (dest == "MHC" || n <= 0L) next
    rows[[length(rows) + 1L]] <- data.frame(
      leg_type = "secondary",
      origin = "MHC",
      destination = dest,
      n_legs = n,
      stringsAsFactors = FALSE
    )
  }

  if (length(rows) == 0L) {
    return(data.frame(
      leg_type = character(0), origin = character(0),
      destination = character(0), n_legs = integer(0),
      stringsAsFactors = FALSE
    ))
  }

  do.call(rbind, rows)
}

#' @rdname export_fig2_medevac_routes
build_fig2_row_routes <- function(dat) {
  if (length(dat$flow_rows) == 0L) {
    return(data.frame(
      village = character(0), mhc = character(0),
      receiving_facility = character(0),
      stringsAsFactors = FALSE
    ))
  }

  rows <- lapply(dat$flow_rows, function(fr) {
    prim <- fr$primary
    if (identical(prim, "MHC")) {
      mhc <- TRUE
      recv <- if (length(fr$sec_from_mhc) >= 1L) fr$sec_from_mhc[[1L]] else NA_character_
    } else if (nzchar(prim)) {
      mhc <- FALSE
      recv <- prim
    } else {
      mhc <- NA
      recv <- NA_character_
    }
    data.frame(
      village = fr$village,
      mhc = mhc,
      receiving_facility = recv,
      stringsAsFactors = FALSE
    )
  })

  do.call(rbind, rows)
}
