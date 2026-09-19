#!/usr/bin/env Rscript
# =============================================================================
# 07-calendar_scars.R — calendar-year burn mask -> 8-connected SCARS (id + area)
# =============================================================================
# Step 07b. The network publishes scar id / area / size-range per CALENDAR year, defined
# as "sets of spatially connected pixels within the same year". Our objects are FIRE-YEAR
# entities under a deliberately non-standard connectivity (step 05's 1-px dilation), so
# the scars are a SEPARATE labelling pass, done locally because GEE cannot do it —
# `connectedPixelCount` caps at 1024 px, far below a real scar.
#
# TWO PASSES, because each fire-year feeds TWO calendar years and reading the 248 carta
# tiles is the dominant cost. Run `pixels` to completion first: a calendar year needs
# BOTH its fire-years.
#
# Run from the repo ROOT:
#   Rscript collection-01/workflow/07-calendar_scars.R pixels [fire_year ...]
#   Rscript collection-01/workflow/07-calendar_scars.R scars  [cal_year ...]
#   CARTAS=SK-19-V-A,SK-19-Y-A  Rscript ... pixels 1998     # tiny smoke test
#   OBJ_CORES=<n>  parallelises the per-scar vectorize (as in step 05)
#
#   # both passes over every year, resumable:
#   collection-01/scripts/run_07_scars.sh pixels
#   collection-01/scripts/run_07_scars.sh scars
#   $PYTHON collection-01/scripts/validate_scar_zips.py    # gate BEFORE the manual ingest
#
# Design: docs/07-vector_to_raster.md "07b — the local scar build" — the calendar
# partition, the plain 8-connectivity, why a fire straddling 31 December becomes two
# scars, and the proof that painting the object polygons reproduces the object pixel set
# exactly. Sequence: docs/07-vector_to_raster.md "Order of operations".
#
# Outputs (collection-01/data/):
#   scars-pixels-cache/cy<Y>_fy<fy>.rds   regenerable pixel cache (pass 1)
#   objects-scars/scars_<Y>.gpkg          scar polygons + scar_id/area_ha/n_px/year
#   objects-scars/scars_<Y>_summary.csv   per-year validation: month histogram, px, ha, guard
#   scars-upload-cache/scars_<Y>.zip      zipped Shapefile for the manual GEE ingest
# =============================================================================

suppressPackageStartupMessages({
  library(terra)
  library(sf)
  library(data.table)
  library(Rcpp)
})

# ── reuse the step-05 machinery (vectorize_sparse/.one_object/grid_of). Sourcing does NOT
#    run its main(): 05 guards on sys.nframe() == 0. ─────────────────────────────────────
.this <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
HERE  <- if (length(.this)) dirname(normalizePath(.this)) else file.path(getwd(), "collection-01/workflow")
source(file.path(HERE, "05-objects_metrics.R"))
Rcpp::sourceCpp(file.path(HERE, "..", "utils", "label_uf.cpp"))

# ── config ───────────────────────────────────────────────────────────────────
SNIC_DIR        <- "collection-01/data/snic-rasters"   # MIRRORS 05-objects_metrics.R::SNIC_DIR
OBJ_DIR         <- "collection-01/data/objects-raw"
PRED_DIR        <- "collection-01/data/objects-pred"
PIX_CACHE       <- "collection-01/data/scars-pixels-cache"   # -cache = regenerable
SCAR_DIR        <- "collection-01/data/objects-scars"
ZIP_DIR         <- "collection-01/data/scars-upload-cache"   # -cache = regenerable

FIRST_FIRE_YEAR <- 1998; LAST_FIRE_YEAR <- 2025
CAL_YEARS       <- 1999:2025      # the published calendar series (docs/07)
MIN_FIRE_HA     <- 1              # minimum mapped fire, on the OBJECT (docs/07 "The decisions this step rests on")

