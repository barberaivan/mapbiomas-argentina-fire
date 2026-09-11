# 09 — Statistics, publication and launch (stages 5–6, to 24 Sep 2026)

Everything that happens **after** the GEE assets exist and **before** the public launch. The assets
themselves — the month-of-burn collection and the nine subproducts — are
[`07-vector_to_raster.md`](07-vector_to_raster.md) (what we build) and
[`08-postprocessing.md`](08-postprocessing.md) (what the network expects); reference material (the
launch guide, the read-only reference repo, the legend spreadsheet) is catalogued in **docs/08 §1**
and not repeated here.

This file is a *build* document: what to write, where, in what order, and why each choice is the one
taken. **[`ROADMAP.md`](../../ROADMAP.md) is the *when*; this file is the *how*.** The statistics
come **after** the product re-export — every table below reads the published assets, so a table
built before the object filters land is a table that has to be thrown away.

Two things to keep in mind throughout:

- **Validation gate.** *"Antes de avanzar a la siguiente etapa, cada producto debe ser validado por
  el equipo del país correspondiente."* Every stage ends with our review, not an automatic hand-off.
- **Division of labour.** Brazil (IPAM) owns the public-asset copy and supports the Workspace
  registration. **We** own the territorial layers, all validation, and
  every country-specific material. The guide's stated goal is *"fortalecer la independencia de cada
  país para las próximas colecciones"* — expect to own more of this next collection.

> **We do not write a reducer.** Stage 5 is computed by the network's `2-Statistics/toolkit/v03/`,
> and the burnable denominator falls out of the same table as the numerator (§7). Everything that
> used to be planned here — the per-year 30 m reduction, the burnable benchmarks, the fixed
> modal-`veg_fire` layer, `workflow/11-burnable_area.py` and `workflow/11-burned_area_stats.py` — is
> **dead**. Those two scripts are kept only until the toolkit route is verified end to end, then
> deleted ([`ROADMAP.md`](../../ROADMAP.md)).

> **The object filters are not here.** The rules that fix the agriculture and Pampa over-mapping are
> part of the *mapping* and live in [`07-vector_to_raster.md` §1.1](07-vector_to_raster.md). By the
> time the statistics run they are already baked into the assets.

> **We do not use Looker Studio.** The network builds a Looker dashboard per country off these CSVs
> — Brazil offers to help set one up, and every other country has one. **Argentina's analysis is
> ours, in R**, straight off the exported CSVs: the factsheet plots, the GAMs, the trend summaries
> and every cross-tab in §9. The toolkit's job ends when the CSV lands in the bucket. If the platform
> team needs a dashboard of its own they can build one from the same files — it is not a deliverable
> of ours and nothing in this document depends on it.

---

## 1. The critical path

| Order | Item | Owner | Blocks |
|---|---|---|---|
| 1 | **Exclusion thresholds fixed and wired** (docs/07 §1.1) | us | every re-export |
| 2 | **Products re-exported** — 07a → 07d, and 07e (docs/07) | us | every number below |
| 3 | **The territorial layer** (§4) — one cut, unique integer id | **us** | every statistic **and** the platform's territory selector |
| 4 | **The `argentina/` toolkit folder** (§3) | us | the CSVs |
| 5 | **The area CSVs** (§5–§8), validated (§8) | us (+Brazil help) | the factsheet, launch materials, staging validation |
| 6 | **Public assets** (§11) — copy, ACL, properties | Brazil | Workspace, platform, downloads |
| 7 | **Workspace catastro** (§12) — subthemes + legends + territorial layers | Brazil support; layers ours | the platform showing anything |
| 8 | **Launch materials** (§13) — ATBD, methodology, downloads, factsheet, press | us + communications | 24 Sep |

Item 3 has a long tail and no external dependency — **start it first**. Item 8 depends on
articulation between our team, communications and the platform team, so it needs calendar lead time
rather than compute.

---

# Part A — stage 5: the area tables

## 2. The route, and why it is fast

The toolkit is `2-Statistics/toolkit/v03/` in the read-only reference repo
(`/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`). 41 files, ~1.5 k lines, and its reducer is
*identical* to the one we benchmarked at 8 h/year — and to the six `toDrive-area-*` reference
scripts of §5.2:

```js
// core/calculate.js
var reducer = ee.Reducer.sum().group(1, 'class').group(1, 'territory');
config.pixelArea.addBands(territory_image.rename('territory')).addBands(image.rename('class'))
  .reduceRegion({reducer: reducer, geometry: geometry, scale: config.scale, maxPixels: 1e12});
```

There is no trick in the reducer. It is fast because of what is *around* it, and those are the five
things we must copy:

1. **The cross-tab lives in the pixel value, not in a loop.** One sweep, two group fields. Every
   crossing is packed into one integer — Brazil goes to four dimensions in one band
   (`fire·10⁵ + lulc·10³ + def_sec_veg·10 + edge`). Cost is O(pixels), never
   O(pixels × combinations).
2. **No vector is ever intersected.** Territory is `ee.Image().paint(fc, id)` — one raster, one
   group field, every territory returned by a single reduce. No `filterBounds`, no per-feature loop,
   no `st_intersection`, and therefore no sliver polygons to clean up.
3. **The reduction geometry is a `bounds()` rectangle.** It can be, because `ee.Image().paint()` is
   masked outside the painted features, so the territory band already drops everything outside the
   country. Passing the buffered national multipolygon (which is what our own scripts did) clips
   every tile against a 2 M-edge geometry and buys nothing.
