> **Extracted from** `collection-01/docs/06-object_model.md` §4 "The 20 predictors" and
> "No predictor may identify the year — or proxy for it" @ `fc6ddef` (2026-09-18).
> Lab notebook — the record of building the step, not documentation of it.

# 06 — How the predictor set was arrived at

Three episodes, all 27–28 July 2026: the 23 raw vegetation fractions collapsed to 5 groups, the
`fire_year` / `year_calendar` label-prevalence leak, and the `n_mean` era proxy. The **rule** they
produced — no predictor may identify the year or proxy for it — is live and stays in the step doc;
the measurements are here.

## The 23 raw fractions → 5 aggregated groups

> *Historical record.* The 5 aggregated fractions replaced the 23 raw `frac_c1..frac_c23` columns
> (2026-07-27): on the same objects and folds the aggregated set won on every grid-blocked metric
> (then-current AUC 0.902 → 0.921), with the gain landing in the weak 1–50 ha band. The reason is
> **split budget** — 23 sparse columns were 58 % of the design matrix and BART draws split variables
> uniformly over what is available. The raw fractions are kept in the step-05 metrics and summed at
> load time; only the 5 sums enter the model. Those AUC figures were measured before the leak fix
> below and are not comparable to the current ones.

## The `fire_year` / `year_calendar` leak, and the `n_mean` era proxy

### No predictor may identify the year — or proxy for it

This is the rule the predictor set is built around, and it cost two predictors. It is recorded
because the failure is easy to reintroduce and hard to see.

Per-year label prevalence in the fitting set is an artifact of **where people drew**, not of the
fire regime: it runs from 0.00 (2001, 2009, 2016) to 1.00 (1998), and seven fire-years have no
labels at all. Give the model the year and it learns that sampling pattern, then applies it to every
object of that year.

**`fire_year` and `year_calendar` were predictors, and they were leaking the labels.** Removed
2026-07-28. What was measured on the then-deployed fit: those two columns took **18.4 % of all
splits** in the forest (9.9 % + 8.5 %) — the **top two of 22**, ahead of `seed_mean` (6.7 %);
Spearman(per-year label prevalence, per-year predicted fire %) was **0.83** on deployed predictions
and **0.96** out of fold — out of fold, the prediction for a year *was* its label prevalence. The
symptom that exposed it was three implausible fire-years (**1998 called 100.0 % fire**, 2012 96.6 %,
2013 93.3 % — and 2013 has no labels at all, so that figure was interpolated between 2012 and 2014),
but every year was affected. Removing them cost pooled OOF AUC (0.9211 → 0.8948) and **gained**
n-weighted **within-year** OOF AUC (0.8400 → 0.8467): the pooled gap had been pure between-year
prevalence. That signature — pooled falls, within-year holds — is what removing leakage looks like.

**Grid-blocked CV structurally could not detect it.** Each of the 5 grid folds contains 17–20 of the
21 labelled years, so the year lookup sits on both sides of every split and reads as skill. The fold
design blocks *space*, not *time* (§7). A per-year diagnostic therefore exists as a standing check:
`notebooks/objects-analysis.qmd` §8.

**`n_mean` was dropped for the same class of reason** (same day). The mean Landsat observation count
per object was carried as a **proxy for polygon quality** — how well-observed, and so how
well-constrained, each object's probability is. But it is a **soft era proxy**: observation density
rises across the record as sensors come online (L5, +L7 1999, +L8 2013, +L9 2021), giving
Spearman(fire_year, mean `n_mean`) = **0.81**, and with it in the model the per-year fire rate
inherited a **0.79** time trend. In a 28-year collection built for trend analysis, that lets an
improving satellite archive masquerade as a rising fire regime. Dropping it is cheap because
**`seed_mean` already carries observation quality density-normalised**: the step-04 seed threshold K
is chosen per pixel by `(veg_fire, n)` (04 §4.1). Measured, the two are near-orthogonal per object
(Spearman **+0.014**) and `seed_mean`'s own era trend is far weaker (+0.45 vs +0.81) — so removing
`n_mean` strips the raw density that normalisation was designed to neutralise, and nothing else. The
manufactured trend roughly halved (Spearman 0.789 → **0.407**) for **0.0014** of within-year AUC.

What replaced them:

- **`fire_year`, `year_calendar` — dropped as predictors**, but they keep their product roles:
  `year_calendar` places an object in a calendar year for the step-08 monthly products (08 §6), and
  the fire-year is embedded in `oid`. Both remain in the step-05 metrics and in the upload.
- **`doy_median` → `doy_sin` + `doy_cos`** (period 365.25). Day-of-year carries season, not year, so
  it is legitimate — but it must be **circular**. The fire season straddles Dec/Jan (the entire
  reason a fire-year exists, 04 §2), so an axis-aligned tree cannot express "December through
  February" as one region in raw DOY. A threshold on `sin` or `cos` selects a single arc, so the pair
  represents wrap-around intervals in two splits. (A linear day-of-*fire*-year coordinate would fix
  the wrap in one column, but would hard-code the fire-year start convention.)
- **`date_span` — kept.** A duration names neither a year nor a season, so it carries no sampling
  signal.
- **No absolute time coordinate is a predictor**, including the raw `date_{median,min,max}` columns,
  which never were — the reason is restated at `objects_data_functions.R::add_derived`.

The residual time trend in the deployed product is **Spearman 0.407 / Pearson 0.325** over a range
of 71.0–83.7 % fire (sd 3.0). Some interannual structure is real. It is **unattributed**, not proven
clean: do not publish it as a fire-regime finding without checking against an independent record.

> Removing the leak does **not** make prevalence calibrated. The labels are still not a random
> sample of objects, so the *level* of the fire rate remains uncertain (§6, §9). What the fix removes
> is the model reading the year off the sampling.

### Collection 2: two metrics to stop computing

- **`n_mean` — do not compute it at all** in the object summaries. It is not a predictor, and
  carrying it invites exactly the mistake above. The observation count still belongs where it is
  already used and normalised: inside the step-04 seed definition.
- **`n_pixels` — drop it too; `area_ha` is the meaningful one.** The pixel scale is
  latitude-dependent (§9), so a pixel count is not a size, and the model confirms it carries nothing
  the area does not: `n_pixels` is **last of 20** on every importance measure (permutation |Δp|
  **0.0006**, permutation AUC drop **0.0000**, ALE range 0.0076 — §8). It is kept in collection 1
  only because it answers "how many pixels is this really" when reading a QGIS row.