# ── the two object EXCLUSION rules (docs/07 "Object exclusion ruleset") ─────────────────────────────
# FINAL thresholds, confirmed with the team 2026-09-11, and ON BY DEFAULT: a run with no
# environment overrides produces the PUBLISHED selection. MIRRORED from
# utils/constants.py::{T_GRASS, GRASS_WINDOW, T_AGRI} -- there is no automatic sync between
# this file and the Python constants, so KEEP THESE IN SYNC. They must equal what 07a painted
# with or the scar layer stops being the month raster's mask.
#
# The env overrides exist for the explorers and TESTS/ only. RULES=0 builds the unfiltered
# pixel set; both passes and the launcher read the same variables, so a run cannot end up with
# one pass filtered and the other not.
RULES        <- Sys.getenv("RULES", "1") != "0"
T_GRASS      <- as.numeric(Sys.getenv("T_GRASS", "0.70"))   # rule A: frac_c15 above this
GRASS_WINDOW <- c("07-01", "11-15")                          # rule A: date_med inside (MM-DD)
T_AGRI       <- as.numeric(Sys.getenv("T_AGRI",  "0.40"))   # rule B: frac_agri above this
# Rule A's two CONFINEMENTS (docs/07 "Object exclusion ruleset", added 2026-09-12). veg_fire 15 is the remap of
# MapBiomas 11/12/15 in the PAMPA region, so the Delta del Parana marshes carry it like a
# Pampa pasture; unconfined, rule A deleted 65.7 % of the Delta's FY2020 burned area.
RULE_A_MAX_HA <- as.numeric(Sys.getenv("RULE_A_MAX_HA", "150"))
# AOI membership is NOT tested here. It is precomputed ONCE per fire-year by
# scripts/rule_a_aoi_tag.R (terra::is.related(v, aoi, "intersects")) into
# objects-analysis/aoi_rule_a_<fy>.csv, and read as a column. Both passes and every other
# reader then see the same answer, and the GEE side tests the same PLANAR polygon with
# ee.Filter.bounds -- verified identical to the object on FY2020 (8,227 dropped / 136,993 ha).
AOI_TAG_DIR  <- "collection-01/data/objects-analysis"   # symlink into the store

# The canonical SNIC grid — IDENTICAL in all 56 snic/snic_metrics assets and in every carta
# tile (verified 2026-07-29). Mirrored in utils/constants.py::SNIC_TRANSFORM; keep in sync.
#
# THE LATTICE IS A CONSTANT, never derived from the tiles on disk. `cell = (row-1)*NC + col` is
# the labelling key, so if NC differed between the two fire-years feeding a calendar year — or
# between the two passes — unrelated scars would silently merge. Verified over all 28
# fire-years: the same 248 cartas, byte-identical extents, so NC/NR below are exact.
#
# The origin is shifted ONE PIXEL WEST of the SNIC transform origin (-73.58468801489491),
# because the westernmost carta starts exactly there (offset -1 px, integral). Without the
# shift `col` would run 0..74085 — 74086 distinct values against NC = 74085 — and
# (row-1)*NC + NC would collide with row*NC + 0.
G_D  <- 0.000269494585236
G_X0 <- -73.58468801489491 - G_D    # = -73.58495750948015, the westernmost carta's xmin
G_Y0 <- -21.764113209062533         # northernmost carta's ymax (offset 0, no shift needed)
G_NC <- 74086L                      # 74085 + the shifted column
G_NR <- 123601L

# Patagonia dieback longitude cut — MIRRORS 05-objects_metrics.R::DIEBACK_LON_CUT. Step 05
# dropped candseed==3 east of this BEFORE labelling, so the objects never contained them.
DIEBACK_LON_CUT <- -70.6
# A candseed==3 pixel takes its PARENT OBJECT's median date: its own abs_date is a next-year
# spring dieback-detection date, not a burn date (docs/07 "candseed == 3"). Measured: 881k such pixels
# (~79 kha) survive the cut over the 28 fire-years. Left raw they report austral-winter burn
# months and, whenever the parent fire burned May-Dec, fall into the NEXT calendar year —
# splitting the scar and minting a phantom scar with its own id and size class.
DIEBACK_USE_PARENT_DATE <- TRUE

EPOCH        <- "1970-01-01"
BANDS_DIRECT <- c("abs_date", "veg_fire", "n",
                  "burned_around_1", "burned_around_2", "burned_around_3", "candseed")
POLY_CHUNK   <- 10000L    # polygons per terra::cells() call — caps peak RSS

terraOptions(progress = 0)

dayn <- function(y, m = 1, d = 1) as.integer(as.IDate(sprintf("%04d-%02d-%02d", y, m, d)))

