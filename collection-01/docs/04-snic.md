# 04 — Burned-area segmentation (fire-year SNIC)

Step 04 grows the per-pixel annual metrics of step 03 into **spatial objects** — fire scars. It
thresholds each pixel into a *seed* or a *candidate*, then lets **supervised SNIC** grow the seeds
through the connected candidate footprint, and exports one image per **fire-year** holding a
single band, `candseed`. It is the first spatial stage; steps 05–06 turn those pixels into objects
and decide which of them are fires. Read [`03-bpts.md`](03-bpts.md) first — step 04 consumes its
annual metrics.

## Foundations

**A fire is an object in space *and* time, and this step buys the time axis with a calendar, not
an algorithm.** Segmenting calendar years independently splits every scar that straddles 31
December and duplicates it across two years. The obvious repairs — a temporal firebreak inside the
segmentation, a backward gap-fill from the previous year — were built first and did not work,
because the step-03 per-pixel dates are too noisy to be a barrier
([`notes/04-snic3d_firebreaks.md`](notes/04-snic3d_firebreaks.md)). The whole problem disappears
if the year boundary is placed where almost nothing is burning: **fire-years partition the calendar, so
almost all fires belong to exactly one of them** and there is no firebreak, no gap-fill and no
cross-year de-duplication to manage.

**Seeds and candidates are how the step avoids deciding early.** A single probability cut would
force one threshold to be both sensitive and specific. Instead a permissive cut defines where a
scar *could* extend and a strict cut defines where one certainly started, and region growing
resolves the two: a candidate joins a scar only if it is connected to a seed, and a candidate
island with no seed in it is dropped. SNIC is thereby doing the classifying, and it errs toward
**recall** on purpose — precision is recovered at the step-06 object model, which can see the
patch's shape, size and seed density. The same "keep quantities, decide late" logic as the rest of
the chain ([`00-overview.md`](00-overview.md)).

## Inputs → Outputs

step-03 `bpts` images for Y1 and Y2 → **`workflow/04-snic.py`** → `candseed` asset → (`--to-asset`)
metric bands → `download_snic.py` → per-carta GeoTIFFs for step 05

| | What it is | Where |
|---|---|---|
| **in** | two calendar-year `bpts` images (Y1 and Y2 = Y1+1), mosaicked and decoded | `C.BP_TS_METRICS_COL` (+ `…_CHACO` for 1999–2009) |
| **in** | `veg_fire`, the burnable class of the previous year | `F.veg_fire_image(Y1)`, i.e. MapBiomas Y1−1 |
| **out** | one image per fire-year, single band `candseed`, masked to the segmented burned region | `C.SNIC_COL` / `snic_<fy>` |
| **out** | companion metric bands `abs_date`, `veg_fire`, `n`, `burned_around_{1,2,3}` | `C.SNIC_METRICS_COL` / `snic_metrics_<fy>` |
| **out** | the two stacked, 7 bands, int16, one GeoTIFF per *carta* | `data/snic-rasters/<fy>/` |

Everything is on the `bpts` 30 m grid over Argentina buffered ~2 km (`C.ARG_BUFFER_FC`). Each
asset is tagged `fire_year`, `partial`, and `system:time_start`/`time_end` set to its **actual**
coverage.

| `candseed` | meaning |
|---|---|
| 1 | candidate (focal fire-year) |
| 2 | seed (focal fire-year) |
| 3 | next-year candidate — Patagonia slow-dieback padding only |

Downstream reads `burned = candseed > 0`, `seed = candseed == 2`, `candidate = candseed ∈ {1,3}`.
Only burned pixels survive the mask — ~0.3–1 % of the country — which is what makes the download
tens of MB per year.

## How it works

### The fire-year

**FY Y1 = 1 May Y1 → 30 Apr Y2**, whole country, one boundary, named by its **start** year Y1 (May
2024 → Apr 2025 is "fire-year 2024"). May is the country-wide activity trough in MODIS/VIIRS *and*
in our own `bpts` mid-dates, so no region's season is cut in half: the summer burners (Dec–Apr)
and the winter–spring `centro_norte` season both fall inside one May→Apr year. Naming by Y1 only
mis-labels Patagonia's Feb–Apr tail.

`bpts` covers calendar 1999–2025, so step 04 maps fire-years **1998…2025** with two **partial**
edges: FY1998 is only the Jan–Apr 1999 tail, FY2025 only the May–Dec 2025 head. Completing them
means extending `bpts` back to May 1998 and forward through 2026.

We initially tried to define regions with their own fire-year, but getting all the country in a 
single pass brought much more advantages than the sub-optimal whole-country fire-year. 
Patagonia would ideally break in June-July, not in April-May, but it's not that bad.

### Seed and candidate

A fire-year spans two `bpts` images; at the archive edges only one exists and whichever exists is
used. For each:

