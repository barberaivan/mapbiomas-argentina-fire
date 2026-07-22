#!/usr/bin/env Rscript
# Path B: per-object loop, parallel on N cores. For each pid, build a tiny local raster
# (its bbox), burn ALL its cells (connected or not), as.polygons(dissolve=TRUE) -> one
# (multi)polygon per pid natively (preserves the dilation bridge, no fix-up). Workers write
# per-shard GPKGs (no cross-fork geometry serialization); master merges them.
suppressPackageStartupMessages({ library(terra); library(data.table); library(parallel); library(jsonlite) })
terraOptions(progress = 0)

D <- Sys.getenv("F2000_DIR")
NCORES <- as.integer(Sys.getenv("F2000_CORES", "13"))
meta <- jsonlite::fromJSON(file.path(D, "meta.json"))
x0 <- meta$x0; y0 <- meta$y0; dx <- meta$dx; ady <- meta$ady; CRS <- meta$crs

row <- readBin(file.path(D, "row.i32"), integer(), n = meta$n_cells, size = 4L)
col <- readBin(file.path(D, "col.i32"), integer(), n = meta$n_cells, size = 4L)
pid <- readBin(file.path(D, "pid.i32"), integer(), n = meta$n_cells, size = 4L)
dt  <- data.table(row = row, col = col, pid = pid); setkey(dt, pid)
pids <- sort(unique(pid))
cat(sprintf("[B] cells=%d  n_pids=%d  cores=%d\n", nrow(dt), length(pids), NCORES))

one_poly <- function(pd) {
  cc <- dt[.(pd)]
  rmin <- min(cc$row); rmax <- max(cc$row); cmin <- min(cc$col); cmax <- max(cc$col)
  h <- rmax - rmin + 1L; w <- cmax - cmin + 1L
  rr <- terra::rast(nrows = h, ncols = w, crs = CRS,
                    xmin = x0 + (cmin - 1) * dx, xmax = x0 + cmax * dx,
                    ymin = y0 - rmax * ady,      ymax = y0 - (rmin - 1) * ady)
  v <- rep(NA_integer_, as.numeric(h) * w)
  v[(cc$row - rmin) * w + (cc$col - cmin) + 1L] <- 1L
  terra::values(rr) <- v
  p <- terra::as.polygons(rr, dissolve = TRUE); p$pid <- pd; p
}

# split pids into NCORES contiguous chunks; each worker writes one shard gpkg
chunks <- split(pids, cut(seq_along(pids), NCORES, labels = FALSE))
t <- Sys.time()
shards <- mclapply(seq_along(chunks), function(k) {
  polys <- lapply(chunks[[k]], one_poly)
  out <- do.call(rbind, polys)
  f <- file.path(D, sprintf("B_shard_%02d.gpkg", k))
  terra::writeVector(out, f, overwrite = TRUE); f
}, mc.cores = NCORES, mc.preschedule = FALSE)
t_par <- as.numeric(Sys.time() - t, units = "secs")
bad <- vapply(shards, function(x) inherits(x, "try-error") || is.null(x), logical(1))
if (any(bad)) stop("worker(s) failed: ", paste(which(bad), collapse = ","))
cat(sprintf("[B] parallel per-object: wall_s=%.1f\n", t_par))

t <- Sys.time()
merged <- do.call(rbind, lapply(unlist(shards), terra::vect))
terra::writeVector(merged, file.path(D, "B.gpkg"), overwrite = TRUE)
t_merge <- as.numeric(Sys.time() - t, units = "secs")
cat(sprintf("[B] merge shards: features=%d  wall_s=%.1f\n", nrow(merged), t_merge))
cat(sprintf("[B] TOTAL wall_s=%.1f\n", t_par + t_merge))
