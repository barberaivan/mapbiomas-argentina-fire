# 09 — Statistics (stage 5), publication and launch (stage 6)

Everything that happens **after** the GEE assets exist and **before** the public launch. The assets
themselves are [`07-vector_to_raster.md`](07-vector_to_raster.md) (what we build) and
[`08-postprocessing.md`](08-postprocessing.md) (what the network expects); the launch guide, the
read-only reference repo and the legend spreadsheet are catalogued in **docs/08 §1** and not
repeated here. The factsheet's *content* — which graphic says what — is
[`10-factsheet_design.md`](10-factsheet_design.md); this file is where each of its **numbers** comes
from. **[`ROADMAP.md`](../../ROADMAP.md) is the *when*; this file is the *how*.**

**Four things that are settled, so nobody re-opens them:**

- **We do not compute the burned-area table at all.** As of 14 Sep it comes from **the network's
  toolkit**, run with our ecoregion layer registered in it. The only thing we compute in GEE is the
  **burnable denominator** — one constant layer, 26 rows, §4. The old per-year hand-written 30 m
  reductions (`workflow/11-burnable_area.py`, `workflow/11-burned_area_stats.py`) stay dead and are
  deleted once this route is verified ([`ROADMAP.md`](../../ROADMAP.md)).
- **A fixed modal burnable layer is back — but on col-3, not `veg_fire`.** September's earlier plan
  cancelled the modal layer because a per-year space-filling table carried its own denominator.
  With the numerator
  coming from the toolkit that is no longer true, so the denominator is a **mode over 1998–2024 of
  the col-3 burnable classes** (§4.2, §6). It is a different layer from the `veg_fire` modal one
  that was cancelled, and the reason it is acceptable is written down in §4.4.
- **The object filters are not here.** The rules that fix the agriculture and Pampa over-mapping
  are part of the *mapping* and live in [`07-vector_to_raster.md` §1.1](07-vector_to_raster.md). By
  the time the statistics run they are already baked into the assets.
- **We do not use Looker Studio.** The network builds a Looker dashboard per country off these
  CSVs. **Argentina's analysis is ours, in R**, straight off the exported table: the factsheet
  plots, the GAMs, the trend summaries, every cross-tab in §8. The export's job ends when the CSV
  lands on disk.
- **September is ecoregion-only.** See §1.2 — this is the scope decision that shrinks the whole
  stage.

---

## 1. What we build, and where it lives

### 1.1 The layout

```
collection-01/statistics/          ALL statistics + factsheet code, Python and R
  burnable_export.py  ✅ the constant burnable layer: the Córdoba test (--test-rect), the
                      per-ecoregion table + gate (--regions), the national Drive export (--export)
  legends.py          ✅ the burnable class list (§6), the 4 status codes, the 13 ecoregion names
                      as literals, the 16->13 crosswalk kept for December (§5.2)
  decode.py           the toolkit's CSV -> tidy table (ours is decoded by burnable_export.py)
  fire_counts.R       fire counts off the LOCAL object database (§8.2)
  factsheet_tables.R  the four factsheet analyses, from the tidy tables + the counts (§8)
  factsheet_plots.R   the plots; content plan in docs/10-factsheet_design.md

collection-01/data/statistics/     ALL statistics data — raw exports and derived tables
  burnable_eco13_raw.csv   as GEE returned it: code, area_ha
  burnable_eco13.csv       decoded: ecoregion, status, area_ha, polygon_ha — the denominator
  burned_toolkit_*.csv     what the toolkit produced (month x year x ecoregion x LULC)
  fire_counts_by_month.csv per ecoregion x CALENDAR year x month (counts, from objects)
  fire_region_summary.csv  per ecoregion: fires/year, area/year, size quantiles
  figures/                 the plots handed to the designers
```

`collection-01/data/` is a symlink into the Insync store, so `data/statistics/` is Drive-synced —
which is also how the export arrives (§4.4). Everything the factsheet reads is in that one
directory; nothing factsheet-related is written to `data/objects-analysis/` any more.

`scripts/objects_region_tag.R` stays where it is — it is a general object utility, not factsheet
code — but `scripts/factsheet_object_stats.R` is factsheet code and moves in as
`statistics/fire_counts.R`, with the rule change of §8.2.

### 1.2 ⚠️ Scope for September: **ecoregion only**

**We compute at the ecoregion, and not at departamento or provincia.** The finer territorial cuts
are real work we intend to do — they are for the **December Bariloche launch**, not for the 24 Sep
factsheet. Consequences, all deliberate:

- One territorial cut, so **one export task on our side** (§4.3) and one cut asked of the toolkit
  (§4.1), not a family of either.
- The territory id is **packed into the class code** (§4.3) instead of being a second group field,
  which is what makes one integer per pixel enough.
- The `ecoregion16 · 100000 + GEOCODE(departamento)` packing designed for the master cut is
  **deferred, not cancelled** — it is written down in §5.4 so December does not re-derive it.
- Anything the platform's territory selector needs at province level (§11) is a *registration*
  question, not a statistics one, and is unaffected.

**Both sides run on the 13-class layer** — the toolkit's numerator and our denominator are joined on
that id, so they cannot be keyed differently (§5.2).

---

## 2. The method is theirs, and why it is fast

The toolkit is `2-Statistics/toolkit/v03/` in the read-only reference repo
(`/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`). Its reducer is *identical* to the one we
benchmarked at 8 h/year:

```js
// core/calculate.js
var reducer = ee.Reducer.sum().group(1, 'class').group(1, 'territory');
```

There is no trick in the reducer. It is fast because of what is *around* it — and since the
numerator is now literally their app, these five are what **our one export** (§4.3) copies, and what
to check if their run is ever slow:

1. **The cross-tab lives in the pixel value, not in a loop.** Every crossing is packed into one
   integer — Brazil goes to four dimensions in one band (`fire·10⁵ + lulc·10³ + def_sec_veg·10 +
   edge`). Cost is O(pixels), never O(pixels × combinations).
2. **No vector is ever intersected.** Territory is `ee.Image().paint(fc, id)` — one raster, one
   band, every territory returned by a single reduce. No `filterBounds`, no per-feature loop, no
   `st_intersection`, and therefore no slivers to clean up.
3. **The reduction geometry is a `bounds()` rectangle.** It can be, because `paint()` is masked
   outside the painted features, so the territory band already drops everything outside the country.
   Passing the buffered national multipolygon clips every tile against a 2 M-edge geometry and buys
   nothing.
4. **No `tileScale`.** Ours was 4 — roughly 16× the shards, each re-paying the fixed per-shard cost.
   Add it only if a task OOMs, and record that it was needed.
5. **All years in one task.** 27 reductions flattened into a single `Export.table`: one queue slot,
   one CSV.

