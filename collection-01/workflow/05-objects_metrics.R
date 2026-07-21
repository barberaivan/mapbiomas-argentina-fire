#!/usr/bin/env Rscript
# =============================================================================
# 05-objects_metrics.R — vectorize fire-year SNIC objects + per-object metrics
# =============================================================================
# Pipeline step 05 (R, terra/sf). Consumes the step-04 Drive COG
# (candseed + abs_date + veg_fire [+ n]) for one fire-year and turns the burned
# pixels into fire-scar OBJECTS with a metrics table, ready for the step-06
# object filter. One fire-year at a time; objects are global within a year (no
# tiling), so nearby fragments of the same scar share one id.
#
# Run from the repo ROOT (paths below are repo-relative; collection-01/data is a
# symlink into the Insync store):
#
#   Rscript collection-01/workflow/05-objects_metrics.R [test] [fire_year ...]
#     fire_year…  one or more START years (e.g. 2000 2015). Default: every
#                 snic_<year>*.tif present in collection-01/data/snic-polygons.
#     test        read the small-ROI snic_test_<year> COGs instead, writing
#                 objects_test_<year>.{gpkg,csv} (mirrors 04-snic.py --test).
#   e.g.  Rscript collection-01/workflow/05-objects_metrics.R 2000
#         Rscript collection-01/workflow/05-objects_metrics.R              # all present
#         Rscript collection-01/workflow/05-objects_metrics.R test 1998 1999
#
# Design + rationale: see docs/05-object_metrics.md. Summary of the procedure,
# per fire-year:
#   [1] Load the Drive COG (terra::vrt() if GEE auto-split it into sub-tifs).
#   [2] Assign object ids with a 1-px DILATION CONNECTIVITY HACK: grow the burned
#       mask by one 8-neighbour ring (EXCEPT out of agriculture/grassland pixels,
#       where dilation would merge distinct fields → commission error), run
#       terra::patches() on the grown mask so fragments 1 px apart share an id,
#       then DROP the halo — only the original burned pixels keep their id.
#   [3] Per-object RASTER summaries (data.table over burned cells only):
#       veg_fire abundance (per-class fractions + top-5), area, and {median,
#       mean, p2.5, p97.5, min, max} of abs_date and of n.
#   [4] Vectorize the id raster (terra::as.polygons(dissolve=TRUE) → one
#       multipolygon per id — this IS the per-id dissolve/merge).
#   [5] Join the step-[3] metrics onto the polygons as attributes.
#   [6] Add geometry SHAPE/SPARSITY metrics (ported from collection-00
#       addShapeMetrics, fuego collection-00/utils/functions.js): perimeter,
#       convexity, mbr_fill, mbr_elongation, circularity, shape_index; plus the
#       raster neighbourhood sparseness burned_around_{1,2,3} (computed in [3]).
#
# Outputs (collection-01/data/snic-polygons/):
#   objects_<fire_year>.gpkg          — polygons (one per object) + all metrics
#   objects_<fire_year>_metrics.csv   — the metrics table alone (no geometry)
#
# COG note: terra/GDAL read cloud-optimized GeoTIFFs transparently; the COG
# structure (internal tiling + overviews) only matters for partial/remote reads.
# These files are LOCAL (Insync-synced), so no vsicurl / GDAL COG config is
# needed — a plain terra::rast()/vrt() is enough.
# =============================================================================

suppressPackageStartupMessages({
  library(terra)
  library(sf)
  library(data.table)
})

# ── config ───────────────────────────────────────────────────────────────────
SNIC_DIR <- "collection-01/data/snic-polygons"   # symlink into the store

# veg_fire codes where the connectivity dilation is SUPPRESSED as a source:
# agriculture (1,2,3) + grassland_chaco (13) + grassland-inund_chaco (17). In
# these covers burned fields sit close together and bridging them inflates
# commission error, so they never grow outward (docs/05 §2). Keep in sync with
# utils/constants.py veg_fire codes.
AG_GRASS_NO_DILATE <- c(1L, 2L, 3L, 13L, 17L)

