# 04 — Burned-area segmentation (fire-year SNIC)

Step 04 grows the per-pixel burn-probability metrics from step 03 (`bpts`) into **spatial
objects** (fire scars). Seeds and candidates are thresholded from the `bpts` metrics, then
**supervised SNIC** grows seeds through connected candidates into scar objects. Downstream (steps
05–06, in R) vectorizes, filters false positives, and builds the final products.

**Read `docs/03-bpts.md` first** — step 04 consumes its annual metrics.

Production: `workflow/04-snic.py`. Tuning/inspection tools live in the **fuego** GEE repo (see
CLAUDE.md → "GEE Code Editor scripts"), listed in §6.

---

## 1. What we tried first, and why we dropped it (SNIC-3D) — [SHELVED]

The **ideal** is a full 3D (space × space × time) clustering of the Landsat archive into fire
events — out of reach (custom clustering + the whole stack exported out of GEE).

The **first approximation** ran per-year 2D SNIC and faked the time axis with two devices:
a **temporal firebreak** (mask any pixel whose absolute burn date jumps > `D` from a neighbour, so
SNIC can't grow across two events that merely touch) and a **backward gap-fill** (import late
`y−1` pixels so a New-Year-straddling scar stays spatially whole). It **did not work well**:
step-03 per-pixel dates are too noisy, so the firebreak masked a lot of genuinely-burned area, and
without it the prev-year join leaked neighbouring fires. **Shelved, not abandoned** — worth
revisiting with more time.

- Where it lives: fuego `visualization-misc/explore_snic_firebreaks_IB-01`; original notes in
  `misc/SNIC 3D notes.odt`. The old `candseed {1,2,3,4}` encoding, the `D = f(n)` firebreak, the
  terra erode-then-restore, and the cross-year overlap-merge all belong to this shelved path.

The **current approach (below) replaces all of that** with a single time-partitioning trick: a
non-calendar fire-year. Because fire-years partition the calendar, each fire belongs to exactly one
of them — so there is **no cross-year duplication, no firebreak, and no gap-fill** to manage.

---

## 2. Current approach: whole-country, one non-calendar fire-year

- **Fire-year FY = 1 May Y1 → 30 Apr Y2**, **whole country, one boundary**, named by its start year
  Y1 (e.g. May 2024 → Apr 2025 = "fire-year 2024").
- **Why May.** May is the country-wide activity **trough** in *both* MODIS/VIIRS and our `bpts`
  mid-dates, so no region's fire season is split by the seam (summer burners Dec–Apr and the
  winter–spring `centro_norte` season both fall inside a May→Apr year). Naming by Y1 is correct for
  most of the country; it only mis-labels Patagonia's Feb–Apr tail. Analysis + the deciding charts:
  fuego `visualization-misc/explore_fire_seasons_regions` (source CSVs
  `notebooks/regions_monthly_{modis,bpts}_ee-chart.csv`).
- **Coverage.** Collection-1 `bpts` runs calendar years **1999–2025**, so step 04 maps fire-years
  **1998 … 2025**, with two **trimmed** edge years spanning the archive ends:
  - **FY1998 = jan99–apr99** (no 1998 image → only the Jan–Apr 1999 tail);
  - **FY2025 = may25–dec25** (no 2026 image → only the May–Dec 2025 head).
  Each edge asset carries a `partial = true` flag and `system:time_start`/`time_end` set to its
  **actual** coverage (not the nominal full fire-year). Completing them later means extending `bpts`
  back to May 1998 and forward through 2026.

---

## 3. The `candseed` product

`workflow/04-snic.py` exports **one image per fire-year**, a single band `candseed`, to
`…/COLLECTION-1/WORKFLOW-EXPORTS/snic/candseed_<Y1>`, on the `bpts` 30 m grid over Argentina
(`C.ARG_BUFFER_FC`), tagged `fire_year = Y1`, `partial`, and the coverage `system:time_start/end`.

| `candseed` | meaning |
|---|---|
| 1 | candidate (focal fire-year) |
| 2 | seed (focal fire-year) |
| 3 | next-year candidate — **Patagonia `forest_pat`/`shrubland_pat` slow-dieback padding** only (§4.3) |

Derived: `burned = candseed > 0`, `seed = candseed == 2`, `candidate = candseed ∈ {1,3}`,
`seed_mean = mean(candseed == 2)`. Only the sparse burned pixels survive the mask, which is what
makes the (compressed) download tiny (§5).

---

## 4. Building `candseed` for one fire-year (what `04-snic.py` does)

A fire-year spans **two calendar `bpts` images** (Y1 and Y2 = Y1+1). Either may be absent at the
archive edges (§2) — whichever exists is used.

### 4.1 Per-image seed / candidate + mid-date
For each calendar image (thresholds hand-copied from fuego `explore_snic_IB-02` — **keep in sync**):

