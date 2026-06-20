# Models documentation task

## What we did (step-02 burn-probability LR)

- Designed the canonical LR term structure (features + interactions).
- Investigated collinearity in the expanded design and **reduced it 427 → 133 terms**
  (focal mains 11 — MIRBI dropped as an exact linear combo; prev-year mains 32;
  focal×focal interactions; prev×focal blocks).
- Found the "glmnet too slow" problem was **numerical, not statistical**: the default
  `thresh=1e-7` crawls in the ill-conditioned low-λ tail, and a coarse `nlambda` gives
  poor warm starts. Settled the fitting config (full data, `nlambda=50`,
  `lambda.min.ratio=1e-4`, `thresh=1e-4`, α grid {0.25,0.5,0.75,1}).

## Where the docs are

- `notebooks/logistic_regression_terms.qmd` — design of the LR term structure
  (which features/interactions, and why).
- `notebooks/predictors_terms_correlations.qmd` — pairwise-correlation analysis, the
  427→133 reduction decisions, separability/ash tests, VIF, and the CV-tuning findings.

## The task

**Merge the two notebooks above into a single coherent notebook**, guided by Iván.
One narrative: term design → collinearity reduction → final design + fitting config.
