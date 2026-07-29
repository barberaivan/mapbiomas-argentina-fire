# 07 — From classified objects to the calendar-year products

Step 07 is the hand-off from *our* mapping method to the network's calendar-year products. Its job
is to turn the step-06 fire-year objects into **month of burn per calendar year** and into the
**calendar-year scars** (id + area) that the size products are painted from.

This is **implemented**. Three scripts:

| Script | Where it runs | Produces |
|---|---|---|
| `workflow/07-month_of_burn.py` | GEE, server-side | `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` — one 1-band uint8 image per calendar year, value 1–12 = month of burn, masked elsewhere |
| `workflow/07-calendar_scars.R` | local (terra/sf/data.table + the step-05 Rcpp union-find) | `data/objects-scars/scars_<Y>.gpkg` + `data/scars-upload-cache/scars_<Y>.zip` — 8-connected calendar-year scars with `scar_id`, `area_ha`, `n_px`, `year` |
| `workflow/07-scar_rasters.py` | GEE, after the manual ingest | the three scar subproducts, multiband, one band per year |

`scripts/run_07_scars.sh` is the launcher for the local pass (two modes, resumable, biggest-year
first, one process per year — same pattern as `run_05_years.sh` / `run_06_predict.sh`).

---

## 1. The decisions this step rests on

**The fire layer is the object-level classification.** Only objects with **`fire == 1` and
`area_ha >= 1`** contribute a pixel. `fire` is the deployed call — the collected label where there
is one, else the model (docs/06 §5); `fire_tag == -1` means *unlabelled*, never *not fire*. The
filter is a **positive** selection, not "everything not rejected": 36 objects in the collection are
entirely `candseed==3` dieback, so they have a null `date_median` and a null `fire`, and
"not rejected" would admit them.

**The whole object set is what was uploaded** in step 06 (`objects_raw_<fy>`, 28 FCs, every object
with all 20 predictors), because a fire-only layer can show commission error but never omission,
and the rejected objects are what aims the next label campaign (docs/06 §12). Step 07 filters at
read time; nothing about the upload changes.

**Calendar year and month are assigned PER PIXEL, from `abs_date`** — not per object from
`year_calendar`. The object-level `year_cal` remains a property of the object database and is not
used by any raster product. Per-pixel is what makes `annual_burned`, `monthly_burned` and
`scar_size` agree pixel-for-pixel (docs/08 §6.7). The consequence is deliberate: **a fire that
straddles 31 December is split into two calendar years**, and therefore into two scars.

**A `candseed==3` dieback pixel takes its parent object's median date**, not its own `abs_date`
(§4).

**Minimum mapped fire: 1 ha**, applied to the *object* before the calendar split — so a
calendar-year part of a qualifying object may itself be smaller.

---

## 2. The calendar-year partition, and why it is a union

```
calendar year Y  =  Jan–Apr Y  from fire-year (Y−1)   ⊎   May–Dec Y  from fire-year Y
```

Checked over all 28 fire-years: **no object's `date_min`/`date_max` leaves its own fire-year
window** (1 May *fy* → 30 Apr *fy*+1), 0 exceptions. So the two contributions are disjoint in month
by construction and merging them is a **union**, not an arbitration. `max` only ever decides
genuine **reburn** — a pixel burning Feb *Y* and again Sep *Y* — where the later date wins, which
is what the pixel looks like at year end.

The series is **1999–2025**. FY1998 exists only as its Jan–Apr 1999 part plus a Nov–Dec 1998
remainder; that remainder falls in calendar 1998, which is not published, and the pixels pass
reports it as dropped rather than silently discarding it.

**The pixel accounting closes exactly.** Summing each fire-year's two calendar halves against its
accepted pixel count, **27 of 28 fire-years match to the pixel** (0 difference). The only exception
is FY1998, by construction: **1,058,206 px (~76 kha)** of genuinely mapped Nov–Dec 1998 burned area
sit in calendar 1998 and therefore appear in **no published product**. Totals reconcile —
911,617,919 accepted px, 910,559,713 in the published series, difference exactly 1,058,206. This is
inherent to the series starting at 1999, not a defect, but it should be **stated in the ATBD**:
Argentina's collection maps a fire-year that the calendar-year products cannot fully express at the
lower edge.

