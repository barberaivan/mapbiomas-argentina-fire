# 09 — Statistics, publication and launch (1 Aug → 24 Sep 2026)

Everything that happens **after** the GEE assets are delivered (31 July 2026) and **before** the public
launch (24 September 2026). The assets themselves — the month-of-burn collection and the ten
subproducts — are [`08-postprocessing.md`](08-postprocessing.md); reference material (the network's
launch guide, the read-only reference repo, the legend spreadsheet) is catalogued in **docs/08 §1** and
not repeated here.

These are stages **5 and 6** of the network's six-stage launch process (docs/08 §2), plus the parallel
launch-preparation track. Two things to keep in mind throughout:

- **Validation gate.** *"Antes de avanzar a la siguiente etapa, cada producto debe ser validado por el
  equipo del país correspondiente."* Every stage below ends with our review, not an automatic hand-off.
- **Division of labour.** Brazil (IPAM) owns the public-asset copy and supports the Workspace
  registration and the Looker Studio build. **We** own the territorial layers, all validation, and every
  country-specific material. The guide's stated goal is *"fortalecer la independencia de cada país para
  las próximas colecciones"* — expect to own more of this next collection.

---

## 1. The critical path

| Order | Item | Owner | Blocks |
|---|---|---|---|
| 1 | **Territorial layer** (§2.2) — one asset, few cuts, unique `id` | **us** | every statistic **and** the platform's territory selector |
| 2 | `*_coverage` subproducts exist and are validated (docs/08 §5.3) | us | all LULC-class statistics |
| 3 | **Six statistics CSVs** (§2.1) → validate → Looker Studio (§2.3) | us (+Brazil help) | launch materials, staging validation |
| 4 | **Public assets** (§3) — copy, ACL, properties | Brazil | Workspace, platform, downloads |
| 5 | **Workspace catastro** (§4) — subthemes + legends + territorial layers | Brazil support; layers ours | the platform showing anything |
| 6 | **Launch materials** (§5) — ATBD, methodology, downloads page, fact sheet, press | us + communications | 24 Sep |

Item 1 is the one with a long tail and no external dependency — **start it first**. Item 6 depends on
articulation between our team, communications and the platform team, so it needs calendar lead time
rather than compute.

---

## 2. Stage 5 — preliminary statistics

### 2.1 The six exports

Reference scripts: `2-Statistics/2-ColAnual-Products-Reference/` in the reference repo (copy them into
an `argentina/` folder, as every country does).

| Script | Computes |
|---|---|
| `toDrive-area-annual-burned-coverage` | burned area per **year × LULC class × territory** |
| `toDrive-area-monthly-burned-coverage` | idem, per **month** |
| `toDrive-area-accumulated-burned-coverage` | accumulated burned area per LULC class × territory |
| `toDrive-area-frequency-burned-coverage` | area per **burn frequency** class × LULC class × territory |
| `toDrive-area-scar-size` | area per **scar-size range** × territory (two legend levels) |
| `toDrive-area-year-last-fire` | area per **year of last fire** × territory |

Shape of each: load the subproduct, paint the territorial FC by its `id` to get a territory raster,
`ee.Image.pixelArea()` → **km² and ha**, grouped reduction over year × class × territory, join legend
metadata, `Export.table.toDrive` as **CSV** (reference folder: `mapbiomas-fuego-sudamerica`; downloaded
by hand from the Tasks tab).

`2-Statistics/1-Burned_area_products/` additionally computes the same areas for **FireCCI, GABAM and
MCD64A1** — the inter-comparison used in launch materials. Optional, but it is the standard way to show
a new collection is sane, and Argentina has no previous MapBiomas Fuego collection to compare against,
so it is worth doing.

> **Fire regions are not the statistics unit.** `regiones_fuego_*` is only used for masking and export
> geometry (docs/08 §5.2). Statistics are always per *territory* (§2.2).

### 2.2 The territorial layer — ours to build, and the real constraint

