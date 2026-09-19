#!/usr/bin/env Rscript
# =============================================================================
# 05-objects_metrics.R — vectorize fire-year SNIC objects + per-object metrics
# =============================================================================
# Pipeline step 05 (R, terra/sf/data.table + a small Rcpp union-find). Consumes the
# step-04 SNIC per-carta tiles for one fire-year and turns the burned pixels into fire
# OBJECTS with a metrics table, ready for the step-06 classifier. One fire-year at a
# time; objects are global within a year (no tiling), so nearby fragments of the same
# scar share one id.
#
# Run from the repo ROOT (paths below are repo-relative):
#   Rscript collection-01/workflow/05-objects_metrics.R [test] [fire_year ...]
#     fire_year...  one or more START years (e.g. 2000). Default: every year present.
#     test        read the small-ROI snic_test_<year> products -> objects_test_<year>.
#   OBJ_CORES=<n> parallelises the per-object vectorize (default: ~half the cores; 1 = serial).
#   e.g.  OBJ_CORES=13 Rscript collection-01/workflow/05-objects_metrics.R 2000
#
#   # all years overnight, one Rscript per year, resumable — ABSOLUTE path, in tmux:
#   collection-01/scripts/run_05_years.sh
#
# Design: docs/05-object_metrics.md "How it works" — the per-carta extract, the
# union-find labelling with dilation as a wider union window, the per-object vectorize
# and the metrics. What broke at 9.16 B cells and why each of those three replaced
# something simpler: docs/notes/05-whole_country_redesign.md.
#
# Outputs (collection-01/data/objects-raw/):
#   objects_<fire_year>.gpkg                — polygons (one per object) + `oid` only (no metrics)
#   objects_<fire_year>_raster_metrics.csv  — raster metrics, keyed by oid
#   objects_<fire_year>_shape_metrics.csv   — geometry/shape metrics, keyed by oid
# =============================================================================

suppressPackageStartupMessages({
  library(terra)
  library(sf)
  library(data.table)
  library(Rcpp)        # compiles utils/label_uf.cpp (union-find labelling)
  library(parallel)    # per-object vectorize fan-out (unix fork)
})

# ── locate self + the Rcpp union-find source ──────────────────────────────────
.this_file <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE))
HERE   <- if (length(.this_file)) dirname(normalizePath(.this_file)) else getwd()
UF_CPP <- file.path(HERE, "..", "utils", "label_uf.cpp")

# ── config ───────────────────────────────────────────────────────────────────
# Input: snic-rasters/<fy>/<carta>.tif — the step-04 per-carta tiles (docs/04 "The R-facing bands and the download"): 248 cartas,
# 7 bands incl. burned_around_{1,2,3} PRE-COMPUTED in GEE as CELL COUNTS.
SNIC_DIR <- "collection-01/data/snic-rasters"   # input: per-carta tiles (symlink into store)
OUT_DIR  <- "collection-01/data/objects-raw"    # output: GPKG + the two metric CSVs

# veg_fire codes that get NO enlarged connectivity context (8-connectivity only): agriculture
# (1,2,3) + grasslands ba/chaco/pampa/inund (12,13,15,17) + pastures ba/chaco (18,19). Burned
# fields/paddocks sit close together and bridging them inflates commission error (docs/05 "Label").
# candseed==3 dieback pixels ALSO get no enlarged context (added in label_uf). Keep in sync w/ docs.
NO_DILATE_VEG <- c(1L, 2L, 3L, 12L, 13L, 15L, 17L, 18L, 19L)

# Patagonia steppe dieback cut (docs/05 "Extract"): drop candseed==3 pixels EAST of this longitude.
# SNIC pads dieback only west of -70.3 (docs/04 "Patagonia dieback padding"); this tightens the western limit to -70.6.
DIEBACK_LON_CUT <- -70.6

