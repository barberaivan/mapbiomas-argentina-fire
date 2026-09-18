# 02 — Burn probability per observation (the fitted model in GEE)

This is the product of the spectral stage: for one 30 m pixel on one Landsat date, the
probability that it is burned. `02-model_fitting.md` produces the coefficients — one CSV per
`veg_fire` class; this doc is how those CSVs become a probability **image** inside GEE. It
decides nothing, and it is never written to an asset: the probability exists only inside step
03's computation, which reads it as a time series.

## Foundations

**The year is the unit of work, and that is a choice.** Mapping change across decades of Landsat
is expensive, and there are methods that avoid discretising time at all: CCDC fits a continuous
harmonic model per pixel and flags breaks in it (Zhu & Woodcock 2014), and CODED extends that
idea to forest degradation with spectral unmixing (Bullock et al. 2020). MapBiomas instead works
in **discrete annual units**, and so does this collection — the product is one burned-area map per
year, so aggregating the raw Landsat information by year is the natural shape for everything
upstream of it. That decision is what makes the per-observation probability an *intermediate*.

**And the intermediate is not materialized, which is a size argument.** Over the padded window a
*carta* is covered by roughly 150 image **dates** (~294 raw scenes, collapsed by
`mosaic_by_date`), so storing the probability per observation would mean ~150 layers per
tile-year where the annual summary exported by step 03 has 16 bands — an order of magnitude more
data than a product that is itself ~55 GiB per year, over 248 tiles × 27 years. And nothing
downstream wants a single observation's probability: what carries the evidence is the *shape* of
the series, which step 03 reduces on the fly. Since the model is a coefficient set plus a dot
product, recomputing it inside the graph is cheaper than writing it out and reading it back.

> **~150 dates is not `n`.** The two counts are different things and it is worth keeping them
> apart. **~150** is how many date-mosaics *the graph evaluates* over a carta — every model
> evaluation is paid on all of them, which is why it drives cost. **`n`** is how many of those
> dates leave a *valid* observation at a given pixel after cloud masking: tens, not hundreds
> (mean 25, max 54 over a 2015 Patagonian carta; up to ~75 where coverage is best). A pixel is
> judged on `n` observations; the tile is billed for ~150.

> **A *carta*** is one sheet of the MapBiomas Argentina working grid
> (`C.CARTAS_FC` = `projects/mapbiomas-chaco/BASE/cartas-argentina`), the national 1:250,000
> chart series: the id in `grid_name` names the million-sheet and its subdivisions
> (`SK-19-Y-A`), and each sheet covers ~14,000 km². The grid has ~286 sheets and **248 intersect
> the buffered country**, which is the tile set every image-based GEE step here runs over —
> *not* Landsat WRS-2 path/row, and not an arbitrary bounding box.

**One model per vegetation class, applied without branching.** 23 fittable `veg_fire` classes
mean 23 coefficient sets, and the obvious implementation — evaluate each model on its own masked
subset and mosaic the results — would build 23 parallel branches of the same graph. Instead the
*class selection is pushed into the data*: every term becomes **one band whose per-pixel value is
that pixel's class's coefficient** (see "From CSV rows to coefficient bands"). Prediction is then
a single arithmetic expression over the whole image, identical everywhere, and choosing the model
costs nothing at evaluation time. This is what `02-model_fitting.md` "Foundations" means by the
prediction pipeline building one band set and reusing it for all classes — it is also why the
predictor set has to be shared across classes in the first place.

## Inputs → Outputs

`one Landsat observation + prev-year MB mosaic + veg_fire + P050 coefficients` → **burn
probability** → `a 2-band [prob, day_num] image, in memory only`

| Input / Output | What it is | Where |
|---|---|---|
| Coefficients | the deployed model, one CSV per fittable class, raw scale | `models/P050/` (`C.COEF_DIR`), parsed by `load_all_coefficients` |
| `veg_fire` | previous-year LULC × region — the class that selects the coefficients | `F.veg_fire_image`, `C.REGION_RASTER`, `02-vegetation_remap.md` |
| MapBiomas annual mosaic | previous-year spectral summaries (`med`/`wet`/`dry`/`sd`) | `F.get_mb_mosaic_bands` |
| Landsat observation | one cloud-masked scene with the fire indices added | `F.get_landsat`, `F.add_indices` |
| **Output** | `prob` + `day_num`, masked to fittable pixels, carrying the scene's timestamp | `compute_burn_prob_img` — consumed by step 03, never exported |

## How it works

### Which model judges the pixel

`veg_fire` is the previous-year MapBiomas class crossed with the region raster
(`region_id * 100 + mb_class`, remapped by `C.VEG_FIRE_TO`); pixels outside any region or with an
unmapped class fall through to the **non-observed sentinel 25**, non-burnable covers to **24**,
and only classes 1–23 are predicted at all (`is_fittable`). The LULC year is
`min(year − 1, C.MB_LIMIT_YEAR)`. Reading the context from `y−1` is what keeps the fire being
detected out of the evidence used to detect it.

### From CSV rows to coefficient bands

`load_all_coefficients` reads every class's CSV into one term list, and `_parse_term` recovers
each term's factors from its name: `_t` is a focal index (`BLUE_t` → `BLUE`, matching
`add_indices`), a summary suffix is a mosaic band via `C.PREV_SUFFIX_MAP` (`GREEN_med` →
`mb_mos_green_median`), `A__B` is a product, and `(Intercept)` becomes `intercept_term` because
parentheses are illegal band characters.

