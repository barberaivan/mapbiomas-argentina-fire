# 07 — The published products: the nine subproducts and the polygon layer

The second half of step 07. [`07-vector_to_raster.md`](07-vector_to_raster.md) says how the burned
**pixels** are made — the object selection, the calendar partition, the grid, and sub-steps 07a
(month of burn), 07b (the local scar build) and 07c (the scar rasters). This file says what is
**packaged from them**: the shape every published asset takes, **07d**'s nine derived subproducts,
and **07e**'s merged fire-object polygon layer for early users.

Nothing here reads a vector from disk or runs locally. 07d derives from 07a's month collection plus
the MapBiomas LULC; 07e reads the step-06 object FeatureCollections directly and depends on no other
sub-step, so it can be rebuilt at any time and in any order. The order of operations for the whole
step, and the commands for 07a–07c, are in the other file.

```bash
# 07d  (re-runnable, skips existing assets) — all nine derive from 07a, NOT from 07c
$PYTHON collection-01/workflow/07-subproducts.py --check      # band bookkeeping + ROI counts
$PYTHON collection-01/workflow/07-subproducts.py --launch     # 9 tasks
#   one product only:  --only frequency_burned

# 07e  — the polygon layer for early users. Independent of 07b-07d; needs only step 06.
$PYTHON collection-01/workflow/07-burned_area_polygons.py --check
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch              # the merged FC
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch --overwrite  # re-export in place
$PYTHON collection-01/workflow/07-burned_area_polygons.py --verify              # THE gate ("`objects_raw_2021` is duplicated in storage")
$PYTHON collection-01/workflow/07-burned_area_polygons.py --set-props           # after it lands
```

> **Citing across the two files.** `docs/07` on its own means
> [`07-vector_to_raster.md`](07-vector_to_raster.md), which is still the entry point for the step;
> this file is cited as `docs/07-published_products`. Sections are cited **by name**, never by
> number.

---

## Products, and the shape they take

The subproducts are **single multiband images, one band per calendar year** — not ImageCollections
of per-year images. Confirmed in the launch guide ("Imagen multibanda con el ID de cada cicatriz")
and in `ToPublish/2-toAsset-Public`, whose `band_format` property (`burned_monthly_{year}`,
`scar_area_ha_{year}`, …) only means anything for a multiband image.

The **one** ImageCollection in the chain is the stage-3 pivot,
`collection1_fire_mask_v<N>` — one single-band image per year — which is what 07a produces and what
every stage-4 script reads. `v<N>` throughout this file is `C.PRODUCT_VERSION`, currently **2**
(`docs/07` "The `_v2` re-export").

**One asset per subproduct, with one BAND per year — not one asset per year.** The scar chain is
three images of 27 bands, never 27 images of 3 bands. Reference script 5 builds them that way
(`ee.Image().select()` then `addBands` per year, one export each), script 6 reclassifies every band
of the area image in a single expression, and `ToPublish/2-toAsset-Public` attaches a `band_format`
property per subproduct (`scar_id_{year}`, `scar_area_ha_{year}`) — a `{year}` token that only means
anything if each band *is* a year.

| Asset | Shape | Bands | dtype / pyramiding | Built by |
|---|---|---|---|---|
| `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v<N>` | **ImageCollection**, one 1-band image per year | `burned_monthly` (1–12) | uint8 / `mode` | `07-month_of_burn.py` |
| `FINAL_PRODUCTS/annual_burned_vectors_v<N>/scars_<Y>` | FeatureCollection per year | `scar_id`, `area_ha`, `n_px`, `year` | — | manual ingest of `scars_<Y>.zip` |
| `FINAL_PRODUCTS/…_annual_burned_id_v<N>` | single multiband image | `scar_id_1999` … `scar_id_2025` | int / `mode` | `07-scar_rasters.py` |
| `FINAL_PRODUCTS/…_annual_burned_area_ha_v<N>` | single multiband image | `scar_area_ha_1999` … | float / `median` | idem |
| `FINAL_PRODUCTS/…_annual_burned_scar_size_range_v<N>` | single multiband image | `scar_area_ha_1999` … (see below) | uint8 / `mode` | idem |
| `FINAL_PRODUCTS/…_<subproduct>_v<N>` (×9) | single multiband image | one band per year or per window | see "The nine products" | `07-subproducts.py` |
| `FINAL_PRODUCTS/burned_area_polygons_v<N>` | one FeatureCollection, all 28 fire-years | ten properties | — | `07-burned_area_polygons.py` |

