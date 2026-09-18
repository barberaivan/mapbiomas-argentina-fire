> **Extracted from** `collection-01/docs/06-object_model.md` §10 "The collection-00 empirical
> filter, as a baseline" and §11 "Where to look first" @ `fc6ddef` (2026-09-18).
> Lab notebook — the record of building the step, not documentation of it.

# 06 — The collection-00 empirical filter, measured

The filter is still computed (`objects_data_functions.R::c00_pass`) and still lands in the QGIS
inspection layer as `c00_pass` / `c00_case` / `verdict` — that much is live. Where it breaks, and
the full disagreement table, are here.

## 10. The collection-00 empirical filter, as a baseline

Reproduced verbatim in `objects_data_functions.R::c00_pass`. Against the 5255 labels: **accuracy
0.62, sensitivity 0.50, specificity 0.77, precision 0.70** — versus 0.79 / 0.72 / 0.87 for BART
out-of-fold at 0.5, or 0.81 / 0.85 / 0.78 at the deployed cuts. Where it breaks (from
`scripts/objects_data_explore.R`):

- **Case 1 (1–50 ha) has sensitivity 0.19** — it discards 81 % of the real fires in the band holding
  83 % of all objects. One threshold does nearly all the damage: `burned_around_3 > 0.7` cuts **81 %
  of the FIRE objects** there (and 90 % of the non-fire) — in collection 1 that band's fire objects
  sit at a median `burned_around_3` of 0.58, well below the cut.
- **Case 3 (≥ 300 ha auto-accept) has precision 0.77** — 166 of the 732 labelled objects above
  300 ha are non-fire, so "very large is rarely non-fire" does not hold here. Those objects supply
  **69.6 % of all the area the filter keeps**, so the assumption is load-bearing.
- `circularity > 0.01` is **inert** (cuts 0.0 % of fire, 0.4 % of non-fire); `shape_index < 7` is the
  one term working as intended (cuts 20 % of fire vs 48 % of non-fire in case 2).
- On the full population it keeps **23.8 % of objects / 80.6 % of the area**, stable across years
  (18.5–27.5 %).

Keep the filter only as a **baseline to compare against**, and as the source of the two ideas worth
keeping — the hard small-object cut, and size-stratified reasoning. The model replaces the
thresholds.

## How the two calls disagree, across all 28 fire-years

Across all 28 fire-years the model and the collection-00 filter **disagree on 26.6 % of the object
area** (58–70 % of objects, year by year), and the disagreement is cleanly structured — `c00 only`
is *large* objects, `model only` is *small* ones:

| verdict | objects | area (kha) | mean ha | mean `p_mean` | mean `p_width` | % of area |
|---|---|---|---|---|---|---|
| both | 318 565 | 57 462 | 180 | 0.785 | 0.302 | 67.6 |
| **c00 only** (filter keeps, model rejects) | 83 122 | 11 051 | 133 | 0.161 | 0.316 | 13.0 |
| **model only** (model keeps, filter rejects) | 976 781 | 11 597 | 12 | 0.719 | 0.353 | 13.6 |
| neither | 310 915 | 4 880 | 16 | 0.088 | 0.220 | 5.7 |

**Start with `"verdict" = 'c00 only' AND "area_ha" >= 300`.** That is **5872 objects holding 6397 kha
— 7.5 % of all object area** — where the old filter auto-accepts under its `>= 300 ha` rule and the
model rejects *without confidence* (mean `p_mean` 0.35, mean `p_width` 0.46). It is the
highest-area-stakes set in the collection, small enough to walk object by object, and at `>= 300 ha`
each one is unmistakable against imagery. Whatever is decided there moves the headline number more
than anything else in step 06.

By contrast `model only` below 1 ha is **31 933 objects for 22 kha** — 0.03 % of area. Worth a
glance to see *what* they are, not worth arguing about.
