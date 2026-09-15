# ROADMAP

**What to do next, in order.** This file is the *when*; `collection-01/docs/NN-*.md` are the *how*.
Read it at the start of every session, before planning anything.

**How to use it**

- Work top-down. `Now` is in flight, `Next` is ordered and its blockers are named, `Later` is
  scheduled but not yet startable.
- Each item says whether it is **run** (execute what exists) or **edit → run** (code must change
  first). That distinction is the whole point of the file — several things below look like a re-run
  and are not.
- **Update this file as you go**: tick an item when it lands, and delete it on the next pass. Git
  history is the archive; a long done-list costs every future session context it could spend on the
  work.
- [`BACKLOG.md`](BACKLOG.md) is the *unscheduled* pile, per topic, with the post-mortems. An item
  moves BACKLOG → ROADMAP when it is scheduled, never the other way.

**Dates.** MapBiomas Argentina col-3 (with fire col-1) launches **24 Sep 2026**. The factsheet is
drawn by graphic designers, so its **data is due ~Wed 16 Sep**. Ideally, assets sould be ready 
at **15 Sep 2026** for Brazil to copy them to `mapbiomas-public`.

---

## Now — the burnable denominator, and the factsheet off the toolkit's numbers

> **Goal: have real numbers to analyse for the factsheet on Tue 15 Sep.** What is left on our side
> is **one small GEE export** plus local R. Nothing here waits on a product asset.
> **Scope: ecoregion only** — departamento and provincia are December (docs/09 §1.2).

**The strategy changed again on 14 Sep, and it shrinks this section.** We are **not** computing the
burned-area cross-tab. The split is now (docs/09 §4):

- **The numerator — burned area by month × year × ecoregión × LULC — comes from the network's
  toolkit**, run with **our 13-class ecoregion vector** registered in it:
  `…/ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`. **Hand them the vector,
  never the `_r` raster** — the raster numbers the regions alphabetically and the vector does not, so
  six of thirteen ids disagree and Monte's 47 Mha decodes as Pampa (docs/09 §5.1, measured 14 Sep).
- **The denominator — burnable area per ecoregión — is ours**: one constant layer, the **mode of the
  col-3 burnable classes over 1998–2024**, reduced as `eco13·10 + burnable`. 26 rows, one task,
  minutes. Same programming strategy as their app (docs/09 §4.2–§4.3).
- **The fire counts stay local**, off the object database, and never touch Earth Engine (docs/09 §8.2).