VEG_CODES   <- 1:23                 # burnable veg_fire classes (24/25 are sentinels)
BA_RADII    <- c(1L, 2L, 3L)        # burned_around neighbourhood radii (px)
EPOCH       <- "1970-01-01"         # abs_date is whole days since this
EXPECT_BANDS <- c("abs_date", "veg_fire", "n",                    # per-carta tiles (docs/04 "The R-facing bands")
                  sprintf("burned_around_%d", BA_RADII), "candseed")
DILATE_R    <- 3L                   # 1-px dilation ≡ union within Chebyshev ≤3 (docs/05 "Label")

# per-object vectorize parallelism (unix fork only; 1 elsewhere)
OBJ_CORES <- {
  n <- suppressWarnings(as.integer(Sys.getenv("OBJ_CORES", "")))
  if (is.na(n)) n <- max(1L, min(13L, parallel::detectCores() - 2L))
  if (.Platform$OS.type != "unix") 1L else max(1L, n)
}

terraOptions(progress = 0)   # keep tee'd tmux logs clean

# ── [1] locate + load one fire-year ───────────────────────────────────────────
snic_tifs <- function(fy, test = FALSE) {
  # Returns the per-carta tile paths for one fire-year; `test` reads the small-ROI variants.
  ddir  <- file.path(SNIC_DIR, if (test) sprintf("test_%d", fy) else as.character(fy))
  tifs  <- if (dir.exists(ddir)) list.files(ddir, pattern = "\\.tif$", full.names = TRUE) else character(0)
  if (!length(tifs))
    stop(sprintf("no tiles for FY%d in %s/ (run 04-snic.py --to-asset + download_snic.py)",
                 fy, ddir))
  tifs
}

load_snic <- function(fy, test = FALSE) {
  # Named whole-country mosaic (terra vrt) — grid geometry + band naming for the extract.
  tifs <- snic_tifs(fy, test)
  r <- if (length(tifs) > 1L) terra::vrt(tifs, overwrite = TRUE) else terra::rast(tifs)
  if (!all(names(r) %in% EXPECT_BANDS)) {              # vrt() drops names → assign by stack order
    if (!nlyr(r) %in% length(EXPECT_BANDS))
      stop(sprintf("FY%d raster has %d bands; expected %d", fy, nlyr(r), length(EXPECT_BANDS)))
    names(r) <- EXPECT_BANDS
  }
  r
}

grid_of <- function(r) list(nc = ncol(r), nr = nrow(r), x0 = terra::ext(r)$xmin,
                            y0 = terra::ext(r)$ymax, dx = terra::xres(r), ady = terra::yres(r),
                            crs = terra::crs(r), lonlat = terra::is.lonlat(r))

# Per-carta burned-cell extract → data.table(all bands, row, col, cell). Each tile is read
# whole (< 2^31 cells), burned cells kept, local (row,col) mapped to the GLOBAL lattice via
# the tile's offset. Never touches the 9.16 B-cell grid at once (docs/notes/05-whole_country_redesign.md).
extract_burned <- function(tifs, r) {
  g <- grid_of(r); expect <- names(r)
  parts <- lapply(tifs, function(tf) {
    tl <- terra::rast(tf)
    if (!all(expect %in% names(tl))) names(tl) <- expect[seq_len(nlyr(tl))]
    d  <- as.data.table(terra::as.data.frame(tl, cells = TRUE, na.rm = TRUE))[candseed > 0]
    if (!nrow(d)) return(NULL)
    tnc <- ncol(tl); te <- terra::ext(tl)
    gcol0 <- as.integer(round((te$xmin - g$x0) / g$dx))   # 0-based col offset of tile in mosaic
    grow0 <- as.integer(round((g$y0 - te$ymax) / g$ady))  # 0-based row offset
    d[, `:=`(row = grow0 + (((cell - 1L) %/% tnc) + 1L),
             col = gcol0 + (((cell - 1L) %% tnc) + 1L))]
    d[, cell := NULL]; d
  })
  dt <- rbindlist(parts, use.names = TRUE)
  if (!nrow(dt)) return(dt)
  dt <- unique(dt, by = c("row", "col"))                # guard carta seams (clipped disjoint anyway)
  # Patagonia steppe dieback cut (docs/05 "Extract"): drop candseed==3 east of DIEBACK_LON_CUT.
  dt <- dt[!(candseed == 3L & (g$x0 + (col - 0.5) * g$dx) > DIEBACK_LON_CUT)]
  if (!nrow(dt)) return(dt)
  dt[, cell := (as.numeric(row) - 1) * g$nc + col]      # global linear cell (double; > 2^31 ok)
  dt[]
}

