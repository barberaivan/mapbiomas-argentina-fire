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
  fire_counts.R       THE VECTOR PASS (§4) — the fire tables + the plotting geometry
  factsheet_tables.R  THE ANALYSIS PASS (§5) — the plot-ready tables and the GAMs
  factsheet_style.R   the shared palette, theme, map-as-legend and figure variants

collection-01/notebooks/
  factsheet.qmd       THE FIGURES (§5.2) — draws only; writes PNG + PDF

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
  factsheet_*.csv                 the plot-ready tables (§5.1)
  figures/                        120 files: 60 figures × PNG + PDF
```

The GEE JavaScript is in the **`fuego` repo**, not here:
`users/mapbiomas-arg/fuego:collection-01/statistics/` (app, datasets, `_shared`,
`territories`).

**Run order**, from the repo root:

```bash
$PYTHON collection-01/statistics/burnable_export.py --export     # §3, once
$PYTHON collection-01/statistics/lulc_area_export.py --export    # §5.4, once
$PYTHON collection-01/statistics/lulc_area_export.py --fetch     # ...then pull it down
Rscript collection-01/statistics/fire_counts.R                   # §4, ~20 s
Rscript collection-01/statistics/factsheet_tables.R              # §5, ~10 s
quarto render collection-01/notebooks/factsheet.qmd              # §5.4, ~60 s
```

Only the two exports touch GEE. The point of the split is that **everything the factsheet draws
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
  it is **análisis 6**, `factsheet_lulc_pct.csv`. The two must never be conflated in a caption:
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
  count**, by design (docs/10 análisis 3); the national row is computed from the fire set
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
summary makes it do. docs/10 asks for `k = 12`; measured, **12 does the opposite at the one
place it matters** — nationally it overshoots the August peak by 8 % and the Chaco's by
10.5 %, drawing a curve higher than any month actually is. **`k = 10`** reproduces the
national peak to 0.2 % and is the compromise across the 12 regions.

**The toolkit writes only rows that burned**, so a region-year with no fire is simply absent.
Every table is therefore built on a complete grid and filled with zeros — otherwise a mean
over years silently divides by the number of years that happened to burn.

### 5.2 Análisis 5 — the composition of what burned

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

### 5.3 Análisis 6 — what percentage of each class burned

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
is **55 % forest of what burned** (análisis 5) and burns **0.16 % of its forest a year**
(análisis 6): almost everything that burns there is forest, because almost everything there
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
docs/10 in code, so the whole factsheet reads as one family: one **colour per ecorregión,
stable everywhere**, on a **latitude ramp** (hue 12 → 280, warm north to cool south, with
luminance alternating along it so that mid-ramp neighbours — which are also neighbours on the
map — stay apart); the **map as the legend**, exported loose; and the two variants,
`all_regions` for choosing whom to highlight and *focal* for the slide.

`params$write_plots` (default `true`) writes every figure to `data/statistics/figures/` as
**PNG** (the PowerPoint draft) and **PDF** (the designer). Render with
`-P write_plots:false` to preview without writing. 60 figures:

| prefix | n | what |
|---|---|---|
| `fig00_mapa_leyenda`, `fig00_mapa_focal_*` | 13 | the map-as-legend and its focal variants |
| `fig01_*` | 2 | análisis 1 — proporción quemada media: el mapa y las barras |
| `fig02_*` | 15 | análisis 2 — el mapa de tendencia, la serie nacional, `all_regions` normalizada, 12 focales |
| `fig03_pirograma_*` | 13 | análisis 3 — pirograma nacional y por ecorregión, doble eje |
| `fig04_*` | 13 | análisis 4 — la forma intraanual, `all_regions` y 12 focales |
| `fig05_*` | 2 | análisis 5 — la composición de lo quemado: barras apiladas y el mapa de `share_bosques` |
| `fig06_*` | 2 | análisis 6 — qué % de cada clase se quema: el heatmap región × clase y el mapa del bosque |

Análisis 4 draws **straight lines between the 12 points, not the GAM**: docs/10 asks for the
same format as análisis 2, and a cyclic smooth over a sharply peaked share series displaces
and overshoots the peak. The fit is still in `factsheet_season_fits.csv`, and it *is* what
accompanies the pirogram in análisis 3.

---

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
| 12 | The factsheet makes **two** land-cover statements, with two denominators and never conflated: the **composition of what burned** (análisis 5), from the already-exported `annual_burned_coverage`; and **what % of each class burned** (análisis 6), which needed the second export `lulc_area_export.py`. Both read the **previous** year's cover | Iván, 2026-09-15 |
| 12b | In análisis 6 the **mean over years is taken LAST** — per-year ratios, then averaged. `Σburned / Σarea` is a different number (Jensen) and double-counts every reburn | Iván, 2026-09-15 |
| 13 | **We do not use Looker Studio.** The network builds one per country off these CSVs; Argentina's analysis is ours, in R, straight off the tables | Iván, 2026-09-11 |
| 14 | The object exclusion rules and their thresholds are **FINAL** (docs/07 §1.1) — not a parameter these statistics may vary | Iván + team, 2026-09-11 |
| 15 | Statistics on our own **fire-year objects** (per-event size distributions, season-spanning fires) are worth a separate, clearly-unofficial output — but not before 24 September | Iván, 2026-09-11 |
