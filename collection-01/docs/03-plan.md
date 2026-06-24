# Implementation plan — workflow/03-bp_ts_metrics.py

## What this step does

For every year × MapBiomas carta tile: compute observation-level burn probability
for every Landsat image, reduce to annual time-series metrics, export as an image
to `projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics`.

**Export asset name pattern:** `bpts_YYYY_tile-id`
(e.g. `bpts_2015_SK-19-Y-A`)

---

## New constants needed in `utils/constants.py`

```python
from pathlib import Path

MODELS_DIR        = Path(__file__).resolve().parent.parent / "models"
REGION_RASTER     = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/RASTER/ARG/ARG-Regiones-MapBiomas-buffer2km"
CARTAS_FC         = "projects/mapbiomas-chaco/BASE/cartas-argentina"
ARG_BUFFER_FC     = "projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_1-Pais_buffer"
BP_TS_METRICS_COL = f"{_FIRE_ROOT}/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics"

PAD_MONTHS    = 4   # months of Landsat context before/after focal year (Sep–Apr window)
PAD_OBS_LEFT  = 3   # max prev-year obs pulled into padded array
PAD_OBS_RIGHT = 2   # max next-year obs

# CSV term suffix → MB mosaic band suffix (used in coefficient parsing)
PREV_SUFFIX_MAP = {
    "med": "median",
    "wet": "median_wet",
    "dry": "median_dry",
    "sd":  "stdDev",
}
```

---

## New functions needed in `utils/functions.py`

### Coefficient loading (pure Python, no ee)

```python
def load_all_coefficients():
    """
    Read all 23 per-class CSVs from MODELS_DIR.
    Returns list of 130 term dicts, each with:
      block     : str  — '(intercept)','focal','prev','pairs','sameband','cross_idx','cross_band'
      term      : str  — original CSV name
      band_name : str  — sanitized GEE band name ('(Intercept)' → 'intercept_term')
      factor1   : str  — first feature name (focal band OR mb_mos_* prev band) or None
      f1_src    : str  — 'focal' or 'prev' or None
      factor2   : str  — second feature name (focal band) or None
      coefs     : dict {veg_fire_class: float}  — 23 entries
    """
```

**Term name parsing rules:**
- `(Intercept)` → band_name `intercept_term`, no factors
- `BLUE_t` → focal factor `BLUE` (strip `_t`)
- `GREEN_med` → prev factor `mb_mos_green_median` (lowercase base + PREV_SUFFIX_MAP)
- `BLUE_t__NBR_t` → pairs: factor1=`BLUE` focal, factor2=`NBR` focal
- `GREEN_med__GREEN_t` → sameband: factor1=`mb_mos_green_median` prev, factor2=`GREEN` focal
- `NDVI_med__NBR_t` → cross_idx: factor1=`mb_mos_ndvi_median` prev, factor2=`NBR` focal
- `NDVI_med__RED_t` → cross_band: factor1=`mb_mos_ndvi_median` prev, factor2=`RED` focal

The CSV has **130 terms** across 7 blocks: (intercept)=1, focal=11, prev=32,
pairs=22, sameband=10, cross_idx=22, cross_band=32. All 23 class CSVs have
the same term order.

### GEE image building (require ee.Initialize already run)

```python
def build_coeff_image(veg_fire_img, terms):
    """
    130-band image; each band = coefficient for this pixel's veg_fire class.
    Uses veg_fire_img.remap(FITTABLE_VEG_FIRE, [coef_c1,...,coef_c23], 0.0)
    for each term. Band named by term['band_name'].
    """

def build_prev_scalar(coeff_img, mb_mosaic_img, terms):
    """
    Intercept + sum(prev_coef × mb_mosaic_band) for all prev-block terms.
    This is the time-invariant part of the linear predictor — computed once
    per year and reused for every Landsat image.
    Returns single-band image 'prev_scalar'.
    """

def build_cross_factor1_coef(coeff_img, mb_mosaic_img, terms):
    """
    For all cross terms (sameband, cross_idx, cross_band):
    precompute prev_feature × coefficient as a multi-band image.
    Multiplied by focal_f2 per image at runtime.
    One band per cross term (same order as terms list).
    """
```

### Landsat pipeline

```python
def mosaic_by_date(imgcol):
    """
    Mosaic all images sharing the same calendar date (mean reducer).
    Avoids duplicate obs from overlapping Landsat scenes on the same day.
    Returns sorted ImageCollection.
    """

def _frac_year(img):
    """
    Fractional year from system:time_start.
    e.g. 2010-07-02 → 2010.5. Returns single-band image 'frac_year'.
    """

def compute_burn_prob_img(img, prev_scalar, coeff_img, cross_f1_coef_img, terms):
    """
    Compute burn probability for one Landsat image (already has spectral indices).
    Returns 2-band image ['prob', 'frac_year'].

    Linear predictor = prev_scalar
                     + sum(focal_coef × focal_band)          # focal main
                     + sum(pairs_coef × f1 × f2)             # focal×focal pairs
                     + sum(cross_f1_coef × focal_f2)         # prev×focal cross

    prob = sigmoid(eta) = 1 / (1 + exp(-eta))
    Predictors used on their RAW scale — no centering, no standardisation.
    """
```

