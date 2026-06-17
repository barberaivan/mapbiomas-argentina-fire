#!/usr/bin/env Rscript
# veg-fire_remap_clean-google-sheet.R
# -----------------------------------------------------------------------------
# Build the canonical veg_fire remap table from the "remap_by_region" sheet of
# the working Google Sheet, and write it to collection-01/config/veg_fire_remap.csv.
#
# The Google Sheet is the human-facing source (documentation / editing surface).
# The CSV it produces is the canonical, language-agnostic source of truth that
# both Python (utils/constants.py) and R (model fitting) load. Re-run this script
# whenever the sheet changes.
#
#   Source sheet (sheet/tab = "remap_by_region"):
#   https://docs.google.com/spreadsheets/d/17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A/edit?gid=1376068841
#
# Reads the PUBLIC CSV export (no OAuth) — the sheet must be link-viewable.
# Base R only (no tidyverse), so it runs from a bare Rscript.
#
# Run from the repo root:  Rscript collection-01/scripts/veg-fire_remap_clean-google-sheet.R
# -----------------------------------------------------------------------------

SHEET_ID <- "17ZShb8D0JaJw4nLvBDzt19xF6Fdg8lGHYs4Jogh0X1A"
GID      <- "1376068841"
OUT      <- file.path("collection-01", "config", "veg_fire_remap.csv")

# veg_fire classes that get NO model fitted, but must still be identified
# (training: filter these points out; prediction: flag them in QA bands).
NONFITTABLE <- c("non-burnable", "non-observed")

squish <- function(x) {
  x <- gsub("\\s+", " ", trimws(x))
  x[x == ""] <- NA_character_
  x
}

url <- sprintf("https://docs.google.com/spreadsheets/d/%s/export?format=csv&gid=%s",
               SHEET_ID, GID)
raw <- read.csv(url, stringsAsFactors = FALSE, na.strings = c("NA", ""),
                check.names = FALSE, encoding = "UTF-8")

# Keep only level-2/3 land-cover rows: the level-1 grouping rows carry id = NA.
# (Note: "No Observado" is level 1 but has id = 27, so we filter on id, not level.)
raw <- raw[!is.na(raw$id), ]

out <- data.frame(
  mb_class_raw  = as.integer(raw$id),                 # MB country-level class; matches training-data column
  arg_name      = squish(raw$arg_name),               # MB country-level class name (Argentina legend)
  region        = squish(raw$region),
  region_num    = as.integer(raw$region_num),         # region code, as in the GEE region-id raster
  local_class   = squish(raw$region_name_ambig),      # region-wise name(s); may list several
  veg_fire_name = squish(raw$veg_fire_name),          # post-workshop physiognomic class name
  stringsAsFactors = FALSE
)

# Drop classes that do not occur in a region: those are left with an empty
# veg_fire_name in the sheet on purpose. Keeping them would invent veg_fire
# classes with no data. Log what's dropped so a genuine omission stays visible.
drop_absent <- out[is.na(out$veg_fire_name), c("region", "mb_class_raw", "arg_name")]
if (nrow(drop_absent) > 0) {
  message(nrow(drop_absent), " row(s) dropped (no veg_fire_name = class absent in region):\n",
          paste(capture.output(print(drop_absent, row.names = FALSE)), collapse = "\n"))
}
out <- out[!is.na(out$veg_fire_name), ]

# ── validation ───────────────────────────────────────────────────────────────
key <- paste(out$region_num, out$mb_class_raw)
dup <- names(which(table(key) > 1))
if (length(dup) > 0) {
  warning("Duplicate (region_num, mb_class_raw) keys — the remap is not 1:1: ",
          paste(dup, collapse = "; "))
}

# ── number the veg_fire classes 1..K ─────────────────────────────────────────
# Fittable classes first (alphabetical) → 1..M, then the non-fittable ones.
fittable_names <- sort(unique(
  out$veg_fire_name[!is.na(out$veg_fire_name) & !out$veg_fire_name %in% NONFITTABLE]))
ordered_names <- c(fittable_names, intersect(NONFITTABLE, unique(out$veg_fire_name)))

out$veg_fire <- match(out$veg_fire_name, ordered_names)                 # integer code 1..K
out$fittable <- !is.na(out$veg_fire_name) & !(out$veg_fire_name %in% NONFITTABLE)

out <- out[, c("mb_class_raw", "arg_name", "region", "region_num",
               "local_class", "veg_fire", "veg_fire_name", "fittable")]
out <- out[order(out$region_num, out$mb_class_raw), ]

dir.create(dirname(OUT), showWarnings = FALSE, recursive = TRUE)
write.csv(out, OUT, row.names = FALSE, na = "", fileEncoding = "UTF-8")

message(sprintf("Wrote %s\n  %d rows | %d veg_fire classes (%d fittable, %d non-fittable)",
                OUT, nrow(out), length(ordered_names),
                length(fittable_names), length(ordered_names) - length(fittable_names)))
