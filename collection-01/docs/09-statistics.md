# 09 — Statistics (stage 5), publication and launch (stage 6)

Everything that happens **after** the GEE assets exist and **before** the public launch. The assets
themselves are [`07-vector_to_raster.md`](07-vector_to_raster.md) (what we build) and
[`08-postprocessing.md`](08-postprocessing.md) (what the network expects); the launch guide, the
read-only reference repo and the legend spreadsheet are catalogued in **docs/08 §1** and not
repeated here. The factsheet's *content* — which graphic says what — is
[`10-factsheet_design.md`](10-factsheet_design.md); this file is where each of its **numbers** comes
from. **[`ROADMAP.md`](../../ROADMAP.md) is the *when*; this file is the *how*.**

**Four things that are settled, so nobody re-opens them:**

- **We do not write a reducer, and we do not fork their JavaScript.** The *method* is the network's
  `2-Statistics/toolkit/v03/` (§2); the *code* is a Python implementation of it in
  `collection-01/statistics/` (§1). The per-year hand-written 30 m reductions
  (`workflow/11-burnable_area.py`, `workflow/11-burned_area_stats.py`) and the fixed
  modal-`veg_fire` layer are **dead** — those two scripts survive only until the route is verified
  end to end, then they are deleted ([`ROADMAP.md`](../../ROADMAP.md)).
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
  d1_export.py      build the packed D1 image and launch the Drive export (§4)
  decode.py         raw CSV -> tidy table: year, eco16, eco13, month, LULC, burnable, area_ha
  legends.py        col-3 legend nivel 0/1/2, the burnable list (§6), the 16->13 crosswalk and
                    the 16 ecoregion names as literals (§5.1-§5.2)
  territories.py    paint the territorial vectors on the pinned grid (§5)
  fire_counts.R     fire counts off the LOCAL object database (§8.2)
  factsheet_tables.R  the four factsheet analyses, from the tidy table + the counts (§8)
  factsheet_plots.R   the plots; content plan in docs/10-factsheet_design.md

collection-01/data/statistics/     ALL statistics data — raw export and derived tables
  d1_ecoregion_raw.csv     exactly what GEE wrote: year, code, sum
  d1_ecoregion.csv         the decoded tidy table — the input to every factsheet number
  fire_counts_by_month.csv per ecoregion x fire-year x month (counts, from objects)
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

- One territorial cut, so **one export task and one table** (§4), not a family.
- The territory id is **packed into the class code** (§4.1) instead of being a second group field,
  which is what makes one integer per pixel enough.
- The `ecoregion16 · 100000 + GEOCODE(departamento)` packing designed for the master cut is
  **deferred, not cancelled** — it is written down in §5.4 so December does not re-derive it.
- Anything the platform's territory selector needs at province level (§11) is a *registration*
  question, not a statistics one, and is unaffected.

The factsheet reports the **13-class** ecoregions; the export runs on the **16-class** layer because
16 → 13 is an exact aggregation (§5.2), so one table serves both.

---

## 2. The method is theirs, and why it is fast

The toolkit is `2-Statistics/toolkit/v03/` in the read-only reference repo
(`/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`). Its reducer is *identical* to the one we
benchmarked at 8 h/year:

```js
// core/calculate.js
var reducer = ee.Reducer.sum().group(1, 'class').group(1, 'territory');
```

There is no trick in the reducer. It is fast because of what is *around* it, and those are the five
things the Python implementation must copy:

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

**Where we diverge from their `core/`, and why.** Mark each of these in the code, because the first
is one we owe back to Brazil (§13):

| divergence | reason |
|---|---|
| `crs` + `crsTransform` instead of `scale: 30` | §3 — every raster here is on one lattice |
| Python instead of JavaScript | the analysis is already Python + R in this repo, the constants already exist in `utils/constants.py`, and a Code Editor round-trip is the wrong dependency in this calendar |
| `Export.table.toDrive` instead of GCS | we have no write access to `gs://mapbiomas-fire/…` and do not need one; Drive syncs straight into the store (§4.4) |
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

## 4. D1 — the big table: one packed integer, one grouped sum

