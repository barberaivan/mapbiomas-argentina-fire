# 04 — The SNIC-3D attempt: temporal firebreaks and backward gap-fill

> **Extracted from** `collection-01/docs/04-snic.md` §1 ("What we tried first, and why we
> dropped it (SNIC-3D) — [SHELVED]")
> @ `c949f6b` (2026-09-18) — that section no longer exists; the doc was restructured to
> `docs/TEMPLATE.md` and its headings are now named, not numbered.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcome: the non-calendar fire-year partitions time, so there is no
firebreak, no gap-fill and no cross-year de-duplication to manage. This is the route that was
tried before it.

---

## 1. What we tried first, and why we dropped it (SNIC-3D) — [SHELVED]

The **ideal** is a full 3D (space × space × time) clustering of the Landsat archive into fire
events — out of reach (custom clustering + the whole stack exported out of GEE).

The **first approximation** ran per-year 2D SNIC and faked the time axis with two devices:
a **temporal firebreak** (mask any pixel whose absolute burn date jumps > `D` from a neighbour, so
SNIC can't grow across two events that merely touch) and a **backward gap-fill** (import late
`y−1` pixels so a New-Year-straddling scar stays spatially whole). It **did not work well**:
step-03 per-pixel dates are too noisy, so the firebreak masked a lot of genuinely-burned area, and
without it the prev-year join leaked neighbouring fires. **Shelved, not abandoned** — worth
revisiting with more time.

- Where it lives: fuego `visualization-misc/explore_snic_firebreaks_IB-01`; original notes in
  `misc/SNIC 3D notes.odt`. The old `candseed {1,2,3,4}` encoding, the `D = f(n)` firebreak, the
  terra erode-then-restore, and the cross-year overlap-merge all belong to this shelved path.

The **current approach (below) replaces all of that** with a single time-partitioning trick: a
non-calendar fire-year. Because fire-years partition the calendar, each fire belongs to exactly one
of them — so there is **no cross-year duplication, no firebreak, and no gap-fill** to manage.