VEG_CODES   <- 1:23                 # burnable veg_fire classes (24/25 are sentinels)
BA_RADII    <- c(1L, 2L, 3L)        # burned_around neighbourhood radii (px)
EPOCH       <- "1970-01-01"         # abs_date is whole days since this
EXPECT_BANDS <- c("candseed", "abs_date", "veg_fire", "n")  # n optional; see header

# terra: lean on out-of-core processing — the country-wide 30 m grid is far too
# large to hold densely in RAM, but the burned mask is sparse, so every step
# below stays sparse (1/NA rasters, focal with na.rm, cells-only extraction).
# progress=0: keep tee'd tmux logs clean (per-year progress goes via message()).
terraOptions(progress = 0)

# ── [1] load one fire-year COG ────────────────────────────────────────────────
load_snic <- function(fy, test = FALSE) {
  # 4-digit years are never prefixes of one another, so a simple snic_<fy>* glob
  # is unambiguous. `test` reads the small-ROI snic_test_<fy> COGs instead (the
  # non-test glob's snic_%d never matches snic_test_*). GEE may split a big export
  # into several sub-tifs → mosaic them virtually with vrt().
  prefix <- if (test) "snic_test_" else "snic_"
  tifs <- list.files(SNIC_DIR, pattern = sprintf("^%s%d.*\\.tif$", prefix, fy),
                     full.names = TRUE)
  if (length(tifs) == 0L)
    stop(sprintf("no %s%d*.tif in %s (run 04-snic.py --to-drive first)", prefix, fy, SNIC_DIR))
  r <- if (length(tifs) > 1L) terra::vrt(tifs, overwrite = TRUE) else terra::rast(tifs)

  # Band names: trust the file if it already labels them; else assign by the
  # export stack order (candseed, abs_date, veg_fire[, n]). See EXPECT_BANDS.
  if (!all(names(r) %in% EXPECT_BANDS)) {
    if (!nlyr(r) %in% c(3L, 4L))
      stop(sprintf("snic_%d has %d bands; expected 3 (candseed,abs_date,veg_fire) or 4 (+n)",
                   fy, nlyr(r)))
    names(r) <- EXPECT_BANDS[seq_len(nlyr(r))]
  }
  r
}

# ── [2] object ids via the dilation connectivity hack ─────────────────────────
object_ids <- function(candseed, veg_fire) {
  burned <- candseed > 0                       # 1 / NA  (candseed is masked to burned)

  # Dilate the burned mask by one 8-neighbour ring, then MASK any halo pixel whose
  # ONLY burned neighbours are the avoided ag/grassland classes {1,2,3,13,17} —
  # bridging those would merge distinct fields and inflate commission error. A
  # halo pixel is kept iff it has ≥1 burned neighbour OUTSIDE the avoided set.
  # focal max over the 1/NA masks (na.rm=TRUE) stays sparse: 1 in the ring, NA away.
  ring     <- terra::focal(burned, w = matrix(1, 3, 3), fun = "max", na.rm = TRUE)  # burned ∪ 1-px halo
  keep_veg <- terra::ifel(burned & !(veg_fire %in% AG_GRASS_NO_DILATE), 1, NA)      # non-avoided burned
  has_keep <- terra::focal(keep_veg, w = matrix(1, 3, 3), fun = "max", na.rm = TRUE) # 1 where a non-avoided burned neighbour exists
  conn     <- terra::cover(burned, terra::mask(ring, has_keep))  # burned ∪ (halo with a non-avoided neighbour)

  # Global connected components on the grown mask (8-connectivity).
  pid_grown <- terra::patches(conn, directions = 8, zeroAsNA = FALSE,
                              filename = tempfile(fileext = ".tif"), overwrite = TRUE)

  # Drop the halo: keep ids ONLY on original burned pixels. Two scars bridged by
  # the halo keep the shared id even though the bridge pixels are now gone.
  terra::mask(pid_grown, burned, filename = tempfile(fileext = ".tif"),
              overwrite = TRUE) |> stats::setNames("pid")
}