⚠️ **The size-range bands are named `scar_area_ha_<year>`, NOT `scar_size_range_<year>`.** That is
not a copy-paste slip: the reference inherits the band names from the area product, and the publish
map lists `annual_burned_scar_size_range: 'scar_area_ha_{year}'`. Renaming them to something more
sensible would break the platform's band lookup.

Naming keeps **our** `COLLECTION-1` spelling while the asset *names* inside follow the network
exactly (`C.product_name()`). That is settled: the Brazil team adapted their side to read our
spelling, so nothing has to be renamed for the public copy.

**`annual_burned_vectors` uses underscores, unlike the reference's `annual-burned-vectors`.** That is
deliberate, not a typo: everything else under `FINAL_PRODUCTS` is underscored (`FINAL_PRODUCTS`
itself, `..._annual_burned_v<N>`, `..._annual_burned_area_ha_v<N>`), so the hyphenated folder is an
oddity in the reference tree. Nothing external reads the path — the only consumer is
`07-scar_rasters.py` via `C.ANNUAL_BURNED_VECTORS`, because we **replaced** reference script
`5-export_annual_burned_id_and_size_by_year` rather than adapting it (`docs/07` "07c — the scar
rasters": we paint our own pixel-count `area_ha` instead of letting it recompute
`geometry().area()`, and we classify sizes server-side). That script would not run against our tree anyway: it expects per-year assets named
`mbfogo-col1-<year>-v1`, and ours are `scars_<Y>`. If IPAM ever needs to run their version, both the
folder and the per-year names have to be aligned — not just the folder.


---

## 07d — the nine derived subproducts

Everything here derives from **07a's month-of-burn collection** plus the **MapBiomas LULC**. No new
vectors, no local work, no re-labelling. Script: `workflow/07-subproducts.py`, **nine export tasks,
one per subproduct**.

Reference: `Reference/2-Collection_Fire_Subproducts/1_burned_area_products_monthly_annual_coverage`
(products 1–4), `2_burned_area_frequency_accumulated_coverage` (5–8), `3_year_last_fire` (9).
**Do not innovate here** — copy the encodings exactly; they are what the platform decodes.

### The four settled answers

**1. Which LULC layer?** `C.PRODUCT_LULC` — the **published MapBiomas Argentina land-cover
integration**, bands `classification_<year>`. **NOT `veg_fire`.** `veg_fire` is our internal
25-class fire-modelling remap (region-specific, built for the burn-probability model); it is not the
published LULC legend and no other country has it. Using it would make our `*_coverage` products
undecodable by the platform and incomparable across the network. `veg_fire`'s only role in step 07 is
the argument that the LULC *mask* is already embedded upstream (docs/08 "Foundations") — it never enters a
product.

⚠️ **`C.PRODUCT_LULC` is deliberately a SECOND constant, not a repoint of `C.MAPBIOMAS_LULC`.**
`MAPBIOMAS_LULC` is the **model-side** input: `utils/functions.py::get_mb_class_band` derives
`veg_fire` from it, which drives the step-01 training export and the step-03/04 candidate mask, so
the entire collection's SNIC candidate set was built against that exact asset (LULC col-2 v8) and it
must stay frozen there. The coverage products answer a different question — "which *published* land
cover burned in year Y" — so they track whatever LULC Argentina publishes. **The two pointing at
different collections is not an inconsistency to fix.**

`PRODUCT_LULC` is **LULC collection 3, published** —
`…/COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`. It has moved twice: col-2 v8 → the
preliminary col-3 (`…_integration_v1_buffer`, 2026-07-29, which is what the **v1** coverage
products on the asset store were built against) → the published col-3, which the `_v2` re-export
crosses.

