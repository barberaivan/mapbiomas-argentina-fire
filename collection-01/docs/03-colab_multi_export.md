# 03 — Distributed export via Colab (a how-to)

> **This is a how-to, not a step doc.** It is the operating procedure for running one step's
> exports across several people, written for whoever is coordinating them. The step itself — what
> `bpts` computes and why — is [`03-bpts.md`](03-bpts.md). Nothing here is part of the method.
>
> **Collection 1's `bpts` export is finished** (all years landed; steps 04–07 are built on them),
> so this is kept as the recipe for collection 2 rather than as a live campaign.

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
   (`C.REGION_RASTER`). Without it every run fails at runtime. *(Done for collection 1,
   2026-06-24.)*
4. **Grant each contributor's Google account writer access to BOTH output collections**, not one:
   `C.bpts_target_col(year)` routes **1999–2009 to `projects/mapbiomas-chaco/FIRE/bp_ts_metrics`**
   and every other year to `C.BP_TS_METRICS_COL`, because the `mapbiomas-argentina` asset home ran
   out of space (`03-bpts.md` "Inputs → Outputs"). A contributor who claims an early
   year and has writer access only to the main collection fails immediately. Reader on the inputs
   too.
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

- `F.bpts(year=Y)` submits all ~248 tiles for year `Y` and **skips tiles that are already
  exported OR already have a PENDING/RUNNING task** — safe to re-run to resume a
  partially-finished year, and safe to launch from two accounts: neither re-submits a tile the
  other is already running. The in-flight check is **cross-account and cross-project** — it runs
  `listOperations` (project-scoped, sees every user's tasks) over both `mapbiomas-argentina` and
  `mapbiomas-fire-485203` (`C.BPTS_TASK_PROJECTS`). `overwrite=True` forces resubmission, but
  GEE won't overwrite, so delete the asset first.
- `F.bpts_status(Y)` → classifies each tile as **done / in flight / to launch**, prints one line
  per year, and returns `{Y: {"done": [...], "in_flight": [...], "to_launch": [...]}}`. No GEE
  compute (`listAssets` + `listOperations`); anyone who can read the collection can run it.
- Caveat: `listOperations` needs read access to each project. Most contributors can read
  `mapbiomas-argentina` but **not** the Fire compute project — if a project can't be read it's
  skipped with a `UserWarning` naming which projects were evaluated. A tile running only under an
  unreadable project is invisible to the skip, so the **per-year Excel sign-out still governs**
  that residual case (don't sign out a year another account is working).

## CLI equivalent (for running locally, e.g. Positron)

```bash
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003            # export a year
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003 --status   # progress only
$PYTHON collection-01/workflow/03-bp_ts_metrics.py --year 2003 --project mapbiomas-argentina-...
```