The guide is explicit: because **every subproduct × territory combination becomes a Looker Studio
table**, the number of territorial divisions must be **deliberately limited**. Its specification of the
ideal input:

> *"Capa ideal en asset: un único asset con intersección de estados, municipios y biomas con un ID único
> y una columna para cada dato."*

So: **one FeatureCollection**, whose features are the intersection of the chosen cuts, each with a
**unique `id`** and one column per attribute. Bolivia's is `bioma_depart_munic` (biome × department ×
municipality).

Argentina decisions to make (none of these exist yet):

- **Which cuts.** Provinces (`POLITICAL_LEVEL_1` equivalent) and departments are near-certain; then some
  ecological cut — ecoregions or the MapBiomas Argentina biome/region layer. Candidates to consider and
  then probably decline for v1: protected areas, indigenous territories, watersheds, and our own 5 fire
  regions (useful to *us* analytically, but they multiply tables).
- **The intersection cost.** Provinces × departments is hierarchical (cheap); adding ecoregions
  multiplies feature count, and every added cut multiplies every statistic.
- **Where it lives.** `projects/mapbiomas-argentina/assets/FIRE/AUXILIARY_DATA/…` alongside
  `regiones_fuego_argentina_v1`, and registered in Workspace as the platform's territorial layer (§4).
- **Source data.** IGN for provinces/departments; ecoregions from the accepted national layer — decide
  and record the source and vintage, since the platform will publish area numbers against it.

### 2.3 Looker Studio and the ~1 % tolerance

CSVs feed **Looker Studio** (ex-Data Studio) dashboards, one per country — see the network's
[Paraguay / Peru / Bolivia Col. 1 dashboards](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit)
(linked from the guide). Brazil can help build and organise them.

Their purpose is to enable analysis, launch materials and **validation in *staging* before the platform
is loaded**. Note the accepted discrepancy:

> Statistics are computed **in GEE, on the fly, independently of the platform**; an expected **mean
> difference of ~1 %** against the platform's own numbers is normal.

**Don't chase that 1 %.** Do check for differences much larger than that — they indicate a real problem
(wrong territory layer, wrong LULC year, missing region in the mosaic).

---

## 3. Stage 6a — public assets

Two distinct destinations, and it is worth being clear about which one the platform reads:

| Destination | Script | What it is |
|---|---|---|
| **Public GEE assets** — `projects/mapbiomas-public/assets/argentina/fire/collection1/` | `ToPublish/2-toAsset-Public` (`script_to_asset_Public`) | `copyAsset` → `setAssetAcl({all_users_can_read: true})` → `setAssetProperties({data_type, band_format, version})`. `data_type ∈ {annual, monthly, accumulated}`; `band_format` is the literal band template (`burned_monthly_{year}`, `fire_accumulated_{year1}_{year2}`, …) |
| **Cloud Storage COGs** — `gs://shared-development-storage/COLLECTIONS/ARGENTINA/FIRE/COLLECTION1/temp/…` | `ToPublish/1-toBucket-subproducts` | one **COG per band**, cast to `byte` (or `uint16` for `year_last_fire`) |

**What the platform ingests: the public GEE assets.** The evidence is the Workspace subtheme form, whose
key field is a **`GEE Asset ID`** pointing at `projects/mapbiomas-public/...`, with the
`data_type`/`band_format`/`version` properties telling the platform how to read the bands. *Inference
(not stated in the code):* the bucket COGs serve the **download page** — public download URLs are
`https://storage.googleapis.com/mapbiomas-public/initiatives/…/*.tif|.zip` — and the `/temp/` path
suggests a staging area the platform team promotes from. Brazil supplies the final direct links.

**Brazil owns this step** ("para garantizar parámetros necesarios"), so our job is to have the
`FINAL_PRODUCTS` assets correct and named exactly right, and to check the copies afterwards.

---

## 4. Stage 6b — Workspace catastro