Each move cost nothing, because **all three share one byte-identical grid**, offset from the SNIC
lattice by exactly **9953 columns / −25102 rows — integers**. So combining LULC with the month
raster involves no resampling and no half-pixel shift, which for a *categorical* band is the
difference between a class code and its neighbour's. Their footprints all contain the 2 km buffer,
so no burned pixel can fall outside the LULC and silently drop out of a coverage product (`add`
propagates the mask).

**Max class code 77 < 100 is what makes the encodings work** — it is why `M*100 + L` and
`freq*100 + L` are decodable and `mod 100` exact. Re-check it whenever `PRODUCT_LULC` moves, along
with the lattice offset and the footprint; the measured audits are in
[`notes/07-verification_log.md`](notes/07-verification_log.md). The available band list is read
from the **asset**, never hardcoded, so extending or repointing the source self-corrects — which is
why duplicating a missing last year forward (the network's own answer) was never a blocker, and is
moot now that col-3 carries `classification_2025` natively.

**2. Same year or previous year?** **The same calendar year.** The reference selects
`lulc.select('classification_' + year)` for the burning year itself. Note this differs from
`veg_fire`, which is built from the **previous** year's LULC (the classifier must not see the burn it
is predicting). The coverage products have no such constraint — they answer "which land cover burned
in year Y", as classified in year Y — so the two layers are genuinely different and differently
aligned in time. Do not "fix" one to match the other.

For the **frequency** products the LULC year is the **moving end of the window**: the forward pass
(`fire_frequency_<y_first>_<y>`) uses `classification_<y>`, the backward pass
(`fire_frequency_<y>_<y_last>`) also uses `classification_<y>`. In both cases it is the end that
varies, not the fixed anchor.

**3. Do they split by region?** **No.** Scripts 1, 2, 3, 5 and 6 all export **one multiband image per
subproduct** over `regions.union().geometry()` — the whole country. The only per-region assets in the
network's chain are the stage-2/3 classification collections (one image per region-year), and ours has
no region dimension at all: 07a wrote one whole-country image per calendar year. So there is nothing
to reconcile. (Not to be confused with the **statistics** exports, statistics/docs/statistics.md, which *are* cut by
territory — that is a different stage and a different layer.)

**4. Shape.** One asset per subproduct, one **band** per year — never one asset per year
("Products, and the shape they take").

### The nine products

`M` = the month-of-burn band (1–12, masked elsewhere); `L` = `classification_<year>`.

| Subproduct | Band | Encoding | dtype | Pyramiding |
|---|---|---|---|---|
| `monthly_burned` | `burned_monthly_<year>` | `M` | uint8 | mode |
| `annual_burned` | `burned_area_<year>` | `M > 0` → 1 | uint8 | mode |
| `monthly_burned_coverage` | `burned_coverage_<year>` | `M * 100 + L` | uint16 | mode |
| `annual_burned_coverage` | `burned_coverage_<year>` | `(M >= 1) * L` | uint8 | mode |
| `frequency_burned` | `fire_frequency_<y1>_<y2>` | count of years burned in the window, `selfMask()`ed | int16 | mode |
| `frequency_burned_coverage` | `fire_frequency_<y1>_<y2>` | `freq * 100 + L` | int16 | mode |
| `accumulated_burned` | `fire_accumulated_<y1>_<y2>` | `freq >= 1` → 1 | uint8 | mode |
| `accumulated_burned_coverage` | `fire_accumulated_<y1>_<y2>` | `freq_coverage mod 100` (recovers `L`) | uint8 | mode |
| `year_last_fire` | `classification_<year+1>` | calendar year of the most recent fire up to that band | uint16 | mode |

Export with `crs=C.SNIC_CRS` + `crsTransform=C.SNIC_TRANSFORM` (never `scale=30`, `docs/07`
"One grid, pinned everywhere"),
`region = ARG_BUFFER_FC`, `maxPixels=1e13`, `pyramidingPolicy` `mode` throughout.

Band counts as built: **27** for the four annual/monthly products and for `year_last_fire`, **53**
for each of the four window products (frequency / accumulated, with and without coverage).