4. **No `tileScale`.** Ours was 4 — roughly 16× the shards, each re-paying the fixed per-shard cost.
5. **One task per (dataset × territory), all years inside it.** `bandNames().map(...)` reduces each
   year's band and flattens the 27 results into a single `Export.table`. Year cannot be a group
   field — it lives in the band dimension and a grouped reducer takes one group field — so this is
   one queue slot and one CSV, against our 2-tasks-per-account ceiling.

Note what is *not* on that list: **computing the image on the fly is fine**. Brazil's own datasets
are `multiply`/`unmask`/`add` combinations of two public assets, 41 bands, national, and they run.
Cheap arithmetic over stored byte bands on one lattice is not the problem; complex clip geometry,
shard multiplication and hidden resampling are.

Decoding class codes and territory ids to names happens on the few thousand *result rows*, via
`ee.Dictionary` lookups after the reduce — never per pixel.

---

## 3. Where our code lives, and the one patch we must make

### 3.1 Their layout, and ours

| Path in `toolkit/v03/` | What it is |
|---|---|
| `core/calculate.js`, `core/export.js`, `core/ui.js` | the engine — shared by every country |
| `<country>/datasets/fuego_col1.js` | which product assets and bands to read, and how to decode a class code |
| `<country>/territories/*.js` | one per territorial cut — the painted id raster and its decode |
| `<country>/_shared/legends.js`, `lulc_base.js` | legend lookups and the base images |
| `<country>/apps/fuego_col1.js` | the entry point that wires the above together |

Closest models: `peru/` and `colombia/` are the simple case (one `regiones.js`); `paraguay/` shows
one id decoding to four nested levels; `brasil/` is the elaborate case (`bioma_estado.js`,
`malungus_bioma_estado.js`).

`mapbiomas-latam-fire-gee` is **read only** (CLAUDE.md). And `core/calculate.js` hard-codes
`scale: config.scale`, which we cannot use (§3.2). So the Argentina toolkit lives in **our** `fuego`
repo:

```
mapbiomas-arg-fire-gee/collection-01/statistics/
  core/calculate.js          # fork: scale -> crs + crsTransform.  THE ONLY LOGIC CHANGE.
  core/export.js             # fork: require paths point at ours; bucket/folder from config
  core/ui.js                 # fork, byte-identical (no compute in it)
  argentina/apps/fuego_col1.js
  argentina/datasets/fuego_col1.js
  argentina/territories/index.js
  argentina/_shared/products.js   # FINAL_PRODUCTS asset ids — mirrors utils/constants.py
  argentina/_shared/legends.js    # thin: LULC legends come from their 00_Tools/Legends.js
```

Keep the fork **minimal and annotated**, one comment block per divergence, so the `crsTransform`
patch can be handed back to Brazil as a proposal (§16).

### 3.2 The grid: pin it, never `scale: 30`

Every raster in this pipeline sits on one lattice and must keep sitting on it — that rule has held
since step 03 and the statistics do not get an exception. `reduceRegion` takes **either** `scale`
**or** `crs` + `crsTransform`; the patch to `core/calculate.js` is:

```js
.reduceRegion({
    reducer: reducer,
    geometry: geometry,
    crs: config.crs,                  // was: scale: config.scale
    crsTransform: config.crsTransform,
    maxPixels: 1e12
});
```

The lattice is not in the GEE-side constants yet. **Add it to
`mapbiomas-arg-fire-gee/collection-01/utils/constants.js` and require it** — do not paste the
numbers into the app:

```js
var SNIC_CRS       = 'EPSG:4326';
var SNIC_TRANSFORM = [0.000269494585236, 0, -73.58468801489491,
                      0, -0.000269494585236, -21.764113209062533];
```

(the same values as `utils/constants.py::SNIC_CRS` / `SNIC_TRANSFORM`; that file stays the source of
truth and the JS copy carries the same SYNC WARNING the `veg_fire` arrays already carry). Add
`PRODUCT_LULC`, the `FINAL_PRODUCTS` prefix and `MONTH_OF_BURN_COL` in the same pass.

Two things worth knowing about why this is cheap rather than expensive:

- `30 / 111319.49 = 0.000269494585236` — the toolkit's `scale: 30` in EPSG:4326 lands on **exactly**
  our pixel size. So pinning does not change the pyramid level and cannot trigger the
  mode-pyramid dilation of a sparse burned raster (+14 % at 90 m, +36 % at 120 m, measured). What
  `scale: 30` *would* get wrong is only the **origin phase** — a sub-pixel shift of every product
  against every other.
- The published LULC (`mapbiomas_argentina_collection3_pb`) is an **integer offset** from our
  lattice (+67 px lon, −62 px lat, verified 2026-09-10). Integer offset means same phase: pinned to
  `SNIC_TRANSFORM`, the LULC band and the month band land on identical pixels with **no resampling
  anywhere in the reduction**.

### 3.3 The rest of the config

```js
var cfg = {
    gcsBucket: 'mapbiomas-fire',
    gcsFolder: 'data-container/stats/mapbiomas_fuego_argentina_collection1/',
    collection: 'MapBiomas Fuego Col. 1',
    descriptionPrefix: 'WS_MBFUEGO_AR_COL1-',      // namespaced: the project is shared
    crs: C.SNIC_CRS,
    crsTransform: C.SNIC_TRANSFORM,
    global_geometry: ee.FeatureCollection(C.ARG_BUFFER_FC).geometry().bounds(),   // RECTANGLE
    pixelArea: ee.Image.pixelArea().divide(1e6)    // km²; the core multiplies by 100 -> ha
};
```

