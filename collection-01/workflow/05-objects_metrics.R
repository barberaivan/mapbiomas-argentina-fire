#!/usr/bin/env Rscript
# =============================================================================
# 05-objects_metrics.R — vectorize fire-year SNIC objects + per-object metrics
# =============================================================================
# Pipeline step 05 (R, terra/sf/data.table + a small Rcpp union-find). Consumes the
# step-04 SNIC product for one fire-year — EITHER the direct-download per-carta tiles
# (snic-direct/<fy>/, 7 bands incl. burned_around_{1,2,3} pre-computed in GEE; preferred,
# 04 §5b) OR the legacy Drive COG (snic-polygons/) — and turns the burned pixels into
# fire-scar OBJECTS with a metrics table, ready for the step-06 object filter. One fire-year
# at a time; objects are global within a year (no tiling), so nearby fragments of the same
# scar share one id.
#
# SCALES TO THE WHOLE COUNTRY (docs/05). The three steps that broke at 9.16 B cells were
# replaced (see docs/05 §7/§8 for the FY2000 profile that forced each change):
#   * EXTRACT burned cells PER-CARTA TILE, not as.data.frame() on the whole mosaic — the
#     latter builds 1:ncell (9.16 B) and R's cbind throws "long vectors not supported".
#   * LABEL with a UNION-FIND (utils/label_uf.cpp: parent array only, edges streamed one
#     window-offset at a time), not igraph (which OOM'd > 31 GB). The 1-px DILATION is done
#     as a WIDER-WINDOW union with a veg-class distance threshold — no halo raster (§2 below).
#   * VECTORIZE per-object in parallel (tiny local rasters), not by densifying a country-wide
#     34 GB `pid` raster for one big as.polygons().
# The old dense route survives as the `terra` method (ROI-scale fallback only).
#
# Run from the repo ROOT (paths below are repo-relative):
#   Rscript collection-01/workflow/05-objects_metrics.R [test] [terra] [fire_year ...]
#     fire_year…  one or more START years (e.g. 2000). Default: every year present.
#     test        read the small-ROI snic_test_<year> products → objects_test_<year>.
#     terra       use the dense terra::patches() labelling (ROI-scale fallback); default is
#                 the scalable union-find path.
#   OBJ_CORES=<n> parallelises the per-object vectorize (default: ~half the cores; 1 = serial).
#   e.g.  OBJ_CORES=13 Rscript collection-01/workflow/05-objects_metrics.R 2000
#
# Design + rationale: docs/05-object_metrics.md. Procedure per fire-year:
#   [1] Extract burned cells (per-carta tile) into a data.table with all bands.
#   [2] Assign object ids via the 1-px DILATION connectivity (union-find, §2).
#   [3] Per-object RASTER metrics (data.table over burned cells): veg_fire abundance
#       (fractions + top-5), area, {median,mean,p2.5,p97.5,min,max} of abs_date and n,
#       burned_around_{1,2,3}.
#   [4] Vectorize the objects (one (multi)polygon per id), parallel per-object.
#   [5] Join the [3] metrics onto the polygons.
#   [6] Geometry SHAPE/SPARSITY metrics (ported from collection-00 addShapeMetrics).
#
# Outputs (collection-01/data/snic-polygons/):
#   objects_<fire_year>.gpkg          — polygons (one per object) + all metrics
#   objects_<fire_year>_metrics.csv   — the metrics table alone (no geometry)
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
# Two input layouts (snic_tifs prefers the first):
#   snic-direct/<fy>/<carta>.tif — direct-download per-carta tiles (04 §5b): 248 cartas,
#       7 bands incl. burned_around_{1,2,3} PRE-COMPUTED in GEE as CELL COUNTS.
#   snic-polygons/snic_<fy>*.tif — legacy Drive COG: candseed+abs_date+veg_fire[+n];
#       burned_around computed locally here. (Legacy is ROI-scale only — one big COG is one
#       "tile", so it re-hits the whole-mosaic extract limit at country scale.)
SNIC_DIR        <- "collection-01/data/snic-polygons"   # legacy Drive COG (symlink into store)
SNIC_DIRECT_DIR <- "collection-01/data/snic-direct"     # direct-download per-carta tiles

