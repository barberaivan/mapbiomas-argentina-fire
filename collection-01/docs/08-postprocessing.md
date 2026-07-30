# 08 — Post-processing: building the MapBiomas Fuego products

> ## How to read this file — §§1–5 are NOT our pipeline
>
> **§§1–5 describe what Brazil and the other countries do.** They are a reference for the *shape* of
> the published products — asset topology, band names, encodings, dtypes, pyramiding, legends — and
> nothing more. Do **not** read them as a to-do list for Argentina: several stages that they run as
> post-processing are already embedded earlier in our pipeline, and reproducing them here would be a
> no-op at best and double-counting at worst.
>
> **§6 is ours, and it is implemented** — see **[`07-vector_to_raster.md`](07-vector_to_raster.md)**
> for the built article. Where §§1–5 and §6/docs-07 disagree, docs/07 wins.
>
> Three specific claims in the earlier draft of this file were wrong and are corrected in §6:
> we do **not** owe the LULC mask or the solitary-pixel filter (§6.2); painting a polygon does
> **not** fill its interior (§6.3); and the calendar-year scars are **not** a regrouping of the
> step-05 objects but a separate 8-connected labelling pass (§6.4).

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
| **Territorial layers** for platform statistics | **us** — deferred to ~20 Aug 2026; the territory set is undecided (possibly vegetation units, not the 5 fire regions). §8.10 |
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
fire-year** → object-level probit-BART fire/non-fire classification. Our month of burn is **measured**
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

⚠️ **The reference script's size ranges do NOT match the published legend, on the same pixel values
1–8** — a raster built with the script and registered with the legend is silently mislabelled in
every class. **RESOLVED 2026-07-29: the legend wins, and we write the legend's ranges**
(`C.SCAR_SIZE_LOWER_HA`).

| pixel | ⛔ LatAm reference script | ✅ published legend — what we write |
|---|---|---|
| 1 | `< 5 ha` | `< 10 ha` |
| 2 | `5–25 ha` | `10–250 ha` |
| 3 | `25–50 ha` | `250–500 ha` |
| 4 | `50–250 ha` | `500–5 000 ha` |
| 5 | `250–500 ha` | `5 000–10 000 ha` |
| 6 | `500–1 000 ha` | `10 000–50 000 ha` |
| 7 | `1 000–5 000 ha` | `50 000–100 000 ha` |
| 8 | `≥ 5 000 ha` | `≥ 100 000 ha` |

Confirmed from **two independent sources**, so this needs no ruling from IPAM:

- **[`CODIGO DE LEGENDA FOGO COLECAO 5`](https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2026/05/CODIGO-DE-LEGENDA-FOGO-COLECAO-5.pdf)**
  (May 2026) — §4 *Área queimada anual por tamanho de cicatriz*, verbatim `1: '< 10 ha'` …
  `8: '>= 100.000 ha'`, asset
  `mapbiomas_fire_collection5_annual_burned_scar_size_range_v1`, bands `scar_area_ha_<year>`.
- the **live platform legend** for Fogo col-5 (launched July 2026), which shows exactly those 8
  classes as *level 2*.

**docs/08 previously guessed the reference ranges were right for us** because Brazil's are tuned to
Amazon-scale scars and ours are smaller. Measured over all 27 calendar years (2,734,416 scars,
69,020,102 ha), that guess was **wrong**: the legend's scheme populates **all 8 classes**, because
Argentina does reach the top bin — **24 scars ≥ 100 000 ha**, the largest 219 410 ha in calendar
2003. Counts concentrate in class 1 (76 % of scars, but only 5.7 % of area) while the **area** spreads
across all eight, which is what the product is read for.

The Workspace legend is also **two-level** (level-1 aggregates at pixel values 10/20/30/40/50: `<250`,
`250–500`, `500–10 000`, `10 000–100 000`, `>100 000` ha), defined as *"annual burned area classified
into scar size categories, based on sets of spatially connected pixels within the same year."*
Brazil's ranges are tuned to Amazon-scale scars; ours are far smaller, so **the LatAm ranges are almost
certainly right for us** — but confirm, because the registered legend must match the pixel values we
write (§8.6).