- **candidate** = `delta2_peak ≥ candidate_cut` — always the K=2 form, the broadest footprint.
- **seed** = `deltaK_peak ≥ seed_cut`, with **K chosen per pixel** from `(veg_fire, n)`: a pixel
  uses `delta3_peak` where its observation count `n` reaches the class's `n_break`, else
  `delta2_peak`. A temporal-gap gate also applies (`min(jumpgap2, jumpgap3)` under an `n`-adaptive
  ceiling). Cuts are per-`veg_fire` class with global defaults; non-vegetated classes get an
  unreachable cut so they can never fire.
- **mid-date** = `date_post2 − jumpgap2/2`, converted to an **absolute day count** since epoch, so
  every later date comparison is cross-year safe.

### Window-filter and combine

Keep only pixels whose mid-date falls in `[1 May Y1, 1 May Y2)`. This is what turns two calendar
images into one non-calendar year: the Y1 image contributes May–Dec Y1, the Y2 image Jan–Apr Y2,
and a Y1 detection dated before May Y1 belongs to the *previous* fire-year and is dropped. The two
are then combined per pixel by **rank — seed (2) > candidate (1) > none (0)** (a `max`). Each
pixel's `abs_date` follows the image that won: the Y2 image only where it is strictly higher rank,
ties keeping the Y1 date.

### Patagonia dieback padding (`candseed = 3`)

Andean Patagonian forest dies **slowly** after fire, so part of a real scar first crosses the
change thresholds in the *following* fire-year. For `forest_pat` and `shrubland_pat` pixels west of
`C.PAT_LON_MAX`, a pixel that is seed-or-candidate in the **Y2** image with a mid-date in Jun–Nov
Y2 is added to the focal year as a **candidate**, coded 3, wherever the focal value is 0 — even
where it is a seed in Y2, because dieback must never *seed* a fire, only extend one. It needs no
third image: that window is already in the Y2 image. And since padding survives SNIC only where it
connects to a real focal seed, it can extend a detected scar but never manufacture one.

Whether the Patagonian **steppe** (`grassland_pat`) needs the same padding was settled downstream,
negatively: step 05 drops `candseed == 3` east of −70.6° because the steppe-edge strip is mostly
false positives ([`05-object_metrics.md`](05-object_metrics.md) "Extract"). That cut tightens
the padding's western limit rather than re-running SNIC. But this should belong here; the problem
was just detected once SNIC had already run all years.

### Supervised SNIC

