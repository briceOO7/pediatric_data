# Synthetic tests (no PHI): complaint tables never drop a journey.
# Run from the repo root: Rscript tests/test_complaint_groups.R
source(file.path("analysis", "R", "complaint_groups.R"))

x <- c(rep("Fever", 12), rep("Cough", 10), rep("Rash", 3), rep("Ear pain", 2),
       NA, "", "Unknown", "Undefined")
f <- cc_display_factor(x, min_n = 10)

stopifnot(length(f) == length(x), !anyNA(f))
stopifnot(identical(levels(f), c("Fever", "Cough", "Other", "Unknown/Undefined")))
stopifnot(sum(f == "Fever") == 12, sum(f == "Cough") == 10)
stopifnot(sum(f == "Other") == 5, sum(f == "Unknown/Undefined") == 4)
stopifnot(identical(attr(f, "other_members"), c(Rash = 3L, `Ear pain` = 2L)))

# No pooled complaints and no unknowns: no extra levels, nothing missing.
g <- cc_display_factor(rep("Fever", 12), min_n = 10)
stopifnot(identical(levels(g), "Fever"), !anyNA(g))
cat("test_complaint_groups.R: OK\n")
