# `validation/`

Design-based accuracy assessment of the collection-1 burned-area product: a stratified random
sample of pixels, Olofsson/Stehman estimators, error-adjusted national burned area with
confidence intervals.

**Episodic.** Validation is not a stage of the mapping chain — it *consumes* the finished map, and
a collection can ship without it. That is why it lives here beside its code instead of in
[`../docs/`](../docs/), which holds the map-making chain and nothing else.

Everything here is **fire-year** (1 May → 30 Apr), including every external product it compares
against.

→ **[`docs/design.md`](docs/design.md)** — the design, the strata recipe, the frozen sample lists
and the response design. **Read its status box first**: the strata were built against the `_v1`
map and the published product is now `_v2`.
→ [`docs/notes/abandoned-paths.md`](docs/notes/abandoned-paths.md) — routes already tried and
dropped. Read it before re-inventing one.

Scripts run in order: `01_strata_export.py` → `02_sample_pool.py` → `03_ceo_export.py`.
`--help` on each; `colab_sample_pool_export.ipynb` is the distributed variant of the draw, and
`demo_small_region.py` is a tutorial that touches nothing frozen.
