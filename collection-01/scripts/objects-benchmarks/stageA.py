"""Path A: out-of-core pid raster write (block-aware, touch only populated blocks) +
gdal.Polygonize (8-connected) -> A_raw.gpkg. Reports raw feature count (which EXCEEDS
n_pids exactly because gdal splits disconnected same-pid fragments — the dilation-bridge
case) and the write/polygonize wall-times. Dissolve-by-pid is done afterwards in R."""
import os, json, time
import numpy as np
from osgeo import gdal, ogr, osr
gdal.UseExceptions()

D = os.environ["F2000_DIR"]
meta = json.load(open(f"{D}/meta.json"))
nrow, ncol = int(meta["nrow"]), int(meta["ncol"])
row = np.fromfile(f"{D}/row.i32", dtype="<i4")
col = np.fromfile(f"{D}/col.i32", dtype="<i4")
pid = np.fromfile(f"{D}/pid.i32", dtype="<i4")
print(f"[A] cells={row.size:,}  n_pids={meta['n_pids']:,}  grid={nrow}x{ncol}", flush=True)

# ---- 1. write pid.tif, block-aware (only blocks containing burned cells) ----
t = time.time()
BS = 512
nbc = (ncol + BS - 1) // BS
drv = gdal.GetDriverByName("GTiff")
ds = drv.Create(f"{D}/pid.tif", ncol, nrow, 1, gdal.GDT_Int32,
                options=["TILED=YES", f"BLOCKXSIZE={BS}", f"BLOCKYSIZE={BS}",
                         "COMPRESS=DEFLATE", "SPARSE_OK=TRUE", "BIGTIFF=YES"])
ds.SetGeoTransform((meta["x0"], meta["dx"], 0.0, meta["y0"], 0.0, -meta["ady"]))
srs = osr.SpatialReference(); srs.ImportFromWkt(meta["crs"]); ds.SetProjection(srs.ExportToWkt())
band = ds.GetRasterBand(1); band.SetNoDataValue(0)

br = (row - 1) // BS            # 0-based block row/col of each cell
bc = (col - 1) // BS
blk = br.astype(np.int64) * nbc + bc
order = np.argsort(blk, kind="stable")
blk_s, row_s, col_s, pid_s = blk[order], row[order], col[order], pid[order]
cut = np.flatnonzero(np.diff(blk_s)) + 1
starts = np.concatenate(([0], cut)); ends = np.concatenate((cut, [blk_s.size]))
nblocks = 0
for s, e in zip(starts, ends):
    r0 = int((row_s[s] - 1) // BS) * BS         # block origin (global, 0-based)
    c0 = int((col_s[s] - 1) // BS) * BS
    h = min(BS, nrow - r0); w = min(BS, ncol - c0)
    arr = np.zeros((h, w), dtype=np.int32)
    arr[(row_s[s:e] - 1) - r0, (col_s[s:e] - 1) - c0] = pid_s[s:e]
    band.WriteArray(arr, c0, r0)
    nblocks += 1
band.FlushCache(); ds = None
t_write = time.time() - t
print(f"[A] pid.tif write: blocks={nblocks}  wall_s={t_write:.1f}  "
      f"size_MB={os.path.getsize(f'{D}/pid.tif')/1e6:.1f}", flush=True)

# ---- 2. gdal.Polygonize (8-connected), values -> 'pid' field ----
t = time.time()
src = gdal.Open(f"{D}/pid.tif"); b = src.GetRasterBand(1); mb = b.GetMaskBand()
srs2 = osr.SpatialReference(); srs2.ImportFromWkt(src.GetProjection())
gdrv = ogr.GetDriverByName("GPKG")
raw = f"{D}/A_raw.gpkg"
if os.path.exists(raw): gdrv.DeleteDataSource(raw)
rds = gdrv.CreateDataSource(raw)
lyr = rds.CreateLayer("scars", srs=srs2, geom_type=ogr.wkbPolygon)
lyr.CreateField(ogr.FieldDefn("pid", ogr.OFTInteger))
gdal.Polygonize(b, mb, lyr, 0, ["8CONNECTED=8"])
n_raw = lyr.GetFeatureCount()
rds = None; src = None
t_poly = time.time() - t
print(f"[A] polygonize: raw_features={n_raw:,}  (n_pids={meta['n_pids']:,} -> "
      f"{n_raw - meta['n_pids']:,} extra from disconnected same-pid fragments)  "
      f"wall_s={t_poly:.1f}", flush=True)
print(f"[A] SUBTOTAL (write+polygonize) wall_s={t_write + t_poly:.1f}  "
      f"(dissolve-by-pid added next in R)", flush=True)
