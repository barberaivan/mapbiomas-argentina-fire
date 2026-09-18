> **Extracted from** `collection-01/validation/docs/design.md` Appendix B @ `54e3e8d`
> (2026-09-18) — **this recipe does not work at country scale**; see
> [`implementation-log.md`](implementation-log.md) and `validation/02_sample_pool.py`.
> Lab notebook — the record of building the step, not documentation of it.

# Appendix B — the `stratifiedSample`-per-stratum draw (SUPERSEDED, does not scale)

Kept because it is what the design originally specified and what two weeks of OOM debugging were
aimed at, and because `validation/colab_sample_pool_export.ipynb` (2026-08-28) still implements
**this** recipe rather than the one that works. The working implementation draws an *unstratified*
pool with `Image.sample()` and splits by stratum locally in pandas
(`02_sample_pool.py`, module docstring "LA SAGA DEL OOM Y LA CAUSA REAL").

## Appendix B — the frozen ordered lists (GEE)

One export per stratum per year. Draw 6,000, keep the first 5,000 by rank (§5 rule 2).

```javascript
var FY = 2015, H = 1, SEED = 42;      // stratum H in {1,2,3}; SEED fixed and recorded forever
var img = ee.Image(ee.ImageCollection(
      'projects/mapbiomas-argentina/assets/FIRE/VALIDATION/sampling_strata')
    .filter(ee.Filter.eq('collection', 1))
    .filter(ee.Filter.eq('year', FY)).first());   // 'year' is the FIRE year

// sample the map call alongside the stratum, so the CSV is self-contained (S4)
var pool = img.select('stratum').eq(H).selfMask().rename('sel')
             .addBands(img.select('stratum'))
             .addBands(img.select('burned'))
             .addBands(ee.Image.random(SEED).rename('order_key'));

var pts = pool.stratifiedSample({
  numPoints: 6000,                    // over-draw; truncate to 5000 after sorting
  classBand:  'sel',
  region:     ee.FeatureCollection('projects/mapbiomas-argentina/assets/ANCILLARY_DATA/' +
                'VECTOR/ARG/ARG-Political_Level_1-Pais').geometry(),
  projection: ee.Projection('EPSG:4326', [0.000269494585236, 0, -73.58468801489491,
                                          0, -0.000269494585236, -21.764113209062533]),
  seed: SEED, geometries: true, tileScale: 8, dropNulls: true
}).sort('order_key');

Export.table.toDrive({
  collection:  pts,
  description: 'val10_sample_fy' + FY + '_s' + H,
  fileFormat:  'CSV'});
```

Each row comes out with `stratum`, `burned`, `order_key` and a point geometry. Then, locally and
once: verify the row count, assert `burned == (stratum == 1)` (§4), keep the first 5,000 rows, add
`rank` as the row index, derive `col` / `row` from the pixel-centre lon/lat (§5 rule 4), drop `sel`
and `order_key`, and archive the CSV together with the seed, `Nh`, the strata asset id and the date.
**Never regenerate or re-sort it.**
