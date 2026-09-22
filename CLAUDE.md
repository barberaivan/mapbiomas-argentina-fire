# CLAUDE.md

Operating rules for Claude Code (and any contributor), plus a one-line index of every document
in the repo. **It is the index, not the encyclopedia** — what to do next is
[`ROADMAP.md`](ROADMAP.md), how a step works is its `collection-01/docs/NN-*.md`.

## The roadmap comes first

**[`ROADMAP.md`](ROADMAP.md) is the ordered list of what to do next.** It is the *when*; the step
docs are the *how*.

- **Read it before planning any task.** If the task is on it, work from its ordering and its
  "run" / "edit → run" note — several items look like a re-run and are not.
- **Tick an item when it lands, delete it on the next pass.** Git history is the archive; never
  let the roadmap and reality disagree.
- **For a large task that is not on it, ask Iván whether to add it** first. Small, self-contained
  work does not belong there.
- **Do not read [`BACKLOG.md`](BACKLOG.md) unless asked**, and never edit it without explicit
  permission. It is the unscheduled pile for every collection — long, unordered, none of it next.

## Primary focus

**Active development is almost always in `collection-01/`, running scripts from
`collection-01/workflow/`.** Default to that context unless told otherwise. `collection-00/` is
the completed Patagonia pilot — reference, frozen, not active work.

## The documents

**When a workflow step is in play, read its `docs/NN-*.md` first.** Paths below are relative to
`collection-01/`; numbers repeat when several topics feed one step.

| Document | What it is |
|---|---|
| [`ATBD/`](collection-01/ATBD/) | the **ATBD** — the conceptual document above `docs/`, and the one that goes outside the project. Says what each stage measures and why; sends every parameter, threshold and asset id to `docs/` |
| [`docs/00-overview.md`](collection-01/docs/00-overview.md) | **read first** — the method in one page: spectral → temporal → spatial, and which step is which |
| [`docs/TEMPLATE.md`](collection-01/docs/TEMPLATE.md) | the shape a step doc follows — read before writing or rewriting one |
| `docs/01-training_data.md` | step 01 — training-data export, labels, inputs |
| `docs/02-vegetation_remap.md` | the `veg_fire` fire-class remap (input to step 02) |
| `docs/02-data_cleaning.md` | the `fit`-column cleaning gate (input to step 02) |
| `docs/02-model_fitting.md` | step 02 — elastic-net LR fitting, one model per `veg_fire` class |
| `docs/02-burn_probability.md` | that model **deployed in GEE**: per-observation burn probability, never materialized. Runs inside `workflow/03-bp_ts_metrics.py` |
| `docs/02-diagnostic_plots.md` | the per-fire burn-probability panels — a diagnostic tool, not a step |
| `docs/03-bpts.md` | step 03, the **temporal** stage — the probability series reduced to 16 int16 annual metrics per pixel, and the per-year precomputation that joins it to `02-burn_probability.md` |
| `docs/03-colab_multi_export.md` | step 03 how-to — distributed multi-account export via Colab |
| `docs/04-snic.md` | step 04 — whole-country non-calendar **fire-year** SNIC: the burned-pixel candidate set and the handoff to R |
| `docs/05-object_metrics.md` | step 05 (R) — candidate pixels → fire **objects**, with per-object raster and shape metrics |
| `docs/06-object_labels.md` | step 06, part 1 — where the ~5 k labels come from, and why **the labelled sample is not a random sample of objects** |
| `docs/06-object_model.md` | step 06, part 2 — the probit-BART object classifier: predictors, the per-size-band threshold, cross-validation, and the upload to GEE |
| `docs/06-object_inspection.md` | the QGIS review layer — a diagnostic tool, not a step |
| `docs/07-vector_to_raster.md` | step 07a–07c — fire-year objects → calendar-year burned pixels: the object exclusion ruleset, the `_v2` re-export, the month-of-burn and scar builds |
| `docs/07-published_products.md` | step 07d–07e — the nine derived subproducts and the fire-object polygon layer, with the traps in the reference encodings |
| `docs/08-postprocessing.md` | step 08 — Argentina's route through the network's shared post-processing spec, and what is still undecided |
| `docs/external/mapbiomas-fuego-reference.md` | **the network's spec as we read it** — code we do not own, pinned to a commit. Not a to-do list, and it goes stale silently |
| [`docs/notes/`](collection-01/docs/notes/) | the **lab notebook**: benchmarks, abandoned roads, post-mortems, status snapshots. Cited by filename; see its `README.md` |