**Frequency windows are two-sided.** A forward pass accumulates `y_first…y` and a backward pass
`y…y_last`; both band sets are concatenated and sorted, and the duplicated join band — the full
`1999_2025` window, which both passes produce — is kept from the forward pass only (the reference
drops the backward copy with `freqPost.slice(0,-1)`). 27 + 27 − 1 = **53**. Never-burned pixels are
`selfMask`ed out, so frequency is `1..N`-or-absent, never 0. The coverage variant encodes the LULC of
the window's **moving end** — `y` in both passes, i.e. the window's end going forward and its start
going backward.

### Four traps in the reference code

1. **`year_last_fire` bands are `classification_<year+1>`** — an off-by-one the platform expects.
   Preserve it; it looks like a bug and is not.
2. **The `accumulated_burned` filename typo.** Script 2 builds
   `'..._accumulate' + coll_n + '_burned_v1'` → `..._accumulate1_burned_v1`, while the publish list
   expects `..._accumulated_burned_v1`. Use the correct spelling.
3. **The reference disagrees with itself on `frequency_burned`'s band name.** Script 2 writes
   `fire_frequency_<y1>_<y2>`, while `ToPublish/2-toAsset-Public`'s `band_format` map says
   `frequency_burned_{year1}_{year2}`; the `accumulated_*` pair agrees in both places, only
   frequency does not. **We follow the script** — `C.FREQ_BAND_PREFIX = "fire_frequency"` — so the
   asset matches the code every other country ran.
