# 07 — From classified objects to the raster products

Step 07 is the hand-off from *our* mapping method to the network's common post-processing (docs/08).
Its job: get the classified objects into GEE and turn them into the **raster of month-of-burn per
calendar year**, which is what every MapBiomas Fuego country publishes.

No script yet — this file records the decisions that shape it, and where each one is implemented.

---

## 1. Decisions that are settled

**Label collection happens on the SNIC layer, not on uploaded objects.** The objects are many,
heavy, and carry metrics a collector never looks at, while the step-04 `candseed` asset already shows
candidate-vs-seed per pixel — and shape plus seed density is the discriminating signal. Full
rationale and the collection code: docs/06 §1.

**Geometry and metrics stay split, with no redundancy.** Step 05 writes `objects_<fy>.gpkg`
(geometry + `oid` only) and two metrics CSVs keyed by `oid` (docs/05 §4). Step 06 fits and predicts
from the CSVs alone. Geometry is read only to build a QGIS layer or an upload package.

**The whole object set is uploaded, not only the fire subset** *(revised 2026-07-28)*. This file
originally specified fire-only, to save space. Overridden: an expert user needs the rejected objects
to find fires the model **missed**, and those objects with their predictors are what aims the next
label campaign. One FeatureCollection per fire-year, 28 of them, at
`…/WORKFLOW-EXPORTS/objects_raw/objects_raw_YYYY` — the packaging, the field set, the 2 GB
Shapefile cap that forces per-year uploads, and the manual-ingest recipe are all in **docs/06 §12**.

**The fire call the raster must use is `fire`, not `fire_model`** — the collected label wherever
there is one, else the model (docs/06 §5). `fire_tag = -1` means "unlabelled", *not* "not fire";
reading it as 0 would throw away the model's call on 1.68 M objects.

**Calendar year comes from the `year_calendar` metric, not from the fire-year.** Objects are
fire-year entities (the season straddles Dec/Jan, 04 §2) and the products are calendar-year, so each
object is placed by the mode of its pixels' calendar years (05 §2.4). `candseed==3` dieback pixels
inherit the parent object's date and never their own next-year date (04 §4.3). Argentina's route
through the network's calendar-year products is docs/08 §6.

## 2. What still has to be built

- **The month-of-burn raster.** Server-side in GEE: rasterize the uploaded objects where `fire == 1`
  and combine with the SNIC metrics images to take the per-pixel burn date, coded as month within the
  calendar year. `oid` is the join key between the FeatureCollection and the raster side.
- **The unofficial vector database.** The uploaded per-year FeatureCollections *are* this, once
  merged — `ee.FeatureCollection([...]).flatten()` over the 28 assets into one asset. Nothing is
  lost by merging: `oid` carries the fire-year.
- **The minimum mapped fire size.** Evidence is in (docs/06 §9); 1 ha is the defensible default,
  0.5 ha if we want to keep everything that costs nothing. Must be stated in the ATBD and applied
  consistently here. Open (BACKLOG).
- **The manual ash/drought mask.** A hand-made pass removing false positives that survive
  classification; needs domain-expert review before the raster is final.

## 3. Original notes (2026-07, superseded in part)

Kept for the reasoning, not the instructions — the metric-set changes below were implemented in
step 05 and are documented at docs/05 §2.4.

Raster-based metrics kept for each object: per-class veg fractions `frac_c1…c23` (no ranked top-5),
`area_ha` + `n_pixels`, `abs_date` `{median, min, max}`, `year_calendar` (pixel mode);
~~`n_mean`~~ *(computed in collection 1, but dropped as a predictor and not uploaded — docs/06 §4;
collection 2 should not compute it, and should drop `n_pixels` too)*; and neighbourhood sparseness
`burned_around_{1,2,3}` (pre-computed in GEE for direct tiles, computed locally for the legacy COG).

Pixel dilation for connecting components: `candseed == 3` (next-year spring candidates) causes
problems in the Patagonian steppe, so those pixels are dropped east of longitude −70.6. Re-running
SNIC would be the correct fix but is expensive; this is clumsy and cheap. In the union-find
labelling, pixels get **no enlarged context** (8-neighbour connectivity only) when they are
ag/grass/pasture — `veg_fire ∈ {1, 2, 3, 12, 13, 15, 17, 18, 19}` — **or** `candseed == 3`. Full
geometry of the distance thresholds: docs/05 §2.2.
