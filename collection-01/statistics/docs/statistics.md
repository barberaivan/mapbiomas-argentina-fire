# 09 — Statistics: every number the factsheet reports

How we compute fire statistics from the published maps. **None of this is part of the
product** — it exists to communicate results. The maps themselves are
[`07-vector_to_raster.md`](07-vector_to_raster.md) (what we build) and
[`08-postprocessing.md`](08-postprocessing.md) (what the network expects); what each graphic
*says* is [`10-factsheet_design.md`](10-factsheet_design.md). This file is where each of its
**numbers** comes from. [`ROADMAP.md`](../../ROADMAP.md) is the *when*.

**Three sources, and every figure must say which one it used.**

| | what | who computes it | where |
|---|---|---|---|
| **numerator** | burned area by calendar year × mes × ecorregión (× LULC) | **the network's toolkit**, run on our ecoregion layer | §2 |
| **denominator** | burnable area per ecorregión — **one constant**, no year dimension | us, one small GEE export | §3 |
| **fire counts** | events per ecorregión × año × mes, and their sizes | us, **locally**, off the fire polygons — never GEE | §4 |

**Scope: ecorregión only.** Departamento and provincia are December (Bariloche) work. One
territorial cut is what makes the whole stage one export on our side and one cut asked of
the toolkit.

---

## 1. Files, directories and scripts

```
collection-01/statistics/         all statistics + factsheet code
  legends.py          the burnable class list, the 4 status codes, the 13 ecoregion
                      names, the 16->13 crosswalk kept for December (§7.2)
  burnable_export.py  the constant burnable layer (§3): --test-rect, --regions, --export
  lulc_area_export.py the per-class area, ecorregión x clase x año (§5.3), same route
  burn_perc_export.py THE FIRST RASTER (§5.5): % of the years each pixel burned, 480 m.
                      `--reducer max` is a SECOND run of the same script and a second
                      file — the integer-count map (§5.5.1)
  last_fire_export.py THE SECOND RASTER (§5.6): the year of the last fire, 480 m. Reuses
                      this one's OAuth/Drive/GCS plumbing, and NOT its grid (§5.6)
  lulc_change_export.py  ANÁLISIS 6 (§5.7): the WHOLE COUNTRY, crossed by fire state and
                      the land cover of Y-1 and Y+offset. The third and last GEE reduction,
                      and the only one with a control (§5.7.1)
  fire_counts.R       THE VECTOR PASS (§4) — the fire tables + the plotting geometry
  factsheet_tables.R  THE ANALYSIS PASS (§5) — the plot-ready tables and the GAMs
  factsheet_style.R   the shared palette, theme, map-as-legend and figure variants

collection-01/notebooks/          ⚠️ FOUR notebooks, TWO ship in September — see §5.0
  factsheet_sep2026   THE DELIVERABLE (§5.10): the slide-by-slide spec. 16 images,
        .qmd          `figNN_`, into a folder of its own with one CSV per figure. Clean
                      (no title, no caption inside the image): it is what the DESIGNER gets
  factsheet.qmd       THE FIGURE BANK (§5.2) — draws only; writes PNG + PDF. Análisis 1-5.
                      Every variant, with titles and captions, for deciding what goes.
  factsheet_veg.qmd   EXPLORATORY. Análisis 6, on its own (§5.7): it moved out because
                      factsheet.qmd takes minutes (millions of raster cells) and this one
                      reads three small CSVs. Prefix `fig06_`, one producer per figure
  factsheet_veg_short EXPLORATORY. Análisis 6 cut to three sentences and two figures (§5.8)
        .qmd          plus §4 FOREST ONLY (§5.9). Prefix `fig06c_`

collection-01/data/statistics/    every statistics input and output (Insync store)
  burnable_eco13{,_raw}.csv       the burnable denominator, decoded and as GEE returned it
  lulc_area_eco13{,_raw}.csv      the per-class denominator: ecorregión x clase x año
  annual_burned_*.csv             \
  monthly_burned_*.csv             |  the toolkit's output, one file per
  annual_burned_coverage_*.csv    /   subproduct × territorial cut
  fires.csv                       one row per mapped fire: año/mes calendario, área
  fires_regions.csv               one row per (fire, ecorregión)
  fire_counts_by_month.csv        ecorregión × año × mes: n, n>=10/100/1000 ha, área
  fire_region_summary.csv         per ecorregión: incendios/año, área/año, cuantiles
  ecoregions13_meta.csv           id, nombre, centroide, área — the palette order
  ecoregions13_simple.gpkg        the 13 polygons simplified for plotting
  lulc_change_eco13_y{1,3}{,_raw}.csv  análisis 6: estado de fuego x eco x clase ANTES x
                                  clase DESPUÉS x año, las dos ventanas (§5.7)
  lulc_change_eco13_y*_[w5_]n44*.csv   idem con el corte latitudinal, y con la ventana de
                                  exclusión fijada en 5 (`_w5`) — el caso patagónico (§5.7.3)
  factsheet_patagonia_{bosque,destinos}.csv  la trayectoria Y+1..Y+5 y su mezcla de destinos
  factsheet_bosques.csv           sólo bosques, nacional: % que deja de ser bosque, control
                                  y q, por clase de nivel 2 x 4 ventanas x 2 cohortes (§5.9)
  factsheet_bosques_destinos.csv  a dónde va el bosque quemado (permanencia incluida, §5.9)
  arg_burn_perc_480m_{mean,max}.tif  the frequency raster, the two reducers (§5.5)
  arg_last_fire_480m_mean.tif     the year-of-last-fire raster (§5.6)
  factsheet_*.csv                 the plot-ready tables (§5.1), incl. the four
                                  `factsheet_change*` of análisis 6
  figures/                        PNG + PDF of every figure of `factsheet{,_veg,_veg_short}.qmd`
  factsheet_sep2026_figures_and_tables/   ⚠️ THE FOLDER THE DESIGNER GETS (§5.10): the 13
                                  images of the September deck, PNG + PDF, plus one
                                  `figNN_datos.csv` per figure (the maps have none)
```

The GEE JavaScript is in the **`fuego` repo**, not here:
`users/mapbiomas-arg/fuego:collection-01/statistics/` (app, datasets, `_shared`,
`territories`).

**Run order**, from the repo root:

```bash
$PYTHON collection-01/statistics/burnable_export.py --export     # §3, once
$PYTHON collection-01/statistics/lulc_area_export.py --export    # §5.4, once
$PYTHON collection-01/statistics/lulc_area_export.py --fetch     # ...then pull it down
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 1  # §5.7
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 3  # §5.7.2
$PYTHON collection-01/statistics/lulc_change_export.py --fetch  --offset 1
$PYTHON collection-01/statistics/lulc_change_export.py --fetch  --offset 3
$PYTHON collection-01/statistics/burn_perc_export.py --export    # §5.5, the raster
$PYTHON collection-01/statistics/burn_perc_export.py --export --reducer max   # §5.5.1
$PYTHON collection-01/statistics/last_fire_export.py --export    # §5.6
# ...--fetch each of the three when the tasks land (each one runs its own gate)
Rscript collection-01/statistics/fire_counts.R                   # §4, ~20 s
Rscript collection-01/statistics/factsheet_tables.R              # §5, ~10 s
quarto render collection-01/notebooks/factsheet.qmd              # §5.4, ~5 min
quarto render collection-01/notebooks/factsheet_veg.qmd          # análisis 6, ~2 min
quarto render collection-01/notebooks/factsheet_veg_short.qmd    # §5.8, ~10 s
quarto render collection-01/notebooks/factsheet_sep2026.qmd      # §5.10, ~7 min
```

Only the exports touch GEE (five scripts, seven tasks: two denominators, three rasters, two crossings). The point of the split is that **everything the factsheet draws
is cheap**: the geometry is read once, in `fire_counts.R`, and every figure afterwards is a
read of a CSV with at most a few thousand rows — so a new figure idea costs seconds, not a
re-run.

---

## 2. The numerator — the network's toolkit

We do **not** compute the burned-area cross-tab. It comes from
`2-Statistics/toolkit/v03/` in the read-only reference repo, whose `argentina/` island
(Wallace Silva and Vera Laisa, IPAM) already carries our ecorregiones. We run a **repointed
copy** in our own repo — `users/mapbiomas-arg/fuego:collection-01/statistics/apps/fuego_col1.js`
— identical to theirs except for the asset paths in `_shared/lulc_base.js`: their base module
reads `mapbiomas-public/..._v1`, where the two layers the factsheet needs do not exist.
`core/*` and `00_Tools/Legends.js` are still required **from their repo**; the engine is not
ours to fork. **Delete the copy** once their `lulc_base` points at ours.

