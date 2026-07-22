#!/bin/bash
# Benchmark: whole-country (FY2000, 9.16e9 cells) vectorization — legacy terra
# as.polygons vs streaming gdal-polygonize (rasterio). Input: legacy snic_2000
# Drive-COG sub-tifs (being replaced by direct-download images). Results → bench_2000.log
set -u
BASE=/home/ivan/dev/MapBiomas/mapbiomas-arg-fire
SCRATCH=/tmp/claude-1000/-home-ivan-dev-MapBiomas-mapbiomas-arg-fire/f1153fc2-432d-4038-8c16-6cab1dca7765/scratchpad
PY=/home/ivan/.venvs/gee/bin/python
MASK=$SCRATCH/burned_2000.tif
cd "$BASE" || exit 1
TIME=/usr/bin/time
exec > "$SCRATCH/bench_2000.log" 2>&1

echo "######## BENCH FY2000 (9,156,980,085 cells) — started $(date -Is)"

echo; echo "######## STEP 1: build burned-mask uint8 sparse tif (terra, out-of-core)"
$TIME -v Rscript -e '
suppressPackageStartupMessages(library(terra)); terraOptions(progress=0)
t<-Sys.time()
tifs <- list.files("collection-01/data/snic-polygons", pattern="^snic_2000-.*\\.tif$", full.names=TRUE)
r <- terra::vrt(tifs, filename=tempfile(fileext=".vrt"), overwrite=TRUE)
m <- terra::ifel(r[[1]] > 0, 1L, NA)                      # band 1 = candseed; burned = >0
terra::writeRaster(m, "'"$MASK"'", datatype="INT1U", overwrite=TRUE, NAflag=0,
                   gdal=c("COMPRESS=DEFLATE","TILED=YES","SPARSE_OK=TRUE"))
cat(sprintf("STEP1 mask written; wall_s=%.1f\n", as.numeric(Sys.time()-t, units="secs")))
'
echo "mask file size: $(du -h "$MASK" 2>/dev/null | cut -f1)"

echo; echo "######## STEP 2: NEW — streaming gdal-polygonize (rasterio band, 8-conn)"
$TIME -v $PY - <<PYEOF
import time, rasterio
from rasterio.features import shapes
t=time.time(); n=0
with rasterio.open("$MASK") as src:
    b = rasterio.band(src, 1)                             # Band source → GDAL streams it
    for geom, val in shapes(b, mask=b, connectivity=8):  # one polygon per 8-conn burned blob
        n += 1
print(f"STEP2 NEW polygons={n} wall_s={time.time()-t:.1f}")
PYEOF

echo; echo "######## STEP 3: OLD — terra::as.polygons on the same mask (risky; last)"
$TIME -v Rscript -e '
suppressPackageStartupMessages(library(terra)); terraOptions(progress=0)
t<-Sys.time()
m <- terra::rast("'"$MASK"'")
v <- terra::as.polygons(m, dissolve=TRUE, values=TRUE, na.rm=TRUE)
cat(sprintf("STEP3 OLD as.polygons features=%d wall_s=%.1f\n", nrow(v),
            as.numeric(Sys.time()-t, units="secs")))
'
echo; echo "######## DONE $(date -Is)"