---

## 6. Argentina's route — implemented

**Built. The article, with the verification numbers and the run commands, is
[`07-vector_to_raster.md`](07-vector_to_raster.md).** This section is the summary and, where the
earlier draft of this file got it wrong, the correction.

### 6.1 The design

**Vectors only; GEE does the pixel work.** Nothing new is uploaded for the month layer — step 06
already put the whole object set in GEE (`objects_raw_<fy>`, 28 FCs, every object with all 20
predictors and the three call columns, docs/06 §12). Step 07 filters it at read time to
`fire == 1 & area_ha >= 1` and paints it against the SNIC assets that are already there
(`snic_metrics_<fy>.abs_date`, `snic_<fy>.candseed`). The per-pixel calendar year and month that R
computed locally are knowingly recomputed in GEE; that redundancy is the price of not moving 28
fire-years × ~248 cartas of imagery.

One thing *is* uploaded, by hand: **`scars_<Y>`, 27 FeatureCollections**, the calendar-year scars
(`scar_id`, `area_ha`, `n_px`, `year`), because the labelling cannot be done in GEE (§5.4) and is
done locally instead.

| Layer | Source | Feeds |
|---|---|---|
| `objects_raw_<fy>` (28, already uploaded) | step 06 | the month-of-burn collection, and every raster subproduct derived from it |
| `scars_<Y>` (27, manual ingest) | `07-calendar_scars.R` | `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range` |

### 6.2 CORRECTION — the LULC mask and the solitary-pixel filter are NOT owed

The earlier draft listed both as things "we still owe" from stage 3. **We do not.** Both are already
in the pipeline, and stricter than the reference:

- `veg_fire` comes from the **previous-year MapBiomas LULC**, and every non-burnable class is
  unreachable as a SNIC candidate (no `VEG_TABLE` entry → `THR_DEF = 9` → no delta ever passes).
  Verified on FY2000/2014/2023 over ~3.6 M candidate pixels: **zero `candseed>0` pixels on
  `veg_fire` 24 (non-burnable) or 25 (non-observed)**. The reference drops water (26) only; ours
  drops every non-burnable class.
- The `>= 1 ha` object cut (≈ 11 px) is stricter than deleting 4-connected components of ≤ 4 px.

Running the reference's versions anyway "so the rule is identical across countries" — which the
earlier draft recommended — would be a no-op for the mask and would only shave true positives off
calendar-year fragments of already-qualifying fires. The output collection keeps the name
`collection1_fire_mask_v1` (that is the asset downstream scripts read) and records
`lulc_mask` / `solitary_pixel_filter` properties saying the rule was applied upstream, not skipped.

### 6.3 CORRECTION — painting a polygon does not fill its interior

The earlier draft's §6.4.2 warned that `ee.Image().paint(fc, 1)` "fills holes and gaps" and that the
result must always be intersected with the real burned mask. **That is not what happens.** Step 05
vectorized the *accepted pixel set* with `as.polygons(dissolve=TRUE)`, so holes are true interior
rings and the boundary follows pixel edges; both GEE's `paint` and `terra::cells` use
pixel-centre-in-polygon and recover exactly that set. Verified twice:

- `terra::cells(country template, accepted polygons)`, FY2020 → **55,008,255** cells vs
  `sum(n_pixels) = 55,008,255`. Exact, over 55 M pixels. Every fire-year reports `EXACT`.
- In GEE, `paint` vs the `candseed` burned mask → **0 painted-but-not-burned** on the audited ROIs.

The `candseed > 0` intersection is kept on both sides as a **guard**, and the residual is logged per
year rather than assumed. What *is* real is the step-05 **longitude cut**: `candseed==3` east of
−70.6 was dropped before labelling, so the objects exclude it while `snic_<fy>` still carries it
(65,752 px over 28 fire-years) — GEE replays the cut with `pixelLonLat`.

