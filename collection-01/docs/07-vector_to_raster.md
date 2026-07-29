# 07 — From classified objects to the calendar-year products

Step 07 is the hand-off from *our* mapping method to the network's calendar-year products. It turns
the step-06 fire-year objects into every published raster: month of burn, the calendar-year scars,
and the derived subproducts.

**Everything Argentina builds lives in step 07** (this file), in the sub-steps below.
**docs/08 is the network's reference** — what Brazil and the other countries do, who owns what, and
the delivery dates. Read docs/08 for the *shape* of a product; read this file for what we actually
run. Where they disagree, this file wins.

## Order of operations

Run in this order; each sub-step needs the one before it.

| # | Sub-step | Script | State |
|---|---|---|---|
| **07a** | **Month of burn** per calendar year → `CLASSIFICATION_COLLECTIONS/collection1_fire_mask_v1` (ImageCollection, one 1-band uint8 image per year, 1–12, masked elsewhere). The pivot everything else reads. | `workflow/07-month_of_burn.py` (GEE) | ✅ **done** — 27/27 exported |
| **07b** | **Calendar-year scars**, 8-connected, labelled locally → `data/scars-upload-cache/scars_<Y>.zip`, then ingested by hand as `FINAL_PRODUCTS/annual_burned_vectors/scars_<Y>` | `workflow/07-calendar_scars.R` + `scripts/run_07_scars.sh` (local, two passes) | ✅ **done** — 27/27 built, gated and ingested, all verified against the local build |
| **07c** | **Scar rasters** — `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range`, painted from the ingested scars and masked to 07a | `workflow/07-scar_rasters.py` (GEE) | ✅ **done** — 3/3 exported and verified on the landed assets (§9.1) |
| **07d** | **The nine derived subproducts** — `monthly_burned`, `annual_burned`, both `*_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`), `year_last_fire` | `workflow/07-subproducts.py` (GEE) | 🔄 **exporting** (9 tasks, 2026-07-29; the 4 `*_coverage` ones re-launched against LULC col-3, §12.1) |

Commands, in order:

```bash
# 07a  (done; re-runnable, skips existing assets)
$PYTHON collection-01/workflow/07-month_of_burn.py --all --launch

# 07b  (done) — pass 1 must finish before pass 2: a calendar year needs BOTH its fire-years
tmux new-session -d -s s07pix  '/abs/path/collection-01/scripts/run_07_scars.sh pixels -j 5'
tmux new-session -d -s s07scar 'OBJ_CORES=6 /abs/path/collection-01/scripts/run_07_scars.sh scars -j 2'
$PYTHON collection-01/scripts/validate_scar_zips.py              # gate the zips  -> 27/27
$PYTHON collection-01/scripts/validate_scar_zips.py --ingested   # gate the upload -> 27/27

# 07c  (in flight)
$PYTHON collection-01/workflow/07-scar_rasters.py --check --years 2003,2020 --roi=-61.6,-25.6,-61.1,-25.1
$PYTHON collection-01/workflow/07-scar_rasters.py --launch
#   if the monolith fails:  --per-year --launch   then   --merge --launch

# 07d  (in flight) — all nine derive from 07a, so they do NOT wait for 07c
$PYTHON collection-01/workflow/07-subproducts.py --check     # band bookkeeping + ROI counts
$PYTHON collection-01/workflow/07-subproducts.py --launch     # 9 tasks
#   one product only:  --only frequency_burned
```

`scripts/run_07_scars.sh` is the launcher for 07b (two modes, resumable, biggest-year first, one
process per year — same pattern as `run_05_years.sh` / `run_06_predict.sh`).

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

⚠️ **That check has not actually run yet.** The one task submitted (`mobstats_2000`) **FAILED** with
*"Unable to export features with null geometry"* — `ee.Feature(None, …)` cannot be written to a table
**asset**. Fixed 2026-07-29 (the feature now carries a placeholder point); the 27 tasks still need
submitting.

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

**No size class is written into the vectors.** It is derived in GEE from `area_ha`
(`C.SCAR_SIZE_LOWER_HA`), so the ranges are a one-line, one-task change rather than 27 re-uploads.
That mattered: the reference script's ranges turned out **not** to match the published legend, and the
classes were switched to the legend's after the vectors were already built (docs/08 §5.4).