- `global_geometry` is `.bounds()`. **Never the multipolygon** (§2, point 3).
- No `tileScale`. Add it only if a task OOMs, and record that it was needed.
- `descriptionPrefix` is mandatory, not cosmetic: the compute project is shared with the whole
  network and a generic task description collides with another country's (docs/07 §12.7).
- Output goes to **Cloud Storage**, which needs write access on that bucket — an open item (§16).
  The fallback is a one-line switch to `Export.table.toDrive` in our forked `core/export.js`.

---

## 4. The territorial layer

This is the only stage-5 item that was always ours, and it serves two consumers at once: the
statistics (as a painted id raster) and the **platform's territory selector** (as a registered
Workspace layer, §12).

### 4.1 The constraint the guide sets

Because **every subproduct × territory combination becomes its own table**, the number of
territorial divisions must be **deliberately limited**. The guide's specification of the ideal input:

> *"Capa ideal en asset: un único asset con intersección de estados, municipios y biomas con un ID
> único y una columna para cada dato."*

One FeatureCollection, features = the intersection of the chosen cuts, each with a **unique `id`**
and one column per attribute. Bolivia's is `bioma_depart_munic` (biome × department × municipality);
Paraguay's is `paraguay_political_levels` with a single `FEATURE_ID` decoding to ecoregion,
macroregion, department and district.

Cuts to consider and then probably decline for v1: protected areas, indigenous territories,
watersheds, and our own 5 fire regions — each is analytically interesting and each multiplies every
table. **Fire regions are not a statistics unit**: `regiones_fuego_*` is only used for masking and
export geometry (docs/08 §5.2).

### 4.2 The layers exist — the `Stats-Arg_*` family

**Verified 2026-09-11 in the asset browser.** A complete, purpose-built territorial family is
already in `ANCILLARY_DATA/`, vector *and* raster, carrying MapBiomas's own territory schema
(`CATEG_ID`, `GEOCODE`, `LEVEL_1..3`, `NAME_STD`, `SOURCE`, `VERSION`) — i.e. it was prepared for
exactly this stage:

| asset (`ANCILLARY_DATA/VECTOR/ARG/`) | n | id property | names | notes |
|---|---|---|---|---|
| `Stats-Arg_political_level_3_v` | **528** departamentos | `GEOCODE` = `cde` = INDEC 5-digit | `LEVEL_3` depto, **`LEVEL_2` provincia** | also carries `cpr` = province code |
| `Stats-Arg_political_level_2_v` | **24** provincias | `GEOCODE` = INDEC 2-digit (2…94) | `LEVEL_2` | `SOURCE` = Instituto Geográfico Nacional |
| `Stats-Arg_ecorregions` | **16** ecorregiones | `GEOCODE` 1..16 | `LEVEL_2` | `SOURCE` = Administración de Parques Nacionales |
| `ARG-Political_Level_2-13Ecorregiones_3857` | **13** ecorregiones | `GEOCODE` 1..13 | `LEVEL_2` | the aggregation; clean UTF-8 names |

Each has a raster twin in `…RASTER/ARG/` — `Stats-Arg_political_level_{2,3}_r`,
`Stats-Arg_ecorregions_r` and `ARG-Political_Level_2-13Ecorregiones_3857_r` — all **EPSG:3857 at
30 m**. §4.3 says why we paint the vectors instead.

Three things that follow, all measured:

**1. The department layer carries the province.** `LEVEL_2` on
`Stats-Arg_political_level_3_v` is the province name and `cpr` its code, and `GEOCODE` is
`provincia·1000 + departamento` (2007 … 94021). So **one painted layer gives both levels** and the
province dictionary needs no second asset.

**2. 16 → 13 ecoregions is an exact aggregation.** Measured by crossing the two painted layers over
the whole country: every 16-class falls **100 %** inside one 13-class.

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

**Therefore export on the 16-class layer.** Both regionalisations come out of one table: the
13-class figures the factsheet wants are a `group_by` on the crosswalk above, and the finer split
(Chaco Húmedo vs Chaco Seco, the two Montes) is there for free if anyone asks. Exporting the
13-class layer instead would throw that away and save nothing.

**3. ⚠️ The `Stats-Arg_*` names are mis-encoded.** They come back as `Esteros del Iber<?>`,
`Bosques Patag<?>nicos`, `Administraci<?>n de Parques Nacionales` — Latin-1 bytes stored as UTF-8.
The 13-ecoregion asset is clean. **Do not let that reach a CSV a designer reads**: repair the names
where the dictionary is built (a fixed 16-entry list in `argentina/_shared/legends.js` is the
simplest honest fix) and check the departamento names too before hand-off.

### 4.3 Pack painted vectors, do not intersect them

Brazil packs painted layers arithmetically (`bioma·10⁶ + estado·10⁴ + malungu`); Paraguay and
Bolivia pre-intersect a vector. **We pack.** Packing has no sliver problem (there are no new
polygons) and no topology cleaning, and it is reversible by integer division in `getProperties`.
The Workspace registration can still take a plain vector layer — the two do not have to be the
same object.

One territory cut, from which every other level falls out:

```
territory_id = ecoregion16 · 100000  +  GEOCODE(departamento)
```

Maximum id `16·10⁵ + 94021 = 1,694,021` — exact in int32 and in float64.

```js
var eco = ee.Image().paint(ECOREGIONS16, 'GEOCODE');            // masked outside Argentina
var dep = ee.Image().paint(DEPARTAMENTOS, 'GEOCODE').unmask(0); // unmasked: see below
return eco.multiply(100000).add(dep).toInt().rename('territory');
```