- **candidate** = `delta2_peak ≥ candidate_cut` (K=2, the broadest footprint).
- **seed** = `deltaK_peak ≥ seed_cut`, with **K chosen per pixel** by `(veg_fire, n)` — a pixel uses
  `delta3_peak` where its observation density `n ≥` the veg's `n_break`, else `delta2_peak` — **and**
  a temporal-gap gate (`min(jumpgap2, jumpgap3) ≤` an `n`-adaptive ceiling). Cuts are per-veg with
  global defaults; non-vegetated classes get an unreachable cut so they never fire.
- **mid-date** = `date_post2 − jumpgap2/2` (K=2), converted to an **absolute day count** (days since
  epoch, using the image's calendar year) so all date logic is **cross-year safe**.

### 4.2 Window-filter, then combine (seed > candidate > none)
Keep only pixels whose mid-date falls in the fire-year `[1 May Y1, 1 May Y2)` — this turns the two
calendar images into one non-calendar year (Y1 image contributes May–Dec Y1; Y2 image contributes
Jan–Apr Y2; a Y1 detection dated before May Y1 belongs to the *previous* fire-year and is dropped).
Combine the two per pixel by **rank: seed (2) > candidate (1) > none (0)** (`max`). Each pixel's
**`abs_date`** follows the image that won the `max` (the Y2 image wins only if it is strictly higher
rank; ties keep the Y1 date). `abs_date` is built here alongside `candseed` but is **not stored in
the asset** — it is recreated at the Drive stage (§5).

### 4.3 Patagonia slow-dieback forward padding (`candseed = 3`)
Andean Patagonian forest dies **slowly** after fire, so part of a real scar only crosses the change
thresholds the *following* fire-year. For **`forest_pat` (8) / `shrubland_pat` (21)** pixels **west
of −70.3° longitude**: a pixel that is seed-or-candidate in the **Y2 image with mid-date in
[Jun, Nov] Y2** is added to the focal year as a **candidate** (code 3) where focal is 0 — even if it
is a seed there (dieback must never *seed* a fire, only *extend* one). It needs no third image: that
window lives in the Y2 image already loaded. Padding pixels survive SNIC only if connected to a real
focal seed, so it **extends** detected scars, never manufactures one. **[OPEN]** whether the
**steppe** (`grassland_pat`) needs the same padding — check in fuego `explore_snic_IB-03`.

### 4.4 Supervised SNIC → asset (stage 1, default)
`ee.Algorithms.Image.Segmentation.SNIC` grows the **seed** pixels (after a connected-speck drop of
≤5-px seed clumps) through the candidate footprint; **seedless candidate islands get no cluster and
fall out** (SNIC *is* the seed/candidate classifier). Keep the **burned mask** (cluster ids
discarded — R relabels globally), export `candseed` masked to it. `neighborhoodSize = 512`. All the
cuts/params above are in `utils/constants.py` (Step 04 section), not the script.

This is the script's **default stage**: it writes `snic_<fire_year>` (a single-band `candseed`
asset) to `C.SNIC_COL`. The idempotent launcher skips a fire-year whose asset exists or that has a
PENDING/RUNNING task.

### 4.5 San Ramón exception (fire-year 1998 only)
The Jan–Apr 1999 San Ramón fire (fire-year 1998, "jan99-apr99") is very sparse ("ralo") — its
`delta` is too low to seed enough candidate footprint for SNIC to grow it. Inside a small box
(`SAN_RAMON_RECT`), and **only for fire-year 1998**, the candidate is loosened to also accept
high-max-probability pixels (`pmax3 ≥ 0.3`). It is scoped this tightly on purpose: a pmax-based
candidate breaks other years/areas (valle de río negro), and San Ramón maps largely as agriculture
so it can't be separated by veg cover. From the `explore_snic_IB-02` Observaciones; both the box and
the cut are in `utils/constants.py` (Step 04 section).

---

## 5. Handoff to R (steps 05–06)

Object work is done in R (`terra`/`sf`) — GEE vector topology is its weak spot and objects cross
tiles. Mechanics:

- **Asset stores only `candseed`; the Drive COG carries four bands.** Stage 2, run with
  `04-snic.py --to-drive` (same `--fire-year`/`--all`/`--test`/`--launch` flags), writes an R-facing
  cloud-optimized GeoTIFF (`Export.image.toDrive`, `formatOptions={'cloudOptimized': True}`) to
  `C.SNIC_DRIVE_FOLDER` holding **`candseed` + `abs_date` + `n` + `veg_fire`**. It **reads `candseed`
  (and its burned mask) straight from the `snic_<fire_year>` asset — SNIC is NOT recomputed** — and
  recreates only `abs_date` + `veg_fire` by re-running the §4 construction, masking both to the
  asset. `abs_date`/`veg_fire` are thus computed per pixel, **not** looked up from the `candseed`
  code. `candseed == 3` flags a dieback pixel so R gives it the **parent object's** date for the
  month-of-burn raster, never its own (next-year) dieback date. The stage is idempotent: it skips a
  fire-year whose asset is missing (run stage 1 first) or that has a PENDING/RUNNING Drive task.
