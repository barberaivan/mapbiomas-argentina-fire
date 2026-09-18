# 02 — How the predictor set got from 427 terms to 50

> **Extracted from** `collection-01/docs/02-model_fitting.md` ("Approach" bullets), on 2026-09-18.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcome: **P=50 is deployed**, 52 coefficient rows. This is the route.

## Reduction 1 — 427 → 129 terms (fit-side)

Verbatim from the doc:

> **Design**: a reduced **129-term** predictor set (11 focal mains + 32 prev-year mosaic
> mains + 22 focal×focal + 10 same-band + 22 prev×fire-index + 32 prev×fire-band). Reduced
> from a 427-term "canonical-team" design that was too collinear to fit quickly — the full
> story (correlation pruning, exact-linear-combo cut, VIF/eigenvalue analysis) is in
> `notebooks/logistic_regression_design.qmd`.

The driver was **fitting**, not prediction: the 427-term design was ill-conditioned enough that
`glmnet` crawled. The block structure that survived is in `workflow/02-model_fitting.R`
(`BLOCKS <- c(focal = 11, prev = 32, pairs = 22, sameband = 10, cross_idx = 22, cross_band = 32)`).

MIRBI was dropped from the focal mains as an exact linear combination.

## Reduction 2 — 129 → top-P, and P=50 deployed (prediction-side)

Verbatim from the doc:

> **A second, later reduction decides what GEE actually runs.** The 129 terms are what gets
> *fit*; term count dominates per-tile prediction cost in step 03, so a top-P cut on the global
> standardized-coefficient ranking was swept (P ∈ {30,40,50,60,80}) and **P=50 deployed**. The
> fitting code is unchanged — the sweep drives it through its `KEEP_TERMS_CSV` / `COEF_TAG`
> hooks.

A different motivation from reduction 1. `notebooks/lr_term_pruning.qmd` states it:

> **Why prune.** The burn-probability model is applied per Landsat observation over ~150
> date-mosaicked scenes per tile in the GEE prediction step (`workflow/03-bp_ts_metrics.py`).
> Profiling (`docs/03-bpts.md §8`) showed the **130-term elastic-net LR dominates per-tile compute** —
> the per-term band selects / multiplies / sums, and the computation-graph "plumbing" they generate,
> scale with the term count, while the clever time-series array metrics are <1% of cost. So fewer
> terms ⇒ cheaper prediction across all 248 tiles × 27 years.

**The ranking.** Terms are ranked globally by standardized coefficient `|β_z|` (= `β · sd(raw
column)`, written as `coef_std` by `02-model_fitting.R`), pooled across the 23 fittable classes
under an area weighting. Three weightings were compared — `area` (K=1), `√area` (K=2),
`area^(1/3)` (K=3) — and **K=3 was chosen**. That is where the `K3` token in
`models-store/pruning/K3_P<P>/` and `keep_K3_P<P>.csv` comes from; it has nothing to do with CV
folds, and it has been misread as a fold count in this repo's own docs at least twice.

**Why P=50** (from `docs/03-bpts.md` §11, decided 2026-06-27): area-weighted mean ΔAUC is ~0 at
P≥50 under all three weightings, with a real drop only below it.

**How it was deployed.** Rather than promoting the chosen variant into a single `models/`
folder, every variant keeps its own tracked folder (`models/P129/`, `models/P050/`, …) so the
deployed set travels with the repo for the Colab multi-account export, and
`C.DEPLOYED_MODEL = "P050"` selects it. Redeploying is that one constant.

## Where the evidence lives

| | |
|---|---|
| `notebooks/logistic_regression_design.qmd` | reduction 1 — correlation pruning, exact-linear-combo cut, VIF/eigenvalues |
| `notebooks/lr_term_pruning.qmd` | reduction 2 — the ranking, the three area weightings, the P comparison |
| `scripts/refit_pruning_sweep.R` | refits every P through `02-model_fitting.R`'s hooks |
| `config/pruning_terms.csv` | the kept-term list per P (scheme `area_cbrt_K3`) |
| `models-store/pruning/metrics_by_P.csv` | the OOF metrics the choice was made on |
| `docs/03-bpts.md` §9/§11 | the decision record and the profiling that motivated it |