# veg_fire codes where the connectivity DILATION is SUPPRESSED: agriculture (1,2,3) +
# grassland_chaco (13) + grassland-inund_chaco (17). Burned fields sit close together there
# and bridging them inflates commission error (docs/05 §2). Keep in sync with constants.py.
AG_GRASS_NO_DILATE <- c(1L, 2L, 3L, 13L, 17L)

VEG_CODES   <- 1:23                 # burnable veg_fire classes (24/25 are sentinels)
BA_RADII    <- c(1L, 2L, 3L)        # burned_around neighbourhood radii (px)
EPOCH       <- "1970-01-01"         # abs_date is whole days since this
EXPECT_BANDS        <- c("candseed", "abs_date", "veg_fire", "n")  # legacy COG; n optional
EXPECT_BANDS_DIRECT <- c("abs_date", "veg_fire", "n",             # direct-download tiles (04 §5b)
                         sprintf("burned_around_%d", BA_RADII), "candseed")
DILATE_R    <- 3L                   # 1-px dilation ≡ union within Chebyshev ≤3 (docs/05 §2)

# per-object vectorize parallelism (unix fork only; 1 elsewhere)
OBJ_CORES <- {
  n <- suppressWarnings(as.integer(Sys.getenv("OBJ_CORES", "")))
  if (is.na(n)) n <- max(1L, min(13L, parallel::detectCores() - 2L))
  if (.Platform$OS.type != "unix") 1L else max(1L, n)
}

terraOptions(progress = 0)   # keep tee'd tmux logs clean

# ── [1] locate + load one fire-year ───────────────────────────────────────────
snic_tifs <- function(fy, test = FALSE) {
  # Returns list(tifs = <paths>, layout = "direct"|"legacy"). Prefers the direct-download
  # per-carta tiles; falls back to the legacy Drive COG glob. 4-digit years never prefix
  # one another, so the globs are unambiguous; `test` reads the small-ROI variants.
  prefix <- if (test) "snic_test_" else "snic_"
  ddir   <- file.path(SNIC_DIRECT_DIR, if (test) sprintf("test_%d", fy) else as.character(fy))
  dtifs  <- if (dir.exists(ddir)) list.files(ddir, pattern = "\\.tif$", full.names = TRUE) else character(0)
  if (length(dtifs)) return(list(tifs = dtifs, layout = "direct"))
  ltifs <- list.files(SNIC_DIR, pattern = sprintf("^%s%d.*\\.tif$", prefix, fy), full.names = TRUE)
  if (!length(ltifs))
    stop(sprintf("no tiles for FY%d in %s/ or %s (run 04-snic.py --to-asset + download_snic.py, or --to-drive)",
                 fy, ddir, SNIC_DIR))
  list(tifs = ltifs, layout = "legacy")
}

load_snic <- function(fy, test = FALSE) {
  # Named whole-country mosaic (terra vrt) — used by the `terra` fallback and for grid geometry.
  s <- snic_tifs(fy, test)
  r <- if (length(s$tifs) > 1L) terra::vrt(s$tifs, overwrite = TRUE) else terra::rast(s$tifs)
  expect <- if (s$layout == "direct") EXPECT_BANDS_DIRECT else EXPECT_BANDS
  if (!all(names(r) %in% expect)) {                    # vrt() drops names → assign by stack order
    ok <- if (identical(expect, EXPECT_BANDS_DIRECT)) length(expect) else c(3L, 4L)
    if (!nlyr(r) %in% ok)
      stop(sprintf("FY%d raster has %d bands; expected %s", fy, nlyr(r), paste(ok, collapse = " or ")))
    names(r) <- expect[seq_len(nlyr(r))]
  }
  r
}

grid_of <- function(r) list(nc = ncol(r), nr = nrow(r), x0 = terra::ext(r)$xmin,
                            y0 = terra::ext(r)$ymax, dx = terra::xres(r), ady = terra::yres(r),
                            crs = terra::crs(r), lonlat = terra::is.lonlat(r))