### Array operations

```python
def safe_to_array(imgcol):
    """
    Convert a 2-band [prob, frac_year] ImageCollection to an [N×2] array image.
    Guards against empty collections using ee.Algorithms.If:
        nonempty → imgcol.toArray()           # [N, 2]
        empty    → ee.Array([[0,0]]).slice(0,0,0)  # [0, 2] stub
    imgcol must be sorted by system:time_start before calling.
    """

def compute_bp_ts_metrics(focal_arr, prev_arr, next_arr):
    """
    Reduce per-pixel bp time-series arrays to annual metrics.
    Returns 18-band float image (see Output bands section).
    Does NOT apply veg_fire sentinels — caller handles that.
    """
```

---

## Padded array construction (inside `compute_bp_ts_metrics`)

**Key rule:** take *up to* N obs from prev/next (greedy, no minimum per side),
then check total length. Fixed offsets work because the cap guarantees
focal obs never appear before position 3 (K=3) or 2 (K=2) in the array.

```python
# K=3: up to 3 from prev + focal + up to 2 from next
prev_tail3 = prev_arr.arraySlice(0, -3)      # GEE clamps if len < 3
next_head2 = next_arr.arraySlice(0, 0, 2)
padded_k3  = prev_tail3.arrayCat(focal_arr, 0).arrayCat(next_head2, 0)
padded_k3  = padded_k3.updateMask(padded_k3.arrayLength(0).gte(6))
# gte(6) leaves UNMASKED where length >= 6. Mask otherwise.

# K=2: up to 2 from prev + focal + up to 1 from next
prev_tail2 = prev_arr.arraySlice(0, -2)
next_head1 = next_arr.arraySlice(0, 0, 1)
padded_k2  = prev_tail2.arrayCat(focal_arr, 0).arrayCat(next_head1, 0)
padded_k2  = padded_k2.updateMask(padded_k2.arrayLength(0).gte(4))
```

**Why ≥6/≥4 is sufficient:** the window for K=3 is 3+1+2=6 entries wide.
If N_total ≥ 6 and actual_L ≤ 3, actual_R ≤ 2, there is always at least
one focal obs with fully defined maxback3 and minfore3.

**Why fixed offsets work:** with actual_L capped at 3, focal obs start at
position ≥ 0, so `arraySlice(0, 3, -2)` always lands on focal obs (never
prev). Likewise `arraySlice(0, -2)` at the end never reaches focal obs
because actual_R ≤ 2.

### Fixed-offset slices for K=3 (column 0 = prob, column 1 = date)

```python
p3 = padded_k3.arraySlice(1, 0, 1)   # prob column [N,1]
d3 = padded_k3.arraySlice(1, 1, 2)   # date column [N,1]

p3_f  = p3.arraySlice(0, 3, -2)      # p[t]
p3_f1 = p3.arraySlice(0, 4, -1)      # p[t+1]
p3_f2 = p3.arraySlice(0, 5, None)    # p[t+2]
p3_b1 = p3.arraySlice(0, 2, -3)      # p[t-1]
p3_b2 = p3.arraySlice(0, 1, -4)      # p[t-2]
p3_b3 = p3.arraySlice(0, 0, -5)      # p[t-3]

# date slices: d3_f, d3_b1, d3_b3, d3_f2 (same offsets as p3)

minfore3 = p3_f.arrayCat(p3_f1,1).arrayCat(p3_f2,1).arrayReduce(ee.Reducer.min(),[1])
maxback3 = p3_b3.arrayCat(p3_b2,1).arrayCat(p3_b1,1).arrayReduce(ee.Reducer.max(),[1])
delta3   = minfore3.subtract(maxback3)   # [T_valid, 1]
```

### Finding the argmax peak (sort trick)

