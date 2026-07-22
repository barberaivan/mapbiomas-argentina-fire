suppressPackageStartupMessages(library(terra))
terraOptions(progress=0)
# Realistic per-object op: allocate an s-side bbox raster, fill ~38% (the real
# overall poly/bbox ratio) as a solid-ish blob, build SpatRaster, as.polygons(dissolve).
per_obj <- function(side, reps) {
  h <- w <- max(1L, as.integer(round(sqrt(side))))   # square bbox of ~`side` cells
  ts <- numeric(reps)
  for (k in seq_len(reps)) {
    t0 <- Sys.time()
    m <- matrix(NA_integer_, h, w)
    i1 <- max(1L, as.integer(round(h*0.62)))          # ~0.62^2 ≈ 0.38 fill
    j1 <- max(1L, as.integer(round(w*0.62)))
    m[seq_len(i1), seq_len(j1)] <- 1L
    r <- rast(nrows=h, ncols=w, xmin=0, xmax=w, ymin=0, ymax=h)
    values(r) <- m
    p <- as.polygons(r, dissolve=TRUE)
    ts[k] <- as.numeric(Sys.time()-t0, units="secs")
  }
  median(ts)
}
sizes <- c(1, 50, 128, 300, 906, 2254, 7039, 19284, 78297, 222232, 1e6, 5e6, 25.8e6)
reps  <- c(80, 80, 80,  60,  50,  40,   30,    20,    10,    6,      3,   2,   1)
cat(sprintf("%-12s %-14s\n", "bbox_cells", "median_s"))
res <- data.frame(bbox=numeric(), t=numeric())
for (i in seq_along(sizes)) {
  tt <- per_obj(sizes[i], reps[i])
  res <- rbind(res, data.frame(bbox=sizes[i], t=tt))
  cat(sprintf("%-12.0f %-14.6f\n", sizes[i], tt))
}
write.csv(res, "costcurve.csv", row.names=FALSE)