---

## 9. The scar rasters, and the mask invariant

`07-scar_rasters.py` paints the ingested `scars_<Y>` FCs into the three subproducts. Two departures
from the reference `5-export_annual_burned_id_and_size_by_year`:

- **Our `area_ha` is painted, not recomputed.** The reference maps
  `area_ha = feat.geometry().area()/10000`. For a pixel-edge polygon with interior rings, GEE's
  geodesic polygon area is not the pixel-count area that every other figure we publish derives
  from, and the statistics stage is checked to ~1 % (docs/09).
- **Size classes are applied server-side** from `C.SCAR_SIZE_LOWER_HA`, for the reason in §8. The
  values are the **published legend's**, not the reference script's: `< 10 / 10–250 / 250–500 /
  500–5 000 / 5 000–10 000 / 10 000–50 000 / 50 000–100 000 / ≥ 100 000 ha`, confirmed from the
  Coleção 5 legend-code PDF and the live col-5 platform legend (docs/08 §5.4). We write **level 2
  only** (1–8); the platform derives its level-1 aggregation. Argentina populates all 8 classes —
  24 scars ≥ 100 000 ha, largest 219 410 ha in calendar 2003.

**The scar mask is forced to equal the month-of-burn mask** — both products are painted with
`.updateMask(month.mask())`, so the requirement holds by construction, and `--check` reports
`month-only` and `scar-only` pixel counts per year so the residual is a number, not an assumption.

### 9.1 The built result, verified on the LANDED assets

All three exported 2026-07-29. Checked against the exported assets, not the graph — a different
question, and the one that catches export-time grid or masking surprises:

| Asset | Bands | dtype | Grid |
|---|---|---|---|
| `…_annual_burned_id_v1` | 27, `scar_id_1999 … scar_id_2025` | int | pinned, 74085 × 123601 |
| `…_annual_burned_area_ha_v1` | 27, `scar_area_ha_1999 …` | float | idem |
| `…_annual_burned_scar_size_range_v1` | 27, `scar_area_ha_1999 …` | int | idem |

Over the Chaco audit box, calendar 2003 / 2020 / 2025: `month px == scar px == size px`
(15,492 / 32,559 / 27,508), **`month-only = scar-only = 0`** in every year, and **0** pixels where the
stored size class disagrees with recomputing it from the painted `area_ha`. The mask invariant holds
on the published rasters, not just in the expression that built them.

**The monolith held**, so the `--per-year` + `--merge` fallback and the `--roi` smoke test were
deleted rather than left as a second path to maintain (docs/08 open decisions do not cover this; it
was a build-time hedge). No GEE limit was ever measured against one task painting 27
FeatureCollections — it simply worked. The empty `FINAL_PRODUCTS/scar_year_parts` collection that a
dry run once created is left for Iván to delete.

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
- ~~The stage-4 raster subproducts~~ — **built and exporting** (07d, §12). The LULC-to-2025 item was
  never a blocker: duplicating 2024 forward is the network's own answer (§12.4).
- **`regiones_fuego_argentina_v1` does not exist** as a FeatureCollection — only the 5-region
  raster. Every reference script uses it for the export geometry and the `region` property; step 07
  uses `ARG_BUFFER_FC` instead and sets `region = 'argentina'`.
- ~~Scar-size ranges~~ — **settled**: the published legend's, confirmed from two independent sources
  (docs/08 §5.4). No IPAM ruling needed. Do not copy `6-export_scar_size_range_by_year`.
- **Asset-name cosmetics**: the month images are
  `mapbiomas_argentina_fire_collection1_fire_mask_v1_<year>`, which carries `v1` mid-name. Only the
  `year` property is read downstream, so this is cosmetic — but if it is to be renamed, do it
  before the publish copy.

---

## 12. Sub-step 07d — the nine derived subproducts

Everything here derives from **07a's month-of-burn collection** plus the **MapBiomas LULC**. No new
vectors, no local work, no re-labelling. Script: `workflow/07-subproducts.py`, **9 export tasks
launched 2026-07-29**.

Reference: `Reference/2-Collection_Fire_Subproducts/1_burned_area_products_monthly_annual_coverage`
(products 1–4), `2_burned_area_frequency_accumulated_coverage` (5–8), `3_year_last_fire` (9).
**Do not innovate here** — copy the encodings exactly; they are what the platform decodes.

