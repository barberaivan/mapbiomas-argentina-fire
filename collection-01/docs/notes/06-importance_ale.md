> **Extracted from** `collection-01/docs/06-object_model.md` §8 "What the model leans on —
> importance and ALE" @ `fc6ddef` (2026-09-18) — the doc keeps the conclusions and a short table.
> Lab notebook — the record of building the step, not documentation of it.

# 06 — Importance and ALE, in full

## 8. What the model leans on — importance and ALE

`scripts/objects_importance_ale.R` → `importance_objects.csv` + `ale_curves_objects.csv`, rendered
in `notebooks/objects-analysis.qmd` §9. Four measures, because none is trustworthy alone: the
predictors are strongly correlated (`area_ha`/`n_pixels`/`perimeter_m` near-collinear,
`burned_around_{1,2,3}` nested windows) and every importance measure mishandles correlation its own
way.

| measure | what it is | how it misleads |
|---|---|---|
| `split_share` / `root_share` | fraction of all (root) forest splits taken by the column, parsed from the saved forest JSON | biased toward high-cardinality continuous columns; credit splits arbitrarily between correlated columns |
| `perm_dp` | mean \|Δ predicted probability\| when the column is shuffled | the measure that matches the upload question — but a correlated pair can both look small |
| `perm_auc_drop` | AUC lost on the labelled set when the column is shuffled | in-sample, so "what separates the classes it was shown", not validation |
| `ale_range` | max − min of the 1-D **ALE** curve (Apley & Zhu), in probability units | ALE not PDP *because* of the correlation — a PDP averages over combinations that do not exist (a 1-pixel object with a 10 km perimeter) and invents effects there |

Ordered by `perm_dp` (full table in the notebook):

| predictor | split share | perm \|Δp\| | perm AUC drop | ALE range |
|---|---|---|---|---|
| `frac_grass_temp` | 0.083 | **0.243** | 0.217 | 0.488 |
| `seed_mean` | 0.070 | **0.206** | 0.081 | **0.587** |
| `frac_woody` | 0.049 | 0.073 | 0.010 | 0.171 |
| `burned_around_1` | 0.062 | 0.072 | 0.008 | 0.222 |
| `frac_grass_inund` | 0.064 | 0.068 | 0.028 | 0.415 |
| `frac_agri` | 0.064 | 0.061 | 0.010 | 0.263 |
| `doy_cos` | 0.068 | 0.061 | 0.011 | 0.140 |
| … | | | | |
| `perimeter_m` | 0.025 | 0.006 | 0.001 | 0.028 |
| `shape_index` | 0.034 | 0.003 | 0.000 | 0.005 |
| `n_pixels` | 0.021 | **0.0006** | **0.0000** | 0.008 |

Two things this settles:

- **Two predictors carry the model**: the temperate-grassland fraction and the seed share. That is
  the intended story — real scars are densely seeded (04 §4.1), and the fuel type decides how a
  burned patch looks. `seed_mean` has the largest *effect size* (ALE 0.587) even though
  `frac_grass_temp` moves the output most on average.
- **The size/shape block is nearly inert**, and `n_pixels` is inert outright — hence the collection-2
  note in §4. `area_ha` still earns its place (ALE 0.160) because it selects the threshold band.

No predictor shows the signature that caught `fire_year`: a large split share concentrated at the
root with an effect that tracks the calendar. `doy_sin`/`doy_cos` sit mid-table with small ALE
ranges, which is what a genuine seasonal signal looks like.
