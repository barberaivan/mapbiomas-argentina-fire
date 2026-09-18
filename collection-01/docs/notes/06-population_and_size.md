> **Extracted from** `collection-01/docs/06-object_model.md` §9 "The whole population — size and
> uncertainty" @ `fc6ddef` (2026-09-18) — the doc keeps the conclusions, not the tables.
> Lab notebook — the record of building the step, not documentation of it.

# 06 — The whole population: size, uncertainty, and the minimum-size decision

## 9. The whole population — size and uncertainty

`notebooks/objects-analysis.qmd` scores all **1 689 419** objects (28 fire-years; 36 unscored) and
asks the question the minimum-size decision was supposed to rest on: *is the model measurably less
able to classify small objects?* `% undecided` = the `p_q05`–`p_q95` interval straddles the cut that
applies to that object.

| display class | objects | area (kha) | cut | median `p` | mean `p_width` | % called fire | % undecided |
|---|---|---|---|---|---|---|---|
| < 0.5 ha | 15 070 | 4 | 0.250 | 0.187 | 0.412 | 44.5 | 49.6 |
| 0.5–1 ha | 42 514 | 34 | 0.250 | 0.366 | 0.322 | 59.3 | 40.5 |
| 1–50 ha | 1 409 244 | 16 787 | 0.202 | 0.649 | 0.319 | 78.6 | 31.0 |
| 50–300 ha | 192 380 | 20 465 | 0.436 | 0.736 | 0.310 | 68.3 | 31.5 |
| 300–1000 ha | 22 791 | 11 534 | 0.690 | 0.950 | 0.217 | 77.4 | 24.9 |
| ≥ 1000 ha | 7 384 | 36 167 | 0.690 | 0.989 | 0.129 | 90.3 | 13.2 |
| **all** | **1 689 383** | **84 991** | — | — | **0.317** | ~77 | **31.3** |

**The answer is no — or rather, not distinctively.** Uncertainty falls monotonically with size
(width 0.412 → 0.129, undecided 50 % → 13 %), the expected direction, but the model is **unsure
everywhere**: a mean `p_width` of 0.317 means the average 5–95 % interval spans 32 points of
probability, and even the ≥1000 ha class cannot place 13 % of its objects on one side of its cut. So
a minimum-size cut removes objects that are *somewhat* worse than average, not objects that are
qualitatively unclassifiable:

| cut | objects dropped | area dropped | fire-area dropped | dropped: width / undecided | kept: width / undecided |
|---|---|---|---|---|---|
| 0.5 ha | 0.89 % | 0.005 % | 0.002 % | 0.412 / 49.6 % | 0.316 / 31.1 % |
| 1 ha | 3.41 % | **0.044 %** | 0.032 % | 0.346 / 42.9 % | 0.316 / 30.9 % |
| 2 ha | 12.60 % | 0.321 % | 0.296 % | 0.332 / 40.8 % | 0.315 / 29.9 % |
| 5 ha | 33.99 % | 1.749 % | 1.665 % | 0.317 / 34.9 % | 0.317 / 29.4 % |

So **the honest argument for a 1 ha minimum is cost/benefit, not uncertainty**: 3.4 % of objects for
0.044 % of area — a large reduction in count and noise for a rounding error in the headline number.
Do not claim the model "cannot classify" sub-hectare objects; it classifies them the same way it
classifies everything, only with wider intervals, and it does push them toward non-fire (median
`p_mean` 0.187 in `<0.5 ha` vs 0.989 in `>=1000 ha`, so the discrimination is real).

**What the width actually indicates is covariate shift.** 5255 labels against 1.69 M objects,
collected where fires were known rather than sampled from the object population — BART widens its
posterior exactly where it has no data, and 31 % undecided is that message. This reinforces, from
the population side, the caveat §6 reached from the label side: the binding limitation is the
labelled sample, not the model or the cut. The deployed cuts should be treated as a lower bound.

### Also measured: the pixel scale is latitude-dependent

`area_ha` is **not** `n_pixels * 0.09`. Objects carry lat/lon pixel coordinates (~30 m *at the
equator*) and area is measured on the ellipsoid, so one pixel is `900*cos(lat)` m² — **831 m² at
22° S down to 517 m² at 55° S** (median 778). Harmless, but two consequences: a size class is a
pixel-count *range* (1 ha = 12 px in Formosa, 19 px in Santa Cruz), and the same 15-px object
changes class between the north and Patagonia. This is the first reason `n_pixels` is not a size
(§4); the importance analysis is the second. Also visible there: the `n_pixels` count **dips** from
3796 one-pixel objects to 778 at five, then climbs monotonically (6 px → 3081 … 20 px → 12 474). A
segmentation floor would give a hard cut, not a dip-then-rise, so something is producing isolated
1–2 px objects that 3–5 px does not get — the step-05 1-px dilation connectivity hack is the
suspect (BACKLOG).
