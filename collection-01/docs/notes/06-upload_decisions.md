> **Extracted from** `collection-01/docs/06-object_model.md` §12 "Uploading to GEE" and §11's
> tool-choice paragraph @ `fc6ddef` (2026-09-18) — the doc keeps the recipe and the gate.
> Lab notebook — the record of building the step, not documentation of it.

# 06 — The upload: how it was decided, and the run of record

## Upload everything, not just the fire subset (2026-07-28)

The earlier plan was fire-only, to save space. Two reasons overrode it: an expert user needs the
rejected objects to find **fires the model missed** (a fire-only layer can only ever show
commission error), and the rejected objects with their predictors are the raw material for aiming
the next collection's label campaign. Measured, fire-only would have saved ~33 % of the geometry
with extreme per-year variance — not enough to justify a one-sided product.

## Why the ingest is by hand — the GCS investigation (2026-07)

`earthengine upload table` rejects any source without a `gs://` prefix
(`ee/cli/commands.py:_check_valid_files`) and the client library exposes no upload-URL helper (the
legacy `getTableUploadUrl()` is gone; the Code Editor stages through a browser-internal endpoint
with no public equivalent). A scripted ingest therefore needs a GCS bucket, and as of 2026-07 we
have none: `mapbiomas-fire-485203` has **no billing account** (bucket creation → `403 … billing
account … disabled in state absent`) and neither GEE account has `storage.buckets.list` on
`mapbiomas-argentina`.

## The NULL-code bug the validator caught

Unscored objects were leaving `fire_model`/`fire` unset in the DBF, which GEE would have read as
`0` — a silent "not fire" for objects that were never classified at all. Hence the −1 sentinel in
all three code columns, and the validator's NULL-code check.

## Run of record (2026-07-28)

28 zips, 1.3 GB, **ALL PASS** — 1 689 419 features, 5256 tagged objects, 1 295 006 called fire,
36 unscored. Format comparison on one year: 373 MB GPKG → ~880 MB GeoJSON → **73 MB zipped SHP**.

## A Shiny review app, and a whole-country raster overview — both declined

That covers Lican's suggestion without a Shiny app: the sampling-by-predictor-range panel is a QGIS
filter expression or a geemap cell. Build the app only if a *shared* review tool is wanted — for one
analyst it adds a UI to maintain and no capability QGIS lacks. A whole-country raster overview is
the other option not taken: rasterizing `p_mean` at 30 m country-wide is 9.16 B cells (`05` "Foundations"), so it
would have to be coarsened to ~300 m, which erases the small objects that are precisely the ones in
doubt.
