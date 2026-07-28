#!/usr/bin/env Rscript
# Stage 0a: per-carta burned-cell extract → row/col int32 binaries + meta_grid.json.
# Cached so labelling can be re-tried without the ~11-min tile scan.
suppressPackageStartupMessages({ library(terra); library(data.table); library(jsonlite) })
terraOptions(progress = 0)
source("collection-01/workflow/05-objects_metrics.R")
OUT <- Sys.getenv("F2000_DIR"); fy <- 2000
tifs <- list.files(file.path("collection-01/data/snic-rasters", as.character(fy)),
                   pattern = "\\.tif$", full.names = TRUE)
t0 <- Sys.time()
r  <- terra::vrt(tifs, overwrite = TRUE)
nc <- ncol(r); nr <- nrow(r)
e  <- terra::ext(r); x0 <- e$xmin; y0 <- e$ymax; dx <- terra::xres(r); ady <- terra::yres(r)
parts <- vector("list", length(tifs))
for (i in seq_along(tifs)) {
  tl <- terra::rast(tifs[i]); if (!"candseed" %in% names(tl)) names(tl) <- EXPECT_BANDS_DIRECT[seq_len(nlyr(tl))]
  d  <- as.data.table(terra::as.data.frame(tl[["candseed"]], cells = TRUE, na.rm = TRUE))[candseed > 0]
  if (!nrow(d)) next
  tnc <- ncol(tl); te <- terra::ext(tl)
  gcol0 <- as.integer(round((te$xmin - x0) / dx)); grow0 <- as.integer(round((y0 - te$ymax) / ady))
  parts[[i]] <- data.table(row = grow0 + (((d$cell - 1L) %/% tnc) + 1L),
                           col = gcol0 + (((d$cell - 1L) %% tnc) + 1L))
}
dt <- unique(rbindlist(parts)); rm(parts)
cat(sprintf("STAGE0a extract: burned_cells=%d wall_s=%.1f\n", nrow(dt), as.numeric(Sys.time()-t0, units="secs")))
writeBin(as.integer(dt$row), file.path(OUT, "row.i32"), size = 4L)
writeBin(as.integer(dt$col), file.path(OUT, "col.i32"), size = 4L)
write_json(list(nrow=nr, ncol=nc, x0=x0, y0=y0, dx=dx, ady=ady, crs=terra::crs(r), n_cells=nrow(dt)),
           file.path(OUT, "meta_grid.json"), auto_unbox = TRUE, digits = 15)
cat("STAGE0a DONE\n")
