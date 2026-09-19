# MapBiomas Argentina Fire — Collection 01

*In development.* All five regions, Landsat 1999–2025. Collection 0
([`../collection-00/README_00.md`](../collection-00/README_00.md)) is the completed Patagonia pilot.

**This file is the map.** It says what is where and which document explains it. It carries **no
commands**: how to run one step is that step's `Run` section in [`docs/`](docs/), and how to invoke
one script is its own `--help` or header.

→ **Start at [`docs/00-overview.md`](docs/00-overview.md)** — the method in one page (spectral →
temporal → spatial) and which workflow step is which. Then the step doc you need;
[`docs/TEMPLATE.md`](docs/TEMPLATE.md) is the shape they all follow.

---

## What changed from collection 0

| Aspect | Collection 0 | Collection 1 |
|--------|-------------|-------------|
| Coverage | Patagonia only | BA, CHACO, PAMPA, CUYO, PAT |
| Model | Logistic regression (2 levels) | Elastic-net logistic regression (`glmnet`), one per `veg_fire` class |
| Language | GEE JavaScript + R | Python (GEE processing) + R (fitting, objects) |
| Previous-year features | Custom index summaries | MapBiomas mosaic (40 bands) |
| Spectral features | NBR/NBR2/MIRBI/NDVI | 21 per observation — optical, fire indices, tasseled-cap, and the canonical-team additions |
| Burned-area delineation | — | SNIC segmentation → fire objects → a probit-BART object classifier |

The feature list is `ALL_FOCAL_FEATURES` in `utils/constants.py`, which is its source of truth;
the previous-year MapBiomas mosaic bands are attached from the year *prior* to each observation.

---

## Where things live

