> **Extracted from** `collection-01/docs/08-postprocessing.md` §§6.2–6.4 (the three
> `CORRECTION —` sections), §7 (the delivery checklist) and §8 (open decisions)
> @ `90462b7` (2026-09-18) — that file is now a short signpost and `docs/external/`.
> Lab notebook — the record of building the step, not documentation of it.

# 08 — What the first draft of the post-processing doc got wrong, and the July 2026 delivery

Three claims in an early draft of `08-postprocessing.md` were wrong. They are corrections to our
reading of *the network's* code, not to our own design, which is why they are here. Each is a live
rule today and each is stated in `docs/07`, measured: the LULC mask and the solitary-pixel filter
are already embedded upstream; polygon paint reproduces the object pixel set exactly; the
calendar-year scars are a fresh 8-connected labelling pass.

### 6.2 CORRECTION — the LULC mask and the solitary-pixel filter are NOT owed

The earlier draft listed both as things "we still owe" from stage 3. **We do not.** Both are already
in the pipeline, and stricter than the reference:

- `veg_fire` comes from the **previous-year MapBiomas LULC**, and every non-burnable class is
  unreachable as a SNIC candidate (no `VEG_TABLE` entry → `THR_DEF = 9` → no delta ever passes).
  Verified on FY2000/2014/2023 over ~3.6 M candidate pixels: **zero `candseed>0` pixels on
  `veg_fire` 24 (non-burnable) or 25 (non-observed)**. The reference drops water (26) only; ours
  drops every non-burnable class.
- The `>= 1 ha` object cut (≈ 11 px) is stricter than deleting 4-connected components of ≤ 4 px.

Running the reference's versions anyway "so the rule is identical across countries" — which the
earlier draft recommended — would be a no-op for the mask and would only shave true positives off
calendar-year fragments of already-qualifying fires. The output collection keeps the name
`collection1_fire_mask_v1` (that is the asset downstream scripts read) and records
`lulc_mask` / `solitary_pixel_filter` properties saying the rule was applied upstream, not skipped.

### 6.3 CORRECTION — painting a polygon does not fill its interior

The earlier draft's §6.4.2 warned that `ee.Image().paint(fc, 1)` "fills holes and gaps" and that the
result must always be intersected with the real burned mask. **That is not what happens.** Step 05
vectorized the *accepted pixel set* with `as.polygons(dissolve=TRUE)`, so holes are true interior
rings and the boundary follows pixel edges; both GEE's `paint` and `terra::cells` use
pixel-centre-in-polygon and recover exactly that set. Verified twice:

- `terra::cells(country template, accepted polygons)`, FY2020 → **55,008,255** cells vs
  `sum(n_pixels) = 55,008,255`. Exact, over 55 M pixels. Every fire-year reports `EXACT`.
- In GEE, `paint` vs the `candseed` burned mask → **0 painted-but-not-burned** on the audited ROIs.

The `candseed > 0` intersection is kept on both sides as a **guard**, and the residual is logged per
year rather than assumed. What *is* real is the step-05 **longitude cut**: `candseed==3` east of
−70.6 was dropped before labelling, so the objects exclude it while `snic_<fy>` still carries it
(65,752 px over 28 fire-years) — GEE replays the cut with `pixelLonLat`.

### 6.4 CORRECTION — the scars are a new labelling pass, not a regrouping

The earlier draft proposed getting the calendar-year scar parts by grouping step 05's pixels by
`(pid, cyear)` — "without any new labelling pass and without re-vectorizing". That would have
produced *calendar-year parts of our dilation-connectivity objects*, which is not what the network
means by a scar. The published definition is "sets of spatially connected pixels within the same
year", so the scars are labelled afresh:

- **calendar** year, not fire-year;
- **plain 8-connectivity**, deliberately *not* step 05's 1-px-dilation connectivity, so two distinct
  fires that touch merge into one scar — matching the reference;
- and yes, a fire straddling 31 December becomes two scars, one per year. That is the intended
  consequence of per-pixel dating (§6.6).

`scar_id` is a fresh integer, 1..n within the year, ordered by the scar's first cell — deterministic
across re-runs. **No size class is stored in the vectors**; it is applied in GEE from `area_ha`, so a
legend change (§5.4 is still unresolved) does not mean 27 re-uploads.


---

# The 31 July 2026 delivery checklist, as it stood

## 7. What Argentina delivers, and when

**Argentina is expected to deliver all six subproducts** — the guide's country table marks Argentina
with *anual, mensual, acumulado, frecuencia, último año, tamaño de cicatriz* (Chile, Ecuador and
Venezuela deliver only the first four). `severity_class`, `interval_since_fire` and `time_after_fire`
appear in the publish script's lists but **not** in the country table — Brazil extras, not ours.