**Episodic activities** — they consume the map, they are not stages of it, so their docs sit with
their code:

| Document | What it is |
|---|---|
| `statistics/docs/statistics.md` | step 09 — where **every factsheet number and figure** comes from: the three sources, the code, the verification gates, and the published `mapbiomas-arg-fire-stats.xlsx` |
| `statistics/docs/factsheet-sep2026-spec.md` | what each factsheet slide **says** and why (Spanish, per-launch) |
| `validation/docs/design.md` | the accuracy-assessment design (stratified sample, Olofsson/Stehman estimators). **Read its status box first** — the strata were built on `_v1` and the product is `_v2` |

**Signposts**: [`collection-01/README.md`](collection-01/README.md) is **the map** — the directory
tree, the `data/` layout, the pipeline table and the notebooks table, no commands and no status.
Then `scripts/README.md` (the non-pipeline scripts, grouped by step), `models/README.md`
(artifact layout, file schema, the raw-scale prediction recipe), `samples/README.md`,
`statistics/README.md`, `validation/README.md`. The root [`README.md`](README.md) is the setup
tutorial; `collection-00/README_00.md` is the frozen pilot.

**Where a fact lives**: how to invoke one script → its own `--help` or docstring. The order of the
steps → the step doc's `Run`. Parameters, paths, thresholds, asset ids → `config/` and
`utils/constants.py`. Why it is like this → the step doc's `Key decisions`. What we tried and
measured on a date → `docs/notes/`.

## Development environment

- **Python interpreter**: run collection-01 scripts with `$PYTHON` (e.g. `$PYTHON
  collection-01/workflow/01-training_data_export.py …`), from **the repo root** — scripts add
  `collection-01/` to `sys.path` at startup. `$PYTHON` is machine-local, set by
  `./setup.sh /path/to/store /path/to/venv/bin/python`. Use the project's GEE venv; never create
  a new one.
- **GEE project**: `mapbiomas-fire-485203` (in `collection-01/utils/constants.py`).
- **GEE accounts — two of them.** Most work runs as `ivanbarbera93@gmail.com`. A few steps run as
  **`ivanbarbera@comahue-conicet.gob.ar`**, which owns the Drive that Insync syncs into
  `STORE_ROOT` and is registered under the shared `mapbiomas-argentina` compute project, **not**
  `mapbiomas-fire-485203` — so a script hardcoding `C.GEE_PROJECT` may need a project override.
  - **Pass the credentials file explicitly rather than swapping
    `~/.config/earthengine/credentials`**: `ee.Initialize()` accepts a
    `google.oauth2.credentials.Credentials` built from any file, so both accounts work in one
    session and a half-finished `cp` cannot leave the wrong token resident.
    `workflow/07-burned_area_polygons.py::initialize()` is the pattern (`--credentials` +
    `--project`). Worth the bother because **the task queue is per user**: submitting as the
    second account starts the export immediately, not behind the first account's queue.
  - `ee.data.listOperations()` is **scoped to the compute project**, so anything tracking tasks
    from both accounts must poll both projects. A one-project watcher reports the other account's
    task as missing, which is indistinguishable from never having submitted it.

## Conventions & gotchas

- **The GEE compute project is SHARED with the whole network.** `listOperations()` returns *every*
  country's tasks. **Never cancel, restart or reason about a task you did not launch**, and
  **namespace every task `description`** (`bpts_…`, `mob_…`, `arg07d_…`) — matching a bare
  `annual_burned` can collide with another country's export and silently skip one of ours.
- **GEE asset deletions**: prepare the script and a dry-run, then hand off. Iván runs deletions.
- **Asset-based processing**: every workflow step exports an intermediate GEE asset. Don't
  collapse steps into one in-memory computation.
