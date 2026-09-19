# Validation — sampling design

How the collection-1 burned-area product is validated: a **stratified random sample of pixels**
with known inclusion probabilities, analysed with the **Olofsson / Stehman** design-based
estimators, producing accuracy metrics **and an error-adjusted national burned-area estimate with
confidence intervals**. Validation is **episodic** — it is not a stage of the mapping chain, it
consumes the finished map — which is why it lives beside its code rather than in `docs/`.

Everything here is fixed by design and must be frozen before any interpretation begins. The two
artefacts that cannot be retrofitted are **the strata rasters** and **the ordered sample lists**.

---

## ⚠️ Status, and one thing to settle before interpreting

**Nothing has moved since 2026-08-31.** Landed: the three strata rasters (fire-years 2003, 2013,
2022), the nine frozen ordered lists (3 years × 3 strata) and the three `ceo_points_fy<FY>` GEE
table assets. Interpretation has not begun. The lists are written to `validation/outputs/frozen/`,
which is **not tracked in this repo** — they live on the machine that ran the draw.

**Still open**: the second pool, which extends the frozen lists to the full 5,000-unit reserve
("Drawing the frozen ordered sample lists"); the exact-`Nh` pixel census, whose `weights_launch()`
in `01_strata_export.py` was never re-tested after the frame-geometry fix and very plausibly now
works; and the validator-facing `ceo_val_00_template` script in the `fuego` repo, which still
points at the demo asset.

The paths that were tried and abandoned on the way here — and must not be taken again — are listed
in [`notes/abandoned-paths.md`](notes/abandoned-paths.md).