4. **The `*_coverage` products are the easiest to forget** and are exactly what the statistics stage
   reads ([`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) §2). Four of the
   nine are coverage products.

### The LULC is the only place land cover enters our chain

The stage-3 LULC *mask* does not apply to us (`docs/08` "Foundations"), so the four `*_coverage`
products are the **only** point at which land cover touches the published rasters. Everything that
makes that safe — the shared lattice, the integer offset, the footprint, the `< 100` class codes —
is above, under "The four settled answers".

### What was verified

`--check` prints the band bookkeeping for all nine products plus per-year ROI counts, and a
value-level decode of **every encoding** was run on a Chaco 0.5° box before submitting and again
against the landed assets. Both passes agree to the pixel: every decode residual 0, single-year
window = annual, and the five window-scoped products sharing one mask exactly
([`notes/07-verification_log.md`](notes/07-verification_log.md)).

> **ROI histograms taken with `frequencyHistogram` come out a few pixels below the
> `sum().unweighted()` counts.** That is `reduceRegion`'s **edge weighting** of partial pixels at
> the box boundary, not a disagreement between products — the same artefact the scar check records.
> Use `sum().unweighted()` whenever a count has to match a local build.

`scripts/audit_product_properties.py` is the standing property-drift check (dry run by default,
`--apply` to write). Run it after any re-export and after any move of `C.PRODUCT_LULC`: a silent
drift there is how a published asset ends up advertising the wrong land-cover collection.

### Three departures from the reference, all plumbing

The encodings are copied verbatim; what differs is how the graph is fed.

1. **The grid is pinned** (`crs` + `crsTransform`), never `scale=30` — `docs/07` "One grid, pinned
   everywhere", the same rule as 07a/07c.
2. **`region = ARG_BUFFER_FC`** instead of `regions.union().geometry()`, because
   `regiones_fuego_argentina_v1` does not exist as a FeatureCollection (`docs/07` "What is still
   open").
3. **All nine products read the 07a month collection**, whereas the reference exports `annual_burned`
   first and has scripts 2 and 3 read *that asset*. `annual_burned` is *defined* as `month > 0`, so a
   frequency built from the month images is bit-identical to one built from the exported annual
   product — and deriving everything from the single pivot makes the nine consistent **by
   construction** rather than by sequencing. The operational win is that the nine tasks are
   independent: nothing waits for a 27-band export to land, and any one product can be re-run alone
   (`--only`). Confirmed by the two exact cross-product agreements in "What was verified".

The reference's `accumulated_burned` filename typo is not copied ("Four traps in the reference code").

---

## Namespace the task descriptions

`mapbiomas-fire-485203` is used by **many people across the network**, and
`ee.data.listOperations()` is **project-scoped, not per-account**: it returns every user's tasks (226
of them when 07d was launched — Peru's `MONITOR_01_*`, Bolivia's
`GT_Fuego-mapbiomas_bolivia_fire_collection1_burned_area_*`, …). Step 03 already documents that
scoping for `bpts_` (`03-bp_ts_metrics.py::_inflight_bpts_names`).

07d was first written matching in-flight tasks on the **bare** subproduct name (`annual_burned`,
`monthly_burned`, `year_last_fire`) — which is exactly what another country's adaptation of these same
reference scripts would call its exports. A collision would print
`[skip] … has a PENDING/RUNNING task` and **silently not submit one of our products**, which is the
worst kind of failure here: it looks like the resumable-skip working. Descriptions are therefore
namespaced **`arg07d_<subproduct>`** (`TASK_PREFIX`).

`destinationUris` — which would identify the task by *our* asset path and settle it exactly — is
populated **only on FINISHED operations**, so it cannot serve the in-flight test. The prefix is the
fix, not a workaround for a nicer one.

⚠️ **Never cancel or touch a task you did not launch**, and never match one by a generic description:
in this project the other tasks belong to other countries' teams.

The first batch went out under the bare descriptions, so a `LEGACY_DESCRIPTIONS` fallback kept them
accepted by the in-flight test — otherwise a re-run before they landed would have double-submitted.
✅ **Deleted 2026-07-30**, once all nine had finished: it was the collision-prone form the prefix
exists to retire, and keeping it any longer would have meant one of our products could be silently
skipped because another country happened to be exporting an `annual_burned`. The in-flight test now
matches the namespaced description only.

---

## 07e — the fire-object polygon layer, for early users

```
FINAL_PRODUCTS/burned_area_polygons_v2
```

Every mapped fire, all 28 fire-years, in **one** FeatureCollection. Script:
`workflow/07-burned_area_polygons.py`. Nothing is computed and no geometry is touched — it is the
step-06 object set under the full positive selection 07a paints (`fire == 1 & area_ha >= 1 &
not(A) & not(B)`, `docs/07` "Object exclusion ruleset"), stripped to ten properties, merged and
flattened.

**`_v2`: 1,012,648 rows for 1,012,645 objects, 63.33 Mha** (counted on the asset 2026-09-15).

⚠️ **The `_v1` figures quoted in this section — 1,263,079 rows / 1,263,076 objects / 69.12 Mha —
are the PRE-RULE layer**, exported 31 July, before exclusion rules A and B were finalised
(2026-09-11/12). The 250,431-object gap between the two is the rules: −196,804 to rule A and
−53,627 to rule B, measured per fire-year by `statistics/fire_counts.R`, whose local object tables
reproduce the v2 count **to the object**
([`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) §4 "The fire counts"). Do not
quote a v1 number as the size of the published layer. (A naive row-sum of `area_ha` overstates the
area in either version — "`oid` is unique per OBJECT, not per row".)

It depends only on step 06, not on 07a–07d, so it can be rebuilt at any time and in any order.

### The name, and the folder

**A plain `burned_area_polygons_v<N>`, NOT `C.product_name()`.** Every raster subproduct is
`mapbiomas_argentina_fire_collection1_<subproduct>_v<N>` because the platform's `band_format` lookup
and the publish copy require that exact form. This layer is not one of those: it is ours, it is for
people, and it is a name a user has to read out and type (Iván, 2026-07-30 — the first launch used
the long form and was cancelled and re-run for this).

**`polygons`, not `vectors`.** `FINAL_PRODUCTS/annual_burned_vectors_v<N>/` is already taken by the
**calendar-year scars** (07b/07c) — plain 8-connectivity, calendar-clipped, one scar per connected
burn, a genuinely different layer from these fire-year objects. Reusing the network's word would put
two unrelated layers one line apart under near-identical names. "polygons" also tells a user what
they are getting, where a "vector" could be points or lines.