# ── [2] object ids ────────────────────────────────────────────────────────────
# Forward-half offsets of a (2R+1)² window: each undirected pair listed once (dr>0, or dr==0&dc>0).
make_forward_offsets <- function(R) {
  g <- CJ(dr = -R:R, dc = -R:R)[!(dr == 0L & dc == 0L)][dr > 0L | (dr == 0L & dc > 0L)]
  g[, cheb := pmax(abs(dr), abs(dc))][order(cheb)]
}

# Union-find labelling with the 1-px-DILATION connectivity, WITHOUT materializing a halo
# (docs/05 "Label"). The dilation ⇔ union two burned cells at Chebyshev distance d iff:
#   d ≤ 1 always;  d ≤ 2 if ≥1 endpoint is non-ag/grass;  d ≤ 3 if BOTH are non-ag/grass.
# (Exact: a non-ag/grass burned pixel "occupies" its 3×3 dilation, an ag/grass one just 1×1;
# two occupied regions 8-touch at exactly those distances. Reproduces terra dilate→label→drop
# pixel-for-pixel.) Pass dilate=FALSE for plain 8-connectivity.
label_uf <- function(dt, nc, dilate = TRUE) {
  if (!exists("uf_new", mode = "function")) Rcpp::sourceCpp(UF_CPP)
  N <- nrow(dt)
  dt[, idx := seq_len(N)]                               # node id, assigned in EXTRACT order
  # per-node "no enlarged context" flag: ag/grass/pasture veg OR a candseed==3 dieback pixel (docs/05 "Label — union-find, with dilation as a wider window")
  ag_by_node <- (dt$veg_fire %in% NO_DILATE_VEG) | (dt$candseed == 3L)
  if (is.null(dt[["cell"]])) dt[, cell := (as.numeric(row) - 1) * nc + col]
  setkey(dt, cell)
  a_ag <- ag_by_node[dt$idx]                            # ag flag aligned to keyed row order
  uf   <- uf_new(N)
  offs <- make_forward_offsets(if (dilate) DILATE_R else 1L)
  for (k in seq_len(nrow(offs))) {
    dr <- offs$dr[k]; dc <- offs$dc[k]; d <- offs$cheb[k]
    ncl  <- dt$col + dc; ok <- ncl >= 1L & ncl <= nc
    nb   <- (as.numeric(dt$row) + dr - 1) * nc + ncl
    j    <- dt[.(nb), on = "cell", idx]                 # neighbour node id, NA if not burned
    keep <- ok & !is.na(j)
    if (d >= 2L) {                                      # veg-class distance threshold
      b_ag <- ag_by_node[j]
      keep <- if (d == 2L) keep & !(a_ag & b_ag) else keep & !a_ag & !b_ag
      keep[is.na(keep)] <- FALSE
    }
    if (any(keep)) uf_union(uf, dt$idx[keep], j[keep])
  }
  roots <- uf_labels(uf)
  dt[, pid := as.integer(factor(roots[idx]))]           # compact roots → 1..n_pids, aligned to rows
  dt[, idx := NULL]
  dt
}


# ── [3] per-object raster summaries ───────────────────────────────────────────
# Mode of an integer vector (ties → smallest). Cheap per-object; not data.table-GForce.
mode_int <- function(x) { u <- unique(x); u[which.max(tabulate(match(x, u)))] }

