source("renv/activate.R")

# On Windows, prefer pre-built binaries to avoid needing Rtools for packages
# with compiled components (sf, units, s2, etc.)
if (.Platform$OS.type == "windows") {
  options(pkgType = "binary")
}