> ### ⚠️ The strata were built against the **v1** map, and the product is now **v2**
>
> Found in this review (2026-09-18), not previously recorded. The strata rasters were exported on
> 2026-08-31, when `C.MONTH_OF_BURN_COL` resolved to `collection1_fire_mask_v1`;
> `C.PRODUCT_VERSION = 2` landed on 2026-09-11 (`8cf4b7f`), and the published month-of-burn
> collection is now `_v2` — the layer with exclusion rules A and B applied
> (`docs/07` "The `_v2` re-export"). So **`S1` is v1's burned pixel set, and the frozen `burned`
> band records v1's call.**
>
> This does **not** invalidate the sample. The estimators require only that the strata partition
> the population and that the weights are known, and both still hold — a stratum is allowed to be
> defined by anything, including a superseded map. What it does invalidate is one rule below:
> **"Estimators and outputs" says the map class is the frozen `burned` band and is never looked up
> later.** Against v2 it must be looked up again, at the same pixel addresses, or the confusion
> matrix describes the wrong map. The `col`/`row` addresses stored with every unit exist precisely
> so that is possible.
>
> **To settle before interpretation**: re-sample `burned` from v2 at the frozen addresses and add
> it as a second column (keeping v1's, which is what defines the strata), and recompute `W2` — v2
> is a smaller burned set, so `W1` shrinks and some S1 pixels are no longer mapped-burned. Whether
> the strata themselves should be rebuilt on v2 is a bigger call: rebuilding means new lists and
> discards the frozen ones.

---

## Decisions already taken

| | |
|---|---|
| Method | Olofsson et al. (2014) design-based estimation; Stehman (2014) estimators |
| Population | **Whole country**, not only burnable land cover — `ARG-Political_Level_1-Pais`, 279.27 Mha |
| Sampling unit | One **30 m pixel** on the product grid, labelled burned / not burned for the fire-year |
| Temporal unit | **Fire year** (1 May Y → 30 Apr Y+1), named by start year — never calendar year |
| Strata | S1 mapped burned · S2 independent fire evidence, dilated, minus S1 · S3 the rest |
| Strata asset | `projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata` — one 2-band image (`stratum`, `burned`) per fire year, keyed by the `year` + `collection` properties |
| Years | **Three, to be defined** — see "Choosing the three years" for the constraints |
| Initial sample | **100 units per stratum per year** (n = 300/year) |
| Pre-drawn reserve | **5,000 units per stratum per year**, ordered, fixed seed — the sample can be extended later without redesign |
| Regionalization | None. Per-ecoregion figures, if ever wanted, come from the same sample as subpopulation estimates |
| Scope | Annual burned / not burned only. Month-of-burn accuracy is **not** assessed |

The primary reported result is **error-adjusted burned area with a 95 % CI**. Overall, user's and
producer's accuracy with standard errors are secondary.

---

## Why not the Alencar et al. (2022) design

Alencar (MapBiomas Fogo Brasil col-1, their §2.5) stratifies 2 × 2 km cells by FIRMS burned fraction,
then has interpreters segment each cell and records **the centroid of each interpreter-drawn
segment** as the sample unit. Three consequences:

- **No defined inclusion probability.** Whether a given pixel enters the sample depends on how the
  interpreter segmented the chip, which breaks the probability-sampling requirement the estimators
  rest on.
- **Rare-class weights applied post hoc** to the confusion matrix, rather than designed in — a patch
  for a design that gave no control over how many mapped-burned units would be drawn.
- **No area estimate.** Only OA / UA / PA and commission / omission. For a product whose headline
  number is "X hectares burned in year Y", the error-adjusted area with a CI is the deliverable
  that matters, and it is nearly free once a probability sample exists.

The sample-size formula itself is not the disagreement — Alencar's Eq. 2 is Cochran's
single-proportion formula, the same one Olofsson gives as a starting point. What follows it is.

---

## Every layer must be a fire-year layer

Our product is published as calendar-year images, but the objects, and therefore the thing being
validated, are fire-year entities. So **every** layer entering the design — ours and every external
product — is built by selecting the window **1 May Y → 30 Apr Y+1**.

**Our layer** comes from the month-of-burn collection
(`C.MONTH_OF_BURN_COL`, band `burned_monthly`, values 1–12, one image per calendar year, already
filtered to `fire == 1 & area_ha >= 1`):

```
FY(Y) burned  =  (burned_monthly[Y] >= 5)  OR  (burned_monthly[Y+1] <= 4)
```

This is exact, because step 07 assigned the month and calendar year **per pixel** from `abs_date`.
It also reconstructs precisely what a user of the published product sees, which is the right thing
to validate. It requires calendar year Y+1 to exist, so the validatable range is **FY 1999–2024**
(the collection holds calendar 1999–2025).

**External products** are ImageCollections with dates, so the same window is just
`filterDate(YYYY-05-01, (YYYY+1)-05-01)`. MCD64A1, VNP64A1 and FireCCI51 are *monthly composites*:
a composite straddling the window boundary is included **whole** rather than split by its
`Burn_Date` band. S2 favours recall ("Why a union, dilated"), so over-inclusion at the boundary is the safe error.

---

## Building the strata rasters

One raster per validated fire-year. Pure raster algebra — dilation on binary masks plus boolean
logic, no vectorization anywhere. Export once as a GEE asset, record the fingerprint, **never
regenerate**.

```
S1 = our_burn
S2 = dilate( our_burn OR mcd64 OR vnp64 OR firecci OR firms )  AND NOT our_burn
S3 = NOT S1 AND NOT S2
```

Each image carries **two bands**:

| band | values | what it is |
|---|---|---|
| `stratum` | 1 / 2 / 3 | the partition — what the sample is drawn from |
| `burned` | 0 / 1 | **our map's own call** for that fire year, i.e. `our_burn` |

Carrying `burned` means the drawn points record what the product says as well as which stratum they
came from, so the confusion matrix and every accuracy metric can be built straight from the sample
CSV with no raster lookup afterwards. By construction `burned == (stratum == 1)`, which makes it a
free consistency assertion on every drawn list — and it stops being redundant the moment a later
collection changes the map, because the frozen band still says what the map said when the strata
were fixed.

### Why a union, dilated, and why recall beats precision

A **union**, not an intersection: intersecting our buffered scars with MODIS burn would return only
near-misses next to scars we already found, and would exclude a fire we missed entirely — the case
S2 exists to catch. Because dilation distributes over union, one `focalMax` delivers both omission
types at once:

| component | catches |
|---|---|
| external products, dilated | fires missed **entirely** — MODIS/VIIRS saw it, we did not |
| our own layer, dilated | scars found but drawn **too small** — omission concentrates at scar edges (Olofsson et al. 2020) |

Both are needed: evidence-only misses edge omission on the small grassland and agricultural fires
the coarse sensors never detect; edge-only misses whole fires.

**Design rule: favour recall over precision in S2.** Over-inclusion only enlarges `W2`, which costs
a little sample efficiency. Under-inclusion pushes omission into S3, which carries ~94 % of the area
weight and therefore most of the variance ("Sample size, and how to extend"). Two direct consequences: no `confidence` filter on
FIRMS, and **`max`, never `mode`, as the aggregation reducer** ("The aggregation rule").

### The coarse grid must be nested

The dilation runs at ~500 m so the kernel stays a 3 × 3 instead of a 33 × 33. But the coarse
lattice must be **our product grid decimated by an integer**, not an independent 500 m grid and not
the MODIS sinusoidal grid. If it is not nested, the final coarse → 30 m reprojection resamples,
S2's boundary lands mid-pixel, it shifts between years, and the raster cannot be reproduced.

```
base   crs = EPSG:4326   transform = [ 0.000269494585236, 0, -73.58468801489491,
                                       0, -0.000269494585236, -21.764113209062533]
COARSE = base transform × 16  (same origin)
       = [ 0.004311913363776, 0, -73.58468801489491,
           0, -0.004311913363776, -21.764113209062533]        ≈ 480 m N–S
```

Every coarse cell is then an exact 16 × 16 block of product pixels: aggregation is exact and
coarse → 30 m is pure block replication with no resampling ambiguity. 480 m rather than 500 m costs
nothing.

`base` is `C.SNIC_CRS` / `C.SNIC_TRANSFORM` — the one pinned grid of the whole collection. Pin
`crs` + `crsTransform` on **every** reprojection and export. `scale: 30` in EPSG:4326 is a
*different* grid and a half-pixel shift would misalign S1 against the strata raster.

### The aggregation rule — `max`, never `mode`

| relation to COARSE | operation | why |
|---|---|---|
| finer or ~equal (ours 30 m, FireCCI 250 m, VNP64A1 & MCD64A1 463 m) | `unmask(0).reduceResolution(max, maxPixels: 1024).reproject(COARSE)` | never drops a detection |
| coarser (FIRMS 927 m) | `unmask(0).reproject(COARSE)` | nearest replicates the coarse cell into ~2 × 2, loses nothing |

`maxPixels: 1024` is required — the default of 64 is below the 256 input pixels of a 16 × 16 block.

**`max`, not `mode`.** At 16 × 16 a coarse cell holds 256 product pixels, so `mode` means "burned
only if more than 128 pixels burned" — roughly >10 ha *inside that single cell*. Our minimum mapped
fire is 1 ha (`C.MIN_FIRE_HA`), so `mode` would delete most small fires from the union outright and
erode every scar to its core; on the sparse coarse-sensor detections it is worse still. The pixels
it deletes do not disappear — they fall into **S3**, where they carry area weight ~0.94 and inflate
the variance. `mode` is correct for downsampling a categorical map for display; here it inverts the
design goal.

Note that `.reproject(COARSE)` on a 463 m product using nearest neighbour would drop isolated cells
(output cells are slightly larger than input), which is why the first row of the table uses
`reduceResolution` even where the ratio is only 1.04.

### Dilation, partition, export

- **Dilation**: `focalMax({radius: 1, units: 'pixels', kernelType: 'square'})` on the coarse union
  — a 3 × 3 coarse window, ±480 m. Because `max`-aggregation already inflates by up to one coarse
  cell before the dilation, the effective buffer around any burned pixel is **~0.5–1.0 km**, i.e.
  16–32 Landsat pixels. That is well clear of the 1–3 pixel buffers Olofsson et al. (2020) show to
  be too small to reduce the standard error. The projection is set *before* the neighbourhood
  operation so the kernel is fixed to the coarse grid.
- **Subtract S1 at 30 m, not at coarse resolution**, so S1 is exactly the product's own pixel set
  and the partition is exact.
- **Clip to the population frame** — `ARG-Political_Level_1-Pais`, the unbuffered country. The
  products are exported over `C.ARG_BUFFER_FC` (282.39 Mha), which is a superset, so no product
  pixel is missing from the frame.
- **Export**, one image per fire year, into the already-created ImageCollection

  ```
  projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata
  ```

  with `crs` + `crsTransform` pinned and `pyramidingPolicy: {'.default': 'mode'}` (categorical —
  never `mean`). Two properties are **mandatory**, because together they are how downstream steps
  select an image:

  | property | value | note |
  |---|---|---|
  | `year` | the **fire year** — start year of 1 May Y → 30 Apr Y+1 | never a calendar year |
  | `collection` | `1` | integer, as on every other published asset |

  Set the provenance on the asset too, rather than only in a log: `coarse_factor`,
  `dilation_radius_px`, `products` (which external products entered the union), `frame`, `bands`,
  plus the house-style `source` / `region` / `fire_year_definition`.
- **Record `Nh`**, the per-stratum pixel count from a `frequencyHistogram`. It serves twice: the
  stratum weights are `Wh = Nh / ΣNh`, and since GEE assets cannot be checksummed the histogram is
  the reproducibility fingerprint. Log it with the asset id, the export timestamp, the fire year,
  the dilation radius and the decimation factor.

The implementation — and the record of what was actually run — is `01_strata_export.py`.

### Which external products exist for which fire year

Verified in the GEE catalogue on 2026-08-21:

| product | id | native | coverage | fully covers FY |
|---|---|---|---|---|
| MODIS burned area | `MODIS/061/MCD64A1`, `BurnDate` | 463 m | Nov 2000 → | 2001 → |
| **VIIRS burned area** | `NASA/VIIRS/002/VNP64A1`, `Burn_Date` | 463 m | Mar 2012 → | 2012 → |
| FireCCI burned area | `ESA/CCI/FireCCI/5_1`, `BurnDate` | 250 m | 2001 – 2020 | 2001 – 2019 |
| MODIS active fire | `FIRMS`, `T21` | 927 m | Nov 2000 → | 2001 → |

VIIRS enters as a **burned-area** product, not active fire — `VNP64A1` is in the public catalogue
(172 monthly images, 2012-03 → 2026-06, on the same sinusoidal grid as MCD64A1), so no FIRMS-archive
download or ingest is needed. Do **not** use `NOAA/VIIRS/001/VNP64A1`, which is deprecated and only
spans 2014–2018.

**Use every product available in the given fire year.** A year with fewer auxiliary products gets a
weaker S2, which means more residual omission leaks into S3, which means a **wider confidence
interval** for the same sample size. It introduces **no bias**: each year is an independent
stratified estimate with its own strata and its own weights, and the estimator only requires that
the strata partition the population and that the weights are known. There is no reason to degrade a
recent year for consistency with an old one — but years must never be compared without reporting
their intervals.

### Check `W2` before freezing

`W2 = N2 / ΣNh` is computable from pixel counts alone, before a single unit is interpreted. Expect
a few per cent. If a year comes out very small (< 2 %) or very large (> 15 %), revisit the dilation
radius **then** — once the raster is frozen and the lists drawn, changing it is a new design and the
samples cannot be merged.

---

## Drawing the frozen ordered sample lists

This is the mechanism that makes every later extension legitimate, and it must be done once, before
any interpretation.

For each stratum of each year, draw **5,000 pixels** by simple random sampling in **random order**,
and store the list with its row order fixed. Interpretation proceeds strictly down the list;
extending the sample means continuing further down the same list. That is mathematically identical
to having drawn the larger sample from the outset, which is why no later phase needs any statistical
justification.

Rules:

1. **Simple random selection within each stratum, never systematic.** Systematic selection would
   force variance approximations and make extension awkward (Olofsson et al. 2014 §2.1.3; Stehman et al. 2012).
   It costs nothing to avoid.
2. **The draw is one unstratified pool per year, split by stratum locally** — `Image.sample()`
   with no `classBand` on the strata image, the `stratum` and `burned` bands sampled alongside
   the point, and the split into S1 / S2 / S3 done afterwards in pandas (`02_sample_pool.py`).
   Drawing within each stratum separately and drawing once and then conditioning on the stratum
   are the same thing statistically — conditioning on stratum commutes with a random draw — and
   the pool costs one GEE request per year instead of three. A per-stratum `stratifiedSample` at
   country scale does not run at all ([`notes/abandoned-paths.md`](notes/abandoned-paths.md)).
   **One frozen list per stratum per year** is still the output (9 lists for three years), so a
   shortfall in any stratum is visible instead of being silently redistributed: **over-draw to
   6,000 per stratum and keep the first 5,000 by rank**, and verify the row count of every list
   before freezing. Truncating a randomly ordered simple random sample is itself a simple random
   sample, so the truncation is valid.
3. **Pass `projection`, not `scale`**, to the sampler, built from the pinned crs + crsTransform,
   so the drawn points are exact product pixel centres. **Pass a plain rectangle as `region`**,
   never the country polygon — the reason is in
   [`notes/abandoned-paths.md`](notes/abandoned-paths.md); the points are cut to the frame by the
   strata image itself, which is already clipped to it.
4. **Store the pixel address, not only the coordinates.** From the pixel-centre lon/lat,
   `col = round((lon − x0)/dx − 0.5)`, `row = round((y0 − lat)/dy − 0.5)`. The address makes the
   unit recoverable years later independently of coordinate formatting.
5. **Store per row**: `fire_year`, `stratum`, **`burned`** (the sampled map call, "Building the
   strata rasters"), `rank`, `lon`, `lat`, `col`, `row`, plus two context columns sampled at the
   same time — `mb_class_raw` (the *raw* MapBiomas Argentina class of the calendar year before the
   fire year, not the `veg_fire` reclass) and `region_id`. Neither enters the estimator; they let
   the sample be read by land cover and by region afterwards. **Store per list**: the seed, `Nh`,
   the strata asset id and the source CSV.
6. **Never regenerate a list, never re-sort one, never discard or substitute a drawn unit.** If a
   unit is genuinely uninterpretable, record it as such and report it — deviations from probability
   sampling have to be documented, not repaired.
7. **Stop on precision, not on results.** Adding units because the standard error is still too wide
   is safe: that depends on `nh` and `Wh`, not on the labels. Adding units because "the accuracy
   looks bad, let us check further" makes the sample size a function of the observed data, which is
   the one thing that biases the estimator.

**The pool is built in two stages.** Pool 1 is sized only to clear the initial 100 per stratum per
year comfortably (~100–150 k points per year, seconds to minutes), so a wrong bet on the pool size
costs almost nothing; pool 2, which fills the lists to the 5,000-unit reserve, reuses the same draw
with a larger N and is appended after pool 1's ranks, de-duplicated on exact `(col, row)` — the
collision rate at these scales is ≈ 0.03 %. **Pool 1's rows and ranks are never touched** (rule 6).
Pool 2 is not built yet ("Status").

5,000 per stratum per year covers every scenario in "Sample size, and how to extend" with room to
spare — the most demanding one shown (±9 % on area) asks for 3,100 in S3, the stratum that needs
the most — and absorbs units discarded as uninterpretable. The reserve is a cost decision, not a
statistical one: it is what keeps the draw cheap at country scale. All three strata hold far more
than 5,000 pixels — even S1 holds on the order of ten million in a typical year — so drawing
without replacement is unconstrained.

**What is frozen is the lists and their order, not the allocation.** The estimator is unbiased for
any `nh` (Stehman et al. 2012 is precisely about extending a stratified sample after collection has
begun), so how far down each stratum's list we walk can be decided later, in the light of the
measured `Wh` and the interpretation rate.

---

## Sample size, and how to extend

Illustrative, for a typical fire year with `W = 0.009 / 0.050 / 0.941` and true-burned fractions
inside the strata of `0.85 / 0.042 / 0.00053` (≈ 2.9 Mha truly burned, ~25 % of it omitted by the
map). Variance of the stratified area estimator, `V = Σ Wh² · θh(1 − θh) / (nh − 1)`:

| S1 / S2 / S3 | n | ± on burned area | ± Mha | ± on UA of burned |
|---|---|---|---|---|
| **100 / 100 / 100** | **300** | **±46 %** | ±1.32 | ±7.0 pp |
| 300 / 300 / 300 | 900 | ±27 % | ±0.76 | ±4.0 pp |
| 200 / 600 / 1200 | 2,000 | ±15 % | ±0.43 | ±4.9 pp |
| 300 / 900 / 1800 | 3,000 | ±12 % | ±0.35 | ±4.0 pp |
| 500 / 1400 / 3100 | 5,000 | ±9 % | ±0.27 | ±3.1 pp |

The two objectives behave very differently. **User's accuracy of burned is respectable at 100 units
in S1**; the area interval at 100/100/100 is ±46 %, because 100 units in a stratum carrying 94 % of
the country's area is where all the variance sits. So the opening sample delivers a usable accuracy
assessment, and the area estimate is what the extension is for.

**Extend towards Neyman, not equally.** For the area objective the optimal shares here are
**S1 9 % / S2 29 % / S3 62 %** (`nh ∝ Wh·√(θh(1−θh))`), so the extension should go mostly into S2
and S3. Under those shares:

| target on area | n per year |
|---|---|
| ±30 % | ~500 |
| ±20 % | ~1,100 |
| ±15 % | ~2,000 |
| ±10 % | ~4,500 |

Standard errors scale as `1/√n`: **doubling the work narrows the interval by 41 %, not 50 %.** Plan
on square roots. And before buying precision with interpretation effort, buy it with a better S2
("Why a union, dilated" and "Check `W2` before freezing") — reducing residual omission in S3 is far cheaper than adding units.

Recompute all of this with the **measured** `Nh` once the strata rasters are frozen. The numbers
above are illustrative; only `Wh` is known exactly before interpretation, and `θh` is what the
validation itself estimates.

---

## Response design and interpretation

- A **written protocol before any interpretation**: what counts as burned, minimum detectable scar,
  how to treat partial burns within a pixel, how to handle agricultural residue burning. These are
  decided in advance, not during.
- **Blind labelling.** Interpreters must never be shown the product's label, and batches must mix
  strata and years in shuffled order — S1 is by construction mapped-burned, so a recognisable
  single-stratum batch leaks the map's answer and inflates agreement. This is also why phases should
  advance across all years together rather than finishing one year at a time: if interpreters drift
  over a long campaign and one year is interpreted mostly at the start, drift becomes correlated
  with year, which is precisely the variable being compared.
- **The segmentation workflow can be kept as an interpretation aid** — show the interpreter a
  segmented chip if that helps — but the unit entering the confusion matrix is the randomly drawn
  pixel, labelled by whichever segment it falls in. Same effort, valid design.
- **A training set with agreed answers** that every interpreter passes before contributing.
- **~10 % duplicate interpretation carried through the whole campaign**, not only at the start, to
  measure inter-interpreter agreement and detect drift. No sample size repairs an inconsistent
  response design.
- **Record the failure rate** — units where the imagery does not permit a confident call.
- **Timing by stratum, separately.** S1 and S2 units are ambiguous and slow; S3 units are
  overwhelmingly obvious non-burn and take seconds. A single average badly misleads the cost model.

**Reference imagery.** For recent years, Sentinel-2 at 10 m plus high-resolution imagery in Google
Earth. For years before ~2000 there is nothing finer than Landsat itself, so the reference must be
superior *temporally* instead: a dense Landsat NBR/dNBR trajectory for the pixel rather than one or
two date composites. The full annual trajectory plus human judgement is genuinely more information
than the classifier uses, even at the same spatial resolution. It must nonetheless be reported as a
limitation — where reference and map derive from the same imagery their errors may be correlated and
the accuracy estimates are optimistic.

---

## Choosing the three years

Constraints, not a decision:

- **FY 1999–2024** is the validatable range ("Every layer must be a fire-year layer").
- **FY 2012 onwards** has all four auxiliary products, so the strongest S2 and the tightest interval
  for a given effort. **FY 2001–2011** has MCD64A1 + FireCCI51 + FIRMS. **FY 1999–2000** has only
  partial MODIS coverage and would get a markedly weaker S2.
- The **sensor eras** worth spanning are Landsat 5 + 7 SLC-on (to Apr 2003), Landsat 7 SLC-off
  (2003–2012, with **FY 2012 the thinnest year in the archive** — L5 retired Nov 2011, L8 launched
  Feb 2013), and Landsat 8/9 (2013 →).
- **Fire regime** matters as much as sensor regime: a mega-fire season behaves differently from a
  moderate one. Large contiguous scars are easy; smoke, repeated burns and saturated composites are
  not. Rank the candidate fire years by mapped burned area from the product itself, and by national
  SNMF statistics, before deciding.
- Reference-imagery quality improves monotonically with year ("Response design and interpretation"), which argues for at least one
  recent year.

---

## Estimators and outputs

Our strata **nest within** the map classes: S1 is exactly the mapped-burned class, and
S2 ∪ S3 is exactly the mapped-unburned class. That is a special case of "strata different from map
classes", so use **Stehman (2014)** — `mapaccuracy::stehman2014()` in R, which handles it correctly.
Do **not** use `mapaccuracy::olofsson()`, which assumes strata = map classes.

The map class of each unit is not looked up later — it is the **`burned` band sampled at draw
time** ("Building the strata rasters"), already in the CSV. Interpretation adds one column, the
reference label, and the confusion matrix follows.

> ⚠️ **That rule has an exception as of the `_v2` re-export**: the frozen `burned` band records
> the **v1** map's call, so for v2 the map class *must* be re-sampled at the frozen `col`/`row`
> addresses. See the status box at the top. The strata themselves, and therefore `Wh`, are
> unaffected in their validity — only the map class is.

Report, per validated fire year:

- **Error-adjusted burned area with a 95 % confidence interval** — the primary result.
- **Overall, user's and producer's accuracy, each with its standard error.**
- The mapped area alongside the estimated area, so the correction is visible.
- `Nh`, `Wh`, `nh`, the strata asset ids and the seed, so the estimate is reproducible.
- The count of uninterpretable units, and the inter-interpreter agreement.

---

## References

- Olofsson, P., Foody, G.M., Herold, M., Stehman, S.V., Woodcock, C.E., Wulder, M.A. (2014). Good
  practices for estimating area and assessing accuracy of land change. *RSE* 148:42–57.
  DOI 10.1016/j.rse.2014.02.015 — the canonical reference: sampling design, response design,
  estimators, sample size.
- Olofsson, P. (2025). Accuracy and Area Estimation. In *Comprehensive Remote Sensing*, 2nd ed. —
  more readable synthesis, good entry point.
- Stehman, S.V. (2014). Estimating area and map accuracy for stratified random sampling when the
  strata are different from the map classes. *IJRS* 35(13):4923–4939.
  DOI 10.1080/01431161.2014.930207 — **the estimator used here.**
- Stehman, S.V., Olofsson, P., Woodcock, C.E., Herold, M., Friedl, M.A. (2012). A global land-cover
  validation data set, II. *IJRS* 33(22):6975–6993. DOI 10.1080/01431161.2012.695092 — extending a
  stratified sample after collection has begun.
- Olofsson, P., Arévalo, P., Espejo, A.B., et al. (2020). Mitigating the effects of omission errors
  on area and area change estimates. *RSE* 236:111492. DOI 10.1016/j.rse.2019.111492 — why buffer
  strata must be generous.
- Cochran, W.G. (1977). *Sampling Techniques*, 3rd ed. Wiley.
- Alencar, A.A.C. et al. (2022). Long-term Landsat-based monthly burned area dataset for the
  Brazilian biomes using deep learning. *Remote Sensing* 14(11):2510. DOI 10.3390/rs14112510.

The Olofsson and Alencar PDFs are not tracked in this repo — fetch them alongside this doc.
R implementation: package **`mapaccuracy`**.

---

## Run

```bash
$PYTHON collection-01/validation/01_strata_export.py --launch        # the strata rasters
$PYTHON collection-01/validation/02_sample_pool.py --pilot-launch    # size the pool
$PYTHON collection-01/validation/02_sample_pool.py --pilot-report
$PYTHON collection-01/validation/02_sample_pool.py --launch-pool
$PYTHON collection-01/validation/02_sample_pool.py --freeze --from-pool
$PYTHON collection-01/validation/03_ceo_export.py                    # the CEO upload CSVs
```

Namespace every task description (`val10_…`): the compute project is shared with the whole
MapBiomas Fuego network and `ee.data.listOperations()` returns every user's tasks.

## Files

| File | Role |
|---|---|
| `validation/01_strata_export.py` | build and export the strata rasters; the `Nh` census |
| `validation/02_sample_pool.py` | draw the pool, split by stratum, freeze the ordered lists |
| `validation/03_ceo_export.py` | the CEO upload CSVs — `LON`/`LAT`/`PLOTID` only, shuffled |
| `validation/demo_small_region.py` | a tutorial over a small region; not part of the frozen design |
| `validation/colab_sample_pool_export.ipynb` | ⚠️ superseded — it implements the per-stratum draw that does not run at country scale ([`notes/abandoned-paths.md`](notes/abandoned-paths.md)) |
| `ceo_val_00_template` (GEE, `fuego` repo) | the validator-facing script; still points at the demo asset |

## Related

- [`../../docs/07-vector_to_raster.md`](../../docs/07-vector_to_raster.md) — the product being
  validated, the pinned grid, and the `_v2` re-export.
- [`notes/abandoned-paths.md`](notes/abandoned-paths.md) — the routes this design tried and
  dropped, and why none of them should be tried again.
- `notebooks/validation_year_selection.qmd` — the evidence behind "Choosing the three years".
