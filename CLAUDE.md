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
| `collection-01/docs/02-model_fitting.md` | step 02 — elastic-net LR fitting |
| `collection-01/docs/03-bp_ts_metrics.md` | step 03+ — burn-probability time-series metrics (stub) |

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
3. **Prediction pipeline (stubs, in development):** obs-level burn probability → time-series / annual summary → SNIC segmentation → object metrics & filtering, plus a manual ash/drought masking pass. Step numbering above 02 is still in flux — check `collection-01/workflow/` for the current files.

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
- **Prediction tiling**: all image-based GEE predictions run over the MapBiomas *cartas* grid
  (`projects/mapbiomas-chaco/BASE/cartas-argentina`), not Landsat WRS-2 path/row.
- **Manual masking step**: a hand-made masking pass removes ash/drought false positives and
  needs domain-expert review before vectorization (exact step number is in flux).
- **GEE asset deletions**: the user runs deletions themselves — prepare the script and a
  dry-run, then hand off. Don't delete assets directly.

## GEE Code Editor scripts (separate repo)

All GEE JavaScript lives in a separate repo, **not** in this one:

- **Local**: `/home/ivan/Insync/MapBiomas/mapbiomas-argentina-fire-gee/`
- **Remote**: `https://earthengine.googlesource.com/users/mapbiomas-arg/fuego` (`mapbiomas-arg/fuego`)

The user does not regularly pull it, so it may be behind. **Always `git pull` before editing,
then edit, then `git push`** — the Code Editor reflects the push on next refresh. The `fuego`
repo is the sole source of truth for GEE JS code; do not keep `.js` copies here.

## Running long scripts

For local processing over ~15 minutes, use `tmux` so the run survives session closure
(GEE task-submission scripts are short enough to run normally):

```bash
tmux new-session -d -s <name> \
  '$PYTHON -u <script> [args] 2>&1 | tee <logfile>'
```

Reattach with `tmux attach -t <name>`; detach with `Ctrl+B D`. If unsure whether a run is
heavy enough, ask before launching.