**It lives in `FINAL_PRODUCTS` and it stays there.** An early draft parked the fire-year vector
database outside that folder pending a ruling on whether Argentina may publish it; Iván's call
(2026-07-30) was to put it in, so early users get a stable link, and Brazil's own col-5
`annual_burned_vectors` is the precedent. It remains **our** asset, shared by us rather than copied
into the network's public collection — `ToPublish/2-toAsset-Public` copies an **explicit**
subproduct list rather than the folder, so it cannot be swept in by accident. The ATBD says so
(`docs/08` "What Argentina delivers").

### The ten properties

| property | source | meaning |
|---|---|---|
| `oid` | `oid` | stable object id `<fy>_<n>` — the key that joins user feedback back to the object database and its 20 metrics |
| `fire_year` | **the asset name** | the non-calendar mapping year, 1 May *fy* → 30 Apr *fy*+1 |
| `calendar_year` | `year_cal` | the **mode** of the object's per-pixel calendar years |
| `area_ha` | `area_ha` | pixel-count area — *not* a geodesic polygon area |
| `date_med` / `date_min` / `date_max` | idem | burn dates, ISO 8601 `YYYY-MM-DD` ("Dates readable, and the layer `filterDate`-able") |
| `p_mean` | `p_mean` | posterior mean fire probability (probit BART, docs/06) |
| `p_width` | `p_width` | width of its credible interval, `p_q95 − p_q05` |
| `seed_mean` | `seed_mean` | mean SNIC seed burn probability over the object |

`fire_year` is **not** a property of the source FCs — it exists only in the asset name, so the
script sets it per source collection. `year_cal` → `calendar_year` is the one rename; everything
else keeps the object database's vocabulary. The classification **threshold is deliberately not
included** (Iván, 2026-07-30) — it is a per-size-band constant from
`config/object_model_thresholds.csv`, not a property of a fire, and `p_mean` is what a user actually
wants to filter on.

#### Dates readable, and the layer `filterDate`-able

The object database stores the three dates as **whole days since 1970-01-01** — an integer `19018`
that nobody can read in the Inspector or a QGIS attribute table. In this layer they are
**`YYYY-MM-DD` strings** instead (Iván, 2026-07-30). Nothing is lost: the integers stay in the object
database, `oid` joins back to them, and ISO-8601 still range-filters correctly because it sorts
lexicographically — `ee.Filter.gte('date_med', '2021-01-01')` does what it looks like.

Each feature also carries **`system:time_start`, stamped from `date_med`**, so the collection answers
`filterDate()`. Two decisions inside that:

- **`date_med`, not `date_min`** — one fire, one instant, matching what `calendar_year` already does
  (the modal year, "Two things users must be told").
- **`system:time_end` deliberately NOT set.** With both timestamps the date filter passes on interval
  *intersection*, so a fire burning 28 Dec → 4 Jan would come back from a December query *and* a
  January one, and summing `area_ha` per month would double-count it. One timestamp keeps one fire in
  one bucket, so `filterDate` results stay summable. The true span is still right there and readable:
  `date_min`…`date_max`.

Implementation trap: **`Feature.select()` drops `system:time_*`** along with every other unlisted
property, so the timestamp is set *after* the select. Set it before and it vanishes — and a
`filterDate` that silently matches nothing is indistinguishable from a window with no fires in it.

### Two things users must be told

1. **`calendar_year` is the object's majority year, and the rasters do not agree with it.** It is
   `mode_int(cyear)` over the object's pixels (`05-objects_metrics.R:239`), while every published
   raster assigns year and month **per pixel** (`docs/07` "The decisions this step rests on"). A
   fire straddling 31 December is split across
   two years in the rasters and lands whole in one year here. Neither is wrong — but a user who
   cross-tabulates the two without knowing this finds "missing" area.
2. **Fire-year 1998 is here and in no published raster.** 3,845 polygons, `calendar_year` 1998 or
   1999; the calendar series starts at 1999, so FY1998's Nov–Dec 1998 tail (~76 kha) exists in this
   layer only (`docs/07` "The verified calendar-year partition").