- **Pin `crs` + `crsTransform` on every export.** `scale=30` in EPSG:4326 is a *different* grid.
- **Two LULC constants, on purpose**: `C.MAPBIOMAS_LULC` (col-2 v8) is the frozen model-side layer
  `veg_fire` was built from; `C.PRODUCT_LULC` (col-3) is what the published products cross against.
- **`fire_id`** is a verbatim string whose only guaranteed structure is the `"fire_"` prefix
  (`"fire_sde10"` alongside `"fire_07"`). **Never zero-pad, parse a numeric part, or reconstruct
  it**; build asset tokens with `C.fire_token(fire_id)`. Bare ids also **repeat across regions** —
  key fires as `paste(region, fire_id)`.
- **`oid` is the object key** from step 05 onward: `"<fire_year>_<pid>"`, unique across the
  collection, and every join is on it. The fire-year is embedded, so geometry files carry no
  separate `fire_year` column.
- **Prediction tiling** runs over the MapBiomas *cartas* grid
  (`projects/mapbiomas-chaco/BASE/cartas-argentina`), not WRS-2 path/row.
- **Never give the object model a predictor that names the year or proxies for it** — that leak
  has been found and fixed twice; read `docs/06-object_model.md` "Why no predictor may identify
  the year" before touching `PREDICTORS`.
- **In `data/`, a `-cache` suffix means regenerable** — safe to delete, rebuilt by its launcher.
- **Cite a section by name, never by number** (`docs/05 "Metrics"`, not `docs/05 §2.4`), in code
  comments and docstrings as much as in docs. A heading number is a position: insert anything
  above it and the citation silently points elsewhere.
- **Two remotes: `origin` and `mapbiomas`.** `origin`
  (`barberaivan/mapbiomas-argentina-fire`) is the **source of truth** — every ordinary commit and
  push targets it, at whatever frequency work happens. `mapbiomas` (`mapbiomas/argentina-fire`) is
  the official, public-facing mirror, updated only when **explicitly** asked, at low frequency
  (e.g. milestones) — never as a side effect of "commit and push". No fork relationship exists
  between them (mapbiomas' side couldn't fork), so syncing is a plain `git push mapbiomas main`,
  not a PR.

## GEE Code Editor scripts (separate repos)

All GEE JavaScript lives outside this repo, in files with **no extension**.

- **Ours — `fuego`** (write here): `/home/ivan/dev/MapBiomas/mapbiomas-arg-fire-gee/`, remote
  `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego`, branch `master`. Iván does not
  regularly pull it, so **always `git pull` → edit → `git push`**. It is the sole source of truth
  for our GEE JS; keep no `.js` copies here.
- **The network's — `mapbiomas-fire`** (READ ONLY, never push):
  `/home/ivan/dev/MapBiomas/mapbiomas-latam-fire-gee/`, remote
  `https://earthengine.googlesource.com/users/mapbiomasworkspace1/mapbiomas-fire`. Start at
  `4-Collection_anual_final_products/Reference/`; `2-Statistics/toolkit/v03/` is the stage-5
  statistics method. **It is not always cloned** — clone it before reading, and see
  `docs/external/mapbiomas-fuego-reference.md` for the map of it.

## Running long scripts

**Launch anything that runs more than a couple of minutes inside `tmux`**, with an absolute path
(a detached tmux shell may not start in the repo root):

```bash
tmux new-session -d -s <name> '$PYTHON -u <script> [args] 2>&1 | tee <logfile>'
```

This includes GEE task-submission scripts that fan out over many tiles — a full-year step-03
launch submits one export per *carta*. Only a handful of tasks is safe in the foreground.

Two rules for bulk work. **Make launchers idempotent**: skip tiles that already have a completed
asset *or* an in-flight task, so a killed-and-rerun launch never duplicates. And **one process per
year**, so an OOM kills one year and not the batch — the shape of `scripts/run_05_years.sh`,
`run_06_predict.sh`, `run_06_inspect.sh`, `run_07_scars.sh` and `run_07_upload_zips.sh`.