### By 31 July 2026 — the assets (this doc)

**All of it is exported and verified on the landed assets** (2026-07-30). The per-item detail, the
verification numbers and the run commands are in docs/07; this table is the delivery checklist.

| # | Item | State |
|---|---|---|
| 1 | Object FCs `objects_raw_<fy>` (28) | ✅ step 06 — no separate `fires_<fy>` upload; step 07 filters at read time (§6.1) |
| 2 | `collection1_fire_mask_v1` — the month-of-burn collection, 1-band uint8 per calendar year, properties set | ✅ **27/27** images (`07-month_of_burn.py`); the LULC mask and pixel filter are upstream, not owed (§6.2) |
| 3 | `scars_<Y>` (27) calendar-year scar FCs | ✅ **27/27 built, gated and ingested** — `validate_scar_zips.py` passes both on the packages and `--ingested` on what landed (docs/07 §8.1) |
| 4 | `annual_burned_id`, `annual_burned_area_ha`, `annual_burned_scar_size_range` | ✅ **3/3** (`07-scar_rasters.py`), verified on the exported assets: `month px == scar px == size px`, `month-only = scar-only = 0` (docs/07 §9.1) |
| 5 | `monthly_burned`, `annual_burned`, `monthly_burned_coverage`, `annual_burned_coverage`, `frequency_burned` (+`_coverage`), `accumulated_burned` (+`_coverage`), `year_last_fire` | ✅ **9/9** (`07-subproducts.py`), re-verified on the landed assets — band counts, dtypes, pinned grid, every coverage code decoding exactly (docs/07 §12.8). The four coverage products cross **LULC col-3 v1**, so nothing is duplicated forward (§8.3) |

⚠️ The `*_coverage` products are the easiest to forget and are exactly what the statistics read
(statistics/docs/statistics.md §2). All four exist.

**Not part of the network delivery, but built and shared alongside it:** the fire-object polygon layer
`FINAL_PRODUCTS/burned_area_polygons_v1` — every mapped fire, all 28 fire-years, ten properties,
1,263,079 rows for 1,263,076 objects / 69.12 Mha (docs/07 §13). It is **ours**, not one of the six subproducts, and
whether it may ever be *published* is §8.8. ✅ **Verified and shareable** (2026-07-31): `--verify`
clean on all 28 fire-years, dates ISO `YYYY-MM-DD`, `filterDate()` working, 19 properties set. It took
three exports — the first two carried 1,249 duplicate FY2021 rows (docs/07 §13.6).

**What is still owed on the asset side** — neither blocks the delivery, both belong to validation:

- the whole-country **month-histogram cross-check** (`--stats` / `--stats-read`, docs/07 §7): the GEE
  half is running, the local `scars_<Y>_months.csv` half has to be regenerated from
  `scars-pixels-cache` first;
- the network's **visual validation gate** (§2) — `1-Toolkit_Collection1/Visualize-Collections-Fire`
  over a few years, by eye, before IPAM copies anything to `mapbiomas-public`.

### Between 1 August and 24 September 2026 — statistics, publication, launch

See **[`09-statistics.md`](09-statistics.md)**: the area-statistics CSVs (computed by the network's
`2-Statistics/toolkit/v03/`, analysed by us in R — not in Looker), the territorial layer
(**ours to build**), the public-asset copy, the Workspace catastro, and the launch track
(ATBD, methodology page, downloads page, materials, event).

---


---

# The open-decisions list, as it stood on 2026-07-30

## 8. Open decisions

**Genuinely open, as of 2026-07-30:** #1 (the `COLLECTION-1` spelling, before the public copy), #8
(may we publish the fire-year vectors), #9 (`frequency_burned`'s band name — the only one that needs
an IPAM ruling before the platform reads the asset), #10 (the territorial layer, deferred to
~20 Aug). Everything else below is struck through and kept for the reasoning, not the question —
several were closed by *measuring* rather than deciding, and the notes say which.

1. ~~Asset naming~~ — **decided (provisional): keep `COLLECTION-1`**, ours, and rename at publish time.
   The asset *names* inside already follow the network exactly (`C.product_name()`). Revisit before the
   `mapbiomas-public` copy, which must use their spelling regardless.
2. ~~LULC mask classes per region~~ — **not applicable.** The mask is embedded upstream and is stricter
   than the reference (§6.2). Nothing to choose.