And a third for us: **the layer's area must be summed per OBJECT, not per row**, because one FY2000
object is stored as 4 rows each carrying the whole object's area ("`oid` is unique per OBJECT, not
per row"). Summed per row, v1 read 74.23 Mha instead of 69.12 — an overstatement of **5,118,513 ha**
from one fire counted four times. Done correctly, the layer and the scars agree to **0.14 %**
(69.12 vs 69.02 Mha on v1), where the naive arithmetic made them look 5.2 Mha apart. The residual
differences are real and should **not** be forced to zero: fire-year vs calendar partition, calendar
1998 included here and dropped there, intra-year reburn deduplicated there but not here, and a
different minimum unit.


### Which ACCOUNT submits it

**The GEE task queue is per user**, so the merged export runs as the **second account**
(`ivanbarbera@comahue-conicet.gob.ar`) on the **`mapbiomas-argentina`** compute project, whose queue
was empty, rather than waiting behind the primary account's tasks. Only the *compute* project
changes — the destination asset is the same either way, so the link shared with early users does not
depend on who submitted it.

```bash
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch \
    --project mapbiomas-argentina \
    --credentials ~/.config/earthengine/credentials.comahue
```

**`--credentials`, never swapping the resident file.** `ee.oauth.get_credentials_path()` hardcodes
`~/.config/earthengine/credentials` with no env override, so the obvious route is to `cp` the
account you want into place; passing the file explicitly is strictly better — nothing is clobbered,
both accounts are usable in one session, and a half-finished swap cannot leave the wrong token
resident. This function is the pattern CLAUDE.md points other scripts at.

**Monitoring has to ask twice.** `ee.data.listOperations()` is project-scoped *and* cross-user, so
the resident account can see the comahue task — but only when initialized against
`mapbiomas-argentina`. A watcher that polls only `C.GEE_PROJECT` reports the 07e task as `MISSING`,
which looks exactly like a task that was never submitted. The same asymmetry applies to a re-export:
`--overwrite` on an asset the comahue account created is submitted by that account too.

Write permission **cannot be pre-flighted** — `getAssetAcl` on `FINAL_PRODUCTS` returns empty
`writers`/`owners` because access comes from the cloud project's IAM, not a per-asset ACL — so a
missing write permission surfaces as an immediate task failure, not hours in. Launching is the
cheaper test. Feasibility measurements and the EECU trap:
[`notes/07-export_post_mortems.md`](notes/07-export_post_mortems.md).


### ⚠️ `objects_raw_2021` is duplicated in storage, and no count reveals it

**`objects_raw_2021` hands the export 1,249 FY2021 features twice**, byte-identical in geometry and
in every property. It came in through step 06's hand ingest, it is reproducible under a given read,
and it is on the GEE side —
**not** in what we uploaded: the ingest package on disk is 66,393 records for 66,393 distinct `oid`
(`docs/06` "Gotchas"). But **no metadata count shows it**: `size()`, `aggregate_count('oid')` and
`len(aggregate_array('oid'))` all agree on the wrong number, because an aggregation over a plain
filtered *stored* collection is answered from the asset's metadata. Force GEE to **iterate** and the
extra features come back. An export iterates, so it writes them.

**Still live as of 2026-09-18, and the surplus is query-dependent** — which is the part the
post-mortem could not know from one export. The asset was never re-ingested (`updateTime` is still
`2026-07-28`) and `fires()` reproduces the July figures to the row (**54,514 for 53,263 distinct
`oid`**), but `area_ha >= 1` alone surfaces only 241 surplus rows and `fire == 1` alone surfaces
none. It also takes a **`Feature.select()`** in the map: a bare `.map()` that only `set`s comes back
clean under the very filter that yields 1,251. So a clean count proves nothing about the next query,
and the only real fix is the re-ingest. The full 2026-09-18 measurement table is in
[`06-object_model.md`](06-object_model.md) "Gotchas".

Two rules outlast the bug:

1. **A count that agrees with itself is not a clean bill of health.** Three numbers, one pushed-down
   answer, all three wrong about what a read returns. The honest check materialises — and a bare
   `.map()` does not materialise: it takes a `Feature.select()` in the map, or a count on the
   **landed asset**.
2. **A COMPLETED task is not evidence that each feature was written once.** The original `--verify`
   — size, schema, one feature — passed the bad asset without a murmur.