This is the deliverable of stage 5 and the input to every factsheet number. **One row per
(year, class code)**, one area value.

### 4.1 The encoding

A row is an area; the class code says what that area *is*: burned or not, in which month, on which
land cover of the previous year, in which ecoregion.

```
code = ecoregion16 · 10⁴  +  month · 10²  +  lulc_col3(calendar_year − 1)
```

| field | range | digits |
|---|---|---|
| `ecoregion16` | 1..16 (`GEOCODE`) | 2 |
| `month` | **0**..12, where **0 = did not burn** | 2 |
| `lulc` | col-3 codes, 0..77 | 2 |

Maximum code `16·10⁴ + 12·10² + 77 = 161,277`.

**Therefore int32, not uint16.** uint16 caps at 65,535 and six decimal digits do not fit. It could
be forced to fit by bit-packing (`eco<<11 | month<<7 | lulc`, max 34,381) — we decline: the image is
computed on the fly and never stored, so the dtype buys nothing, while a decimal code is readable
straight off the raw CSV (`161277` *is* eco 16, month 12, class 77) and that is worth real money the
first time a number looks wrong.

**The burned flag is not encoded**, because `month == 0` already *is* "did not burn". Adding a
separate 0/1 digit costs a digit and creates a field that can disagree with the month. `burned` is
`month >= 1`, everywhere, and it is derived at decode.

**Year is not in the code either.** It is a column, written per reduction (§4.3) — 27 more digits'
worth of packing for a field the reducer can carry for free.

### 4.2 The image

```python
# GEOCODE is a STRING on this asset (§5.1) — cast, or every id paints as 0
eco16 = (ee.FeatureCollection(C.ECOREGIONS16)          # ARG-Political_Level_2-16Ecorregiones_3857
         .map(lambda f: f.set("GEOCODE", ee.Number.parse(f.get("GEOCODE")))))
eco   = ee.Image().paint(eco16, "GEOCODE")             # masked outside Argentina: the mask driver

def code(year):
    mob  = (ee.Image(ee.ImageCollection(C.MONTH_OF_BURN_COL)
                     .filter(ee.Filter.eq("year", year)).first())
            .select(C.MONTH_OF_BURN_BAND).unmask(0))          # 0 = did not burn
    lulc = ee.Image(C.PRODUCT_LULC).select(f"classification_{year - 1}").unmask(0)
    return eco.multiply(10000).add(mob.multiply(100)).add(lulc).toInt().rename("code")
```

`C.ECOREGIONS16` does not exist yet — **add the two ecoregion asset ids to
`utils/constants.py`** (16- and 13-class, §5.1) in the same pass. Everything else the export needs
is already there: `MONTH_OF_BURN_COL`, `MONTH_OF_BURN_BAND`, `PRODUCT_LULC`, `ARG_BUFFER_FC`,
`SNIC_CRS`, `SNIC_TRANSFORM`. That one file stays the single source of truth — do not retype an
asset id into `statistics/`.

**`unmask(0)` on the month band is load-bearing.** It makes the image space-filling, so *unburned*
pixels are reported too. That single decision is what turns one table into numerator **and**
denominator:

| question | rows to sum |
|---|---|
| burned area, year × ecoregion | `month >= 1`, burnable LULC |
| burned area × land cover | idem, grouped by `Nivel 1/2` |
| burned area × month (pirogram) | idem, grouped by `month` |
| **burnable area** (the denominator) | **all** `month` 0..12, burnable LULC |
| burned on non-burnable (QC) | `month >= 1`, non-burnable LULC |
| no observado (excluded everywhere) | `lulc` in {0, 27} |

**Exactly one layer drives the mask** — the ecoregions, which tile the country. `add()` propagates
masks, so if two layers were masked, any pixel missing from either would drop silently out of the
reduction. Hence `unmask(0)` on both month and LULC, and `paint` (masked) on the ecoregions.

