"""Native gdal.Polygonize (osgeo, C) of the whole-country FY2000 burned mask → GPKG.
Writes geometries straight to OGR (no Python-object round-trip), 8-connected, streaming.
Reuses the burned_2000.tif built by bench_2000.sh STEP 1."""
import os, sys, time
from osgeo import gdal, ogr, osr

gdal.UseExceptions()
MASK, OUT = sys.argv[1], sys.argv[2]
t = time.time()

src = gdal.Open(MASK)
band = src.GetRasterBand(1)
maskband = band.GetMaskBand()               # nodata=0 → excludes background
srs = osr.SpatialReference(); srs.ImportFromWkt(src.GetProjection())

drv = ogr.GetDriverByName("GPKG")
if os.path.exists(OUT):
    drv.DeleteDataSource(OUT)
ds = drv.CreateDataSource(OUT)
layer = ds.CreateLayer("scars", srs=srs, geom_type=ogr.wkbPolygon)
layer.CreateField(ogr.FieldDefn("val", ogr.OFTInteger))

# One native C pass: one polygon per 8-connected burned blob, written to GPKG.
gdal.Polygonize(band, maskband, layer, 0, ["8CONNECTED=8"])
n = layer.GetFeatureCount()
ds = None; src = None
print(f"NATIVE gdal.Polygonize features={n} wall_s={time.time()-t:.1f} out={OUT}")
print(f"gpkg size: {os.path.getsize(OUT)/1e6:.1f} MB")
