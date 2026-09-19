# 08 — Post-processing: Argentina's route through the network's spec

Everything up to step 07 is **ours** — our own mapping method, from observation-level burn
probability to object-based classification. Step 08 is **not**: it is the **post-processing every
MapBiomas Fuego country runs**, so that the published products are identical in name, band format,
encoding, dtype and legend across the network. This file says what that spec requires of Argentina,
how our route through it differs, and how the questions it raised were settled. It is written for
a reader comparing Argentina with the other countries — the spec itself is
[`external/mapbiomas-fuego-reference.md`](external/mapbiomas-fuego-reference.md), and what Argentina
actually built and runs is [`07-vector_to_raster.md`](07-vector_to_raster.md) (the pixels) and
[`07-published_products.md`](07-published_products.md) (the published assets).

> **Rule for this step: do not innovate.** Copy the reference and adapt only the country-specific
> bits — paths, LULC, regions, mask classes. Anything else changed breaks cross-country
> comparability, the Workspace legends, and the platform that reads these assets.

## Foundations

**The network's post-processing is a spec, not a program we run.** The reference implementation
assumes the reference *mapping* method (Alencar et al. 2022: a deep-learning classifier over annual
quality mosaics, producing a masked annual burn raster whose month is inferred from min-NBR). Ours
produces something different and richer — dated fire **objects** with a probability attached — so
several stages of the reference are already satisfied upstream, and one is satisfied better:

| the reference's stage | in Argentina |
|---|---|
| consolidate the unmasked collection | nothing to consolidate — we have no unmasked variant |
| LULC mask | **already upstream and stricter**: `veg_fire` comes from the previous-year LULC and every non-burnable class is unreachable as a SNIC candidate (verified: zero `candseed > 0` on `veg_fire` 24 or 25). The reference drops water only |
| solitary-pixel filter (≤ 4 px, 4-connected) | **already upstream and stricter**: the `>= 1 ha` object cut is ≈ 11 px |
| month coding, inferred from min-NBR | **measured per pixel** from `abs_date` |
| the subproducts | ours, built by `07-subproducts.py` and `07-scar_rasters.py` from the same per-pixel calendar-year assignment |

Running the reference's mask and pixel filter anyway, "so the rule is identical across countries",
would be a no-op for the mask and would only shave true positives off calendar-year fragments of
already-qualifying fires. The month-of-burn collection records `lulc_mask` and
`solitary_pixel_filter` properties saying the rule was applied **upstream**, not skipped.

## How Argentina's route differs

**Vectors only; GEE does the pixel work.** Nothing new is uploaded for the month layer — step 06
already put the whole object set in GEE (`objects_raw_<fy>`, 28 FCs, `docs/06` "Upload to GEE").
Step 07 filters it at read time to `fire == 1 & area_ha >= 1` and paints it against the SNIC assets
that are already there. The per-pixel calendar year and month that R computed locally are knowingly
recomputed in GEE; that redundancy is the price of not moving 28 fire-years × ~248 *cartas* of
imagery. One thing *is* uploaded by hand: **`scars_<Y>`, 27 FeatureCollections**, because the
8-connected labelling cannot be done in GEE (`connectedPixelCount` caps at 1024 px).

Three things this buys, all of them consequences of dating **per pixel** rather than per object:

- **Per-pixel month, measured** rather than inferred from min-NBR — better grounded than the
  reference method, at no transport cost.
- **`annual_burned`, `monthly_burned` and `scar_size` agree pixel-for-pixel**, because all three
  derive from one calendar-year assignment. Painting each whole object into its modal
  `year_calendar` would have been cheaper but would make `scar_size` disagree with `annual_burned`
  on every scar straddling 31 December — in Argentina not a corner case, since the
  Patagonian/Pampean season peaks Dec–Feb. That is why the fire-year is non-calendar in the first
  place (`04` "The fire-year").
- **Faithful to the network's semantics** — their scars are calendar-clipped too — with one
  improvement: ours are labelled from the burn mask with the standard 8-connectivity, so the
  published definition matches while the *underlying* fire objects stay separate in our own
  database.

The cost is the mirror image: **a fire that straddles 31 December becomes two scars**, one per
calendar year. That is intended, not a defect.

## What Argentina delivers

**All six subproducts** — *anual, mensual, acumulado, frecuencia, último año, tamaño de cicatriz*.
The guide's country table marks Argentina for all six; Chile, Ecuador and Venezuela deliver only the
first four. `severity_class`, `interval_since_fire` and `time_after_fire` appear in the publish
script's lists but **not** in the country table — Brazil extras, not ours.

