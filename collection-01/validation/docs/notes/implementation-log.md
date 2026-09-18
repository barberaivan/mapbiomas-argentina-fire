> **Extracted from** `collection-01/validation/docs/design.md` §0 "Implementation status
> (2026-08-31)" @ `54e3e8d` (2026-09-18). Written by Ramón Peña Agrest alongside the code.
> Lab notebook — the record of building the step, not documentation of it.

# Validation — implementation log

## 0. Implementation status (2026-08-31)

The strata rasters (§4) are landed for all three fire-years (2003, 2013, 2022) exactly as
Appendix A specifies — unchanged.

**Appendix B's point-drawing recipe (`stratifiedSample` per stratum) does not scale — do not use
it as written.** It OOMs (GEE error code 8) at country scale in every variant tried: direct,
tuned `tileScale`/`classValues`, partitioned across the ~248 MapBiomas cartas, even a plain
`reduceRegion` for the pixel counts. The cause is not `stratum`, not `stratifiedSample` itself —
it is the **region geometry**: `FRAME` (`ARG-Political_Level_1-Pais`) has 2M+ edges, and any op
that receives it as `region=` pays the cost of evaluating "is this candidate inside?" against
that geometry, regardless of what's being sampled or reduced. A controlled test confirmed it: the
identical call, only swapping that geometry for a plain `ee.Geometry.Rectangle`, went from 5/5
failures to 3/3 successes in ~15-20 s.

**The actual, working implementation** is in `collection-01/validation/02_sample_pool.py` —
draws an *unstratified* pool with `Image.sample()` (no `classBand`, so no per-class scan of the
whole country — cost scales with how many points are requested, not with the country's size),
then splits by stratum locally in pandas. Statistically identical to sampling within each stratum
separately (conditioning on stratum commutes with random draw); only the order of operations
changed. See that file's module docstring ("LA SAGA DEL OOM Y LA CAUSA REAL") for the full
post-mortem and the exact working recipe (`--pilot-launch` → `--pilot-report` → `--launch-pool`
→ `--freeze --from-pool`).

Two-stage by design (not in Appendix B, decided 2026-08-30): a first "pool 1" is sized only to
clear the **initial 100/stratum/year** (§1) comfortably, not the 5,000-unit reserve — cheap
(~100-150k points/year, seconds to minutes), so a wrong bet costs little. A larger "pool 2" to
reach the 5,000/stratum reserve is **not built yet** — it reuses the same `draw_pool()` with a
bigger N, combined with pool 1 by de-duplicating on exact `(col, row)` (collision rate at these
scales is negligible, computed at ≈0.03% — not worth an exclusion-mask instead), appended after
pool 1's existing ranks. Pool 1's frozen rows/ranks are never touched — satisfies §5 rule 6.

**Landed as of 2026-08-31**: 9 frozen lists (3 years × 3 strata, `outputs/frozen/`), all comfortably
above the initial-100 floor. `03_ceo_export.py` produced and this session manually uploaded the 3
`ceo_upload_fy<FY>.csv` (LON/LAT/PLOTID only — never `stratum`/`burned`, per the CEO-hygiene rule
in that script's docstring) as GEE table assets:
`projects/mapbiomas-argentina/assets/FIRE/VALIDATION/ceo_points/ceo_points_fy<2003|2013|2022>`.
**Still open**: pool 2 (above); the exact-`Nh` pixel census (§4.4) — `weights_launch()` in
`01_strata_export.py` is still the old `reduceRegion`-at-country-scale approach and was **not
re-tested** with the geometry fix (verify before assuming it's still broken — it very plausibly
isn't); the validator-facing `ceo_val_00_template` GEE script (repo `fuego`, not this repo) still
points `POINTS_ASSET_PREFIX` at the `ceo_points_demo_sierras_cordoba_fy` demo asset and needs
updating to `ceo_points_fy` before real interpretation starts.

