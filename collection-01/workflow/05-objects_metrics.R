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
#   Rscript collection-01/workflow/05-objects_metrics.R [test] [terra] [fire_year ...]
#     fire_year…  one or more START years (e.g. 2000 2015). Default: every
#                 snic_<year>*.tif present in collection-01/data/snic-polygons.
#     test        read the small-ROI snic_test_<year> COGs instead, writing
#                 objects_test_<year>.{gpkg,csv} (mirrors 04-snic.py --test).
#     terra       use the terra patches() labelling (dense, O(all cells)); default
#                 is the SPARSE igraph path (O(burned cells), the fast route).
#   e.g.  Rscript collection-01/workflow/05-objects_metrics.R 2000
#         Rscript collection-01/workflow/05-objects_metrics.R              # all present
#         Rscript collection-01/workflow/05-objects_metrics.R test 1998 1999
#         Rscript collection-01/workflow/05-objects_metrics.R terra 2000  # dense fallback
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
  library(igraph)     # sparse connected-components labelling (default method)
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
  # 1 / NA mask. NB the COG fills unburned pixels with 0 (not NoData), so we must
  # collapse BOTH 0 and NA to NA — a bare `candseed > 0` would leave a dense 0/1
  # grid and patches() would swallow the whole background as one object.
  burned <- terra::ifel(candseed > 0, 1, NA)

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
  x <- as.numeric(x)   # force double: else 1-pixel groups return integer min/max/median
                       # and data.table rejects the per-group type mismatch.
  q <- stats::quantile(x, c(0.025, 0.975), names = FALSE, type = 7, na.rm = TRUE)
  list(median = stats::median(x, na.rm = TRUE), mean = mean(x, na.rm = TRUE),
       p2.5 = q[1], p97.5 = q[2], min = min(x, na.rm = TRUE), max = max(x, na.rm = TRUE))
}