3. ~~LULC year coverage~~ — **resolved, and moot**: the coverage products cross against **LULC
   collection 3 v1** (`C.PRODUCT_LULC`), which carries `classification_2025` natively, so nothing is
   duplicated forward. It was never a blocker either way — duplicating the last year forward is what
   every reference country does, and `07-subproducts.py` reads the band list from the asset so it
   self-corrects. `C.PRODUCT_LULC` is deliberately **separate from `C.MAPBIOMAS_LULC`**, the
   model-side input `veg_fire` was built from (col-2 v8, frozen). Verified (docs/07 §12.1): col-3 v1
   has a byte-identical grid to col-2 v8 and to our lattice up to an integer 9953-column /
   −25102-row offset, its footprint contains the 2 km buffer, and its class codes max out at **77 <
   100** — the condition that makes the `*100 + L` encodings decodable. Still the only place LULC
   enters our chain.
4. ~~Month per pixel or per object~~ — **decided: per pixel**, from `snic_metrics.abs_date` (§6.5).
5. ~~`scar_id` numbering~~ — **decided: integer 1..n within the calendar year, ordered by the scar's
   first cell** on the global lattice. Deterministic and stable across re-runs; `oid` is unusable
   because `ee.Image().paint` needs a number.
6. ~~Scar-size ranges~~ — **RESOLVED 2026-07-29: the published legend's, not the reference script's**
   (§5.4). Confirmed from the Coleção 5 legend-code PDF *and* the live col-5 platform legend, so no
   IPAM ruling is needed. `C.SCAR_SIZE_LOWER_HA = [10, 250, 500, 5000, 10000, 50000, 100000]`. We write
   only **level 2** (values 1–8); the platform derives its level-1 aggregation
   (`<250 / 250–500 / 500–10 000 / 10 000–100 000 / >100 000 ha`) itself, exactly as Brazil's own
   asset does. Do NOT copy `6-export_scar_size_range_by_year`.
7. ~~Reburn rule~~ — **later date wins**, and it is nearly moot: the two fire-years feeding a calendar
   year are disjoint in month (§6.5), so `max` only fires on genuine reburn. Confirm nobody downstream
   expects otherwise.
8. **Our fire-year vector database** — ask whether Argentina may publish it as `annual_burned_vectors`.
   ⚠️ **Partly overtaken by events (2026-07-30):** the merged fire-object layer now EXISTS in
   `FINAL_PRODUCTS`, as `burned_area_polygons_v1` (1,263,079 rows for 1,263,076 objects, 69.12 Mha, docs/07 §13), by
   Iván's deliberate call — early users needed a link that survives a favourable ruling. It is named
   `polygons`, not `vectors`, so it cannot be confused with the calendar-year scars, and
   `ToPublish/2-toAsset-Public` copies an explicit subproduct list rather than the folder, so it
   cannot leak into a published collection by itself. **The question below is still open**, and if
   the answer is no the asset moves and the shared link dies with it.
   Precedent confirmed: Brazil publishes col-5 annual burned vectors publicly, one asset per year, at
   `projects/mapbiomas-public/assets/brazil/fire/collection5/mapbiomas_fire_collection5_annual_burned_vectors/mbfogo_col5_<year>_v1`,
   each polygon carrying a unique numeric `id` (Coleção 5 legend-code PDF §1.1). So the door is open.
   Until settled, keep it out of `FINAL_PRODUCTS` so it cannot leak into a published collection. Note
   `objects_raw_<fy>` currently lives under `WORKFLOW-EXPORTS`, not `FINAL_PRODUCTS`, so this is safe
   today.
9. **`frequency_burned` band name** — the publish map says `frequency_burned_{year1}_{year2}` while
   script 2 writes `fire_frequency_<y1>_<y2>`; confirm which the platform reads.
10. **The territorial layer — DEFERRED to ~20 August 2026, by Iván's call (2026-07-29).** Not needed
    for the 31 July asset delivery; it belongs to the statistics stage (statistics/docs/statistics.md), which cannot start
    until the 07d `*_coverage` products land anyway. Do not build it before then, because
    **which territories to cut by is still an open question** — possibly *not* the 5 fire regions at
    all, but a **vegetation-units map**. That decision comes first; the layer is mechanical after it.
    - When it is taken, note that `regiones_fuego_argentina_v1` does not exist *under that name* but
      ⚠️ **the "only the raster exists" claim was wrong**:
      `ANCILLARY_DATA/VECTOR/ARG/regiones_arg_col1_simplificada_num` is a 5-feature region vector with
      `Region` + integer `Zona` 1-5 (found 2026-07-29). If the 5 fire regions win, this is a
      rename/reproperty job rather than a build from the raster.
    - Two caveats to settle either way: it is **`simplificada`** (simplified geometry — the statistics
      are checked to ~1 %, statistics/docs/statistics.md), and its `Zona` numbering is **unverified** against
      `REGION_RASTER.region_id` and is not `C.REGIONS` order.