One exception to the window rule matters in the code: **dieback pixels genuinely do leave their
fire-year window** (their raw date is Jun–Nov of *fy*+1), so each fire-year's contribution is
filtered with the general test `date ∈ [Y, Y+1)` and is never shortcut to "Jan–Apr for the older
fire-year".

---

## 3. One grid, pinned everywhere

All **56** SNIC assets (28 `snic_<fy>` + 28 `snic_metrics_<fy>`) share one identical projection:

```
EPSG:4326, transform [0.000269494585236, 0, -73.58468801489491,
                      0, -0.000269494585236, -21.764113209062533]
```

and the 248 per-carta tiles in `data/snic-rasters/<fy>/` sit on the same lattice (offset exactly
22578 columns, 0 rows). All 28 fire-years have byte-identical tile footprints. Recorded as
`C.SNIC_CRS` / `C.SNIC_TRANSFORM`.

**Every export pins `crs` + `crsTransform`, never `scale=30`.** `scale: 30` in EPSG:4326 — which
every reference script uses — is a *different* grid: different origin, and 30 m is not that degree
step. A half-pixel shift there would misalign the GEE month raster from the scar rasters painted
from locally-built vectors, which is precisely the thing this step has to get right.

The local side derives the lattice from those constants rather than from a `vrt` of whatever tiles
are on disk, because `cell = (row−1)·NC + col` is the labelling key: if `NC` differed between the
two fire-years feeding a calendar year, unrelated scars would silently merge. The origin is shifted
**one pixel west** of the transform origin, because the westernmost carta starts exactly there —
without the shift `col` would run 0…74085, 74086 distinct values against `NC = 74085`, and
`(row−1)·NC + NC` would collide with `row·NC + 0`.

Lattice: `NC = 74086`, `NR = 123601` (9.16 B cells, matching docs/05).

---

## 4. `candseed == 3`: dieback pixels take the parent object's date

A `candseed==3` pixel is Patagonian slow-dieback padding (docs/04 §4.3): it was a candidate in the
*next* year's image with a mid-date in Jun–Nov of *fy*+1. That date is when the **dieback was
detected**, a different physical event from the burn — the pixel has no burn date of its own.

Measured across the 28 fire-years: **881 k such pixels (~79 kha) survive** the step-05 longitude
cut — **4.0 %** of all candidate pixels west of the cut, and **14–18 % in FY2014, 2015, 2021 and
2024**. Their raw dates fall in Jun–Nov (plus ~10 k in April).

Left raw they would do two things:

1. report Andean Patagonia burning in **austral winter** in the monthly product; and
2. whenever the parent fire burned **May–Dec**, fall into the *next* calendar year — splitting the
   scar and minting a **phantom scar** with its own id and size class.

So each dieback pixel takes its **parent object's `date_median`** (`C.DIEBACK_USE_PARENT_DATE`,
`DIEBACK_USE_PARENT_DATE` in the R script). No pixel that has a real measured date is touched, and
`date_med` was already a property on the uploaded FCs, so it costs nothing. The 36 all-dieback
objects have no parent date at all and are filtered out.

**FY2025 has no dieback padding**, because that needs the FY2026 image. The last year of the series
is asymmetric in this one respect — worth a line in the ATBD.

Two step-05 behaviours are replayed rather than re-derived:

- **The longitude cut.** Step 05 dropped `candseed==3` east of **−70.6** *before* labelling, so the
  objects never contained them — but `snic_<fy>` still carries them (65,752 px over 28 fire-years).
  GEE replays the cut with `pixelLonLat`; the local pass gets it for free (the objects are already
  post-cut) and keeps the test as a guard.
- **Objects, not calendar dates, own the `candseed==3` assignment.** Their date being in the "wrong"
  fire-year is not a problem to fix; the substitution removes the question entirely.

---

## 5. The LULC mask and the solitary-pixel filter are embedded upstream

