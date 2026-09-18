# 00 — Overview: the shape of the algorithm

This is the bridge between the concept and the code. It states the method in one page and maps
each workflow step onto it, so a step doc can open with "this is the spatial stage, second part"
and get on with its own business. For the full algorithm, see the ATBD; for any single step, see
its `NN-*.md`.

The algorithm detects burned area at the finest temporal and spatial resolution Landsat
allows: one 30 m pixel on one observation date — by exploiting the **spectral, temporal and
spatial** signature of fire, **in that order**. Each stage consumes what the previous one
produced and adds a kind of evidence the previous one could not see.

## 1. Spectral — is this observation burned?

The first stage asks a question about a single pixel on a single date: given what it looks like
now, how likely is it that it is burned? The evidence is spectral — the reflectance and the fire
indices of that observation — combined with **previous-year context**: the MapBiomas LULC class,
which selects *which* model judges the pixel, and the previous year's MapBiomas mosaic, which
supplies the pixel's own baseline. Both are read from `y−1` so that the fire being detected
cannot influence the context used to detect it.

The output is a **burn probability per observation**. Nothing is decided here.

## 2. Temporal — was this pixel burned this year, and when?

A burn probability on one date is not a detection: cloud shadow, wet soil and dark surfaces all
raise it. What distinguishes fire is what the probability does **through time** — it rises and
*stays* risen. So the second stage quantifies, per pixel and per calendar year, a **maintained
increase** in burn probability: a jump whose post-jump floor stays above the pre-jump baseline,
measured in consecutive valid observations rather than elapsed days, because the Landsat series
is irregular and its density varies by pixel and by year.

The output is a small set of **time-series metrics** per pixel per year, carrying both how
strongly the pixel behaves like a burn and **when** the jump happened — the burn date.

## 3. Spatial — is this pixel part of a fire?

Fires are patches, not independent pixels, and the third stage brings in that context twice.

**(1) Region growing.** Pixels whose time-series metrics make them *clearly* burned become
**seeds**. Pixels that are only *plausibly* burned become **candidates**, and a candidate is
admitted only by **contagion** — by being connected to a seed. A pixel whose own evidence is
weak is therefore accepted when it belongs to a patch whose evidence is strong, and rejected
when it stands alone. Seeds and candidates grow into **scar objects**.

**(2) Object-level classification.** The objects are vectorized and passed through a
probabilistic classifier built on **polygon-level metrics** — shape, size, vegetation
composition, the date and probability summaries of the pixels inside — which removes false
positives that no single pixel could have revealed. The output is a **probability of fire per
object**.

This stage works in a **fire year** (1 May → 30 April), not a calendar year, so that a fire
season is not split down the middle.

## The unifying principle: keep quantities, decide late

One idea runs through all three stages: **quantitative information is preserved for as long as
possible**, so every later step can weigh the earlier evidence instead of inheriting someone
else's verdict.

- The temporal stage analyses a **burn probability**, not a hard burned/unburned class.
- The region-growing algorithm judges pixels on **numeric metrics**, which is what makes the
  seed/candidate distinction expressible at all.
- The object classifier consumes **continuous metrics** and returns a **probability of fire**,
  which is used to filter — and is also published as quality information, so a user can apply a
  stricter or looser threshold than ours.

A pipeline that thresholded early would be simpler and would throw away exactly the evidence the
next stage needs.

## Which step is which

| Stage | Steps | Produces |
|---|---|---|
| **Spectral** | [01 training data](01-training_data.md); 02 [vegetation remap](02-vegetation_remap.md), [cleaning](02-data_cleaning.md), [model fitting](02-model_fitting.md) | burn probability per observation |
| **Temporal** | [03 burn-probability time-series metrics](03-bpts.md) | annual per-pixel metrics + burn date |
| **Spatial (1)** | [04 SNIC segmentation](04-snic.md) | scar objects, grown from seeds through candidates |
| **Spatial (2)** | [05 object metrics](05-object_metrics.md); [06 object model](06-object_model.md) | a fire probability and a fire call per object |
| *Publication* | [07 calendar-year products](07-vector_to_raster.md) | the layers MapBiomas ships |

**Steps 01–06 are the algorithm; step 07 is the delivery.** If the goal were burned-area data as
such, the chain could stop at 06 — the scored fire objects, each with its dates and its fire
probability, already are the map. Step 07 exists because MapBiomas Fuego publishes a *specific*
set of layers in a specific shape: the fire-year objects are re-partitioned into **calendar
years**, with year and month assigned **per pixel** from its burn date, and derived into the nine
subproducts the network defines. It is a change of packaging, not of evidence.

The network's shared post-processing is the spec those products conform to.
[`08-postprocessing.md`](08-postprocessing.md) is mostly **our reading of the reference
implementation** the other countries run, rather than a stage we execute: several of its stages
are already embedded upstream here, and Argentina's actual route is
[`07-vector_to_raster.md`](07-vector_to_raster.md), which wins wherever the two disagree.

**Statistics and validation are not stages of this chain.** They consume the finished map — see
[`../statistics/docs/statistics.md`](../statistics/docs/statistics.md) and
[`../validation/docs/design.md`](../validation/docs/design.md).