### 6.4 CORRECTION — the scars are a new labelling pass, not a regrouping

The earlier draft proposed getting the calendar-year scar parts by grouping step 05's pixels by
`(pid, cyear)` — "without any new labelling pass and without re-vectorizing". That would have
produced *calendar-year parts of our dilation-connectivity objects*, which is not what the network
means by a scar. The published definition is "sets of spatially connected pixels within the same
year", so the scars are labelled afresh:

- **calendar** year, not fire-year;
- **plain 8-connectivity**, deliberately *not* step 05's 1-px-dilation connectivity, so two distinct
  fires that touch merge into one scar — matching the reference;
- and yes, a fire straddling 31 December becomes two scars, one per year. That is the intended
  consequence of per-pixel dating (§6.6).

`scar_id` is a fresh integer, 1..n within the year, ordered by the scar's first cell — deterministic
across re-runs. **No size class is stored in the vectors**; it is applied in GEE from `area_ha`, so a
legend change (§5.4 is still unresolved) does not mean 27 re-uploads.

### 6.5 The calendar-year partition, verified

```
calendar year Y  =  Jan–Apr Y  from fire-year (Y−1)   ⊎   May–Dec Y  from fire-year Y
```

Checked over all 28 fire-years: **no object's date range leaves its own fire-year window**, 0
exceptions. So the merge is a **union**, not an arbitration; `max` only decides genuine reburn, where
the later date wins. Series: **1999–2025** (FY1998 contributes only its Jan–Apr 1999 part; its
Nov–Dec 1998 remainder falls outside the published series and is reported as dropped).

`candseed==3` pixels are the one exception — their raw dates *do* leave the window — so each
fire-year is filtered with the general `date ∈ [Y, Y+1)` test, never shortcut to "Jan–Apr".

### 6.6 `candseed == 3`: parent-object date, and why it is not cosmetic

A dieback pixel's `abs_date` is when the **dieback was detected** the following spring, not when the
pixel burned. Measured: **881 k pixels (~79 kha)** survive the longitude cut over 28 fire-years —
**4.0 %** of candidate pixels west of the cut, **14–18 % in FY2014/2015/2021/2024** — with dates in
Jun–Nov.

Left raw they report Andean Patagonia burning in austral winter, and — whenever the parent fire
burned May–Dec — fall into the *next* calendar year, splitting the scar and minting a **phantom
scar** with its own id and size class. So each takes its **parent object's `date_median`**
(`date_med`, already a property on the uploaded FCs, so the fix is free). No pixel that has a real
measured date is touched. The 36 all-dieback objects have no parent date and are filtered out.

**FY2025 has no dieback padding at all** (it needs the FY2026 image) — the series' last year is
asymmetric in that one respect. Worth a line in the ATBD.

### 6.7 What this buys us

- **Per-pixel month, measured** rather than inferred from min-NBR — strictly better grounded than
  the reference method, at no transport cost.
- **`annual_burned`, `monthly_burned` and `scar_size` agree pixel-for-pixel**, because all three
  derive from the same per-pixel calendar-year assignment. Painting each whole object into its modal
  `year_calendar` would have been cheaper but would make `scar_size` disagree with `annual_burned` on
  every scar straddling 31 December — in Argentina not a corner case, since the Patagonian/Pampean
  season peaks Dec–Feb. That is exactly why the fire-year is non-calendar in the first place.
- **Faithful to the network's semantics** — their scars are calendar-clipped too — with one
  improvement: ours are labelled from the burn mask with the standard connectivity, so the
  definition matches while the *underlying* fire objects stay separate in our own database.
- **One grid, pinned.** All 56 SNIC assets and all 248 carta tiles share one lattice, and every
  export pins `crs` + `crsTransform` rather than `scale: 30` (which is a *different* grid in
  EPSG:4326). The GEE rasters and the locally-built vectors are therefore aligned by construction.

