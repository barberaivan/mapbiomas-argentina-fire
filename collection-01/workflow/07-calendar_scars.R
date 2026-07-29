#!/usr/bin/env Rscript
# =============================================================================
# 07-calendar_scars.R — calendar-year burn mask -> 8-connected SCARS (id + area)
# =============================================================================
# Step 07b (docs/07 §5). The network publishes scar id / area / size-range per CALENDAR
# year, defined as "sets of spatially connected pixels within the same year". Our objects
# are FIRE-YEAR entities under a deliberately non-standard connectivity (the 1-px dilation
# of step 05), so the scars are a SEPARATE labelling pass:
#
#   * CALENDAR year, not fire-year — calendar Y = Jan-Apr Y (from FY Y-1) ⊎ May-Dec Y (FY Y).
#   * PLAIN 8-CONNECTIVITY, intentionally NOT step 05's dilation connectivity: two distinct
#     fires that touch become one scar, which is what the network's definition says.
#   * A fire that straddles 31 December IS split into two scars, one per calendar year.
#     That is the point of the per-pixel date assignment: annual, monthly and scar_size then
#     agree pixel-for-pixel (docs/08 §6.7).
#
# GEE cannot do the labelling (`connectedPixelCount` caps at 1024 px ≈ 92 ha, far below a real
# scar), which is why Brazil round-trips through Drive + Colab. We label locally instead, from
# the per-carta SNIC tiles and the step-06 object polygons we already have on disk — no
# download, no Drive.
#
# WHAT GOES IN THE VECTORS: `scar_id`, `area_ha`, `n_px`, `year`. NO size class — that is
# derived in GEE from `area_ha`, so it follows whatever ranges the platform finally registers
# (docs/08 §5.4 has the reference-vs-Workspace conflict).
#
# ONLY ACCEPTED OBJECTS CONTRIBUTE: `fire == 1 & area_ha >= MIN_FIRE_HA`. `fire` is the
# deployed call — the collected label where there is one, else the model (docs/06 §5); note
# `fire_tag == -1` means "unlabelled", NOT "not fire". Positive selection is deliberate: 36
# objects in the collection are all-dieback with a null `fire`/`date_median`, so "not
# rejected" would wrongly admit them.
#
# VERIFIED (2026-07-29) that painting/rasterizing the object polygons reproduces the object
# pixel set EXACTLY, so the mask built here is the mask GEE paints:
#   * terra::cells(country template, accepted polys) for FY2020 -> 55,008,255 cells,
#     identical to sum(n_pixels) over the same objects. Zero discrepancy over 55 M pixels.
#   * In GEE, painted == candseed-burned with 0 painted-but-not-burned on the audited ROIs.
# The `candseed > 0` intersection below is therefore a guard, not a correction — and the
# per-year validation CSV records the residual so it is never silently assumed.
#
# TWO PASSES, because each fire-year feeds TWO calendar years and reading the 248 carta tiles
# is the dominant cost — doing it once per fire-year rather than once per (calendar year,
# fire-year) halves the I/O:
#
#   pass "pixels" (per FIRE-year, 28x): tiles -> accepted burned pixels -> effective date ->
#       split into the two calendar halves -> cache <cache>/cy<Y>_fy<fy>.rds  (row, col, month)
#   pass "scars"  (per CALENDAR year, 27x): read the two halves -> merge (later month wins on
#       reburn) -> 8-connected union-find labelling -> area -> vectorize -> GPKG + zipped SHP
#
# Run from the repo ROOT:
#   Rscript collection-01/workflow/07-calendar_scars.R pixels [fire_year ...]
#   Rscript collection-01/workflow/07-calendar_scars.R scars  [cal_year ...]
#   CARTAS=SK-19-V-A,SK-19-Y-A  Rscript ... pixels 1998     # tiny smoke test
#   OBJ_CORES=<n>  parallelises the per-scar vectorize (as in step 05)
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
SNIC_DIRECT_DIR <- "collection-01/data/snic-rasters"
OBJ_DIR         <- "collection-01/data/objects-raw"
PRED_DIR        <- "collection-01/data/objects-pred"
PIX_CACHE       <- "collection-01/data/scars-pixels-cache"   # -cache = regenerable
SCAR_DIR        <- "collection-01/data/objects-scars"
ZIP_DIR         <- "collection-01/data/scars-upload-cache"   # -cache = regenerable

FIRST_FIRE_YEAR <- 1998; LAST_FIRE_YEAR <- 2025
CAL_YEARS       <- 1999:2025      # the published calendar series (docs/07)
MIN_FIRE_HA     <- 1              # minimum mapped fire, on the OBJECT (docs/07 §1)

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
# spring dieback-detection date, not a burn date (docs/07 §4.3). Measured: 881k such pixels
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
  d <- file.path(SNIC_DIRECT_DIR, as.character(fy))
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
accepted_oids <- function(fy) {
  pr <- fread(file.path(PRED_DIR, sprintf("objects_%d_pred.csv", fy)), select = c("oid", "fire"))
  mt <- fread(file.path(OBJ_DIR, sprintf("objects_%d_raster_metrics.csv", fy)),
              select = c("oid", "area_ha", "date_median", "n_pixels"))
  a <- merge(pr, mt, by = "oid")[fire == 1 & area_ha >= MIN_FIRE_HA & !is.na(date_median)]
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
  # pixel looks like at year end (docs/08 §6.4.3). The two halves are otherwise disjoint.
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
  # there is nothing for OGR to truncate — unlike the step-06 object upload, docs/06 §12).
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
