# 08 — Post-processing: building the MapBiomas Fuego products

Everything up to step 07 is **ours**: our own mapping method (obs-level burn probability → time-series
metrics → SNIC objects → object-based classification). Step 08 is **not ours** — it is the
**post-processing every MapBiomas Fuego country runs**, unchanged, so the published products are
identical in name, band format, encoding, dtype and legend across the network.

> **Rule for this step: do not innovate.** Copy the reference scripts (§4–5) and adapt only the
> country-specific bits (paths, LULC, regions, mask classes). Anything else we change breaks
> cross-country comparability, the Workspace legends and the platform that reads these assets.

**Scope of this doc:** stages 1–4 of the launch process — the **GEE assets** (the masked collection +
the subproducts). Stage 5 (statistics), stage 6 (public assets + Workspace) and the launch-preparation
track live in **[`09-statistics.md`](09-statistics.md)**.

**Argentina's dates:** assets delivered to MapBiomas Argentina **31 July 2026**; public launch
**24 September 2026**. §7 says what belongs to each.

---

## 1. Reference material

| What | Where | Notes |
|---|---|---|
| **Launch-process guide** — the network's own step-by-step (source for §2) | [*MapBiomas Fuego — Guía del Proceso de Lanzamiento*](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit), 39 slides | **Readable by tooling** — the `/edit` view is a JS shell, but the PDF export is public: `curl -sL -o slides.pdf "https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/export/pdf"` then read the PDF. |
| **Reference code** — source of truth for §5 | Local clone: `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/` | GEE Code Editor repo, remote `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire` (branch `master`). Files have **no extension**. **Read-only for us** — the network's repo; never push. |
| **Mapping method paper** (theirs, not ours) | Alencar, A. A. C., Arruda, V. L., Silva, W. V. da, Conciani, D. E., Costa, D. P., Crusco, N., Duverger, S. G., Ferreira, N. C., Franca-Rocha, W., Hasenack, H., Martenexen, L. F. M., Piontekowski, V. J., Ribeiro, N. V., Rosa, E. R., Rosa, M. R., Santos, S. M. B., Shimbo, J. Z., Vélez-Martin, E. (2022). *Long-Term Landsat-Based Monthly Burned Area Dataset for the Brazilian Biomes Using Deep Learning.* **Remote Sensing 14(11), 2510.** <https://doi.org/10.3390/rs14112510> | What our steps 01–07 replace (§3). |
| **ATBD** | [ATBD MapBiomas Fogo Colección 4](https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/06/ATBD-MapBiomas-Fogo-Colecao-4.pdf) | Product definitions in prose; also the template for **our own ATBD** (docs/09). |
| **Legend colours / codes** | `Mapbiomas-Fogo-Legenda-Col4.xlsx` (linked from the guide) + each country's *códigos de la leyenda* page | Authoritative pixel values + hex colours per subproduct. **Use this, don't eyeball colours** from the slides. |
| **Per-country examples** | Peru: [descargas](https://peru.mapbiomas.org/descargas-mapbiomas-fuego/), [ATBD](https://peru.mapbiomas.org/wp-content/uploads/sites/14/2025/10/ATBD-General-MapBiomas-Fuego-Peru-Col-1-ES.pdf) · Paraguay: [descargas](https://paraguay.mapbiomas.org/descargas/), [ATBD por etapa](https://paraguay.mapbiomas.org/atbd-entienda-cada-etapa/) | Closest models for what Argentina must produce. |

---

## 2. The launch process — six stages

| # | Stage | Where |
|---|---|---|
| 1 | **Finalización de la colección anual** de la serie histórica | ours (steps 01–07) |
| 2 | **Versión consolidada (sin máscaras)** — one ImageCollection, all years and regions | §5.2 |
| 3 | **Versión final (con máscaras)** — LULC mask + solitary-pixel removal + month coding | §5.2 |
| 4 | **Generación de subproductos** | §5.3–5.4 |
| 5 | **Estadísticas preliminares** → Looker Studio | docs/09 §2 |
| 6 | **Assets públicos + catastro en Workspace + enlaces directos** | docs/09 §3–4 |

> ⚠️ **Validation gate: "antes de avanzar a la siguiente etapa, cada producto debe ser validado por el
> equipo del país correspondiente."** Expect a human check between stages, not one unattended run.
> `1-Toolkit_Collection1/Visualize-Collections-Fire` exists for that visual validation.

**Who does what** (the guide's intent is *"fortalecer la independencia de cada país"* — expect to own
more of this in collection 2):

| Task | Owner |
|---|---|
| Standardising into a single ImageCollection; mask script; subproduct generation | **Brazil support** (IPAM — Wallace Silva, Vera Arruda) |
| Copy of subproducts to the public repository with the standardised properties | **Brazil** |
| Registering assets + legends in Workspace | Brazil support |
| **Territorial layers** for platform statistics | **us** |
| Reviewing and validating every product | **us** |

---

## 3. Their mapping method vs ours — why only step 08 is shared

**Alencar et al. 2022 (all other countries):** annual Landsat **quality mosaics** → burned/unburned
samples → **deep neural networks** trained off-platform → an **annual** burned/not-burned raster per
region-year. The **month is not mapped**: it is reconstructed from the date of **minimum NBR** in the
annual mosaic (its `monthOfYear` band), so the monthly product is a re-labelling of the annual one.
Everything is calendar-year.

**Ours (steps 01–07):** per-observation logistic-regression burn probability → per-pixel
burn-probability time-series metrics → SNIC segmentation into fire objects on a **non-calendar
fire-year** → object-level XGBoost fire/non-fire classification. Our month of burn is **measured**
per pixel (`abs_date`), not inferred from min-NBR.

Two consequences step 08 must absorb — both resolved in §6:

1. **Calendar-year framing.** Their chain is indexed by calendar year; our objects live in fire-years.
2. **Month source.** Ours is better grounded but comes from a fire-year raster, so it has to be
   re-partitioned into calendar years.

---

## 4. Layout of the reference repo

```
mapbiomas-latam-fire-gee/
├── 00_Tools/                          # Palettes.js ('mensual', 'frecuencia25'), Legends.js
├── 01_Mosaics/                        # THEIR mapping inputs (quality mosaics) — we don't use this
├── 1-Toolkit_Collection1/             # sample collection + Visualize-Collections-Fire (validation app)
├── 2-Statistics/                      # area statistics → CSV (docs/09 §2)
├── 4-Collection_anual_final_products/ # ⭐⭐ THE CHAIN
│   ├── Reference/                     #   ⭐ copy THIS one
│   │   ├── 1-Post_classifications/    #     stages 2–3   (§5.2)
│   │   ├── 2-Collection_Fire_Subproducts/  # stage 4     (§5.3–5.4)
│   │   └── ToPublish/                 #     stage 6      (docs/09 §3)
│   └── bolivia/ chile/ colombia/ paraguay/ peru/ suriname/   # country adaptations — best examples
└── 5-Monitor-Fuego/                   # near-real-time monitor — out of scope
```

**Each country makes its own copy of `Reference/` and adapts it** (the guide says so explicitly).
`bolivia/` and `peru/` are the most complete and the best model for an `argentina/` folder. Scripts are
Spanish-commented, parameterised by `var country = '…'` + `var coll_n = '1'`.

---

## 5. The reference chain, stage by stage

### 5.1 Asset topology (their convention)

```
projects/mapbiomas-<country>/assets/FIRE/
├── COLLECTION1/CLASSIFICATION/                     # raw model output, per region-year, versioned
├── COLLECTION1/CLASSIFICATION_COLLECTIONS/
│   ├── collection1_fire_no_mask_v1                 # ImageCollection — approved, version stripped
│   └── collection1_fire_mask_v1                    # ImageCollection — LULC-masked, month-coded ← pivot
├── COLLECTION1/FINAL_PRODUCTS/                     # multiband subproducts (§5.3–5.4)
│   └── annual-burned-vectors/mbfogo-col1-<year>-v1 # FeatureCollection per year (scars)
└── AUXILIARY_DATA/regiones_fuego_<country>_v1      # fire regions
```
Published copies go to `projects/mapbiomas-public/assets/<country>/fire/collection1/` (docs/09 §3).

> **Naming gotcha:** they use **`COLLECTION1`** (no hyphen), `AUXILIARY_DATA` (underscore) and
> lowercase `mapbiomas_<country>_…`; our repo uses **`COLLECTION-1`** / `AUXILIARY-DATA`
> (`_FIRE_ROOT` in `utils/constants.py`). See §8.1.

### 5.2 `1-Post_classifications` — stages 2 and 3

**`1-final_classifications_col1_no_masks`** (stage 2) — creates the destination ImageCollections if
absent, then copies each **approved** classification from `CLASSIFICATION/` into
`collection1_fire_no_mask_v1`, **stripping the `_vN` token**. A hand-curated `final_collection` list
picks the winning version per region-year. Goal: **one ImageCollection covering all years and regions.**

**`2-export_col1_masks_lulc_and_pixel_date`** (stage 3) — per image:

1. **LULC mask.** Select LULC band `classification_<year>`, test membership in a **per-region class
   list**, drop those pixels. Reference ships `[26]` (water) for every region; the guide's example is
   `[26, 22]` (water + non-vegetated); other countries add `9` (forest plantation). A commented block
   shows the extras pattern (90 m `focalMax` buffer around water). The last LULC year is **duplicated
   forward** (`classification_2024` → `classification_2025`).
2. **Solitary-pixel removal.** `connectedPixelCount({maxSize: 100, eightConnected: false})` → pixels
   with `count <= 4` set to 0 → `selfMask()` → `reproject('EPSG:4326', null, 30)`. I.e. **4-connected
   components of ≤ 4 px are deleted.**
3. **Month coding.** Output value = the `monthOfYear` band of the annual quality mosaic, masked by the
   cleaned scar. **`pixel_unit: 'month'`.** ← *this is the step we replace (§6)*.
4. **Properties:** `source: 'mapbiomas-fuego'`, `pixel_unit: 'month'`, `name`, `year`, `region`,
   `system:time_start/end` (Jan 1 → Jan 1 of year+1).
5. Export with `pyramidingPolicy: 'mode'`, `scale: 30`, `maxPixels: 1e13`.

**The masked collection — one image per region-year, value 1–12 = month of burn, masked elsewhere — is
the single input to everything downstream, and where our pipeline lands (§6).**

### 5.3 Stage 4, scripts 1–3 — raster subproducts

Each mosaics the masked collection per year into one multiband image (band per year, 1999–2025 for
South America), exported to `FINAL_PRODUCTS/` with `pyramidingPolicy: mode`, `scale: 30`.

| Subproduct | Band name | Encoding | dtype | Script |
|---|---|---|---|---|
| `monthly_burned_coverage` | `burned_coverage_YYYY` | `month * 100 + lulc_class` | uint16 | `1_burned_area_products_monthly_annual_coverage` |
| `annual_burned_coverage` | `burned_coverage_YYYY` | `(month ≥ 1) * lulc_class` | uint8 | idem |
| `monthly_burned` | `burned_monthly_YYYY` | month `1–12` | uint8 | idem |
| `annual_burned` | `burned_area_YYYY` | `0/1` | uint8 | idem |
| `frequency_burned` | `fire_frequency_<y1>_<y2>` | years burned in the window | int16 | `2_burned_area_frequency_accumulated_coverage` |
| `frequency_burned_coverage` | `fire_frequency_<y1>_<y2>` | `freq * 100 + lulc_class(y2)` | int16 | idem |
| `accumulated_burned` | `fire_accumulated_<y1>_<y2>` | `freq ≥ 1` → `1` | uint8 | idem |
| `accumulated_burned_coverage` | `fire_accumulated_<y1>_<y2>` | `freq_coverage mod 100` (LULC class) | uint8 | idem |
| `year_last_fire` | `classification_YYYY` | calendar year of most recent fire up to that band | uint16 | `3_year_last_fire` |

- **Frequency windows are two-sided:** a forward pass accumulates `y_first…y`, a backward pass
  `y…y_last`; both band sets are concatenated and sorted. Never-burned pixels are `selfMask`ed out.
- **`year_last_fire` is an iterative carry-forward** (`where(burned, year)`, else keep previous).
  ⚠️ Bands are named `classification_<year+1>` — preserve that off-by-one; the platform expects it.
- **Don't copy the typo** in script 2: `outFileNameAccumulated` builds `…_accumulate1_burned_v1`
  where the publish list expects `…_accumulated_burned_v1`.
- ⚠️ **The `*_coverage` products are easy to forget** and are exactly what the statistics read
  (docs/09 §2). They need our LULC asset extended to 2025 (§8.3).

### 5.4 Stage 4, scripts 4–6 — the scar-size chain

Their route, in four sub-steps:

1. **`4-export_vectorization_annual_burned`** — export each `burned_area_YYYY` band as a **binary
   GeoTIFF to Drive**.
2. **Colab** (`Col1_Fire_4.2-subproduct_export_vectorization_annual_burned.ipynb`,
   [link](https://colab.research.google.com/drive/1JVQMcTVbj9hRA8iIFMteTl86e4FmX_4E)) — polygonize,
   assign a unique integer `id`, upload back as `annual-burned-vectors/mbfogo-col1-<year>-v1`.
3. **`5-export_annual_burned_id_and_size_by_year`** — `area_ha = geometry().area()/10000`, then
   `ee.Image().paint(fc,'id')` → `annual_burned_id` (band `scar_id_YYYY`, int, pyramiding `mode`) and
   `.paint(fc,'area_ha')` → `annual_burned_area_ha` (band `scar_area_ha_YYYY`, float, pyramiding `median`).
4. **`6-export_scar_size_range_by_year`** — reclassify into 8 size classes; band names inherited
   (`scar_area_ha_YYYY`); product `annual_burned_scar_size_range`.

**Why the Drive round-trip exists:** GEE cannot label arbitrarily large connected components —
`connectedPixelCount` caps at `maxSize ≤ 1024` px (≈92 ha at 30 m) and `connectedComponents` is
similarly bounded. Real scars exceed that, so labelling must happen outside GEE. **We skip sub-steps
1–2 entirely: we already own the labels** (§6).

⚠️ **The size ranges in the reference script and in the Workspace legend disagree while using the same
pixel values 1–8** — a raster built with one and registered with the other is silently wrong:

| pixel | LatAm reference script | Workspace legend "Scar size" (Brazil col-5) |
|---|---|---|
| 1 | `< 5 ha` | `< 10 ha` |
| 2 | `5–25 ha` | `10–250 ha` |
| 3 | `25–50 ha` | `250–500 ha` |
| 4 | `50–250 ha` | `500–5 000 ha` |
| 5 | `250–500 ha` | `5 000–10 000 ha` |
| 6 | `500–1 000 ha` | `10 000–50 000 ha` |
| 7 | `1 000–5 000 ha` | `50 000–100 000 ha` |
| 8 | `≥ 5 000 ha` | `> 100 000 ha` |

The Workspace legend is also **two-level** (level-1 aggregates at pixel values 10/20/30/40/50: `<250`,
`250–500`, `500–10 000`, `10 000–100 000`, `>100 000` ha), defined as *"annual burned area classified
into scar size categories, based on sets of spatially connected pixels within the same year."*
Brazil's ranges are tuned to Amazon-scale scars; ours are far smaller, so **the LatAm ranges are almost
certainly right for us** — but confirm, because the registered legend must match the pixel values we
write (§8.6).

---

## 6. Argentina's route — calendar-year products from fire-year objects

### 6.1 The design in one line

**Upload vectors only; let GEE do the pixel work.** Two FeatureCollections go up; every raster product
is built server-side from them plus the **SNIC assets that are already in GEE**.

| Upload | Content | Feeds |
|---|---|---|
| `fires_<fire_year>` (28 FCs, one per fire-year 1998–2025) | our **step-06 filtered** fire objects: geometry + `oid`, `year_calendar`, `date_median` | the **month-of-burn / annual / coverage / frequency / accumulated / year-last-fire** chain |
| `scars_<calendar_year>` (27 FCs, 1999–2025) | **calendar-year scar parts**: geometry + `scar_id` (int), `area_ha`, `oid` | `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range` |

Rationale: the per-pixel dates we need are **already in GEE** as `C.SNIC_METRICS_COL`
(`snic_metrics_<fy>`: `abs_date`, `veg_fire`, `n`, `burned_around_*`) alongside `C.SNIC_COL`
(`snic_<fy>.candseed`). So there is no reason to upload rasters — the polygons are far lighter than
28 fire-years × ~248 cartas of imagery. **We knowingly recompute in GEE the per-pixel calendar year and
month that R already computed locally; that redundancy is the price of not moving the data.**

### 6.2 Why fire-year → calendar-year is a clean partition

The fire-year runs **1 May Y → 30 Apr Y+1** (`docs/04` §2), and fire-years partition the calendar. So:

```
calendar year Y  =  Jan–Apr Y  from fire-year (Y−1)      ⊎  May–Dec Y  from fire-year Y
```

Exactly **two** source fire-years per calendar year, disjoint in time — a union, not an overlay
requiring arbitration (except genuine reburn, §6.4.3). It also lands exactly on our target series:
FY1998 exists only as its Jan–Apr 1999 part, which is precisely what calendar 1999 needs, so the
series is **1999–2025** — matching `C.YEARS` and the network's South-America range.

### 6.3 What already exists on disk / in GEE

| Thing | Where | Notes |
|---|---|---|
| SNIC per-pixel bands, local | `data/snic-direct/<fy>/<carta>.tif`, 28 fire-years × ~248 cartas | `abs_date, veg_fire, n, burned_around_{1,2,3}, candseed`, Int16 |
| SNIC per-pixel bands, **in GEE** | `C.SNIC_METRICS_COL/snic_metrics_<fy>` + `C.SNIC_COL/snic_<fy>` (`candseed`) | candseed is **not** duplicated into the metrics asset |
| `abs_date` encoding | whole **days since 1970-01-01** (`05-objects_metrics.R:84`, `EPOCH`) | |
| Objects + metrics | `data/snic-polygons/objects_<fy>.gpkg`, `_raster_metrics.csv`, `_shape_metrics.csv` | metrics carry `date_{median,min,max}`, `year_calendar`, `area_ha`, `n_pixels`, `seed_mean`, `frac_c*` |
| Per-pixel calendar year | **already computed in step 05** — `05-objects_metrics.R:227`: `cyear := year(as.IDate(abs_date, origin = EPOCH))` | |

### 6.4 Three gotchas that decide correctness

**1. `candseed == 3` pixels must not use their own `abs_date`.** Their date is a *next-year spring*
dieback date, so per-pixel binning would throw them into the wrong calendar year and split the scar.
Step 05 already excludes them from object date/year stats (`dtf <- dt[candseed != 3L]`, line 235), so
`year_calendar` and `date_median` are clean — but the **raster still carries the raw dieback date**.
Rule (already the intent in `docs/04` §4.3 and `docs/07`): a dieback pixel takes the **parent object's**
date, so it joins the part containing the object's `year_calendar`. In GEE:
`date = abs_date.where(candseed.eq(3), paint(fires_fc, 'date_median'))`.

**2. Painting a polygon fills its interior — that is not our pixel set.** Step 05's accepted pixels
exclude, among others, `candseed==3` pixels east of lon −70.6 (`docs/07`). `ee.Image().paint(fc, 1)`
fills holes and gaps those exclusions created. **Always intersect the painted mask with the real burned
mask**: `objmask = paint(fires_fc,1).gt(0).and(candseed.gt(0))` — and replicate the lon −70.6 rule if
`candseed==3` pixels survive inside a polygon footprint. Never trust polygon fill alone.

**3. Reburn inside one calendar year** is the only genuine conflict: a pixel burning Feb *Y* (from
FY *Y*−1) and Sep *Y* (from FY *Y*) is claimed by both sources. The published raster allows one month
per pixel per year — take the **later** date (what the pixel looks like at year end), and record that
the earlier scar loses those pixels in `annual_burned` while keeping them in its own fire-year object.

### 6.5 Building the monthly layer in GEE

Per calendar year `Y`, for `fy in {Y-1, Y}`:

```js
var m   = ee.Image(SNIC_METRICS + '/snic_metrics_' + fy);       // abs_date, …
var cs  = ee.Image(SNIC_COL     + '/snic_'         + fy).select('candseed');
var fc  = ee.FeatureCollection(OBJECTS + '/fires_' + fy);       // step-06 filtered
var objmask = ee.Image().paint(fc, 1).gt(0).and(cs.gt(0));      // §6.4.2
var date = m.select('abs_date')
            .where(cs.eq(3), ee.Image().paint(fc, 'date_median'));  // §6.4.1
// → keep pixels whose calendar year == Y, value = month 1–12
```
then mosaic the two contributions, later date winning (§6.4.3).

> **GEE has no per-pixel date decomposition.** `abs_date` is days-since-epoch, and there is no
> per-pixel `ee.Date`. Decode by **thresholding against month boundaries**: with `b_k` = day-number of
> the first day of each month, `k = Σ_k date.gte(b_k)` gives the month index, from which year and month
> follow by integer arithmetic. Only the ~24 boundaries spanning the two candidate fire-years are
> needed per output year, so it's cheap.

### 6.6 Building the calendar-year scar parts

Step 05 already groups by `pid`; grouping by **`(pid, cyear)`** instead yields, per object × calendar
year: pixel count, `area_ha`, date summaries and the modal month — i.e. the calendar-year **scar parts**,
with areas, **without any new labelling pass and without re-vectorizing**. Then:

- `scar_id` — a fresh **integer**, unique within the calendar year (`ee.Image().paint` cannot use our
  string `oid`; keep `oid` as an extra property for traceability). Must be stable across re-runs (§8.5).
- `area_ha` — from the part's pixel count × cell area, exactly as step 05 computes area today.
- Dieback pixels follow their parent object's part (§6.4.1).
- Upload as `scars_<Y>`; then reference scripts 5 and 6 run **unchanged** on it.
- **Do not simplify the geometries** on export — vertices follow pixel edges, and simplification would
  misalign the painted rasters from the month raster.

### 6.7 What this buys us

- **Per-pixel month, measured** — strictly better grounded than min-NBR, at no transport cost.
- **`annual_burned`, `monthly_burned` and `scar_size` agree pixel-for-pixel**, because all three derive
  from the same per-pixel calendar-year assignment. (The alternative — painting each whole object into
  its modal `year_calendar` — is cheaper but makes `scar_size` disagree with `annual_burned` on every
  scar that straddles 31 December, which in Argentina is not a corner case: the Patagonian/Pampean
  season peaks Dec–Feb. That is exactly why we chose a non-calendar fire-year.)
- **Faithful to the network's semantics** — their scars are calendar-clipped too (they polygonize the
  annual mask) — with one improvement: our parts come from *fire objects*, so two distinct fires that
  happen to touch stay separate instead of merging into one scar.
- **Our fire-year objects survive as a richer database**, ours to publish later as vectors
  (Brazil already publishes `annual_burned_vectors_v1`, so that door is open — just slow; §8.8).

### 6.8 What we still owe from §5.2

We replace stage 3's month coding and stage 2's version curation (no competing model versions), but we
still owe:

- the **LULC mask** — which Argentina classes? (§8.2);
- the **solitary-pixel removal** — our step-06 `< 1 ha` cut (≈11 px) is stricter than `≤ 4 px`, so
  likely a no-op; **run it anyway** so the rule is identical across countries;
- the **property block** (`source`, `pixel_unit`, `year`, `region`, `system:time_start/end`);
- a **single ImageCollection covering all years and regions** — our predictions are tiled by *cartas*,
  not by their regions, so the mosaic step must reconcile the two;
- `regiones_fuego_argentina_v1` as a FeatureCollection where their scripts expect it (only the 5 fire
  regions exist today, as a raster via `scripts/export_region_raster.py`).

---

## 7. What Argentina delivers, and when

**Argentina is expected to deliver all six subproducts** — the guide's country table marks Argentina
with *anual, mensual, acumulado, frecuencia, último año, tamaño de cicatriz* (Chile, Ecuador and
Venezuela deliver only the first four). `severity_class`, `interval_since_fire` and `time_after_fire`
appear in the publish script's lists but **not** in the country table — Brazil extras, not ours.

### By 31 July 2026 — the assets (this doc)

1. Upload `fires_<fy>` (28) and `scars_<Y>` (27) — §6.1.
2. `collection1_fire_mask_v1` equivalent: the month-of-burn collection, LULC-masked, solitary-pixel
   filtered, properties set — §6.5 + §6.8.
3. Subproducts: `monthly_burned`, `annual_burned`, **`monthly_burned_coverage`**,
   **`annual_burned_coverage`**, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`),
   `year_last_fire`, `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range`.

### Between 1 August and 24 September 2026 — statistics, publication, launch

See **[`09-statistics.md`](09-statistics.md)**: the six area-statistics CSVs, the territorial layer
(**ours to build**), Looker Studio, the public-asset copy, the Workspace catastro, and the launch track
(ATBD, methodology page, downloads page, materials, event).

---

## 8. Open decisions

1. **Asset naming.** Adopt their `COLLECTION1` / `AUXILIARY_DATA` spelling for step-08 outputs (breaking
   our `COLLECTION-1` convention), or keep ours and rename only at publish time? The `mapbiomas-public`
   copy must use their names regardless.
2. **LULC mask classes per region.** Water (26) at minimum; the guide's example adds 22 (non-vegetated);
   others add 9 (forest plantation). Verify ids against the **MapBiomas Argentina** legend (not
   Paraguay's) and decide per fire region — Patagonian steppe, Chaco and Pampa don't want the same rule.
3. **LULC year coverage.** Check the last year in `C.MAPBIOMAS_LULC` and duplicate it forward to 2025,
   as they do 2024→2025. Blocks every `*_coverage` product.
4. ~~Month per pixel or per object~~ — **decided: per pixel**, from `snic_metrics.abs_date` in GEE (§6.5).
5. **`scar_id` numbering.** Integer, unique per calendar year, stable across re-runs — pick the rule
   (e.g. order by `oid`) and record it.
6. **Scar-size ranges** — the reference script's or the Workspace legend's (§5.4)? Ask IPAM; the LatAm
   ranges are probably right for us, but the registered legend must match the pixel values we write.
7. **Reburn rule** (§6.4.3) — later date wins; confirm nobody downstream expects otherwise.
8. **Our fire-year vector database** — ask whether Argentina may publish it as `annual_burned_vectors`.
   Until settled, keep it out of `FINAL_PRODUCTS` so it can't leak into a published collection.
9. **`frequency_burned` band name** — the publish map says `frequency_burned_{year1}_{year2}` while
   script 2 writes `fire_frequency_<y1>_<y2>`; confirm which the platform reads.