# Shared aggregator: from a burned-cell data.table with columns
# pid, veg_fire, abs_date, [n], cell_area, burned_around_1..3 → list(num,fracs,tops).
# Used by BOTH the terra (dense) and the sparse paths.
aggregate_metrics <- function(dt, has_n) {
  # veg abundance: per-class fractions + top-5 (by pixel count)
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
  setnames(tops, paste0("top_",  1:5), paste0("veg_top", 1:5),        skip_absent = TRUE)
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

# ── [3a] TERRA (dense) path: patches()-labelled `pid` → metrics ────────────────
raster_metrics <- function(r, pid) {
  burned <- terra::ifel(is.na(pid), NA, 1)
  has_n  <- "n" %in% names(r)
  if (!has_n) warning("no 'n' band in the COG — n-summaries skipped (04 §5).", call. = FALSE)
  ba <- lapply(BA_RADII, function(k) {
    w <- 2L * k + 1L
    terra::mask(terra::focal(burned * 1, matrix(1, w, w), "sum", na.rm = TRUE), pid) / (w * w)
  })
  ba <- terra::rast(ba); names(ba) <- sprintf("burned_around_%d", BA_RADII)
  cell_area <- terra::mask(terra::cellSize(pid, unit = "m"), pid)
  bands <- c("veg_fire", "abs_date", if (has_n) "n")
  stk   <- c(pid, r[[bands]], cell_area, ba)
  names(stk)[names(stk) == "area"] <- "cell_area"
  dt <- as.data.table(terra::as.data.frame(stk, na.rm = TRUE))
  aggregate_metrics(dt, has_n)
}

# ── [3b] SPARSE path: igraph connected-components over burned CELLS only ───────
# Everything below is O(burned), never scanning the dense background grid.
.in_set <- function(x, bs)                      # membership by binary search (bs sorted once)
  { p <- findInterval(x, bs); p >= 1L & bs[pmax(p, 1L)] == x }

# Label burned cells with globally-unique component ids (adds `pid`), applying the
# SAME dilation rule: bridge via a 1-px halo grown only from non-ag/grass burned.
label_sparse <- function(dt, nc) {
  off8  <- CJ(dr = -1:1, dc = -1:1)[!(dr == 0 & dc == 0)]
  nonag <- dt[!(veg_fire %in% AG_GRASS_NO_DILATE), .(row, col)]
  halo <- rbindlist(lapply(seq_len(nrow(off8)), function(i) {
    ncl <- nonag$col + off8$dc[i]; nrw <- nonag$row + off8$dr[i]
    ok  <- ncl >= 1 & ncl <= nc & nrw >= 1
    data.table(cell = (nrw[ok] - 1L) * nc + ncl[ok])
  }))
  halo  <- unique(halo)[!dt, on = "cell"]                 # drop cells that are burned
  nodes <- unique(rbindlist(list(dt[, .(cell)], halo)))
  nodes[, `:=`(row = ((cell - 1L) %/% nc) + 1L, col = ((cell - 1L) %% nc) + 1L, idx = .I)]

  fwd <- list(c(0L, 1L), c(1L, 0L), c(1L, 1L), c(1L, -1L))  # 4 offsets cover all 8-adjacency once
  edges <- rbindlist(lapply(fwd, function(o) {
    ncl <- nodes$col + o[2]; ok <- ncl >= 1 & ncl <= nc
    nb  <- (nodes$row + o[1] - 1L) * nc + ncl
    j   <- nodes[data.table(cell = nb), on = "cell", idx]
    keep <- ok & !is.na(j)
    data.table(a = nodes$idx[keep], b = j[keep])
  }))
  g <- igraph::make_graph(edges = if (nrow(edges)) as.vector(rbind(edges$a, edges$b)) else integer(0),
                          n = nrow(nodes), directed = FALSE)
  nodes[, comp := igraph::components(g)$membership]
  dt[nodes, pid := i.comp, on = "cell"]                   # burned cells get their component id
  dt
}

# burned_around_k = fraction of the (2k+1)² window that is burned, per burned cell.
add_burned_around <- function(dt, nc) {
  bs   <- sort(dt$cell)
  K    <- max(BA_RADII)
  offs <- CJ(dr = -K:K, dc = -K:K)[, cheb := pmax(abs(dr), abs(dc))]
  cnt  <- matrix(0L, nrow(dt), length(BA_RADII))
  for (i in seq_len(nrow(offs))) {
    ncl <- dt$col + offs$dc[i]; ok <- ncl >= 1 & ncl <= nc
    nb  <- (dt$row + offs$dr[i] - 1L) * nc + ncl
    hit <- ok & .in_set(nb, bs)
    for (ri in seq_along(BA_RADII)) if (offs$cheb[i] <= BA_RADII[ri]) cnt[hit, ri] <- cnt[hit, ri] + 1L
  }
  for (ri in seq_along(BA_RADII))
    dt[, (sprintf("burned_around_%d", BA_RADII[ri])) := cnt[, ri] / (2L * BA_RADII[ri] + 1L)^2]
  invisible(dt)
}

# Returns list(pid = <SpatRaster of component ids>, mets = aggregate_metrics(...)).
objects_sparse <- function(r) {
  has_n <- "n" %in% names(r)
  nc <- ncol(r)
  # burned cells + bands in one pass (candseed>0 works for NA- or 0-background)
  dt <- as.data.table(terra::as.data.frame(r, cells = TRUE, na.rm = TRUE))[candseed > 0]
  if (!nrow(dt)) stop("no burned pixels in raster")
  dt[, `:=`(row = ((cell - 1L) %/% nc) + 1L, col = ((cell - 1L) %% nc) + 1L)]

  label_sparse(dt, nc)                                    # → pid

  # per-cell area. For a regular lon/lat grid the area depends only on the ROW
  # (latitude), so compute terra::cellSize on a 1-column strip (O(nrow), cheap) and
  # map by row — identical to the dense path's cellSize(), no full-grid scan.
  if (terra::is.lonlat(r)) {
    e <- terra::ext(r)
    strip <- terra::rast(nrows = nrow(r), ncols = 1L, crs = terra::crs(r),
                         xmin = e$xmin, xmax = e$xmin + terra::xres(r),
                         ymin = e$ymin, ymax = e$ymax)
    carow <- terra::values(terra::cellSize(strip, unit = "m"))[, 1]   # length nrow
    dt[, cell_area := carow[row]]
  } else {
    dt[, cell_area := terra::xres(r) * terra::yres(r)]
  }
  add_burned_around(dt, nc)

  mets <- aggregate_metrics(dt, has_n)
  pr <- terra::rast(r, nlyrs = 1); terra::values(pr) <- NA_integer_
  pr[dt$cell] <- dt$pid; names(pr) <- "pid"
  list(pid = pr, mets = mets)
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
  # via the vertex table. The SNIC grid is WGS84 lon/lat, so bbox spans come out
  # in DEGREES — convert the sides to ground METRES (else mbr_fill mixes m²/deg²
  # and mbr_elongation is distorted by cos(lat)). Guard keeps a projected CRS as-is.
  g  <- as.data.table(terra::geom(v))
  bb <- g[, .(dx = max(x) - min(x), dy = max(y) - min(y),
              latc = (max(y) + min(y)) / 2), by = geom][order(geom)]
  if (terra::is.lonlat(v)) {
    sx <- bb$dx * 111320 * cos(bb$latc * pi / 180)   # E-W ground span (m)
    sy <- bb$dy * 110574                             # N-S ground span (m)
  } else {
    sx <- bb$dx; sy <- bb$dy                         # already metres
  }

  polys_sf$perimeter_m   <- p
  polys_sf$convexity     <- a / ha                                 # area / convex hull
  polys_sf$mbr_fill      <- a / (sx * sy)                          # area / bbox area
  polys_sf$mbr_elongation <- pmax(sx, sy) / pmin(sx, sy)
  polys_sf$circularity   <- 4 * pi * a / (p^2)                     # 4πA / P²
  polys_sf$shape_index   <- p / (2 * sqrt(pi * a))                 # P / (2√πA)
  polys_sf
}

# ── driver ────────────────────────────────────────────────────────────────────
process_year <- function(fy, test = FALSE, method = "sparse") {
  message(sprintf("── fire-year %d%s [%s] ──", fy, if (test) " test-ROI" else "", method))
  r <- load_snic(fy, test)
  if (method == "sparse") {                       # igraph over burned cells (default)
    os <- objects_sparse(r); pid <- os$pid; mets <- os$mets
  } else {                                        # terra patches() fallback
    pid <- object_ids(r[["candseed"]], r[["veg_fire"]]); mets <- raster_metrics(r, pid)
  }
  polys <- vectorize_join(pid, mets)
  polys <- add_shape_metrics(polys)
  polys$fire_year <- fy

  # `pid` is only unique WITHIN a year (patches() restarts at 1 each year), so
  # build a globally-unique object id by prefixing the fire-year: "<fy>_<pid>".
  polys$oid <- sprintf("%d_%d", fy, polys$pid)
  polys <- polys[, c("oid", setdiff(names(polys), "oid"))]  # oid first

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
  test   <- "test"  %in% args                      # tokens (any order): test, terra, then years
  method <- if ("terra" %in% args) "terra" else "sparse"
  args   <- setdiff(args, c("test", "terra"))
  prefix <- if (test) "snic_test_" else "snic_"
  years <- if (length(args)) as.integer(args) else {
    f <- list.files(SNIC_DIR, pattern = sprintf("^%s\\d{4}.*\\.tif$", prefix))
    sort(unique(as.integer(sub(sprintf("^%s(\\d{4}).*$", prefix), "\\1", f))))
  }
  if (!length(years)) stop("no fire-years to process (none given, none found in ", SNIC_DIR, ")")
  for (fy in years) process_year(fy, test, method)
}

if (sys.nframe() == 0L) main()