It writes to `gs://mapbiomas-fire/data-container/stats/mapbiomas_fuego_argentina_collection1/`
([console](https://console.cloud.google.com/storage/browser/mapbiomas-fire/data-container/stats/mapbiomas_fuego_argentina_collection1)),
and we download from there into `data/statistics/`. The CSVs arrive **already decoded** —
`Área ha`, `Ano`, `Mes_id`, `Nivel 0/1/2`, `Ecorregión` — so nothing here decodes a packed
integer.

### 2.1 Follow their programming strategy, it is absurdly fast

Their reducer is the one we once benchmarked at 8 h/year:
`ee.Reducer.sum().group(1,'class').group(1,'territory')`. There is no trick in the reducer.
It is fast because of what is *around* it, and these five are what **our own export** (§3)
copies:

1. **The cross-tab lives in the pixel value**, packed into one integer — cost is O(pixels),
   never O(pixels × combinations).
2. **No vector is ever intersected.** Territory is `ee.Image().paint(fc, id)`: one raster,
   one band, every territory out of a single reduce. No `filterBounds`, no per-feature loop,
   no slivers.
3. **The reduction geometry is a `bounds()` rectangle.** It can be, because `paint()` is
   masked outside the painted features. Passing a buffered national multipolygon clips every
   tile against a 2 M-edge geometry and buys nothing.
4. **No `tileScale`.** Ours was 4 — ~16× the shards, each re-paying the fixed per-shard cost.
   Add it only if a task OOMs, and record that it was needed.
5. **All years in one task**, flattened into a single `Export.table`.

Computing the image on the fly is *not* the problem: cheap arithmetic over stored byte bands
on one lattice is fine. Complex clip geometry, shard multiplication and hidden resampling are.

### 2.2 The land-cover year: we cross the PREVIOUS one

Upstream pairs `burned_area_<Y>` with `classification_<Y>`. **Our copy crosses `<Y−1>`**
(`alignThemeToFirePrevYear`). A fire consumes the vegetation that was there *before* it
burned, and the same-year class of a burned pixel is partly a **consequence** of the fire.
Argentina reports what burned, not what the pixel became.

`frequency_burned_coverage` and `accumulated_burned_coverage` stay on same-year: their band
names end in the **last** year of a multi-year window, so "previous year" has no single
meaning there. Neither feeds the factsheet.

⚠️ **This creates a real discrepancy, in three places.** Our statistics CSV crosses the
**previous** year; the **published** `*_coverage` assets and every other country's statistics
cross the **same** year. The app computes coverage on the fly from `annual_burned × LULC` and
never reads the `*_coverage` asset, so the change moves the CSV only — the product stays
network-conformant. Any figure or table that crosses fire with land cover must say which of
the two it came from.

### 2.3 The grid

`reduceRegion` takes **either** `scale` **or** `crs` + `crsTransform`. On our side we always
pass the pair, from `utils/constants.py` (`C.SNIC_CRS`, `C.SNIC_TRANSFORM`). Their run stays
on `scale: 30`, and that is fine: `30 / 111319.49 = 0.000269494585236` is **exactly** our
pixel size, so it is the same pyramid level and a **sub-pixel phase shift**, not a resolution
difference. What a coarser read *would* do is real and is worth warning the network about:
reading a sparse burned raster below native resolution over-reports by **+14 % at 90 m and
+36 % at 120 m** (measured).

The published LULC (`C.PRODUCT_LULC`) is an **integer** offset from our lattice (+67 px lon,
−62 px lat, verified 2026-09-10) — same phase, so no resampling anywhere in the reduction.

---

## 3. The denominator — one constant burnable layer

`% burned` is **entirely Argentina's own addition**: nobody in the network computes a
burnable denominator (grepped — no `burnable`, no `quemable` anywhere in the reference repo).
There is no spec to deviate from, which is exactly why it has to be *stated*.

**Burnable is not per-year.** One boolean per pixel — was this pixel burnable *most of the
time* over 1998–2024? — then one area per ecorregión, computed once, used for every year.
1998–2024 is the previous-year range of calendar years 1999–2025: the same 27 LULC layers a
per-year design would have read, collapsed instead of crossed.

**Implemented as the mean, not `ee.Reducer.mode()`, and it writes four statuses, not two.**
The two reducers agree everywhere except exact 50/50 pixels, which `mode()` sends silently to
0. Both of the things that could quietly shrink the denominator therefore get their own code:

| status | meaning |
|---|---|
| 0 | not burnable |
| 1 | burnable |
| **2** | **never observed** — masked in every year 1998–2024 |
| **3** | **tie** — burnable in exactly half the observed years |

```python
mean   = ee.ImageCollection([burnable_year(y) for y in years]).reduce(ee.Reducer.mean())
status = (ee.Image(0).where(mean.gt(0.5), 1).where(mean.eq(0.5), 3)
          .updateMask(mean.mask())      # observed pixels only...
          .unmask(2))                   # ...everything else is "never observed"
code   = eco.multiply(10).add(status)   # max 13*10+3 = 133, fits uint8
```

A shrunk denominator inflates every percentage in the factsheet, so it has to be visible in
the table rather than discovered later. **Exactly one layer drives the mask** — the
ecorregiones; `status` is unmasked into 0–3 *before* it is added, so nothing can vanish
silently. At most 52 rows, one task, one CSV. Namespace the task description
(`arg09_burnable_eco13`) — the compute project is shared with the whole network.

**The rectangle test first** (`--test-rect`): a small box in Córdoba (−63.90 −31.55 →
−63.70 −31.35), where nearly everything is burnable. 7 s, and it catches every structural
error the national run takes longer to reveal. Measured: reported total **42,156.3 of
42,191.8 ha = 99.92 %** of the rectangle (the gap is boundary pixels), and **99.92 %
burnable**.

**Drive, not GCS**, folder `gee_fire_stats` on the **primary (gmail)** account
(`C.STATS_DRIVE_FOLDER`), so the resident credentials are the right ones. That folder is
**not** Insync-synced, which does not matter: the tables are tens of rows, so the script also
computes them locally and writes `data/statistics/burnable_eco13{,_raw}.csv` directly. The
Drive copy is the shareable artefact, not the path the analysis reads. Two operational notes:
**batch, not interactive** (the national task is 2 m 15 s; the per-region `getInfo` fallback
needed over 13 minutes for its *first* region), and the **Drive API is not enabled on
`mapbiomas-fire-485203`** — enabling an API on a project shared with the whole network to read
one of our own files is not ours to do, so `--fetch` builds its Drive client without a quota
project.

### 3.1 The numbers, and the one thing to look at

Run 2026-09-14, one batch task, 2 m 15 s, 52 rows.

| ecorregión | quemable Mha | no quemable | nunca obs. | ráster Mha | polígono Mha | quemable / región |
|---|---|---|---|---|---|---|
| Altos Andes | 4.582 | 7.696 | 0.002 | 12.281 | 12.296 | 37.3 % |
| Bosques Patagónicos | 4.435 | 2.017 | 0.004 | 6.455 | 6.438 | 68.9 % |
| Campos y Malezales | 2.600 | 0.080 | 0.000 | 2.680 | 2.684 | 96.9 % |
| Chaco | 63.201 | 1.771 | 0.009 | 64.982 | 65.085 | 97.1 % |
| **Delta e Islas del Paraná** | 3.495 | 0.585 | **1.530** | 5.610 | 5.613 | **62.3 %** |
| Espinal | 29.377 | 0.500 | 0.001 | 29.878 | 29.886 | 98.3 % |
| Estepa Patagónica | 47.939 | 6.313 | 0.003 | 54.255 | 54.136 | 88.6 % |
| Monte | 44.409 | 2.605 | 0.001 | 47.015 | 47.007 | 94.5 % |
| Pampa | 38.860 | 0.765 | 0.000 | 39.625 | 39.623 | 98.1 % |
| Puna | 4.879 | 4.385 | 0.000 | 9.264 | 9.282 | 52.6 % |
| Selva Paranense | 2.639 | 0.066 | 0.001 | 2.706 | 2.711 | 97.3 % |
| Yungas | 4.674 | 0.085 | 0.000 | 4.759 | 4.769 | 98.0 % |
| *Islas del Atlántico Sur* | *1.158* | *0.042* | *0.007* | *1.207* | *1.202* | *96.3 %* |
| **TOTAL reportado (12)** | **251.090** | 26.868 | 1.552 | 279.510 | 279.531 | **89.8 %** |

Burnable ≤ the region's own polygon area, every region. Rasterised total vs polygon area
agrees to **0.2 % or better** everywhere — the two share only the asset, so the paint, the
lattice and the packing are confirmed at once. The shape of the low numbers is right: Altos
Andes 37 % and Puna 53 % are rock, salt and ice.

⚠️ **Delta e Islas del Paraná: 1.53 Mha — 27 % of the region — is "never observed".** Col-3
does not map the open water of the Paraná and the Río de la Plata, so those pixels are class 0
in every year and are excluded from the denominator, which is exactly what §8 asks for. But it
means the Delta's `%` runs on **3.50 Mha, not 5.61 Mha** — around 60 % larger than a reader
computing it off the region's map area would get. **If the Delta appears in the factsheet,
that sentence goes in the caption.** Every other region's never-observed area is under 10 kha.

**Ties are negligible**: 268 ha nationally, all in Altos Andes. So `mean` and `mode()` agree
here; the tie code stays anyway, because "it was negligible in 2026" is not a property of the
next collection.

### 3.2 ⚠️ Islas del Atlántico Sur is NOT reported

It has 1.158 Mha of burnable land and **zero** burned area — but that zero is a **mapping
gap, not a finding**: **no carta of the processing grid overlaps the layer** (measured
2026-09-15: 0 of 248, the grid stops at lon −53.62). Reporting "0 % quemado" would present a
hole in the map as a fact about fire. `factsheet_tables.R` drops it from every table, from
every map and from the national denominator (252.25 → **251.09 Mha**) via one constant,
`UNMAPPED_REGIONS`. The 13 rows stay in `burnable_eco13.csv`, so nothing is lost.

**It is still drawn on every map, unpainted** (factsheet-sep2026-spec.md, the box before §0.1): outside the
processing grid means no data, not no territory, and an empty outline says both at once.
`MALVINAS_SF` + `geom_malvinas()` in `factsheet_style.R`; `ECO_SF` stays the 12 reported
ones, because that is the geometry the numbers join to.

### 3.3 What a constant denominator changes — read before quoting a `%`

- **`%` is "of the area that is burnable most of the time"**, not "of this year's burnable
  area". For a 27-year series that is the better reference: a fixed denominator means the
  trend is a trend in *fire*, not in land-cover change. Say it in the footnote in those terms.
- **Numerator and denominator no longer read the same layer-year.** They cannot be reconciled
  pixel by pixel, and a `%` above 100 is no longer structurally impossible — it would mean a
  region burned more than its modal burnable area, a real (if unlikely) finding, not an
  arithmetic bug.
- **Two different land-cover questions, and they have two different denominators.**
  *"¿Qué se quemó?"* — the **composition** of the burned area, what share of what burned in a
  region was forest. Denominator: the region's own burned area. **Análisis 5**,
  `factsheet_lulc_share.csv` (§5.2). *"¿Qué % del bosque se quemó?"* — denominator: the area of
  that class, in that region, in that year. That one needs a **second export**, which §5.3 is;
  it is **análisis 5**, `factsheet_lulc_pct.csv`. The two must never be conflated in a caption:
  Campos y Malezales is 0.3 % forest *of what burned* and burns a high share of the little
  forest it has.
- **Everything is keyed on the 13-class ecorregión**, on both sides, because the join is on
  that id.

---

## 4. The fire counts — the vector pass (`fire_counts.R`)

Counts are not a pixel statistic and never touch Earth Engine. Source: the local object
database (`objects-pred/`, `objects-raw/*_raster_metrics.csv`, the territory tags from
`scripts/objects_region_tag.R`).

- **The selection is the published one** — `fire == 1 & area_ha >= 1 & not(rule A) &
  not(rule B)`, mirrored from `workflow/07-calendar_scars.R` (docs/07 §1.1). The factsheet
  counts the fires that are *in* the published map, no more and no fewer. The thresholds are
  repeated in the R file because R cannot import `utils/constants.py`; **keep them in sync**.
- **Calendar year and month, both from `date_median`**, so a whole fire lands in exactly one
  year and one month. (`date_median` is the local CSV column; the same value is `date_med` on
  the uploaded FCs.)
- **A calendar year needs TWO fire-years.** Fire-year `Y` feeds calendar years `Y` and `Y+1`,
  so all 28 fire-years are read and the calendar year assigned afterwards — never aggregate
  per file. Calendar 1998 and 2026 exist only as fragments and are dropped; the series is
  **1999–2025**.
- **A fire counts in EVERY ecorregión it intersects.** `terra::relate(..., "intersects")` —
  a true/false, never an actual intersection geometry, which on 1.3 M polygons would cost
  hours for an answer nothing needs. Regional counts therefore **sum to more than the national
  count**, by design (factsheet-sep2026-spec.md análisis 3.2); the national row is computed from the fire set
  itself, never by summing regions. (The tags are precomputed by `objects_region_tag.R`,
  which writes both this `_multi` assignment and a centroid-based `_one`; the factsheet uses
  `_multi`.)
- It also writes the **plotting geometry** — `ecoregions13_simple.gpkg` (28 MB of coastline
  simplified to 0.3 MB; the detail is invisible at factsheet size) and `ecoregions13_meta.csv`
  (centroid latitude = the palette order, polygon area = the density denominator, both in an
  equal-area CRS, never the layers' EPSG:3857 `Shape_Area`).

**Measured, 2026-09-15**: 1,012,645 fires kept of 1,263,076 candidates over the 28 fire-years
(rule A −196,804, rule B −53,627); 63.33 Mha; 1,011,994 in calendar 1999–2025; **20 fires fall
in no ecorregión**. 18 s end to end.

---

## 5. The analysis pass and the figures

### 5.0 ⚠️ Four notebooks, and only one of them is the deliverable

**`factsheet_sep2026.qmd` is what the designer gets** (§5.10): the September deck, slide by
slide, the deck's images and one CSV per figure in a folder of their own. **`factsheet.qmd` is the figure bank it
selects from** — 170 figures with every regional variant, each with its title, subtitle and
caption, which is what you need to *decide* and exactly what you do not want in a file handed
to a graphic designer. `factsheet_veg.qmd` and `factsheet_veg_short.qmd` are **exploratory**:
real analysis, fully documented and regularly re-run, but nothing they draw goes out in
September.

| notebook | status | figures | covers |
|---|---|---|---|
| `factsheet_sep2026.qmd` | **THE DELIVERABLE (Sep)** | `fig01`–`fig12`, own folder | the 3 láminas, clean, with their CSVs |
| `factsheet.qmd` | ships as the **source** (Sep) | `fig00`–`fig05` | análisis 1–5, every variant |
| `factsheet_veg.qmd` | exploratory | `fig06_` (202 files) | análisis 6, whole |
| `factsheet_veg_short.qmd` | exploratory | `fig06c_` (8 files) | análisis 6 short + forest |

Exploratory means **not published in September**, not discarded. The two vegetation notebooks
are the working material for the **December fire launch** (Bariloche, 7–11 Dec 2026) and for
**the paper** — the control, `q`, the window trajectory and the per-forest-class split are the
part that can carry a publishable result. They keep being documented to the same standard.

Note what the September deck did **not** take: análisis 5 (what % of each class burns) and
análisis 6 (land-cover change around fire) are not in it. The three láminas are *dónde y cuánto*
(análisis 1 + 4), *cambios en el tiempo* (análisis 2) and *cuándo* (análisis 3).

### 5.1 `factsheet_tables.R` — the plot-ready tables

Reads the three sources, writes ten tables into `data/statistics/`. All of them are small,
and between them they hold every number the factsheet quotes.

| table | what |
|---|---|
| `factsheet_annual.csv` | ecorregión × año: `burned_ha`, `burnable_ha`, `pct`, and `pct_rel` = `pct` / la media de esa región ("veces el año típico") |
| `factsheet_monthly.csv` | ecorregión × año × mes: `burned_ha`, `pct`, plus `month_fy` |
| `factsheet_lulc.csv` | ecorregión × año × clase (Nivel 0/1/2): `burned_ha`, absolutos |
| `factsheet_lulc_share.csv` | ecorregión × clase, niveles 1 y 2: **la composición de lo quemado** en % (§5.3) |
| `factsheet_trend_fits.csv` | the GAM trend of `pct` vs año on a 0.1-year grid: `fit`, `se`, `lo`, `hi` |
| `factsheet_pirogram.csv` | ecorregión × mes: área e incendios por año, sus dos `share_*` normalizados, densidad |
| `factsheet_season_fits.csv` | the cyclic GAM through those 12 points |
| `factsheet_region_scalars.csv` | **one row per ecorregión — every scalar a map can paint** |

Two things are decided here rather than in the notebook, because they are analysis:

**The trend.** One normal GAM per region, `k = 5`, summarised as the **mean slope** (finite
differences on the fine grid, read at the observed years). Three readings, all in the scalars
table: `b_abs` (puntos porcentuales/año — comparable only between regions that burn alike),
`b_rel` = `b_abs / mean_pct` (comparable, "fracción del año típico por año"), and
`trend_ratio` = fitted end / fitted start ("la tendencia se multiplicó por X en 26 años").
**`trend_ratio` is what the map paints**: it reads best in a caption and it is the one a
reader can check against the series. No fitted value is negative anywhere, so the ratio is
always meaningful.

**The seasonal curve.** Cyclic GAM, fitted on the **12 summary points**, not on the raw
year-by-month data — it is there to follow the mean curve, which is what fitting it to the
summary makes it do. factsheet-sep2026-spec.md asks for `k = 12`; measured, **12 does the opposite at the one
place it matters** — nationally it overshoots the August peak by 8 % and the Chaco's by
10.5 %, drawing a curve higher than any month actually is. **`k = 10`** reproduces the
national peak to 0.2 % and is the compromise across the 12 regions.

**The toolkit writes only rows that burned**, so a region-year with no fire is simply absent.
Every table is therefore built on a complete grid and filled with zeros — otherwise a mean
over years silently divides by the number of years that happened to burn.

### 5.2 Análisis 4 — the composition of what burned

**It needs no new export.** `annual_burned_coverage` is already burned area × LULC × ecorregión
× year, it is already in `data/statistics/`, and our copy of the app already crosses the
**previous** year (§2.2) — which is exactly the right layer for this question: what was there
to burn, not what the pixel was classified as after burning. The composition is that table
divided by each region's own burned-area total, summed over the whole series (summing the
years before dividing weights each year by how much it burned, which is what "de todo lo que
se quemó en esta región" means).

The result is the one land-cover statement the factsheet can make honestly: **Yungas 66 % of
what burned was forest, Bosques Patagónicos 55 %, Chaco 43 % — against Estepa Patagónica
1.4 % and Pampa 3.4 %.** (Selva Paranense is the outlier at 60 % *agropecuario*, worth a look
before it goes on a slide.)

Two traps, both of which belong in the caption:

- **It is not "% of the forest that burned".** Same two words, different denominator (§3.3).
- **"No observado" is dropped**, as it is everywhere else in this stage — measured, 0.24 ha
  nationally over 27 years, one pixel in 2025. Reported by the script rather than assumed.

`share_bosques`, `share_herb_arbust`, `share_agro`, `share_no_veg` and `share_agua` are also
written into `factsheet_region_scalars.csv`, so the map can paint any of them.

### 5.2.1 Non-burnable classes are dropped from BOTH land-cover analyses

Burned area on water, glacier, city or bare ground is a **mapping error** — those classes do
not burn — so neither análisis 4 nor análisis 5 reports them. Measured before dropping:
**57,449 ha over 27 years, 0.09 % of everything that burned** (32,122 ha in *Áreas sin
vegetación* + 25,327 ha in *Cuerpos de agua*), worst region Estepa Patagónica at 1.56 %.

The cut is by **nivel-1 family** (`NON_BURNABLE_N1` in `factsheet_tables.R`) and it is exact,
not an approximation: the col-3 classes that occur in Argentina inside those two families are
**24, 25, 33, 34** — precisely the members of `legends.py::NON_BURNABLE` that exist in the
country (22 and 26 never occur). Verified against `lulc_area_eco13.csv`, the only table that
carries the class CODE next to the names.

Two consequences worth stating in a caption: the composition now **sums to 100 % over what can
actually burn**, which is what a reader assumes when they read "30 % of what burned was
forest"; and `factsheet_region_scalars.csv` no longer carries `share_agua` / `share_no_veg`,
because those families never reach it.

### 5.3 Análisis 5 — what percentage of each class burned

The other land-cover question, and the one that **does** need a second export:
`statistics/lulc_area_export.py`, the area of every col-3 class per ecorregión per year,
space-filling. Same route as the burnable layer, same programming strategy (§2.1), one
integer band `code = ecoregion13·100 + col3_class` (max 1377, uint16), **all 27 years in one
task**. `--split` falls back to one task per year.

**Why not the toolkit.** Every dataset in the network's app is a *fire* product: its
reductions are masked to burned pixels, so it can say how much forest burned and never how
much forest there was. A space-filling per-class area is a different reduction, and it was
never theirs to produce.

**The years are 1998–2024, and the offset is the whole point.** The numerator crosses fire in
year `Y` with `classification_<Y−1>`, so the class label on a burned hectare refers to `Y−1`
and its denominator must be the class area in `Y−1`. Pairing `Y` with `Y` would be wrong by
one year in a way no gate would catch, so the join is written in exactly one place
(`factsheet_tables.R`, block 3b).

**The mean is taken LAST.** `pct` is computed per year and then averaged over years — never
`Σburned / Σarea`. Two independent reasons, both real: a ratio of sums is not the mean of the
ratios (Jensen), and summing burned area over 27 years counts **every reburn again**, so a
pooled numerator can exceed the class area outright. A class with zero area in a region-year
has no row and no `%` — undefined, not zero — so the mean runs over the years the class
actually existed, and `n_years` is written out beside it.

The masking rule of §3 applies again: the ecoregions are the only mask driver, and the LULC
band is `unmask(0)`ed first, so a pixel the collection does not map becomes a visible
"No observado" row rather than vanishing from the denominator and inflating every `%`.
"No observado" is then dropped from both sides, as everywhere else in this stage.

**Gates, and what they measured (2026-09-15).** The Córdoba rectangle decodes and closes to
**99.92 %** of its own area — the *same* total the burnable run reported, which confirms both
exports share one lattice. The national area comes out at **280.716 Mha in all 27 years**,
spread **0.000 %** (the country does not change size). Every (year, ecorregión) pair is
present. **20 of the legend's 26 codes appear**; the six that never do are the aggregate
parent codes (1, 10, 14, 18, 22, 26), which is why they can carry an aggregate *name* at
nivel 2 without ever showing up as a class. And the numerator's **orphan count is zero** —
no burned row failed to find its denominator, which is the check worth keeping: `all.x`
would have dropped such a row without a word, and dropped numerator is the one error that
makes every `%` look fine and be too low.

### 5.3.1 The results, and what the two questions do to each other

Mean annual `%` burned, nivel 1, 1999–2025:

| ecorregión | bosque | herb./arbust. | agropecuario |
|---|---|---|---|
| Espinal | **2.96** | 3.19 | 0.22 |
| Monte | **2.70** | 0.78 | 0.56 |
| Delta e Islas del Paraná | **2.31** | 3.34 | 0.54 |
| **Argentina** | **1.38** | 0.94 | 0.43 |
| Chaco | 1.28 | 2.38 | 1.29 |
| Yungas | 0.67 | 1.80 | 0.37 |
| Pampa | 0.61 | 0.52 | 0.11 |
| Altos Andes | 0.55 | 0.08 | 0.58 |
| Puna | 0.40 | 0.06 | 0.17 |
| Campos y Malezales | 0.27 | **5.15** | 2.37 |
| Selva Paranense | 0.21 | 1.76 | 0.59 |
| Bosques Patagónicos | 0.16 | 0.15 | 0.26 |
| Estepa Patagónica | 0.14 | 0.05 | 0.22 |

**The two land-cover analyses invert each other, and that is the point.** Bosques Patagónicos
is **55 % forest of what burned** (análisis 4) and burns **0.16 % of its forest a year**
(análisis 5): almost everything that burns there is forest, because almost everything there
*is* forest — not because its forest burns a lot. Campos y Malezales is the mirror: 0.3 % of
what burns is forest, yet it has the country's highest herbaceous burn rate at 5.15 %. Quote
one of these without saying which, and the reader gets the opposite of the truth.

**How much the "mean last" rule is worth**, measured on the forest column: the ratio of sums
differs from the mean of the ratios by up to **+5.0 %** (Campos y Malezales) and **−4.5 %**
(Altos Andes), ~1 % nationally. Not enormous, and not a rounding difference either — it is a
different estimator, and only one of them is "what fraction of the forest burns in a typical
year".

### 5.4 `factsheet.qmd` — the figures

The notebook **draws and does not compute**. `factsheet_style.R` holds the conventions of
factsheet-sep2026-spec.md in code, so the whole factsheet reads as one family: one **colour per ecorregión,
stable everywhere**, on a **latitude ramp** (hue 12 → 280, warm north to cool south, with
luminance alternating along it so that mid-ramp neighbours — which are also neighbours on the
map — stay apart); the **map as the legend**, exported loose; and the two variants,
`all_regions` for choosing whom to highlight and *focal* for the slide.

`params$write_plots` (default `true`) writes every figure to `data/statistics/figures/` as
**PNG** (the PowerPoint draft) and **PDF** (the designer). Render with
`-P write_plots:false` to preview without writing. 170 figures:

| prefix | n | what |
|---|---|---|
| `fig00_mapa_leyenda`, `fig00_mapa_leyenda_texto`, `fig00_mapa_focal_*` | 14 | the map-as-legend, the variant **with the names written next to it**, and the 12 focal ones |
| `fig00_mapa_frecuencia`, `fig00_apertura`, `fig00_tres_mapas` | 3 | the % of years burned per pixel (§5.5): alone, beside the labelled map-legend, and the **three-panel opening** (names → `mean_pct` by region → per-pixel). The last two `%` are different quantities whose relation is exact: **averaging the per-pixel map over a region gives the region's `mean_pct`** — measured nationally, 0.932 % vs 0.933 % |
| `fig00_mapa_veces`, `fig00_mapa_veces_max` | 2 | the same frequency raster read in *times burned* — the cell mean, and the integer version off `--reducer max` (§5.5.1) |
| `fig01_*` | 2 | análisis 1 — proporción quemada media: el mapa y las barras |
| `fig02_*` | 28 | análisis 2 — el mapa de tendencia, la serie nacional, `all_regions` normalizada, 12 focales normalizadas, **12 paneles en % quemado + su multipanel** |
| `fig03_mapa_mes_pico` | 1 | análisis 3.1 — el mes con más área quemada por ecorregión, en paleta cíclica |
| `fig03_pirograma_*` | 13 | análisis 3.2 — pirograma nacional y por ecorregión, doble eje |
| `fig03_estacionalidad_*` | 13 | análisis 3.3 — la forma intraanual, `all_regions` y 12 focales |
| `fig03_pirograma_pmf_*` | 13 | análisis 3.4 — el pirograma normalizado: las dos repartijas en un eje, con los totales de la serie en el panel |
| `fig04_*` | 3 | análisis 4 — la composición de lo quemado, **en nivel 2 (clase nativa) y en nivel 1 (familia)**, y el mapa de `share_bosques` |
| `fig05_*` | 3 | análisis 5 — qué % de cada clase se quema: los heatmaps región × clase **de nivel 2 y de nivel 1**, y el mapa del bosque |

> **Los tres análisis intraanuales son uno solo** (factsheet-sep2026-spec.md §3): el prefijo `fig03_` los cubre a
> los tres, y por eso los que siguen se corrieron un número — `fig04_` es la composición y
> `fig05_` el porcentaje por clase, no lo que decían las versiones anteriores de esta tabla.

**The notebook opens with the map-legend, not with the headline numbers.** If the map *is* the
legend of every other figure, it has to be on screen before the first figure that uses it — so
the section moved to the top and carries the Burkart et al. (1999) citation and the reason
Islas del Atlántico Sur is missing (§3.2). The `_texto` variant writes the names out; the plain
one is what accompanies a multi-region chart.

**Two levels of the land-cover legend, natives first.** Análisis 5 and 6 each draw twice: the
**nivel-2 native classes** (17 of them burn) and then the **nivel-1 families** (5). Both come
from the *integrated national* col-3 legend — `.../COLLECTION-3/INTEGRATION/mapbiomas_argentina_collection3_pb`
decoded with the network's `lulc_argentina_nivel{0,1,2}` — never a per-region classification,
where one name can mean different things in different MapBiomas regions. The aggregation is the
legend's own; notebook §5.1 prints the whole crosswalk (código col-3 → nivel 2 → nivel 1 →
nivel 0), read off `lulc_area_eco13.csv` rather than retyped, and every figure's subtitle names
the level it is drawing.

Análisis 3.3 draws **straight lines between the 12 points, not the GAM**: factsheet-sep2026-spec.md asks for the
same format as análisis 2, and a cyclic smooth over a sharply peaked share series displaces
and overshoots the peak. The fit is still in `factsheet_season_fits.csv`, and it *is* what
accompanies the pirogram in análisis 3.2 and 3.4.

**The seasonal fit stops at abril.** Its grid is a full cycle in calendar month (1 → 12.999),
which in the display coordinate (mayo = 1 … abril = 12) wraps past 12 — drawn, the curve ran a
whole extra month beyond the last point, into a second mayo. Being cyclic, that tail was a
redrawing of mayo rather than an extrapolation, but it read as one. `factsheet_tables.R` now
trims the fits at `month_fy <= 12`.

### 5.5 `burn_perc_export.py` — the first raster, and the three traps in it

The factsheet's opening figure is the ecoregion map beside **a national map of the % of the
years each pixel burned**. It is the first of the **three images** the factsheet downloads
(the other two are §5.5.1 and §5.6; everything else here is a table) — and it is the same quantity as análisis 1 (mean annual burned proportion),
resolved per pixel instead of per region. That equivalence is the point: **the map's own mean
is the number the tables publish**, so the two cannot drift apart.

**The source** is `frequency_burned_v2`, band `fire_frequency_1999_2025` — how many of the 27
calendar years each pixel burned — divided by 27. The raw count is unpublishable: it is a
function of how long the series happens to be, and it will mean something different in
collection 2.

Three traps, all of them measured, and the GEE tuning tool
(`fuego:collection-01/visualization-misc/explore_burn_perc_display`) exists to show them:

1. **The product is `selfMask`ed.** Never-burned pixels are *absent*, not 0 (`07-subproducts.py`:
   "frequency is 1..N-or-absent, never 0"). Aggregate without `unmask(0)` first and the average
   is taken over burned pixels only — a country on fire, with any reducer.
2. **The reducer decides the map, not the scale.** Measured on a 2°×2° Chaco window (truth at
   30 m: 1.71 % of years): `mean` gives 1.71 % at *every* scale — it has to, it is a mean of
   means over equal-area cells — while `max` gives 3.69 % at 480 m (×2.2) and 7.56 % at 1920 m
   (×4.4). `max` does not aggregate, it propagates the worst 30 m pixel of each cell. That is
   the "zoomed out, everything looks burned", and no palette fixes it.
3. **EPSG:3857 is a display grid, not a measurement grid.** The v2 products sit on
   EPSG:3857 @ 30 m (v1 was on the 4326 SNIC lattice — check before comparing). There a cell's
   *ground* area falls with cos²(lat), so a naive `mean()` over its cells under-weights the
   north, which is where the fire is:

   | | |
   |---|---|
   | plain mean of the cells | 0.759 % |
   | weighted by ground area | **0.838 %** |
   | expected (63.23 Mha / 279.5 Mha / 27 years) | **0.838 %** |

   The map is right; the naive arithmetic is wrong. `--check` is that gate. On the R side the
   raster is reprojected to the factsheet's equal-area Albers before anything is done with it,
   which makes a plain mean honest again.

**Scale: 480 m**, 16× the native grid — an integer factor on the product's own lattice, origin
kept, so the coarse cells nest exactly in the fine ones: no resampling, no phase shift. The
choice is set by print, not by data: Argentina is ~3,700 km north–south, and a 20 cm figure at
300 dpi resolves ~1.6 km. 480 m is already three times finer than the paper, ~12 M pixels,
~24 MB as uint16. 120 m would be 16× the data for nothing visible.

**Why a batch task and not `getDownloadURL`.** Measured: the interactive download's size check
is done at the *native* 30 m, not at the requested grid, so a 2° box already answers "Object
too large (247 MB)" for a real result of 0.5 MB, and a 1° box exhausts memory on the burnable
mask (27 LULC bands). The whole country in 0.75° tiles would be ~900 requests. The batch task
has none of those limits.

**The cell denominator is the burnable area** (the mode over 1998–2024 of the col-3 burnable
classes — §3, the same denominator as every other `%` here), so a cell with nothing burnable in
it — a lake, a salt flat, a glacier — comes out **empty, not 0**. "Not burnable" and "burnable
and never burned" are different statements and the map keeps them apart.

```bash
$PYTHON collection-01/statistics/burn_perc_export.py --export    # one batch task -> Drive
$PYTHON collection-01/statistics/burn_perc_export.py --status
$PYTHON collection-01/statistics/burn_perc_export.py --fetch     # -> data/statistics/, + gate
```

---

### 5.5.1 The same raster in *times burned*, and the integer version

"3 % of the years" does not read on its own. The **same file** × 27 / 100 is "how many times
the average pixel of this cell burned", drawn with the same breaks and the same tones — one
`labs()` apart, and therefore unable to contradict the frequency map. That is
`map_burn_count(stat = "mean")` on the R side; no new download.

The number is **fractional**, because the cell is a mean of its 256 pixels. To get the
integer counts that let a legend start at 1 you need the cell's **maximum** — "somewhere in
this 480 m cell there is a pixel that burned N times" — which is a second file:

```bash
$PYTHON collection-01/statistics/burn_perc_export.py --export --reducer max
$PYTHON collection-01/statistics/burn_perc_export.py --fetch  --reducer max
```

It is a different quantity, not a different rendering, and it is the trap of §5.5 (2) applied
on purpose: it exaggerates. The worst pixel paints its whole 23 ha cell, which is exactly why
**the opening plate uses the mean version** and this one is the alternative. `--check` knows:
for any reducer other than `mean` it prints the numbers and explicitly declines to gate, so a
`max` run does not look broken.

---

### 5.6 `last_fire_export.py` — the second raster: the year of the last fire

The figure that opens **análisis 2** (factsheet-sep2026-spec.md §2.1): where it burned recently and where it
last burned twenty years ago. It is the exact complement of the opening map — that one says
*how much* each place burned in 27 years, this one says *when it last did* — and it comes from
the same family of products.

**The source** is `year_last_fire_v2`, band **`year_last_fire_2026`**. The `+1` is not a typo:
the band naming is `<subproduct>_<year+1>` in the reference and the platform expects it
(docs/07 §12.3.1), so `…_2026` is the complete 1999–2025 series and `…_2025` would stop at
2024. (The publish map's `band_format` says `classification_{year}`; the exported **asset**
carries the subproduct name. Verified 17 Sep 2026 on the v2.)

The product is `selfMask`ed, and here that is what we want: **never burned is absent, so it is
white on the map**, not the first tone of the ramp. Unlike `burn_perc_export.py` there is no
`unmask(0)` — adding zeros to the mean of a *date* means nothing.

**The reducer is `mean`** (decided with Iván, 17 Sep 2026): the value of a cell is the average
year-of-last-fire over the pixels that burned, and a cell where nothing burned comes out
masked. The two alternatives were measured against the map they produce, not against a number:

| reducer | what the cell would say | why not |
|---|---|---|
| `max` | "the most recent year anything in this cell burned" | saturates — in the Chaco nearly every 480 m cell has some pixel burned in the last two years, so the map goes flat |
| `mode` | the most common last-fire year among burned pixels | unstable when a cell has a handful of scattered burned pixels |
| **`mean`** | the average year over the burned pixels | fractional years (2011.4), which the class breaks absorb: the legend is a period, not a year |

**⚠️ The grid is NOT the frequency raster's, and that is the finding worth keeping.** Measured
17 Sep 2026, the nine v2 subproducts **do not share a lattice**:

| asset | CRS | origin |
|---|---|---|
| `frequency_burned_v2`, `annual_burned_v2` | EPSG:3857 @ 30 m | −8189460 / −2483190 |
| `year_last_fire_v2` | EPSG:4326, SNIC step | −73.56770985602505 / −21.73446880468659 |
| `PRODUCT_LULC` (col-3) | EPSG:4326, SNIC step | −73.5666318776841 / −21.780821873347158 |

The last two share a lattice: the origins differ by **exactly 4 columns and 172 rows** of the
same step, so an integer factor nests without resampling. The first does not. So this raster
aggregates on **its own asset's lattice** — asking for 3857 would resample both the year *and*
the mask of where fire happened, and that mask is the footprint the map draws.

The consequence, stated so nobody looks for it: **the two factsheet rasters cannot be crossed
cell by cell.** The gate crosses *national numbers* instead (the burned footprint), which no
lattice can move. For drawing it changes nothing — R reprojects both to Albers anyway.

**Two bands, two different encodings** (uint16 with an explicit 65535 nodata, because in
uint16 the default fill for masked is 0, which here would read as "1998" and as "never
burned", two different lies):

1. `last_fire` = (mean year − 1998) × 100. The offset exists because 2025 × 100 does not fit
   in uint16.
2. `burned_pct` = % of the cell's burnable pixels that ever burned, × 100. Built from **the
   same asset** as band 1 (`selfMask`ed ⇒ "has a year" *is* "ever burned"), not from
   `frequency_burned`, which lives on the other lattice — so the two bands count exactly the
   same pixels and gate 2 below is an identity, not an approximation.

Band 2 is not decoration: a cell where 0.4 % of the ground burned carries a year just like one
that burned whole, and drawn identically the map overstates the footprint. R decides with it
(`min_denom` in `map_last_fire()`, 0 by default — see factsheet-sep2026-spec.md §2.1 for why nothing is hidden).

**The gate** (`--check`) is three checks, none of them "the published number", because a date
has no published number:

1. every decoded year falls in [1999, 2025] — a mean of years cannot leave the range, so a
   value outside it exposes the encoding, which is the error you cannot see on the map;
2. band 1 has a value **iff** band 2 > 0 (the identity above);
3. **the two rasters together**, via the average number of fires per ever-burned pixel.

⚠️ **Check 3 cannot be "the same footprint on both rasters", and the first version of it was
wrong in a way worth recording.** The frequency raster gives the *mean* number of times a
cell burned, and a mean does not recover what fraction of pixels ever burned: a cell averaging
0.25 can be a quarter of its pixels burning once or an eighth burning twice. The first version
compared **14.68 %** (fraction of burnable *pixels* that ever burned, band 2 here) against
**26.45 %** (fraction of burnable area falling in 480 m *cells* that contain at least one
burned pixel, off the frequency raster) and failed by 11.8 pp while measuring two different
things. The second number is larger by construction — it is a dilation to cell size — and
neither raster is wrong.

What *does* tie them together:

```
fires per ever-burned pixel = (times the average pixel burned) / (fraction that ever burned)
```

The numerator comes from the frequency raster (`burn_perc` × 27 / 100, weighted by burnable
area); the denominator is band 2 here. The ratio **must** fall in [1, 27] — a pixel that
burned, burned at least once, and no more times than the series has years. Measured:

| | |
|---|---|
| burnable area that ever burned (band 2, area-weighted) | **14.68 %** |
| times the average burnable pixel burned (frequency raster) | 0.2515 |
| **fires per ever-burned pixel** | **1.71** |

and it reconciles with the published totals: 63.23 Mha burned with recurrences over ~36.9 Mha
ever burned is 1.71. The area-weighted quartiles of the year itself are 2004.0 / 2013.8 /
2019.7.

**The class breaks are regular four-year periods** (`1999 – 2002` … `2023 – 2025`), not
quantile cuts. Measured on the raster, the year of last fire is close to uniform over
1999–2025 (quartiles 2004.8 / 2011.4 / 2018.0), so constant width already gives even classes
*and* the legend reads without translating — a quantile cut would have produced
"2009.4 – 2013.7", which means nothing on a map.

```bash
$PYTHON collection-01/statistics/last_fire_export.py --export
$PYTHON collection-01/statistics/last_fire_export.py --status
$PYTHON collection-01/statistics/last_fire_export.py --fetch    # -> data/statistics/, + gate
```

---

### 5.7 `lulc_change_export.py` — análisis 6: what was there before, what is there after

The third and last GEE reduction, and the only question in the factsheet that needs **two**
land-cover maps per hectare. For each calendar year Y, the **whole country** crossed by

```
code = state * 1000000 + ecoregion13 * 10000 + col3_class(Y-1) * 100 + col3_class(Y+offset)
```

— the full area × fire state × ecorregión × class-before × class-after table, annual. One
integer, one `groupField`, one sweep: the same programming strategy copied from the network's
app (§2.1).

**⚠️ The packing does not fit in uint16** (3·10⁶ + 13·10⁴ + 7777 = 3,137,777). The band is
**int32**. Copying `lulc_area_export.py`'s `toUint16()` would overflow silently and the
classes would decode to something plausible; `legends.decode_lulc_change` validates the
state, the ecoregion and both classes, so an overflow raises instead of publishing.

**The design is Ferro et al. (2026)**, *"Why are you burning? The interplay between land
cover, climatic variability and fire activity in the dry forests of Argentina"*, Int. J.
Wildland Fire 35: WF25126 — this group's own Dry Chaco paper. What is copied verbatim is what
defines the analysis: the Y−1 → Y+1 window, the exclusion rule (§5.7.1) and the ratio `q`.
What differs: our 30 m fire product instead of MCD64A1 at 500 m, the whole country instead of
the Dry Chaco, and **exhaustive area accounting** instead of a multinomial GLM on sampled
points — they get probabilities with confidence intervals, we get hectares with none.

**Why Y−1 and not Y.** Because you cannot know whether the cover of the fire year is the
pre- or the post-fire one (their words). Y−1 is also, exactly, the one the network's numerator
assigns to the burned hectare (`annual_burned_coverage` crosses with `classification_<Y-1>`,
§2.2), so the "before" column reproduces análisis 4 class by class — and the gate checks it.
Y+offset is the "after", which caps the series: col-3 reaches 2025, so Y+1 ends at 2024
(26 years) and Y+3 at 2022 (24 years).

**The grid, and the trap it carries.** `annual_burned_v2` is EPSG:3857 and col-3 is on the
SNIC lattice (4326) — see the table in §5.6. Crossing them resamples one of the two, and the
one resampled is **the fire**: the reduction runs on `C.SNIC_CRS` + `C.SNIC_TRANSFORM`, the
native lattice of the *categorical* layer, where half a pixel of shift changes the class, and
the same lattice `lulc_area_export.py` already used. Measured, it costs nothing: the gate
closes at **0.00 % in every one of the 26 years**, because the toolkit reduces on that lattice
too.

**Masking: exactly one layer drives the mask** — the ecoregions, which tile the country. There
is no fire mask any more (§5.7.1). Both land-cover bands are `unmask(0)`ed, so a pixel the
collection does not map becomes a **visible "No observado"** row instead of vanishing.

---

### 5.7.1 The control, and why the reduction covers the whole country

**"15 % of what burned changed cover" means nothing without knowing how much cover changes
when there is no fire.** That is the entire reason the reduction is no longer masked to fire:
it sweeps the country and the fire state is one more dimension of the code.

It is nearly free. What costs is **reading** three 30 m bands over 279 Mha, and that happened
with the mask on too — `reduceRegion` does not read less because pixels are masked. What grows
is the number of groups, which is reducer memory and CSV rows (129 k rows for 26 years).

**The exclusion rule**, from Ferro et al.: use only pixels that did not burn in the previous
or the next year, to avoid land-cover classification errors — which is exactly the scar
artifact. Here it applies to **both** groups, and the two contaminated ones are kept as their
own states rather than dropped in silence:

| state | definition | share of country-years | changed nivel 1 |
|---|---|---|---|
| 0 `control` | no fire anywhere in [Y−1, Y+offset] | 97.63 % | **3.88 %** |
| 1 `burned_clean` | burned in Y, no other year of the window | 0.77 % | **14.51 %** |
| 2 `window_fire` | did not burn in Y, burned elsewhere in the window | 1.53 % | 11.39 % |
| 3 `burned_repeat` | burned in Y *and* elsewhere in the window | 0.07 % | 17.99 % |

The headline of análisis 6 ("of everything that burned, how much changed") is **1 + 3**; `q`
compares **1 against 0**, the two clean ones.

**That state 2 lands at 11.39 %, between the control and the burned group, is the check that
the rule does something**: it is a mixture of both, and it behaves like one.

The ratio is

```
q = P(changed | burned) / P(changed | not burned)
```

`q` > 1 fire promotes the change, `q` < 1 it limits it, `q` = 1 the same happens either way.
Nationally, **q = 3.74** at nivel 1 (14.51 % / 3.88 %) and 3.16 at nivel 2.

**`q` is conditioned on the origin class** in the per-transition table
(`factsheet_change_q.csv`): the transition probability is P(prev → post | prev, state), so
within each origin class the probabilities sum to 1. Unconditioned, `q` would mostly measure
*which classes burn*, which is análisis 4 and not this one.

**Why the control changes the reading, with the measured numbers.** Pampa has the highest raw
change (33.9 %) and also the highest background (6.9 %), so it drops from first to third.
**Campos y Malezales (q = 0.7) and Altos Andes (q = 0.8) come out below 1**: burned land there
changes cover *less* than unburned land — the raw number said "almost nothing changes", the
control says "less than nothing". And Bosques Patagónicos goes to the top (q = 7.3) on a
middling raw number.

### 5.7.2 Is it the scar or is it conversion? The Y+3 window

The standing objection to the whole analysis: col-3 is built from the same Landsat imagery
that sees the burn scar, so a burned forest can be classified as herbaceous in Y+1 **without
the forest having gone**, and be back to forest in Y+3.

`--offset 3` measures it. If the Y+1 signal were mostly that, the burned rate would fall back
toward the control by Y+3 and `q` would collapse toward 1:

| window | burned | control | q |
|---|---|---|---|
| Y+1 | 14.51 % | 3.88 % | **3.74** |
| Y+3 | 17.63 % | 5.81 % | **3.04** |

The burned rate **rises** (14.5 → 17.6), it does not fall. The mild `q` decline is the control
accumulating its own background change over a longer window, not burned pixels reverting.
**The transitions are persistent.** The artifact exists and is not eliminated, but it is not
what produces the bulk of the signal.

Note that the Y+3 window demands five fire-free years for the clean states, so considerably
less area feeds that number. That is the price of the question.

**What R does with it** (`factsheet_tables.R`, five decisions, all printed when it runs): the
level is aggregated *before* comparing (bosque cerrado → bosque abierto changes at nivel 2 and
not at nivel 1, so the two tables are built separately from the class code); the "before" side
is filtered like análisis 4 **in all four states** (filtering the treatment and not the control
would make `q` compare two different populations); `q` is conditioned on the origin class;
"No observado" stays visible; and the table is annual while the figures sum.

Four tables come out: `factsheet_change.csv` (burned only, the tidy annual source the Sankey
and the composition draw), `factsheet_change_annual.csv` (per state and year),
`factsheet_change_summary.csv` (the scalars, including `q_changed`) and
`factsheet_change_q.csv` (`q` per transition).

**And the caveat that belongs in the caption.** With a control and a persistence test this
says much more than it did without them, but it stays **observational**: pixels that burn are
not a random sample of the country, so part of `q` may be fire happening where the change was
going to happen anyway — fire as the tool of an already-decided clearing is in fact the most
likely reading of bosque → agropecuario (q = 10.9). factsheet-sep2026-spec.md §6 carries the same box for the
slide.

```bash
$PYTHON collection-01/statistics/lulc_change_export.py --test-rect            # seconds
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 1
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 3
$PYTHON collection-01/statistics/lulc_change_export.py --fetch  --offset 1    # decode + gates
$PYTHON collection-01/statistics/lulc_change_export.py --fetch  --offset 3
```

### 5.7.3 Two flags the general analysis does not use: `--lat-split` and `--window`

Both were added on 17 Sep 2026 to answer one objection, and both are general.

**The objection.** In the Andean-Patagonian forests fire is high-severity and the literature
puts stand mortality near **95 %**: what burns turns to shrubland or grassland. The general
analysis said **44 %** of burned forest changed cover at Y+1. Either the map is wrong or it
is slow.

**`--lat-split LAT`** adds a north/south bit to the code (`north * 10⁷ + …`, §5.7) so an
ecoregion that is not homogeneous can be split without inventing a new ecoregion. Bosques
Patagónicos is the case: north of −44 (from the middle of Chubut up) holds **87 %** of its
burned area and a different fire regime. Measured at Y+1, north 45.6 % against south 32.2 %,
with controls of 1.6 % and 4.3 % — two different systems inside one polygon.

**`--window N`** separates the fire-free **exclusion window** from the post-fire **lag**, and
without it the lag series cannot be read at all. By default the window equals the offset, so
each lag carries its own exclusion window *and therefore its own range of focal years*: Y+1
runs 1999–2024 and Y+5 runs 1999–2020, so Y+5 is missing every fire from 2021–2024. The four
numbers are then four **populations**, not a trajectory. Pinning `--window 5` makes all lags
share the same pixels and the same focal years, and only then does Y+1 → Y+5 mean "how long
does it take".

⚠️ `--offset 5 --window 5` **is** the plain `--offset 5` run — the `_wN` suffix is only
written when the window differs from the lag, so asking for `_y5_w5_…` asks for a file that
by construction does not exist.

**The result** (burned forest north of −44, fixed cohort, 44.1 kha identical at every lag):

| window | leaves forest | control | q |
|---|---|---|---|
| Y+1 | 48.9 % | 1.6 % | 30.5 |
| Y+3 | 71.1 % | 2.8 % | 25.4 |
| Y+4 | 76.2 % | 3.3 % | 23.4 |
| Y+5 | **78.4 %** | 3.7 % | 21.2 |

The increments collapse (+22.2, +5.1, +2.2 points), so it converges near **80 %**, not 95 %.
The destination is unambiguous: `Bosque cerrado` falls 51 → 22 % while `Matorrales y
arbustales abiertos` rises 36 → 57 %. **That is the arbustalización, reaching the map about
three years late.** The fixed cohort also reads *higher* than the shifting one at short lags
(48.9 vs 45.6 at Y+1), which is what must happen if the recent fires it excludes simply have
not had time.

**What does not explain the remaining ~17 points**: not reburn (`burned_repeat` is 0.3–0.7 kha,
negligible) and not the cohort (now fixed). Two candidates survive, both testable and neither
tested: our burned-forest set includes low-severity edge and small fires that severity mapping
does not count, and col-3's temporal integration — built to resist one-year flips — may never
release a fraction of killed stands.

**The consequence for the whole analysis, and it is not local to Patagonia.** Y+1 is Ferro et
al.'s window, calibrated on the Chaco, where fire *clears*: burn to deforest, crop next year.
Where fire **kills but does not clear**, one year is not enough, and the general analysis
understates those systems structurally. Read woody natural vegetation at **Y+3 minimum**, and
anything claimed about forest at **Y+4–5**.

Note also that **`q` falls as the window lengthens** (30.5 → 21.2) while the effect grows,
because the control accumulates its own background change. `q` answers "is this fire's doing?"
and the percentage answers "how much of this forest converted". They are different questions
and the window changes them in opposite directions.

`factsheet_tables.R` writes `factsheet_patagonia_bosque.csv` (the trajectory, both cohorts)
and `factsheet_patagonia_destinos.csv` (the destination mix); `notebooks/factsheet_veg.qmd` §5
draws them.

```bash
# el corte latitudinal, cada lag con su propia ventana (cuatro poblaciones)
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 5 --lat-split -44
# la cohorte FIJA: la ventana clavada en 5 para todos los lags (una trayectoria)
$PYTHON collection-01/statistics/lulc_change_export.py --export --offset 1 --window 5 --lat-split -44
```

---

### 5.8 `factsheet_veg_short.qmd` — análisis 6 cut down to what fits on a slide

`factsheet_veg.qmd` answers the question properly: a control, `q`, 12 ecoregions, two windows,
the Patagonian trajectory. **A slide holds none of that.** This notebook is the other end of the
same analysis — three sentences and two figures, national, and the exact wording each number
travels with. It recomputes nothing: it reads `factsheet_change.csv` and
`factsheet_change_annual.csv`, the same tables `factsheet_tables.R` already writes, and calls the
same `sankey_change()` from `factsheet_style.R`. Renders in ~10 s. The figure prefix is
**`fig06c_`** so it cannot collide with the long notebook's `fig06_` — one producer per figure.

**The three claims, measured (Argentina, 1999–2024, window Y−1 → Y+1):**

| | nivel 1 (familias) | nivel 2 (clases) |
|---|---|---|
| burned, series total | 61.4 Mha | 61.4 Mha |
| …of which changed class | **9.1 Mha — 14.8 %** | **12.5 Mha — 20.3 %** |
| vegetated surface, annual | 252 Mha | 252 Mha |
| …that changes class per year | **10.4 Mha — 4.1 %** | 17.4 Mha — 6.9 % |
| …that changes *and* burned | 0.35 Mha — **3.4 % of the change** | 0.48 Mha — 2.8 % |
| burned share of the surface | 0.9 % | 0.9 % |
| fire's weight in change / in area | **3.6×** | 2.9× |

**Every percentage carries its area.** A bare percentage cannot be checked against anything, and
"how many hectares is that?" is the first question a slide gets. Two units, and the notebook says
which is which in the column header: what **burned** is the **series total** (26 years,
recurrences included), what is **country surface** is **per year** — "6,521 Mha" is hectare-years
and means nothing to anyone, "252 Mha of vegetated surface" is the country.

**Four things this notebook has to say and the long one can take for granted:**

1. **"Of what burned" is hectare-years, not hectares.** 61.4 Mha is the sum over 26 years: a
   hectare that burned twice counts twice, with the cover of each of its two fires. It is **not**
   the accumulated area of the country that ever burned, which is smaller and does **not** come
   out of this table.
2. **"Changed cover" is a property of the hectare *and of the legend level*.** Bosque cerrado →
   bosque abierto changes at nivel 2 and does not at nivel 1, hence 20.3 % and 14.8 %. **Each
   Sankey must be captioned with its own level's number** — pairing the nivel-2 Sankey with the
   nivel-1 percentage is the easy mistake here.
3. **The window is two years, not one.** Y−1 against Y+1 (§5.7).
4. **The third claim's two bars have different denominators on purpose** — surface and change —
   and that is the comparison: if fire were indifferent to cover change the two would be equal.
   3.4 / 0.9 = 3.6 is the same thing `q` = 3.74 says on the clean states; they are close because
   they are two routes to one fact, not two findings.

**Five figures**: the two Sankeys of the change (nivel 2 and nivel 1, §1.1–1.2), the two complete
Sankeys with the diagonal (§1.4), and the two-bar weight-of-fire figure (§2). §1.3 is a table, not
a figure: the level reconciliation above, computed and asserted at render time.

**What the short notebook deliberately drops, and where to get it back**: the control itself
(the country changes 3.9 % without any fire) and `q`. §3 of the notebook says so, so that
"¿y eso es mucho?" from the audience has an answer that is one click away in
`factsheet_veg.qmd`.

**The Sankey threshold is per TRANSITION, and that makes arrival area unreadable.** Found by
Iván asking the right question of the two figures: the nivel-1 Sankey appeared to send *more* area
into forest than the nivel-2 one, which is impossible. The data is exactly consistent — the
identity is asserted in the notebook — and the whole effect is the threshold:

| | nivel 1 | nivel 2 |
|---|---|---|
| arrives at forest **from outside the family** | 0.891 Mha | **0.891 Mha** (identical, as it must be) |
| arrives at forest **from another forest class** | — (not a change at nivel 1) | 0.594 Mha |
| **total** arriving at forest | 0.891 Mha | **1.485 Mha** |
| spread over | 2 bands | **37 bands** |
| survives the figure's threshold | 0.891 Mha, 2 bands (**100 %**) | at ≥1.5 %: 0.355 Mha, **1 band (24 %)** |

Two separate things stack: the nivel-1 family `Bosques` is **three** nivel-2 classes (cerrado,
abierto, inundable), and a destination fed by many small flows is systematically under-drawn while
one fed by a single large flow is drawn whole. **Never read a class's arrival area off a
thresholded Sankey** — that is análisis 4's job. The fixes: nivel 2 now cuts at **0.5 %** (34
flows, 10.9 Mha, **87 %** of the change instead of 72 %, and the three forest classes actually
appear), the warning lives in `sankey_change()`'s header so the long notebook inherits it, and the
subtitle prints the coverage on every figure.

**`keep_unchanged = TRUE` — the complete Sankey, diagonal included** (new argument on
`sankey_change()`, default `FALSE`, so the long notebook is unaffected). It changes the question
and therefore the denominator: the total becomes all burned area and `min_share` is measured
against that. It comes out **flat, which is the finding** — 85 % of what burns is still what it
was at nivel 1, 80 % at nivel 2 — and it is the honest frame for the two zoomed figures above it.
At nivel 1 all 17 transitions fit (the 0.1 % cut is only so that the ~0-area destination classes
do not stack labels on the axis; it costs 0.14 % of the area), so the total height *is* the burned
area and proportions can be read off the drawing. At nivel 2, 0.25 % keeps 29 flows and 94.7 %.

Two figure-mechanics notes, both learned by looking: a long ggplot subtitle is **not** wrapped, it
is drawn off-canvas, so the subtitles go through `cap()`; and the nivel-2 y scale is re-declared
purely to add bottom expansion, because the smallest stratum otherwise sits on the axis with its
label clipped.

```bash
quarto render collection-01/notebooks/factsheet_veg_short.qmd     # ~10 s
```

### 5.9 Forest only — `factsheet_bosques.csv`, and the four windows we already have

The slide question is *"how much more likely is a forest to stop being a forest if it burns?"*.
`factsheet_tables.R` block 6b answers it nationally, reusing the Patagonian block's machinery
(`pat_file()` reads the `_n44` files), and writes `factsheet_bosques.csv` (the scalars) and
`factsheet_bosques_destinos.csv` (where the burned forest goes). The event is always **"leaves the
`Bosques` family"** — `nivel1_post != "Bosques"` — measured **by nivel-2 origin class**.

**⚠️ Y+4 and Y+5 ARE national.** `--lat-split` adds a north/south bit to the packed code; it does
**not** clip the reduction. `lulc_change_eco13_y{4,5}_n44.csv` are the whole country (13
ecoregions, 280.7 Mha/yr) and collapsing `north` recovers the plain national table. So all four
lags exist in both cohorts — **no new GEE run is needed** to report Y+4 or Y+5. (Lag 2 is the only
one never exported.)

**There are four different "forest" numbers and they are not interchangeable.** Measured, national,
Y+1, moving cohort:

| claim | level | burned | control | q |
|---|---|---|---|---|
| `Bosques` (family) stops being forest | 1 | 29.3 % | 4.6 % | **6.4** |
| **`Bosque cerrado` stops being forest** | 2 → 1 | 43.6 % | 3.1 % | **14.0** |
| `Bosques` → `agropecuario` (that one transition) | 1 | 17.3 % | 1.6 % | **10.9** |
| `Bosque cerrado` leaves its own nivel-2 class | 2 | 49.4 % | 4.2 % | **11.7** |

The sentence *"tras el fuego la transformación de bosques a otras clases es 11 veces más probable"*
reads as **row 1, which is 6.4**. The 10.9 is one transition out of the family's several (it is
61 % of what leaves, not all of it), and the 11.7 counts closed → open forest as a transformation
although it is **still forest**. Row 2 is the recommended headline: strongest *and* soundest.

**The family average is the trap, and this is the finding of the section.** The three forest
classes do not behave alike at all — `Bosque cerrado` q = 14.0, `Bosque abierto` 2.2, and
**`Bosque inundable` q = 1.0: fire does nothing measurable to it**. The 6.4 is an average over
three systems, describing none of them. **If one forest number goes on a slide it has to be a
class, not the family**, and `factsheet_bosques.csv` always carries the three classes *and* the
family row so the average can never be quoted alone.

**Window: the two numbers move in opposite directions** (closed forest, moving cohort): the
percentage rises 43.6 → 51.4 % from Y+1 to Y+5 (conversion takes time and one year does not see it
all) while q falls 14.0 → 9.1 (the control accumulates its own background over a longer window).
They answer "how much forest converted?" and "was it the fire?" — different questions. For a
*"it takes N years"* claim use the **fixed cohort** (`cohorte == "fija"`, window pinned at 5, the
same pixels at every lag), which the same file carries.

**Where the burned forest goes** (Y+1, states 1+3): of the 18.6 Mha of burned forest, 30 % leaves,
and of that **60.9 % goes to agropecuario** and 38.5 % to natural herbaceous/shrub. From closed
forest specifically, **50.9 % of what leaves goes to `Cultivos temporarios`** — the clearing
reading, which the figure cannot separate from fire *causing* it (factsheet-sep2026-spec.md §6.4).

**Two traps in the tables, both of which fail silently:** `"Bosques (familia)"` is a **row label in
the scalar table, not a legend class** — `factor()`ing it against the legend levels yields `NA` and
the Sankey renders as an empty panel with no error; and that label **does not exist at all** in
`factsheet_bosques_destinos.csv`, which is opened by nivel-2 class, so filtering for it returns
zero rows (the family figure has to sum the three classes). The notebook asserts against both.

### 5.10 `factsheet_sep2026.qmd` — the folder the designer gets

The deliverable. It draws **nothing new**: every figure is a version of one that
`factsheet.qmd` already draws, redone under one rule — **no title, no subtitle, no caption
inside the image**. What stays inside is what the picture cannot say otherwise: the legend and
its title, the axis titles, and (series and pirogramas) the region's name. The caption belongs
in the piece, set by the designer, and this document is where it is written.

It writes to its own folder, **not** to `figures/`:

```
collection-01/data/statistics/factsheet_sep2026_figures_and_tables/
```

with, for each figure, a **PNG at 300 dpi** and a **vector PDF**, and next to them
**`figNN_datos.csv`, the table that generates it**. The two maps have no CSV: they are
rasters of millions of cells and go as images only. A copy of the rendered HTML goes in too, so the folder explains itself. 43 files, 14 MB.

| # | figure | file | source |
|---|---|---|---|
| 0 | ecorregiones, blank | *not ours* | — |
| 1 | how many years each pixel burned | `fig01_mapa_anios_quemados` | `arg_burn_perc_480m_max.tif` (§5.5.1) |
| 2 | what burns nationally, nivel 2, in three cuts | `fig02_{torta,barras}_cobertura`, `fig02_torta_dos_anillos` | `factsheet_lulc_share.csv` (análisis 4) |
| 3 | year of the last fire | `fig03_mapa_ultimo_fuego` | `arg_last_fire_480m_mean.tif` (§5.6) |
| 4–8 | Mha burned per year: país, Monte, Espinal, Delta, Bosques Patagónicos | `fig0N_serie_<region>` | `factsheet_annual.csv` + `factsheet_trend_fits.csv` |
| 5–8 | the four regions in a 2 × 2, falling on top, rising below | `fig05-06-07-08_series_regiones` | same |
| 9–12 | pirograma: país, Delta, Chaco, Bosques Patagónicos | `figNN_pirograma_<region>` | `factsheet_pirogram.csv`, GAM refitted in the notebook |
| 10–12 | the three regions stacked in one column, to sit beside figure 9 | `fig10-11-12_pirogramas_regiones` | same |

#### ⚠️ 5.10.1 The network's nivel-2 legend had three class names rotated (fixed)

**Found 17 Sep 2026**, joining the MapBiomas palette by class code. The network's
`00_Tools/Legends.js::lulc_argentina_nivel2` has the VALUES of codes 11, 12 and 63 shifted one
place against their keys, so each code kept the next one's name. `statistics/legends.py` copied
that dictionary verbatim, so the error was in **every nivel-2 table we produce**.

| code | the legend said | what it **is** | share of burned |
|---|---|---|---|
| 11 | Mosaicos de arbustos y herbaceas | **Herbaceas Inundables** | 21.2 % |
| 12 | Herbaceas Inundables | **Herbaceas** | 21.7 % |
| 63 | Herbaceas | **Mosaicos de arbustos y herbaceas** | 4.1 % |

**Six independent lines of evidence; the geographic one alone settles it.** Code 11 is **75 %
of what burned in Delta e Islas del Paraná**, a wetland. Code 12 is **62 % of what burned in
the Pampa**, dry grassland. Code 63 is **51 % in the Puna** and **37 % in the Estepa
Patagónica**, and `config/veg_fire_remap.csv` names it per region `Estepa (ID=63)` and
`Arbustales Dispersos (ID=45); Pastizales (ID=12)`. Also: our col-2 remap assigns the three the
other way and calls 11 `Vegas/Mallines`; **Chile's legend in that same file** uses the global
convention (11 Humedal, 12 Pastizal, 63 Estepa); MapBiomas worldwide uses 11 = wetland,
12 = grassland; and the order the three Argentine entries are written in (`63:`, `12:`, `11:`)
is exactly the rotation.

##### The fix is on BOTH sides, and they go together

This is the part that can be got wrong. **The numerator↔denominator join in
`factsheet_tables.R` is BY NAME** (`by = c("ecoregion_id", "year", "clase")`):

- the **denominator** is ours and decodes by CODE, so fixing `legends.py` fixes it;
- the **numerator** is the network's toolkit CSVs (`annual_burned_coverage_*.csv`), which
  arrive with the class NAME already decoded by that same buggy `Legends.js`. We do not
  generate them, so they are permuted **on read**, in `factsheet_tables.R` (`fix_n2()`).

**Fixing only one side is worse than fixing neither.** All three names exist on both sides, so
`Herbaceas` in the denominator would pair with `Herbaceas` in the numerator while being
different classes: no orphan rows, no gate fires, and every análisis-5 percentage comes out
wrong in silence. The permutation is **closed** (the three names swap among themselves), so
applying it to both sides leaves the join identical in structure and correct in meaning.

##### What had to be re-run: no GEE at all

Every `_raw.csv` was already on disk, and both exporters re-decode from it without touching the
network (`--check`). Total cost about a minute, plus the renders.

```bash
$PYTHON collection-01/statistics/lulc_area_export.py --check            # denominador
$PYTHON collection-01/statistics/lulc_change_export.py --check --offset 1
# ...y las otras ocho combinaciones de --offset / --window / --lat-split
Rscript collection-01/statistics/factsheet_tables.R                     # 4.5 s
```

All ten gates PASS. `burnable_export.py` and `burn_perc_export.py` are **not affected**: they
use the burnable/non-burnable code lists and the ecorregión+status decode, never the LULC names.

##### What moved and what did not

**Nivel 0 and nivel 1 are untouched** because all three classes sit in `Vegetación natural
herbácea y arbustiva`: every family-level figure and number is byte-identical, including the
factsheet's 25 % forest and the whole forest block of §5.9 (codes 3, 4 and 6). What changed is
**only the label** on the nivel-2 half: `factsheet_lulc*.csv`, `lulc_area_eco13.csv`, the
`factsheet_change*` tables, and the nivel-2 figures of all four notebooks. **No number moved**;
the same hectares now carry the right name.

The sanity check, after: Pampa is 62 % *Herbaceas*, the Delta 75 % *Herbaceas Inundables*, the
Puna 51 % *Mosaicos de arbustos y herbaceas*. And in análisis 5 the two flooded classes are the
ones that burn most per year (bosque inundable 4.05 %, herbáceas inundables 3.47 %), which is
the Delta, the Chaco and the Iberá.

##### Still owed

**Tell the network.** The file is theirs and every country that decodes the Argentine legend
reads it; it is worth checking whether the same rotation is in another country's block. And
check whether anything already published (ATBD, old decks, the paper draft) quotes one of the
three names.

#### The four things decided here

Each one is a way the figure could have been wrong:

- **The unit of the series and of the pirograma bars is Mha, not `%` of burnable.** The long
  notebook plots `%` because that is what compares regions; a factsheet reader wants hectares.
  The GAM is **not re-fitted**: a region's burnable area is constant, so `fit / 100 * burnable`
  is the same fit in another unit.
- **The trend band's two colours are read off the year-of-last-fire map, not chosen here.**
  That map uses plasma INVERTED, so dark is recent; the band therefore puts the rising regions
  (Delta, Bosques Patagónicos) in the dark violet and the falling ones (Monte, Espinal) in the
  light orange. The two figures share a lámina, and the opposite assignment would have them
  saying contrary things in the same colour.
- **Decimals on the Y axis are taken from the step between ticks**, not fixed. In Mha per month
  Argentina runs to 0,42 and Bosques Patagónicos to 0,002: with two fixed decimals the
  Patagonian axis reads `0,00` five times. `num_auto()`.
- **The nivel-2 palette is the same system with more luminance range.** `LULC_N2_COLORS` is
  tuned for a stacked bar, where a class touches its neighbours; on a pie the six beiges of
  *Vegetación natural herbácea y arbustiva* collapsed into one colour. Same families, same
  order, wider ramp (`LULC_N2_PIE`).
- **A map's legend title cannot be changed with `labs(fill = ...)`.** `map_classes()` sets it
  through `scale_fill_manual(name = ...)`, and in ggplot2 the scale's `name` **wins over
  `labs`** — silently, so the figure comes out with the old title and nothing warns. Hence
  `relabel_fill()`, which renames the scale that is already there instead of adding a second
  one (which would also mean a second hand-typed copy of the colour table).

A fifth: **the pirogramas are stacked with patchwork, not `facet_wrap`.** The second axis is
why: the factor `k` that turns Mha into fire counts differs per region, and a facet shares ONE
scale specification, so the right-hand axis would come out carrying one region's factor for all
three. `plot_layout(axis_titles = "collect")` gives what the facet was wanted for anyway (the
three axis titles written once, the axis VALUES repeated in every panel) and leaves no box
around each panel. The stacked image keeps figure 9's width, because twelve month labels need
it; what shrinks is the height of each panel.

Also: **the four regional series come as a 2 × 2 facet**, falling on the top row and rising on
the bottom, with the row order derived from the sign of each trend rather than written down, so
a region that changed sides would reorder the figure instead of contradicting its own layout.
`facet_wrap` IS the right tool there, unlike in the pirogramas: that figure has no second axis,
so nothing per region is beyond what a facet can express, and only the Y range differs
(`scales = "free_y"`, with the floor pinned at 0 for all four).

A sixth: **the seasonal GAM is refitted in the notebook**, not read from
`factsheet_season_fits.csv`, so its basis can be moved — but it is run at the **same setting as
the tables, `k = 10` and `gamma = 1`** (`GAM_K` / `GAM_GAMMA`, one place). A harder fit was
tried (`k = 12`, `gamma = 0.5`: 10.95 effective degrees of freedom, 99.99 % of deviance
explained, i.e. very nearly an interpolation) and **dropped on 18 Sep**: at that setting the
curve stops summarising anything and just joins the points, which is not what a seasonality
curve is for. Do not move those two constants again without being asked.

Its grid is generated **in drawing order, not in calendar months**, and that is a bug worth
remembering: built from January to December, the April-to-May stretch lands at `month_fy` 12 to
13, half a month to the RIGHT of the April tick, and the curve ran off the axis into a month
already drawn at the other end. Built from 1 to 12 in drawing order it starts in May and ends
in April. The price is that it **does not close the cycle**: there is a visual break between
April and May even though the model is cyclic. Deliberate, and the cheaper of the two errors.

A seventh: **the pie's classes are ordered by decreasing woodiness**, not by area: bosque
cerrado, abierto, inundable, matorrales, mosaicos, herbáceas, pastura, herbáceas inundables.
It is a gradient of vegetation structure rather than a ranking, so the circle reads as a
physical axis. The bar uses the same order, because two orders for one legend on one lámina is
what makes a reader treat them as two legends. **`fig02_torta_dos_anillos` is the exception**
and has to be: a nested ring needs a family's children to be contiguous, so there the order is
family first and woodiness within it, which moves *Pastura* next to the other agricultural
classes. Its family colours are the standard palette's PARENT codes (1, 10, 14), which exist in the
dictionary even though no pixel of the integration ever carries them.

The two-ring figure has **nivel 2 inside and nivel 1 outside**, which is the only orientation
that reads: the outer ring is the *sum* of the inner one, so each family arc covers exactly its
own children and the eye goes from the coarse reading inward to the detail. The inner ring is
**grouped at 4 %**, so it shows ten slices and none is a sliver. ⚠️ The grouping is **per
family, not once**: a nested ring needs a family's children contiguous, so a single "Otros"
mixing turberas with silvicultura would have to break into two arcs under different parents.
There are therefore two grey slices, one in the herbaceous family and one in the agricultural,
sharing a name and a colour, and the legend shows one entry.

⚠️ **The arcs are computed by hand, with `geom_rect` and not `geom_col`.** `geom_col` stacks by
the **levels of the fill factor**, not by the order of the rows, so no amount of `setorder()`
fixes it: the inner ring came out in pure-woodiness order (with *Pastura* between the two
herbáceas) while the outer went by family, and the two rings were offset — *Pastura* drawn
inside the natural-vegetation arc. Reordering the levels does not fix it either, because the
two "Otros" share a level and `geom_col` would fuse them into one slice. With explicit
`ymin`/`ymax` there is no implicit order left to guess.

An eighth: **the cover palette is MapBiomas', joined by class code.** `MB_PALETTE` is the col-3
`mapbiomasPalette` copied verbatim from the LULC team's own production script
(`mapbiomas-arg-pat-col3/Workflow/13-reclass`), indexed by class code, and `lulc_area_eco13.csv`
is the only table carrying `class_id` next to the legend levels, so the join is read and never
retyped. Two codes that palette does not cover, both Argentina-only: **77** (Matorrales y
arbustales abiertos, 12.5 % of what burned) takes the colour from our own `fuego` repo and is
the one colour in the figure that is not the network's; **73** (Turberas) takes index 75, which
is what the LULC team's own workflow calls that class.

**The notebook checks itself before finishing** (the `compuerta` chunk). Two things are verified
against what the run actually wrote: that every `figNN_...` the prose names in backticks exists,
and that nothing in the folder is left over from an older run under a name no longer used. The
third, that every figure written also appears in the HTML, is settled by construction rather
than by a list: `save2()` returns the plot **visibly**, so any chunk ending in `save2(...)`
draws it, and the two loop chunks end in `invisible(NULL)` so they do not duplicate what is
shown below them. That one was a real bug: the two-ring pie spent a whole run in the delivery
folder and absent from the HTML, because `save2()` returned `invisible()` and nothing inside the
notebook could tell.

Cost: **the first render is ~7 minutes and every one after it is under one.** Figure 1 alone
was about six of those seven: it is the only raster drawn at its native 480 m with
nearest-neighbour (§5.5.1: averaging would push half the mapped cells below 1 on a scale that
starts at 1), so reprojecting it to Albers and flattening ~5 M cells to a data frame dominated
the run. **The two maps are now simply not redrawn**: if their PNG and PDF are already in the
delivery folder and newer than the `.tif` they come from, the notebook inserts the written PNG
instead of recomputing anything. They rebuild on their own when a file is missing or a new
`.tif` lands, and `-P force_maps:true` forces it. Nothing else in the notebook is cached, because
nothing else takes longer than a second.

## 6. Everything is calendar-year — and the three divergences

**Every number the factsheet reports is calendar-year**: the burned area, the denominator and
the fire counts. The fire year (1 May → 30 Apr) is how the *mapping* is organised, not how
anything is reported. The month axis is nonetheless **displayed** May → April, so the season
is not cut in half — a display order, nothing more.

What differs is *how* each side files a fire into a year and a month:

1. **Per pixel vs per object.** The rasters assign year and month **per pixel** from
   `abs_date`; the counts assign **per object** from `date_median`. A fire straddling
   31 December is split between two calendar years in the area numbers and filed whole in one
   of them in the counts.
2. **"Area burned in month M"** is a pixel sum on the toolkit's side and a whole-object
   assignment on the object side. Same shape, different values.
3. **The denominator is a 27-year mode**, not that year's burnable area (§3.3).

Acceptable — say all three out loud, and always say which side a number came from.

---

## 7. The territorial layer

Three consumers: the toolkit's numerator run, our denominator export, and the platform's
territory selector (§11). All three must name the **same 13-class asset**, because the
factsheet joins the numerator to the denominator on that id:

```
projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857
```

13 features, unique id **`GEOCODE`** (a number, 1..13), name **`LEVEL_2`**, clean UTF-8. The
names, straight off the asset: 1 Altos Andes · 2 Bosques Patagónicos · 3 Campos y Malezales ·
4 Chaco · 5 Delta e Islas del Paraná · 6 Espinal · 7 Estepa Patagónica · 8 Monte · 9 Pampa ·
10 Puna · 11 Selva Paranense · 12 Yungas · 13 Islas del Atlántico Sur. They live as a
**literal** in `statistics/legends.py`, so no decode depends on reading a vector.

### 7.1 Three traps, all measured on 2026-09-14

1. **The `_r` rasters are numbered differently from their own vectors.** On the 13-class
   `_r` the pixel values run **alphabetically** — Islas del Atlántico Sur is **8**, Monte 9,
   Pampa 10, Puna 11, Selva Paranense 12, Yungas 13 — while the vector's `GEOCODE` appends
   Islas at 13. Ids 1–7 agree; **six of thirteen do not**. Verified by cross-tabbing the
   raster against the painted vector over the whole country: each raster id maps ~100 % onto
   one polygon, so the geometry is the same and only the numbering diverges. Decoding a
   raster-derived table with the vector's dictionary reports **Monte's 47 Mha as Pampa**.
   **Paint the vectors, never read the `_r` rasters.** (Their background is also `0` and
   *unmasked*, so a reduction without `selfMask()` gets a giant "territory 0" row.)
2. **`Stats-Arg_*` names are Latin-1 bytes stored as UTF-8** — `Esteros del Iber<?>`. The
   `_3857` layers are clean. The damage is also in `Stats-Arg_political_level_*` and will
   matter again in December; never let it reach a CSV a designer reads.
3. **`GEOCODE` is a STRING on the 16-class `_3857` asset** (a number on the 13-class one), so
   `paint(fc, 'GEOCODE')` silently paints nothing useful. Cast before painting. Only bites in
   December, but it is exactly the kind of difference that makes an export succeed and decode
   to nonsense.

Other layers in the same family, for December: `ARG-Political_Level_2-16Ecorregiones_3857`
(16), `Stats-Arg_political_level_3_v` (528 departamentos, INDEC 5-digit `GEOCODE`),
`Stats-Arg_political_level_2_v` (24 provincias).

### 7.2 16 → 13 is an exact aggregation (measured)

Every 16-class falls **100 %** inside one 13-class: 4 Chaco Húmedo and 5 Chaco Seco → 4 Chaco;
9 **Esteros del Iberá → 4 Chaco** (the only non-obvious row, which is why it was measured);
10 Monte de Llanuras y Mesetas and 11 Monte de Sierras y Bolsones → 8 Monte; every other one
maps across unchanged. Kept in `legends.py::ECO16_TO_13` for December: an exact aggregation
means a 16-class run can always be collapsed, but a 13-class table can never be split up.

### 7.3 Deferred to December: ecorregión × departamento

Written down so it is not re-derived:

```
territory_id = ecoregion16 · 100000 + GEOCODE(departamento)   # max 1,694,021 — exact in int32
```

`GEOCODE` on the department layer is `provincia·1000 + departamento`, so **one painted layer
gives both political levels** and the province needs no second asset. Because the pieces are
disjoint, every coarser cut is a `group_by` on the finer table. With two packed layers the
masking rule of §3 bites again: keep the ecorregiones as the single mask driver and
`unmask(0)` the departments, so a `departamento == 0` row is *visible* rather than silently
dropped. At that point the class code no longer fits one field — either the territory becomes
the reducer's second group field or the two pack into one int64. Decide then.

*Provenance*: the 16 ecoregions are **Administración de Parques Nacionales**, Burkart et al.
1999, and the 13-class layer is the published aggregation of the same; departments and
provinces are **IGN**.

---

## 8. Burnable: a col-3 legend decision

"Burnable" is a property of the **class**, not a computation. Our col-2 remap
(`config/veg_fire_remap.csv`) is the anchor: in **every one of the 5 regions** it sends
MapBiomas classes 24, 25, 33, 34 → non-burnable and 27 → non-observed. Region-independent, so
it carries to col-3 unchanged. The list lives in `statistics/legends.py`, next to the decode,
and is named in the export task description.

| col-3 code | nombre (nivel 2) | veredicto |
|---|---|---|
| 0, 27 | No observado | **fuera del numerador y del denominador** |
| 22 | Áreas sin vegetación | no quemable |
| 24 | Áreas urbanas | no quemable |
| 25 | Otras áreas no vegetadas | no quemable |
| 26, 33 | Cuerpos de agua / ríos, lagunas, lagos y océano | no quemable |
| 34 | Hielo en superficie y nieve permanente | no quemable |
| 1, 3, 4, 6 | Bosques | quemable |
| 9, 14, 15, 18, 19, 21, 36 | Agropecuario / silvicultura | quemable |
| 10, 11, 12, 63, 66, 73, 77 | Herbáceas, arbustales, turberas | quemable |

**22 and 26 had no precedent and were decided.** They do not appear in col-2 v8 at all, so our
remap never ruled on them; both are **non-burnable** (Iván, 2026-09-11) — the bare-ground and
water families, where the col-2 remap puts their nearest equivalents.

The decode **raises** on any code present in the export and absent from this table: a class
that falls through into a decode default is a silent error.

---

## 9. Verification gates

Two tables, computed by two teams on two grids, joined on one id. Most of what can go wrong
is in that join.

| # | check | status |
|---|---|---|
| 1 | **The test rectangle** decodes to 13 ecorregiones × {0,1} and nothing else | ✅ before anything national ran (§3) |
| 2 | **Both sides key the same** — the toolkit's territory names, our denominator's and the object tags' are the same set | ✅ measured: `setdiff` empty in both directions. Check the **names**, not the count: a mis-keyed join produces a plausible, wrong `%` for six regions (§7.1 trap 1) |
| 3 | **Ties and always-no-observado pixels** | ✅ 268 ha of ties nationally; never-observed reported as its own row, and the Delta's 1.53 Mha is a caption (§3.1) |
| 4 | **Denominator ≥ numerator, every ecorregión × año** | ✅ max observed `%` is 18.9 % (Delta, 2020). A `%` over 100 would be either a mis-keyed join or real burning on modally non-burnable pixels |
| 5 | **Total area closes** — Σ our rows ≈ the national area | ✅ rasterised 279.51 Mha vs 279.53 Mha of polygon, 0.2 % or better per region (§3.1) |
| 6 | **National annual burned: toolkit vs the object database** | ✅ **63.23 vs 63.25 Mha over 1999–2025 — 0.03 %.** Per-year differences reach 10 % and are *expected*: the products split an object per pixel by `abs_date`, the object table files it whole by `date_median` (§6). This is the one check that the toolkit read *our* products correctly |
| 7 | **Lattice** — our export pinned vs at `scale: 30` | sub-pixel rounding, not systematic inflation (§2.3) |
| 8 | **Against the platform, in *staging*, before launch** | pending. Within the network's stated ~1 % mean difference. **Don't chase the 1 %** — do chase anything much larger (wrong territory layer, wrong LULC year, a region missing) |

Gates 2, 4 and 5 are cheap and catch the failure modes that are invisible in the numbers
themselves. Do them first.

---

## 10. What these tables cannot answer

- (**`%` per LULC class** used to be here. It is answered now — §5.3.)
- **Scar size crossed with land cover or month**: `annual_burned_scar_size_range` has no LULC
  dimension.
- **Fire-year totals**, directly — but the toolkit's table carries month *and* year, so a
  fire-year total is recoverable as May..Dec of *y* plus Jan..Apr of *y+1*. A legitimate
  aggregation of calendar-year products, and it should be labelled as such.
- **Error-adjusted area.** That is [`11-validation.md`](11-validation.md)'s design-based
  estimate, and it is not ready for September.
- **Anything at departamento or provincia level with a `%`.** The toolkit already exports the
  provincia cut (`*_Provincia.csv`, absolute areas), but there is **no burnable denominator at
  that cut** — §7.3.

---

## 11. Publication and launch (stage 6)

Not statistics, but it is what happens next and it has no other home.

**Public assets.** Brazil owns the copy: `ToPublish/3-toAsset-Public` does `copyAsset` →
`setAssetAcl({all_users_can_read: true})` → `setAssetProperties({data_type, band_format,
version})` into `projects/mapbiomas-public/assets/argentina/fire/collection1/`;
`ToPublish/2-toBucket-subproducts` writes one COG per band to
`gs://shared-development-storage/…`. **The platform ingests the public GEE assets**; the
bucket COGs serve the download page. Our job is to have the `FINAL_PRODUCTS` assets correct
and named exactly right, and to check the copies afterwards. ⚠️ **Re-exporting
`FINAL_PRODUCTS` changes nothing the public sees until Brazil re-copies**, and the COGs need
regenerating alongside.

**Workspace catastro** (<https://workspace.mapbiomas.org/modules>) is the internal metadata
registry — **nothing appears on the platform until it is registered here**. Three
registrations: the **subthemes** (one per published product; *match an existing country's
names* rather than inventing ours), the **legends** (⚠️ take values and hex colours from
`Mapbiomas-Fogo-Legenda-Col4.xlsx`, never from screenshots, and make sure the registered
scar-size ranges match the ranges we actually rasterized), and the **territorial layers** of
§7 — ours. Brazil supports; we supply the values and verify.

**The network's other five stage-5 tables** (`toDrive-area-{monthly,accumulated,frequency}-burned-coverage`,
`-scar-size`, `-year-last-fire`) are publication artefacts no factsheet number depends on.
They read the published products **as they are**, with the **same-year** LULC their reference
encoding specifies — so they and the factsheet's numbers **cannot agree, by construction**
(§2.2, §3.3). Say so in the hand-off. The **scar-size side stays blocked** on the manual
ingest of the 27 calendar-scar packages, which nobody else can do for us.

**Launch track** (parallel, non-code): destacados + infographic (Brazil provides a template),
validation in *staging*, website materials (ATBD, methodology page, informative note),
downloads page + a legend-codes page, the event, the press release.

> **Argentina's ATBD is the one document nobody else can write for us.** Our method differs
> from every other country in the network, so it cannot be adapted mechanically from Brazil's
> — it has to describe the burn-probability → SNIC → object-model chain, including the
> non-calendar fire-year and how it is re-partitioned into calendar years.

**Open questions for Brazil**: which ecoregion layer the platform's territory registration
expects; whether the `Stats-Arg_*` encoding damage should be repaired at the source before
December needs the departments; whether they would take a `crsTransform` patch upstream in
`core/calculate.js`; the **last date** we can hand them updated assets and still be on the
platform for 24 Sep (that date, not the 24th, is the real deadline); who regenerates the
Cloud-Storage COGs after a re-export; and whether to run the FireCCI / GABAM / MCD64A1
comparison (`2-Statistics/1-Burned_area_products/`) — recommended, since it is the only
external sanity check available for a first collection.

---

## 12. Decisions on record

| # | decision | who / when |
|---|---|---|
| 1 | **The burned-area table is the network's toolkit's**, run with our ecoregion layer; we compute **only the burnable denominator**. No JS fork, no hand-written reducer | Iván, 2026-09-11 / 09-14 |
| 2 | The toolkit exports to **GCS** (`gs://mapbiomas-fire/data-container/stats/…`, downloaded into `data/statistics/`); our own denominator export goes to **Drive** | Iván, 2026-09-14 |
| 3 | **September computes at ecorregión only.** Departamento and provincia are December (Bariloche) | Iván, 2026-09-14 |
| 4 | The denominator is a **constant burnable layer**: the **mode over 1998–2024** of the col-3 burnable classes, reduced as `ecoregion13·10 + status` on the pinned grid | Iván, 2026-09-14 |
| 5 | Fire counts assign each fire to **every ecorregión it intersects** (`terra::relate`, a predicate, never a geometry); regional counts exceed the national total by design | Iván, 2026-09-15 |
| 6 | The lattice is pinned (`crs` + `crsTransform`), never `scale: 30`, on our side | Iván, 2026-09-11 |
| 7 | Territories are **packed painted vectors**, never intersected ones, and never the `_r` rasters | Iván, 2026-09-11 / 09-14 |
| 8 | Everything crosses **col-3 (`PRODUCT_LULC`)**, and the burned × LULC cross reads the **PREVIOUS** year in our copy of the toolkit. The published `*_coverage` products keep the network's **same-year** encoding, so the two disagree by construction and every figure says which it used | Iván, 2026-09-11 / 09-14 |
| 9 | Burnable is defined on **col-3 classes**, never on `veg_fire`. Col-3 **22 and 26 are non-burnable** | Iván, 2026-09-11 / 09-14 |
| 10 | Ecoregions are **Burkart et al. 1999**, and **both sides run on the 13-class vector**. The 16-class layer and the exact 16 → 13 crosswalk stay for December | Iván, 2026-09-10 / 09-14 |
| 11 | **Islas del Atlántico Sur is not reported**: it is outside the processing grid, so its zero is a mapping gap, not a finding | 2026-09-15 |
| 12 | The factsheet makes **two** land-cover statements, with two denominators and never conflated: the **composition of what burned** (análisis 4), from the already-exported `annual_burned_coverage`; and **what % of each class burned** (análisis 5), which needed the second export `lulc_area_export.py`. Both read the **previous** year's cover | Iván, 2026-09-15 |
| 12c | **Non-burnable classes are out of both land-cover analyses** (§5.2.1): fire on water/glacier/city/bare ground is mapping error — 0.09 % of what burned — and keeping it put two invisible bars in every chart and stole a point from the 100 % | Iván, 2026-09-16 |
| 12b | In análisis 5 the **mean over years is taken LAST** — per-year ratios, then averaged. `Σburned / Σarea` is a different number (Jensen) and double-counts every reburn | Iván, 2026-09-15 |
| 13 | **We do not use Looker Studio.** The network builds one per country off these CSVs; Argentina's analysis is ours, in R, straight off the tables | Iván, 2026-09-11 |
| 14 | The object exclusion rules and their thresholds are **FINAL** (docs/07 §1.1) — not a parameter these statistics may vary | Iván + team, 2026-09-11 |
| 15 | Statistics on our own **fire-year objects** (per-event size distributions, season-spanning fires) are worth a separate, clearly-unofficial output — but not before 24 September | Iván, 2026-09-11 |