```js
getProperties: function(id) {
    var eco = id.divide(100000).int();
    var dep = id.mod(100000).int();
    return ee.Dictionary({
        'Ecorregion':    ECO16_NAMES.get(eco.format('%d')),
        'Ecorregion13':  ECO13_NAMES.get(CROSSWALK.get(eco.format('%d'))),
        'Provincia':     PROV_OF_DEP.get(dep.format('%d')),
        'Departamento':  DEP_NAMES.get(dep.format('%d'))
    });
}
```

**Paint the vectors, not the `_r` rasters.** The rasters are EPSG:3857 at 30 m — a different grid
from ours — so reading one inside a reduction pinned to `SNIC_TRANSFORM` reprojects it. For an
integer category band that is nearest-neighbour, so no code is ever invented, but boundary pixels
shift by up to half a pixel for no benefit. `paint` rasterises the vector directly at the pinned
grid. Keep the rasters as an independent cross-check, not as the input.

**The masking trap, and the rule.** `ee.Image().paint()` is *masked* outside the painted features,
and `add()` propagates masks — so if both layers are masked, any pixel missing from either drops
silently out of the reduction. Keep **exactly one** layer as the mask driver (the ecoregions: they
tile the country) and `unmask(0)` the other. A `departamento == 0` then means "inside an ecoregion,
outside the department layer" and is visible as its own row — which is why §8 has a QC gate on it.

**Name dictionaries come off the FCs themselves**, Bolivia's pattern, so nothing has to be added to
their `00_Tools/Legends.js`:

```js
var ids = FC.aggregate_array('GEOCODE').map(function(i){ return ee.Number(i).format(); });
var DEP_NAMES   = ee.Dictionary.fromLists(ids, FC.aggregate_array('LEVEL_3'));
var PROV_OF_DEP = ee.Dictionary.fromLists(ids, FC.aggregate_array('LEVEL_2'));
```

— except the 16 ecoregion names, which are hand-written because of the encoding damage (§4.2).

### 4.4 The cuts to offer, in order

| cut | territory image | when |
|---|---|---|
| **`ecoregion`** | `paint(ECOREGIONS16, 'GEOCODE')` | build first — 16 rows, fast, and it answers the whole factsheet via the §4.2 crosswalk |
| **`ecoregion_departamento`** | the packed id of §4.3 | the master cut; ecorregión (16 **and** 13), provincia and departamento all aggregate from it exactly, because the pieces are disjoint |
| `provincia` | `paint(PROV, 'GEOCODE')` | only if the platform's territory selector wants it as its own registration |

Because the pieces are disjoint, **every coarser cut is a `group_by` on the finer table** — no
double counting, no re-export. That is the whole point of computing the crossing once.

**Provenance, for the record**: departments and provinces are **IGN** (`SOURCE` on
`Stats-Arg_political_level_2_v`); the 16 ecoregions are **Administración de Parques Nacionales**,
Burkart et al. 1999; the 13-class layer is the published aggregation of the same. The platform will
publish area numbers against whichever is registered in Workspace (§12), so the registration and the
statistics must name the same asset — see §15.

---

## 5. The datasets

A "dataset" in the toolkit is just *an image whose every band name ends in a 4-digit year*
(`core/calculate.js::getYearFromBandnameUniversal` = `ee.Number.parse(bandname.slice(-4))`), plus a
`decodeStrategy(classId)` that turns the packed class code into output columns. Two families.

### 5.1 D1 — the master table, and the only one the `%` metric may use

```
class = month(0..12) · 100 + lulc_col3(calendar_year − 1)
```

```js
// one band per calendar year, named ..._<year>
var d1 = ee.Image.cat(YEARS.map(function (y) {
    var month = ee.Image(MONTH_OF_BURN_COL.filter(ee.Filter.eq('year', y)).first())
                  .select('burned_monthly').unmask(0);          // 0 = did not burn
    var lulc  = ee.Image(PRODUCT_LULC).select('classification_' + (y - 1));
    return month.multiply(100).add(lulc).toUint16().rename('burned_lulc_' + y);
}));
```

Max value `12·100 + 77 = 1277`, so uint16. Decode is `month = class / 100`, `lulc = class % 100`,
and the output columns are `Mes`, `Mes_id`, `Nivel 0/1/2` from their `lulc_argentina_nivel0/1/2`
legends (already present in `00_Tools/Legends.js` — nothing to add).

**`unmask(0)` is the load-bearing part.** It makes the image space-filling, so unburned pixels are
reported too. That single decision is what turns one table into numerator *and* denominator:

| question | rows to sum |
|---|---|
| burned area, year × territory | `Mes_id ≥ 1`, `Nivel 2` burnable |
| burned area × land cover | idem, grouped by `Nivel 1/2` |
| burned area × month (pirogram) | idem, grouped by `Mes_id` |
| **burnable area** (the denominator) | **all** `Mes_id` 0..12, `Nivel 2` burnable |
| burned on non-burnable (QC) | `Mes_id ≥ 1`, `Nivel 2` non-burnable |
| no-observado (excluded everywhere) | `Nivel 2 == 'No observado'` |

**Why the *previous* year's land cover.** A fire consumes the vegetation that was there *before* it
burned; the same-year class of a burned pixel is partly a *consequence* of the fire. And it is what
makes `%` coherent: numerator and denominator then read the same layer, so "% of grassland that
burned" is a ratio of two areas of the same thing. Band years are 1999..2025, so the LULC bands
needed are 1998..2024 — all inside col-3's `classification_1985..2025`, no forward duplication, no
`MB_LIMIT_YEAR` cap.