### 6.8 What stage 3 still leaves us

Not the mask and not the pixel filter (§6.2). What remains:

- the **property block** (`source`, `pixel_unit`, `year`, `region`, `system:time_start/end`) — done,
  set by `07-month_of_burn.py`;
- **one ImageCollection covering all years** — done: one whole-country image per calendar year, so
  the cartas-vs-regions mismatch never arises;
- `regiones_fuego_argentina_v1` as a **FeatureCollection** — still missing; only the 5-region raster
  exists (`scripts/export_region_raster.py`). Step 07 uses `ARG_BUFFER_FC` for the export geometry
  and sets `region = 'argentina'`.

## 7. What Argentina delivers, and when

**Argentina is expected to deliver all six subproducts** — the guide's country table marks Argentina
with *anual, mensual, acumulado, frecuencia, último año, tamaño de cicatriz* (Chile, Ecuador and
Venezuela deliver only the first four). `severity_class`, `interval_since_fire` and `time_after_fire`
appear in the publish script's lists but **not** in the country table — Brazil extras, not ours.

### By 31 July 2026 — the assets (this doc)

| # | Item | State |
|---|---|---|
| 1 | Object FCs `objects_raw_<fy>` (28) | **done** in step 06 — no separate `fires_<fy>` upload; step 07 filters at read time (§6.1) |
| 2 | `collection1_fire_mask_v1` — the month-of-burn collection, 1-band uint8 per calendar year, properties set | **done** — `07-month_of_burn.py`; the LULC mask and pixel filter are upstream, not owed (§6.2) |
| 3 | `scars_<Y>` (27) calendar-year scar FCs | **built locally** (`07-calendar_scars.R`); the 27 zips need the **manual GEE ingest** |
| 4 | `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range` | **coded** (`07-scar_rasters.py`), runs once item 3 is ingested |
| 5 | `monthly_burned`, `annual_burned`, `monthly_burned_coverage`, `annual_burned_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`), `year_last_fire` | **coded + launched** (`07-subproducts.py`, 9 tasks, 2026-07-29) — all nine derive from item 2; the LULC-to-2025 gap is closed by duplicating 2024 forward, as every reference country does (docs/07 §12.4) |

⚠️ The `*_coverage` products are the easiest to forget and are exactly what the statistics read
(docs/09 §2).

### Between 1 August and 24 September 2026 — statistics, publication, launch

See **[`09-statistics.md`](09-statistics.md)**: the six area-statistics CSVs, the territorial layer
(**ours to build**), Looker Studio, the public-asset copy, the Workspace catastro, and the launch track
(ATBD, methodology page, downloads page, materials, event).

---

## 8. Open decisions

1. ~~Asset naming~~ — **decided (provisional): keep `COLLECTION-1`**, ours, and rename at publish time.
   The asset *names* inside already follow the network exactly (`C.product_name()`). Revisit before the
   `mapbiomas-public` copy, which must use their spelling regardless.
2. ~~LULC mask classes per region~~ — **not applicable.** The mask is embedded upstream and is stricter
   than the reference (§6.2). Nothing to choose.
3. ~~LULC year coverage~~ — **resolved, and moot**: the coverage products cross against **LULC
   collection 3 v1** (`C.PRODUCT_LULC`), which carries `classification_2025` natively, so nothing is
   duplicated forward. It was never a blocker either way — duplicating the last year forward is what
   every reference country does, and `07-subproducts.py` reads the band list from the asset so it
   self-corrects. `C.PRODUCT_LULC` is deliberately **separate from `C.MAPBIOMAS_LULC`**, the
   model-side input `veg_fire` was built from (col-2 v8, frozen). Verified (docs/07 §12.1): col-3 v1
   has a byte-identical grid to col-2 v8 and to our lattice up to an integer 9953-column /
   −25102-row offset, its footprint contains the 2 km buffer, and its class codes max out at **77 <
   100** — the condition that makes the `*100 + L` encodings decodable. Still the only place LULC
   enters our chain.