# From a burned-cell data.table (pid, candseed, veg_fire, abs_date, [n], cell_area,
# burned_around_1..3) → ONE metrics data.table keyed by pid (docs/05 "Metrics"). Reducers are
# data.table-GForce-optimizable (mean/median/min/max/sum/.N) except the calendar-year mode, kept in
# its own tiny group-by. Date/seed/year stats EXCLUDE candseed==3 dieback pixels (docs/05 "Metrics — raster-native, then geometry"). Used by
# BOTH the union-find and the terra paths.
aggregate_metrics <- function(dt, has_n) {
  dt[, is_seed := as.integer(candseed == 2L)]
  dt[, cyear   := data.table::year(as.IDate(abs_date, origin = EPOCH))]  # per-pixel calendar year
  ba_cols <- sprintf("burned_around_%d", BA_RADII)

  # (a) whole-object aggregates over ALL burned pixels (GForce)
  num <- dt[, .(n_pixels = .N, area_ha = sum(cell_area) / 1e4), by = pid]
  ba  <- dt[, lapply(.SD, mean), by = pid, .SDcols = ba_cols]
  # (b) focal-only aggregates (drop candseed==3 dieback): seed share + date summary (GForce), then
  #     the calendar-year mode in its own group-by (non-GForce, but cheap).
  dtf <- dt[candseed != 3L]
  foc <- dtf[, .(seed_mean = mean(is_seed), date_median = as.numeric(median(abs_date)),
                 date_min = min(abs_date), date_max = max(abs_date)), by = pid]
  yr  <- dtf[, .(year_calendar = mode_int(cyear)), by = pid]
  parts <- list(num, ba, foc, yr)
  if (has_n) parts <- c(parts, list(dt[, .(n_mean = mean(n)), by = pid]))
  num <- Reduce(function(a, b) merge(a, b, by = "pid", all = TRUE), parts)
  num[, date_median_date := as.IDate(round(date_median), origin = EPOCH)]

  # veg abundance — per-class fractions frac_c1..c23 (NO ranked top-5), over ALL pixels
  vt <- dt[, .N, by = .(pid, veg_fire)]
  vt[, frac := N / sum(N), by = pid]
  fracs <- dcast(vt[veg_fire %in% VEG_CODES], pid ~ veg_fire, value.var = "frac", fill = 0)
  present <- setdiff(names(fracs), "pid")
  setnames(fracs, present, sprintf("frac_c%s", present))
  for (c in sprintf("frac_c%d", VEG_CODES)) if (!c %in% names(fracs)) fracs[, (c) := 0]
  setcolorder(fracs, c("pid", sprintf("frac_c%d", VEG_CODES)))

  merge(num, fracs, by = "pid", all.x = TRUE)[]
}

# SCALABLE (union-find) path: returns list(geom = dt[row,col,pid], mets). Never builds a dense
# pid raster — vectorize_sparse() polygonizes per object from `geom`.
objects_sparse <- function(tifs, r, tag = "") {
  message(sprintf("[%s] extract: reading %d carta tile(s)…", tag, length(tifs)))
  dt <- extract_burned(tifs, r)
  if (!nrow(dt)) stop("no burned pixels in raster")
  message(sprintf("[%s] extract: %s burned cells", tag, format(nrow(dt), big.mark = ",")))
  nc    <- ncol(r)
  has_n <- "n" %in% names(dt)
  if (!has_n) warning("no 'n' band — n-summaries skipped (docs/04 \"The R-facing bands\").", call. = FALSE)

  # per-cell area: for a lon/lat grid it depends only on the ROW (latitude) → cellSize on a
  # 1-column strip (O(nrow)) mapped by row; identical to a full cellSize(), no full-grid scan.
  if (terra::is.lonlat(r)) {
    e <- terra::ext(r)
    strip <- terra::rast(nrows = nrow(r), ncols = 1L, crs = terra::crs(r),
                         xmin = e$xmin, xmax = e$xmin + terra::xres(r), ymin = e$ymin, ymax = e$ymax)
    carow <- terra::values(terra::cellSize(strip, unit = "m"))[, 1]
    dt[, cell_area := carow[row]]
  } else dt[, cell_area := terra::xres(r) * terra::yres(r)]

  # burned_around_k arrives from GEE as a CELL COUNT → window fraction
  for (k in BA_RADII) dt[, (sprintf("burned_around_%d", k)) :=
                           get(sprintf("burned_around_%d", k)) / (2L * k + 1L)^2]

  message(sprintf("[%s] labelling (union-find + dilation)…", tag))
  label_uf(dt, nc, dilate = TRUE)                        # → pid (dilation-window union-find)
  message(sprintf("[%s] raster metrics…", tag))
  mets <- aggregate_metrics(dt, has_n)                   # mutates dt (is_seed/cyear) — before geom copy
  list(geom = dt[, .(row, col, pid)], mets = mets)
}