- **Compression is what makes the download cheap** (`cloudOptimized` → DEFLATE + tiling); burned is
  ~0.3–1 % of area, so a masked image collapses to tens of MB/yr. A plain uncompressed export is
  dense and large regardless of the mask. Drive (not GCS: the project has no CS budget).
- **In R:** `terra::vrt()` re-mosaics the auto-split GeoTIFF tiles → `patches()` for global object
  ids → per-object metrics **raster-native via `terra::zonal()`** on the id raster (no vectorizing
  first): `seed_mean` (the real fake-fire discriminator), `date_mode`, size, and a pixel-neighborhood
  **sparseness** score → vectorize once, join metrics → filter → build products.
- **Permissive SNIC by design:** loose cuts protect **recall** at segmentation; **precision** is
  recovered at the object filter (`seed_mean` + shape: real scars are compact and seeded throughout,
  noise is sparse and unseeded).
- **No cross-year de-dup.** Fire-years partition time, so each fire lands in exactly one — the
  SNIC-3D overlap-merge is gone. Output-file seams are healed by the R re-mosaic (ids are global).

### Final products
1. **Filtered fire-object polygons** (id, fire_year, area, `date_mode`, `seed_mean`, …).
2. **Per-pixel month-of-burn raster** (one band per fire-year, value = month 1–12) — **mandatory**
   for MapBiomas. Per-pixel `abs_date` is preserved end-to-end; each pixel's month/year-band comes
   from its own date, except code-3 dieback pixels which inherit the parent object's `date_mode`.

A manual ash/drought masking pass removes remaining false positives before the deliverable
(domain-expert review).

---

## 6. Tools

| Tool (fuego `visualization-misc/`, unless noted) | Purpose |
|---|---|
| `explore_fire_seasons_regions` (+ `_bpts_ARG`, `_firms_ARG`) | fire-year boundary — monthly burn-season charts, region layout |
| `explore_snic_IB-02` | tune seed/candidate thresholds by eye (single calendar year); **source of the Step 04 thresholds in `utils/constants.py`** |
| `explore_snic_IB-03` | visualize the **production fire-year `candseed`** on the fly; the steppe-padding check (§4.3) |
| `explore_snic_firebreaks_IB-01` | the **shelved** SNIC-3D firebreak experiment (§1) |
| `snic_regions_definition` | trace SNIC regions — only needed if the whole-country memory fallback is triggered |
| `scripts/trial-snic_wholecountry.py` (this repo) | whole-country SNIC trial that picked `neighborhoodSize` |
| `workflow/04-snic.py` (this repo) | **production** fire-year `candseed` export |

**Whole-country, not regions — [DECIDED].** SNIC's memory footprint is per **internal ~256-px
tile + `neighborhoodSize` buffer**, independent of export extent, so country-wide costs the same
per-tile memory as a region. `neighborhoodSize = 512` (the trial value) heals the internal seams
(only seed-to-candidate reach across a seam matters — R relabels the mask). Regions stay a **memory
fallback** only if a larger `neighborhoodSize` ever OOMs.

**SYNC:** the seed/candidate thresholds exist in three places — `explore_snic_IB-02` (JS, the
tuning source), `utils/constants.py` (Step 04 section, consumed by `04-snic.py`), and
`explore_snic_IB-03` — with **no automatic sync**. Update all three together. `config/snic_seed_candidate_thresholds.csv` holds the earlier data-calibrated
per-veg cuts, kept only as a **reference** (they failed out of sample; the live cuts are the by-eye
globals in `explore_snic_IB-02`).

---

## 7. Open questions / to-dos

- **[§4.3]** Does the **steppe** (`grassland_pat`) need dieback padding? Decide from
  `explore_snic_IB-03` (Bari 1999).
- **[§2]** Complete the trimmed edge fire-years by extending `bpts` back to **May 1998** (FY1998)
  and through **2026** (FY2025 focal + its Jun–Nov padding).
- **[§4.4]** Confirm whole-country SNIC @512 **completes** (memory) on a real fire-year.
- **[§5]** Object filter: empirical tree vs object-level model; the shape/sparseness feature set and
  cuts; the exact per-pixel (month, year-band) rule for the month-of-burn raster.
- **veg_fire is `MB(Y1−1)`** for the whole fire-year (MapBiomas covers 1986–2024, capped at
  `MB_LIMIT_YEAR`). Sub-optimal for a scar that actually burns in Y2 (its pre-fire cover is then
  stale), but there is no pixel-level fire-region raster to do better now — accepted.