SNIC is an unsupervised image segmentation method ([Achanta & Süsstrunk
2017](https://doi.org/10.1109/CVPR.2017.520), *Superpixels and Polygons Using Simple Non-Iterative
Clustering*, CVPR), and its most frequent use is to objectify (raster) a wall-to-wall image, from
uniformly placed seeds and spectral features. However, we use it defining the seed and
candidates, which is not exactly a supervised approach, but it's far more guided than the usual
application.

Seed clumps of ≤ `C.SNIC_SEED_MAX_DROP` connected pixels are demoted to candidate — they no longer
seed, but stay in the footprint so a genuine cluster can still grow through them. SNIC then grows
the surviving seeds through the whole `candseed > 0` footprint at `neighborhoodSize = 512` px;
seedless candidate islands get no cluster and fall out. Only the **mask** of the result is kept —
cluster ids are discarded, because R relabels globally in step 05 — and `candseed` is exported
masked to it.

### The San Ramón exception

The Jan–Apr 1999 San Ramón fire is very sparse ("ralo"): its `delta` is too low to raise enough
candidate footprint for SNIC to grow it. Inside `C.SAN_RAMON_RECT_COORDS`, and **only** for
fire-year 1998, the candidate rule also accepts high max-probability pixels. It is scoped that
tightly on purpose — a pmax-based candidate breaks other years and areas (valle de río negro), and
San Ramón maps largely as agriculture, so vegetation cover cannot separate it either.

### The R-facing bands and the download

`candseed` is the only band stored in `snic_<fy>`. The bands R needs are recreated by **re-running
the construction above** and masking it to the exported asset — SNIC is *not* recomputed — and
baked into the companion `snic_metrics_<fy>`: `abs_date`, `veg_fire`, `n` and
`burned_around_{1,2,3}`. Baking them once makes the download a pure pixel **read** rather than a
per-tile recompute, which empirically outran the SNIC itself. `burned_around_<r>` (pixel-level
sparseness, ported from collection-00) is a `reduceNeighborhood` **sum** of the 0/1 burned mask
over a (2r+1)² window — cheap and non-densifying in GEE, where terra densified the grid. It keeps
the collection-00 name but is a plain int16 **cell count**, so the download stays integer with no
scale factor: **R divides by (2r+1)²**.

`download_snic.py` then stacks the two and pulls the 7 bands **one carta at a time** via `geedim`,
which sub-tiles each carta to the compute-pixels limits and fetches tiles concurrently. The carta
set is the **248 cartas intersecting `C.ARG_BUFFER_FC`**, not the full ~286-sheet grid. Each carta
is clipped to its polygon so a burned pixel lands in exactly one tile, and `crs_transform` pins
every tile to the `bpts` lattice so they `vrt()` cleanly in step 05. The carta loop is not the
tiling — geedim tiles anyway — it buys a land-only footprint (Argentina's bbox is about half ocean
and neighbours), resumability, and **cross-account parallelism** through `--shard i/n`.

## Run

```bash
# stage 1 — candseed asset (tiny-ROI feasibility test first)
$PYTHON collection-01/workflow/04-snic.py --fire-year 1998 --test --launch
$PYTHON collection-01/workflow/04-snic.py --fire-year 2015 --launch

# stage 2 — the R-facing metric bands, once the candseed asset exists
$PYTHON collection-01/workflow/04-snic.py --fire-year 2015 --to-asset --launch

# the whole archive (1998..2025): ~28 whole-country tasks each, use tmux
tmux new-session -d -s snic '$PYTHON -u collection-01/workflow/04-snic.py --all --launch'

# stage 3 — pull to disk for step 05 (add --project mapbiomas-argentina under the comahue account)
$PYTHON collection-01/scripts/download_snic.py --all-years
```

Without `--launch` the script builds and sanity-checks without submitting. Both GEE stages are
idempotent: a fire-year is skipped if its asset exists or a PENDING/RUNNING task targets it; the
download skips cartas whose `.tif` is already on disk.

## Key decisions

- **A non-calendar fire-year, one boundary for the whole country.** It removes the cross-year
  problem instead of patching it; the route it replaced is shelved, not refuted
  ([`notes/04-snic3d_firebreaks.md`](notes/04-snic3d_firebreaks.md)).
- **Whole country, not regions.** SNIC's memory footprint is per internal ~256-px tile plus the
  `neighborhoodSize` buffer, **independent of export extent**, so country-wide costs what a region
  costs, and `neighborhoodSize = 512` heals the internal seams (only seed-to-candidate reach across
  a seam matters — R relabels the mask anyway). Regions stay a memory fallback should a larger
  neighbourhood ever OOM; `scripts/trial-snic_wholecountry.py` picked the value.
- **Permissive cuts.** Recall is protected here, precision at the step-06 object filter.
- **The asset stores `candseed` only.** Every other band is reproducible from the same
  construction, so storing it would duplicate state that can fall out of sync.
- **Thresholds live in `utils/constants.py`, not in the script**, so a new collection re-tunes in
  one place — but they are *tuned* in GEE JS (below).

## Gotchas

- **The seed/candidate thresholds exist in three places with no automatic sync**:
  `explore_snic_IB-02` (JS, where they are tuned by eye and hand-copied from), the Step 04 section
  of `utils/constants.py` (what production reads), and `explore_snic_IB-03`. Update all three
  together.
- **`config/snic_seed_candidate_thresholds.csv` is not live.** It holds the earlier
  data-calibrated per-veg cuts, kept as reference only; they failed out of sample and the deployed
  cuts are the by-eye globals.
- **`veg_fire` is `MB(Y1−1)` for the whole fire-year** (MapBiomas covers 1986–2024, capped at
  `MB_LIMIT_YEAR`). For a scar that actually burns in Y2 the pre-fire cover is a year stale —
  accepted, since there is no pixel-level fire-date raster to do better with at this stage.
- **A `candseed == 3` pixel carries a *next-year* date.** It must never contribute a date:
  step 05 excludes dieback pixels from every date and year statistic, and step 07 substitutes the
  parent object's date for them.
- **The edge fire-years are `partial = true`** and their `system:time_start`/`time_end` describe
  real coverage, not the nominal year. Anything that averages across fire-years has to know.

## Files

| File | Role |
|---|---|
| `workflow/04-snic.py` | the step — both GEE stages, procedure only |
| `utils/constants.py` (Step 04 section) | every threshold, the fire-year calendar, SNIC params, the ROIs |
| `scripts/download_snic.py` | per-carta tiled download to `data/snic-rasters/<fy>/` |
| `config/snic_seed_candidate_thresholds.csv` | reference only — the rejected calibrated cuts |
| `scripts/trial-snic_wholecountry.py` | the whole-country trial that picked `neighborhoodSize` |
| fuego `explore_snic_IB-02` | tunes the thresholds by eye on one calendar year — their source |
| fuego `explore_snic_IB-03` | views the production fire-year `candseed` on the fly |
| fuego `explore_fire_seasons_regions` (+ `_bpts_ARG`, `_firms_ARG`) | the monthly burn-season charts that set the fire-year boundary (source CSVs in `notebooks/`) |
| fuego `snic_regions_definition` | traces SNIC regions — only if the whole-country memory fallback is ever triggered |

The `fuego` scripts are GEE Code Editor files in a separate repo — see CLAUDE.md, "GEE Code Editor
scripts".

## Related

- [`03-bpts.md`](03-bpts.md) — the annual metrics this step thresholds.
- [`05-object_metrics.md`](05-object_metrics.md) — what R does with these pixels.
- [`notes/04-snic3d_firebreaks.md`](notes/04-snic3d_firebreaks.md) — the shelved SNIC-3D route.
- [`notes/04-vectorization_benchmark.md`](notes/04-vectorization_benchmark.md) — the FY2000
  whole-country vectorize benchmark measured across this handoff.
- `notebooks/snic_candidates_seeds_definition.qmd` — the threshold exploration.