Note what is *not* on that list: **computing the image on the fly is fine**. Brazil's datasets are
`multiply`/`unmask`/`add` combinations of public assets, 41 bands, national, and they run. Cheap
arithmetic over stored byte bands on one lattice is not the problem; complex clip geometry, shard
multiplication and hidden resampling are.

Decoding codes to names happens on the few thousand *result rows*, locally in `decode.py` — never
per pixel.

**Where our one export diverges from their `core/`, and why:**

| divergence | reason |
|---|---|
| `crs` + `crsTransform` instead of `scale: 30` | §3 — every raster here is on one lattice. Their numerator run stays on `scale: 30`; at this pixel size that is a sub-pixel phase difference (§3), not a resolution difference |
| Python instead of JavaScript | the analysis is already Python + R in this repo and the constants already exist in `utils/constants.py`; a Code Editor round-trip is the wrong dependency for a 26-row table |
| `Export.table.toDrive` instead of GCS | we have no write access to `gs://mapbiomas-fire/…` and do not need one; Drive syncs straight into the store (§4.6) |
| territory packed into the class code | one cut (§1.2), so one group field is enough |

---

## 3. The grid: pin it, never `scale: 30`

Every raster in this pipeline sits on one lattice and must keep sitting on it — that rule has held
since step 03 and the statistics get no exception. `reduceRegion` takes **either** `scale` **or**
`crs` + `crsTransform`; we always pass the pair, from `utils/constants.py`:

```python
crs          = C.SNIC_CRS         # 'EPSG:4326'
crsTransform = C.SNIC_TRANSFORM   # [0.000269494585236, 0, -73.58468801489491,
                                  #  0, -0.000269494585236, -21.764113209062533]
```

Two things worth knowing about why this is cheap rather than expensive:

- `30 / 111319.49 = 0.000269494585236` — the toolkit's `scale: 30` in EPSG:4326 lands on **exactly**
  our pixel size. So pinning does not change the pyramid level and cannot trigger the mode-pyramid
  dilation of a sparse burned raster (+14 % at 90 m, +36 % at 120 m, measured). What `scale: 30`
  *would* get wrong is only the **origin phase** — a sub-pixel shift of every product against every
  other.
- The published LULC (`C.PRODUCT_LULC`) is an **integer offset** from our lattice (+67 px lon,
  −62 px lat, verified 2026-09-10). Integer offset means same phase: pinned to `SNIC_TRANSFORM`, the
  LULC band and the month band land on identical pixels with **no resampling anywhere** in the
  reduction.

---

## 4. The two tables, and who computes each

**The strategy changed on 14 Sep.** We no longer compute the burned-area cross-tab ourselves. The
split is now:

| table | what it is | who computes it | how |
|---|---|---|---|
| **the numerator** | burned area by **month × year × ecoregion × LULC** | **the network's toolkit**, with our ecoregion layer registered in it (§4.1) | their app, their grid, their encoding |
| **the denominator** | **burnable area by ecoregion**, one constant | **us**, one small GEE export (§4.2–§4.3) | the same programming strategy as their app |
| the fire counts | fires per ecoregion × **calendar year** × month | us, **locally**, off the object database | §8.2 — never touches GEE |

What this buys: the one heavy, error-prone export is no longer ours to write, verify and re-run
three days before the factsheet. What it costs is written down in §4.4 — read it before quoting a
`%`.

### 4.1 The numerator — the toolkit run

Brazil runs their toolkit with **our ecoregion layer** as the territorial cut. The layer to hand
them is the **13-class vector**, and the id is:

```
projects/mapbiomas-argentina/assets/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857
```

13 features, unique id **`GEOCODE`** (a number, 1..13), name **`LEVEL_2`**, clean UTF-8 — the schema
their toolkit expects (§5).

**⚠️ Do not hand them the `_r` raster twin instead.** Its pixel values are *not* `GEOCODE`: the
raster numbers the regions alphabetically, the vector appends Islas del Atlántico Sur at 13, and
they disagree for six of thirteen (§5.2). A dictionary built from one and applied to the other
reports Monte's 47 Mha as Pampa. Verified by cross-tab, 2026-09-14.

**Reviewed against their code, 2026-09-14** (`toolkit/v03/argentina/`, by Wallace Silva and Vera
Laisa). It is real, it already carries our ecorregiones, and it works. What the review settled:

| question | answer |
|---|---|
| territory | `ecorregiones.js` reads **our 13-class vector**, keys on `GEOCODE`, names from `LEVEL_2` ✅. Its `ee.Number.parse()` on a numeric `GEOCODE` is harmless (tested) |
| which assets | `_shared/lulc_base.js` reads **public `_v1`** — and `annual_burned_v1` / `monthly_burned_v1` **are not there**, while the v1 that is there is the superseded mapping. See below |
| which LULC year | upstream is **SAME-year** (`alignThemeToFire()` pairs `burned_area_<Y>` with `classification_<Y>`). **Our copy crosses the PREVIOUS year** — see §4.1.1 |
| month × LULC | **not available** — there is no `monthly_burned_coverage` dataset in their app, though our v2 asset of that name exists. The pirogram is month-only |
| grid | `scale: 30`, not our pinned transform — same pixel size on this lattice, a sub-pixel phase shift (§3). Fine, and not worth asking them to change |
| destination | `Export.table.toCloudStorage` → `gs://mapbiomas-fire`, and **we have write access** (`storage.objects.create` granted). The "do we need a Drive fallback?" question is closed |
| units | `pixelArea/1e6` km², `×100` → the `Área ha` column really is hectares |

**The one problem, and the fix.** Their base module reads `mapbiomas-public/..._v1`, which is missing
exactly the two layers the factsheet needs. So we run **a repointed copy** in our own repo —
`users/mapbiomas-arg/fuego:collection-01/statistics/apps/fuego_col1.js` — identical to theirs except
that `_shared/lulc_base.js` reads our `FINAL_PRODUCTS` `_v2`, with an in-place warning on the four
products that have no v2 yet (frequency, accumulated, scar size, year-last-fire: exporting those
today would publish v1 numbers). `core/*` and `00_Tools/Legends.js` are still required from **their**
repo — the engine is not ours to fork. **Delete the copy** once their `lulc_base` points at v2, or
once v2 is published to `mapbiomas-public`.

The click-by-click — which boxes to tick, what lands where — is in [`ROADMAP.md`](../../ROADMAP.md)
under "RUN THIS", because it is a procedure, not a design.

#### 4.1.1 The land-cover year: we cross the PREVIOUS one, and that is a discrepancy

