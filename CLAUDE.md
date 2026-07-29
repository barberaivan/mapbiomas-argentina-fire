# CLAUDE.md

Guidance for Claude Code (and any contributor) working in this repo. Durable operating
rules only — for status and pending work see `collection-01/BACKLOG.md`; for design detail
see the per-step notes in `collection-01/docs/` (below).

## Primary focus

**Active development is almost always in `collection-01/`, running scripts from
`collection-01/workflow/`.** Default to `collection-01/` context unless told otherwise.
Collection 0 (`collection-00/`) is the completed Patagonia pilot — reference, not active work.

## How this repo is documented — read the right file

Documentation is modular. **Most development notes live in `collection-01/docs/`, one file
per workflow step**, numbered to match the step (numbers repeat when several topics belong to
one step, e.g. the remap and the fit are both inputs to step 02):

| Doc | Covers |
|---|---|
| `collection-01/docs/01-training_data.md` | step 01 — training-data export, labels, inputs |
| `collection-01/docs/02-vegetation_remap.md` | the `veg_fire` fire-class remap (input to step 02) |
| `collection-01/docs/02-data_cleaning.md` | the `fit`-column cleaning gate (input to step 02) |
| `collection-01/docs/02-model_fitting.md` | step 02 — elastic-net LR fitting |
| `collection-01/docs/03-bpts.md` | step 03 — burn-probability time-series metrics: full design, implementation + GEE array gotchas |
| `collection-01/docs/03-colab_multi_export.md` | step 03 — distributed multi-account export via Colab (admin notes) |
| `collection-01/docs/04-snic.md` | step 04 — burned-area segmentation: the whole-country **non-calendar fire-year** SNIC (fire-year `candseed` construction, Patagonia dieback padding, supervised SNIC, Drive-COG handoff to R); the shelved SNIC-3D attempt in brief; the `explore_snic_IB-0{2,3}` GEE tuning/inspection tools |
| `collection-01/docs/05-object_metrics.md` | step 05 — fire-object vectorization & metrics (R/terra): the 1-px dilation connectivity hack, per-object raster metrics (veg abundance, area, `abs_date`/`n` summaries, sparseness) + geometry shape metrics ported from collection-00; sparse igraph labelling vs terra fallback; **§4** the outputs (`data/snic-rasters/` → `data/objects-raw/`, geometry/metrics split) and **§4.1** the overnight all-years batch launcher (`scripts/run_05_years.sh` + `scripts/mem_monitor.sh`) |
| `collection-01/docs/06-object_model.md` | step 06 — object-based fire/non-fire classification. Opens with **"Files, directories and scripts"** — the step-06 data layout (`objects-labels/`, `objects-pred/`, `objects-analysis/`, the regenerable `*-cache/`) and what each script is for; then label collection in GEE (drawing layers → one asset per collaborator) and their join to objects; the **probit BART** fit (`stochtree`) with posterior probability bounds; the 20 predictors (incl. 5 aggregated vegetation fractions) and **§4 why no predictor may identify the year or proxy for it** (the `fire_year`/`year_calendar` label-prevalence leak, the `n_mean` era proxy, and the two metrics collection 2 should stop computing); **§5 the three call columns** (`fire_model` / `fire_tag` / deployed `fire`, and why `-1` not `NA`); the per-size-band **classification threshold** (Youden's J out-of-fold); **grid-blocked CV** and why the fold design decides the answer; **§8 importance + ALE**; **§11 QGIS inspection** without a GEE upload; **§12 the upload** — all 28 fire-years, whole object set, zipped Shapefiles + the validation gate |
| `collection-01/docs/07-vector_to_raster.md` | step 07 — **everything Argentina builds**, in four sub-steps **07a–07d** with an explicit order-of-operations table and run commands at the top (07a month of burn ✅, 07b local scars ✅, 07c scar rasters, 07d **the nine derived subproducts** — §12: the encodings copied from the reference, the four settled answers, the four traps, the LULC-on-our-lattice verification and the pre-launch decode audit). Also covers the ONE pinned grid (`crsTransform`, never `scale=30`) and the col-0 lattice collision; the verified calendar-year partition; the **`candseed==3` parent-date substitution** (881 k px / ~79 kha, and why it protects the scar product); why the LULC mask + solitary-pixel filter are **already embedded upstream** (verified: zero candidates on non-burnable `veg_fire`); the proof that polygon paint/rasterize reproduces the object pixel set **exactly**; and why `terra::cells()` is the right membership tool |
| `collection-01/docs/08-postprocessing.md` | step 08 — the **MapBiomas Fuego network-wide post-processing** (stages 1–4: the GEE assets), identical in every country and summarised from the network's [*Guía del Proceso de Lanzamiento*](https://docs.google.com/presentation/d/1Y5SUeS_405k5zZkBX4z6BDaC_umI8Saiguk7coITB1Q/edit) (§1 gives the `curl …/export/pdf` recipe to read the slides as a PDF): LULC masking + month coding, the `FINAL_PRODUCTS` subproducts (annual/monthly burned, burned coverage, frequency, accumulated, year-last-fire, scar id/area/size-range). Also: their mapping method (Alencar et al. 2022) vs ours, and **§6 Argentina's route — vectors-only upload, calendar-year products from fire-year objects** |
| `collection-01/docs/09-statistics.md` | **stages 5–6 + launch** (1 Aug → 24 Sep 2026): the six area-statistics CSVs, the **territorial layer we must build**, Looker Studio (~1 % tolerance), public assets vs Cloud-Storage COGs (the platform reads **GEE assets**), the **Workspace** subtheme/legend/territory catastro, and the launch track (ATBD, methodology page, downloads, materials, event) |

> **When a workflow step is in play, read the matching `collection-01/docs/NN-*.md` first.**
> Those notes point onward to the production files (`config/`, `models/`, `workflow/`) and to
> the notebooks that hold the deeper analysis. Add a new `docs/NN-*.md` when you start a new
> step; keep CLAUDE.md as the index, not the encyclopedia.

Other documentation:

- `collection-01/README.md` — human orientation: repo structure, how to run each step, the
  pipeline overview, status, and the **notebooks table** (what each `.qmd` contains).
- `collection-01/models/README.md` — model output schema + coefficient export details.
- `collection-01/BACKLOG.md` — pending work items.
- `collection-00/README_00.md` and `collection-00/docs/` — pilot reproduction + ATBD.

## Development environment

- **Python interpreter**: run collection-01 scripts with `$PYTHON` (e.g. `$PYTHON
  collection-01/workflow/01-training_data_export.py …`). `$PYTHON` is machine-local — set by
  `./setup.sh /path/to/store /path/to/venv/bin/python`, which records it in `.local-paths`
  (your shell) and `.claude/settings.local.json` (Claude Code's Bash). Use the project's GEE
  venv; never create a new venv for this repo.
- **GEE project**: `mapbiomas-fire-485203` (hardcoded in `collection-01/utils/constants.py`).
- **GEE accounts — two of them.** Most work runs under the primary personal account
  (`ivanbarbera93@gmail.com`). A few steps run under a **second account,
  `ivanbarbera@comahue-conicet.gob.ar`** — specifically anything that writes to Drive for the
  `-store` side (e.g. step 04 `--to-drive`), because that account **owns the Google Drive that
  Insync syncs into `STORE_ROOT`** (`.local-paths`). GEE credentials live in a single file
  (`~/.config/earthengine/credentials`), so switching accounts means swapping that file — keep
  per-account backups (`credentials.gmail`, `credentials.comahue`) and `cp` the one you need
  into place before running. Note the comahue account is registered under the shared
  `mapbiomas-argentina` compute project, **not** `mapbiomas-fire-485203`, so a script that
  hardcodes `C.GEE_PROJECT` may need a project override when run under it.
- **Run scripts from the repo root**, not from inside `collection-01/` — scripts add
  `collection-01/` to `sys.path` at startup.
- `collection-01/utils/constants.py` is the single source of truth for paths, year range,
  spectral features, the MB reclass table, LR terms, and the MB mosaic band list.

## Technology stack

| Component | Collection 0 | Collection 1 |
|-----------|-------------|-------------|
| GEE processing | JavaScript API | Python API (`earthengine-api`) |
| Model fitting | R (logistic regression) | same (`glmnet`, elastic net) |
| Source imagery | Landsat C2 SR — L5/L7/L8/L9 | same |
| Land cover reference | MapBiomas Argentina LULC | same + MapBiomas annual mosaic |
| Spatial segmentation | SNIC (GEE native) | same (steps 04+) |

## Collection 1 — pipeline at a glance

Numbered steps in `collection-01/workflow/`, each **exporting a GEE asset** so intermediate
stages can be inspected and limits avoided:

1. `01-training_data_export.py` — sample Landsat + prev-year MB mosaic at training points → one asset per fire.
2. `02-model_fitting.R` — fit one elastic-net LR per `veg_fire` class (locally, R), export coefficients for GEE.
3. **Prediction pipeline:** obs-level burn probability → time-series / annual summary (`03-bp_ts_metrics.py`) → SNIC segmentation (`04-snic.py`) → object vectorization & metrics (`05-objects_metrics.R`), plus a manual ash/drought masking pass still to be built.
4. `06-object_model.R` — **object-level fire/non-fire classification, replacing collection-00's
   empirical filter** (which scores accuracy 0.62 / sensitivity 0.50 on our labels). A probit BART
   (`stochtree`) on 20 object metrics, fitted locally in R and applied per fire-year; the fire call
   uses a **per-size-band threshold** from `config/object_model_thresholds.csv`, overridden by a
   collected label where one exists (`fire = fire_tag` if tagged, else `fire_model`). Modes: `fit`,
   `predict [years|all]`, `cv [region|grid K|random K]`. All of it runs **locally on CSVs from step
   05** — no GEE round-trip — and then the **whole scored object set** (all 28 fire-years, every
   object, all 20 predictors) goes back up as one FeatureCollection per fire-year, so a reviewer can
   also find the fires the model missed (docs/06 §12). Labels are prepared by
   `scripts/objects_labels_prep.R`; the threshold by `scripts/objects_threshold.R`; the upload by
   `scripts/objects_upload.py` + `scripts/validate_upload_zips.py`.
   **Never give the model a predictor that names the year or proxies for it** — that leak has been
   found and fixed twice here; docs/06 §4 before touching `PREDICTORS`.
5. **Step 07 — fire-year objects → calendar-year products** (docs/07). Four scripts:
   `07-month_of_burn.py` builds the **month-of-burn ImageCollection** in GEE (one 1-band uint8 image
   per calendar year, 1–12, masked elsewhere) by painting the step-06 objects filtered to
   `fire == 1 & area_ha >= 1` against the SNIC assets; `07-calendar_scars.R` builds the
   **8-connected calendar-year scars** locally (GEE cannot label them — `connectedPixelCount` caps
   at 1024 px); `07-scar_rasters.py` paints the ingested scar FCs into the three size subproducts;
   `07-subproducts.py` derives the **nine remaining subproducts** (monthly/annual burned, both
   `*_coverage`, frequency, accumulated, year-last-fire) from the month collection plus the
   MapBiomas LULC — encodings copied verbatim from the network's reference, do not innovate there.
   The published products cross against **`C.PRODUCT_LULC`** (LULC col-3), which is a *separate*
   constant from **`C.MAPBIOMAS_LULC`** (col-2 v8) on purpose: the latter is the model-side layer
   `veg_fire` — and hence the whole SNIC candidate set — was built from, and must stay frozen.
   Calendar year and month are assigned **per pixel** from `abs_date`, never per object from
   `year_calendar` — that is what makes annual/monthly/scar agree pixel-for-pixel, at the cost of
   splitting a fire that straddles 31 December. **Pin `crs` + `crsTransform` on every export**;
   `scale=30` in EPSG:4326 is a *different* grid.
6. **Step 08 — post-processing to the network's common products.** After step 07 the work stops being
   ours: every MapBiomas Fuego country runs the *same* post-processing to publish the *same* subproducts,
   even though their mapping method differs from ours. **Do not innovate there** — reproduce the
   reference code (see `docs/08-postprocessing.md` and the reference repo below). **But read
   docs/08's header box first:** its §§1–5 describe what *Brazil* does, and several of those stages
   (the LULC mask, the solitary-pixel filter) are already embedded upstream in our pipeline — running
   them again is a no-op at best. docs/07 wins where the two disagree.

See `collection-01/README.md` for the full structure and run commands, and the `docs/` notes
above for per-step design.

## Conventions & gotchas

- **`fire_id`** is a verbatim string whose **only guaranteed structure is the `"fire_"`
  prefix** — the body need not be numeric or two digits (e.g. `"fire_sde10"` alongside
  `"fire_07"`). **Never zero-pad, parse a numeric part, or reconstruct it**; build asset
  tokens with `C.fire_token(fire_id)` (`collection-01/utils/constants.py`) and use the id
  as-is otherwise. Bare `fire_id`s also **repeat across regions** — always key fires
  region-uniquely (`region_fire_id = paste(region, fire_id)`) in any analysis.
- **Asset-based processing**: every workflow step exports an intermediate GEE asset; don't
  collapse steps into one in-memory computation.
- **`oid` is the object key** from step 05 onward: `"<fire_year>_<pid>"`, unique across the whole
  collection, and every join (labels ↔ objects, predictions ↔ geometry, upload ↔ raster) is on it.
  Since the fire-year is embedded, no separate `fire_year` column is written to geometry files.
- **`data/` directory naming** (steps 04–06, all in the Insync store): `snic-rasters/` →
  `objects-raw/` → `objects-labels/`, `objects-pred/`, `objects-analysis/`, plus
  `objects-inspect-cache/` and `objects-upload-cache/`. Two rules: it is an **object** (a fire is an
  object; the sparse layer is not an OBIA partition, so "polygons" was retired), and a **`-cache`
  suffix means regenerable** — safe to delete, rebuilt from the CSVs by its launcher. Layout tables:
  docs/05 §4 and docs/06 "Files, directories and scripts".
- **Prediction tiling**: all image-based GEE predictions run over the MapBiomas *cartas* grid
  (`projects/mapbiomas-chaco/BASE/cartas-argentina`), not Landsat WRS-2 path/row.
- **Manual masking step**: a hand-made masking pass removes ash/drought false positives and
  needs domain-expert review before vectorization (exact step number is in flux).
- **GEE asset deletions**: the user runs deletions themselves — prepare the script and a
  dry-run, then hand off. Don't delete assets directly.

## GEE Code Editor scripts (separate repos)

All GEE JavaScript lives outside this repo. Two Code Editor repos matter — **ours** (writable) and
the **network's reference** (read-only). Files in both have **no extension**.

### Ours — `fuego` (write here)

- **Local**: `/home/ivan/dev/MapBiomas/mapbiomas-arg-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego` (`mapbiomas-arg/fuego`); pushes to branch `master`

The user does not regularly pull it, so it may be behind. **Always `git pull` before editing,
then edit, then `git push`** — the Code Editor reflects the push on next refresh. The `fuego`
repo is the sole source of truth for GEE JS code; do not keep `.js` copies here.

### The network's reference — `mapbiomas-fire` (READ ONLY, never push)

The MapBiomas Fuego network's own Code Editor repo: the canonical implementation of the **step-08
post-processing and published subproducts** that every country shares, plus their mapping-side
scripts (annual quality mosaics) which we do *not* use.

- **Local**: `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire` (branch `master`)
- **Start at** `4-Collection_anual_final_products/Reference/` — the country folders are adaptations of it.

It is **not ours**: pull to stay current, never commit or push. See
`collection-01/docs/08-postprocessing.md` for a map of the repo and what each script does.

## Running long scripts

**Always launch anything that runs more than a couple of minutes inside `tmux`** (or another
detached, long-surviving mechanism) so it survives session/terminal closure. This includes not
only local processing but **GEE task-submission scripts that fan out over many tiles** — e.g. a
full-year step-03 launch (`03-bp_ts_metrics.py --year YYYY`) submits one export task per *carta*
(hundreds of `task.start()` round-trips) and takes well over the few-minutes a foreground call
tolerates. Only a single-tile / handful-of-tasks submission is safe to run in the foreground.

```bash
tmux new-session -d -s <name> \
  '$PYTHON -u <script> [args] 2>&1 | tee <logfile>'
```

Reattach with `tmux attach -t <name>`; detach with `Ctrl+B D`. If unsure whether a run is
heavy enough, default to `tmux`.

> Make bulk launchers **idempotent / resumable**: skip tiles that already have a completed asset
> *or* an in-flight (PENDING/RUNNING) task, so a killed-and-rerun launch never duplicates work.

Long local runs that iterate over years follow the same rule via `scripts/run_05_years.sh` (step
05): **one `Rscript` per year** so an OOM kills only that year (flagged `rc=137`), not the whole
batch; skips years whose completion CSV exists; `scripts/mem_monitor.sh` samples RAM alongside and
logs a `WARN` when free memory nears the OOM limit. See `docs/05-object_metrics.md` §4.1. Launch
from tmux with an **absolute path** — a detached tmux shell may not start in the repo root.

The same one-process-per-fire-year pattern covers step 06: `run_06_predict.sh` (scoring — stochtree
prediction is single-threaded, so `-j 8`), `run_06_inspect.sh` (QGIS layers — I/O- and memory-bound,
`-j 6`), `run_07_upload_zips.sh` (upload packages, `-j 4`). All three are resumable, biggest-year
first, and log per year to `collection-01/logs/`.

Step 07's local scar build uses the same launcher shape in **two passes**
(`scripts/run_07_scars.sh pixels|scars`): `pixels` is one process per **fire-year** (28, `-j 5`,
tile-read bound, ~6-9 min each), `scars` is one process per **calendar year** (27, `-j 2` with
`OBJ_CORES=6`, dominated by the per-scar vectorize). Run `pixels` to completion first — a calendar
year needs **both** its fire-years. Memory, not CPU, is the binding constraint on `scars`: it holds
a whole calendar year's pixel set (up to ~100 M px) through the union-find, so prefer fewer
concurrent years with more `OBJ_CORES` each — `mclapply` forks share the parent's table
copy-on-write, which separate year processes do not. Gate the packages with
`scripts/validate_scar_zips.py` before any manual ingest.