**Why the *previous* year's land cover.** A fire consumes the vegetation that was there *before* it
burned; the same-year class of a burned pixel is partly a *consequence* of the fire. And it is what
makes `%` coherent: numerator and denominator read the same layer, so "% of grassland that burned"
is a ratio of two areas of the same thing. Calendar years are 1999..2025, so the LULC bands needed
are 1998..2024 — all inside col-3's `classification_1985..2025`, no forward duplication, no cap.

**Why col-3 and not our `veg_fire`.** Col-3 is the best current estimate of land cover, it is the
legend every reader and every other MapBiomas product uses, and its non-burnable classes are
directly identifiable — so the denominator needs no extra asset at all (§6). The cost is that the
denominator is no longer *exactly* the layer the SNIC candidate set was built from (col-2 v8
reclassed to `veg_fire`), so a pixel can be mapped as burned and be non-burnable under col-3. That
residual is measurable in this same table, is excluded from both numerator and denominator so it
can never produce a `%` above 100, and gets **reported once** (gate 4, §7).

### 4.3 The reduction and the export

```python
area    = ee.Image.pixelArea().divide(1e4)                      # hectares
reducer = ee.Reducer.sum().group(groupField=1, groupName="code")

def rows(year):
    g = area.addBands(code(year)).reduceRegion(
            reducer=reducer, geometry=BOUNDS,                   # a RECTANGLE, never the multipolygon
            crs=C.SNIC_CRS, crsTransform=C.SNIC_TRANSFORM,
            maxPixels=1e12)
    return ee.List(g.get("groups")).map(
        lambda d: ee.Feature(None, ee.Dictionary(d).set("year", year)))

fc = ee.FeatureCollection(ee.List([rows(y) for y in YEARS]).flatten())
```

- **Hectares, converted in GEE**, so the CSV needs no unit convention downstream.
- `BOUNDS` is `ee.FeatureCollection(C.ARG_BUFFER_FC).geometry().bounds()`. That rectangle is
  ~74 k × 124 k ≈ **9.2 × 10⁹ px**, so `maxPixels=1e12` has two orders of headroom.
- The client-side `for y in YEARS` is the toolkit's "all years in one task" — 27 reductions, one
  export, one CSV.
- **Namespace the task `description`** (`arg09_d1_eco_…`). The compute project is shared with the
  whole network and a generic description collides with another country's (docs/07 §12.7).
- `selectors=["year", "code", "sum"]` — pin the columns, do not let GEE choose them.

Expected size: 27 years × 16 ecoregions × 13 months × ~25 classes = **140 k rows** upper bound, most
combinations empty. A few MB. If it ever is not, the problem is not the table.

> **Escape hatch if the reduction is slow** — it should not be; it is two stored byte reads, a
> multiply and an add on one lattice, i.e. exactly Brazil's shape. Materialise the 27 code bands as
> **one int32 asset** with a pixel-wise `Export.image.toAsset` (a pixel-wise export is not a
> reduction and is cheap) and reduce that. **Do not go back to a hand-written per-year reducer.**

### 4.4 Drive, and which account

Output goes to **Google Drive, not Cloud Storage** — we have no write access to the network's
bucket and do not need one. Export with `folder=` set to the Drive folder Insync syncs into the
store, so the CSV appears under `collection-01/data/statistics/` with no manual download (the
`objects-raw` handoff of step 04 is the same mechanism, `C.SNIC_DRIVE_FOLDER`).

**That Drive belongs to the `ivanbarbera@comahue-conicet.gob.ar` account**, so the export must be
submitted as that account — pass the credentials explicitly (`--credentials` + `--project`, the
`workflow/07-burned_area_polygons.py::initialize()` pattern) rather than swapping the credentials
file. That account is registered under the `mapbiomas-argentina` compute project, and its task queue
is its own, which is a second reason to use it.

### 4.5 Test on a rectangle first

Before the national launch, run the identical code with `BOUNDS` replaced by a small rectangle
inside Argentina (one that contains known fire — a Chaco or Pampa box). It returns in seconds and it
catches every structural error the national run would take an hour to reveal: a wrong band name, a
mask that ate the country, a code that decodes to an impossible class, an empty `groups` list.
`d1_export.py` must carry that as a flag, not as a commented-out block.

---

## 5. The territorial layer