**What we changed.** In our copy, `annual_burned_coverage` crosses fire band `<Y>` with
`classification_<Y−1>` (`alignThemeToFirePrevYear`, `fuego` 742b23a3). Verified server-side:
`burned_area_1999..2025` select `classification_1998..2024`, all inside col-3's 1985–2025, no band
missing.

**Why.** A fire consumes the vegetation that was there *before* it burned. The same-year class of a
burned pixel is partly a **consequence** of the fire — burned forest is frequently classified as
something else in the very year it burns — so a same-year cross answers "what did this pixel
become", not "what burned". Argentina reports the second question.

**What we did NOT change, and why.** `frequency_burned_coverage` and `accumulated_burned_coverage`
stay on same-year: their band names end in the **last** year of a multi-year window
(`fire_frequency_1999_2025`), so "previous year" has no single meaning there, and they are
network-spec products we do not reinterpret. Neither feeds the factsheet.

**The discrepancy this creates — three places, and they are not the same thing:**

| | crosses | why |
|---|---|---|
| our statistics CSV (`annual_burned_coverage` via our copy) | **previous year** | the question we report |
| the **published** `*_coverage` assets (`..._v2`, docs/07 §12) | **same year** | the network's encoding, copied verbatim; not ours to change |
| every other country's statistics | **same year** | their spec |

**The published asset is untouched by this.** The app computes coverage on the fly from
`annual_burned × LULC` and never reads the `*_coverage` asset — so our change moves the CSV only.
That is deliberate: the product stays network-conformant, the analysis answers our question, and the
two **disagree by construction**. Any figure or table that crosses fire with land cover must say
which of the two it came from. See §9 for the same warning on the platform's side.

### 4.2 The denominator — one constant burnable layer

**Burnable stops being per-year.** One boolean per pixel: was this pixel burnable *most of the
time* over 1998–2024? Then one area per ecoregion, computed once, used as the denominator for every
year.

```python
BURNABLE = [1, 3, 4, 6, 9, 10, 11, 12, 14, 15, 18, 19, 21, 36, 63, 66, 73, 77]   # §6
NON_BURN = [22, 24, 25, 26, 33, 34]                                              # §6
# 0 and 27 (no observado) are in NEITHER list, so remap leaves them MASKED and the
# mode never sees them — which is exactly "no observado is excluded everywhere" (§6).

def burnable_year(y):
    return (ee.Image(C.PRODUCT_LULC).select(f"classification_{y}")
            .remap(BURNABLE + NON_BURN, [1] * len(BURNABLE) + [0] * len(NON_BURN)))

burnable = (ee.ImageCollection([burnable_year(y) for y in range(1998, 2025)])
            .reduce(ee.Reducer.mode()))        # masked where every year was no-observado
```

- **1998–2024**, i.e. the previous-year range of calendar years 1999–2025 — the same 27 layers the
  per-year design would have read, collapsed instead of crossed.
- The result is **one image, no year dimension**. That is the whole point: 13 numbers, stable, and
  nothing in the denominator moves when a LULC class does.

**What is implemented is the mean, not `ee.Reducer.mode()` — and it writes four statuses, not
two.** The two reducers agree everywhere except exact 50/50 pixels, which `mode()` sends silently to
0 (it breaks ties toward the smaller value). Both of the things that could quietly shrink the
denominator therefore get **their own code** instead of being folded into "not burnable":

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
```

A shrunk denominator inflates every percentage in the factsheet, so it has to be visible in the
table rather than discovered later. Gate 3 (§7) is then just "read rows 2 and 3"; the decode folds
them wherever we decide, on the record.

### 4.3 The reduction — the same programming strategy as the app

Same shape as §2, one cut, so the territory packs into the class code and one group field is enough:

```
code = ecoregion13 · 10 + status          # max 13·10 + 3 = 133 — fits uint8
```

```python
eco = ee.Image().paint(ee.FeatureCollection(C.ECOREGIONS13), "GEOCODE")   # the mask driver
code = eco.multiply(10).add(status).toUint8().rename("code")

g = (ee.Image.pixelArea().divide(1e4)                    # hectares
     .addBands(code)
     .reduceRegion(reducer=ee.Reducer.sum().group(groupField=1, groupName="code"),
                   geometry=BOUNDS,                      # a RECTANGLE, never the multipolygon
                   crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
                   maxPixels=1e12))
