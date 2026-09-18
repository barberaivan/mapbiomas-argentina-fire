> **Extracted from** `collection-01/validation/docs/design.md` Appendix A @ `54e3e8d`
> (2026-09-18) — superseded by `validation/01_strata_export.py`, a direct Python port.
> Lab notebook — the record of building the step, not documentation of it.

# Appendix A — the strata raster, as first written in GEE JavaScript

`01_strata_export.py` is the implementation of record ("Traducción directa a Python del Appendix A",
its module docstring) and is what actually produced the three landed strata rasters. This is kept
as the prototype it was ported from.

⚠️ **Two things in it are out of date and were true when it was written.** `MOB` hardcodes
`collection1_fire_mask_v1`; the published month-of-burn collection is now `_v2`
(`C.MONTH_OF_BURN_COL`, `C.PRODUCT_VERSION = 2` since 2026-09-11, `docs/07` "The `_v2` re-export").
And it is JavaScript pasted into a doc, so nothing lints or runs it — the reason the appendices
left `design.md` at all.

## Appendix A — the strata raster (GEE)

```javascript
// ---------------------------------------------------------------- parameters
var FY      = 2015;                 // fire year = 1 May FY -> 30 Apr FY+1
var FACTOR  = 16;                   // coarse grid = product grid / FACTOR  (~480 m)
var RAD_PX  = 1;                    // focalMax radius, coarse pixels, square kernel

var BASE_CRS = 'EPSG:4326';
var BASE_T   = [0.000269494585236, 0, -73.58468801489491,
                0, -0.000269494585236, -21.764113209062533];
var COARSE_T = [BASE_T[0]*FACTOR, 0, BASE_T[2],
                0, BASE_T[4]*FACTOR, BASE_T[5]];
var COARSE = ee.Projection(BASE_CRS, COARSE_T);

var MOB   = 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/' +
            'CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1';
var FRAME = ee.FeatureCollection('projects/mapbiomas-argentina/assets/ANCILLARY_DATA/' +
            'VECTOR/ARG/ARG-Political_Level_1-Pais').geometry();

var t0 = ee.Date.fromYMD(FY, 5, 1), t1 = t0.advance(1, 'year');

// ------------------------------------------------- 1. our fire-year layer = S1
// per-pixel month/year from abs_date, so the two-slice OR is exact (S3)
function mob(y) {
  return ee.Image(ee.ImageCollection(MOB)
    .filter(ee.Filter.eq('year', y)).first()).select('burned_monthly').unmask(0);
}
var mNext   = mob(FY + 1);
var ourBurn = mob(FY).gte(5)                             // May-Dec of FY
                .or(mNext.gte(1).and(mNext.lte(4)));     // Jan-Apr of FY+1

// ------------------------------------------ 2. external evidence, fire-year
// monthly composites straddling the window boundary are taken WHOLE: recall > precision (S4.1)
var mcd64   = ee.ImageCollection('MODIS/061/MCD64A1')
                .filterDate(t0,t1).select('BurnDate').max().gte(1).unmask(0);
var vnp64   = ee.ImageCollection('NASA/VIIRS/002/VNP64A1')          // VIIRS BURNED AREA, 2012->
                .filterDate(t0,t1).select('Burn_Date').max().gte(1).unmask(0);
var firecci = ee.ImageCollection('ESA/CCI/FireCCI/5_1')             // 2001-2020 only
                .filterDate(t0,t1).select('BurnDate').max().gte(1).unmask(0);
var firms   = ee.ImageCollection('FIRMS')                           // no confidence filter (S4.1)
                .filterDate(t0,t1).select('T21').max().gt(0).unmask(0);

// -------------------------------- 3. one nested coarse grid, MAX aggregation
// finer-or-equal than COARSE -> reduceResolution(max); NEVER mode (S4.3).
// maxPixels must exceed FACTOR^2 = 256; the default of 64 is too small.
function toCoarseFine(img) {
  return img.reduceResolution({reducer: ee.Reducer.max(), maxPixels: 1024})
            .reproject(COARSE);
}
// coarser than COARSE (FIRMS, 927 m) -> nearest replicates the cell, loses nothing
function toCoarseCoarse(img) { return img.reproject(COARSE); }

var parts = [toCoarseFine(ourBurn), toCoarseFine(mcd64), toCoarseCoarse(firms)];
var products = ['ours', 'MCD64A1', 'FIRMS'];                     // recorded on the asset (S4.4)
if (FY >= 2012 && FY <= 2024) { parts.push(toCoarseFine(vnp64));   products.push('VNP64A1'); }
if (FY >= 2001 && FY <= 2019) { parts.push(toCoarseFine(firecci)); products.push('FireCCI51'); }

var union = parts.reduce(function(a, b) { return a.or(b); });

// ------------- 4. dilate on the coarse grid, then back to the product grid
// projection is already COARSE, so the 3x3 kernel is fixed to the coarse lattice
var dilated = union
      .focalMax({radius: RAD_PX, units: 'pixels', kernelType: 'square'})
      .reproject({crs: BASE_CRS, crsTransform: BASE_T});   // exact block replication

// ------------------------ 5. mutually exclusive, exhaustive partition at 30 m
// S1 subtracted at 30 m so it is exactly the product's own pixel set
var s1 = ourBurn;
var s2 = dilated.and(s1.not());
var s3 = s1.not().and(s2.not());

var stratum = s1.multiply(1).add(s2.multiply(2)).add(s3.multiply(3)).rename('stratum');

// TWO bands: the partition, and our map's own call so the sample carries it (S4)
var out = stratum.addBands(s1.rename('burned')).toByte().clip(FRAME)
  .set({
    year:               FY,       // FIRE year   -- mandatory
    collection:         1,        // integer     -- mandatory
    source:             'mapbiomas-fuego',
    region:             'argentina',
    fire_year_definition: 'non-calendar: 1 May <year> to 30 Apr <year>+1',
    coarse_factor:      FACTOR,
    dilation_radius_px: RAD_PX,
    products:           products.join(','),
    frame:              'ARG-Political_Level_1-Pais',
    bands:              'stratum(1=mapped burned,2=evidence buffer,3=rest);burned(our map 0/1)'
  });

// ------------------------------------------------------------- 6. freeze it
var COL = 'projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata';
Export.image.toAsset({
  image: out,
  description: 'val10_strata_fy' + FY,
  assetId: COL + '/sampling_strata_fy' + FY,    // one image per fire year, in the existing IC
  region: FRAME,
  crs: BASE_CRS, crsTransform: BASE_T,          // NEVER scale: 30
  maxPixels: 1e13,
  pyramidingPolicy: {'.default': 'mode'}        // categorical, both bands
});

// ------------------------------- 7. Nh = the weights AND the fingerprint (S4.4)
print('Nh -- record this', stratum.clip(FRAME).reduceRegion({
  reducer: ee.Reducer.frequencyHistogram(), geometry: FRAME,
  crs: BASE_CRS, crsTransform: BASE_T, maxPixels: 1e13, tileScale: 4}));
```

Namespace every task description (`val10_…`) — the compute project is shared with the whole
MapBiomas Fuego network and `ee.data.listOperations()` returns every user's tasks.