# ── [4] vectorize ─────────────────────────────────────────────────────────────
# One (multi)polygon per pid from a tiny local-bbox raster holding ALL of that pid's cells
# (connected or not → dissolve gives a single multipolygon, preserving the dilation bridge).
.one_object <- function(cc, g) {
  rmin <- min(cc$row); rmax <- max(cc$row); cmin <- min(cc$col); cmax <- max(cc$col)
  h <- rmax - rmin + 1L; w <- cmax - cmin + 1L
  rr <- terra::rast(nrows = h, ncols = w, crs = g$crs,
                    xmin = g$x0 + (cmin - 1) * g$dx, xmax = g$x0 + cmax * g$dx,
                    ymin = g$y0 - rmax * g$ady,      ymax = g$y0 - (rmin - 1) * g$ady)
  v <- rep(NA_integer_, as.numeric(h) * w)
  v[(cc$row - rmin) * w + (cc$col - cmin) + 1L] <- 1L
  terra::values(rr) <- v
  p <- terra::as.polygons(rr, dissolve = TRUE); p$pid <- cc$pid[1]; p
}

# Parallel per-object polygonize (docs/notes/05-whole_country_redesign.md, Path B). Workers return terra::wrap()ped chunks
# (serializable across fork); master unwraps + rbinds. ncores=1 → serial.
vectorize_sparse <- function(geom, g, ncores = OBJ_CORES) {
  setkey(geom, pid)
  pids <- sort(unique(geom$pid))
  chunks <- if (ncores <= 1L) list(pids)
            else split(pids, cut(seq_along(pids), ncores, labels = FALSE))
  # terra::vect(<list of SpatVectors>) row-binds them — NOT do.call(rbind, .): a fork-unwrapped
  # SpatVector misdispatches rbind's S4 method to `merge` ("argument 'x' is missing"), killing the
  # whole run at the final merge. terra::vect(list) (and Reduce(rbind,.)) are immune; vect is the idiom.
  worker <- function(ch) terra::wrap(terra::vect(lapply(ch, function(pd) .one_object(geom[.(pd)], g))))
  res <- if (ncores > 1L) parallel::mclapply(chunks, worker, mc.cores = ncores, mc.preschedule = FALSE)
         else lapply(chunks, worker)
  bad <- vapply(res, function(x) inherits(x, "try-error") || is.null(x), logical(1))
  if (any(bad)) stop("vectorize worker(s) failed: ", paste(which(bad), collapse = ","))
  v <- terra::vect(lapply(res, terra::unwrap))
  sf::st_as_sf(v)
}