```

- **At most 52 rows** (13 ecoregions × 4 statuses), in practice fewer. One task, one CSV.
- **Exactly one layer drives the mask** — the ecoregions. `add()` propagates masks, so `status` is
  already unmasked into codes 0–3 before it is added, and nothing can vanish silently.
- Constants: `C.ECOREGIONS13`, `C.ECOREGION_ID_PROPERTY`, `C.STATS_DRIVE_FOLDER` were added to
  `utils/constants.py` alongside the existing `PRODUCT_LULC`, `ARG_BUFFER_FC`, `SNIC_CRS`,
  `SNIC_TRANSFORM`. Never retype an asset id into `statistics/`.
- **Pin the grid anyway** (§3). Their toolkit reduces the numerator at `scale: 30`, which on this
  lattice is the same pixel size and a sub-pixel phase shift (§3) — irrelevant for a denominator
  quoted to three significant figures, but our side costs nothing to get exactly right.
- **Namespace the task `description`** (`arg09_burnable_eco13`). The compute project is shared with
  the whole network (docs/07 §12.7).

### 4.4 What the constant denominator changes — read before quoting a `%`

- **`%` is now "of the area that is burnable most of the time", not "of this year's burnable
  area".** For a series over 27 years that is arguably the better reference: a fixed denominator
  means the trend is a trend in *fire*, not in land-cover change. Say it in the footnote in exactly
  those terms.
- **Numerator and denominator no longer read the same layer-year.** They cannot be reconciled pixel
  by pixel, and a `%` above 100 is no longer structurally impossible — it would mean a region burned
  more than its modal burnable area, which is a real (if unlikely) finding about non-burnable pixels
  burning, not an arithmetic bug. Gate 4 (§7) checks it.
- **`%` by LULC class is not computable from these two tables.** The toolkit's table is burned-masked
  (no unburned rows) and our denominator has no class dimension. If the factsheet wants "% of
  grassland that burned" (docs/10 analysis 1's per-class variant), it needs one more small export of
  the same shape — `code = eco13 · 100 + lulc`, per year, space-filling — which is the same cost as
  §4.3 plus a digit. Decide before promising the panel, not after.
- **Everything is keyed on the 13-class ecoregion**, on both sides, because the join is on that id.
  Do not let one side be computed on the 16-class layer (§5.2).

### 4.5 The rectangle test — `--test-rect`

Before the national run, the same code runs over a small rectangle in **Córdoba** (dry Chaco /
Espinal, west of Villa María: −63.90 −31.55 → −63.70 −31.35), where nearly everything is burnable.
Two numbers have to come out right, and both are cheap:

| check | measured 2026-09-14 |
|---|---|
| **reported total vs the rectangle's own area** — does the table account for the whole rectangle? | 42,156.3 / **42,191.8 ha = 99.92 %** (the gap is boundary pixels: the rectangle does not fall on the lattice) |
| **burnable share** — Córdoba should be nearly all burnable | **99.92 %** (31.9 ha of `no_burnable`) |

7 s. It catches every structural error the national run takes longer to reveal: a wrong band name, a
mask that ate the country, a code that decodes to an impossible class, an empty `groups` list. It is
a flag on `burnable_export.py`, not a commented-out block.

### 4.6 Drive, and which account

Output goes to **Google Drive, not Cloud Storage** — we have no write access to the network's bucket
and do not need one. The folder is **`gee_fire_stats` on the PRIMARY (gmail) account's Drive**
(`C.STATS_DRIVE_FOLDER`, Iván 2026-09-14), so the default resident credentials are the right ones
and nothing has to be swapped.

**That folder is NOT Insync-synced into the store** — unlike step 04's `objects-raw`
(`C.SNIC_DRIVE_FOLDER`), which lands under `STORE_ROOT/collection-01/data/`. It does not matter
here: these tables are tens of rows, so `burnable_export.py` also computes them locally and writes
`data/statistics/burnable_eco13{,_raw}.csv` directly. The Drive copy is the shareable artefact, not
the path the analysis reads.

To run as the second account anyway (its task queue is its own):
`--credentials ~/.config/earthengine/credentials.comahue --project mapbiomas-argentina`, the
`workflow/07-burned_area_polygons.py::initialize()` pattern — never swap the credentials file.

### 4.7 First run — the numbers, and the one thing to look at

Run 2026-09-14. The national reduction is **one batch task, 2 m 15 s**, 52 rows, landing in Drive
`gee_fire_stats` and in `data/statistics/burnable_eco13{,_raw}.csv`.

| ecorregión | burnable Mha | not burnable | never obs. | raster Mha | polygon Mha | burnable / region |
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
| Islas del Atlántico Sur | 1.158 | 0.042 | 0.007 | 1.207 | 1.202 | 96.3 % |
| **TOTAL** | **252.248** | 26.910 | 1.558 | 280.717 | 280.733 | **89.9 %** |

**The gates it passes.** Burnable ≤ the region's own polygon area, every region (the gate the run
exists for). Rasterised total vs polygon area agrees to **0.2 % or better** everywhere — the two
share only the asset, so the paint, the lattice and the packing are all confirmed at once. The
shape of the low numbers is the right shape: Altos Andes 37 % and Puna 53 % are rock, salt and ice;
Chaco, Espinal, Pampa and Yungas are 97–98 %.

**⚠️ Delta e Islas del Paraná: 1.53 Mha — 27 % of the region — is "never observed".** Col-3 does not
map the open water of the Paraná and the Río de la Plata, so those pixels are class 0 in every year
and are excluded from the denominator, which is exactly what §6 asks for. But it means the Delta's
`%` runs on **3.50 Mha, not 5.61 Mha** — a `%` around 60 % larger than a reader computing it off the
region's map area would get. **If the Delta appears in the factsheet, that sentence goes in the
caption.** Every other region's never-observed area is under 10 kha.

**Ties are not a problem.** 268 ha nationally, all of it in Altos Andes. So `mean` and
`ee.Reducer.mode()` would give the same answer here; the tie code stays anyway, because "it was
negligible in 2026" is not a property of the next collection.

**Two operational notes for whoever runs this again.** (1) **Batch, not interactive**: the national
batch task took 2 m 15 s, while the per-region `getInfo` fallback needed over 13 minutes for its
*first* region — interactive compute is throttled differently. `--regions` is a fallback, not a
route. (2) **The Drive API is not enabled on `mapbiomas-fire-485203`**, and enabling an API on a
project shared with the whole network to read one of our own files is not ours to do — so `--fetch`
builds its Drive client **without a quota project**, which bills the call to the OAuth client and
touches nothing shared.

---

## 5. The territorial layer

Three consumers now: **the toolkit's numerator run** (§4.1), our denominator export (§4.3), and the
**platform's territory selector** (§11). All three must name the **same 13-class asset**, because
the factsheet joins the numerator to the denominator on that id.

### 5.1 The layers exist — and three of them are traps

**Verified 2026-09-11 in the asset browser, and re-checked against the assets themselves
2026-09-14.** A complete, purpose-built territorial family is already in
`ANCILLARY_DATA/VECTOR/ARG/`, carrying MapBiomas's own schema (`CATEG_ID`, `GEOCODE`, `LEVEL_1..3`,
`NAME_STD`, `SOURCE`, `VERSION`):

| asset (`ANCILLARY_DATA/VECTOR/ARG/`) | n | `GEOCODE` | names | notes |
|---|---|---|---|---|
| **`ARG-Political_Level_2-13Ecorregiones_3857`** | **13** | 1..13, numbers | `LEVEL_2`, clean UTF-8 | ✅ **THE layer — ours and the toolkit's** |
| `ARG-Political_Level_2-16Ecorregiones_3857` | 16 | 1..16, **STRINGS** | clean UTF-8 | December / the finer split (§5.2) |
| `Stats-Arg_ecorregions` | 16 | 1..16, numbers | **Latin-1 damaged** | same ids as the above — do not use for names |
| `Stats-Arg_political_level_3_v` | 528 departamentos | INDEC 5-digit | `LEVEL_3` depto, **`LEVEL_2` provincia** | December (§5.4) |
| `Stats-Arg_political_level_2_v` | 24 provincias | 2..94 | `LEVEL_2` | December (§5.4) |

The 13-class `GEOCODE` → name list, straight off the asset: 1 Altos Andes · 2 Bosques Patagónicos ·
3 Campos y Malezales · 4 Chaco · 5 Delta e Islas del Paraná · 6 Espinal · 7 Estepa Patagónica ·
8 Monte · 9 Pampa · 10 Puna · 11 Selva Paranense · 12 Yungas · 13 Islas del Atlántico Sur. Put it in
`statistics/legends.py` as a literal, so no decode depends on reading a vector.

**⚠️ Three traps, all measured on 2026-09-14:**

1. **The `_r` rasters are numbered differently from their own vectors.** On
   `ARG-Political_Level_2-13Ecorregiones_3857_r` the pixel values run **alphabetically** — Islas del
   Atlántico Sur is **8**, Monte 9, Pampa 10, Puna 11, Selva Paranense 12, Yungas 13 — while the
   vector's `GEOCODE` appends Islas at 13 and numbers Monte 8, Pampa 9, Puna 10, Selva Paranense 11,
   Yungas 12. Ids 1–7 agree; **six of thirteen do not**. Verified by cross-tabbing the raster against
   the painted vector over the whole country: each raster id maps ~100 % onto one polygon, so the
   geometry is the same and only the numbering diverges. Decoding a raster-derived table with the
   vector's dictionary reports **Monte's 47 Mha as Pampa**. **Hand the toolkit the vector** (§4.1).
2. **`Stats-Arg_*` names are Latin-1 bytes stored as UTF-8** — `Esteros del Iber<?>`,
   `Administraci<?>n de Parques Nacionales`. The `_3857` layers are clean. The damage is also in
   `Stats-Arg_political_level_*` and will matter again in December; never let it reach a CSV a
   designer reads.
3. **`GEOCODE` is a STRING on the 16-class `_3857` asset** (it is a number on the 13-class one), so
   `ee.Image().paint(fc, 'GEOCODE')` silently paints nothing useful. Cast before painting:
   `fc.map(lambda f: f.set('GEOCODE', ee.Number.parse(f.get('GEOCODE'))))`. Only bites in December,
   but it is exactly the kind of difference that makes an export succeed and decode to nonsense.

Every layer has a raster twin in `…RASTER/ARG/`, all **EPSG:3857 at 30 m** — a different grid from
ours, and mis-numbered per trap 1. **Paint the vectors, never read the `_r` rasters.** Keep them as
an independent cross-check, not as an input. (Their background is also `0` and *unmasked*, so a
reduction that reads one without `selfMask()` gets a giant "territory 0" row.)

### 5.2 16 → 13 is an exact aggregation (measured)

Measured by crossing the two painted layers over the whole country: every 16-class falls **100 %**
inside one 13-class.

| 16-class | → 13-class | | 16-class | → 13-class |
|---|---|---|---|---|
| 1 Altos Andes | 1 Altos Andes | | 9 **Esteros del Iberá** | **4 Chaco** |
| 2 Bosques Patagónicos | 2 | | 10 Monte de Llanuras y Mesetas | 8 Monte |
| 3 Campos y Malezales | 3 | | 11 Monte de Sierras y Bolsones | 8 Monte |
| 4 Chaco Húmedo | 4 Chaco | | 12 Pampa | 9 |
| 5 Chaco Seco | 4 Chaco | | 13 Puna | 10 |
| 6 Delta e Islas del Paraná | 5 | | 14 Selva Paranense | 11 |
| 7 Espinal | 6 | | 15 Yungas | 12 |
| 8 Estepa Patagónica | 7 | | 16 Islas del Atlántico Sur | 13 |

The only non-obvious row is **Esteros del Iberá → Chaco**, which is why this was measured rather
than assumed.

**We nonetheless run on 13**, both sides, because the toolkit's numerator is keyed on the 13-class
layer and the join has to be on one id (§4.4). The crosswalk stays here for December, when the finer
split (Chaco Húmedo vs Chaco Seco, the two Montes) is worth having: it is exact, so a 16-class run
can always be aggregated down, but a 13-class table can never be split up.

### 5.3 Why packing, not intersecting

Brazil packs painted layers arithmetically; Paraguay and Bolivia pre-intersect a vector. **We
pack** — into the class code itself (§4.3) while there is one cut, into a territory id when there
are two (§5.4). Packing has no sliver problem (there are no new polygons) and no topology cleaning,
and it is reversible by integer division at decode.

### 5.4 Deferred to December: ecoregión × departamento

Written down so it is not re-derived. One packed territory id, from which every level falls out:

```
territory_id = ecoregion16 · 100000 + GEOCODE(departamento)      # max 1,694,021 — exact in int32
```

`GEOCODE` on the department layer is `provincia·1000 + departamento`, so **one painted layer gives
both political levels** and the province needs no second asset. Because the pieces are disjoint,
every coarser cut is a `group_by` on the finer table — no double counting, no re-export. With two
packed layers the masking rule of §4.3 bites again: keep the ecoregions as the single mask driver
and `unmask(0)` the departments, so a `departamento == 0` row means "inside an ecoregion, outside
the department layer" and is *visible* rather than silently dropped.

At that point the class code no longer fits one field: either the territory becomes the reducer's
second group field (their `.group().group()` shape) or the two are packed into one int64. Decide
then, with the December scope in hand.

**Provenance, for the record**: the 16 ecoregions are **Administración de Parques Nacionales**,
Burkart et al. 1999, and the 13-class layer is the published aggregation of the same; departments
and provinces are **IGN**. The platform publishes area numbers against whichever layer is registered
in Workspace (§11), so the registration and the statistics must name the same asset (§12).

---

## 6. Burnable: a col-3 legend decision

**Nobody in the network computes a burnable denominator.** Grepped the whole reference repo: no
`burnable`, no `quemable`. Every network statistic is an absolute area. **`% burned` is entirely
Argentina's own addition** — which is also why the denominator is the one piece we still compute
ourselves (§4.2). There is no spec to deviate from, but it must be *stated*, because a CSV carries
no metadata: this list lives in `statistics/legends.py`, next to the decode, and is named in the
export task description.

This table is the input to the modal layer: `BURNABLE` and `NON_BURN` in §4.2 are its two columns,
and "no observado" is in neither, which is what keeps it out of the mode and out of both sides of
every ratio.

"Burnable" is a property of the class, not a computation. Our col-2 remap
(`config/veg_fire_remap.csv`) is the anchor: in **every one of the 5 regions** it sends MapBiomas
classes **24, 25, 33, 34 → non-burnable** and **27 → non-observed**. Region-independent, so it
carries to col-3 unchanged.

| col-3 code | name (nivel 2) | verdict |
|---|---|---|
| 0, 27 | No observado | **excluded from numerator and denominator** |
| 22 | Áreas sin vegetación | non-burnable |
| 24 | Áreas urbanas | non-burnable |
| 25 | Otras áreas no vegetadas | non-burnable |
| 26, 33 | Cuerpos de agua / ríos, lagunas, lagos y océano | non-burnable |
| 34 | Hielo en superficie y nieve permanente | non-burnable |
| 1, 3, 4, 6 | Bosques | burnable |
| 9, 14, 15, 18, 19, 21, 36 | Agropecuario / silvicultura | burnable |
| 10, 11, 12, 63, 66, 73, 77 | Herbáceas, arbustales, turberas | burnable |

**22 and 26 had no precedent and were decided.** They do not appear in col-2 v8 at all, so our remap
never ruled on them. **Both are non-burnable** (Iván, 2026-09-11) — the bare-ground and water
families, where the col-2 remap puts their nearest equivalents.

**Verify the list against the data, once**: the decode must raise on any code present in the export
and absent from this table. A class that falls through into the decode default is a silent error.

---

## 7. Verification gates — run these before any number leaves the building

Two tables now, computed by two teams on two grids, joined on one id. Most of what can go wrong is
in that join.

| # | check | passes if |
|---|---|---|
| 1 | **The test rectangle** (§4.5) decodes to 13 ecoregions × {0,1} and nothing else. | Before anything national runs. |
| 2 | **Both sides key the same.** The toolkit's territory ids and our `ecoregion13` are the same 13 numbers with the same names. | This is the trap of §5.1 item 1 and it is silent: a mis-keyed join produces a plausible, wrong `%` for six regions. Check the names, not the count. |
| 3 | **Mode ties and always-no-observado pixels.** Count pixels where the burnable mode is a 50/50 tie, and pixels masked in every year. | Negligible. If not, swap the mode for `mean >= 0.5` and report the masked area separately (§4.2). |
| 4 | **Denominator ≥ numerator, every ecoregion × year.** | Always. A `%` over 100 means either a mis-keyed join (gate 2) or real burning on modally non-burnable pixels — both are findings, neither is acceptable unexplained (§4.4). |
| 5 | **Total area closes.** Σ our 26 rows ≈ the national area (279.27 Mha), minus whatever gate 3 reports as never-observed. | If it does not, the paint mask or the remap dropped classes, and every `%` is wrong. |
| 6 | **National annual burned, toolkit vs the object database.** | Matches the local object-derived area to well under 1 %. Not exactly: the products split objects per pixel by `abs_date`, the object table does not. This is the one check that the toolkit read *our* products correctly. |
| 7 | **Lattice.** Our export once pinned, once at `scale: 30`. | Difference is sub-pixel rounding, not systematic inflation. Also tells us how much of a difference their `scale: 30` numerator can carry (§3). |
| 8 | **Against the platform, in *staging*, before launch.** | Within the network's stated ~1 % mean difference. **Don't chase the 1 %.** Do chase anything much larger — wrong territory layer, wrong LULC year, a region missing from the mosaic. |

Gates 2, 4 and 5 are cheap and catch the failure modes that are invisible in the numbers themselves.
Do them first.

One failure mode is **ours to warn the network about**, not ours to fix: any statistic that reads
our burned rasters below native resolution over-reports (§3, and §13 item 7).

---

## 8. From the tables to the factsheet

[`10-factsheet_design.md`](10-factsheet_design.md) holds the message and the graphic design; this is
where each number comes from. **Three sources, and every figure must say which one it used**: the
toolkit's burned-area table (§4.1), our 13-row burnable table (§4.2), and the local fire counts
(§8.2).

### 8.1 The four analyses

| # (docs/10) | number | source |
|---|---|---|
| 1 | **mean annual burned proportion**, national and per ecoregion | `quemado` = the toolkit's burned area for that ecoregion × year; `quemable` = our constant burnable area for that ecoregion; `pct = quemado/quemable`, mean over years. The caption absolutes ("4.2 Mha de 100 Mha quemables") are those same two numbers. **The denominator does not vary by year** — §4.4. |
| 1b | the **per-LULC-class** variant | **not computable from these two tables** (§4.4): the toolkit's rows are burned-only, our denominator has no class dimension. It needs one more small export. Settle it before promising the panel. |
| 2 | **time series + trend** | the per-year `pct` series from analysis 1; GAM fitted locally in R (small `k`), summarised as the mean slope standardised by the series mean or sd. The "veces el año típico" variant is that series divided by its own mean. With a constant denominator this series is a pure fire signal — say so, it is the argument for the change. |
| 3 | **pirogram**, area half | the toolkit's rows grouped by month; per month the mean over years of that month's share of the year's burned area. Plot May→April so neither peak is cut — the national curve is bimodal. |
| 3 | **pirogram**, count half | **not from any GEE table** — §8.2. |
| 4 | **intra-annual shape, comparable across regions** | per ecoregion, each month's share of that region's whole-series burned area (sums to 100 %). Preferred source is the toolkit's table (pixels); the object-based version in `fire_counts_by_month.csv` is the fallback and the two do not close (§8.3). |

### 8.2 Fire counts come from the local polygons, and each fire is counted **once**

Counts are not a pixel statistic and never touch Earth Engine. Source: the local object database
(`objects-pred/`, `objects-raw/*_raster_metrics.csv`, the `.gpkg` geometries), filtered to the
deployed selection (`fire == 1 & area_ha >= 1`, docs/07 §1.1).

- **Calendar year and month, both from `date_median`.** The object database is stored by *fire*
  year, but a count is filed under the **calendar** year and month of its median date — so a whole
  fire lands in exactly one year and one month. `date_median` is the local CSV column; the same
  value is `date_med` on the uploaded FCs (docs/07 §13.2.1). **Everything the factsheet reports is
  calendar-year**, on every side (§8.3).
- **A calendar year therefore needs TWO fire-year files.** Fire-year `Y` (1 May Y → 30 Apr Y+1)
  feeds calendar years `Y` and `Y+1`, so no calendar year is complete until both its fire-years are
  read — the same trap as the step-07 scar build (docs/07). Read all 28 fire-years, assign the
  calendar year, then aggregate; never aggregate per file.
- **Territory = the region containing the object's CENTROID.** One fire, one ecoregion, counted
  once. Regional counts therefore **sum to the national count** — which is the point.
  `scripts/objects_region_tag.R` already writes this as `regions_<fy>_one.csv`.
- **The multi-tag rule is retired.** Counting a fire in every region it touches (the old
  `regions_<fy>_multi.csv`, and what docs/10 §3 used to ask for) makes regional counts exceed the
  national total and makes "fires per region" not a partition. Drop the `_multi` output rather than
  leaving both — a losing alternative left in the code is the next person's trap.
- **The predicate is point-in-polygon.** Centroids are points, so ask only *whether* they fall in a
  polygon, never for the intersection geometry: `terra::relate(centroids, regions, "intersects")`
  (or `sf::st_within`) — not `st_intersection`, which on 1.7 M polygons against complex ecoregion
  boundaries is hours of work for an answer nothing needs.
- Centroid, not largest-overlap: the two agree for every object that does not straddle a boundary,
  which is nearly all of them.

Outputs: `data/statistics/fire_counts_by_month.csv` (ecoregion × **calendar year** × month) and
`fire_region_summary.csv` (fires/year, area/year, size quantiles, density per 10,000 km²). These are
**threshold-agnostic** — the tagging runs on every object, `fire == 0` included, and the filter is a
`filter()` on the output — but they must be **regenerated under the final object selection**, since
the selection changed after the existing CSVs were written ([`ROADMAP.md`](../../ROADMAP.md)).

### 8.3 Everything is calendar-year — and the three divergences to state in the footnote

**Every number the factsheet reports is calendar-year**: the toolkit's burned area, our denominator
and the fire counts. The fire-year (1 May → 30 Apr) is how the *mapping* is organised (docs/07), not
how anything is reported. What differs is *how* each side files a fire into a year and a month:

1. **Per pixel vs per object.** The rasters assign year and month **per pixel** from `abs_date`; the
   counts assign **per object** from `date_median`. So a fire straddling 31 December is split
   between two calendar years in the area numbers and filed whole in one of them in the counts.
2. **"Area burned in month M"** is a pixel sum on the toolkit's side and a whole-object assignment
   on the object side. The two curves have the same shape and will not have the same values.
3. **The denominator is a 27-year mode**, not that year's burnable area (§4.4).

Acceptable — say all three out loud, and always say which side a number came from.

### 8.4 What these tables cannot answer

- **Anything per fire** — number of fires, size distribution, median size, density: the object
  database (§8.2).
- **Scar size crossed with land cover or month**: the `annual_burned_scar_size_range` product has no
  LULC dimension.
- **Fire-year totals**, directly — but the toolkit's table carries month *and* year, so a fire-year
  total is recoverable as May..Dec of *y* plus Jan..Apr of *y+1*. That is a legitimate aggregation of the
  published calendar-year products and should be labelled as such.
- **Error-adjusted area.** That is [`11-validation.md`](11-validation.md)'s design-based estimate,
  and it is not ready for September.

---

## 9. The other five network tables (publication, not analysis)

The network's own stage-5 deliverable: the published products read **as they are**, with the
**same-year** LULC their reference encoding specifies. The first of the six is what §4.1 already
gives us; the rest are publication artefacts that no factsheet number depends on. Spec from
`2-Statistics/2-ColAnual-Products-Reference/`; decode strategies copied from
`peru/datasets/fuego_col1.js`.

| reference script | image | computes |
|---|---|---|
| `toDrive-area-annual-burned-coverage` | `…_annual_burned_coverage` | burned area per year × LULC × territory |
| `toDrive-area-monthly-burned-coverage` | `…_monthly_burned_coverage` | idem per month (`month·100 + lulc`) |
| `toDrive-area-accumulated-burned-coverage` | `…_accumulated_burned_coverage` | accumulated burned area per LULC × territory |
| `toDrive-area-frequency-burned-coverage` | `…_frequency_burned_coverage` | area per burn frequency × LULC × territory |
| `toDrive-area-scar-size` | `…_annual_burned_scar_size_range` | area per scar-size range × territory |
| `toDrive-area-year-last-fire` | `…_year_last_fire` | area per year of last fire × territory |

Asset ids come from `utils/constants.py::product_name()` — one source of truth, so a version bump is
one edit.

**These are blocked on the products, and the products are now split between us and Brazil.** As of
14 Sep **Vera is exporting the remaining fire subproducts** (07d) on their side, and **four have
landed**: `annual_burned_v2`, `monthly_burned_v2`, `annual_burned_coverage_v2`,
`monthly_burned_coverage_v2` — 27 bands each, verified against the assets. **The exception is the scar-size side**: `annual_burned_scar_id`,
`annual_burned_scar_area` and `annual_burned_scar_size_range` (07c) are gated on **Iván's manual
ingest of the 27 calendar-scar packages**, which nobody else can do for us, so `toDrive-area-scar-size`
cannot run until that lands ([`ROADMAP.md`](../../ROADMAP.md), "After").

**These tables and the factsheet's numbers cannot agree, by construction**: the published products
cross **same-year** land cover while our statistics CSV crosses the **previous** year (§4.1.1), the
denominator is a 27-year mode rather than a per-year area (§4.4), and their rows are burned-only
while ours is space-filling. Say so in the CSV hand-off.
The `%` metric is **never** computed from these — they are absolute areas for the platform, which is
all the network's six CSVs have ever contained.

`2-Statistics/1-Burned_area_products/` additionally computes the same areas for **FireCCI, GABAM and
MCD64A1** — the inter-comparison used in launch materials. Optional, but it is the standard way to
show a new collection is sane, and Argentina has no previous collection to compare against.

---

# Part B — stage 6: publication

## 10. Public assets

| Destination | Script | What it is |
|---|---|---|
| **Public GEE assets** — `projects/mapbiomas-public/assets/argentina/fire/collection1/` | `ToPublish/3-toAsset-Public` | `copyAsset` → `setAssetAcl({all_users_can_read: true})` → `setAssetProperties({data_type, band_format, version})` |
| **Cloud Storage COGs** — `gs://shared-development-storage/COLLECTIONS/ARGENTINA/FIRE/COLLECTION1/temp/…` | `ToPublish/2-toBucket-subproducts` | one COG per band, `byte` (or `uint16` for `year_last_fire`) |

**The platform ingests the public GEE assets** — the Workspace subtheme form's key field is a
`GEE Asset ID` pointing at `mapbiomas-public`, with `data_type`/`band_format`/`version` telling it
how to read the bands. *Inference:* the bucket COGs serve the download page.

**Brazil owns this step**, so our job is to have the `FINAL_PRODUCTS` assets correct and named
exactly right, and to check the copies afterwards. ⚠️ **Re-exporting `FINAL_PRODUCTS` changes
nothing the public sees until Brazil re-copies**, and the COGs need regenerating alongside (§13).

## 11. Workspace catastro

<https://workspace.mapbiomas.org/modules> is MapBiomas's internal metadata registry — where you
declare which GEE asset is a product, how to colour it, and which territories to aggregate by.
**Nothing appears on the platform until it is registered here.** Three registrations:

1. **Subthemes**, one per published product: `Team` General Team (Argentina), `Type` Classification
   Multiband Image, `Group` Classification, `Territory category` POLITICAL_LEVEL_1, `Territory`
   [Argentina], **`GEE Asset ID`** (§10), `Subtheme name`, `Legend`. Names in use across countries:
   *Annual Burned*, *Monthly Burned*, *Annual Burned Coverage*, *Annual Burned Natural and Anthropic
   Use*, *Scar Size*, *Total Burned* — **match an existing country rather than inventing ours**.
2. **Legends** — class ↔ pixel value ↔ colour: annual = 1 class; monthly = 12; scar size = the
   two-level scheme (docs/08 §5.4). ⚠️ **Take values and hex colours from
   `Mapbiomas-Fogo-Legenda-Col4.xlsx`, never from screenshots**, and make sure the registered
   scar-size ranges match the ranges we actually rasterized — same pixel values, different
   thresholds is a silent, invisible error.
3. **Territorial layers** — the §5 assets, used by the territory selector and the platform's own
   statistics. **Ours.**

Brazil supports the registration; we supply the values and verify.

---

# Part C — launch

## 12. Launch-preparation track (parallel, non-code)

| # | Item | Notes |
|---|---|---|
| 1 | **Destacados** + infographic | Brazil provides `Fact_Fogo_colecao4.pdf` and a template |
| 2 | **Validation of the data in *staging*** | our sign-off, cross-checked against §4–§7 |
| 3 | **Website materials**: ATBD, methodology page, informative note | Peru's and Paraguay's ATBDs are the format model |
| 4 | **Downloads page** + a *códigos de la leyenda* page | Brazil supplies the URLs (§10) |
| 5 | **Launch event** | with communications |
| 6 | **Press release** + dissemination | |

Also from the guide: the brand manual + MapBiomas Fuego logos, and Brazil's launch checklist
(`Checklist de demandas - Col.4 Fogo`) — worth copying as our own tracking sheet.

> **Argentina's ATBD is the one document nobody else can write for us.** Our method differs from
> every other country in the network (docs/08 §3), so it cannot be adapted mechanically from
> Brazil's — it has to describe the burn-probability → SNIC → object-model chain, including the
> non-calendar fire-year and how it is re-partitioned into calendar years (docs/08 §6.2).

Both stages end with **our** review: *"Antes de avanzar a la siguiente etapa, cada producto debe ser
validado por el equipo del país correspondiente."* Brazil owns the public-asset copy and supports
Workspace; **we** own the territorial layers, all validation and every country-specific material.

---

## 13. Open questions, and what to ask Brazil

Actionable work is on [`ROADMAP.md`](../../ROADMAP.md); these are the questions it waits on.

1. **Which ecoregion layer does the platform's territory registration expect** — a 16-class asset
   or the 13-class aggregation the factsheet reports? Our export covers both (§5.2), but Workspace
   registers *one asset*, and the registration and the statistics must name the same one. A question
   for whoever built the `Stats-Arg_*` family — probably the Argentina land-cover team, not Brazil.
2. **The `Stats-Arg_*` names are Latin-1 damaged and there are duplicate ecoregion assets** (§5.1).
   We work around both for September; ask whether the source assets should be repaired and which of
   the two 16-class layers is canonical, before December needs the departments.
3. **Would Brazil take the `crsTransform` patch upstream** in `core/calculate.js` (optional
   `config.crs`/`config.crsTransform`, falling back to `scale`)? Argentina is not the only country
   whose products are off a `scale: 30` EPSG:4326 grid. We now hand them a *diff against their JS*,
   not a branch — our implementation is Python and lives here.
4. **Do they need our CSVs at all, and in what shape?** We export to Drive, not to
   `gs://mapbiomas-fire/data-container/stats/…`. If something on their side consumes those files
   automatically, we need the column spec (`Área ha`, `Ano`, `Nivel 0/1/2`) and a hand-off path.
5. **Last date** we can hand them updated assets and still have them on the platform for 24 Sep.
   That date, not the 24th, is the real deadline.
6. **Anything already generated downstream of our assets** that a re-export silently invalidates —
   loaded statistics, the Cloud-Storage COGs behind the downloads page: who regenerates them, by
   when?
7. **Coarse reads of sparse burned rasters over-report**, network-wide (+14 % at 90 m, +36 % at
   120 m). Worth a warning to every country, not just a fix on our side.
8. **Subtheme naming** (§11) — mirror Peru's or Paraguay's exactly.
9. **Whether to run the FireCCI / GABAM / MCD64A1 comparison** (§9). Recommended: yes — the only
   external sanity check available for a first collection.

---

## 14. Decisions on record

| # | decision | who / when |
|---|---|---|
| 1 | **The burned-area table is the network's toolkit's**, run with our ecoregion layer registered in it; we compute **only the burnable denominator** (§4). No JS fork, no hand-written reducer; both `workflow/11-*.py` are retired | Iván, 2026-09-11 / 09-14 |
| 2 | Results are exported to **Google Drive** (Insync-synced into `data/statistics/`), not to the network's GCS bucket | Iván, 2026-09-14 |
| 3 | **September computes at ecoregion only.** Departamento and provincia are December (Bariloche) work | Iván, 2026-09-14 |
| 4 | The denominator is a **constant burnable layer**: the **mode over 1998–2024** of the col-3 burnable classes (§6), reduced as `ecoregion13·10 + burnable` on the pinned grid — the app's programming strategy, our one export | Iván, 2026-09-14 |
| 5 | Fire counts assign each fire to **one** territory, by **centroid**; the count-in-every-region rule is retired | Iván, 2026-09-14 |
| 6 | The lattice is pinned (`crs` + `crsTransform`), never `scale: 30` | Iván, 2026-09-11 |
| 7 | Territories are **packed painted vectors**, never intersected ones | Iván, 2026-09-11 |
| 8 | Everything crosses **col-3 (`PRODUCT_LULC`)**, and the burned × LULC cross reads the **PREVIOUS** year — implemented in our copy of the toolkit (§4.1.1). The published `*_coverage` products keep the network's **same-year** encoding, so the two disagree by construction and every figure says which it used. Asking Vera to make previous-year the Argentina default upstream | Iván, 2026-09-11 / 09-14 |
| 9 | Burnable is defined on **col-3 classes** (§6), never on `veg_fire` — the modal layer that was cancelled in September was the `veg_fire` one; §4.2's is a different layer. Col-3 **22 and 26 are non-burnable** | Iván, 2026-09-11 / 09-14 |
| 10 | Ecoregions are **Burkart et al. 1999**, and **both sides run on the 13-class vector** `ARG-Political_Level_2-13Ecorregiones_3857` — the toolkit's territory and ours must key identically. The 16-class layer and the exact 16 → 13 crosswalk stay for December (§5.2) | Iván, 2026-09-10 / 09-14 |
| 11 | Territorial layers are **existing assets, painted from the VECTORS** — never the `_r` rasters, whose ids do not match their own vectors' `GEOCODE` (§5.1 trap 1) | Iván, 2026-09-11 / 09-14 |
| 12 | The two object exclusion rules and their thresholds are **FINAL** (docs/07 §1.1) — not a parameter these statistics may vary | Iván + team, 2026-09-11 |
| 13 | The September re-export is **`_v2`** on our tree; Brazil copies it over the public asset, so no public id changes | Iván + Brazil, 2026-09-11 |
| 14 | **Brazil helps export the remaining fire subproducts** (07d); the **scar-size side stays blocked** on the manual scar ingest, which is ours alone (§9) | Iván + Brazil, 2026-09-14 |
| 15 | Statistics on our own **fire-year objects** (per-event size distributions, season-spanning fires) are worth a separate, clearly-unofficial output — but not before 24 September | Iván, 2026-09-11 |