Two consumers: the statistics (as a painted id raster) and the **platform's territory selector** (as
a registered Workspace layer, §11).

### 5.1 The layers exist — and two of them are traps

**Verified 2026-09-11 in the asset browser, and re-checked against the assets themselves
2026-09-14.** A complete, purpose-built territorial family is already in
`ANCILLARY_DATA/VECTOR/ARG/`, carrying MapBiomas's own schema (`CATEG_ID`, `GEOCODE`, `LEVEL_1..3`,
`NAME_STD`, `SOURCE`, `VERSION`):

| asset | n | `GEOCODE` | names | notes |
|---|---|---|---|---|
| `ARG-Political_Level_2-16Ecorregiones_3857` | **16** ecorregiones | 1..16, **as STRINGS** | `LEVEL_2`, clean UTF-8 | **what we paint** |
| `Stats-Arg_ecorregions` | **16** ecorregiones | 1..16, numbers | `LEVEL_2`, **Latin-1 damaged** | same ids, same regions — verified identical |
| `ARG-Political_Level_2-13Ecorregiones_3857` | **13** ecorregiones | 1..13 | clean UTF-8 | the aggregation (§5.2) |
| `Stats-Arg_political_level_3_v` | **528** departamentos | INDEC 5-digit | `LEVEL_3` depto, **`LEVEL_2` provincia** | December (§5.4) |
| `Stats-Arg_political_level_2_v` | **24** provincias | 2..94 | `LEVEL_2` | December (§5.4) |

**⚠️ Two traps here, both measured on 2026-09-14:**

1. **There are two 16-class ecoregion assets and they are not interchangeable.** The id → region
   mapping is *identical* in both, but `Stats-Arg_ecorregions` carries Latin-1 bytes stored as UTF-8
   (`Esteros del Iber<?>`, `Bosques Patag<?>nicos`, `Administraci<?>n de Parques Nacionales`) while
   the `_3857` twin is clean. **Paint the `_3857` one.** The same damage is in
   `Stats-Arg_political_level_*` and will matter again in December — never let it reach a CSV a
   designer reads.
2. **`GEOCODE` on `ARG-Political_Level_2-16Ecorregiones_3857` is a STRING**, so
   `ee.Image().paint(fc, 'GEOCODE')` does not do what it looks like. Cast first:
   `fc.map(lambda f: f.set('GEOCODE', ee.Number.parse(f.get('GEOCODE'))))`. On
   `Stats-Arg_ecorregions` it is already a number — which is exactly the kind of difference that
   makes an export succeed and decode to nonsense.

