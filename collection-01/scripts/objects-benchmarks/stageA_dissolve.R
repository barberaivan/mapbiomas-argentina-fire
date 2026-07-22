#!/usr/bin/env Rscript
# Path A, step 3: dissolve the raw gdal polygons BY pid so disconnected same-pid
# fragments (dilation-bridge case) collapse into one multipolygon — matching terra/Path B.
suppressPackageStartupMessages({ library(terra) })
terraOptions(progress = 0)
D <- Sys.getenv("F2000_DIR")
t <- Sys.time()
v  <- terra::vect(file.path(D, "A_raw.gpkg"))
vd <- terra::aggregate(v, by = "pid")                 # one (multi)polygon per pid
terra::writeVector(vd, file.path(D, "A.gpkg"), overwrite = TRUE)
cat(sprintf("[A] dissolve-by-pid: %d raw -> %d dissolved  wall_s=%.1f\n",
            nrow(v), nrow(vd), as.numeric(Sys.time() - t, units = "secs")))
