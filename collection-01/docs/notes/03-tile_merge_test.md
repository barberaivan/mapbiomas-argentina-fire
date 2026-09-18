# 03 — The tile-merge export test (merging rejected)

> **Extracted from** `collection-01/docs/03-bpts.md` §10
> @ `76dca98` (2026-09-18) — that section no longer exists under that name.
> Lab notebook — the record of building the step, not documentation of it.

The doc keeps only the outcome: production exports one carta per task, never merged.

## 10. Tile-merge export test — DONE (2026-06-27): merging REJECTED

Question: does exporting several cartas as **one merged image** take similar **wall-clock** to a
single tile? If yes, merging tiles per task would amortise the ~17-min per-task fixed floor (§8)
and cut wall-clock. It never cuts compute or storage (the merged image still processes every
tile's area) — acknowledged going in; the only hoped-for payoff was paying the fixed floor once.

**Setup.** `scripts/test-03-tilemerge.py` submitted three 2015 exports with the **reduced P=50
model** (`models-store/pruning/deploy_K3_P50`) and the 16-band output, identical except for how
many cartas were merged into one image. The four tiles formed a 2×2 square:
`tl=SK-19-V-B  tr=SK-19-X-A  bl=SK-19-V-D  br=SK-19-X-C` (each carta ~14k km²).

**FINAL result (all SUCCEEDED, attempt 1):**

| asset | tiles | EECU-h | wall-min | wall/tile | EECU-h/tile | wall vs 1× |
|---|---|---|---|---|---|---|
| `bpts_2015_tilemerge_1` | 1 | 38.3 | 48.9 | 48.9 | 38.3 | 1.0× |
| `bpts_2015_tilemerge_2` | 2 | 145.8 | 146.7 | 73.4 | 72.9 | **3.0×** |
| `bpts_2015_tilemerge_4` | 4 | 251.7 | 250.7 | 62.7 | 62.9 | **5.1×** |

**Conclusion — DO NOT merge tiles; production exports one carta per task.** Both wall-clock and
EECU grow **super-linearly** with merged area (4× tiles → 5.1× wall, 6.6× EECU), so per-tile cost
*rises* when merging (~49→~63–73 wall-min/tile). The decision rule was "merge only if `tilemerge_4`
wall ≪ 4× `tilemerge_1`" (≪ 195.6 min); it came in at **250.7**, *above* 4×. Why the floor doesn't
help: the single tile is the only run where wall (48.9) > EECU-h (38.3) — that ~10-min gap *is* the
fixed floor (§8) — but once merged, wall ≈ EECU-h (the task becomes purely compute-bound) and the
floor is swamped by the extra area's compute. Test assets (`tilemerge_2`/`_4`) are deletable; the
single-tile `tilemerge_1` was renamed to its production name `bpts_2015_SK-19-V-B` (it is a valid
P50/16-band export, so renaming avoids re-running that tile).

> The `tile_geom=` override added to `burn_prob_collection`/`bpts_image` for this test was
> **reverted** after the result — there is no production use for it. Single-tile geometry only.

**Downstream design notes reached this session (step 04 SNIC / regions).** Define fire-regions as
**unions of cartas with boundaries in low-fire zones**; build the SNIC input as a mosaic of *only*
those cartas. GEE's neighborhood ops fetch margins **only from the input image's definition** — a
region-only input has masked edges and imports nothing extra, so **no edge buffer is needed**
(boundaries avoid fires) and compute is minimal. The residual concern is GEE-SNIC's **internal
~256-px tile seams** (independent of region boundaries) — verify on one test segmentation before
committing the step-04 tiling. Step-03 export tiling and downstream regions are decoupled for
correctness but NOT cost: cheapest downstream is region = exact union of step-03 tiles, no buffer,
so align the export tiling to the hand-drawn fire-regions where export limits allow.
