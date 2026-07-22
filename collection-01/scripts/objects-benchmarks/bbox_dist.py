from osgeo import ogr
import numpy as np
ogr.UseExceptions()
PX = 0.00026949458523585647            # pixel size in degrees (from geotransform)
ds = ogr.Open("scars_2000_native.gpkg"); lyr = ds.GetLayer(0)
lyr.ResetReading()
bbox_cells, poly_area = [], []
for feat in lyr:
    g = feat.GetGeometryRef()
    xmin, xmax, ymin, ymax = g.GetEnvelope()
    bbox_cells.append(((xmax-xmin)/PX) * ((ymax-ymin)/PX))
    poly_area.append(g.GetArea() / (PX*PX))
bbox_cells = np.array(bbox_cells); poly_area = np.array(poly_area)
print(f"objects: {len(bbox_cells)}")
print("\nBBOX area (cells) per object  [per-object loop must allocate/scan this]:")
for q in [50, 90, 99, 99.9, 100]:
    print(f"  p{q:<5}= {np.percentile(bbox_cells, q):,.0f}")
print(f"  SUM bbox areas = {bbox_cells.sum():,.0f} cells   (country grid = 9,156,980,085)")
print(f"  bbox-sum / country = {bbox_cells.sum()/9_156_980_085:.4f}")
print("\nActual polygon area (cells):")
for q in [50, 90, 99, 99.9, 100]:
    print(f"  p{q:<5}= {np.percentile(poly_area, q):,.0f}")
print(f"  SUM burned cells = {poly_area.sum():,.0f}   mean/object = {poly_area.mean():,.1f}")
print(f"\n# bbox >1e5: {(bbox_cells>1e5).sum()}   >1e6: {(bbox_cells>1e6).sum()}   >1e7: {(bbox_cells>1e7).sum()}   >1e8: {(bbox_cells>1e8).sum()}")
print(f"max single bbox = {bbox_cells.max():,.0f} cells")
np.save("bbox_cells.npy", bbox_cells); np.save("poly_area.npy", poly_area)
