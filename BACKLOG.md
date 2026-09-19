# Backlog

**Pending work items that are not yet scheduled.** Ordered by topic, not by priority — nothing here
is a commitment to do it, and nothing here is next. What is next is [`ROADMAP.md`](ROADMAP.md); an
item moves BACKLOG → ROADMAP when it gets scheduled, never the other way.

Add new items at the top of their section. This file spans the whole repo: tag a section or an item
with its collection when it is not collection-01 (everything currently listed is **collection-01**).

---

## Data preparation

This is probably for collection 2.

- [ ] **Reconcile CHACO `id_local` gaps in the `areas_regiones` sheet vs the remap.** The remap's
  `local_class` "ID=NN" ids are missing from the sheet for some Chaco classes, so the long-run
  area crosswalk drops/undercounts them: **grassland_chaco (veg_fire 13)** ids 42/43 → 0 km²,
  **shrubland-open_chaco (veg_fire 23)** ids 44/45 → undercounted. This biases the area weights in
  `notebooks/lr_term_pruning.qmd` (worked around by imputing the **median** area to zero-area
  classes) and `land_cover_remap.qmd`'s `area_frac`. Fix the sheet ids (or the remap
  `local_class`), then drop the median workaround.

---

## Burn probability model (obs)

- [ ] Refine models. In Collection 1 the set was hardly decreased so that glmnet converged, but maybe that was not so necessary; maybe we can prune highly correlated variables by veg_fire class, not globally. Anyway, keeping a smaller set is good for reducing the prediction compute.

---

## Patagonian forest late dieback as candidates for SNIC (step 04)

- [ ] For collection 2, correct the application of late dieback in Patagonian forests.
  Read docs/05, section **The Patagonia steppe dieback cut**. That should be applied before
  SNIC is run (step 4), not afterwards (in Col1 we discovered the problem too late).

---

## Reduce the statistics/docs/ file

These files should follow the ideas in collection-01/docs/TEMPLATE.md.
They were simply moved to statistics/docs from docs/, but not cleaned.

- [ ] `statistics/docs/statistics.md` (16.8 k, was `docs/09`) — **two sessions. FROZEN, with its
      move, until the launch lands (24 Sep 2026).**
- [ ] `statistics/docs/factsheet-sep2026-spec.md` (8.8 k, was `docs/10`) — **FROZEN until the
      launch lands.** Stays Spanish. Lightest pass of all: it is a spec, and it is already done
      its job; strip status chatter, leave the figure-by-figure content.

---

*Format: `- [ ]` open, `- [x]` done.*