### 12.1 The four settled answers

**1. Which LULC layer?** `C.PRODUCT_LULC` — the **published MapBiomas Argentina land-cover
integration**, bands `classification_<year>`. **NOT `veg_fire`.** `veg_fire` is our internal
25-class fire-modelling remap (region-specific, built for the burn-probability model); it is not the
published LULC legend and no other country has it. Using it would make our `*_coverage` products
undecodable by the platform and incomparable across the network. `veg_fire`'s only role in step 07 is
the argument that the LULC *mask* is already embedded upstream (docs/08 §6.2) — it never enters a
product.

⚠️ **`C.PRODUCT_LULC` is deliberately a SECOND constant, not a repoint of `C.MAPBIOMAS_LULC`.**
`MAPBIOMAS_LULC` is the **model-side** input: `utils/functions.py::get_mb_class_band` derives
`veg_fire` from it, which drives the step-01 training export and the step-03/04 candidate mask, so
the entire collection's SNIC candidate set was built against that exact asset (LULC col-2 v8) and it
must stay frozen there. The coverage products answer a different question — "which *published* land
cover burned in year Y" — so they track whatever LULC Argentina publishes. **The two pointing at
different collections is not an inconsistency to fix.**

Currently `PRODUCT_LULC` = **LULC collection 3, v1** (`mapbiomas_argentina_collection3_integration_v1_buffer`),
set 2026-07-29. Verified against col-2 v8, which 07d was first launched with:

| | col-2 v8 | col-3 v1 |
|---|---|---|
| Bands | 40, 1985–2024 (2025 duplicated forward) | **41, 1985–2025 — 2025 is native** |
| Grid | origin −76.26696762174738 / −14.999260130472063, 89361 × 155938 | **byte-identical** |
| Offset from the SNIC lattice | 9953 col / −25102 rows (integer) | **identical** |
| Footprint ⊇ 2 km buffer | yes | yes |
| Class codes present | 3,4,6,9,11,12,15,19,21,24,25,27,33,34,36,63,66,73,77 | **identical**, max **77** |

The grids being byte-identical is why the switch cost nothing: the §12.4 alignment proof and the
§12.5 decode audit both transferred rather than needing to be redone (re-run against col-3: all 27
years `lulc_missing = 0`, every residual 0). **Max class 77 < 100 matters** — it is what makes
`M*100 + L` and `freq*100 + L` decodable and `mod 100` exact; measured peak encoded values in the
audit box are 1277 (uint16) and 812 (int16). If a col-3 v2 supersedes v1, change that one line and
re-export the four coverage products.

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
to reconcile. (Not to be confused with the **statistics** exports, docs/09, which *are* cut by
territory — that is a different stage and a different layer.)

**4. Shape.** One asset per subproduct, one **band** per year — never one asset per year (§10).

### 12.2 The nine products

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

Export with `crs=C.SNIC_CRS` + `crsTransform=C.SNIC_TRANSFORM` (never `scale=30`, §3),
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

### 12.3 Four traps in the reference code

1. **`year_last_fire` bands are `classification_<year+1>`** — an off-by-one the platform expects.
   Preserve it; it looks like a bug and is not.
2. **The `accumulated_burned` filename typo.** Script 2 builds
   `'..._accumulate' + coll_n + '_burned_v1'` → `..._accumulate1_burned_v1`, while the publish list
   expects `..._accumulated_burned_v1`. Use the correct spelling.
3. **`frequency_burned`'s band name is unresolved.** Script 2 writes `fire_frequency_<y1>_<y2>`, but
   `ToPublish/2-toAsset-Public`'s `band_format` map says `frequency_burned_{year1}_{year2}`. The
   `accumulated_*` pair is consistent (`fire_accumulated_*` both places); only frequency disagrees.
   **Confirm with IPAM which the platform reads** — docs/08 open #9.
4. **The `*_coverage` products are the easiest to forget** and are exactly what the statistics stage
   reads (docs/09 §2). Four of the nine are coverage products.

### 12.4 The LULC year — never a blocker, and now moot