**The fix** is `distinct('oid')` inside `fires()` — one row per object, the invariant actually
wanted — applied per fire-year and **skipped for FY2000**, whose 4 rows are a legitimate vertex
split (below). `distinct(['oid', '.geo'])` needs no exception but hashes ~4 GB of serialised
multipolygon to buy a distinction that matters in one year. **The root cause belongs upstream**:
`objects_raw_2021` should be re-ingested by step 06 (BACKLOG, `docs/06` "Gotchas"). Until it is,
that guard is what stands between the asset and every product derived from it. Full post-mortem:
[`notes/07-export_post_mortems.md`](notes/07-export_post_mortems.md).

### `oid` is unique per OBJECT, not per row

`objects_raw_2000` stores `2000_57529`, a **1,706,171 ha** object, as **4 features** with disjoint
geometry parts, each repeating the whole object's `area_ha`, dates and probabilities. It is a vertex
split — `Export.table.toAsset(maxVertices=…)` cuts a geometry that exceeds the limit into pieces —
and it happened **upstream, in the step-06 upload**, not here: audited across all 28 sources, the
totals are **1,263,079 rows / 1,263,076 distinct `oid`** and FY2000 is the only year affected. This
layer carries all 4 rows faithfully, which is why the expected row count is 3 above the object count.

Two consequences, both in the asset's `oid_uniqueness` property:

- **a naive `aggregate_sum('area_ha')` over-counts the layer by 5,118,513 ha** — 3 extra copies of
  1,706,171 ha. This is not a footnote: it is what made the layer look like 74.23 Mha instead of
  69.12 Mha ("Two things users must be told"), and it is why `--verify` now prints both totals. Dissolve by `oid`, or subtract
  the split, before quoting an area.
- **never repair a duplicate with a blind `distinct('oid')` on this fire-year.** It would keep one
  part and silently drop ~1.3 Mha of that fire — measured: `distinct(['oid', '.geo'])` leaves the 4
  rows intact, `distinct('oid')` returns 1. That is exactly why the guard in `fires()` skips FY2000
  and why `--verify` carries `KNOWN_VERTEX_SPLITS = {2000: 3}` rather than tolerating any surplus.

Why the split cannot simply be undone: the 4 parts exist *because* the whole geometry exceeds the
exporter's vertex limit, so re-merging them would only be split again on write. Four rows is the
storable form; the caveat is the price.

---

## Files

| File | Role |
|---|---|
| `workflow/07-subproducts.py` | 07d — the nine derived subproducts, from 07a's month collection + `C.PRODUCT_LULC` |
| `workflow/07-burned_area_polygons.py` | 07e — the merged fire-object polygon layer (`--check` / `--launch` / `--verify` / `--set-props`) |
| `scripts/audit_product_properties.py` | the standing property-drift check over the published assets |
| `scripts/run_07_v2_driver.py` + `scripts/v2_driver_tick.sh` | the unattended cron driver that runs the whole step; board at `logs/v2-driver/STATUS.md` |
| `utils/constants.py` | `PRODUCT_VERSION`, `PRODUCT_LULC`, `SNIC_CRS`/`SNIC_TRANSFORM`, `SCAR_SIZE_LOWER_HA`, `product_name()` |

## Related

- [`07-vector_to_raster.md`](07-vector_to_raster.md) — the other half of step 07: the object
  exclusion ruleset every product here is painted under, the `_v2` re-export, the pinned grid, the
  calendar partition, and 07a–07c.
- [`06-object_model.md`](06-object_model.md) — the `fire` call and the object set 07e publishes, and
  the two storage defects of that upload which every consumer here must guard against.
- [`08-postprocessing.md`](08-postprocessing.md) — Argentina's route through the network's spec, and
  [`external/mapbiomas-fuego-reference.md`](external/mapbiomas-fuego-reference.md) — the spec these
  encodings are copied from.
- [`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) — what is computed *from*
  these products.
- `notes/`: [`07-verification_log.md`](notes/07-verification_log.md) (the dated audits, including
  the decode of every encoding before launch and again on the landed assets),
  [`07-export_post_mortems.md`](notes/07-export_post_mortems.md) (the merged-export feasibility, the
  EECU trap, the FY2021 duplication).