```python
# Bundle all quantities needed at t* into one [T_valid, 6] array
bundle3 = delta3.arrayCat(minfore3,1).arrayCat(d3_f,1).arrayCat(d3_b1,1).arrayCat(d3_b3,1).arrayCat(d3_f2,1)
# Sort descending by delta3 (column 0)
sort_key3 = delta3.arrayProject([0]).multiply(-1)   # 1D key, negated for descending
peak3 = bundle3.arraySort(sort_key3).arraySlice(0, 0, 1)  # [1, 6] first row

delta3_peak   = peak3.arrayGet([0, 0])
minfore3_peak = peak3.arrayGet([0, 1])
d_t3          = peak3.arrayGet([0, 2])   # frac_year at t*
d_b1_3        = peak3.arrayGet([0, 3])
d_b3_3        = peak3.arrayGet([0, 4])
d_f2_3        = peak3.arrayGet([0, 5])

DAYS = 365.25
jumpgap3   = d_t3.subtract(d_b1_3).multiply(DAYS)    # d[t] - d[t-1], days
prevwidth3 = d_b1_3.subtract(d_b3_3).multiply(DAYS)  # d[t-1] - d[t-3], days
postwidth3 = d_f2_3.subtract(d_t3).multiply(DAYS)    # d[t+2] - d[t], days
date_post3 = d_t3                                     # frac_year of the jump
```

Same pattern for K=2 (offsets 2/-1 instead of 3/-2; bundle cols: delta2, minfore2, d_f, d_b1, d_b2, d_f1).

### Whole-series metrics (from focal_arr directly)

```python
p_focal = focal_arr.arraySlice(1, 0, 1)
d_focal = focal_arr.arraySlice(1, 1, 2)
n       = focal_arr.arrayLength(0)                                        # scalar
pmax1   = p_focal.arrayReduce(ee.Reducer.max(),[0]).arrayGet([0,0])       # masked if n=0
pmax3   = minfore3.arrayReduce(ee.Reducer.max(),[0]).arrayGet([0,0])      # masked if padded_k3 masked
pmax2   = minfore2.arrayReduce(ee.Reducer.max(),[0]).arrayGet([0,0])

# Median and max inter-observation gap (days), requires n >= 2
diffs = d_focal.arraySlice(0,1).subtract(d_focal.arraySlice(0,0,-1)).multiply(DAYS)
timediff_med = diffs.arrayReduce(ee.Reducer.median(),[0]).arrayGet([0,0])
timediff_max = diffs.arrayReduce(ee.Reducer.max(),  [0]).arrayGet([0,0])
# Both masked when n < 2
```

---

## Output bands (18, all float)

| Band | Definition | Masked when |
|---|---|---|
| `delta3_peak` | max(delta3) over focal year | padded_k3 masked |
| `minfore3_peak` | minfore3 at delta3 argmax | padded_k3 masked |
| `jumpgap3` | d[t*]−d[t*−1], days | padded_k3 masked |
| `prevwidth3` | d[t*−1]−d[t*−3], days | padded_k3 masked |
| `postwidth3` | d[t*+2]−d[t*], days | padded_k3 masked |
| `date_post3` | d[t*] as frac_year | padded_k3 masked |
| `delta2_peak` | max(delta2) | padded_k2 masked |
| `minfore2_peak` | minfore2 at delta2 argmax | padded_k2 masked |
| `jumpgap2` | days | padded_k2 masked |
| `prevwidth2` | d[t*−1]−d[t*−2], days | padded_k2 masked |
| `postwidth2` | d[t*+1]−d[t*], days | padded_k2 masked |
| `date_post2` | frac_year | padded_k2 masked |
| `pmax3` | max(minfore3) whole series | padded_k3 masked |
| `pmax2` | max(minfore2) whole series | padded_k2 masked |
| `pmax1` | max raw prob whole series | n=0 |
| `n` | focal obs count; −1=non-burnable; −2=non-observed | **never masked** |
| `timediff_med` | median inter-obs gap, days | n<2 |
| `timediff_max` | max inter-obs gap, days | n<2 |

---

## `bpts()` function signature

```python
def bpts(year=None, tile_id=None, export=True):
    """
    year    : int or None  — None = all years in C.YEARS
    tile_id : str or None  — None = all tiles intersecting ARG buffer
                             e.g. 'SK-19-Y-A'
    export  : bool         — False returns the ee.Image (requires both year AND tile_id)
    """
    if not export and (year is None or tile_id is None):
        raise ValueError("export=False requires both year and tile_id")
    ...
```

| Call | Effect |
|---|---|
| `bpts(2015, 'SK-19-Y-A', export=False)` | Returns image for inspection |
| `bpts(2015, 'SK-19-Y-A')` | Exports that one tile-year |
| `bpts(2015)` | Exports all tiles for 2015 |
| `bpts(tile_id='SK-19-Y-A')` | Exports all years for that tile |
| `bpts()` | Exports all years × all tiles |

---

## Per-tile-year computation outline

