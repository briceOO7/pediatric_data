# complaint_groups.R -- base R only.
#
# STANDING RULE: a chief complaint never drops a journey. In complaint-specific
# tables every journey sits in exactly one row: a reported complaint (>= min_n
# journeys overall), "Other" (rarer complaints pooled), or "Unknown/Undefined"
# (missing / blank / 999 / "Unknown" / "Undefined"). Row counts therefore sum to
# the journey total. Mirrors cedis_policy.complaint_display_groups() in Python.

CC_UNKNOWN_UNDEFINED <- "Unknown/Undefined"
CC_OTHER             <- "Other"

cc_is_unknown <- function(x) {
  x <- trimws(as.character(x))
  is.na(x) | tolower(x) %in% c("", "undefined", "unknown", "unknown/undefined", "nan", "none", "na")
}

#' @return factor with levels: reported complaints (most frequent first), then
#'   "Other" (only if any complaint was pooled), then "Unknown/Undefined" (only
#'   if any journey has no usable complaint). Attribute `other_members` is a named
#'   integer vector of the complaints pooled into "Other".
cc_display_factor <- function(x, min_n = 10) {
  x <- trimws(as.character(x))
  unknown <- cc_is_unknown(x)
  counts <- table(x[!unknown])
  counts <- counts[order(-as.integer(counts), names(counts))]
  reported <- names(counts)[counts >= min_n]
  pooled <- counts[counts < min_n]

  out <- ifelse(unknown, CC_UNKNOWN_UNDEFINED,
                ifelse(x %in% reported, x, CC_OTHER))
  levels_out <- c(reported,
                  if (length(pooled) > 0) CC_OTHER,
                  if (any(unknown)) CC_UNKNOWN_UNDEFINED)
  res <- factor(out, levels = levels_out)
  attr(res, "other_members") <- stats::setNames(as.integer(pooled), names(pooled))
  res
}