# ── [3] per-object raster summaries ───────────────────────────────────────────
# {median, mean, p2.5, p97.5, min, max} helper for a numeric column.
qstats <- function(x) {
  q <- stats::quantile(x, c(0.025, 0.975), names = FALSE, type = 7, na.rm = TRUE)
  list(median = stats::median(x, na.rm = TRUE), mean = mean(x, na.rm = TRUE),
       p2.5 = q[1], p97.5 = q[2], min = min(x, na.rm = TRUE), max = max(x, na.rm = TRUE))
}

raster_metrics <- function(r, pid) {
  burned <- !is.na(pid)
  has_n  <- "n" %in% names(r)
  if (!has_n)
    warning("no 'n' band in the COG — n-summaries skipped. Add n to 04-snic.py ",
            "--to-drive (see docs/05 §7).", call. = FALSE)

  # burned_around_k = fraction of the (2k+1)² window that is burned, at each
  # burned pixel. Computed sparsely: focal SUM of the 1/NA burned mask (na.rm
  # treats NA as 0) ÷ window size — no country-wide densification.
  ba <- lapply(BA_RADII, function(k) {
    w <- 2L * k + 1L
    s <- terra::focal(burned * 1, w = matrix(1, w, w), fun = "sum", na.rm = TRUE)
    terra::mask(s, pid) / (w * w)
  })
  ba <- terra::rast(ba); names(ba) <- sprintf("burned_around_%d", BA_RADII)

  cell_area <- terra::mask(terra::cellSize(pid, unit = "m"), pid)  # per-cell m² (CRS-correct)

  bands <- c("veg_fire", "abs_date", if (has_n) "n")
  stk   <- c(pid, r[[bands]], cell_area, ba)
  names(stk)[names(stk) == "area"] <- "cell_area"  # cellSize() names its layer "area"

  # Pull ONLY burned cells into a data.table (na.rm drops the empty grid).
  dt <- as.data.table(terra::as.data.frame(stk, na.rm = TRUE))
  setnames(dt, "pid", "pid")

  # veg abundance: per-class fractions + top-5 (by pixel count) ------------------
  vt <- dt[, .N, by = .(pid, veg_fire)]
  vt[, frac := N / sum(N), by = pid]
  # full per-class fraction matrix (23 cols; classes absent in a patch → 0)
  fracs <- dcast(vt[veg_fire %in% VEG_CODES], pid ~ veg_fire,
                 value.var = "frac", fill = 0)
  present <- setdiff(names(fracs), "pid")
  setnames(fracs, present, sprintf("frac_c%s", present))
  for (c in sprintf("frac_c%d", VEG_CODES))                # add any never-seen class as 0
    if (!c %in% names(fracs)) fracs[, (c) := 0]
  setcolorder(fracs, c("pid", sprintf("frac_c%d", VEG_CODES)))
  # ranked top-5 (code + fraction); patches with <5 classes pad with NA
  top <- vt[order(pid, -N),
            .(top = veg_fire[seq_len(5)], topf = frac[seq_len(5)], rk = seq_len(5)),
            by = pid]
  tops <- dcast(top, pid ~ rk, value.var = c("top", "topf"))
  setnames(tops, paste0("top_",  1:5), paste0("veg_top", 1:5),        skip_absent = TRUE)
  setnames(tops, paste0("topf_", 1:5), paste0("veg_top", 1:5, "_frac"), skip_absent = TRUE)

  # numeric summaries: area + abs_date (+ n) + neighbourhood sparseness ---------
  num <- dt[, {
    d   <- qstats(abs_date)
    out <- c(list(n_pixels = .N, area_m2 = sum(cell_area)),
             setNames(d, paste0("date_", names(d))))
    if (has_n) { nn <- qstats(n); out <- c(out, setNames(nn, paste0("n_", names(nn)))) }
    for (nm in sprintf("burned_around_%d", BA_RADII)) out[[nm]] <- mean(get(nm))
    out
  }, by = pid]

  list(num = num, fracs = fracs, tops = tops)
}

