> **Extracted from** `collection-01/docs/07-vector_to_raster.md` §8.1, §9.1, §12.5 and §12.8
> @ `f403d8c` (2026-09-18) — the dated verification tables, in build order.
> Lab notebook — the record of building the step, not documentation of it.

# 07 — The verification log

Four audits, all against the **landed assets** rather than the computed graph, which is the
question that catches export-time grid, dtype and masking surprises. Each was run on the v1 build;
what the step doc keeps is the invariant each one established, not the numbers.

### 8.1 The built result, and the audit that closes

Run 2026-07-29: pass 1 took **41 min** (28 fire-years, 5 workers), pass 2 **96 min** (27 calendar
years, 2 workers × `OBJ_CORES=6`), no failures in either. Output: **27 packages, 2,734,416 scars,
69,020,102 ha, ~1.1 GB** of zipped Shapefiles, all 27 passing `validate_scar_zips.py`.

**Every accepted object pixel is accounted for, exactly:**

```
  accepted object px (28 fire-years)     911,617,919
  − calendar 1998, not published           1,058,206     (FY1998's Nov–Dec tail, §2)
  = inside the published series          910,559,713
  − intra-year reburn, deduped               269,043     (later month kept)
  = expected calendar px                 910,290,670
    actual, summed over the 27 years     910,290,670     difference 0
```

Nothing is silently lost or double-counted anywhere in the fire-year → calendar-year
transformation. The three sinks are the published years, the one unpublishable edge year, and
reburn — and they sum to the input. Reproduce it from the per-year `scars_<Y>_summary.csv` files
plus the `reburn:` lines in `logs/07_scars_<Y>.log`.

Largest calendar year: **2001, 227,146 scars / 5.25 Mha** — FY2000's very large Jan–Apr 2001
portion (47.2 M px) lands there, which is why it is bigger than either adjacent fire-year total.

**No size class is written into the vectors.** It is derived in GEE from `area_ha`
(`C.SCAR_SIZE_LOWER_HA`), so the ranges are a one-line, one-task change rather than 27 re-uploads.
That mattered: the reference script's ranges turned out **not** to match the published legend, and the
classes were switched to the legend's after the vectors were already built (docs/external/mapbiomas-fuego-reference.md "Stage 4, scripts 4–6 — the scar-size chain").

---


---

### 9.1 The built result, verified on the LANDED assets

All three exported 2026-07-29. Checked against the exported assets, not the graph — a different
question, and the one that catches export-time grid or masking surprises:

| Asset | Bands | dtype | Grid |
|---|---|---|---|
| `…_annual_burned_id_v1` | 27, `scar_id_1999 … scar_id_2025` | int | pinned, 74085 × 123601 |
| `…_annual_burned_area_ha_v1` | 27, `scar_area_ha_1999 …` | float | idem |
| `…_annual_burned_scar_size_range_v1` | 27, `scar_area_ha_1999 …` | int | idem |

Over the Chaco audit box, calendar 2003 / 2020 / 2025: `month px == scar px == size px`
(15,492 / 32,559 / 27,508), **`month-only = scar-only = 0`** in every year, and **0** pixels where the
stored size class disagrees with recomputing it from the painted `area_ha`. The mask invariant holds
on the published rasters, not just in the expression that built them.

**The monolith held**, so the `--per-year` + `--merge` fallback and the `--roi` smoke test were
deleted rather than left as a second path to maintain (docs/08 open decisions do not cover this; it
was a build-time hedge). No GEE limit was ever measured against one task painting 27
FeatureCollections — it simply worked. The empty `FINAL_PRODUCTS/scar_year_parts` collection that a
dry run once created is left for Iván to delete.

---


---

### 12.5 What was verified before launch

`--check` prints the band bookkeeping for all nine products plus per-year ROI counts; that plus a
value-level decode of every encoding was run on the Chaco 0.5° box before submitting:

| Check | Result |
|---|---|
| Band names / counts | 27 / 27 / 27 / 27 / 53 / 53 / 53 / 53 / 27, `year_last_fire` = `classification_2000 … classification_2026` |
| `monthly_burned_coverage` decode | `max │mc//100 − month│ = 0`, `max │mc mod 100 − L│ = 0` |
| `annual_burned_coverage` decode | `max │ac − L│ = 0` |
| `frequency_burned_coverage` decode | `max │fc//100 − freq│ = 0` |
| `accumulated_burned_coverage` decode | `max │acc_cov − L(2025)│ = 0` (window `1999_2025`, moving end 2025) |
| Single-year window vs annual | `freq_2025_2025` = `annual_2025` = **27,508 px**, exactly |
| Cross-product mask agreement | `freq_1999_2025` = `accum` = `accum_cov` = `year_last_fire` = **241,281 px**, exactly |
| `year_last_fire` values | `classification_2000` is 1999 only; `classification_2026` spans 1999–2025 with the expected per-year counts |