**What Workspace is:** <https://workspace.mapbiomas.org/modules> is MapBiomas's internal metadata
registry — the admin layer behind the public platform. It is where you declare *which GEE asset* is a
given product, *how to colour it*, and *which territories* to aggregate by. Nothing appears on the
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
| **`GEE Asset ID`** | the `mapbiomas-public` asset (§3) |
| `Subtheme name` | e.g. *Annual Burned*, *Monthly Burned*, *Annual Burned Coverage*, *Scar Size* |
| `Legend` | the legend registered below |
| *"Will it be published?"* | toggle |

Subtheme names in use across countries: **Annual Burned**, **Monthly Burned**, **Annual Burned
Coverage**, **Annual Burned Natural and Anthropic Use** (Paraguay maps this one to
`accumulated_burned_coverage`), **Scar Size**, **Total Burned**. Match an existing country's naming
rather than inventing ours.

**2. Legends** — class ↔ pixel value ↔ colour, per subproduct: annual = 1 class (value 1); monthly = 12
classes (values 1–12); scar size = the **two-level** scheme (docs/08 §5.4). ⚠️ **Take pixel values and
hex colours from `Mapbiomas-Fogo-Legenda-Col4.xlsx`, never from screenshots**, and make sure the
registered scar-size ranges match the ranges we actually rasterized (docs/08 §8.6) — same pixel values,
different thresholds is a silent, invisible error.

**3. Territorial layers** — the §2.2 asset, which the platform uses for its territory selector and its
own statistics. **Our responsibility.**

Brazil supports the registration; we supply the values and verify.

---

## 5. Launch-preparation track (parallel, non-code)

From the guide, six items; all of them adapt Brazil's reference material to Argentina:

| # | Item | Notes |
|---|---|---|
| 1 | **Destacados** (key findings) + infographic | Brazil provides `Fact_Fogo_colecao4.pdf` and an infographic template |
| 2 | **Validation of the data in the *staging* platform** | our sign-off, using §2 statistics as the cross-check |
| 3 | **Website materials**: **ATBD**, methodology page, informative note | our ATBD must describe *our* method (steps 01–07), which is **not** Alencar et al. — see docs/08 §3. Peru's and Paraguay's ATBDs are the format model |
| 4 | **Downloads page** with direct links | Brazil supplies the URLs (§3); we also need a *códigos de la leyenda* page |
| 5 | **Launch event** organisation | with communications |
| 6 | **Press release** + dissemination | Brazil's example: *"Área queimada no Brasil em 2024 supera média histórica em 62 %"* |

Also available from the guide: the **brand manual + MapBiomas Fuego logos**, and Brazil's **launch
checklist** (`Checklist de demandas - Col.4 Fogo`) — worth copying as our own tracking sheet.

> **Argentina's ATBD is the one document nobody else can write for us.** Our method differs from every
> other country in the network (docs/08 §3), so the methodology page and ATBD cannot be adapted
> mechanically from Brazil's — they have to describe the burn-probability → SNIC → object-model chain,
> including the non-calendar fire-year and how it is re-partitioned into calendar years (docs/08 §6.2).

---

## 6. Open items

1. **Territorial cuts** (§2.2) — which ones, from which source layers, at what vintage. Blocks everything.
2. **Whether to run the FireCCI / GABAM / MCD64A1 comparison** (§2.1). Recommended: yes — it is the only
   external sanity check available for a first collection.
3. **Subtheme naming** for Argentina (§4) — mirror Peru's or Paraguay's exactly.
4. **Scar-size legend** must match the rasterized ranges (docs/08 §8.6) — settle before registration.
5. **Who builds the Looker Studio dashboards** — accept Brazil's offer or do it ourselves.
6. **ATBD authorship and review** — the longest-lead item on the launch track (§5).
7. **Statistics for our own fire-year objects.** Everything above is calendar-year, per the network. Our
   fire-year object database supports analyses the official products cannot (per-event size
   distributions, season-spanning fires). Worth a separate, clearly-unofficial output — but not before
   24 September.
