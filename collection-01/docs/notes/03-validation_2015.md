# 03 — Validating the first exported tile (`bpts_2015_SK-19-Y-A`)

> **Extracted from** `collection-01/docs/03-bpts.md` §6 and the first two bullets of §7
> @ `76dca98` (2026-09-18) — those sections no longer exist under those names.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcome: GEE reproduces the hand-computed raw-scale logit to ~7e-9, and
the buffered region raster (the §7 prerequisite) has since been exported and is what production
reads.

## 6. Validation (against `bpts_2015_SK-19-Y-A`)

Done with the non-buffered `…/ARG-Regiones-MapBiomas` as a temporary stand-in for the
not-yet-exported buffered raster:

- **Coefficients:** all 130 terms parse; every focal/prev factor maps to a real
  `add_indices` / mosaic band name (7 blocks: 1/11/32/22/10/22/32).
- **Burn probability:** GEE `prob` reproduces the hand-computed raw-scale logit to **~7e-9**
  for a real pixel (`veg_fire = 21`) — confirms coefficient ordering, band alignment, raw
  products, the `veg_fire→coef` remap, and the sigmoid.
- **Metrics:** all bands verified by hand on a synthetic series (delta/minfore peaks, jumpgap
  / widths, pmax1/2/3, K=2 family). *(Validation predates the §3.7 drop of `timediff_*`; the
  remaining 16 bands are unchanged.)*
- **Masking:** insufficient-padding and no-obs pixels mask cleanly (no errors), `n = 0`.
- **Realism:** over the exported tile `n` averages 25 (max 54), with `−2` sentinels present;
  ~**29,300 ha** of strong persistent detections (`delta3>0.5 & pmax3>0.5`) centred at
  −71.71, −42.40 — the 2015 Cholila forest burn (~40,000 ha).

---

## 7. (the first two bullets of "Open items / future changes")

- **Prerequisite:** export the buffered `C.REGION_RASTER`
  (`scripts/export_region_raster.py`) before a production run; until then border-buffer pixels
  read as non-observed (`n = −2`). (That export is slow not from compute but from re-rasterizing
  lazily-computed buffer/difference geometries over ~3 B pixels — materialize the buffered FC
  first if speed matters.)
- **`date_post` timing:** over the Cholila scar mean `date_post3` ≈ DOY 220 (early August 2015),
  later than the Feb–Mar fire — likely the delta-argmax favouring a post-winter persistence jump.
  Worth a domain look; it's exactly what the manual masking/review step exists to catch.
