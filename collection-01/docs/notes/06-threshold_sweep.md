> **Extracted from** `collection-01/docs/06-object_model.md` §6 "The classification threshold"
> @ `fc6ddef` (2026-09-18) — the doc keeps the deployed cuts and the caveat, not the sweep.
> Lab notebook — the record of building the step, not documentation of it.

# 06 — The threshold sweep, in full

## 6. The classification threshold — 0.5 is wrong, and the right cut rises with size

`scripts/objects_threshold.R` sweeps every cut on the **out-of-fold** probabilities (`oof_grid_5.csv`
— never in-sample, or the cut would be chosen against answers the model already saw) and reports
four criteria. **Youden's J (sens + spec − 1) is the headline** because it is the only one here that
does not move with prevalence, and our labelled set is not a random sample of objects. F1 and
accuracy are reported but drift with that sampling bias; `J_area` weights each object by `area_ha`
(the deliverable is an area product) but a handful of huge objects dominate its weights.

Deployed — `config/object_model_thresholds.csv` (tracked):

| stratum | n | prevalence | **cut** | sens | spec | J | J at 0.5 | bootstrap 5–95 % |
|---|---|---|---|---|---|---|---|---|
| < 1 ha | 114 | 0.254 | 0.250 | 0.897 | 0.929 | 0.826 | 0.643 | 0.211–0.380 |
| **1–50 ha** | 3217 | 0.468 | **0.202** | 0.837 | 0.763 | 0.600 | 0.492 | 0.183–0.283 |
| **50–300 ha** | 1192 | 0.576 | **0.436** | 0.854 | 0.791 | 0.645 | 0.631 | 0.326–0.565 |
| **≥ 300 ha** (pooled) | 732 | 0.773 | **0.690** | 0.857 | 0.849 | 0.706 | 0.662 | 0.601–0.792 |

**The cut rises with size — 0.20 → 0.44 → 0.69**, and for 1–50 vs 50–300 vs ≥300 the bootstrap
intervals are near-disjoint, so those differences are signal, not resampling noise: the model is far
more confident on big objects, and a single threshold would be simultaneously too high for small
objects and too low for large ones. The gain is concentrated where the error was — in 1–50 ha,
sensitivity 0.596 → 0.837.

**Splitting ≥300 ha in two buys nothing**, which is why it is swept but **deployed pooled**: the two
halves' J values sit inside each other's bootstrap intervals. The same evidence standard that
justified the other bands says these two are one band; deploying them separately would add a knob
that can only overfit. Hence `DEPLOY_BANDS` ≠ `SIZE_BANDS` in the script, and the config carries
four rows. `band_lower()` parses each band's lower bound out of its own label, so the config can
gain or lose bands without any code knowing their names.

`06-object_model.R predict` applies the file and logs the rule it used; with the file absent it
falls back to 0.5 and says so. The `< 1 ha` row is recorded for completeness but should not be
leaned on — 114 objects, 29 of them fire, and that whole stratum is 3.4 % of objects for 0.044 % of
area, so the **hard size cut, not a threshold, is the right tool there**.

**The threshold governs object COUNTS, not the area headline.** Against the labelled objects' own
burned area (2387.6 kha), `p > 0.5` gives 2327.7 kha over 2314 objects and the per-band cuts give
2270.6 kha over 2898 objects — ±5 % of area for +25 % of objects. Same story on the full FY2020: the
band cuts call **63 923** objects fire (4257 kha) where 0.5 called **50 519** (4189 kha) — **+13 404
objects for +68 kha** out of 4841 kha in the year. Area is dominated by large objects the model is
confident about, so lowering the cut is cheap in area and expensive only in small-object commission.

**The caveat that limits all of this.** Youden's J is prevalence-invariant *as a measure*, but the
threshold it selects is optimal for the prevalence of the set it was chosen on — and our labels are
not a random sample. In the 1–50 ha band labelled prevalence is 0.47, whereas most of the 1.4 M real
objects in that band are presumably noise. Applied to the whole population the band cuts call
**79 % of 1–50 ha objects fire**, which is implausible as a population rate — and even at 0.5 the
model calls a large majority of them fire, so this is the *label sampling*, not the cut. What would
settle it is a **randomly sampled** set of small-object labels — a collection task, not a modelling
one (BACKLOG). Until then, treat 0.20 as the **lower bound** of a defensible range for the 1–50 ha
cut.