`build_coeff_image` then turns that list into **one band per term**, each band written by
`veg_fire.remap(FITTABLE_VEG_FIRE, [coef_class1 … coef_class23], 0.0)` — so a pixel of class 7
carries class 7's coefficient for every term, and its neighbour of class 12 carries class 12's,
in the same band. Non-fittable classes get 0 and are masked out anyway. The whole per-class model
structure has become a stack of images; the prediction below never mentions a class.

The band count of that stack **is** the compute cost, which is why the deployed folder holds only
the terms it deploys: `load_all_coefficients` builds one band per CSV row, so a trimmed CSV
genuinely computes less (`02-model_fitting.md` "Key decisions" for why P=50, and
`notes/03-performance_profile.md` for what it bought).

### The linear predictor, on the raw band scale

Every CSV exports **raw-scale coefficients** — the mean-centering used while fitting is folded
into the intercept and the main slopes (`models/README.md`) — so prediction is a plain dot
product with no centering before products: intercept + prev-year mosaic mains + focal spectral
mains + focal×focal + prev×focal, through a logistic. `compute_burn_prob_img` assembles the four
contribution groups by multiplying the relevant coefficient bands by the relevant feature bands
and summing with `ee.Reducer.sum()`.

**Every multiply renames first.** Rather than rely on GEE's band-matching rules, each feature
selection is renamed to the coefficient band names (`_select_renamed`) so both operands have
identical names in identical order — correct under any matching rule, and the reason a
coefficient can never be silently paired with the wrong band. The output carries the scene's
valid-data mask on both bands, so a cloudy pixel is *absent* rather than assigned a spurious
probability, and it keeps `system:time_start` because step 03 splits the resulting collection by
date.

### Applying it to a whole year is not quite this

The description above is the model for **one** observation, and running it literally per image
would recompute the previous-year half of the linear predictor ~150 times per tile-year for an
answer that cannot change. Step 03 therefore precomputes everything that is constant within a
focal year and multiplies in only the focal factor per image — a required optimisation, not a
cosmetic one, and one that only makes sense once a whole year's series is in view. See
[`03-bpts.md`](03-bpts.md) "What is precomputed per year".

## Key decisions

- **Class selection by coefficient remap, not by 23 masked branches.** One arithmetic expression
  over the whole image; the class only ever appears as the source of a band value.
- **Raw-scale coefficients.** The fit's centering is folded into the intercept and main slopes,
  so nothing is centred before a product is formed — this was checked explicitly against a
  hand-computed logit (`notes/03-validation_2015.md`).
- **Rename before every multiply.** Band alignment is made structural instead of relying on
  GEE's matching rules.

## Gotchas

- **The probability image is not an asset**, so it cannot be inspected the usual way: an
  interactive `getInfo` over the full graph hits the user memory limit (`03-bpts.md` "Gotchas").
  Sample a single Landsat image, or run `scripts/test-03-bp_ts.py`.
- **A pixel is masked, never zero.** No-data, cloud and non-fittable pixels contribute nothing;
  they are not observations with probability 0.
- **The code lives in step 03's script** (`workflow/03-bp_ts_metrics.py`), for the reason given
  in `03-bpts.md` "Foundations" — the probability and its reduction must run in one graph.

## Files

| File | Role |
|---|---|
| `workflow/03-bp_ts_metrics.py` | `load_all_coefficients`, `_parse_term`, `build_coeff_image`, `_select_renamed`, `compute_burn_prob_img` |
| `models/P050/` | the deployed coefficients (one CSV per fittable class) |
| `utils/functions.py` | `veg_fire_image`, `get_mb_mosaic_bands`, `get_landsat`, `add_indices` |
| `utils/constants.py` | `COEF_DIR`, `FITTABLE_VEG_FIRE`, `VEG_FIRE_TO`, `PREV_SUFFIX_MAP`, `MB_LIMIT_YEAR`, `REGION_RASTER` |
| `scripts/test-03-model_load.py` | asserts the deployed CSVs parse into the expected term set and build one band per term |
| `scripts/export_region_raster.py` | paints `C.REGION_RASTER` (the buffered region ids) |

## Related

- [`02-model_fitting.md`](02-model_fitting.md) — the fit that produces these coefficients, and why P=50; [`02-vegetation_remap.md`](02-vegetation_remap.md) — how `veg_fire` is built; `models/README.md` — the CSV schema.
- [`03-bpts.md`](03-bpts.md) — the only consumer: the time series this feeds, and the export.
- `notes/02-lr_term_reduction.md` (how the predictor set got to 50 terms), `notes/03-validation_2015.md` (the ~7e-9 check against a hand-computed logit).
- The two continuous-time alternatives named in Foundations: Zhu, Z. & Woodcock, C.E. (2014), *Continuous change detection and classification of land cover using all available Landsat data*, Remote Sensing of Environment (CCDC); Bullock, E.L., Woodcock, C.E. & Olofsson, P. (2020), *Monitoring tropical forest degradation using spectral unmixing and Landsat time series analysis*, Remote Sensing of Environment (CODED).