```python
# 1. MB prev-year data (mb_year = min(year-1, MB_LIMIT_YEAR))
lulc_img     = ee.Image(C.MAPBIOMAS_LULC)
mb_class_img = get_mb_class_band(lulc_img, mb_year)
region_img   = ee.Image(C.REGION_RASTER).select('region_id')
region_class = region_img.multiply(100).add(mb_class_img)
veg_fire_img = region_class.remap(C.REGION_CLASS_FROM, C.VEG_FIRE_TO,
                                  C.VEG_FIRE_REMAP_DEFAULT).rename('veg_fire')
mb_mosaic    = get_mb_mosaic_bands(ee.ImageCollection(C.MAPBIOMAS_MOSAIC),
                                   mb_year, tile_geom, C.MB_MOSAIC_BANDS)

# 2. Static LR components (once per year)
coeff_img      = build_coeff_image(veg_fire_img, terms)
prev_scalar    = build_prev_scalar(coeff_img, mb_mosaic, terms)
cross_f1_coef  = build_cross_factor1_coef(coeff_img, mb_mosaic, terms)
is_fittable    = veg_fire_img.gte(1).And(veg_fire_img.lte(23))

# 3. Landsat time series: Sep(y-1)–Apr(y+1)
prev_start  = ee.Date.fromYMD(year-1, 12 - C.PAD_MONTHS + 1, 1)  # Sep 1 prev
prev_end    = ee.Date.fromYMD(year, 1, 1)
focal_start = ee.Date.fromYMD(year, 1, 1)
focal_end   = ee.Date.fromYMD(year+1, 1, 1)
next_start  = ee.Date.fromYMD(year+1, 1, 1)
next_end    = ee.Date.fromYMD(year+1, C.PAD_MONTHS+1, 1)          # May 1 next

full_col = get_landsat(tile_geom, prev_start, next_end)
full_col = mosaic_by_date(full_col)   # deduplicate same-day scenes

def _add_bp(img):
    return compute_burn_prob_img(
        add_indices(img), prev_scalar, coeff_img, cross_f1_coef, terms
    ).updateMask(is_fittable)

bp_col = full_col.map(_add_bp).select(['prob', 'frac_year'])

# 4. Split, convert to sorted arrays
prev_arr  = safe_to_array(bp_col.filterDate(prev_start,  prev_end ).sort('system:time_start'))
focal_arr = safe_to_array(bp_col.filterDate(focal_start, focal_end).sort('system:time_start'))
next_arr  = safe_to_array(bp_col.filterDate(next_start,  next_end ).sort('system:time_start'))

# 5. Compute metrics
metrics = compute_bp_ts_metrics(focal_arr, prev_arr, next_arr)

# 6. n sentinels for non-fittable classes (n band always unmasked)
n_final = (metrics.select('n')
           .where(veg_fire_img.eq(24), ee.Image.constant(-1))
           .where(veg_fire_img.eq(25), ee.Image.constant(-2)))
NON_N_BANDS = ['delta3_peak','minfore3_peak','jumpgap3','prevwidth3','postwidth3','date_post3',
               'delta2_peak','minfore2_peak','jumpgap2','prevwidth2','postwidth2','date_post2',
               'pmax3','pmax2','pmax1','timediff_med','timediff_max']
result = metrics.select(NON_N_BANDS).addBands(n_final.rename('n')).toFloat()

# 7. Export
asset_name = f"bpts_{year}_{tile_id}"
ee.batch.Export.image.toAsset(
    image=result.set({'year': year, 'tile_id': tile_id, 'system:time_start': ...}),
    description=asset_name,
    assetId=f"{C.BP_TS_METRICS_COL}/{asset_name}",
    region=tile_geom,
    scale=30,
    crs='EPSG:4326',
    maxPixels=int(1e10),
)
```

---

## Notes and gotchas

- **Code style:** heavily commented (Ivan's preference). Functions should express each step clearly. See `03-bp_computation.md` and `03-bp_ts_metrics.md` for the design rationale.
- **Coefficients are on raw scale** — no centering, no standardisation before products.
- **Term order matters** for aligned multi-band multiply: factors selected from images must be in the same order as the coefficient bands.
- **`arrayProject([0])`** on [N,1] array gives 1D [N] — needed as sort key for `arraySort`.
- **`arraySort(keys)`** sorts ascending; negate keys for descending (find argmax).
- **`updateMask(cond.gte(threshold))`** leaves UNMASKED where condition is true.
- **`safe_to_array` empty stub:** `ee.Array([[0.0, 0.0]]).slice(0, 0, 0)` gives shape [0, 2].
- **Non-fittable pixels (veg_fire 24/25):** masked from BP computation via `is_fittable`; n sentinel applied after metrics.
- **Testing script:** `scripts/test-03-bp_ts.py` — calls `bpts(year, tile_id, export=False)` and displays on map. First validate with 2015, tile `SK-19-Y-A` (Cholila fire in Feb 2015 should show a large area with high delta and prob in the Patagonia forest zone).
- **CLAUDE.md:** already updated — read `03-bp_computation.md` and `03-bp_ts_metrics.md` for design context before implementing.
