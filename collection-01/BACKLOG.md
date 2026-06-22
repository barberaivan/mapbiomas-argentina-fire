# Backlog — collection-01

Pending work items not yet scheduled. Add new items at the top of each section.

---

## Data preparation

This is probably for collection 2.

- [ ] Sample training points for the 3 missing fires in BA (check `training_locations_status.txt`). The fires are commented in the script that creates the training_fires asset. They must be included in that asset and then, points must be sampled.
- [ ] Add a column to the `toma_de_muestras` Drive table to flag whether the exported GEE asset exists and is validated. A lot of `training_locations` files were not exported, and doing that takes time.

---

## Burn probability model (obs)

- [ ] Refine models. In Collection 1 the set was hardly decreased so that glmnet converged, but maybe that was not so necessary; maybe we can prune highly correlated variables by veg_fire class, not globally. Anyway, keeping a smaller set is good for reducing the prediction compute.


---

*Format: `- [ ]` open, `- [x]` done.*