⚠️ **The open dependency: which asset their dataset reads.** The toolkit's datasets normally read the
**published `*_coverage` subproducts** — which are exactly the nine that are not exported yet. If
that is how it is configured, the numerator waits on 07d (Brazil's help, "After"), and Tue 15 Sep is
tight. If instead the dataset is defined against the **month-of-burn collection + col-3 LULC**
(27/27, landed, what our own table was going to read), it can run today. **Settle this in the same
message as the territorial layer** — it is the one thing that decides whether the factsheet's
numerator exists this week.

The nine subproducts (07d) were launched 00:21 and **cancelled 13:05**; they are not on the path to
any factsheet number, and **Brazil is now helping export them** — see "After". `A2` is paused in the
supervisor (`logs/v2-driver/A2.pause` — delete that file to resume; the board shows ⏸ and prints the
reason). The nine were cancelled cleanly: 9/9 confirmed `CANCELLED`, nothing else left PENDING or
RUNNING in `mapbiomas-argentina`.

### What exists already — 14 Sep 13:10

| What | Where | State |
|---|---|---|
| **Month-of-burn rasters** (07a) | `collection1_fire_mask_v2/…_<year>` | ✅ **27/27**, all carrying the current rule A. 2002 landed 00:16. **This is what the toolkit's numerator reads.** |
| **Fire-object polygon layer** (07e) | `FINAL_PRODUCTS/burned_area_polygons_v2` | ✅ exported, `--verify` green on all 28 fire-years, `--set-props` written. **1,012,648 rows / 63,328,585 ha** |
| **Calendar scar packages** (07b, local) | `data/scars-upload-cache/` | ✅ 27 zips, 739 MB, gate green — **awaiting the manual ingest ("After")** |
| **The nine subproducts** (07d) | `FINAL_PRODUCTS/` | 🟡 **4 of 9 landed — Vera is exporting them.** `annual_burned_v2`, `monthly_burned_v2`, `annual_burned_coverage_v2`, `monthly_burned_coverage_v2`, 27 bands each, verified 14 Sep. Our own launch stays paused; see "After" |
| **The three scar rasters** (07c) | `FINAL_PRODUCTS/` | 🟡 **3 tasks in flight since 15 Sep 03:04**, launched by `watch_07c.py` over **all 27 calendar years** as comahue. Follow them on `logs/v2-driver/C3-watch.md`; the driver runs the C4 check when they land |

Everything is **`_v2`, replaced in place**. There is no `_v3`; the asset paths and
`C.PRODUCT_VERSION = 2` do not change. (Why v2 was rebuilt at all: the first run shipped an
unconfined rule A that deleted two thirds of the Delta del Paraná. Fixed in 8032aa2 — rule A now
also requires `area_ha < 150` and intersection with `config/rule_a_aoi.geojson`. Settled; docs/07
§1.1 and `git log`.)

**The area total is confirmed twice, independently — do not re-derive it.** The local scar build
(pure R, never touches Earth Engine) totals **63.24 Mha**; 07e's `--verify` on the landed asset
reports `area per OBJECT` = **63.33 Mha**. The gap is fire-year vs calendar-year partitioning, as
expected. **When reading 07e's `--verify`, never quote the ROW sum** (68,447,098 ha) — vertex-split
parts are one row each, and object `2000_57529` alone over-counts by 5.1 Mha.

### What is left to write, and what it must copy

**[docs/09](collection-01/docs/09-statistics.md) is the build spec — read it before writing a
line.** Our one export is small, but it copies the app's shape exactly (docs/09 §2): the crossing
packed into the pixel value, territory painted and never intersected, a `bounds()` rectangle as the
reduction geometry, no `tileScale`, one task. The three divergences are deliberate and listed in
§2: the pinned grid (`crs` + `crsTransform`, never `scale: 30`), Python instead of JavaScript, and
`Export.table.toDrive` instead of their GCS bucket.

Two things about the join, because they are what a wrong number will come from:

- **Both sides must key on the same 13 ids** — theirs and ours (docs/09 gate 2). Check the *names*,
  not the count.
- **The denominator no longer varies by year** (docs/09 §4.4). `%` now means "of the area that is
  burnable most of the time", which makes the series a pure fire signal — and makes a `%` over 100
  arithmetically possible. Say it in the footnote; check it in gate 4.

### The work

### ▶ RUN THIS: the toolkit app, interactively (Iván)

**Reviewed 14 Sep — Vera's Argentina toolkit is real, it already carries our ecorregiones, and it
works.** `toolkit/v03/argentina/territories/ecorregiones.js` reads
`ARG-Political_Level_2-13Ecorregiones_3857`, keys on `GEOCODE`, names from `LEVEL_2` — exactly the
layer we asked for, and the `ee.Number.parse()` it does on a numeric `GEOCODE` is harmless (tested).
Export goes to `gs://mapbiomas-fire`, and **we have write access** (`storage.objects.create`
granted — that closes docs/09's open question).

**One thing was wrong, and is fixed in a copy of ours.** Their `_shared/lulc_base.js` reads the
PUBLIC `_v1` assets, where **`annual_burned_v1` and `monthly_burned_v1` do not exist** — the two the
factsheet needs — and where v1 is the superseded mapping anyway (unconfined rule A, the Delta del
Paraná bug). So run **our repointed copy**, which reads our `FINAL_PRODUCTS` `_v2` (`dc02097f` in
the `fuego` repo):

```
users/mapbiomas-arg/fuego:collection-01/statistics/apps/fuego_col1.js
```

Open that script in the Code Editor and press **Run**. The panel is "Herramienta de Análisis de Área
— Fuego Col. 1 (Argentina)".

- [ ] **Tick exactly these boxes.** *(run)* Under **1. Select Layers for Statistics** open the
      **▶ Fuego** group and tick:
      | box | gives | the factsheet needs it for |
      |---|---|---|
      | **Área Quemada Anual** | `Área ha`, `Ano`, `Situación`, `Ecorregión` | analyses 1 and 2 — the burned-area numerator per year |
      | **Área Quemada Mensual** | + `Mes`, `Mes_id` | analyses 3 and 4 — the pirogram and the intra-annual shape |

      Optionally, under **▶ Fuego + Uso y Cobertura**, **Área Quemada Anual + Uso y Cobertura**
      (adds `Nivel 0/1/2`) — only if we go ahead with analysis 1's per-class panel, and read the
      caveat below before promising it.
      **Leave the other four unticked**: *Frecuencia*, *Área Quemada Acumulada*, *Tamaño de
      Cicatrices* and *Año del Último Fuego* still point at **v1** in our copy, because they have no
      v2 yet. The app would export them happily and the numbers would be wrong.
      Under **2. Select Territorial Units** tick **only "Recorte por Ecorregiones"** — September is
      ecoregion-only (docs/09 §1.2); País and Provincia are December.
      Then press **Export Selected Layer Statistics Tables** — it *creates* one task per
      (layer × unit) in the **Tasks** tab. **They do not start themselves: press RUN on each.**

      // comment de Iván: también tildé [Fuego + Uso y Cobertura > Área Quemada Anual + Uso y Cobertura]
      // Y le pedí por ecorregión y por provincia (aunque no sé si están las provincias en el dataset.)

- [ ] **Collect the CSVs.** They land in
      `gs://mapbiomas-fire/data-container/stats/mapbiomas_fuego_argentina_collection1/Ecorregiones/`
      as `annual_burned_Ecorregiones.csv` and `monthly_burned_Ecorregiones.csv` (task descriptions
      `MBFUEGO_ARG_COL1-*`). Columns: **`Área ha`, `Ano`**, the layer's own columns, then
      **`Ecorregión`**. Drop them in `collection-01/data/statistics/` as `burned_toolkit_annual.csv`
      / `burned_toolkit_monthly.csv` — that is what the factsheet code reads (docs/09 §1.1).
- [ ] **Then join to the denominator and check gate 2** — the 13 ids and names must be identical on
      both sides ([docs/09 §7](collection-01/docs/09-statistics.md)). Ours is
      `data/statistics/burnable_eco13.csv`, already computed.

**Three things to know about what comes out** (docs/09 §4.1):

- **The LULC cross is PREVIOUS-year in our copy** (`fuego` 742b23a3). Upstream pairs
  `burned_area_<Y>` with `classification_<Y>`; ours pairs it with `classification_<Y−1>`, because
  the same-year class of a burned pixel is partly a *consequence* of the fire. Only
  `annual_burned_coverage` is shifted — frequency and accumulated keep same-year, since their band
  names end in the last year of a multi-year window. **The published `*_coverage` assets are
  untouched and stay same-year**, so the CSV and the product disagree by construction: say which one
  a figure used (docs/09 §4.1.1).
- **There is no monthly × LULC dataset** in their app, even though our
  `monthly_burned_coverage_v2` asset exists. Month and land cover cannot be crossed through this
  route; the pirogram is month-only.
- **They reduce at `scale: 30`**, not our pinned `crsTransform`. Same pixel size on this lattice, a
  sub-pixel phase shift (docs/09 §3) — fine for these numbers, and not worth asking them to change.

- [ ] **Tell Vera three things** *(Iván)*, two of which would let us delete our copy:
      1. **Their `lulc_base.js` should point at `_v2`** (or v2 should be published to
         `mapbiomas-public`) — as it stands, `annual_burned_v1` and `monthly_burned_v1` do not exist
         there at all, and the v1 that does exist is the superseded mapping.
      2. **Argentina's `annual_burned_coverage` should cross the PREVIOUS year's land cover**, not
         the same year — a fire consumes what was there *before* it burned, and the same-year class
         of a burned pixel is partly a consequence of the fire. We have made that change in our copy
         (`alignThemeToFirePrevYear`, `fuego` 742b23a3) and it is a one-line helper she can lift.
         If the network wants same-year everywhere for comparability, fine — then it stays a
         documented divergence on our side and the factsheet says so (docs/09 §4.1.1).
      3. Their `datasets/fuego_col1.js` has `band_pattern: 'fire_frequency_1995_{year}'` where the
         base module selects `fire_frequency_1999_.*` — a 1995/1999 mismatch that will bite whoever
         exports frequency.
- [x] **Build `collection-01/statistics/`** — `legends.py` (class lists, status codes, the 13
      ecoregion names, the 16→13 crosswalk) and `burnable_export.py` (`--test-rect`, `--regions`,
      `--export`, `--status`). `ECOREGIONS13/16`, `ECOREGION_ID_PROPERTY` and `STATS_DRIVE_FOLDER`
      added to `utils/constants.py`. docs/09 §4 matches the code.
- [x] **The Córdoba rectangle test** — 42,156.3 ha reported against a 42,191.8 ha rectangle
      (**99.92 %**, the gap is boundary pixels) and **99.92 % burnable**. 7 s. docs/09 §4.5.
- [x] **Export the burnable denominator** — `eco13·10 + status` over 1998–2024 on the pinned grid,
      one task → **Drive `gee_fire_stats` (gmail account)**. The table is also written locally by
      the same script, so nothing waits on Drive: `data/statistics/burnable_eco13{,_raw}.csv`.
- [x] **The denominator is computed and gated** — 252.25 Mha burnable of 280.73 Mha (89.9 %),
      burnable ≤ region area in all 13, raster vs polygon within 0.2 %. Table in
      [docs/09 §4.7](collection-01/docs/09-statistics.md).
- [ ] **⏳ AWAITING IVÁN'S REVIEW — what the factsheet says about the Delta e Islas del Paraná.**
      Raised 14 Sep, not yet decided; nothing else is blocked by it, but the Delta cannot be drawn
      until it is. **1.53 Mha —
      27 % of that ecoregion — is "never observed"**: col-3 does not map the open water of the Paraná
      and the Río de la Plata, so it is excluded from the denominator (correct per docs/09 §6). The
      Delta's `%` therefore runs on **3.50 Mha, not 5.61 Mha**, which is ~60 % higher than a reader
      would compute off the region's map area. If the Delta appears in the factsheet, that sentence
      goes in the caption. Every other region's never-observed area is under 10 kha; ties are 268 ha
      nationally.
- [ ] **Run the remaining gates once the toolkit's numerator exists**
      ([docs/09 §7](collection-01/docs/09-statistics.md)): gate 2 (both sides key the same 13 ids,
      checked by NAME), gate 4 (denominator ≥ numerator, every ecoregion × year) and gate 6
      (national burned vs the object database). Gates 1, 3 and 5 are already run — see the per-region
      table in `collection-01/logs/burnable_regions.log`.

## Next — the factsheet datasets

From the toolkit's table, our burnable table and the local vectors. No Earth Engine.

- [ ] **Regenerate the fire-count tables: final filters, each fire ONCE, by CALENDAR year.**
      *(edit → run)* Three changes at once ([docs/09 §8.2](collection-01/docs/09-statistics.md)):
      the object selection changed, so the existing CSVs are stale; a fire is now counted in the
      single region containing its **centroid**, not in every region it touches; and a fire is filed
      under the **calendar year and month of `date_median`**, not under its fire-year — everything
      the factsheet reports is calendar-year. The centroid tags already exist
      (`regions_<fy>_one.csv`), so the work is to switch the consumer to them and **drop the
      `_multi` path from both script and doc**, not to leave both. ⚠️ **A calendar year needs both
      of its fire-years**, so read all 28 files first and aggregate after — never per file. Move
      `scripts/factsheet_object_stats.R` in as `statistics/fire_counts.R`, writing
      `data/statistics/fire_counts_by_month.csv` + `fire_region_summary.csv`. Local R, minutes.
- [ ] **Build the four analyses** from the toolkit's table + `burnable_eco13.csv` + the counts —
      [docs/09 §8.1](collection-01/docs/09-statistics.md), content plan in
      [docs/10](collection-01/docs/10-factsheet_design.md): mean annual burned proportion; the time
      series and its GAM trend; the pirogram (area half from the toolkit, **count half from the
      objects**); the intra-annual shape normalised per region. **Analysis 1's per-LULC-class
      variant is not computable** from these tables (docs/09 §4.4) — decide whether to drop it or to
      pay for one more small export, before it is promised to the designers.
- [ ] **State the three divergences in the footnote.** Everything reported is **calendar-year** —
      the fire-year is how the mapping is organised, not how anything is published. What differs is
      how each side files a fire: (i) rasters assign year and month **per pixel** from `abs_date`,
      the count side **per object** from `date_median`, so a fire straddling 31 December is split in
      one and filed whole in the other; (ii) "area burned in month M" is a pixel sum on one side and
      a whole-object assignment on the other; (iii) the denominator is a **27-year modal burnable
      area**, not that year's. Acceptable — say all three out loud.

## Then — the factsheet plots

- [ ] **Draw the plots** off those datasets, in `statistics/factsheet_plots.R`. There is no
      plotting script yet: the pair pushed in ccc0f08 was written against the old object selection
      and has been deleted (3f494b4). What survives from that commit is the content plan in
      [docs/10](collection-01/docs/10-factsheet_design.md) — the multi-region conventions (colour
      per region, the little map as the legend, `all_regions` vs focal variants), §4's intra-annual
      distribution normalised per region, and §2's interannual series in "veces el año típico".
      Figures land in `data/statistics/figures/`. Data is due to the designers **~Wed 16 Sep**.
- [ ] **Decide what the factsheet says about the Delta** — the same shape of question as the Pampa
      below, and **also waiting on Iván**: 27 % of that ecoregion is unmapped open water, so its
      denominator is 3.50 Mha, not 5.61 Mha. Full statement in the "Now" section above and in
      [docs/09 §4.7](collection-01/docs/09-statistics.md).
- [ ] **Decide what the factsheet says about the Pampa.** Still open, and it needs a call before the
      16th. The Pampa is largely cropland; after the filters its total is still built partly on
      residual cropland pixels (1.37 Mha nationally at `T_AGRI = 0.4`). Candidate framings: report
      it on non-agricultural land only (restricting the denominator the same way); report both and
      make the gap the story; call it an upper bound; or drop the panel and keep it for the December
      Bariloche launch. It is legitimate to show something that is not a straight read of the
      platform — but it has to be said out loud.

## After — finish the v2 product exports

Publication, not analysis. Picks up exactly where 14 Sep 13:05 left it.

**Brazil is helping with this half (14 Sep).** They are exporting the remaining fire subproducts
from our `FINAL_PRODUCTS` — the same reference code, run on their side, which is what takes 07d off
our critical path. **The exception is everything on the scar-size side**: `annual_burned_scar_id`,
`annual_burned_scar_area` and `annual_burned_scar_size_range` (07c) are gated on **the manual ingest
of the 27 calendar-scar packages, which only Iván can do** — nobody can unblock those for us. So the
first item below is still the one that matters, and it is still ours.

- [x] **Ingest the 27 calendar-scar packages by hand** — *Iván uploaded all 27 on the night of
      14-15 Sep.* Everything after the upload is now automatic, and **the 2-min watcher
      `collection-01/scripts/watch_07c.py` owns it** (cron `*/2`, plus `@reboot`; board:
      `collection-01/logs/v2-driver/C3-watch.md`). Per tick it:
      1. stamps `exclusion_rule_a` / `exclusion_rule_b` on each ingested FeatureCollection — a
         **property, not a filter**: the scars were already built from the filtered object set
         (docs/07 §1.1). The write MERGES the existing block, because
         `updateAsset(..., ["properties"])` replaces the whole dict;
      2. runs `validate_scar_zips.py --ingested` as the gate **before** the launch (feature count,
         `area_ha` total, numeric `scar_id`), dropping any year that disagrees with the local build;
      3. launches **07c** — the three scar rasters — **as comahue on `mapbiomas-argentina`**, so
         the gmail queue and the fire project stay free for the statistics exports
         (`MBFUEGO_ARG_COL1-*`), which need GCS write access comahue does not have;
      4. confirms the submission **on the server**, not from `rc=0`, and writes `C3.done`.

      Driver stage C3 is **paused** (`logs/v2-driver/C3.pause`) while the watcher owns the launch —
      both take the same `tick.lock`, so the two can never submit at once. Stage C4 (the
      scar-vs-month check on the landed assets, `C4-check.out`) still belongs to the 15-min driver.

      **If a year's ingest failed, the watcher launches without it** (Iván, 15 Sep: "run the
      following steps with the available years, and I run tomorrow only the remaining ones"): a
      hard 60-min deadline, or 25 min of no ingest in flight, whichever comes first, and a floor of
      20 of 27 years below which it refuses and shouts instead. A partial launch writes
      **`logs/v2-driver/C3-PARTIAL.md`** — which years are missing and the exact delete + re-export
      needed to complete the series — and the three assets carry `partial` and an explicit `years`
      list of their own. Completing them is a full re-export: a band cannot be added to a landed
      image.

      **It ran, and it ran complete — 15 Sep 03:04.** All 27 FCs ingested (2008 and 2009 were
      cancelled and re-uploaded at 02:30 and landed at 03:02), all 27 stamped, the gate green on
      **27/27 MATCH** against the local build with `scar_id` still numeric, and three tasks
      submitted: `arg07c_annual_burned_id`, `arg07c_annual_burned_area_ha`,
      `arg07c_annual_burned_scar_size_range`. No partial, so `C3-PARTIAL.md` does not exist —
      **if you see that file, read it first.**

      Nothing was ingested from the broken run, so **there was nothing to delete in GEE here**.

- [x] **The three scar rasters landed and verify.** 15 Sep, 06:30 / 07:10 / 09:03 local. 27 bands
      each, 1999-2025, no gaps, `partial` absent, band naming per `band_format`. C4 (stage C4,
      Chaco box) is **green on both years: `month-only 0`, `scar-only 0`**, and the 2020 pixel
      count is identical to the month mask's (26,303). The watcher is retired — its cron lines are
      gone and `C3.pause` is deleted.
- [ ] **⚠️ THE LAST THING BETWEEN "EXPORTED" AND "PUBLISHABLE": reconcile the property sets
      BEFORE anyone runs `audit_product_properties.py --apply`.** *(edit → run; re-measured 15 Sep,
      all twelve v2 products now exist and their blocks are in **three** different states)*

      | block | products |
      |---|---|
      | the platform's trio only (`data_type`, `band_format`, `version`) | `annual_burned`, `monthly_burned`, `annual_burned_coverage` |
      | **completely EMPTY** | `monthly_burned_coverage`, `frequency_burned`, `frequency_burned_coverage`, `accumulated_burned`, `accumulated_burned_coverage`, `year_last_fire` |
      | ours (`source`, `region`, `years`, `exclusion_rule_a/b`, `band_format`, …) but **no** `data_type`/`version` | the three scar rasters |

      `audit_product_properties.py` covers only the **nine** — the three scar rasters are not in its
      `SPECS` at all, and nobody has said what `data_type`/`version` should read on them (ask Brazil
      with the docs/09 §13 list). The two half-truths that combine into a silent publication break:
      1. **Vera's exports carry the PLATFORM's properties** — `data_type`, `band_format`, `version`
         — on `annual_burned_v2`, `monthly_burned_v2` and `annual_burned_coverage_v2`.
         **`monthly_burned_coverage_v2` carries none at all.**
      2. **Our audit script's canonical set does not include `data_type` or `version`**, and it
         writes with `updateFields=["properties"]`, which **REPLACES the whole dict** (its own
         docstring says so). So `--apply` today would *strip* the platform's properties from the
         three assets that have them — and `data_type`/`band_format`/`version` are exactly what the
         platform reads to open the bands (docs/09 §10).
      The 18:46 driver tick ran it **dry**, which is why nothing is broken yet; the driver never
      passes `--apply`. Fix: add `data_type` and `version` to `SPECS`/`want` in
      `audit_product_properties.py` so the canonical set is the UNION of ours and the platform's,
      re-run dry, confirm the only remaining lines are `~ set` (no `- drop`), then apply once.
      Keep `lulc_year = "same calendar year as the burn"` on the coverage assets — that property is
      where the published product records the distinction from our own previous-year statistics
      (docs/09 §4.1.1).
- [ ] **Settle with Brazil which of the nine they export, then resume the rest.** *(run)* They are
      helping with 07d, so the first move is to agree the split explicitly — then
      `rm collection-01/logs/v2-driver/A2.pause` and the next tick resubmits **whatever is left to
      us**. Encodings are copied verbatim from the network's reference — **do not innovate there**
      (docs/07 §12). The audit then runs automatically and leaves `A3-check.out` and `A3-props.out`
      — **read them, they are not self-checking.** ⚠️ **Do not let both sides export the same
      subproduct**: the in-flight check is project-scoped and would not see their task, which is the
      same failure mode as the two-account split below.
- [ ] **Watch the throughput, and split across accounts if it repeats.** On 14 Sep only **one** of
      the nine ever started: 12 h at 36 %, eight stuck `PENDING` behind it, with the project
      otherwise idle (one soy task and a table ingest all day) — so it was a concurrency cap, not
      contention. The queue is **per user**, and `mapbiomas-fire-485203` had **0 running**, so the
      lever is to submit some of the nine as **gmail** on the fire project alongside comahue's; the
      destination asset path is unaffected (CLAUDE.md). **The trap:** the in-flight check is
      project-scoped, so a naive relaunch on the other project does not see the first project's
      tasks and would run duplicates into the same asset. Split the list explicitly, do not
      relaunch the same list twice.
- [ ] **Run the five remaining network tables** once the four `*_coverage` + `year_last_fire`
      products exist, and `toDrive-area-scar-size` **after** the scar ingest above. They **cannot
      agree with the factsheet's numbers by construction** (same-year LULC, burned-only rows, and a
      per-year denominator vs our 27-year modal one); say so in the CSV hand-off. docs/09 §9.

## Still owed to people

`burned_area_polygons_v2` was replaced in place on 12 Sep 17:46, so the link early users already
hold still works — but the layer under it moved from **908,346 rows / 58.05 Mha** to
**1,012,648 rows / 63.33 Mha**. **Tell them the numbers changed**, not merely that v1 is
superseded: anyone who already quoted a total from that layer quoted one ~8 % low.

## Operating notes for whoever picks this up

- **The compute project is shared with the whole MapBiomas Fuego network.** `listOperations()`
  returns every country's tasks. Never cancel or reason about a task you did not launch; match only
  on our namespaced prefixes (`mob_`, `arg07d_`, `arg07e_`, `arg07c_`).
- **A wedged GEE task is a real failure mode, and the supervisor now breaks it by itself.** One
  2002 export ran **37 h** frozen at `14/18` work units while every other year finished in 42–54
  min. Settled, do not re-derive. Two things about the fix are worth knowing before touching it:
  **GEE serves a task's current progress but no history**, so last tick's reading lives on disk in
  `logs/v2-driver/mob-progress.json`; and **`updateTime` is not the signal** — the server refreshes
  it on a stalled task too. Only the work-unit count is real. `mob_` tasks flat for 2.5 h are
  cancelled and resubmitted (3 kills max); **07d/07c tasks are shown on the board but never
  auto-cancelled**, because 27 measured healthy `mob_` runs calibrate that threshold and nothing
  calibrates theirs. Tested by `scripts/test-07-v2_driver_stall.py`.
- **A paused stage is not a finished one.** `<stage>.pause` in `logs/v2-driver/` skips a stage and
  shows ⏸ on the board with its reason. It is deliberately **not** a `.done` file — a marker that
  claims a success which never happened is the bug this repo hit three times in Sep 2026.
- **The driver's logs are append-only across runs.** A bare `grep '\[C2\] rc='` matches *last
  night's* line; a `grep '23:3[0-9]'` matches a previous day's tick. Anchor every check on today's
  timestamp, on a line count taken before you start, or on the live process.
- **A marker is not evidence.** Three bugs in Sep 2026 were the same shape: a `.done` file or a gate
  asserting a success that was not real. All fixed — but distrust the pattern. When a run is
  invalidated, its markers are as stale as its assets: clear **every** `*.done` and `*.tries`.
- **Verify a launch on the server, not from `rc=0`.** The 00:21 subproduct launch was confirmed by
  listing nine `arg07d_*` operations, not by the launcher's exit code.

## Later — hand-off and cleanup

- [ ] **Tell Brazil the assets are ready, and work the question list** in
      [docs/09 §13](collection-01/docs/09-statistics.md) — whether the public asset ids stay the
      same, the real deadline, whether they need our CSVs at all now that we export to Drive, and the
      coarse-read over-reporting warning that affects every country. The `crsTransform` patch is now
      a Python implementation of `core/`, so offering it back means handing them a diff against their
      JS, not a branch. Say so plainly; the grid fix still matters to them.
- [ ] **The departamento / provincia cut — December, not September.** The finer cut for the
      Bariloche launch, on both sides of the ratio: the packed `ecoregion16·100000 + GEOCODE`
      territory id and the masking rule that comes with it are written down in
      [docs/09 §5.4](collection-01/docs/09-statistics.md) so nothing is re-derived, and the 16 → 13
      ecoregion crosswalk (exact, measured) is in §5.2. Province falls out of the department layer;
      no second asset. Note the `Stats-Arg_political_level_*` names are Latin-1 damaged and the
      16-class `GEOCODE` is a string — both bite here, not in September (docs/09 §5.1).
- [ ] **Delete the dead step-11 code** once the toolkit route is verified end to end:
      `workflow/11-burnable_area.py`, `workflow/11-burned_area_stats.py`. Both are superseded —
      [docs/09](collection-01/docs/09-statistics.md)'s opening note.
- [ ] **Fix the stale doc pointers in code comments.** Two generations of drift now. (a) The
      **validation doc moved 10 → 11** on 14 Sep (`docs/10` is now the factsheet design), so every
      `docs/10 §…` in `collection-01/validation/*.py` and `scripts/10_burned_area_by_fire_year.py`
      means **docs/11**. (b) The older one: `docs/11-*.md` as cited by 24 `docs/11 §…` references in
      five files no longer exists at all. `07-month_of_burn.py` (6) →
      [docs/07 §1.1](collection-01/docs/07-vector_to_raster.md) for the rules and
      [docs/09](collection-01/docs/09-statistics.md) for the TESTS/ notes;
      `factsheet_object_stats.R` (4) and `objects_region_tag.R` (3) → docs/07 §1.1 for the filter,
      [docs/09 §8.2](collection-01/docs/09-statistics.md) for the fire-count family. The 11 in
      `workflow/11-*.py` need no fixing — those two scripts are deleted by the item above.
- [ ] **Delete the `FIRE/COLLECTION-1/TESTS/` asset folder** when the September work is done. It
      holds only benchmark assets. Deletions are Iván's to run.

## Not on the critical path

Running in parallel, nothing above depends on them: validation
([docs/11](collection-01/docs/11-validation.md), and the open items in
[`BACKLOG.md`](BACKLOG.md)), the ATBD and methodology page, and the December Bariloche launch
materials.