# ── [4]+[5] vectorize + join ──────────────────────────────────────────────────
vectorize_join <- function(pid, mets) {
  v <- terra::as.polygons(pid, dissolve = TRUE)   # one (multi)polygon per id
  names(v) <- "pid"
  x <- sf::st_as_sf(v)
  m <- Reduce(function(a, b) merge(a, b, by = "pid", all.x = TRUE),
              list(mets$num, mets$fracs, mets$tops))
  merge(x, m, by = "pid", all.x = TRUE)
}

# ── [6] geometry shape / sparsity metrics ─────────────────────────────────────
# Ported from collection-00 addShapeMetrics (fuego collection-00/utils/functions.js).
# Area denominators use the GEOMETRY area (self-consistent with perimeter/hull/
# bbox, all geometry-derived); the canonical reported area_m2 stays the RASTER
# pixel area from step [3].
add_shape_metrics <- function(polys_sf) {
  v <- terra::vect(polys_sf)
  a  <- as.numeric(sf::st_area(polys_sf))                          # geometry area (m²)
  p  <- terra::perim(v)                                            # perimeter (m)
  ha <- as.numeric(sf::st_area(sf::st_convex_hull(polys_sf)))      # convex-hull area (m²)

  # per-feature axis-aligned bounding box (matches EE geom.bounds()), vectorized
  # via the vertex table.
  g  <- as.data.table(terra::geom(v))
  bb <- g[, .(sx = max(x) - min(x), sy = max(y) - min(y)), by = geom][order(geom)]

  polys_sf$perimeter_m   <- p
  polys_sf$convexity     <- a / ha                                 # area / convex hull
  polys_sf$mbr_fill      <- a / (bb$sx * bb$sy)                    # area / bbox area
  polys_sf$mbr_elongation <- pmax(bb$sx, bb$sy) / pmin(bb$sx, bb$sy)
  polys_sf$circularity   <- 4 * pi * a / (p^2)                     # 4πA / P²
  polys_sf$shape_index   <- p / (2 * sqrt(pi * a))                 # P / (2√πA)
  polys_sf
}

# ── driver ────────────────────────────────────────────────────────────────────
process_year <- function(fy, test = FALSE) {
  message(sprintf("── fire-year %d%s ──", fy, if (test) " [test ROI]" else ""))
  r   <- load_snic(fy, test)
  pid <- object_ids(r[["candseed"]], r[["veg_fire"]])
  mets <- raster_metrics(r, pid)
  polys <- vectorize_join(pid, mets)
  polys <- add_shape_metrics(polys)
  polys$fire_year <- fy

  # human-readable median burn date alongside the numeric (days-since-epoch) one
  polys$date_median_date <- as.Date(polys$date_median, origin = EPOCH)

  stem <- if (test) sprintf("objects_test_%d", fy) else sprintf("objects_%d", fy)
  gpkg <- file.path(SNIC_DIR, paste0(stem, ".gpkg"))
  csv  <- file.path(SNIC_DIR, paste0(stem, "_metrics.csv"))
  sf::st_write(polys, gpkg, delete_dsn = TRUE, quiet = TRUE)
  fwrite(as.data.table(sf::st_drop_geometry(polys)), csv)
  message(sprintf("   %d objects → %s", nrow(polys), gpkg))
  invisible(polys)
}

main <- function() {
  args <- commandArgs(trailingOnly = TRUE)
  test <- length(args) && args[1] == "test"       # `... 05-objects_metrics.R test [year ...]`
  if (test) args <- args[-1]
  prefix <- if (test) "snic_test_" else "snic_"
  years <- if (length(args)) as.integer(args) else {
    f <- list.files(SNIC_DIR, pattern = sprintf("^%s\\d{4}.*\\.tif$", prefix))
    sort(unique(as.integer(sub(sprintf("^%s(\\d{4}).*$", prefix), "\\1", f))))
  }
  if (!length(years)) stop("no fire-years to process (none given, none found in ", SNIC_DIR, ")")
  for (fy in years) process_year(fy, test)
}

if (sys.nframe() == 0L) main()