**Why col-3 and not our `veg_fire`.** Col-3 is the best current estimate of land cover, it is the
legend every reader and every other MapBiomas product uses, and its non-burnable classes are
directly identifiable — so the denominator needs no extra asset at all (§6). The cost is that the
denominator is no longer *exactly* the layer the SNIC candidate set was built from (col-2 v8
reclassed to `veg_fire`), so a pixel can be mapped as burned and be non-burnable under col-3. That
residual is measurable in this same table, is excluded from both numerator and denominator so it can
never produce a `%` above 100, and gets reported once (§8).

> If D1 turns out slow — it should not; it is two stored byte reads, a multiply and an add, on one
> lattice, i.e. exactly Brazil's shape — the escape hatch is to materialise it as **one 27-band
> uint16 asset** with a single pixel-wise `Export.image.toAsset` and point the dataset at that. A
> pixel-wise export is not a reduction and is cheap. Do not go back to a hand-written reducer.

### 5.2 D2 — the six network-spec tables

The network's stage-5 deliverable: the published products read **as they are**, i.e. with the
**same-year** LULC the reference encoding specifies. The specification of what each number is comes
from `2-Statistics/2-ColAnual-Products-Reference/`; the decode strategies are copied from
`peru/datasets/fuego_col1.js`, which is that reference already adapted to a country.

| reference script / dataset | image | computes |
|---|---|---|
| `toDrive-area-annual-burned-coverage` | `FINAL_PRODUCTS/…_annual_burned_coverage_v1` | burned area per **year × LULC class × territory** |
| `toDrive-area-monthly-burned-coverage` | `…_monthly_burned_coverage_v1` | idem per **month** (`month·100 + lulc`) |
| `toDrive-area-accumulated-burned-coverage` | `…_accumulated_burned_coverage_v1` | accumulated burned area per LULC class × territory |
| `toDrive-area-frequency-burned-coverage` | `…_frequency_burned_coverage_v1` | area per **burn frequency** × LULC class × territory (`freq·100 + lulc`) |
| `toDrive-area-scar-size` | `…_annual_burned_scar_size_range_v1` | area per **scar-size range** × territory (two legend levels) |
| `toDrive-area-year-last-fire` | `…_year_last_fire_v1` | area per **year of last fire** × territory |

Asset ids come from `argentina/_shared/products.js`, which mirrors
`utils/constants.py::product_name()` — one place, so a `_v2` rename (§16) is one edit.

`2-Statistics/1-Burned_area_products/` additionally computes the same areas for **FireCCI, GABAM and
MCD64A1** — the inter-comparison used in launch materials. Optional, but it is the standard way to
show a new collection is sane, and Argentina has no previous MapBiomas Fuego collection to compare
against, so it is worth doing.

**D1 and D2 will not agree, by construction**, because one crosses the previous year's land cover
and the other the same year's. Say so in the factsheet footnote and in the CSV hand-off. The `%`
metric is **only ever** computed from D1; D2 is absolute areas for the platform, which is all the
network's six CSVs have ever contained.

---

## 6. Burnable: the col-3 class list

**Nobody in the network computes a burnable denominator.** Grepped the whole reference repo: no
`burnable`, no `quemable`, no percentage-of-burnable concept. Every network statistic is an absolute
area — "area of class X, in territory Y, in year Z", in km² and ha. **`% burned` is entirely
Argentina's own addition**, which means we are free to define it however we like: there is no
network spec to deviate from.

"Burnable" is a property of the land-cover class, so it is a legend decision, not a computation. Our
own col-2 remap (`config/veg_fire_remap.csv`) is the anchor: in **every one of the 5 regions** it
sends MapBiomas classes **24, 25, 33, 34 → `veg_fire` 24 (non-burnable)** and **27 → 25
(non-observed)**. Region-independent, so it carries over to col-3 unchanged.

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

**22 and 26 had no precedent and were decided.** They do not appear in col-2 v8 at all (they are
absent from `REGION_CLASS_FROM`), so our remap never ruled on them. **Both are non-burnable** (Iván,
2026-09-11) — they are the bare-ground and water families, which is where the col-2 remap puts their
nearest equivalents.

**Verify the list against the data, once**: run a `frequencyHistogram` over one col-3 band and check
that every code it contains is in the table above. A class present in col-3 and missing here would
otherwise fall through into whichever bucket the decode default puts it in, silently.

A CSV carries no metadata of its own, so the burnable definition has to be recorded somewhere a
reader will find it: put the class list in the app's source next to the decode strategy, and name
the version in the export task's `description`. Never leave it implicit in a downstream `group_by`.

---

## 7. Running it, and what comes out

The app (`argentina/apps/fuego_col1.js`) is the toolkit's standard UI: check datasets, check
territorial cuts, press export. One task per (dataset × cut).

```
tasks = (1 D1 + 6 D2) × (1..3 cuts)
```

Start with **D1 × ecoregion** alone. It answers the entire factsheet and it is the cheapest thing to
be wrong about. Then D1 × ecoregion_departamento, then the six D2 × the cuts the platform wants.

Output lands in `gs://mapbiomas-fire/data-container/stats/mapbiomas_fuego_argentina_collection1/<cut>/<dataset>_<cut>.csv`,
columns `Área ha`, `Ano`, then the dataset's columns, then the territory's.

**Expected sizes** — worth knowing before an export runs for an hour and produces something
unopenable:

| table | rows (upper bound) | note |
|---|---|---|
| D1 × ecoregion | 27 y × 13 terr × 13 months × ~20 classes ≈ **91 k** | trivially small |
| D1 × ecoregion_departamento | 27 × ~800 × 13 × 20 ≈ **5.6 M** worst case | the dense part (`Mes_id == 0`) is 27 × 800 × 20 ≈ 430 k; realistic total 1–2 M rows, ~150 MB |
| any D2 × ecoregion | ≤ 100 k | burned-masked, so sparse |