# ── [5] geometry shape / sparsity metrics ─────────────────────────────────────
# Ported from collection-00 addShapeMetrics (fuego collection-00/utils/functions.js).
add_shape_metrics <- function(polys_sf) {
  v  <- terra::vect(polys_sf)
  a  <- as.numeric(sf::st_area(polys_sf))                          # geometry area (m²)
  p  <- terra::perim(v)                                            # perimeter (m)
  ha <- as.numeric(sf::st_area(sf::st_convex_hull(polys_sf)))      # convex-hull area (m²)
  g  <- as.data.table(terra::geom(v))
  bb <- g[, .(dx = max(x) - min(x), dy = max(y) - min(y),
              latc = (max(y) + min(y)) / 2), by = geom][order(geom)]
  if (terra::is.lonlat(v)) {                                       # bbox spans in degrees → metres
    sx <- bb$dx * 111320 * cos(bb$latc * pi / 180)
    sy <- bb$dy * 110574
  } else { sx <- bb$dx; sy <- bb$dy }
  polys_sf$perimeter_m    <- p
  polys_sf$convexity      <- a / ha
  polys_sf$mbr_fill       <- a / (sx * sy)
  polys_sf$mbr_elongation <- pmax(sx, sy) / pmin(sx, sy)
  polys_sf$circularity    <- 4 * pi * a / (p^2)
  polys_sf$shape_index    <- p / (2 * sqrt(pi * a))
  polys_sf
}

# ── driver ────────────────────────────────────────────────────────────────────
process_year <- function(fy, test = FALSE) {
  t0  <- Sys.time()
  tag <- sprintf("FY%d%s", fy, if (test) "-test" else "")
  message(sprintf("\n══ %s ── start [%d core(s)] ══", tag, OBJ_CORES))
  tifs <- snic_tifs(fy, test); r <- load_snic(fy, test)

  os          <- objects_sparse(tifs, r, tag)
  raster_mets <- os$mets
  message(sprintf("[%s] vectorize: %d objects across %d core(s)…",
                  tag, length(unique(os$geom$pid)), OBJ_CORES))
  polys       <- vectorize_sparse(os$geom, grid_of(r))

  message(sprintf("[%s] shape metrics…", tag))
  polys <- add_shape_metrics(polys)
  # `pid` is unique only WITHIN a year → globally-unique oid = "<fy>_<pid>" (the join key).
  polys$oid <- sprintf("%d_%d", fy, polys$pid)
  raster_mets[, oid := sprintf("%d_%d", fy, pid)]

  # split outputs (docs/05 "Inputs → Outputs"): GPKG (oid + geometry ONLY) + two metric CSVs, all keyed by oid.
  shape_cols <- c("oid", "perimeter_m", "convexity", "mbr_fill", "mbr_elongation",
                  "circularity", "shape_index")
  shape_mets <- as.data.table(sf::st_drop_geometry(polys))[, ..shape_cols]
  raster_out <- raster_mets[, c("oid", setdiff(names(raster_mets), c("oid", "pid"))), with = FALSE]

  stem <- if (test) sprintf("objects_test_%d", fy) else sprintf("objects_%d", fy)
  gpkg <- file.path(OUT_DIR, paste0(stem, ".gpkg"))
  rcsv <- file.path(OUT_DIR, paste0(stem, "_raster_metrics.csv"))
  scsv <- file.path(OUT_DIR, paste0(stem, "_shape_metrics.csv"))
  message(sprintf("[%s] writing GPKG + raster/shape CSVs…", tag))
  sf::st_write(polys[, "oid"], gpkg, delete_dsn = TRUE, quiet = TRUE)
  fwrite(raster_out, rcsv)
  fwrite(shape_mets, scsv)
  message(sprintf("[%s] done: %d objects → %s (+ raster/shape CSVs) in %.1f min",
                  tag, nrow(polys), basename(gpkg),
                  as.numeric(difftime(Sys.time(), t0, units = "mins"))))
  invisible(polys)
}

main <- function() {
  args   <- commandArgs(trailingOnly = TRUE)
  test   <- "test"  %in% args
  args   <- setdiff(args, "test")
  years <- if (length(args)) as.integer(args) else {
    dpat   <- if (test) "^test_(\\d{4})$" else "^(\\d{4})$"
    dnames <- if (dir.exists(SNIC_DIR)) list.files(SNIC_DIR, pattern = dpat) else character(0)
    sort(as.integer(sub(dpat, "\\1", dnames)))
  }
  if (!length(years)) stop("no fire-years to process (none given; none found in ", SNIC_DIR, "/)")
  for (fy in years) process_year(fy, test)
}

if (sys.nframe() == 0L) main()