The network's stage 3 applies a LULC mask (water 26 at minimum) and deletes 4-connected components
of ≤ 4 px. **Argentina applies neither at this stage, because both are already in the pipeline —
and more strictly:**

- `veg_fire` is derived from the **previous-year MapBiomas LULC**, and every non-burnable class has
  no `VEG_TABLE` entry, so `THR_DEF = 9` makes it unreachable as a SNIC candidate. Verified on
  FY2000/2014/2023 over ~3.6 M candidate pixels: **zero `candseed>0` pixels on `veg_fire` 24
  (non-burnable) or 25 (non-observed)**. The reference rule drops water only; ours drops every
  non-burnable class.
- The `>= 1 ha` object cut (≈ 11 px, before the calendar split) is stricter than `<= 4 px`.

The collection is still named `collection1_fire_mask_v1`, because that is the asset every
downstream reference script reads, and the images carry `lulc_mask` and `solitary_pixel_filter`
properties recording that it was applied upstream rather than skipped.

---

## 6. Why the object polygons can be trusted as the pixel set

Both sides of this step recover a pixel set from the step-06 polygons, so that had to be exact
rather than approximately right. docs/08 §6.4.2 warned that "painting a polygon fills its
interior". **It does not**, and this was verified two independent ways:

- **Locally**: `terra::cells(country template, accepted polygons)` for FY2020 returned
  **55,008,255** cells against `sum(n_pixels) = 55,008,255` over the same objects — exact over
  55 M pixels. Every fire-year processed since reports the same `EXACT`.
- **In GEE**: on the audited ROIs, `paint(fc,1)` and the `candseed`-derived burned mask agree with
  **0 painted-but-not-burned** pixels.

The reason is that step 05 vectorized the *accepted pixel set* with `as.polygons(dissolve=TRUE)`,
so holes are true interior rings and the boundary follows pixel edges. Both `terra::cells` and
GEE's `paint` use pixel-centre-in-polygon, so they recover the same set.

The `candseed > 0` intersection is therefore a **guard, not a correction**. It is kept on both
sides, and the residual is logged per year rather than assumed to be zero.

---

## 7. The GEE month-of-burn build

`07-month_of_burn.py`, per calendar year `Y`, for `fy ∈ {Y−1, Y}`:

1. `fc = objects_raw_<fy>` filtered to `fire == 1 & area_ha >= 1 & date_med` not null.
2. `footprint = ee.Image().paint(fc, 1).gt(0)` — `paint` on an empty image is **masked outside** the
   features, so this is the footprint and nothing else.
3. `burned = candseed > 0 & (candseed != 3 | lon <= −70.6)`.
4. `date = abs_date.where(candseed == 3, paint(fc, 'date_med'))`.
5. `keep = footprint & burned & date ∈ [Y, Y+1)`.
6. `month = Σ_{k=1..12} (date >= first day of month k of Y)` — exact on that interval.

then `ee.ImageCollection([contribution(Y−1), contribution(Y)]).max()`.

GEE has **no per-pixel date decomposition**: `abs_date` is whole days since 1970-01-01 and there is
no per-pixel `ee.Date`, hence the threshold sum. Only 12 comparisons per fire-year, so it is cheap.

Two GEE gotchas are baked into that code, both found the hard way:

- **`paint` the FC once, not twice.** `date_med` is notNull for every feature in `fc`, so the painted
  date band is non-null exactly on the object footprint — its `.mask()` *is* the footprint. The
  earlier version rasterized the same FC twice per fire-year (four times per calendar year) to get
  the footprint and the date separately; rasterizing 20–70 k polygons is the dominant cost of this
  export, so that was double work for nothing.
- **Do NOT replace `ee.Image.pixelLonLat()` with a clipped constant** for the longitude cut, however
  tempting (pixelLonLat materializes two float bands over 9.16 B cells to answer one threshold).
  `clip` sets the image's **footprint** and `unmask(0)` does not reset it, so the subsequent
  `.And()`/`.Or()` intersect footprints and confine the *entire result* to west of the cut. Measured:
  the Chaco audit box, east of the cut, went from 32,546 burned px to **0** — it would have silently
  emptied most of the country while still producing a valid-looking asset.