If the crossed table is unwieldy, the fix is not a coarser grid — it is to export D1 × ecoregion and
D1 × departamento separately and accept that the ecoregion × department crossing is then unavailable.
Decide that only after seeing the real row count.

---

## 8. Verification gates — run these before any number leaves the building

| # | check | passes if |
|---|---|---|
| 1 | **Lattice.** One territory, one year, run once pinned and once with `scale: 30`. | Difference is a sub-pixel-scale rounding, not a systematic inflation. A large gap means the phase assumption in §3.2 is wrong. |
| 2 | **National annual burned, D1 vs the object database.** Sum D1's `Mes_id ≥ 1` rows over all territories per calendar year. | Matches the local object-derived area to well under 1 %. Not exactly: the products split objects per pixel by `abs_date`, the object table does not. |
| 3 | **National annual burned, D1 vs `mob_month_stats`.** 27 assets of per-month whole-country pixel counts already exist (docs/07 §7). | *Relative* month shape matches. Absolute hectares will not — those are pixel counts and `× 0.09 ha` is wrong by 18.5 % on a lon/lat lattice (mean effective pixel 0.0759 ha at lat ≈ 32°), and the bias is not uniform by month. |
| 4 | **`departamento == 0`.** | Area is negligible. If it is not, the department layer does not cover the country and §4.2's mask rule is hiding it. |
| 5 | **Burned on non-burnable.** | Small, and *reported*. This is the price of using col-3 instead of `veg_fire` (§5.1) and it must be a stated number, not a discovery. |
| 6 | **D1 vs D2 on one year.** | They differ, and the difference is explainable as the previous-year/same-year LULC shift — concentrated in classes that change (agriculture, secondary vegetation), near zero in stable classes. |
| 7 | **Row-count sanity.** | No territory is missing from the output. A territory absent from every year means its id collided in the packing or its polygon is outside the mask. |
| 8 | **Against the platform, in *staging*, before launch.** | Within the network's accepted tolerance. These statistics are computed **in GEE, on the fly, independently of the platform**, and the guide states an expected **mean difference of ~1 %** against the platform's own numbers. |

Gates 1 and 4 are cheap and catch the two failure modes that are invisible in the numbers
themselves. Do them first.

**Don't chase the 1 % of gate 8.** Do chase anything much larger — it means a real problem (wrong
territory layer, wrong LULC year, a region missing from the mosaic). And note the one failure mode
that is *ours to warn the network about*: any statistic that reads our burned-area rasters below
native resolution over-reports, because `mode` pyramiding dilates a sparse burn mask (§16.8).

---

## 9. From the tables to the factsheet

`presentations/factsheet-notes.md` holds the message; this is where each number comes from. All of
it is a `group_by` on D1 except the fire counts.

**Analysis 1 — mean annual burned proportion.** Per territory and calendar year:
`quemado = Σ(Mes_id ≥ 1, burnable)`, `quemable = Σ(all Mes_id, burnable)`, `pct = quemado/quemable`.
Mean over years. The absolutes for the caption ("4.2 Mha quemadas de 100 Mha quemables") are the
same two sums. The per-LULC-class version is the same rows grouped by `Nivel 1` or `Nivel 2`.

**Analysis 2 — the time series and its trend.** The per-year `pct` series from analysis 1; fit the
GAM locally in R (few bases, `k` small) and summarise as the mean slope, standardised by the series
mean or sd so regions are comparable. Nothing new is exported.

**Analysis 3 — the pirogram, area half.** Group D1's `Mes_id ≥ 1` rows by `Mes_id`; per month take
the mean over years of that month's share of the year's burned area; normalise to 100 %. Plot
May→April so neither peak is cut — the national curve is bimodal (Aug/Sep/Oct and Dec/Jan/Feb), two
regimes in one line, which is the argument for the regional panels.

**Analysis 3 — the count half.** **Not from these tables.** Fire counts are the local object
database (`objects-pred/` + `objects-raw/*_raster_metrics.csv` + the `.gpkg` geometries), joined to
the ecoregions in `sf`, fire-year based, month = month of `date_median`, an object counted in every
region it intersects. That work is done and is threshold-agnostic — re-tagging under a different
filter is a `filter()` call. `factsheet_region_summary_min10ha.csv` and
`factsheet_counts_by_month_min10ha.csv` already exist; they must be **re-generated under the final
filters** ([`ROADMAP.md`](../../ROADMAP.md)) because the object selection changed.

**The two divergences to state in the footnote.** The rasters assign calendar year and month **per
pixel** from `abs_date`; the object/count side assigns **per object** from `date_median`. So (i) a
fire straddling 31 December is split in the rasters and not in the counts, and (ii) "area burned in
month M" is a pixel sum in D1 and a whole-object assignment in the counts. Acceptable — say it.

---

## 10. What these tables cannot answer

- **Anything per fire**: number of fires, size distribution, median fire size, fire density. That is
  the object database (§9, count half).
- **Scar size** crossed with land cover or month: the `annual_burned_scar_size_range` product has no
  LULC dimension (D2 gives size × territory only).
- **Fire-year anything**, directly — but D1 carries month *and* year, so fire-year totals are
  recoverable by summing May..Dec of year *y* with Jan..Apr of *y+1*. That is a legitimate
  aggregation of the published calendar-year products and should be labelled as such.
- **Error-adjusted area.** That is [`10-validation.md`](10-validation.md)'s design-based estimate and
  is not ready for September.

---

# Part B — stage 6: publication