It was listed as blocking all four `*_coverage` products that `C.MAPBIOMAS_LULC` ends at
`classification_2024` while the series runs to 2025. **It never blocked anything**: duplicating the
last year forward *is* the network's answer (`.slice(-1).rename(['classification_2025'])`, in every
reference country), and the script does it and prints the substitution. The available band list is
read from the **asset**, never from `C.MB_LIMIT_YEAR`, so this self-corrects whenever the source is
extended or repointed — no code change was needed to move to col-3.

With `C.PRODUCT_LULC` on LULC col-3 v1 the question is moot anyway: it carries
`classification_2025` natively, so **nothing is duplicated forward** and the last year of the fire
series is crossed with its own land cover.

This is the **only** remaining place LULC enters our pipeline — the stage-3 LULC *mask* does not
apply to us (docs/08 §6.2).

**The LULC sits on our lattice.** Verified 2026-07-29 for col-2 v8 and col-3 v1 alike: the LULC has
the same 30 m pixel size as the SNIC grid, and its origin is offset by exactly **9953 columns /
−25102 rows — integers**.
So combining it with the month raster on `C.SNIC_TRANSFORM` involves no resampling and no half-pixel
shift, which for a *categorical* band is the difference between a class code and its neighbour's.
Its footprint also `contains` the 2 km buffer, so no burned pixel can fall outside the LULC and
silently drop out of a coverage product (`add` propagates the mask). Measured over the Chaco audit
box, all 27 years: `lulc_missing = 0`, and `month == annual == coverage` to the pixel.

### 12.5 What was verified before launch

`--check` prints the band bookkeeping for all nine products plus per-year ROI counts; that plus a
value-level decode of every encoding was run on the Chaco 0.5° box before submitting:

| Check | Result |
|---|---|
| Band names / counts | 27 / 27 / 27 / 27 / 53 / 53 / 53 / 53 / 27, `year_last_fire` = `classification_2000 … classification_2026` |
| `monthly_burned_coverage` decode | `max │mc//100 − month│ = 0`, `max │mc mod 100 − L│ = 0` |
| `annual_burned_coverage` decode | `max │ac − L│ = 0` |
| `frequency_burned_coverage` decode | `max │fc//100 − freq│ = 0` |
| `accumulated_burned_coverage` decode | `max │acc_cov − L(2025)│ = 0` (window `1999_2025`, moving end 2025) |
| Single-year window vs annual | `freq_2025_2025` = `annual_2025` = **27,508 px**, exactly |
| Cross-product mask agreement | `freq_1999_2025` = `accum` = `accum_cov` = `year_last_fire` = **241,281 px**, exactly |
| `year_last_fire` values | `classification_2000` is 1999 only; `classification_2026` spans 1999–2025 with the expected per-year counts |

Note the ROI histograms taken with `frequencyHistogram` come out a few pixels below the
`sum().unweighted()` counts (241,195 vs 241,281) — that is `reduceRegion`'s **edge weighting** of
partial pixels at the box boundary, the same artefact §9 records for the scar check, not a
disagreement between products.

### 12.6 Three departures from the reference, all plumbing

The encodings are copied verbatim; what differs is how the graph is fed.

1. **The grid is pinned** (`crs` + `crsTransform`), never `scale=30` — §3, the same rule as 07a/07c.
2. **`region = ARG_BUFFER_FC`** instead of `regions.union().geometry()`, because
   `regiones_fuego_argentina_v1` does not exist as a FeatureCollection (§11).
3. **All nine products read the 07a month collection**, whereas the reference exports `annual_burned`
   first and has scripts 2 and 3 read *that asset*. `annual_burned` is *defined* as `month > 0`, so a
   frequency built from the month images is bit-identical to one built from the exported annual
   product — and deriving everything from the single pivot makes the nine consistent **by
   construction** rather than by sequencing. The operational win is that the nine tasks are
   independent: nothing waits for a 27-band export to land, and any one product can be re-run alone
   (`--only`). Confirmed by the two exact cross-product agreements in §12.5.

The reference's `accumulated_burned` filename typo is not copied (§12.3.2).

### 12.7 Namespace the task descriptions — the compute project is shared

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

The first batch went out under the bare descriptions, so `LEGACY_DESCRIPTIONS` keeps them accepted by
the in-flight test — otherwise a re-run before they landed would have double-submitted. **Delete that
fallback once those nine tasks have finished**; it is the collision-prone form the prefix exists to
retire.