# ── the global lattice ────────────────────────────────────────────────────────
# Constant by construction (see above) — takes no arguments so no caller can perturb it.
global_grid <- function() {
  list(nc = G_NC, nr = G_NR, x0 = G_X0, y0 = G_Y0, dx = G_D, ady = G_D,
       crs = "EPSG:4326", lonlat = TRUE)
}

tif_list <- function(fy) {
  d <- file.path(SNIC_DIR, as.character(fy))
  if (!dir.exists(d)) stop(sprintf("no snic-rasters for FY%d (%s)", fy, d))
  tf <- sort(list.files(d, pattern = "\\.tif$", full.names = TRUE))
  keep <- Sys.getenv("CARTAS", "")
  if (nzchar(keep)) {                                  # smoke-test subset
    want <- trimws(strsplit(keep, ",")[[1]])
    tf <- tf[tools::file_path_sans_ext(basename(tf)) %in% want]
  }
  if (!length(tf)) stop(sprintf("no carta tiles selected for FY%d", fy))
  tf
}

# per-row cell area (m²): on a lon/lat grid it depends only on latitude, so one 1-column
# strip gives every row's area — O(nrow), never a full-grid scan (as step 05 does).
row_cell_area <- function(g) {
  strip <- terra::rast(nrows = g$nr, ncols = 1L, crs = g$crs,
                       xmin = g$x0, xmax = g$x0 + g$dx,
                       ymin = g$y0 - g$nr * g$ady, ymax = g$y0)
  terra::values(terra::cellSize(strip, unit = "m"))[, 1]
}

# ── pass 1 — accepted burned pixels of one fire-year, split by calendar year ───
# Rule A's window in DAY NUMBERS since EPOCH, for one fire year. The fire year runs 1 May fy
# to 30 Apr fy+1, so a window month >= 5 belongs to fy and a month <= 4 to fy+1. Mirrors
# utils/constants.py::grass_window_days().
grass_window_days <- function(fy) {
  bound <- function(md) {
    mm <- as.integer(substr(md, 1, 2))
    y  <- if (mm >= 5) fy else fy + 1L
    as.integer(as.Date(sprintf("%d-%s", y, md)) - as.Date(EPOCH))
  }
  c(bound(GRASS_WINDOW[1]), bound(GRASS_WINDOW[2]))
}

# The rule-A AOI membership of one fire-year's objects, as a named 0/1 vector keyed by oid.
# A HARD ERROR when the tag file is missing: silently treating every object as outside the
# AOI would disable half of rule A and produce a map that looks plausible and is not the
# published selection. Run `Rscript collection-01/scripts/rule_a_aoi_tag.R` first.
aoi_tag <- function(fy) {
  f <- file.path(AOI_TAG_DIR, sprintf("aoi_rule_a_%d.csv", fy))
  if (!file.exists(f)) {
    stop(sprintf(paste0("rule-A AOI tag missing for FY%d:\n  %s\n",
                        "Build it with:  Rscript collection-01/scripts/rule_a_aoi_tag.R %d"),
                 fy, f, fy))
  }
  t <- fread(f, select = c("oid", "in_aoi"))
  setNames(as.integer(t$in_aoi), t$oid)
}

