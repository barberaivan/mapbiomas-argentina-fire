# 06 — Object labels: collecting and preparing the fitting set

The step-06 classifier is fitted on **~5 k fire / non-fire labels collected by hand**, one GEE asset
per collaborator, joined to the step-05 objects. This file covers where those labels come from, the
naming convention that carries their metadata, how they are matched to objects, and the cuts that
turn label↔object pairs into the fitting set. The classifier itself is
[`06-object_model.md`](06-object_model.md).

**The labelled sample is not a random sample of objects** — it was collected where fires were known
— and that single fact propagates into every number the model produces: per-year prevalence runs
0.00 to 1.00, small objects are under-sampled, and the deployed cuts are therefore a lower bound
(`06-object_model.md` "Foundations"). Fixing it is a **collection** task, not a modelling one: a
randomly sampled set of small-object labels (BACKLOG).

## Inputs → Outputs

step-04 `candseed` assets → hand-drawn layers in the Code Editor → one asset per collaborator →
**`scripts/objects_labels_prep.R`** → `polygons_data_merged.csv` → `clean_tagged()` → the fitting set

| | What it is | Where |
|---|---|---|
| **in** | the step-04 SNIC layer people draw on, one image per fire-year | `C.SNIC_COL` / `snic_<fy>` |
| **in** | step-05 objects and their metrics, for the join | `data/objects-raw/` |
| **out** | one downloaded GeoPackage per collaborator | `data/objects-labels/polygons_data_<author>.gpkg` |
| **out** | one row per (label, object) pair, metrics attached | `data/objects-labels/polygons_data_merged.csv` |
| **out** | *(in memory)* the clean fitting set — 5255 objects, 20 predictors | `objects_data_functions.R::clean_tagged()` |

## Collecting the labels in GEE

**Labels are collected on the step-04 SNIC `candseed` layer, not on uploaded objects.** That layer
already exists as a GEE asset per fire-year and shows, per pixel, candidate vs. seed on exactly the
clusters SNIC kept, so **shape and seed density — the most informative signal for fire vs. noise —
are fully visible without any polygons**. It also unblocked collection while step-05 vectorization
was still running: the object a point falls in does not change when the pixels are later
polygonized.

One `training_polygons_<author>` Code Editor script per collaborator draws `candseed` for each
fire-year in an exposed `(y_lwr, y_upr)` range, coloured per year. **The drawing-layer NAME is the
metadata** — each user keeps several layers split by class × year so they can place points fast, and
the script parses the name:

| layer name | class | fire-year(s) |
|---|---|---|
| `fire_YYYY` | 1 | `YYYY` |
| `nonfire_YYYY` | 0 | `YYYY` |
| `fire_YYYY_poly` / `nonfire_YYYY_poly` | as above | as above — `_poly` just records that polygons were drawn |
| `fire_YYYY_YYYY` (range) | 1 | **both ends inclusive** — written **once per year**, so every row carries one concrete `fire_year` |

Anything not named `fire_*` / `nonfire_*` is ignored on purpose (ROIs, bare `geometry*`, the
doubtful layers, imported vis params); to promote a doubtful layer, **rename** it. An unparseable
`fire_*`-style name **throws** rather than being silently dropped.

Each collaborator exports **one asset for all their years and both classes**, with `class`,
`fire_year`, `y_lwr`/`y_upr`, `geom_type` (read off the geometry, not the name), `author` and `src`
(the drawing layer, so a suspect feature traces back). Points and polygons share one table, and
geometry-flavour drawing layers are exploded with `geometries()`.

## Label prep — objects, not pixels

`scripts/objects_labels_prep.R [all|download|merge] [--force] [author…]`. **Download** pulls one
asset → one GeoPackage per author (GPKG and not shapefile: the labels mix points and polygons in one
table, and field names survive intact). **Merge** always reads *every* file present, matches each
label to the objects **of its own fire-year**, attaches their metrics, and writes
`polygons_data_merged.csv`, one row per (label, object) pair.

A year is ~78 k objects / ~330 MB and only a handful are ever hit, so a year is never read whole:
labels are grouped into 1° blocks, each block read back through the **GeoPackage R-tree**
(`terra::vect(extent=)`), and the exact predicate run on that subset. Whole merge: 27 s. Two rules
came out of building it and are load-bearing — see `Gotchas`.

Nothing is dropped; problems are **flagged** for the model step to resolve: `n_objects` (0 = the
label hit no object, >1 = a drawn polygon), `oid_n_labels`, `oid_class_conflict` (an object labelled
both fire and non-fire).

## The fitting set

`clean_tagged()` turns the label↔object pairs into one row per OBJECT, reporting every cut: −234
labels that hit no object (drawn where SNIC kept no cluster — there is nothing to classify), −10
objects labelled both classes, −1315 duplicate labels on an already-labelled object, −1 object with
an NA predictor → **5255 objects, 2788 fire / 2467 non-fire** (prevalence 0.531), 20 predictors.

Uneven label density per object is deliberately **not** corrected — a label is a label, and
reweighting by it would invent information.

## Run

```bash
Rscript collection-01/scripts/objects_labels_prep.R all           # download + merge
Rscript collection-01/scripts/objects_labels_prep.R download --force <author>   # one collaborator refreshed
```

`merge` always reads every file present, so refreshing one author does not shrink the merged table.

## Gotchas

- **Match labels to objects with `terra::relate(…, "intersects")`, never `sf::st_intersects`.** The
  step-05 1-px dilation can weld a whole fire season into one object (`1999_24193` is 13 053 parts /
  643 742 vertices), and `st_intersects` degrades pathologically there — one point against that
  object costs ~55 s. Measured pair-for-pair identical results; `notes/06-label_prep_engineering.md`.
- **Never `st_cast` the labels to POINT** to satisfy terra's one-geometry-type-per-SpatVector rule.
  A polygon label collapses to its first vertex and silently loses most of its objects. Split POINT
  from POLYGON per block instead.

## Files

| File | Role |
|---|---|
| `scripts/objects_labels_prep.R` | download the per-collaborator assets, intersect with objects, join metrics |
| `scripts/objects_data_functions.R` | `clean_tagged()` (the fitting set), `tag_lookup()` (the `fire_tag` column) |
| `training_polygons_<author>` (GEE, `fuego` repo) | the interactive collection script — one per collaborator |

## Related

- [`06-object_model.md`](06-object_model.md) — the classifier these labels fit, and how a collected
  label overrides the model's call (`fire_tag`).
- [`04-snic.md`](04-snic.md) — the `candseed` layer people draw on.
- [`notes/06-label_prep_engineering.md`](notes/06-label_prep_engineering.md) — the `terra` vs `sf`
  benchmark, the `st_cast` trap and the first full run's numbers.