Note the ROI histograms taken with `frequencyHistogram` come out a few pixels below the
`sum().unweighted()` counts (241,195 vs 241,281) — that is `reduceRegion`'s **edge weighting** of
partial pixels at the box boundary, the same artefact §9 records for the scar check, not a
disagreement between products.


---

### 12.8 All nine landed — re-verified on the exported assets

The nine tasks all reported SUCCEEDED by 2026-07-30 13:16 (the last was
`accumulated_burned_coverage`, the final col-3 re-launch). §12.5 checked the *computed graph* before
submitting; this re-runs the same audit against the **landed assets**, which is the different
question — it catches export-time grid, dtype and masking surprises:

| Check | Result on the assets |
|---|---|
| Band counts | 27 / 27 / 27 / 27 / **53** / 53 / 53 / 53 / 27, `year_last_fire` = `classification_2000 … classification_2026` |
| dtypes | uint8 / uint8 / **uint16** / uint8 / **int16** / int16 / uint8 / uint8 / **uint16**, pyramiding `MODE` on every band |
| Grid | all 12 step-07 images: `74085 × 123601`, EPSG:4326, `C.SNIC_TRANSFORM` exact — no `scale=30` drift |
| `lulc_asset` on the four coverage products | `…collection3_integration_v1_buffer` — the col-3 re-launch is what landed, not the cancelled col-2 one |
| Chaco box, 2003 / 2020 / 2025 | `month == monthly == annual == mcov == acov` = 15,492 / 32,559 / 27,508 |
| Decodes | `max │mc//100 − month│ = 0`, `max │mc mod 100 − L│ = 0`, `max │ac − L│ = 0`, `max │fc//100 − freq│ = 0`, `max │acc_cov − L(2025)│ = 0` |
| Cross-product masks | `freq_1999_2025` = `accum` = `accum_cov` = `freq_cov` = `year_last_fire` = **241,281**; `freq_2025_2025` = `annual_2025` = **27,508** |
| Scar chain vs month mask | `month_only = scar_only = 0` in 2003 / 2020 / 2025 |

Every number is identical to the pre-launch graph audit. Two **metadata** leftovers were not, and
both were repaired in place on 2026-07-30 with `ee.data.updateAsset` — metadata only, no re-export:

- the five **non-coverage** products carried `lulc_asset = …collection1_integration_v8_buffer` — a
  land-cover collection they never touch, and a stale one at that, since only the four `*_coverage`
  products were re-exported against col-3. They now say `lulc: "not used — this product encodes no
  land cover"`, and `07-subproducts.py` only stamps `lulc_asset`/`lulc_year` on the four products
  that actually cross one in;
- `monthly_burned` had inherited the 1999 month image's own block through `ee.Image.cat` —
  `year: 1999`, `fire_years: 1998,1999`, `name: …fire_mask_v1_1999`, plus `pixel_unit`,
  `min_fire_ha`, `fire_call`, `lulc_mask`, `solitary_pixel_filter`. Every one of those is false or
  meaningless on a 27-band product. The other eight escaped it because they are built by
  arithmetic, which **drops** input properties; `monthly_burned` was the one built by `rename`
  alone. There is no server-side "clear properties" and `.set()` only adds, so the script now
  inserts an `.add(0)` — a band-wise op — before renaming, which is what makes a re-export come out
  clean. The mask statements remain on the 07a month images, where they are true.

All nine blocks are now uniform: `source`, `region`, `band_format`, `years`, `derived_from`, plus
`lulc_asset` + `lulc_year` on the four coverage products or `lulc` on the other five.
**`scripts/audit_product_properties.py`** is the standing drift check (dry run by default, `--apply`
to write) — worth running after any re-export or any move of `C.PRODUCT_LULC`, because a silent drift
here is how a published asset ends up advertising the wrong land-cover collection. Bands, dtypes and
pyramiding were re-read afterwards and are untouched.