| Directory | What is in it | Read |
|---|---|---|
| [`docs/`](docs/) | **the map-making chain and nothing else** — `00-overview` plus one doc per step, `notes/` (the lab notebook) and `external/` (readings of code we do not own) | [`docs/00-overview.md`](docs/00-overview.md) |
| [`workflow/`](workflow/) | the numbered pipeline steps, mixed Python and R. One step, one export | the matching `docs/NN-*.md` |
| [`scripts/`](scripts/) | everything that is *not* a numbered step: launchers, gates, watchers, trials | [`scripts/README.md`](scripts/README.md) |
| [`config/`](config/) | `veg_fire_remap.csv` (the canonical MB→fire-class remap) and `object_model_thresholds.csv` (the step-06 fire call per size band) | `docs/02-vegetation_remap.md`, `docs/06-object_model.md` |
| `utils/` | `constants.py` — **the single source of truth** for paths, years, features, the reclass table, LR terms; `functions.py` — cross-step GEE helpers only | — |
| [`models/`](models/) | fitted coefficients, one folder per model variant (`P050/` is deployed) | [`models/README.md`](models/README.md) |
| [`statistics/`](statistics/) | step 09 — every factsheet number and figure. **Episodic** | [`statistics/README.md`](statistics/README.md) |
| [`validation/`](validation/) | accuracy assessment. **Episodic** | [`validation/README.md`](validation/README.md) |
| [`notebooks/`](notebooks/) | Quarto-R exploration and decisions (table below) | — |
| [`samples/`](samples/) | archive: the JS templates behind the interactive point collection | [`samples/README.md`](samples/README.md) |
| `data/`, `models-store/` | symlinks into the Insync store — **not git**. Set up by `../setup.sh` | [root README](../README.md#getting-started-first-time-setup) |

Steps **01–08 produce the map**; statistics and validation **consume** it, which is why they sit
beside their own code rather than in `docs/`.

### `data/` — the step-04→06 outputs, in the store

| directory | contents | size |
|---|---|---|
| `snic-rasters/<fy>/` | step-04 per-carta SNIC GeoTIFFs — the step-05 input | 11 GB |
| `objects-raw/` | step-05 output: `objects_<fy>.gpkg` (geometry + `oid`) + the two metrics CSVs | 6.8 GB |
| `objects-labels/` | the collected labels: one GPKG per collaborator + `polygons_data_merged.csv` | 4 MB |
| `objects-pred/` | step-06 output: `objects_<fy>_pred.csv`, `_derived.csv`, `oof_grid_5.csv` | 317 MB |
| `objects-analysis/` | every reported table and plot from the step-06 scripts and notebook | 2 MB |
| `objects-inspect-cache/` | 28 QGIS layers + a `.qgz` project — **regenerable** | 6.3 GB |
| `objects-upload-cache/` | the 28 GEE upload zips — **regenerable** | 8.4 GB |
| `statistics/` | every step-09 input and output: the toolkit CSVs, the denominators, the `factsheet_*` tables, the three rasters and `figures/` | ~160 MB |

Two rules: a fire is an **object** (the layer is sparse, not an OBIA partition), and a
**`-cache` suffix means regenerable** — delete it and re-run its launcher. Layouts:
`docs/05-object_metrics.md` "Inputs → Outputs" and `docs/06-object_model.md`
"Files, directories and scripts".

---

## The pipeline

Steps in order, each exporting a GEE asset so it can be inspected and limits avoided. `docs/` has
the design, the `Run` block and the gotchas for each.

| Step | Makes | Doc |
|---|---|---|
| **01** | training data: one row per point × valid Landsat observation | [`01-training_data.md`](docs/01-training_data.md) |
| **02** | the `veg_fire` remap, the `fit` cleaning gate, and one elastic-net LR per class | [`02-vegetation_remap.md`](docs/02-vegetation_remap.md), [`02-data_cleaning.md`](docs/02-data_cleaning.md), [`02-model_fitting.md`](docs/02-model_fitting.md) |
| **02** | that model **deployed in GEE**: burn probability per observation, never materialized | [`02-burn_probability.md`](docs/02-burn_probability.md) |
| **03** | the probability series reduced to 16 annual metrics per pixel | [`03-bpts.md`](docs/03-bpts.md) |
| **04** | fire-year SNIC segmentation → the burned-pixel candidate set | [`04-snic.md`](docs/04-snic.md) |
| **05** | those pixels → fire **objects**, with per-object metrics | [`05-object_metrics.md`](docs/05-object_metrics.md) |
| **06** | which objects are real fire: labels, a probit-BART classifier, the review layer | [`06-object_labels.md`](docs/06-object_labels.md), [`06-object_model.md`](docs/06-object_model.md), [`06-object_inspection.md`](docs/06-object_inspection.md) |
| **07** | fire-year objects → calendar-year pixels, then the published products | [`07-vector_to_raster.md`](docs/07-vector_to_raster.md), [`07-published_products.md`](docs/07-published_products.md) |
| **08** | Argentina's route through the network's shared post-processing spec (no script of its own) | [`08-postprocessing.md`](docs/08-postprocessing.md) |

Diagnostics, not steps: [`02-diagnostic_plots.md`](docs/02-diagnostic_plots.md) (per-fire
time-series panels) and [`06-object_inspection.md`](docs/06-object_inspection.md) (the QGIS review
layer). Distributed export across accounts:
[`03-colab_multi_export.md`](docs/03-colab_multi_export.md).

---

## Notebooks (Quarto-R)

Exploration and evidence. Once an answer changes what production does it moves into the doc, and
the notebook becomes the evidence behind it. Rendered `.html` is tracked alongside each `.qmd`.

| Notebook | Purpose |
|---|---|
| `land_cover_remap.qmd` | validate the MB → fire-class remap against the full observations; CV feasibility per class |
| `logistic_regression_design.qmd` | the 427-term canonical set → the reduction → the 129-term elastic-net design |
| `lr_term_pruning.qmd` | the 129 → top-P cut behind the deployed `P050` |
| `model_fit_diagnostics.qmd` | per-class fit diagnostics: tuning, coefficients, calibration, OOF, by-fire breakdown (`_model_fit_diagnostics_child.qmd` is its per-class template) |
| `burn_prob_ts_metrics.qmd`, `bpts_metrics_explained.qmd` | the step-03 summary metrics |
| `snic_candidates_seeds_definition.qmd` | step 04: where the seed and candidate thresholds come from |
| `categorical_vs_bernoulli.qmd` | formulation notes |
| `logistic_regression_feature_engineering_ideas.qmd` | feature ideas, not deployed |
| `data_collection_stats.qmd` | field-collection stats (time, authors, points, observations per fire) |
| `validation_year_selection.qmd` | which three fire-years to validate |
| `objects-analysis.qmd` | step 06: size distribution, labels vs population, the minimum-fire-size decision, the per-size-band cuts, the per-year leak diagnostic, importance + ALE |
| `factsheet_sep2026.qmd` | **the September deliverable** |
| `factsheet.qmd` | the bank of figures it selects from (análisis 1–5, every regional variant) |
| `factsheet_veg.qmd`, `factsheet_veg_short.qmd` | análisis 6, exploratory — December and the paper |

⚠️ **Which factsheet notebook ships, and what each one is for, is
[`statistics/docs/statistics.md`](statistics/docs/statistics.md) §5.0** — that is the one home for
it. What each figure *says* is
[`statistics/docs/factsheet-sep2026-spec.md`](statistics/docs/factsheet-sep2026-spec.md).

---

## GEE

Compute project **`mapbiomas-fire-485203`**, **shared with the whole MapBiomas Fuego network** —
never touch a task you did not launch, and namespace every task description. Two accounts are in
play, with separate task queues. Both, and the asset tree under
`projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/`, are in `utils/constants.py` and
CLAUDE.md "GEE accounts".

---

## Where things stand

[`ROADMAP.md`](../ROADMAP.md) — what is in flight and what is next, in order.

**No status table here, on purpose.** The one this file used to carry drifted: it still said step
05 was "2001–2025" when all 28 fire-years had been on disk for months, and called step 07 "landed
and verified" in the middle of the `_v2` re-export. ROADMAP's own rule already says not to keep a
done-list, and a second one here could only disagree with it.