## 11. Public assets

Two distinct destinations, and it is worth being clear about which one the platform reads:

| Destination | Script | What it is |
|---|---|---|
| **Public GEE assets** — `projects/mapbiomas-public/assets/argentina/fire/collection1/` | `ToPublish/3-toAsset-Public` (renumbered — was `2-`) | `copyAsset` → `setAssetAcl({all_users_can_read: true})` → `setAssetProperties({data_type, band_format, version})`. `data_type ∈ {annual, monthly, accumulated}`; `band_format` is the literal band template (`burned_monthly_{year}`, `fire_accumulated_{year1}_{year2}`, …) |
| **Cloud Storage COGs** — `gs://shared-development-storage/COLLECTIONS/ARGENTINA/FIRE/COLLECTION1/temp/…` | `ToPublish/2-toBucket-subproducts` (renumbered — was `1-`) | one **COG per band**, cast to `byte` (or `uint16` for `year_last_fire`) |

**What the platform ingests: the public GEE assets.** The evidence is the Workspace subtheme form,
whose key field is a **`GEE Asset ID`** pointing at `projects/mapbiomas-public/...`, with the
`data_type`/`band_format`/`version` properties telling the platform how to read the bands.
*Inference (not stated in the code):* the bucket COGs serve the **download page** — public download
URLs are `https://storage.googleapis.com/mapbiomas-public/initiatives/…/*.tif|.zip` — and the
`/temp/` path suggests a staging area the platform team promotes from. Brazil supplies the final
direct links.

**Brazil owns this step** ("para garantizar parámetros necesarios"), so our job is to have the
`FINAL_PRODUCTS` assets correct and named exactly right, and to check the copies afterwards.

⚠️ **Re-exporting `FINAL_PRODUCTS` changes nothing the public sees until Brazil re-copies**, and the
Cloud-Storage COGs need regenerating alongside. Both are in §16.

---

## 12. Workspace catastro

**What Workspace is:** <https://workspace.mapbiomas.org/modules> is MapBiomas's internal metadata
registry — the admin layer behind the public platform. It is where you declare *which GEE asset* is
a given product, *how to colour it*, and *which territories* to aggregate by. Nothing appears on the
platform until it is registered here.

Three things get registered:

**1. Subthemes** (one per published product). Form fields:

| Field | Value |
|---|---|
| `Team` | General Team (Argentina) |
| `Type` | `Classification Multiband Image` |
| `Group` | `Classification` |
| `Territory category` | `POLITICAL_LEVEL_1` |
| `Territory` | `[Argentina]` |
| **`GEE Asset ID`** | the `mapbiomas-public` asset (§11) |
| `Subtheme name` | e.g. *Annual Burned*, *Monthly Burned*, *Annual Burned Coverage*, *Scar Size* |
| `Legend` | the legend registered below |
| *"Will it be published?"* | toggle |

Subtheme names in use across countries: **Annual Burned**, **Monthly Burned**, **Annual Burned
Coverage**, **Annual Burned Natural and Anthropic Use** (Paraguay maps this one to
`accumulated_burned_coverage`), **Scar Size**, **Total Burned**. Match an existing country's naming
rather than inventing ours.

**2. Legends** — class ↔ pixel value ↔ colour, per subproduct: annual = 1 class (value 1); monthly =
12 classes (values 1–12); scar size = the **two-level** scheme (docs/08 §5.4). ⚠️ **Take pixel values
and hex colours from `Mapbiomas-Fogo-Legenda-Col4.xlsx`, never from screenshots**, and make sure the
registered scar-size ranges match the ranges we actually rasterized (docs/08 §8.6) — same pixel
values, different thresholds is a silent, invisible error.

**3. Territorial layers** — the §4 asset, which the platform uses for its territory selector and its
own statistics. **Our responsibility.**

Brazil supports the registration; we supply the values and verify.

---

# Part C — launch

## 13. Launch-preparation track (parallel, non-code)

From the guide, six items; all of them adapt Brazil's reference material to Argentina:

| # | Item | Notes |
|---|---|---|
| 1 | **Destacados** (key findings) + infographic | Brazil provides `Fact_Fogo_colecao4.pdf` and an infographic template |
| 2 | **Validation of the data in the *staging* platform** | our sign-off, using the §5–§8 statistics as the cross-check |
| 3 | **Website materials**: **ATBD**, methodology page, informative note | our ATBD must describe *our* method (steps 01–07), which is **not** Alencar et al. — see docs/08 §3. Peru's and Paraguay's ATBDs are the format model |
| 4 | **Downloads page** with direct links | Brazil supplies the URLs (§11); we also need a *códigos de la leyenda* page |
| 5 | **Launch event** organisation | with communications |
| 6 | **Press release** + dissemination | Brazil's example: *"Área queimada no Brasil em 2024 supera média histórica em 62 %"* |

Also available from the guide: the **brand manual + MapBiomas Fuego logos**, and Brazil's **launch
checklist** (`Checklist de demandas - Col.4 Fogo`) — worth copying as our own tracking sheet.

> **Argentina's ATBD is the one document nobody else can write for us.** Our method differs from
> every other country in the network (docs/08 §3), so the methodology page and ATBD cannot be
> adapted mechanically from Brazil's — they have to describe the burn-probability → SNIC →
> object-model chain, including the non-calendar fire-year and how it is re-partitioned into
> calendar years (docs/08 §6.2).

---

## 14. Decisions on record