`--check` audits a **small** ROI: the per-month pixel histogram plus the painted-vs-burned residual.
It exists precisely for the above: both were caught by re-running it and comparing against recorded
numbers, not by reading the code. Two audits recorded during the build (and re-verified after the
single-paint change — identical to the pixel):

| ROI | Result |
|---|---|
| San Ramón test ROI, calendar 1999 | 13,082 px, all in months 1–4, entirely from FY1998 (the Feb 1999 fire, docs/04 §4.5); painted = burned = 13,082, residual 0 |
| Chaco 0.5° box, calendar 2020 | 13,064 px in months 1–4 from FY2019 + 19,482 px in months 5–12 from FY2020 = 32,546; residual 0 in both fire-years |

The second is the merge working: the two fire-years land in disjoint month ranges and sum exactly.

**The exported assets were also checked against the computed graph**, which is a different question
from whether the graph is right — it catches export-time grid or masking surprises. Over the same
Chaco box: calendar 2003 → 15,491 px from the graph and 15,491 from the asset; calendar 2004 →
13,708 and 13,708, identical month histograms. Note the San Ramón ROI is **useless for this check on
any year but 1999** — that patch burned in Feb 1999 and not again, so every other year correctly
reads 0 there.

The whole-country histogram cannot be taken interactively — `reduceRegion(...).getInfo()` over the
74085 × 123601 grid returns *Computation timed out*. `--stats` submits it as a batch task instead and
`--stats-read` prints it beside `scars_<Y>_months.csv`; that pair is the standing local↔GEE check.

---

## 8. The local scar build

GEE cannot do the labelling — `connectedPixelCount` caps at 1024 px (≈ 92 ha), far below a real
scar — which is why the reference chain round-trips through Drive and Colab. We label locally from
the carta tiles and object polygons already on disk: no Drive, no download.

The scars are a **separate labelling pass**, not a re-use of the step-05 objects:

- **calendar** year, not fire-year;
- **plain 8-connectivity**, intentionally *not* step 05's 1-px-dilation connectivity, so two
  distinct fires that touch become one scar — which is what the network's definition says;
- a fire straddling 31 December becomes two scars, one per year.

**Two passes**, because each fire-year feeds two calendar years and reading the 248 tiles is the
dominant cost — once per fire-year rather than once per (calendar year, fire-year) halves it:

| Pass | Unit | Does |
|---|---|---|
| `pixels` | fire-year (28) | one sparse `terra::cells()` per fire-year for the accepted-object pixel set → per-tile read of `candseed`+`abs_date` → join on the global cell number → dieback substitution → split into the two calendar halves → `data/scars-pixels-cache/cy<Y>_fy<fy>.rds` (`row`, `col`, `month`) |
| `scars` | calendar year (27) | read the two halves → merge, later month wins on reburn → 8-connected union-find → `area_ha` from the per-row cell area → per-scar vectorize → GPKG + summary CSVs + zipped Shapefile |

Three implementation choices that decide whether this finishes in hours or days:

- **`terra::cells()`, not `rasterize`.** It is sparse — cost and memory scale with the polygons'
  area, not with the template — so one call against the full 9.16 B-cell country template returns
  in ~1 min. `rasterize` would allocate the grid, and per-tile rasterization measured 4–11 h.
- **The cell lookup is keyed the tile's way round.** `d[, obj_date := ct[.(d$cell), on="cell", …]]`
  probes the tile's ~100 k pixels into the keyed object-cell table; `d[ct, on="cell"]` would walk
  all ~55 M object cells once per tile, 248 times per fire-year.
- **`values()` + `which()`, not `as.data.frame(cells=TRUE, na.rm=TRUE)`** — measured 2.3–2.5×
  faster on the tile read, which is the pass's bottleneck, and byte-identical output.

