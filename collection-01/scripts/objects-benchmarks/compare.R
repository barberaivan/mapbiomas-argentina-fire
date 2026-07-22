#!/usr/bin/env Rscript
# Simple (not perfect) A-vs-B agreement: feature counts + total area + per-pid area match.
suppressPackageStartupMessages({ library(terra); library(data.table); library(jsonlite) })
terraOptions(progress = 0)
D <- Sys.getenv("F2000_DIR")
meta <- jsonlite::fromJSON(file.path(D, "meta.json"))

A <- terra::vect(file.path(D, "A.gpkg"))
B <- terra::vect(file.path(D, "B.gpkg"))
aA <- data.table(pid = A$pid, area = terra::expanse(A, unit = "m"))
aB <- data.table(pid = B$pid, area = terra::expanse(B, unit = "m"))
setkey(aA, pid); setkey(aB, pid)

cat(sprintf("n_pids (labels)     : %d\n", meta$n_pids))
cat(sprintf("features  A / B     : %d / %d\n", nrow(A), nrow(B)))
cat(sprintf("total area A / B m2 : %.3e / %.3e   (rel diff %.2e)\n",
            sum(aA$area), sum(aB$area), abs(sum(aA$area) - sum(aB$area)) / sum(aA$area)))
m <- merge(aA, aB, by = "pid", suffixes = c("_A", "_B"))
cat(sprintf("matched pids        : %d\n", nrow(m)))
cat(sprintf("per-pid area: max |A-B| = %.3e m2   max rel = %.2e\n",
            max(abs(m$area_A - m$area_B)),
            max(abs(m$area_A - m$area_B) / pmax(m$area_A, 1))))