4. ~~Month per pixel or per object~~ — **decided: per pixel**, from `snic_metrics.abs_date` (§6.5).
5. ~~`scar_id` numbering~~ — **decided: integer 1..n within the calendar year, ordered by the scar's
   first cell** on the global lattice. Deterministic and stable across re-runs; `oid` is unusable
   because `ee.Image().paint` needs a number.
6. ~~Scar-size ranges~~ — **RESOLVED 2026-07-29: the published legend's, not the reference script's**
   (§5.4). Confirmed from the Coleção 5 legend-code PDF *and* the live col-5 platform legend, so no
   IPAM ruling is needed. `C.SCAR_SIZE_LOWER_HA = [10, 250, 500, 5000, 10000, 50000, 100000]`. We write
   only **level 2** (values 1–8); the platform derives its level-1 aggregation
   (`<250 / 250–500 / 500–10 000 / 10 000–100 000 / >100 000 ha`) itself, exactly as Brazil's own
   asset does. Do NOT copy `6-export_scar_size_range_by_year`.
7. ~~Reburn rule~~ — **later date wins**, and it is nearly moot: the two fire-years feeding a calendar
   year are disjoint in month (§6.5), so `max` only fires on genuine reburn. Confirm nobody downstream
   expects otherwise.
8. **Our fire-year vector database** — ask whether Argentina may publish it as `annual_burned_vectors`.
   ⚠️ **Partly overtaken by events (2026-07-30):** the merged fire-object layer now EXISTS in
   `FINAL_PRODUCTS`, as `burned_area_polygons_v1` (1,263,079 polygons, 74.23 Mha, docs/07 §13), by
   Iván's deliberate call — early users needed a link that survives a favourable ruling. It is named
   `polygons`, not `vectors`, so it cannot be confused with the calendar-year scars, and
   `ToPublish/2-toAsset-Public` copies an explicit subproduct list rather than the folder, so it
   cannot leak into a published collection by itself. **The question below is still open**, and if
   the answer is no the asset moves and the shared link dies with it.
   Precedent confirmed: Brazil publishes col-5 annual burned vectors publicly, one asset per year, at
   `projects/mapbiomas-public/assets/brazil/fire/collection5/mapbiomas_fire_collection5_annual_burned_vectors/mbfogo_col5_<year>_v1`,
   each polygon carrying a unique numeric `id` (Coleção 5 legend-code PDF §1.1). So the door is open.
   Until settled, keep it out of `FINAL_PRODUCTS` so it cannot leak into a published collection. Note
   `objects_raw_<fy>` currently lives under `WORKFLOW-EXPORTS`, not `FINAL_PRODUCTS`, so this is safe
   today.
9. **`frequency_burned` band name** — the publish map says `frequency_burned_{year1}_{year2}` while
   script 2 writes `fire_frequency_<y1>_<y2>`; confirm which the platform reads.
10. **The territorial layer — DEFERRED to ~20 August 2026, by Iván's call (2026-07-29).** Not needed
    for the 31 July asset delivery; it belongs to the statistics stage (docs/09), which cannot start
    until the 07d `*_coverage` products land anyway. Do not build it before then, because
    **which territories to cut by is still an open question** — possibly *not* the 5 fire regions at
    all, but a **vegetation-units map**. That decision comes first; the layer is mechanical after it.
    - When it is taken, note that `regiones_fuego_argentina_v1` does not exist *under that name* but
      ⚠️ **the "only the raster exists" claim was wrong**:
      `ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada_num` is a 5-feature region vector with
      `Region` + integer `Zona` 1-5 (found 2026-07-29). If the 5 fire regions win, this is a
      rename/reproperty job rather than a build from the raster.
    - Two caveats to settle either way: it is **`simplificada`** (simplified geometry — the statistics
      are checked to ~1 %, docs/09), and its `Zona` numbering is **unverified** against
      `REGION_RASTER.region_id` and is not `C.REGIONS` order.