accepted_oids <- function(fy) {
  pr <- fread(file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy)), select = c("oid", "fire"))
  cols <- c("oid", "area_ha", "date_median", "n_pixels")
  if (RULES) cols <- c(cols, "frac_c1", "frac_c2", "frac_c3", "frac_c15")
  mt <- fread(file.path(OBJ_DIR, sprintf("objects_%d_raster_metrics.csv", fy)), select = cols)
  a <- merge(pr, mt, by = "oid")[fire == 1 & area_ha >= MIN_FIRE_HA & !is.na(date_median)]
  if (RULES) {
    before <- nrow(a)
    w <- grass_window_days(fy)
    tag <- aoi_tag(fy)
    a[, in_aoi := tag[oid]]
    if (anyNA(a$in_aoi)) {
      stop(sprintf(paste0("FY%d: %d accepted objects are absent from the rule-A AOI tag -- ",
                          "the tag is stale, rebuild it with FORCE=1"),
                   fy, sum(is.na(a$in_aoi))))
    }
    # rule A -- Pampa grassland in the winter-spring window, CONFINED to objects under
    # RULE_A_MAX_HA that INTERSECT the agricultural-Pampa AOI; rule B -- agriculture anywhere.
    # Both drop on `>`, so the keep is `<=` (docs/07 "Object exclusion ruleset"). `frac_c15` is the SINGLE veg_fire
    # class 15 grassland_pampa, not the aggregated frac_gr_tp. All four of rule A's conjuncts
    # must match 07a/07e exactly, `area_ha <` and the intersects included.
    a <- a[!(frac_c15 > T_GRASS & date_median >= w[1] & date_median <= w[2] &
             area_ha < RULE_A_MAX_HA & in_aoi == 1L)]
    nA <- before - nrow(a)
    a <- a[frac_c1 + frac_c2 + frac_c3 <= T_AGRI]
    message(sprintf(
      "[FY%d]   [rules] A (frac_c15 > %g in %s..%s, < %g ha, in AOI): -%d | B (frac_agri > %g): -%d | %d of %d kept",
      fy, T_GRASS, GRASS_WINDOW[1], GRASS_WINDOW[2], RULE_A_MAX_HA, nA, T_AGRI,
      before - nA - nrow(a), nrow(a), before))
  } else {
    message(sprintf("[FY%d]   [rules] NONE APPLIED -- this is not the published selection", fy))
  }
  a[, date_eff := as.integer(round(date_median))]
  a[, .(oid, date_eff, n_pixels)]
}

# Cell numbers of every accepted object, on the GLOBAL lattice. One sparse terra::cells()
# per polygon chunk — proportional to burned area, never to the 9.16 B-cell grid.
accepted_cells <- function(fy, g, acc, tag) {
  v <- terra::vect(file.path(OBJ_DIR, sprintf("objects_%d.gpkg", fy)))
  v <- v[v$oid %in% acc$oid]
  tmpl <- terra::rast(nrows = g$nr, ncols = g$nc, crs = g$crs,
                      xmin = g$x0, xmax = g$x0 + g$nc * g$dx,
                      ymin = g$y0 - g$nr * g$ady, ymax = g$y0)
  # Resolve each polygon's date ONCE, aligned to `v`'s feature order, and carry the INTEGER
  # date per cell — never the `oid` string. 55 M character entries would cost ~440 MB of
  # pointers and a slow string join; (cell, obj_date) is 12 bytes a row.
  vdate <- acc$date_eff[match(v$oid, acc$oid)]
  chunks <- split(seq_len(nrow(v)), ceiling(seq_len(nrow(v)) / POLY_CHUNK))
  out <- vector("list", length(chunks))
  for (i in seq_along(chunks)) {
    cc <- terra::cells(tmpl, v[chunks[[i]]])
    out[[i]] <- data.table(cell     = as.numeric(cc[, "cell"]),
                           obj_date = vdate[chunks[[i]]][cc[, "ID"]])
    message(sprintf("[%s] cells: chunk %d/%d  (%s cells)", tag, i, length(chunks),
                    format(nrow(out[[i]]), big.mark = ",")))
  }
  ct <- rbindlist(out); rm(out)
  setkey(ct, cell)
  ct
}