**Delivered and verified on the landed assets** (2026-07-30, re-verified after the `_v2` re-export):
the month-of-burn collection, the 27 scar FCs, the three scar rasters and the nine derived
subproducts. Per-item detail, verification numbers and run commands are in `docs/07` and
`docs/07-published_products`; the checklist as it stood at delivery is
[`notes/08-corrections_and_delivery.md`](notes/08-corrections_and_delivery.md).

**Alongside the six, and not one of them: the fire-object polygon layer.** Every mapped fire, all
28 fire-years, merged into `FINAL_PRODUCTS/burned_area_polygons_v<N>`
(`docs/07-published_products` "07e — the fire-object polygon layer"). It is **ours** — we share the
link ourselves rather than hand it to the network's public copy, which takes an explicit subproduct
list — and the **ATBD says so**, because a user who finds the polygons has to know they are
fire-year objects and not the calendar-year scars.

Stage 5 (statistics) and stage 6 (public assets + Workspace catastro) are **not this file** — see
[`../statistics/docs/statistics.md`](../statistics/docs/statistics.md).

## The three questions this step raised, and how they settled

None of them is open any more. The rest were closed by measuring rather than deciding, and the
reasoning is kept in [`notes/08-corrections_and_delivery.md`](notes/08-corrections_and_delivery.md).

- **The `COLLECTION-1` spelling stays ours.** The folder spelling is Argentina's; the asset *names*
  inside follow the network exactly (`C.product_name()`). The Brazil team adapted their side to read
  it, so there is no rename at publish time and nothing to rebuild.
- **Argentina does publish the fire-object polygons.** The merged layer is
  `FINAL_PRODUCTS/burned_area_polygons_v<N>`, it stays **our** asset, and we share the link
  ourselves — it is not one of the six subproducts and `ToPublish/2-toAsset-Public` copies an
  explicit subproduct list rather than a folder, so it cannot be swept into the network's public
  collection. It is named `polygons`, not `vectors`, so it cannot be confused with the
  calendar-year scars, and the ATBD states what it is. Precedent was favourable anyway: Brazil
  publishes col-5 annual burned vectors publicly.
- **The territorial layer is the ecorregiones**, not the five fire regions —
  `ANCILLARY_DATA/VECTOR/ARG/ARG-Political_Level_2-13Ecorregiones_3857`, 13 features keyed by
  `GEOCODE`, which is what the statistics stage already runs on and what the platform's territory
  selector must name ([`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) §7).
  Our own products have no region dimension at all, so nothing in step 07 is cut by it;
  `regiones_fuego_argentina_v1`, which every reference script names, does not exist here under that
  name and is not needed (`docs/07` "What is still open").

## Gotchas

- **The `*_coverage` products are the easiest to forget and are exactly what the statistics read**
  (`../statistics/docs/statistics.md`). All four exist.
- **The coverage products cross `C.PRODUCT_LULC` — the *published* col-3,
  `mapbiomas_argentina_collection3_pb` — not `C.MAPBIOMAS_LULC`** (col-2 v8). The latter is the
  model-side layer `veg_fire` was built from and must stay frozen. Col-3 carries
  `classification_2025` natively, so nothing is duplicated forward. The `_v1` coverage products on
  the asset store were built against the *preliminary* col-3, which is part of what the `_v2`
  re-export is for (`docs/07` "The `_v2` re-export").
- **The network's visual validation gate is a human step**, not an unattended run:
  `1-Toolkit_Collection1/Visualize-Collections-Fire` over a few years, by eye, before IPAM copies
  anything to `mapbiomas-public`.
- **`FY2025 has no dieback padding`** (it needs the FY2026 image), so the series' last year is
  asymmetric in that one respect. Worth a line in the ATBD.

## Related

- [`external/mapbiomas-fuego-reference.md`](external/mapbiomas-fuego-reference.md) — the reading of
  the network's repo: the six launch stages, the asset topology, the reference chain script by
  script, and the scar-size legend. Pinned to a commit, and liable to go stale.
- [`07-vector_to_raster.md`](07-vector_to_raster.md) — what Argentina actually built: the object
  selection, the calendar partition and 07a–07c — and
  [`07-published_products.md`](07-published_products.md) — 07d's nine subproducts and 07e's polygon
  layer.
- [`notes/08-corrections_and_delivery.md`](notes/08-corrections_and_delivery.md) — the three
  corrections to an early draft, the July 2026 delivery checklist, and the full decisions list.
- [`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) — stages 5 and 6.