# Per-carta burned-cell extract → data.table(all bands, row, col, cell). Each tile is read
# whole (< 2^31 cells), burned cells kept, local (row,col) mapped to the GLOBAL lattice via
# the tile's offset. Never touches the 9.16 B-cell grid at once (docs/05 §7).
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
# (docs/05 §2). The dilation ⇔ union two burned cells at Chebyshev distance d iff:
#   d ≤ 1 always;  d ≤ 2 if ≥1 endpoint is non-ag/grass;  d ≤ 3 if BOTH are non-ag/grass.
# (Exact: a non-ag/grass burned pixel "occupies" its 3×3 dilation, an ag/grass one just 1×1;
# two occupied regions 8-touch at exactly those distances. Reproduces terra dilate→label→drop
# pixel-for-pixel.) Pass dilate=FALSE for plain 8-connectivity.
label_uf <- function(dt, nc, dilate = TRUE) {
  if (!exists("uf_new", mode = "function")) Rcpp::sourceCpp(UF_CPP)
  N <- nrow(dt)
  dt[, idx := seq_len(N)]                               # node id, assigned in EXTRACT order
  ag_by_node <- dt$veg_fire %in% AG_GRASS_NO_DILATE     # node-indexed ag/grass flag
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

# terra (dense) fallback labelling — ROI-scale only. Dilate → patches() → drop halo.
object_ids <- function(candseed, veg_fire) {
  burned   <- terra::ifel(candseed > 0, 1, NA)
  ring     <- terra::focal(burned, w = matrix(1, 3, 3), fun = "max", na.rm = TRUE)
  keep_veg <- terra::ifel(burned & !(veg_fire %in% AG_GRASS_NO_DILATE), 1, NA)
  has_keep <- terra::focal(keep_veg, w = matrix(1, 3, 3), fun = "max", na.rm = TRUE)
  conn     <- terra::cover(burned, terra::mask(ring, has_keep))
  pid_grown <- terra::patches(conn, directions = 8, zeroAsNA = FALSE,
                              filename = tempfile(fileext = ".tif"), overwrite = TRUE)
  terra::mask(pid_grown, burned, filename = tempfile(fileext = ".tif"),
              overwrite = TRUE) |> stats::setNames("pid")
}

# ── [3] per-object raster summaries ───────────────────────────────────────────
qstats <- function(x) {
  x <- as.numeric(x)   # force double: 1-pixel groups else return integer min/max/median → type clash
  q <- stats::quantile(x, c(0.025, 0.975), names = FALSE, type = 7, na.rm = TRUE)
  list(median = stats::median(x, na.rm = TRUE), mean = mean(x, na.rm = TRUE),
       p2.5 = q[1], p97.5 = q[2], min = min(x, na.rm = TRUE), max = max(x, na.rm = TRUE))
}

# From a burned-cell data.table (pid, veg_fire, abs_date, [n], cell_area, burned_around_1..3)
# → list(num, fracs, tops). Used by BOTH the union-find and the terra paths.
aggregate_metrics <- function(dt, has_n) {
  vt <- dt[, .N, by = .(pid, veg_fire)]
  vt[, frac := N / sum(N), by = pid]
  fracs <- dcast(vt[veg_fire %in% VEG_CODES], pid ~ veg_fire, value.var = "frac", fill = 0)
  present <- setdiff(names(fracs), "pid")
  setnames(fracs, present, sprintf("frac_c%s", present))
  for (c in sprintf("frac_c%d", VEG_CODES)) if (!c %in% names(fracs)) fracs[, (c) := 0]
  setcolorder(fracs, c("pid", sprintf("frac_c%d", VEG_CODES)))
  top <- vt[order(pid, -N),
            .(top = veg_fire[seq_len(5)], topf = frac[seq_len(5)], rk = seq_len(5)), by = pid]
  tops <- dcast(top, pid ~ rk, value.var = c("top", "topf"))
  setnames(tops, paste0("top_",  1:5), paste0("veg_top", 1:5),          skip_absent = TRUE)
  setnames(tops, paste0("topf_", 1:5), paste0("veg_top", 1:5, "_frac"), skip_absent = TRUE)
  num <- dt[, {
    d   <- qstats(abs_date)
    out <- c(list(n_pixels = .N, area_m2 = sum(cell_area)), setNames(d, paste0("date_", names(d))))
    if (has_n) { nn <- qstats(n); out <- c(out, setNames(nn, paste0("n_", names(nn)))) }
    for (nm in sprintf("burned_around_%d", BA_RADII)) out[[nm]] <- mean(get(nm))
    out
  }, by = pid]
  list(num = num, fracs = fracs, tops = tops)
}

# burned_around_k = fraction of the (2k+1)² window burned, per burned cell (legacy COG: no
# pre-computed band, compute it here; O(burned)).
.in_set <- function(x, bs) { p <- findInterval(x, bs); p >= 1L & bs[pmax(p, 1L)] == x }
add_burned_around <- function(dt, nc) {
  bs   <- sort(dt$cell)
  K    <- max(BA_RADII)
  offs <- CJ(dr = -K:K, dc = -K:K)[, cheb := pmax(abs(dr), abs(dc))]
  cnt  <- matrix(0L, nrow(dt), length(BA_RADII))
  for (i in seq_len(nrow(offs))) {
    ncl <- dt$col + offs$dc[i]; ok <- ncl >= 1 & ncl <= nc
    nb  <- (dt$row + offs$dr[i] - 1) * nc + ncl
    hit <- ok & .in_set(nb, bs)
    for (ri in seq_along(BA_RADII)) if (offs$cheb[i] <= BA_RADII[ri]) cnt[hit, ri] <- cnt[hit, ri] + 1L
  }
  for (ri in seq_along(BA_RADII))
    dt[, (sprintf("burned_around_%d", BA_RADII[ri])) := cnt[, ri] / (2L * BA_RADII[ri] + 1L)^2]
  invisible(dt)
}

# SCALABLE (union-find) path: returns list(geom = dt[row,col,pid], mets). Never builds a dense
# pid raster — vectorize_sparse() polygonizes per object from `geom`.
objects_sparse <- function(tifs, r) {
  dt <- extract_burned(tifs, r)
  if (!nrow(dt)) stop("no burned pixels in raster")
  nc     <- ncol(r)
  has_n  <- "n" %in% names(dt)
  has_ba <- all(sprintf("burned_around_%d", BA_RADII) %in% names(dt))
  if (!has_n) warning("no 'n' band — n-summaries skipped (04 §5).", call. = FALSE)

  # per-cell area: for a lon/lat grid it depends only on the ROW (latitude) → cellSize on a
  # 1-column strip (O(nrow)) mapped by row; identical to a full cellSize(), no full-grid scan.
  if (terra::is.lonlat(r)) {
    e <- terra::ext(r)
    strip <- terra::rast(nrows = nrow(r), ncols = 1L, crs = terra::crs(r),
                         xmin = e$xmin, xmax = e$xmin + terra::xres(r), ymin = e$ymin, ymax = e$ymax)
    carow <- terra::values(terra::cellSize(strip, unit = "m"))[, 1]
    dt[, cell_area := carow[row]]
  } else dt[, cell_area := terra::xres(r) * terra::yres(r)]

  if (has_ba) {                                          # direct-download: counts → window fraction
    for (k in BA_RADII) dt[, (sprintf("burned_around_%d", k)) :=
                            get(sprintf("burned_around_%d", k)) / (2L * k + 1L)^2]
  } else add_burned_around(dt, nc)                       # legacy: compute the fraction here

  label_uf(dt, nc, dilate = TRUE)                        # → pid (dilation-window union-find)
  list(geom = dt[, .(row, col, pid)], mets = aggregate_metrics(dt, has_n))
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

# Parallel per-object polygonize (docs/05 §7b Path B). Workers return terra::wrap()ped chunks
# (serializable across fork); master unwraps + rbinds. ncores=1 → serial.
vectorize_sparse <- function(geom, g, ncores = OBJ_CORES) {
  setkey(geom, pid)
  pids <- sort(unique(geom$pid))
  chunks <- if (ncores <= 1L) list(pids)
            else split(pids, cut(seq_along(pids), ncores, labels = FALSE))
  worker <- function(ch) terra::wrap(do.call(rbind, lapply(ch, function(pd) .one_object(geom[.(pd)], g))))
  res <- if (ncores > 1L) parallel::mclapply(chunks, worker, mc.cores = ncores, mc.preschedule = FALSE)
         else lapply(chunks, worker)
  bad <- vapply(res, function(x) inherits(x, "try-error") || is.null(x), logical(1))
  if (any(bad)) stop("vectorize worker(s) failed: ", paste(which(bad), collapse = ","))
  v <- do.call(rbind, lapply(res, terra::unwrap))
  sf::st_as_sf(v)
}

# ── [5] join metrics ──────────────────────────────────────────────────────────
join_metrics <- function(polys_sf, mets) {
  m <- Reduce(function(a, b) merge(a, b, by = "pid", all.x = TRUE),
              list(mets$num, mets$fracs, mets$tops))
  merge(polys_sf, m, by = "pid", all.x = TRUE)
}

# terra (dense) fallback: metrics from a patches()-labelled `pid` raster, then as.polygons.
raster_metrics <- function(r, pid) {
  burned <- terra::ifel(is.na(pid), NA, 1)
  has_n  <- "n" %in% names(r)
  has_ba <- all(sprintf("burned_around_%d", BA_RADII) %in% names(r))
  if (!has_n) warning("no 'n' band in the COG — n-summaries skipped (04 §5).", call. = FALSE)
  if (has_ba) {
    ba <- terra::mask(r[[sprintf("burned_around_%d", BA_RADII)]], pid)
    for (i in seq_along(BA_RADII)) ba[[i]] <- ba[[i]] / (2L * BA_RADII[i] + 1L)^2
  } else {
    ba <- terra::rast(lapply(BA_RADII, function(k) {
      w <- 2L * k + 1L
      terra::mask(terra::focal(burned * 1, matrix(1, w, w), "sum", na.rm = TRUE), pid) / (w * w)
    }))
  }
  names(ba) <- sprintf("burned_around_%d", BA_RADII)
  cell_area <- terra::mask(terra::cellSize(pid, unit = "m"), pid)
  bands <- c("veg_fire", "abs_date", if (has_n) "n")
  stk   <- c(pid, r[[bands]], cell_area, ba)
  names(stk)[names(stk) == "area"] <- "cell_area"
  dt <- as.data.table(terra::as.data.frame(stk, na.rm = TRUE))
  aggregate_metrics(dt, has_n)
}
vectorize_join <- function(pid, mets) {                  # terra path: dense as.polygons + join
  v <- terra::as.polygons(pid, dissolve = TRUE); names(v) <- "pid"
  join_metrics(sf::st_as_sf(v), mets)
}

# ── [6] geometry shape / sparsity metrics ─────────────────────────────────────
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
process_year <- function(fy, test = FALSE, method = "sparse") {
  message(sprintf("── fire-year %d%s [%s, %d core(s)] ──", fy, if (test) " test-ROI" else "",
                  method, if (method == "sparse") OBJ_CORES else 1L))
  s <- snic_tifs(fy, test); r <- load_snic(fy, test)
  if (method == "sparse") {                       # union-find + per-object vectorize (default)
    os    <- objects_sparse(s$tifs, r)
    polys <- join_metrics(vectorize_sparse(os$geom, grid_of(r)), os$mets)
  } else {                                        # terra patches() dense fallback (ROI only)
    pid   <- object_ids(r[["candseed"]], r[["veg_fire"]])
    polys <- vectorize_join(pid, raster_metrics(r, pid))
  }
  polys <- add_shape_metrics(polys)
  polys$fire_year <- fy
  # `pid` is unique only WITHIN a year → globally-unique oid = "<fy>_<pid>".
  polys$oid <- sprintf("%d_%d", fy, polys$pid)
  polys <- polys[, c("oid", setdiff(names(polys), "oid"))]
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
  args   <- commandArgs(trailingOnly = TRUE)
  test   <- "test"  %in% args
  method <- if ("terra" %in% args) "terra" else "sparse"
  args   <- setdiff(args, c("test", "terra"))
  prefix <- if (test) "snic_test_" else "snic_"
  years <- if (length(args)) as.integer(args) else {
    dpat   <- if (test) "^test_(\\d{4})$" else "^(\\d{4})$"
    dnames <- if (dir.exists(SNIC_DIRECT_DIR)) list.files(SNIC_DIRECT_DIR, pattern = dpat) else character(0)
    dyears <- as.integer(sub(dpat, "\\1", dnames))
    f      <- list.files(SNIC_DIR, pattern = sprintf("^%s\\d{4}.*\\.tif$", prefix))
    lyears <- as.integer(sub(sprintf("^%s(\\d{4}).*$", prefix), "\\1", f))
    sort(unique(c(dyears, lyears)))
  }
  if (!length(years)) stop("no fire-years to process (none given; none found in ",
                           SNIC_DIRECT_DIR, "/ or ", SNIC_DIR, ")")
  for (fy in years) process_year(fy, test, method)
}

if (sys.nframe() == 0L) main()
