# 03 — Distributed export via Colab (admin notes)

How to run step-03 (`bpts`) exports across several people/accounts, since GEE only
runs ~3 export tasks at a time per account. Coordination is a shared **Excel**: one
row per year (1999–2025); each person claims a year, runs it, marks it done, claims
another. The notebook is `scripts/colab_bpts_export.ipynb`.

## Share link

The notebook lives in the repo, so contributors open it straight from GitHub (a fresh,
private copy per person — their edits don't touch the repo or each other):

```
https://colab.research.google.com/github/barberaivan/mapbiomas-argentina-fire/blob/main/collection-01/scripts/colab_bpts_export.ipynb
```

Put that URL in the Excel header. You share the *link*, not the file.

## One-time setup (admin = Iván), before sharing

1. **Push step-03 code + the notebook to `main`** — the notebook clones `main`.
2. **Repo readable** by contributors — make it public, or add them as collaborators
   (the `git clone` line needs read access).
3. **Export the buffered region raster** — `scripts/export_region_raster.py`
   (`C.REGION_RASTER`). Without it every run fails at runtime. ← current blocker.
4. **Grant each contributor's Google account writer access** to the output collection
   `projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/WORKFLOW-EXPORTS/bp_ts_metrics`
   (and reader on the inputs). Immediate permission errors mean this is missing.
5. **Excel**: rows for years 1999–2025 with columns name / status / (optional) project.

## What each contributor does

Open the link → claim a year → edit two cells (their `GEE_PROJECT`, their `YEAR`) →
**Runtime → Run all** → authenticate. After "N tasks submitted" they can close the tab
(work continues server-side). Later they re-run the status cell, and mark the Excel done
when it reads "✓ complete".

## Auth vs. compute project

- `ee.Authenticate()` = the person's **identity** — carries the 3-task limit and the
  write permission. This is what must have writer access to the output collection.
- `ee.Initialize(project=…)` = the **compute/quota bucket** (who pays the EECUs). NOT
  where assets land. Argentina people and Fire people just set a different project; the
  destination collection is the same for everyone. Override per-runner with the cell, or
  the `GEE_PROJECT` env var.

## Skip / resume / monitor (built into `bpts`)

- `F.bpts(year=Y)` submits all ~248 tiles for year `Y` and **skips tiles already
  exported** — safe to re-run to resume a partially-finished year (only missing/failed
  tiles are resubmitted). `overwrite=True` forces resubmission, but GEE won't overwrite,
  so delete the asset first.
- `F.bpts_status(Y)` → prints `done/248` and returns `{Y: [missing tile-ids]}`. No
  compute (just a `listAssets`); anyone who can read the collection can run it.
- Caveat: an asset only appears once its task **completes**, so a RUNNING tile isn't in
  the skip set — don't run the same year from two places at once (the per-year Excel
  sign-out prevents this).

## CLI equivalent (for running locally, e.g. Positron)

```bash
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003            # export a year
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003 --status   # progress only
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003 --project mapbiomas-argentina-...
```