pass_pixels <- function(fy) {
  t0 <- Sys.time(); tag <- sprintf("FY%d", fy)
  g  <- global_grid()
  acc <- accepted_oids(fy)
  message(sprintf("\n══ %s pixels ── %s accepted objects, %s px expected ══", tag,
                  format(nrow(acc), big.mark = ","),
                  format(sum(acc$n_pixels), big.mark = ",")))
  ct <- accepted_cells(fy, g, acc, tag)
  message(sprintf("[%s] polygon pixel set: %s cells (expected %s -> %s)", tag,
                  format(nrow(ct), big.mark = ","), format(sum(acc$n_pixels), big.mark = ","),
                  if (nrow(ct) == sum(acc$n_pixels)) "EXACT" else "MISMATCH"))

  tifs <- tif_list(fy)
  parts <- vector("list", length(tifs))
  for (i in seq_along(tifs)) {
    tl <- terra::rast(tifs[i])
    if (!all(BANDS_DIRECT %in% names(tl))) names(tl) <- BANDS_DIRECT[seq_len(nlyr(tl))]
    # values() + which() rather than as.data.frame(cells=TRUE, na.rm=TRUE): measured 2.3-2.5x
    # faster, and the tile read is THE cost of this pass (248 tiles x 28 fire-years). The
    # data.frame route also materializes a full-tile frame before filtering.
    cs <- terra::values(tl[["candseed"]], mat = FALSE)
    k  <- which(!is.na(cs) & cs > 0)
    if (!length(k)) next
    ad <- terra::values(tl[["abs_date"]], mat = FALSE)[k]
    # a handful of pixels carry candseed>0 with a NA abs_date; step 05 dropped them too (its
    # na.rm extract spanned every band), so they belong to no object — drop them explicitly
    # rather than let a NA date propagate into a month.
    ok <- !is.na(ad)
    d  <- data.table(cell = k[ok], candseed = as.integer(cs[k][ok]), abs_date = ad[ok])
    rm(cs, ad, k)
    if (!nrow(d)) next
    tnc <- ncol(tl); te <- terra::ext(tl)
    gcol0 <- as.integer(round((te$xmin - g$x0) / g$dx))
    grow0 <- as.integer(round((g$y0 - te$ymax) / g$ady))
    d[, `:=`(row = grow0 + (((cell - 1L) %/% tnc) + 1L),
             col = gcol0 + (((cell - 1L) %% tnc) + 1L))]
    d[, cell := NULL]
    # replay step 05's dieback longitude cut (the asset/tile still carries those pixels)
    d <- d[!(candseed == 3L & (g$x0 + (col - 0.5) * g$dx) > DIEBACK_LON_CUT)]
    if (!nrow(d)) next
    d[, cell := (as.numeric(row) - 1) * g$nc + col]
    # Keep only pixels inside an ACCEPTED object, bringing the object's date for the
    # substitution. The lookup MUST be keyed this way round — `d[ct, on="cell"]` would walk all
    # ~55 M object cells once per tile (248x per fire-year); this walks only the tile's pixels.
    d[, obj_date := ct[.(d$cell), on = "cell", obj_date]]
    d <- d[!is.na(obj_date)]
    if (!nrow(d)) next
    if (DIEBACK_USE_PARENT_DATE) d[candseed == 3L, abs_date := obj_date]
    parts[[i]] <- d[, .(row, col, date = abs_date)]
    if (i %% 40L == 0L) message(sprintf("[%s] tiles %d/%d", tag, i, length(tifs)))
  }
  px <- rbindlist(parts); rm(parts)
  if (!nrow(px)) stop(sprintf("FY%d: no accepted burned pixels", fy))
  px <- unique(px, by = c("row", "col"))
  # the guard: polygon cells that carry no burned pixel (expected 0 — see header)
  message(sprintf("[%s] burned ∩ accepted = %s px;  polygon cells with no burned pixel = %s",
                  tag, format(nrow(px), big.mark = ","),
                  format(nrow(ct) - nrow(px), big.mark = ",")))

  px[, `:=`(cyear = year(as.IDate(date, origin = EPOCH)),
            month = month(as.IDate(date, origin = EPOCH)))]
  dir.create(PIX_CACHE, showWarnings = FALSE, recursive = TRUE)
  for (Y in sort(unique(px$cyear))) {
    h <- px[cyear == Y, .(row, col, month)]
    f <- file.path(PIX_CACHE, sprintf("cy%d_fy%d.rds", Y, fy))
    if (!(Y %in% CAL_YEARS)) {
      message(sprintf("[%s] calendar %d is outside the published series — %s px DROPPED",
                      tag, Y, format(nrow(h), big.mark = ",")))
      next
    }
    saveRDS(h, f, compress = FALSE)
    message(sprintf("[%s] -> %s  (%s px, months %s)", tag, basename(f),
                    format(nrow(h), big.mark = ","),
                    paste(range(h$month), collapse = "-")))
  }
  message(sprintf("[%s] pixels done in %.1f min", tag,
                  as.numeric(difftime(Sys.time(), t0, units = "mins"))))
}

