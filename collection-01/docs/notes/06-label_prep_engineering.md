> **Extracted from** `collection-01/docs/06-object_model.md` §1 "Label prep"
> @ `fc6ddef` (2026-09-18) — that section no longer carries the measurements.
> Lab notebook — the record of building the step, not documentation of it.

# 06 — Label prep: why the merge is shaped the way it is

The rules themselves (`terra::relate`, never `st_cast`) survive in the step doc's `Gotchas`; what
follows is the measurement behind them and the first full run's numbers.

*Why it is shaped this way.* A year is ~78 k objects / ~330 MB and only a handful are ever hit, so a
year is never read whole: labels are grouped into 1° blocks, each block read back through the
**GeoPackage R-tree** (`terra::vect(extent=)`), and the exact predicate run on that subset. Two
measured findings worth keeping:

- **`terra::relate(…, "intersects")`, not `sf::st_intersects`.** The 1-px dilation can weld a whole
  fire season into one object — `1999_24193` is **13 053 parts / 643 742 vertices**. `st_intersects`
  degrades pathologically there: **one point against that object costs ~55 s** (identical with
  `prepared = TRUE/FALSE` and with the arguments swapped). `terra::relate` answers the same block in
  1.6 s and returns **pair-for-pair identical** results — verified against sf on every FY1999 block.
  Whole merge: **27 s**.
- **Never `st_cast` the labels to POINT** to satisfy terra's one-geometry-type-per-SpatVector rule.
  A polygon label collapses to its first vertex and silently loses its objects (a 1999 polygon label
  went from 131 objects to 4). The script splits POINT vs POLYGON per block instead.

*Nothing is dropped; problems are flagged* — `n_objects` (0 = the label hit no object, >1 = a drawn
polygon), `oid_n_labels`, `oid_class_conflict` (object labelled both fire and non-fire). The model
step decides what to do with them. First full run (2026-07-27, 4643 labels, 7 collaborators, 21
fire-years): **6597 pairs over 5266 objects**, **234 labels (5 %) hit no object** (drawn where SNIC
kept no cluster — there is nothing to classify), **10 objects carry both classes**, and labels are
very unevenly spread (up to 40 on one object). One matched object (`2011_57456`, 1 px) has NA
`seed_mean`/`date_median` in step 05 itself — all-dieback objects have no seed/date stats by design
(`05` "Metrics"), not a join failure.