| # | decision | who / when |
|---|---|---|
| 1 | Stage 5 is computed by the network's `toolkit/v03`, not by us; both step-11 Python scripts are retired | Iván, 2026-09-11 |
| 2 | The lattice is pinned (`crs` + `crsTransform`), never `scale: 30` — one grid for every raster, as since step 03 | Iván, 2026-09-11 |
| 3 | Territories are **packed painted vectors**, not intersected ones (no slivers); master cut = ecoregion × departamento, province carried by the department layer | Iván, 2026-09-11 |
| 4 | The vegetation cross uses **col-3 (`PRODUCT_LULC`), previous year**, for D1; the published `*_coverage` products keep the network's same-year encoding | Iván, 2026-09-11 |
| 5 | Burnable is defined on col-3 classes (§6); **no separate burnable asset, no fixed modal `veg_fire` layer** | Iván, 2026-09-11 |
| 6 | The statistics run **after** the product re-export, never before | Iván, 2026-09-11 |
| 7 | Ecoregions are **Burkart et al. 1999** — the factsheet reports the **13-class** aggregation (what land cover uses), but the export runs on the **16-class** layer, since 16 → 13 is exact and one table then serves both (§4.2) | Iván, 2026-09-10 / 09-11 |
| 8 | Col-3 classes **22 and 26 are non-burnable** (§6) | Iván, 2026-09-11 |
| 9 | The two object exclusion rules and their thresholds (`T_GRASS = 0.70`, 1 Jul → 15 Nov, `T_AGRI = 0.40`) are **FINAL**, as specified in docs/07 §1.1 — not a parameter these statistics may vary | Iván + team, 2026-09-11 |
| 10 | The territorial layers are the existing **`Stats-Arg_*` family** (§4.2), painted from the vectors — not new assets, and not the `_r` rasters | Iván, 2026-09-11 |
| 11 | The September re-export is **`_v2`** on our tree (`C.PRODUCT_VERSION`, docs/07 §1.2); Brazil copies it over the public asset, so no public id changes | Iván + Brazil, 2026-09-11 |

---

## 15. Open items

Actionable work is on [`ROADMAP.md`](../../ROADMAP.md); these are the questions it is waiting on.

1. **Which ecoregion layer does the platform's territory registration expect** — the 16-class
   `Stats-Arg_ecorregions` (whose schema says it was built for the statistics stage) or the 13-class
   aggregation the factsheet reports? Our export covers both (§4.2), but Workspace registers *one
   asset*, and the statistics and the registration must name the same one (§12). This is a question
   for whoever built the `Stats-Arg_*` family — probably the Argentina land-cover team, not Brazil.
2. **The `Stats-Arg_*` name encoding is broken** (§4.2, Latin-1 stored as UTF-8). Fix it in our
   dictionaries for September; ask whether the source assets should be re-ingested for the long run.
3. **Whether to run the FireCCI / GABAM / MCD64A1 comparison** (§5.2). Recommended: yes — it is the
   only external sanity check available for a first collection.
4. **Subtheme naming** for Argentina (§12) — mirror Peru's or Paraguay's exactly.
5. **Scar-size legend** must match the rasterized ranges (docs/08 §8.6) — settle before
   registration.
6. **ATBD authorship and review** — the longest-lead item on the launch track (§13).
7. **Statistics for our own fire-year objects.** Everything above is calendar-year, per the network.
   Our fire-year object database supports analyses the official products cannot (per-event size
   distributions, season-spanning fires). Worth a separate, clearly-unofficial output — but not
   before 24 September.

---

## 16. To ask / confirm with the Brazil team

Carry this list into the next call; several items block work in §3 and §7.

1. **GCS write access** to `gs://mapbiomas-fire/data-container/stats/…` for our account, and
   confirmation of the folder name `mapbiomas_fuego_argentina_collection1/`. If not, we export to
   Drive and hand over files — does that break anything downstream on their side?
2. **Where should `argentina/` live?** Their repo is read-only for us. We build it in our `fuego`
   repo requiring their `core/`; do they want it copied into `toolkit/v03/argentina/`?
3. **Would they take the `crsTransform` patch upstream** in `core/calculate.js` (optional
   `config.crs` / `config.crsTransform`, falling back to `scale`)? Argentina is not the only country
   whose products are not on a `scale: 30` EPSG:4326 grid.
4. **Asset versioning — decided, confirm the copy.** We write **`_v2`** on our side
   (`C.PRODUCT_VERSION = 2`, docs/07 §1.2) and they copy it over the public asset, so the public id,
   the Workspace registration, `band_format` and every download link are unchanged. Confirm that is
   still their plan, and that `argentina/_shared/products.js` should therefore point at **v2 on our
   tree** for the statistics while the platform keeps reading the public copy.
5. **Last date** we can hand them updated assets and still have them on the platform for 24 Sep.
   That date, not the 24th, is the real deadline.
6. **Does anything on their side consume these CSVs automatically**, and are the column names
   fixed (`Área ha`, `Ano`, `Nivel 0/1/2`)? We add `Ecorregion` / `Provincia` / `Departamento`.
7. **The territorial layer for the platform's territory selector** — is it the same layer as our
   statistics cut, and in what format?
8. **Coarse reads of sparse burned rasters over-report**, network-wide: `mode` pyramiding dilates a
   sparse burn mask, measured at **+14 % at 90 m and +36 % at 120 m**. Anything that reduces a
   published burned-area product below native resolution — a dashboard cross-check, a quick
   `reduceRegion` at 500 m — is wrong in the same direction. Worth a warning to every country, not
   just a fix on our side.
9. **Anything already generated downstream of our assets** that a re-export silently invalidates:
   statistics already loaded into their own dashboards, and the Cloud-Storage COGs behind the
   downloads page — who regenerates them, and by when?