Names go in `statistics/legends.py` as a 16-entry literal, copied from the clean asset (the list is
§5.2's table), so the decode never depends on reading a vector.

Each layer has a raster twin in `…RASTER/ARG/`, all **EPSG:3857 at 30 m** — a different grid from
ours. **Paint the vectors, not the `_r` rasters**: reading one inside a reduction pinned to
`SNIC_TRANSFORM` reprojects it. For an integer category band that is nearest-neighbour, so no code
is ever invented, but boundary pixels shift by up to half a pixel for no benefit. Keep the rasters
as an independent cross-check, not as the input.

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

**Therefore export on 16.** The 13-class figures the factsheet wants are a `group_by` on this
crosswalk at decode time, and the finer split (Chaco Húmedo vs Chaco Seco, the two Montes) is there
for free if anyone asks. Exporting the 13-class layer instead would throw that away and save
nothing.

### 5.3 Why packing, not intersecting

Brazil packs painted layers arithmetically; Paraguay and Bolivia pre-intersect a vector. **We
pack** — into the class code itself (§4.1) while there is one cut, into a territory id when there
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
packed layers the masking rule of §4.2 bites again: keep the ecoregions as the single mask driver
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
Argentina's own addition**, so there is no spec to deviate from — but it must be *stated*, because a
CSV carries no metadata: the class list lives in `statistics/legends.py`, next to the decode, and is
named in the export task description.

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

| # | check | passes if |
|---|---|---|
| 1 | **The test rectangle** (§4.5) decodes to sane classes, months 0..12 and one ecoregion. | Before anything national runs. |
| 2 | **Lattice.** One year, run once pinned and once with `scale: 30`. | Difference is sub-pixel rounding, not systematic inflation. A large gap means §3's phase assumption is wrong. |
| 3 | **National annual burned, D1 vs the object database.** Sum `month >= 1` over all ecoregions per calendar year. | Matches the local object-derived area to well under 1 %. Not exactly: the products split objects per pixel by `abs_date`, the object table does not. |
| 4 | **Burned on non-burnable.** | Small, and *reported*. This is the price of col-3 instead of `veg_fire` (§4.2) and it must be a stated number, not a discovery. |
| 5 | **Every ecoregion present, every year.** | 16 ids × 27 years all appear. A missing one means a paint/mask failure, not a region that did not burn — unburned still has `month == 0` rows. |
| 6 | **Total area closes.** Σ all rows for one year ≈ the national burnable+non-burnable+no-observado area (279.27 Mha for the whole country). | The `unmask(0)` space-filling property is what this tests; if it fails, every `%` is wrong. |
| 7 | **Against the platform, in *staging*, before launch.** | Within the network's stated ~1 % mean difference. **Don't chase the 1 %.** Do chase anything much larger — wrong territory layer, wrong LULC year, a region missing from the mosaic. |

Gates 1, 2 and 6 are cheap and catch the failure modes that are invisible in the numbers themselves.
Do them first.

One failure mode is **ours to warn the network about**, not ours to fix: any statistic that reads
our burned rasters below native resolution over-reports (§3, and §13 item 7).

---

## 8. From the tables to the factsheet

[`10-factsheet_design.md`](10-factsheet_design.md) holds the message and the graphic design; this is
where each number comes from. Everything is a `group_by` on the tidy D1 table **except the fire
counts**.

### 8.1 The four analyses

| # (docs/10) | number | source |
|---|---|---|
| 1 | **mean annual burned proportion**, national and per ecoregion | `quemado = Σ(month >= 1, burnable)`, `quemable = Σ(all months, burnable)`, `pct = quemado/quemable`, mean over years. The caption absolutes ("4.2 Mha de 100 Mha quemables") are the same two sums. The per-LULC version is the same rows grouped by `Nivel 1/2`. |
| 2 | **time series + trend** | the per-year `pct` series from analysis 1; GAM fitted locally in R (small `k`), summarised as the mean slope standardised by the series mean or sd. The "veces el año típico" variant is that series divided by its own mean. Nothing new is exported. |
| 3 | **pirogram**, area half | `month >= 1` rows grouped by `month`; per month the mean over years of that month's share of the year's burned area. Plot May→April so neither peak is cut — the national curve is bimodal. |
| 3 | **pirogram**, count half | **not from this table** — §8.2. |
| 4 | **intra-annual shape, comparable across regions** | per ecoregion, each month's share of that region's whole-series burned area (sums to 100 %). Preferred source is D1 (pixels); the object-based version in `fire_counts_by_month.csv` is the fallback and the two do not close (§8.3). |

### 8.2 Fire counts come from the local polygons, and each fire is counted **once**

Counts are not a pixel statistic and never touch Earth Engine. Source: the local object database
(`objects-pred/`, `objects-raw/*_raster_metrics.csv`, the `.gpkg` geometries), filtered to the
deployed selection (`fire == 1 & area_ha >= 1`, docs/07 §1.1).

- **Fire-year, not calendar year** — the object database is fire-year throughout.
- **Month = the month of `date_median`** (the local CSV column; the same value is `date_med` on the
  uploaded FCs, docs/07 §13.2.1). So a whole fire's count falls in one month.
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

Outputs: `data/statistics/fire_counts_by_month.csv` (ecoregion × fire-year × month) and
`fire_region_summary.csv` (fires/year, area/year, size quantiles, density per 10,000 km²). These are
**threshold-agnostic** — the tagging runs on every object, `fire == 0` included, and the filter is a
`filter()` on the output — but they must be **regenerated under the final object selection**, since
the selection changed after the existing CSVs were written ([`ROADMAP.md`](../../ROADMAP.md)).

### 8.3 The two divergences to state in the footnote

The rasters assign calendar year and month **per pixel** from `abs_date`; the object/count side
assigns **per object** from `date_median`. So (i) a fire straddling 31 December is split in the
rasters and not in the counts, and (ii) "area burned in month M" is a pixel sum in D1 and a
whole-object assignment in the counts. Acceptable — say it out loud, and always say which side a
number came from.

### 8.4 What these tables cannot answer

- **Anything per fire** — number of fires, size distribution, median size, density: the object
  database (§8.2).
- **Scar size crossed with land cover or month**: the `annual_burned_scar_size_range` product has no
  LULC dimension.
- **Fire-year totals**, directly — but D1 carries month *and* year, so a fire-year total is
  recoverable as May..Dec of *y* plus Jan..Apr of *y+1*. That is a legitimate aggregation of the
  published calendar-year products and should be labelled as such.
- **Error-adjusted area.** That is [`11-validation.md`](11-validation.md)'s design-based estimate,
  and it is not ready for September.

---

## 9. D2 — the six network-spec tables (publication, not analysis)

The network's own stage-5 deliverable: the published products read **as they are**, with the
**same-year** LULC their reference encoding specifies. Spec from
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
one edit. **These are blocked on 07c/07d** (the scar rasters and the nine subproducts) and are
therefore *after* the factsheet in [`ROADMAP.md`](../../ROADMAP.md).

**D1 and D2 cannot agree, by construction** — previous-year vs same-year LULC. Say so in the CSV
hand-off. The `%` metric is **only ever** computed from D1; D2 is absolute areas for the platform,
which is all the network's six CSVs have ever contained.

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
| 1 | The **method** is the network's `toolkit/v03`; the **code** is ours, a Python implementation in `collection-01/statistics/`. No JS fork, no hand-written reducer; both `workflow/11-*.py` are retired | Iván, 2026-09-11 / 09-14 |
| 2 | Results are exported to **Google Drive** (Insync-synced into `data/statistics/`), not to the network's GCS bucket | Iván, 2026-09-14 |
| 3 | **September computes at ecoregion only.** Departamento and provincia are December (Bariloche) work | Iván, 2026-09-14 |
| 4 | D1 packs **ecoregion, month and previous-year LULC into one int32 code**, decimal, decoded locally; the burned flag is not encoded because `month == 0` is "did not burn" | Iván, 2026-09-14 |
| 5 | Fire counts assign each fire to **one** territory, by **centroid**; the count-in-every-region rule is retired | Iván, 2026-09-14 |
| 6 | The lattice is pinned (`crs` + `crsTransform`), never `scale: 30` | Iván, 2026-09-11 |
| 7 | Territories are **packed painted vectors**, never intersected ones | Iván, 2026-09-11 |
| 8 | The vegetation cross uses **col-3 (`PRODUCT_LULC`), previous year**, for D1; the published `*_coverage` products keep the network's same-year encoding | Iván, 2026-09-11 |
| 9 | Burnable is defined on col-3 classes (§6); no separate burnable asset, no fixed modal `veg_fire` layer. Col-3 **22 and 26 are non-burnable** | Iván, 2026-09-11 |
| 10 | Ecoregions are **Burkart et al. 1999**: the factsheet reports the **13-class** aggregation, the export runs on the **16-class** layer, since 16 → 13 is exact | Iván, 2026-09-10 / 09-11 |
| 11 | The territorial layers are the existing **`Stats-Arg_*` family**, painted from the vectors — not new assets, not the `_r` rasters | Iván, 2026-09-11 |
| 12 | The two object exclusion rules and their thresholds are **FINAL** (docs/07 §1.1) — not a parameter these statistics may vary | Iván + team, 2026-09-11 |
| 13 | The September re-export is **`_v2`** on our tree; Brazil copies it over the public asset, so no public id changes | Iván + Brazil, 2026-09-11 |
| 14 | Statistics on our own **fire-year objects** (per-event size distributions, season-spanning fires) are worth a separate, clearly-unofficial output — but not before 24 September | Iván, 2026-09-11 |
