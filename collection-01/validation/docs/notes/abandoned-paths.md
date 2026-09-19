# Validation — paths tried and abandoned

Short list, so none of them is tried a second time. Dates are when the route was dropped; the
working implementation of record is always the Python in `collection-01/validation/`.

- **The country polygon as a sampling / reduction `region`** (2026-08-31). `ARG-Political_Level_1-Pais`
  has 2 M+ edges, and *any* GEE op that receives it as `region=` pays "is this candidate inside?"
  against that shape — it OOMs (error code 8) regardless of what is being drawn or reduced.
  Controlled test: the identical call failed 5/5 with the polygon and succeeded 3/3 in ~15–20 s
  with a plain `ee.Geometry.Rectangle`. The complex boundary already baked into the clipped strata
  asset is not the problem; the geometry passed **at query time** is. **Always pass a rectangle.**
- **`stratifiedSample` per stratum, per year** (2026-08-31) — the design's original draw, and what
  two weeks of OOM debugging were aimed at. Every variant died: whole-country, high
  `tileScale`/`classValues`, partitioned across the ~248 cartas, and a plain `reduceRegion` for
  the counts. The cause was the region geometry above, not the sampler, but the route was replaced
  rather than repaired: `02_sample_pool.py` draws one **unstratified** pool with `Image.sample()`
  and splits by stratum in pandas, which is statistically identical and one request per year
  instead of three (`design.md` "Drawing the frozen ordered sample lists").
  `02_sample_pool.py --launch` / `--launch-by-carta` are the dead modes; they are kept only so an
  old command line fails loudly instead of silently meaning something else.
- **`validation/colab_sample_pool_export.ipynb`** (Ramón Peña Agrest, 2026-08-28) implements that
  same superseded per-stratum recipe. Still in the repo; do not run it. Deleting it is his call.
- **A 30,000-unit reserve per stratum per year** (2026-08-30). Cut to 5,000, which still covers
  every scenario in `design.md` "Sample size, and how to extend" — a cost decision about the draw,
  not a statistical one.
- **`01_strata_export.py --weights-launch` as written** — the exact-`Nh` census, a `reduceRegion`
  at country scale, blocked by the same OOM. Not re-tested since the geometry fix and **very
  plausibly works now**: verify before assuming it is broken.
- **The GEE-JS prototypes** of the strata raster and the point draw, which this document carried
  inline as Appendix A and Appendix B until 2026-09-18. Both were a second home for code that
  exists in Python (`01_strata_export.py` is a direct port of A), and Appendix A had already gone
  stale in the way a duplicate does — it hardcoded `collection1_fire_mask_v1` while the Python
  reads `C.MONTH_OF_BURN_COL`, which is how the v1/v2 problem in `design.md` "Status" was found.
  Deleted, not moved: the Python is the record.
