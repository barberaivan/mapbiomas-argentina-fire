# The MapBiomas Fuego network's shared post-processing — a reading

> Describes code we do not own: **`mapbiomas-fire`** (the network's Code Editor repo,
> `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire`, branch `master`)
> @ **`904fbdf`**, the local checkout at `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`,
> read across July–September 2026 and pinned on **2026-09-18**.
>
> ⚠️ On the day it was pinned, `origin/master` was **68 commits ahead** of that checkout and those
> commits have **not** been read against this text. Pull and re-read before trusting a detail.
>
> Derivative and liable to go stale. **Where this disagrees with
> [`../07-vector_to_raster.md`](../07-vector_to_raster.md), docs/07 wins** — it describes what
> Argentina actually runs. Nothing about our own pipeline belongs in this file.

**This is not a to-do list for Argentina.** It is a reference for the *shape* of the published
products — asset topology, band names, encodings, dtypes, pyramiding, legends. Several stages the
other countries run as post-processing are already embedded earlier in our pipeline, and
reproducing them here would be a no-op at best and double-counting at worst; Argentina's route
through this spec is [`../08-postprocessing.md`](../08-postprocessing.md).

---

## Reference material

| What | Where | Notes |
|---|---|---|
| **Launch-process guide** — the network's own step-by-step (source for "The launch process") | [*MapBiomas Fuego — Guía del Proceso de Lanzamiento*](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit), 39 slides | **Readable by tooling** — the `/edit` view is a JS shell, but the PDF export is public: `curl -sL -o slides.pdf "https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/export/pdf"` then read the PDF. |
| **Reference code** — source of truth for "The reference chain" | Local clone: `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/` | GEE Code Editor repo, remote `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire` (branch `master`). Files have **no extension**. **Read-only for us** — the network's repo; never push. |
| **Mapping method paper** (theirs, not ours) | Alencar, A. A. C., Arruda, V. L., Silva, W. V. da, Conciani, D. E., Costa, D. P., Crusco, N., Duverger, S. G., Ferreira, N. C., Franca-Rocha, W., Hasenack, H., Martenexen, L. F. M., Piontekowski, V. J., Ribeiro, N. V., Rosa, E. R., Rosa, M. R., Santos, S. M. B., Shimbo, J. Z., Vélez-Martin, E. (2022). *Long-Term Landsat-Based Monthly Burned Area Dataset for the Brazilian Biomes Using Deep Learning.* **Remote Sensing 14(11), 2510.** <https://doi.org/10.3390/rs14112510> | What our steps 01–07 replace ("Their mapping method vs ours"). |
| **ATBD** | [ATBD MapBiomas Fogo Colección 4](https://brasil.mapbiomas.org/wp-content/uploads/sites/4/2025/06/ATBD-MapBiomas-Fogo-Colecao-4.pdf) | Product definitions in prose; also the template for **our own ATBD** (`../../statistics/docs/statistics.md`). |
| **Legend colours / codes** | `Mapbiomas-Fogo-Legenda-Col4.xlsx` (linked from the guide) + each country's *códigos de la leyenda* page | Authoritative pixel values + hex colours per subproduct. **Use this, don't eyeball colours** from the slides. |
| **Per-country examples** | Peru: [descargas](https://peru.mapbiomas.org/descargas-mapbiomas-fuego/), [ATBD](https://peru.mapbiomas.org/wp-content/uploads/sites/14/2025/10/ATBD-General-MapBiomas-Fuego-Peru-Col-1-ES.pdf) · Paraguay: [descargas](https://paraguay.mapbiomas.org/descargas/), [ATBD por etapa](https://paraguay.mapbiomas.org/atbd-entienda-cada-etapa/) | Closest models for what Argentina must produce. |

---

## The launch process — six stages

| # | Stage | Where | Argentina |
|---|---|---|---|
| 1 | **Finalización de la colección anual** de la serie histórica | ours (steps 01–07) | ✅ |
| 2 | **Versión consolidada (sin máscaras)** — one ImageCollection, all years and regions | "`1-Post_classifications`" | ✅ collapsed into stage 3 — we have no unmasked variant to consolidate |
| 3 | **Versión final (con máscaras)** — LULC mask + solitary-pixel removal + month coding | "`1-Post_classifications`" | ✅ `collection1_fire_mask_v1`, 27 images; mask + pixel filter are upstream (`../08-postprocessing.md` "How Argentina's route differs") |
| 4 | **Generación de subproductos** | "Stage 4" (both) | ✅ 12 images (9 derived + 3 scar) + 27 scar FCs |
| 5 | **Estadísticas preliminares** → Looker Studio *(the network's tool; we analyse in R)* | statistics/docs/statistics.md | ⬜ needs the territorial layer first |
| 6 | **Assets públicos + catastro en Workspace + enlaces directos** | statistics/docs/statistics.md | ⬜ IPAM's copy; the naming decision is `../08-postprocessing.md` "Open decisions" |

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
| **Territorial layers** for platform statistics | **us** — the territory set is undecided (possibly vegetation units, not the 5 fire regions) |
| Reviewing and validating every product | **us** |

---

## Their mapping method vs ours — why only the post-processing is shared

**Alencar et al. 2022 (all other countries):** annual Landsat **quality mosaics** → burned/unburned
samples → **deep neural networks** trained off-platform → an **annual** burned/not-burned raster per
region-year. The **month is not mapped**: it is reconstructed from the date of **minimum NBR** in the
annual mosaic (its `monthOfYear` band), so the monthly product is a re-labelling of the annual one.
Everything is calendar-year.

**Ours (steps 01–07):** per-observation logistic-regression burn probability → per-pixel
burn-probability time-series metrics → SNIC segmentation into fire objects on a **non-calendar
fire-year** → object-level probit-BART fire/non-fire classification. Our month of burn is **measured**
per pixel (`abs_date`), not inferred from min-NBR.

Two consequences Argentina's route must absorb — both resolved in [`../08-postprocessing.md`](../08-postprocessing.md):

1. **Calendar-year framing.** Their chain is indexed by calendar year; our objects live in fire-years.
2. **Month source.** Ours is better grounded but comes from a fire-year raster, so it has to be
   re-partitioned into calendar years.

---

## Layout of the reference repo

```
mapbiomas-latam-fire-gee/
├── 00_Tools/                          # Palettes.js ('mensual', 'frecuencia25'), Legends.js
├── 01_Mosaics/                        # THEIR mapping inputs (quality mosaics) — we don't use this
├── 1-Toolkit_Collection1/             # sample collection + Visualize-Collections-Fire (validation app)
├── 2-Statistics/                      # area statistics → CSV (`../../statistics/docs/statistics.md`)
├── 4-Collection_anual_final_products/ # ⭐⭐ THE CHAIN
│   ├── Reference/                     #   ⭐ copy THIS one
│   │   ├── 1-Post_classifications/    #     stages 2-3
│   │   ├── 2-Collection_Fire_Subproducts/  # stage 4
│   │   └── ToPublish/                 #     stage 6
│   └── bolivia/ chile/ colombia/ paraguay/ peru/ suriname/   # country adaptations — best examples
└── 5-Monitor-Fuego/                   # near-real-time monitor — out of scope
```

**Each country makes its own copy of `Reference/` and adapts it** (the guide says so explicitly).
`bolivia/` and `peru/` are the most complete and the best model for an `argentina/` folder. Scripts are
Spanish-commented, parameterised by `var country = '…'` + `var coll_n = '1'`.

---

## The reference chain, stage by stage

### Asset topology (their convention)

```
projects/mapbiomas-<country>/assets/FIRE/
├── COLLECTION1/CLASSIFICATION/                     # raw model output, per region-year, versioned
├── COLLECTION1/CLASSIFICATION_COLLECTIONS/
│   ├── collection1_fire_no_mask_v1                 # ImageCollection — approved, version stripped
│   └── collection1_fire_mask_v1                    # ImageCollection — LULC-masked, month-coded ← pivot
├── COLLECTION1/FINAL_PRODUCTS/                     # multiband subproducts
│   └── annual-burned-vectors/mbfogo-col1-<year>-v1 # FeatureCollection per year (scars)
└── AUXILIARY_DATA/regiones_fuego_<country>_v1      # fire regions
```
Published copies go to `projects/mapbiomas-public/assets/<country>/fire/collection1/` (`../../statistics/docs/statistics.md`).

> **Naming gotcha:** they use **`COLLECTION1`** (no hyphen), `AUXILIARY_DATA` (underscore) and
> lowercase `mapbiomas_<country>_…`; our repo uses **`COLLECTION-1`** / `AUXILIARY-DATA`
> (`_FIRE_ROOT` in `utils/constants.py`). See [`../08-postprocessing.md`](../08-postprocessing.md) "Open decisions".

### `1-Post_classifications` — stages 2 and 3

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
   cleaned scar. **`pixel_unit: 'month'`.** ← *this is the step Argentina replaces*.
4. **Properties:** `source: 'mapbiomas-fuego'`, `pixel_unit: 'month'`, `name`, `year`, `region`,
   `system:time_start/end` (Jan 1 → Jan 1 of year+1).
5. Export with `pyramidingPolicy: 'mode'`, `scale: 30`, `maxPixels: 1e13`.

**The masked collection — one image per region-year, value 1–12 = month of burn, masked elsewhere — is
the single input to everything downstream, and where our pipeline lands.**

### Stage 4, scripts 1–3 — raster subproducts

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
  (`../../statistics/docs/statistics.md`). ~~They need our LULC asset extended to 2025~~ — **not a blocker and now moot**: they
  cross against LULC **col-3 v1**, which carries `classification_2025` natively (`../07-vector_to_raster.md` "The nine derived subproducts").
- ⚠️ **Not every built subproduct appears in a publish list, and the three lists disagree**
  (read 11 Sep 2026). `ToPublish/` now holds **three** scripts, renumbered since this doc was
  written: `1-products-Public` (ACLs only — new), `2-toBucket-subproducts` (COGs),
  `3-toAsset-Public` (`copyAsset` to `mapbiomas-public`). Comparing their product lists:

  | subproduct | built by | ACL list | bucket list | public-asset list |
  |---|---|---|---|---|
  | `monthly_burned_coverage` | script 1 | — | — | — |
  | `frequency_burned_coverage` | script 2 | — | ✅ | — |
  | `annual_burned_id` | script 5 | — | — | — |
  | `annual_burned_area_ha` | script 5 | ✅ | — | ✅ |

  We have built all four. Whether they are meant to be published, or are deliberately
  internal, is a question for the network (`../../statistics/docs/statistics.md`) — do not infer an answer from the lists,
  since they are inconsistent with each other.

### Stage 4, scripts 4–6 — the scar-size chain

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
1–2 entirely: we already own the labels**.

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
  (May 2026) — their §4 *Área queimada anual por tamanho de cicatriz*, verbatim `1: '< 10 ha'` …
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
into scar size categories, based on sets of spatially connected pixels within the same year."* We write
**level 2 only**; the platform derives level 1 itself.

> A superseded paragraph used to sit here arguing that "Brazil's ranges are tuned to Amazon-scale
> scars, ours are far smaller, so the LatAm reference ranges are almost certainly right for us". That
> reasoning was **wrong on the measured data** — see the table above and its two independent
> sources — and it contradicted this very section. It is recorded only so the argument is not made a
> second time.

---

