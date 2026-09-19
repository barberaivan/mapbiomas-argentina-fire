> **Extracted from** `collection-01/docs/07-vector_to_raster.md` §13.4, §13.5, §13.6 and §7's
> `--stats` failure table @ `f403d8c` (2026-09-18).
> Lab notebook — the record of building the step, not documentation of it.

# 07 — Exporting the polygon layer, and two export post-mortems

Three stories about GEE exports in this step: whether one merged 1.26 M-feature table export was
feasible (and why its EECU counter reads ~0), which account had to submit it, and the duplicated
FY2021 features that no count revealed. The live rules each produced are in the step doc.

### 13.4 Was one merged export feasible? — measured, then tried

The honest answer beforehand was *probably, but this is the one export in step 07 not to bet on*:

- the 28 source shapefiles hold **5.12 GB** of raw `.shp` geometry for 1.689 M objects (~190
  vertices/polygon), so the fire-only subset is **~4–4.5 GB**. GEE already stores exactly that in the
  28 source assets, so reading is not the question — one `Export.table.toAsset` shuffling 1.26 M
  complex multipolygons is (that was v1's size; v2 is 1.01 M), and its failure mode (`User memory
  limit exceeded`) arrives *after* hours;
- precedent is against it: Brazil ships `mbfogo_col5_<year>_v1` **per year**, our scars are 27
  per-year assets, `objects_raw` is 28. Nobody in the network ships one merged all-years vector;
- building it locally and ingesting is worse — >2 GB breaks the Shapefile limit and no GCS bucket is
  reachable (docs/06 "Upload to GEE").

So: **`--year 2012` first** (22,224 polygons — landed in **3 m 09 s**, schema and count exact on the
asset), then the merged task, with `--per-year` as a fallback that wastes nothing because the 2012
asset is already the first of its 28. If the fallback is ever needed, `--check` prints the one-liner
that loads the folder as a single FC.

The FY2012 timing is also the only scaling evidence there is: 57× the features, so a several-hour
task if it scales gracefully at all.

⚠️ **Do NOT read `batchEecuUsageSeconds` as progress on this task.** It sits at ~0.13 EECU-seconds
for hours and looks exactly like a task doing nothing. It isn't: **EECU bills compute, and a table
export of already-stored features is I/O-bound**. The evidence, all from this project:

| Task | Result | EECU-s |
|---|---|---|
| `arg07e_burned_area_polygons_2012` (22,224 features) | ✅ landed, schema + count exact | **0.0087** |
| `polygons_data_*`, `manual_edits_2015_ivan` (stored-FC exports) | ✅ | 0.002–0.005 |
| `BA_final_area_ha_por_clase_*` (exports that *compute*) | ✅ | 11,835–32,339 |
| the 27 `mobstats_*` histograms (whole-country `reduceRegion`) | ✅/running | 576–7,251 and climbing |

FY2012 settles it: an identical graph that produced a *verified* asset spent its entire successful
3-minute run accruing 0.0087 EECU-seconds. And the counter is genuinely live — Google's
[near-real-time reporting announcement](https://medium.com/google-earth/making-progress-reporting-earth-engine-compute-usage-in-near-real-time-2cdfc6fcc1db)
made `batchEecuUsageSeconds` update continuously for RUNNING tasks, which the histogram column above
demonstrates in the same minutes — so a static ~0 is a real measurement of near-zero *compute*, not a
reporting lag.

What that leaves as the only usable signals for a big table export: **`state`, and `updateTime`
advancing**. There are no `stages`/work-units for `EXPORT_FEATURES` either. The failure mode to watch
for is a state change to FAILED with `User memory limit exceeded` — it does not present as a stall.


---

### 13.5 Which ACCOUNT submits it, and why that matters

**The GEE task queue is per user.** Submitted by the primary account it would have waited behind the
27 histogram tasks (§7) before starting at all, so the merged export runs as the **second account**
(`ivanbarbera@comahue-conicet.gob.ar`) on the **`mapbiomas-argentina`** compute project, whose queue
was empty. Only the *compute* project changes — the destination asset is
`projects/mapbiomas-argentina/assets/…/FINAL_PRODUCTS/burned_area_polygons_v1` either way, so the
link shared with early users does not depend on who submitted it.

```bash
$PYTHON collection-01/workflow/07-burned_area_polygons.py --launch \
    --project mapbiomas-argentina \
    --credentials ~/.config/earthengine/credentials.comahue
```

**`--credentials` instead of swapping the resident file.** `ee.oauth.get_credentials_path()`
hardcodes `~/.config/earthengine/credentials` with no env override, so CLAUDE.md's rule is to `cp`
the account you want into place. Passing the file explicitly is strictly better: nothing is
clobbered, both accounts are usable in one session, and a half-finished swap cannot leave the wrong
token resident. `initialize()` builds a `google.oauth2.credentials.Credentials` from the file and
hands it to `ee.Initialize`.

Two consequences worth knowing:

- **The per-account backups had to be recreated** on this machine — only the resident `credentials`
  existed, so `credentials.gmail` was saved first, then
  `earthengine authenticate --force` (note the **space**; `authenticate--force` is a parse error)
  produced the comahue token, which was copied to `credentials.comahue` before the gmail file was
  restored as resident.
- **Monitoring has to ask twice.** `ee.data.listOperations()` is project-scoped *and* cross-user, so
  the resident account can see the comahue task — but only when initialized against
  `mapbiomas-argentina`. A watcher that polls only `C.GEE_PROJECT` reports the 07e task as
  `MISSING`, which looks exactly like a task that was never submitted. The same asymmetry applies to
  the **re-export**: `--overwrite` on an asset the comahue account created is submitted by that
  account too, so the whole cycle stays on `mapbiomas-argentina`.
- **Write permission could not be pre-flighted.** `getAssetAcl` on `FINAL_PRODUCTS` returns empty
  `writers`/`owners` because access comes from the cloud project's IAM, not a per-asset ACL. Reads
  were verified; a missing write permission surfaces as an immediate task failure
  (*"Insufficient permissions to create asset"*, the same error the step-03 backlog entry records),
  not hours in — so launching was the cheaper test.


---

### 13.6 ⚠️ `objects_raw_2021` is duplicated in storage, and no count reveals it

The first merged export **succeeded** and was still wrong: **1,264,328 rows** where 1,263,079 were
expected, the surplus being **1,249 FY2021 features present twice**, byte-identical in geometry (three
sampled pairs hash equal) and in all ten properties. FY2021's area came out **71,478 ha** high
(3,595,965 vs 3,524,487).

The re-export reproduced **the same 1,249 `oid`s**. That killed the first diagnosis — a random
shard-retry in the writer — because the same accident does not happen twice on a different graph. It
is deterministic, and it is in the stored source. Where it hides, measured on `objects_raw_2021`:

| stage | `.size()` | MATERIALISED (`aggregate_count`, `aggregate_array`) |
|---|---|---|
| raw | 66,393 | 66,393 |
| `+ .filter(fire_filter())` | 53,263 | 53,263 |
| `+ .map(one)` | 53,263 | **54,514** |

`size()`, and any aggregation over a *plain filtered stored* collection, is answered from the asset's
**metadata**. Put a `.map()` in the chain and the aggregation can no longer be pushed down to storage,
so GEE has to **iterate** the table — and iterating returns ~1,251 features the metadata denies. An
export iterates, so it writes them.

Two lessons outlast the bug:

1. **A count that agrees with itself is not a clean bill of health.** `size()`,
   `aggregate_count('oid')` and `len(aggregate_array('oid'))` all reported 53,263 on the filtered
   source. Three numbers, one pushed-down answer, all three wrong about what a read returns — and
   that is what made the source look innocent for two whole exports. The honest check materialises:
   put a `.map()` in front, or count on the **landed asset**.
2. **A COMPLETED task is not evidence that each feature was written once**, and the ~0 EECU of a table
   export (§13.4) says nothing either way. The original `--verify` — size, schema, one feature —
   passed the bad asset without a murmur.

**`--per-year` would not have helped**, which is worth recording because it was explicitly kept as
insurance against this symptom: FY2021 exported *alone* lands at the same 54,512 rows. The export's
size was never the variable. It goes, as originally planned.

**The fix** is `distinct('oid')` inside `fires()` — one row per object, the invariant actually wanted,
hashing one short string. It is applied per fire-year and **skipped for FY2000**, whose 4 rows for
`2000_57529` are a legitimate vertex split that `distinct('oid')` would collapse to 1, losing ~1.3 Mha
of that fire (§13.7). `distinct(['oid', '.geo'])` is the alternative that needs no exception —
measured to work, FY2021 54,512 → 53,263 — but it hashes the serialised geometry of every feature,
~4 GB of multipolygon, to buy a distinction that matters in one year. Verified before relaunching:
`fires(2021)` **materialised** is now 53,263, in 34 s.

The root cause belongs upstream — `objects_raw_2021` should be re-ingested by step 06 (BACKLOG). Until
it is, the guard in `fires()` is what stands between that asset and every product derived from it.


#### Re-measured 2026-09-18 — still there, and the count depends on the query

A new lab entry, appended: the text above is the July record and stands as written.

The asset was never re-ingested (`updateTime` `2026-07-28T20:12:31Z`), and `fires(2021)` with the
guard disabled still materialises **54,514 rows for 53,263 distinct `oid`** — the July figure to the
row. Three things are new:

- **What we uploaded is clean.** `objects_raw_2021.shp/.dbf` in `data/objects-upload-cache/` holds
  **66,393 records for 66,393 distinct `oid`**, and `objects_2021_pred.csv` matches it row for row.
  Whatever duplicates the rows is on the GEE side of the ingest, so a re-ingest from the zip already
  on disk is the fix — there is nothing to rebuild first.
- **The surplus is query-dependent**, which one export could not reveal. Measured the same day with
  a `select()`-bearing map: unfiltered **66,393 → 66,393**; `fire == 1` **54,602 → 54,602**;
  `area_ha >= 1` **64,551 → 64,792** (241 surplus); `fire == 1 & area_ha >= 1` **53,263 → 54,514**
  (1,251 surplus). A *range* filter on `area_ha` exposes rows an equality filter on `fire` does not,
  and the number moves with the predicate. "How many duplicates does this asset hold" has no answer.
- **A bare `.map()` does not materialise**, so lesson 1 above needs tightening. Under the export's
  own filter, `map(f => f.set(…))` and a map that rebuilds each feature from its geometry both come
  back at the clean 53,263; only a **`Feature.select()`** in the map — what `one()` does — surfaces
  the 1,251. The July table's `+ .map(one)` row is right about `one`, not about `.map`.

Consequence for the re-ingest: **no count is an acceptance gate**, because the counts are per-query.
The only check that means anything is `fires()` with the guard disabled, compared against the local
66,393 / 53,263.