# ── pass 2 — 8-connected labelling of one calendar year -> scar vectors ────────
# Plain 8-connectivity via the step-05 Rcpp union-find, streamed one window offset at a time.
# INTENTIONALLY not step 05's dilation connectivity (see header).
label8 <- function(dt, nc) {
  N <- nrow(dt)
  dt[, idx := seq_len(N)]
  setkey(dt, cell)
  uf <- uf_new(N)
  offs <- data.table(dr = c(0L, 1L, 1L, 1L), dc = c(1L, -1L, 0L, 1L))  # forward half of 3x3
  for (k in seq_len(nrow(offs))) {
    ncl <- dt$col + offs$dc[k]; ok <- ncl >= 1L & ncl <= nc
    nb  <- (as.numeric(dt$row) + offs$dr[k] - 1) * nc + ncl
    j   <- dt[.(nb), on = "cell", idx]
    keep <- ok & !is.na(j)
    if (any(keep)) uf_union(uf, dt$idx[keep], j[keep])
  }
  roots <- uf_labels(uf)
  dt[, pid := as.integer(factor(roots[idx]))]
  dt[, idx := NULL]
  dt
}

pass_scars <- function(Y) {
  t0 <- Sys.time(); tag <- sprintf("CY%d", Y)
  fs <- file.path(PIX_CACHE, sprintf("cy%d_fy%d.rds", Y, c(Y - 1L, Y)))
  have <- file.exists(fs)
  # EVERY calendar year 1999-2025 legitimately has BOTH halves: 1999 gets Jan-Apr from FY1998 and
  # May-Dec from FY1999, 2025 gets them from FY2024/FY2025, and every fire-year 1998-2025 exists.
  # So a missing half is always an error, never a valid edge case — and it would otherwise yield a
  # silently INCOMPLETE published year that passes every downstream check. Hard stop.
  # ALLOW_PARTIAL_YEAR=1 overrides, for deliberate small-subset testing only.
  if (!all(have)) {
    msg <- sprintf("CY%d: pixel cache incomplete — missing %s. Run the `pixels` pass for that fire-year first.",
                   Y, paste(basename(fs[!have]), collapse = ", "))
    if (!nzchar(Sys.getenv("ALLOW_PARTIAL_YEAR"))) stop(msg)
    message(sprintf("[%s] WARNING %s  (ALLOW_PARTIAL_YEAR set — output is NOT publishable)", tag, msg))
  }
  message(sprintf("\n══ %s scars ── from %s ══", tag, paste(basename(fs[have]), collapse = " + ")))
  px <- rbindlist(lapply(fs[have], readRDS))
  # reburn inside one calendar year is the only real conflict: the LATER month wins — what the
  # pixel looks like at year end (docs/notes/08-corrections_and_delivery.md). The two halves are otherwise disjoint.
  before <- nrow(px)
  # `unique(..., by=)` on the sorted table, NOT `.SD[1L]` by group: at ~100 M rows a per-group
  # subset is orders of magnitude slower than one pass over sorted keys.
  px <- unique(px[order(row, col, -month)], by = c("row", "col"))
  if (before > nrow(px))
    message(sprintf("[%s] reburn: %s px claimed by both fire-years — later month kept",
                    tag, format(before - nrow(px), big.mark = ",")))
  g <- global_grid()
  px[, cell := (as.numeric(row) - 1) * g$nc + col]
  message(sprintf("[%s] %s px -> labelling (8-connected)…", tag, format(nrow(px), big.mark = ",")))
  label8(px, g$nc)

  carow <- row_cell_area(g)
  px[, cell_area := carow[row]]
  # All GForce-optimizable reducers — no per-group table()/mode, which would cost minutes at
  # ~100 k groups over ~100 M rows and buys nothing (the month raster comes from GEE).
  mets <- px[, .(n_px = .N, area_ha = sum(cell_area) / 1e4, first_cell = min(cell)), by = pid]
  # deterministic, re-runnable scar_id: order by position, number 1..n (docs/08 open #5)
  setorder(mets, first_cell)
  mets[, scar_id := seq_len(.N)]
  message(sprintf("[%s] %s scars, %s ha", tag, format(nrow(mets), big.mark = ","),
                  format(round(sum(mets$area_ha)), big.mark = ",")))

  # Per-month histogram NOW, while `month` still exists — it is the number the GEE month raster is
  # cross-checked against (`07-month_of_burn.py --check`).
  hist <- px[, .(n_px = .N), by = month][order(month)]

  # Drop everything vectorize_sparse does not read BEFORE forking. mclapply children inherit the
  # parent's table copy-on-write, so trimming 28 bytes/row down to 12 is the cheapest way to keep a
  # ~100 M-pixel calendar year inside memory with several workers running.
  px[, c("cell", "cell_area", "month") := NULL]
  gc()

  message(sprintf("[%s] vectorize on %d core(s)…", tag, OBJ_CORES))
  polys <- vectorize_sparse(px, g)
  polys <- merge(polys, as.data.frame(mets[, .(pid, scar_id, area_ha, n_px)]), by = "pid")
  polys$year <- Y
  polys <- polys[, c("scar_id", "area_ha", "n_px", "year")]   # NO size class — GEE derives it

  dir.create(SCAR_DIR, showWarnings = FALSE, recursive = TRUE)
  dir.create(ZIP_DIR,  showWarnings = FALSE, recursive = TRUE)
  gpkg <- file.path(SCAR_DIR, sprintf("scars_%d.gpkg", Y))
  sf::st_write(polys, gpkg, delete_dsn = TRUE, quiet = TRUE)

  # per-year validation: compare these numbers against the GEE month-of-burn raster (`hist` was
  # taken above, before `month` was dropped for the fork)
  sm <- data.table(year = Y, n_scars = nrow(mets), n_px = nrow(px),
                   area_ha = sum(mets$area_ha),
                   min_scar_ha = min(mets$area_ha), max_scar_ha = max(mets$area_ha))
  fwrite(sm, file.path(SCAR_DIR, sprintf("scars_%d_summary.csv", Y)))
  fwrite(hist, file.path(SCAR_DIR, sprintf("scars_%d_months.csv", Y)))

  # Zipped Shapefile for the manual GEE ingest (every field name is already <= 10 chars, so
  # there is nothing for OGR to truncate — unlike the step-06 object upload, docs/06 "Upload to GEE").
  # Two traps, both hit here first: `delete_dsn = TRUE` on a path that does not exist yet makes
  # the ESRI Shapefile driver error out, and the zip path must be made ABSOLUTE *before* the
  # setwd() — normalizePath(mustWork = FALSE) leaves a not-yet-existing path relative, so the
  # zip would be written relative to the temp dir (or fail).
  tmp <- file.path(tempdir(), sprintf("scars_%d", Y))
  unlink(tmp, recursive = TRUE); dir.create(tmp, recursive = TRUE)
  sf::st_write(polys, file.path(tmp, sprintf("scars_%d.shp", Y)), quiet = TRUE)
  zipf <- file.path(normalizePath(ZIP_DIR, mustWork = TRUE), sprintf("scars_%d.zip", Y))
  if (file.exists(zipf)) unlink(zipf)
  owd <- setwd(tmp); on.exit(setwd(owd), add = TRUE)
  utils::zip(zipf, list.files(tmp, pattern = sprintf("^scars_%d\\.", Y)), flags = "-q")
  setwd(owd); unlink(tmp, recursive = TRUE)
  if (!file.exists(zipf)) stop(sprintf("CY%d: zip was not written (%s)", Y, zipf))

  message(sprintf("[%s] done: %s scars -> %s + %s (%.1f MB) in %.1f min", tag,
                  format(nrow(polys), big.mark = ","), basename(gpkg), basename(zipf),
                  file.size(zipf) / 1e6, as.numeric(difftime(Sys.time(), t0, units = "mins"))))
}

# ── driver ────────────────────────────────────────────────────────────────────
main07 <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  mode <- args[1]
  yrs  <- suppressWarnings(as.integer(args[-1]))
  yrs  <- yrs[!is.na(yrs)]
  if (!length(mode) || !mode %in% c("pixels", "scars"))
    stop("usage: 07-calendar_scars.R pixels|scars [year ...]")
  if (mode == "pixels") {
    if (!length(yrs)) yrs <- FIRST_FIRE_YEAR:LAST_FIRE_YEAR
    for (fy in yrs) pass_pixels(fy)
  } else {
    if (!length(yrs)) yrs <- CAL_YEARS
    for (Y in yrs) pass_scars(Y)
  }
}

if (sys.nframe() == 0L) main07()