Two smaller ones: the pixel cache carries the object's **integer date**, never its `oid` string
(55 M character entries would cost ~440 MB of pointers and a slow string join); and the reburn
dedup uses `unique(..., by=)` over the sorted table rather than `.SD[1L]` by group, which at ~100 M
rows is orders of magnitude slower.

A handful of pixels carry `candseed > 0` with a **NA `abs_date`**. Step 05 dropped them (its
`na.rm` extract spanned every band), so they belong to no object and both sides exclude them: the
local pass filters them explicitly, and GEE excludes them because they are outside the footprint.

**`scar_id`** is a fresh integer, 1..n within the calendar year, assigned in order of the scar's
first cell — deterministic and stable across re-runs (docs/08 open #5). `oid` cannot be used:
`ee.Image().paint` needs a number.

### 8.1 The built result, and the audit that closes

Run 2026-07-29: pass 1 took **41 min** (28 fire-years, 5 workers), pass 2 **96 min** (27 calendar
years, 2 workers × `OBJ_CORES=6`), no failures in either. Output: **27 packages, 2,734,416 scars,
69,020,102 ha, ~1.1 GB** of zipped Shapefiles, all 27 passing `validate_scar_zips.py`.

**Every accepted object pixel is accounted for, exactly:**

```
  accepted object px (28 fire-years)     911,617,919
  − calendar 1998, not published           1,058,206     (FY1998's Nov–Dec tail, §2)
  = inside the published series          910,559,713
  − intra-year reburn, deduped               269,043     (later month kept)
  = expected calendar px                 910,290,670
    actual, summed over the 27 years     910,290,670     difference 0
```

Nothing is silently lost or double-counted anywhere in the fire-year → calendar-year
transformation. The three sinks are the published years, the one unpublishable edge year, and
reburn — and they sum to the input. Reproduce it from the per-year `scars_<Y>_summary.csv` files
plus the `reburn:` lines in `logs/07_scars_<Y>.log`.

Largest calendar year: **2001, 227,146 scars / 5.25 Mha** — FY2000's very large Jan–Apr 2001
portion (47.2 M px) lands there, which is why it is bigger than either adjacent fire-year total.

**No size class is written into the vectors.** It is derived in GEE from `area_ha`, so the ranges
follow whatever the platform finally registers — the reference script and the Workspace legend
still disagree on the same pixel values 1–8 (docs/08 §5.4), and a legend change must not mean 27
re-uploads.

---

## 9. The scar rasters, and the mask invariant

`07-scar_rasters.py` paints the ingested `scars_<Y>` FCs into the three subproducts. Two departures
from the reference `5-export_annual_burned_id_and_size_by_year`:

- **Our `area_ha` is painted, not recomputed.** The reference maps
  `area_ha = feat.geometry().area()/10000`. For a pixel-edge polygon with interior rings, GEE's
  geodesic polygon area is not the pixel-count area that every other figure we publish derives
  from, and the statistics stage is checked to ~1 % (docs/09).
- **Size classes are applied server-side** from `C.SCAR_SIZE_LOWER_HA`, for the reason in §8.

**The scar mask is forced to equal the month-of-burn mask** — both products are painted with
`.updateMask(month.mask())`, so the requirement holds by construction, and `--check` reports
`month-only` and `scar-only` pixel counts per year so the residual is a number, not an assumption.

---

## 10. Products, and the shape they take

The subproducts are **single multiband images, one band per calendar year** — not ImageCollections
of per-year images. Confirmed in the launch guide ("Imagen multibanda con el ID de cada cicatriz")
and in `ToPublish/2-toAsset-Public`, whose `band_format` property (`burned_monthly_{year}`,
`scar_area_ha_{year}`, …) only means anything for a multiband image.

The **one** ImageCollection in the chain is the stage-3 pivot,
`collection1_fire_mask_v1` — one single-band image per year — which is what step 07 produces and
what every stage-4 script reads.

**One asset per subproduct, with one BAND per year — not one asset per year.** The scar chain is
three images of 27 bands, never 27 images of 3 bands. Reference script 5 builds them that way
(`ee.Image().select()` then `addBands` per year, one export each), script 6 reclassifies every band
of the area image in a single expression, and `ToPublish/2-toAsset-Public` attaches a `band_format`
property per subproduct (`scar_id_{year}`, `scar_area_ha_{year}`) — a `{year}` token that only means
anything if each band *is* a year.

| Asset | Shape | Bands | dtype / pyramiding | Built by |
|---|---|---|---|---|
| `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` | **ImageCollection**, one 1-band image per year | `burned_monthly` (1–12) | uint8 / `mode` | `07-month_of_burn.py` |
| `FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>` | FeatureCollection per year | `scar_id`, `area_ha`, `n_px`, `year` | — | manual ingest of `scars_<Y>.zip` |
| `FINAL_PRODUCTS/…_annual_burned_id_v1` | single multiband image | `scar_id_1999` … `scar_id_2025` | int / `mode` | `07-scar_rasters.py` |
| `FINAL_PRODUCTS/…_annual_burned_area_ha_v1` | single multiband image | `scar_area_ha_1999` … | float / `median` | idem |
| `FINAL_PRODUCTS/…_annual_burned_scar_size_range_v1` | single multiband image | `scar_area_ha_1999` … (see below) | uint8 / `mode` | idem |

⚠️ **The size-range bands are named `scar_area_ha_<year>`, NOT `scar_size_range_<year>`.** That is
not a copy-paste slip: the reference inherits the band names from the area product, and the publish
map lists `annual_burned_scar_size_range: 'scar_area_ha_{year}'`. Renaming them to something more
sensible would break the platform's band lookup.

The **only** ImageCollection in the whole chain is the stage-3 pivot `collection1_fire_mask_v1`;
everything downstream of it is a single multiband image per subproduct.

Naming keeps **our** `COLLECTION-1` spelling (docs/08 open #1) while the asset *names* inside follow
the network exactly; the `mapbiomas-public` copy is renamed at publish time.

**`annual_burned_vectors` uses underscores, unlike the reference's `annual-burned-vectors`.** That is
deliberate, not a typo: everything else under `FINAL_PRODUCTS` is underscored (`FINAL_PRODUCTS`
itself, `..._annual_burned_v1`, `..._annual_burned_area_ha_v1`), so the hyphenated folder is an
oddity in the reference tree. Nothing external reads the path — the only consumer is
`07-scar_rasters.py` via `C.ANNUAL_BURNED_VECTORS`, because we **replaced** reference script
`5-export_annual_burned_id_and_size_by_year` rather than adapting it (§9: we paint our own
pixel-count `area_ha` instead of letting it recompute `geometry().area()`, and we classify sizes
server-side). That script would not run against our tree anyway: it expects per-year assets named
`mbfogo-col1-<year>-v1`, and ours are `scars_<Y>`. If IPAM ever needs to run their version, both the
folder and the per-year names have to be aligned — not just the folder.

---

## 11. What is still open

- **The 27 scar FCs must be ingested by hand** — no GCS bucket is reachable, so the zip is the
  deliverable, same hand-off as docs/06 §12.
- **The stage-4 raster subproducts** (`monthly_burned`, `annual_burned`, both `*_coverage`,
  `frequency_burned`, `accumulated_burned`, `year_last_fire`) are not built yet. They are
  straightforward from the month-of-burn collection; the `*_coverage` ones need the LULC asset
  extended to 2025 (it ends at `classification_2024`).
- **`regiones_fuego_argentina_v1` does not exist** as a FeatureCollection — only the 5-region
  raster. Every reference script uses it for the export geometry and the `region` property; step 07
  uses `ARG_BUFFER_FC` instead and sets `region = 'argentina'`.
- **Scar-size ranges** — reference script vs Workspace legend (docs/08 §5.4). Nothing is blocked
  until the raster is registered, but the legend must match the values written.
- **Asset-name cosmetics**: the month images are
  `mapbiomas_argentina_fire_collection1_fire_mask_v1_<year>`, which carries `v1` mid-name. Only the
  `year` property is read downstream, so this is cosmetic — but if it is to be renamed, do it
  before the publish copy.
