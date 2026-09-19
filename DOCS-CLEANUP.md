# Documentation cleanup — multi-session plan

Working plan for reorganising the repo's documentation. **Any session can pick this up: read
this file first, do exactly one item, tick it, commit.** Delete this file when the last box is
ticked; git history is the archive.

Started 2026-09-18. Language: English (the docs are English; `10-factsheet_design.md` is
Spanish on purpose and stays Spanish — see Phase 2).

---

## 1. Why, and for whom

The repo cannot be strictly reproduced (several input assets are not public). The goal is that
**a MapBiomas team in another country can understand the method and re-apply it**, and that
collection 2 does not re-make collection 1's mistakes.

Those are **two readers with opposite needs**, and today one file tries to rank both:

| reader | wants | today |
|---|---|---|
| another country / a reviewer | concept → design → commands | buried |
| collection 2 / Iván in a year | benchmarks, abandoned roads, post-mortems | dominant |

The split below is not about length. It is about which reader each file serves.

### The measured starting point (2026-09-18)

- 14 step docs ≈ **73 k words**, plus a 6.0 k-word `collection-01/README.md` and a 5.2 k-word
  `CLAUDE.md`. ~84 k words total.
- Four docs are **64 %** of it: `09` (16.8 k), `07` (13.3 k), `10` (8.8 k), `06` (8.0 k).
- **Not code bloat** — code blocks are 0–7 % of every doc except `11-validation` (21 %, GEE JS
  appendices). The "docs carry almost no code" rule is already being met.
- **History bloat**: dated/status/post-mortem markers — 55 in `09`, 37 in `07`, 21 in `03`.
  Section titles like *"Roads taken and abandoned"*, *"STATUS / HANDOFF (in progress)"*,
  *"DONE (2026-06-27): merging REJECTED"*, *"The bug that killed the run (fixed)"*, four
  separate *"CORRECTION —"* headers in `08`.
- **Append-only signature**: in `07`, §12.7–12.8 sit *after* §13.7; `11-validation.md` is
  titled "Step 10" and code still cites it as `docs/10`.
- **The early docs are already the template**: `01-training_data.md` (487 words) and the three
  `02-*.md` follow `Inputs / Step / Outputs / Production files / Related notebooks`. The
  template existed and was abandoned at step 03, exactly when the work got hard.

### Diátaxis, and where this repo sits

Four documentation types, each with a different shape: **tutorial** (guided first run),
**how-to** (to do X, run this), **reference** (the facts), **explanation** (why it is like
this). A file that mixes them serves none of its readers, because a reader always arrives in
one of those four moods.

- **Tutorial** — one, and it is good: the root README's three-step setup. Nothing else needs to be one.
- **How-to** — lives in **four** places for the same command: `collection-01/README.md`, the
  "Run" / "Order of operations" sections in docs, the script docstrings, and the `run_*.sh`
  launchers. It drifts because nothing owns it.
- **Reference** — half in `config/` + `utils/constants.py` (right), half as prose inside the big
  docs (the nine encodings, the 20 predictors, the ten properties, the 32 inspection fields).
- **Explanation** — the ATBD, **which only exists for collection 0**. This is the real hole: with
  no col-1 ATBD, every step doc absorbed the explanation load.
- **A fifth thing Diátaxis has no box for** — the lab notebook. Valuable, but it is the record of
  *building* the pipeline, not documentation *of* it. It goes to `docs/notes/`.

---

## 2. The target shape

```
README.md                      root: what this is, setup tutorial, links.  No pipeline commands.
CLAUDE.md                      operating rules + a ONE-LINE-PER-DOC index.  Target ≤ 1.5 k words.
ROADMAP.md                     unchanged in role: what to do next.
collection-01/
  README.md                    orientation + the pipeline map.  NO commands.  Target ≤ 1.2 k words.
  docs/                        THE MAP-MAKING CHAIN, AND NOTHING ELSE
    00-overview.md             NEW — the bridge: spectral → temporal → spatial, and which step
                               is which.  ~800 words.  Later becomes the ATBD skeleton.
    TEMPLATE.md                NEW — the fixed skeleton + quotas every step doc obeys.
    01..08-<step>.md           one per step.  Target 800–2000 words, more if needed.
    external/                  NEW — readings of code we do not own, commit-pinned (§3).
    notes/                     NEW — the lab notebook: benchmarks, abandoned roads, post-mortems,
                               status snapshots.  No length limit.  Provenance header required.
  validation/
    README.md                  signpost
    docs/design.md             ← today's docs/11-validation.md
  statistics/
    README.md                  signpost
    docs/statistics.md         ← today's docs/09-statistics.md
    docs/factsheet-sep2026-spec.md   ← today's docs/10-factsheet_design.md (Spanish, per-launch)
  workflow/ scripts/ models/ samples/ config/
                               code.  A SIGNPOST README where the directory is not
                               self-evident (see below).
```

### What `docs/` holds — the map-making chain, and only that

**Steps 01–08 produce the map. Statistics (09) and validation (11) consume it.** They take the
finished product as *input*; they are not stages of the chain. They were numbered sequentially
because that is the order they were built in — **the numbering encodes chronology, not
structure** — and they are *episodic*: a collection may ship without validating, and statistics
are produced only for the products a given launch actually shows.

This is the standard Earth-observation documentation family, and those documents are separate
deliverables on purpose:

| document | covers | cadence | here |
|---|---|---|---|
| **ATBD** | the algorithm that makes the product | per collection | `docs/` (00–08) |
| **Validation / accuracy report** | how good it is | when someone validates | `validation/docs/` |
| **Product user guide** | what the layers mean | per release | not written yet |
| **Release notes / factsheet** | what changed, what to say | per launch | `statistics/docs/` |

Validation is never a chapter of the ATBD — not in ESA CCI, not in Copernicus, not in MapBiomas
itself. So the episodic activities keep their documentation **colocated with their code**:

- an activity that does not run in a collection is simply **absent**, leaving no hole in a
  numbered sequence and no stale doc implying a step that never happened;
- `docs/` becomes legible in one glance — `00` plus eight steps, the method and nothing else,
  which is exactly the ATBD's scope and exactly what another country needs;
- working inside `statistics/`, everything is inside `statistics/`.

The cost is one extra lookup, paid off by the one-line index CLAUDE.md gets in Phase 4.

**Within `docs/`, do not mirror the directory tree.** The eight steps are indexed by *method*,
not by which folder the `.py` files sit in.

A **directory README is a different object**: a *signpost*, ~15 lines, answering only *what am I
looking at* and *which doc explains it*. No explanation, no design, no commands beyond a
one-liner. By that rule:

| directory | README? |
|---|---|
| `scripts/` (66 files, none today) | **yes, needed** — the one real gap; group the files by purpose |
| `validation/`, `statistics/` | 5 lines: what this is → its own `docs/` |
| `workflow/` | probably not — numbered files + the `docs/` index already orient |
| `models/`, `samples/` | already have one; check they are signposts and not encyclopedias |

### The rules that decide where a thing goes

1. **One home per fact.** Each of these has exactly one owner; everything else links to it.
   - *How to invoke one script* → **the script's own docstring / `--help`**. It cannot go stale.
   - *The order of the steps and their dependencies* → **the step doc's `Run` section**
     (prose + commands, no *why*). Order is not expressible inside any one script. This plan
     first called it `Pipeline`; `TEMPLATE.md`, written afterwards in Phase 1, settled on **`Run`**
     and its rule 8 gives it exactly this job. One name, and it is `Run`.
   - *Parameters, paths, thresholds, asset ids* → **`config/` and `utils/constants.py`**. Docs
     link, never restate.
   - *Why it is like this* → **the step doc's `Key decisions`** (≤ 5 items), and in the end the ATBD.
   - *What we tried, what broke, what we measured on a date* → **`docs/notes/`**.
2. **Cite a section by name, never by number** — `docs/05 "Metrics"`, not `docs/05 §2.4`. A
   heading number is a *position*: insert or drop anything above it and every citation to it now
   points somewhere else, silently. This is the same failure as the `docs/NN` rot in the Phase 0
   box, one level down, and it was **measured in the step-05 pass** — `docs/05 §3` meant two
   different sections depending on which file was citing it, and `§7b`/`§7c` were cited seven
   times having never existed. Applies to code comments and docstrings as much as to docs.
   `notes/` entries are cited by filename; a `notes/` provenance header is the one exception,
   because it is a past-tense claim pinned to a commit.
   **This is not a repo-wide sweep to run now.** Hundreds of `docs/06 §x`, `docs/07 §x` and
   `docs/08 §x` citations are still live and still correct, because those docs have not had their
   Phase 2 pass. **Each pass converts the citations pointing at the doc it rewrites** — that is
   when the numbers actually move, and it is already part of the per-doc protocol in §4.
3. **The docstring carries usage, not explanation.** The workflow docstrings today hold measured
   results and `WHY …` sections — that is a fourth home for explanation. Strip to: what it does
   (3 lines), usage, pointer to `docs/NN "<section name>"`.
4. **A step doc has no long code chunks.** Named packages, functions, GEE methods — yes; blocks — no.
5. **Every step doc is self-sufficient for its first paragraph.** A reader gets what the step is
   for without opening the ATBD.
6. **Nothing is deleted, it is moved.** History goes to `docs/notes/` with a provenance header.

### `docs/notes/` conventions

One file per topic, free-form, **no length limit**, named `NN-<topic>.md` keeping the step
number it came from. Every file opens with:

```markdown
> **Extracted from** `collection-01/docs/07-vector_to_raster.md` §13.6, on 2026-09-18.
> Lab notebook — the record of building the step, not documentation of it.
```

When a session is told to strip history out of a doc, it **moves the text verbatim** into
`docs/notes/` with that header. Tidying `notes/` (merging, pruning, deciding what is an ADR) is
a **separate sub-task, deliberately deferred** — see Phase 6.

### The ATBD path (why `00-overview.md` exists)

The plan is: docs stay explanatory while the work is live → the ATBD is written from them → the
explanation moves to the ATBD and the docs shrink to design + how-to.

The join is not clean, because **the ATBD is conceptual (three sections: spectral, temporal,
spatial) and the steps are computational** — temporal is roughly one step, spatial is many.
`00-overview.md` is the bridge: it states the three-part method and maps each workflow step onto
it, so a step doc's opening paragraph can say "this is the spatial part, stage 2" and stop.
Write it once, early; it is also the ATBD's skeleton.

### There are TWO reductions, not one — and that is what un-tangles the ATBD

The ordering feels circular only if the docs are shrunk once. They are shrunk twice:

| | when | what leaves | what remains |
|---|---|---|---|
| **reduction 1** | Phase 2, now | **history only** — benchmarks, abandoned roads, post-mortems, status snapshots → `docs/notes/` | the explanation, compressed into `Key decisions` (≤5 items) |
| **reduction 2** | Phase 6, after the ATBD exists | the explanation → the ATBD | pointers |

Three consequences, and they are the whole answer to "where do I start":

1. **A Phase 2 session never has to ask "is this ATBD material or notes?"** — a hard question
   that would stall every doc pass. It asks only *does this stay in the doc, yes or no*, and
   everything that leaves goes to `notes/`.
2. **The docs stay complete and readable throughout.** The ATBD is months away; hollowing the
   docs out now would leave the repo worse for the entire interval.
3. **There is NO `ATBD_draft.md`.** The `Key decisions` sections, spread across the step docs,
   *are* the draft. A parallel draft file would be a fifth home for the same content, needing a
   sync on every doc pass — and accumulating it step-by-step would only reproduce the docs
   concatenated. The ATBD is not a concatenation of step explanations; it is a
   **re-organisation along the conceptual axis**, so its structure has to be decided first, in
   one deliberate pass, with the whole pile visible.

When that pass comes (Phase 6), **start from collection 0's ATBD as a structural template** —
it supplies the skeleton, which is the scarce thing; the content is a different method and comes
from `00-overview.md` + the `Key decisions`. That is a Phase 6 decision. Do not make it now.

---

## 3. Genre decisions (confirm before Phase 2)

Not every file in `docs/` is a step doc. Proposed:

| file | is it a step doc? | proposal |
|---|---|---|
| `01`, `02-*` (×3) | yes | already near-template — they become the model |
| `03-bpts` | yes, but it was **two stages in one file** | **split** — see below |
| `03-colab_multi_export` | **no** — pure how-to, admin | keep, but mark as a how-to, not a step |
| `04-snic`, `05-object_metrics`, `06-object_model`, `07-vector_to_raster` | yes | |
| `08-postprocessing` | **half** — §6 is our step 08; §§1–5 are a reading of the network's repo | **split**, see below |
| `09-statistics` | **no** — episodic, consumes the map | → `statistics/docs/statistics.md`, still to `TEMPLATE.md` |
| `10-factsheet_design` | **no** — a per-launch deliverable spec, in Spanish | → `statistics/docs/factsheet-sep2026-spec.md`; stays Spanish |
| `11-validation` | **no** — episodic, consumes the map | → `validation/docs/design.md`; drops the number (it was "Step 10" in its own title and is cited as `docs/10` in code — both gone, 2026-09-18). ⚠️ An earlier version of this plan said it was *not* written by Iván; `git log --follow` says otherwise — **the design is his, the implementation and the status section are Ramón Peña Agrest's** |

`10-factsheet_design.md` is a **spec** — a specification of what to build — and it is tied to
*one* launch, so the launch goes in the filename. It is **not** `notes/` material: `notes/` is
the record of building the pipeline, whereas the spec stays the reference for what each figure
means. Putting the date in the name makes its decay explicit and lets December and collection 2
add their own beside it instead of overwriting it.

### A fourth genre: *our reading of someone else's undocumented code*

`08-postprocessing.md` exists because the MapBiomas Fuego network documents its shared
post-processing as a **Google Slides deck plus the code itself**. In principle a link would do;
in practice it would not, and writing the reading was the right call. But it is a **derivative
document about an external dependency**, and that has consequences a step doc does not have:

- it goes **stale silently** when the network changes their repo, and nothing here will notice;
- its four `CORRECTION —` sections are not corrections to *our* design, they are us discovering
  we had misread theirs — which is history, and belongs in `notes/`;
- it should never be the home of anything about *our* pipeline.

So: **split `08-postprocessing.md` in two.**

- `docs/08-postprocessing.md` — **our** step 08 (today's §6, "Argentina's route"), to `TEMPLATE.md`.
- `docs/external/mapbiomas-fuego-reference.md` — the reading (today's §§1–5). Header box states:
  *this describes code we do not own; read against `mapbiomas-fire` @ `<commit>` on `<date>`;
  where it disagrees with `docs/07`, `docs/07` wins.* **Pin the commit** — an un-pinned reading
  of a moving target is worse than no reading.

The same rule applies to any future doc of this kind (the network's statistics toolkit in
`2-Statistics/toolkit/v03/` is the next candidate, currently described inside `docs/09`).

### A fifth genre problem: one file, two stages of the method

`03-bpts.md` documented **two conceptual stages**: the per-observation burn probability (the
spectral stage's product) and the reduction of that series to annual metrics (the temporal
stage). They share one file because they must share one GEE graph — the intermediate probability
collection is an order of magnitude larger than the summary it produces, so it is never
materialized. **A computational necessity had become a documentation structure.**

The tell was in `00-overview.md`: its Spectral row already promised "burn probability per
observation" as that stage's product, and listed four `02-*` docs, **none of which described how
that quantity is produced**. The doc was missing, and step 03 was carrying it.

So: **split `03-bpts.md` in two** (Iván, 2026-09-18).

- `docs/02-burn_probability.md` — the fitted model in GEE: which model judges the pixel, the
  coefficient-remap that turns 23 per-class models into one branchless expression, the raw-scale
  dot product, and why nothing is materialized.
- `docs/03-bpts.md` — the temporal stage: the series, the padding, the arrays, the metrics, the
  export and the launcher.

**The join lives in 03, not in 02**, and the reason generalises: the optimisation that fuses them
— precomputing the previous-year half of the linear predictor once per tile-year instead of ~150
times — exploits an invariance ("constant within a focal year") that is *a statement about the
series*. It is not even expressible until a focal year has been defined, so it is temporal-stage
machinery that happens to reach into the model's terms. `02-burn_probability.md` describes the
model for one observation and points at `03-bpts.md` "What is precomputed per year" for what
actually runs.

**The general rule this gives Phase 2**: when a stage named in `00-overview.md` has no doc of its
own, find the step doc that is carrying it. A doc that documents two stages will read as one long
"how it works" and nothing in a per-doc pass will flag it, because nothing in it is history.

---

## 4. Session protocol

**One item per session. Start each session fresh.**

- **`/clear`, not `/compact`.** The whole failure being fixed is that these docs were written
  with the building session in context, where everything looked equally important. Compacting
  preserves exactly that anchoring in lossy form. A clean session reads the `.md` as a stranger
  would, which is the only way to cut it. This file is the handoff, not a compacted summary.
- **Context size is not the constraint; the stranger's eye is.** Even `09` (17 k words ≈ 23 k
  tokens) fits comfortably. Do one doc anyway.
- **Order within a doc**: read it whole → move history to `notes/` → rewrite what stays to
  `TEMPLATE.md` → check every inbound link still resolves (`grep -rn "docs/NN"`).
- **For `07` and `09` only**: split into two sessions — extraction first, rewrite second.
- **Commit per doc**, so any pass is individually revertable.
- **An editor pass is worth it on the big ones**: a second fresh session that sees *only* the
  rewritten `.md`, instructed to cut 20–30 % and make every paragraph open with its point.
- **Do not edit any BACKLOG file without explicit permission.** While working, Claude finds
  lots of open questions that are settled or are unimportant, she just can't know. Ask Iván
  when you want to write there.
---

## 5. The ordered checklist

### Phase 0 — scaffolding ✅ DONE 2026-09-18

- [x] Created `collection-01/docs/notes/` + `docs/external/`, each with a `README.md` stating
      its conventions (§2 and §3 of this file).
- [x] **The moves** (`git mv`, content untouched — the rewrites happen in Phase 2):
      `docs/09-statistics.md` → `statistics/docs/statistics.md`;
      `docs/10-factsheet_design.md` → `statistics/docs/factsheet-sep2026-spec.md`;
      `docs/11-validation.md` → `validation/docs/design.md`.
      `docs/` is now `00`–`08` only (no `00-overview.md` yet — Phase 1).
- [x] **~120 inbound citations rewritten**, and they were *not* mechanical — see the box below.
      Sibling references inside `statistics/docs/` were shortened to bare filenames.
- [x] `ROADMAP.md`'s `## Next` now points here; the Spanish braindump is kept below it, marked
      as source material rather than a task list.



### Phase 1 — the template and the bridge (with Iván, hands-on)

- [x] **Iván reviewed by hand**: `01-training_data.md`, `02-vegetation_remap.md`,
      `02-data_cleaning.md`, `02-model_fitting.md`. Three amendments to this plan came out of it
      — see the box below.
- [x] Wrote `docs/TEMPLATE.md`: a **guide, not a form**. Four always-present sections
      (orientation, Inputs → Outputs, How it works, Files/Related) plus **Foundations**, `Run`,
      `Key decisions` and `Gotchas` offered when the step has one. 800–2000 words
      (widened from 1500 by Iván on 2026-09-18, after three passes landed over it).
      `01-training_data.md` is named in it as the model doc.
- [x] The four docs restructured to it, and `02-diagnostic_plots.md` split out of
      `02-model_fitting.md` (a diagnostic tool, not a step). History →
      `notes/02-lr_term_reduction.md`.

- [x] `docs/00-overview.md` written (819 words) from Iván's framing: the spectral → temporal →
      spatial order, the two parts of the spatial stage (region growing, then object
      classification), **the unifying principle** — quantities are preserved as long as possible
      so every later stage weighs the evidence instead of inheriting a verdict — and the
      step→stage table. Steps 07–08 are marked as publication, not a fourth analysis.


### Phase 2 — per-doc pass (one doc per session)

Each pass = history → `notes/`, then rewrite to `TEMPLATE.md`, then fix inbound links.

> **`docs/notes/` is written during Phase 2, and reconciled only in Phase 6.** A pass moves text
> **verbatim** into a note, pins the source commit in the provenance header, and moves on — it
> does not rewrite the note, merge it with a neighbour, or decide whether it is an ADR. Keeping
> the extraction cheap is what makes a per-doc pass finishable in one session; all the judgement
> is deliberately pooled into one later pass, with the whole folder visible. The same shape as
> the two reductions in §2.
>
> It follows that **a note is expected to be stale on arrival** in one specific way: its header
> names a section that the same pass just deleted. That is correct and is not repaired — see
> `notes/README.md` and the Phase 6 item.

- [x] `05-object_metrics.md` (4.4 k → 1.75 k) — the calibration pass. §6 (status), §7 (the
      FY2000 walls) and §8 (roads abandoned) → `notes/05-whole_country_redesign.md`; §9 (memory
      profile, the merge bug, the trims) + §4.1's measured run → `notes/05-memory_profile.md`.
      2.4 k words moved verbatim. **Two things for Iván to sign off — see the box below.**



- [x] `03-bpts.md` (5,766 → 2,746 words) — §6 (validation), §7's two answered bullets →
      `notes/03-validation_2015.md`; §7's cost bullets + §8 + §8.1 + §9 (the pruning handoff and
      the EECU A/B/C test) → `notes/03-performance_profile.md`; §10 →
      `notes/03-tile_merge_test.md`; the two `timediff_*` drop boxes + §5 gotcha 4 →
      `notes/03-dropped_timediff_bands.md`. 2.3 k words moved verbatim. §11 was **not** history —
      it is what production runs, so it became one `Key decisions` bullet. 19 inbound `§N`
      citations repointed across 11 files. **A live rule was missing from the doc entirely — see
      the box.**
- [x] **`03-bpts.md` split into two docs** (same day, Iván's call): `02-burn_probability.md`
      (1.3 k words, new) takes the spectral stage — the deployed model in GEE; `03-bpts.md`
      (2.7 k) keeps the temporal stage and **the join**. Rationale and the general rule: §3 "A
      fifth genre problem". `00-overview.md`'s Spectral row and CLAUDE.md's index updated; 7 of
      the citations repointed hours earlier moved again, to the new doc.



- [x] `04-snic.md` (2,694 → 2,115 words) — §1 (the shelved SNIC-3D) →
      `notes/04-snic3d_firebreaks.md`; §5c (the FY2000 vectorize benchmark) →
      `notes/04-vectorization_benchmark.md`, both verbatim. §7 "Open questions" dissolved: three
      of its five items had been **answered by the code** since (see the box below). ~35 inbound
      citations repointed from `§N` to named sections across 13 files.


- [x] `06-object_model.md` (7,958 → **4,592**) — **split into three docs on your suggestion**
      (mid-session: *"perhaps doc 06 can be separated in data collection and modelling"*):
      `06-object_labels.md` (1,010 — collection in GEE, the join, the fitting set),
      `06-object_model.md` (4,592 — the classifier and the upload) and `06-object_inspection.md`
      (995 — the QGIS review layer). Seven `notes/` entries extracted verbatim, 4.6 k words. ~45
      inbound citations repointed from `§N` to named sections across 20 files; two dead *named*
      citations found; CLAUDE.md's one step-06 row replaced by three. **Two live defects the doc
      had never recorded — see the box.**


- [x] `validation/docs/design.md` (5,285 → 4,849 → **5,021 after Iván's review**, and **the premise
      of this item was wrong** — see the box). Title de-numbered, all 16 headings de-numbered and
      ~35 internal + ~20 inbound `§N` citations converted to names across 8 files. A **status box**
      was added; the design prose itself was **not cut**. A correctness finding is recorded in the
      doc and below. **Iván's review then changed what `notes/` holds and why the doc grew back**:
      the three verbatim entries are gone, replaced by one brief
      [`notes/abandoned-paths.md`](collection-01/validation/docs/notes/abandoned-paths.md)
      (1,523 → 424 words), and everything the code actually does was folded **into** the design —
      see the second box.

- [x] `08-postprocessing.md` (5,284 → **1,219**) — **split, and the step doc did not survive as
      one.** The plan asked the question and the answer is no: §6 was almost entirely a second
      telling of `docs/07`. Three ways: §§1–5 → `docs/external/mapbiomas-fuego-reference.md`
      (2,433 words, commit-pinned); the three `CORRECTION —` sections, the July delivery checklist
      and the struck-through decisions → `notes/08-corrections_and_delivery.md` (1,999, verbatim);
      what is left is a **1.2 k signpost** that carries the only things neither of the others has
      — the *stage-by-stage comparison* of what Argentina already satisfies upstream, what dating
      per pixel buys and costs, and the four live open decisions. ~25 citations repointed across
      7 files; `00-overview.md`'s closing paragraph rewritten as the plan asked; CLAUDE.md's one
      row replaced by two.


- [x] `03-colab_multi_export.md` (568 → 662) — marked as a **how-to, not a step doc**, in a header
      box, and **it grew, because two facts in it were false.** See the box.

- [x] `07-vector_to_raster.md` (13,298 → **11,014**) — **two passes, as the plan asked**
      (extraction `5653986`, rewrite in the commit below). 4.0 k words verbatim to three `notes/`
      entries; every heading de-numbered; §12.7 moved back where it belongs and §12.8 dropped into
      the verification note, which is the re-order the plan asked for; **94 inbound `§N` citations**
      repointed across 20 files — the most of any pass. Then a **third pass split it in two**
      (`e9e610e`, Iván's call): `07-vector_to_raster.md` (6.6 k) keeps how the burned **pixels** are
      made — the exclusion ruleset, the `_v2` re-export, the calendar partition, the grid, dieback,
      07a–07c — and **`07-published_products.md`** (4.9 k) takes what is **packaged** from them:
      07d's nine subproducts and 07e's polygon layer. `docs/07` bare still means the first.

### Phase 3 — how-to consolidation and the signposts (rule 1)

- [x] Workflow docstrings (`b28561a`): **6,686 → 2,368 words** across the eleven scripts. Every
      deletion was checked against the doc that inherits it first; nothing went to `notes/` because
      nothing in them was history that the Phase 2 passes had not already extracted. **Three
      defects surfaced in that checking**: `07-month_of_burn.py` advertised `--agri-max`, a flag
      that does not exist (the real ones are `--t-agri` / `--t-grass`);
      `07-burned_area_polygons.py` quoted the `_v1` figures and the `_v1` asset as current, which
      the doc already flags as pre-rule; and `01-training_data_export.py` pointed at
      `TASK-DATA-EXPORT.md`, which is in no commit. **17 `§N` citations converted to names** in six
      files — `04 §5b`, `04 §4.3`, `§13.3`, `§13.7`, `§12.1`, `§3.7`, `§1.1`, and two to
      `statistics.md §4.4`, a subsection that never existed. The three surviving numbered citations
      point at `statistics.md`, which has not had its pass, and are correct today.
- [x] Each step doc gets its `Run` section (the sequence, in commands, no why) — the plan's
      `Pipeline`, renamed to match `TEMPLATE.md` (§2 rule 1). **Mostly already done by the Phase 2
      passes**, which is what a rule landing before the work it governs looks like. Two real gaps
      closed: `07-published_products.md`'s command block had no heading at all (it sat under the
      H1, uncitable by name), and `02-burn_probability.md` had no `Run` — its answer is *there is
      nothing to run for this stage alone*, plus the one-time `export_region_raster.py`
      prerequisite and the two checks. `08-postprocessing.md` correctly has none: it owns no
      script and says so.
- [x] `scripts/run_*.sh` launchers: one line each in the relevant step doc's `Run`, nothing more.
      Verified — all five (`run_05_years`, `run_06_predict`, `run_06_inspect`, `run_07_scars`,
      `run_07_upload_zips`) plus `mem_monitor.sh` were already there.
- [x] **`scripts/README.md`** — NEW. 57 files (not 66 — the count included `__pycache__` and the
      three data subdirectories), grouped by the step they serve, each group pointing at its doc.
      Opens by naming the **four kinds of thing** in there, which is what a stranger actually needs
      before the table: launchers, gates, watchers/drivers, and trials/reports. Every file is in
      exactly one row — checked mechanically — and every link resolves. One finding recorded in it:
      **`export_region_raster_v2.py` is on no path**, because `C.REGION_RASTER` still points at the
      v1 output, so the faster rebuild's asset was never adopted. Keep-or-delete is Iván's call.
- [x] `validation/README.md`, `statistics/README.md` — NEW, ~15 lines each rather than 5: what it
      is, **why it is episodic and therefore not in `docs/`**, the one framing fact a reader needs
      before opening anything (validation is all fire-year; statistics has three sources), and the
      pointers. `validation/`'s carries the `_v1`-strata-vs-`_v2`-product warning at the door,
      because that is the thing you must not skip past.
- [x] `models/README.md`, `samples/README.md` — checked, and **the premise needed adjusting**.
      `models/README.md` is not a directory signpost that grew too long; it is the **reference for
      the model artifacts** — folder layout, file schema, and the raw-scale prediction recipe that
      nothing else owns. Rule 1 says that is exactly right, so it keeps its length. What was wrong
      was its two tail sections, which duplicated `docs/02-model_fitting.md`'s explanation, and
      one of them carried a **factual error**: it gave the elastic-net grid as
      `alpha ∈ {0, .25, .5, .75, 1}` when the code fits `{0.25, 0.5, 0.75}` and drops ridge and
      lasso on purpose — the kind of wrong that reproduces a different model. Its
      "full rationale in CLAUDE.md" pointer was also dead; the rationale is in `docs/02`. Both
      sections are now one, keeping only what you need to *read* a file. `samples/README.md` (215
      words) was already a good signpost and only gained a pointer to `docs/01`.
- [x] **`collection-01/README.md` → map + links, NO commands**: 6,166 → **1,423 words**, all 20
      bash blocks gone. Every command it held now has exactly one home — a step doc's `Run`, or
      `scripts/README.md` — which is what made deleting them safe rather than lossy. The
      annotated per-file trees for `scripts/` and `statistics/` collapsed into one row each, now
      that those directories have their own README. What stays is what nothing else owns: the
      directory map, the `data/` layout, the pipeline table, the notebooks table and the per-step
      status. **1,423 is 19 % over the 1.2 k target** and stays that way: the remainder is the
      status table and the pipeline map, and `TEMPLATE.md`'s rule is that a target never overrides
      content. The four factsheet notebook rows, each a 500-word Spanish essay duplicating
      `statistics.md` §5.0, are one line each pointing there. **Two notebooks were missing from the
      old table** (`snic_candidates_seeds_definition.qmd`, `validation_year_selection.qmd`) and are
      now listed. Every link checked.
- [x] Root `README.md` — checked: 573 words, still a clean setup tutorial, and it does **not**
      duplicate the pipeline. Two pointers repaired, because this pass falsified them: it sent the
      reader to `collection-01/README.md` for "how to run the pipeline", which no longer holds
      commands, and to both collection READMEs for "reproduction instructions". It now opens on
      `docs/00-overview.md`. The same two stale claims in **CLAUDE.md** were fixed for the same
      reason — not a Phase 4 land-grab, just not leaving a claim this pass made false.

### Phase 4 — the index

> **Depends on Phase 3.** `CLAUDE.md` is an index of the READMEs and docs; shortening it before
> they are stable means writing it twice. It is last for that reason, not by accident.

- [x] `CLAUDE.md` → one line per doc: **6,213 → 1,584 words**, and the `docs/09` row that was
      ~900 words inside one table cell is now one line. Two tables (the map-making chain, then the
      episodic activities), a signposts paragraph for the READMEs, and a five-line "where a fact
      lives" restatement of §2 rule 1 — the rest is operating rules only. **What left, and where it
      already lived**: the whole "pipeline at a glance" list (`collection-01/README.md`'s pipeline
      table), the collection-0-vs-1 technology table (same file, "What changed from collection 0"),
      and every per-doc précis (the doc itself). Kept, because nothing else owns them: the two
      accounts and the explicit-credentials pattern, the shared-project rule, and the step-specific
      traps that have each been made twice — the year-leak predictor, `crsTransform` vs `scale=30`,
      and the two LULC constants. **1,584 is 5.6 % over target** and stays: the remainder is the
      index itself. Verified mechanically — every `.md` under `docs/`, `docs/external/`,
      `statistics/docs/` and `validation/docs/` appears in it, every link resolves, every backticked
      path exists. One defect found on the way: `07-burned_area_polygons.py`'s docstring still said
      "CLAUDE.md's answer is to `cp` the account into place", which CLAUDE.md has contradicted since
      the explicit-credentials rule landed. The file count in `scripts/README.md` ("57") is **not**
      repeated here — one home.

### Phase 5 — collection 0

**Decided 2026-09-18: `collection-00/` is FROZEN.** It is the completed Patagonia pilot and it
has a real ATBD. No pass, no template, no extraction.

- [x] Header added to `collection-00/README_00.md`: completed pilot (Patagonia only, shipped),
      frozen and not maintained, method in the ATBD not in the repo's step docs, active development
      is `collection-01/`. Sits directly under the title, above the existing "read first" pointer,
      so it is the first thing read. **Nothing else in `collection-00/` was touched** — including
      its "Repository scope" section, which still describes the whole repo as the pilot workflow;
      that is what frozen means.

### Phase 6 — sub-tasks

- [ ] Tidy `docs/notes/`: merge, prune, and decide which entries become ADRs.
      **Not in scope: the heading numbers inside a note.** Asked and settled 2026-09-18 — a note
      keeps the `## 6.` / `## 7.` it was extracted with, because they are archived text and they
      are what makes its provenance header checkable, and a note is cited by filename anyway.
      Written into `notes/README.md` so it is not reopened.
- [ ] **Reconcile `docs/notes/` against the code, once the Phase 2 passes have all landed.**
      A note ages in two different ways and only one of them is a defect:
      - **Its provenance header and its quotes go stale by design.** The section a header names
        will usually not exist after that doc's Phase 2 pass — `notes/02-lr_term_reduction.md`
        was already citing a section that had been rewritten hours later. The header is a
        past-tense claim, so the fix is to **pin the commit** (done, and written into
        `notes/README.md`), never to re-point it at today's nearest heading — that would assert
        a correspondence nobody checked, which is the exact rot §0 found in the `docs/NN`
        citations.
      - **Its claims about live code are a real defect.** A note that names a script, path,
        constant or asset that has since moved is misleading rather than archival. Sweep for
        those: every path and identifier in `notes/` gets checked the way the four Phase 1 docs
        were, and a dead one is either corrected or marked as historical in place.
      Do this **after** Phase 2, not during: every pass adds notes, so an earlier sweep would be
      redone. Until then a stale header is tolerated and flagged, not fixed piecemeal.
      **One is already measured and waiting** (Phase 3, 2026-09-18): a mechanical link check over
      every `.md` in `collection-01/` found exactly one dead link in `notes/` —
      `notes/08-corrections_and_delivery.md` points at `09-statistics.md`, which Phase 0 moved to
      `statistics/docs/statistics.md`. Left unfixed on purpose: one link is the piecemeal this item
      exists to avoid. Re-run that check at the start of this sweep; it is cheap and it is the
      right entry point.
- [ ] Write the **collection-1 ATBD**, in one deliberate pass: collection 0's ATBD supplies the
      **structure**, `00-overview.md` + the `Key decisions` sections supply the **content**.
- [ ] **Reduction 2** (see §2): once the ATBD exists, the `Key decisions` sections shrink to
      pointers. Only then is the "explanation moves out of docs" half of the plan complete.

---

## 6. Progress log

Append one line per completed item: date — what — commit.

- 2026-09-18 — plan written.
- 2026-09-18 — **Phase 1 done** (bar the optional skill box): `00-overview.md` written from
  Iván's framing; `notes/` write-vs-reconcile rule split across Phases 2 and 6.
- 2026-09-18 — **Phase 1, first three boxes**: `TEMPLATE.md` written as a guide not a form;
  the four early docs restructured to it; `02-diagnostic_plots.md` split out;
  `notes/02-lr_term_reduction.md` extracted; three amendments recorded in Phase 1.
- 2026-09-18 — **"cite by name, never by number" adopted as a rule** (Iván): §2 rule 2 +
  `TEMPLATE.md` rule 5; the plan's own two `docs/NN §x` prescriptions and the three bare-number
  citations of the plan itself corrected to match.
- 2026-09-18 — **Phase 2, `05-object_metrics.md`** (the calibration pass): 4,376 → 1,748 words;
  `notes/05-whole_country_redesign.md` + `notes/05-memory_profile.md` extracted verbatim;
  ~30 inbound citations repointed from `§N` to named sections across 14 files; CLAUDE.md's step-05
  index row corrected (it still claimed `igraph` labelling, replaced by union-find in July).
- 2026-09-18 — **Phase 2, `04-snic.md`**: 2,694 → 2,115 words; `notes/04-snic3d_firebreaks.md` +
  `notes/04-vectorization_benchmark.md` extracted verbatim; the "Open questions" section dissolved
  (3 of 5 items already answered by the code, 2 promoted to `Gotchas`); six headings shortened so
  they can be cited by name; ~35 citations repointed across 13 files, including three that named
  long-deleted sections; CLAUDE.md's step-04 index row rewritten.
- 2026-09-18 — **Phase 2, `03-bpts.md`**: 5,766 → 2,746 words; four `notes/` entries extracted
  verbatim (`03-performance_profile.md`, `03-tile_merge_test.md`, `03-validation_2015.md`,
  `03-dropped_timediff_bands.md`); 19 `§N` citations repointed across 11 files; the two-collection
  routing (1999–2009 → `mapbiomas-chaco`) documented for the first time; CLAUDE.md's step-03 index
  row rewritten.
- 2026-09-18 — **`03-bpts.md` split**: `02-burn_probability.md` written (the spectral stage's
  product had no doc, though `00-overview.md` already promised it); the join — the per-year
  precomputation — stays in 03 as "What is precomputed per year"; §3 of this plan amended with
  the general rule.
- 2026-09-18 — **Phase 2, `06-object_model.md`**: 7,958 → 4,592 words, **split three ways** on
  Iván's mid-session suggestion — `06-object_labels.md` (1,010) and `06-object_inspection.md` (995,
  the `02-diagnostic_plots.md` precedent) alongside it; seven `notes/` entries extracted verbatim
  (`06-predictor_selection`, `06-threshold_sweep`, `06-importance_ale`, `06-population_and_size`,
  `06-c00_baseline`, `06-upload_decisions`, `06-label_prep_engineering`); ~45 citations repointed
  across 20 files; two live upload defects recorded in the step doc for the first time (they were
  only in `docs/07`); CLAUDE.md's step-06 row replaced by three.
- 2026-09-18 — **Phase 2, `validation/docs/design.md`**: 5,285 → 4,849 words; headings and ~55
  citations de-numbered across 8 files; **the strata were built on the `_v1` map and the product is
  `_v2`** — recorded, not fixed, because rebuilding is a team call.
- 2026-09-18 — **`validation/docs/design.md`, after Iván's review**: the provenance and
  "the Python wins where they disagree" boxes deleted and the two documented *departures* folded
  into the design instead (the unstratified pool draw, the rectangle `region`, the two-stage pool,
  the two extra frozen columns) — 4,849 → 5,021 words; `notes/` cut from three verbatim entries to
  one 424-word `abandoned-paths.md` (1,523 → 495 with its README), both GEE-JS appendices and the
  implementation log **deleted**; 40 `§N` citations still live in the validation Python and the
  year-selection notebook converted to names.
- 2026-09-18 — **Phase 2, `08-postprocessing.md`**: 5,284 → 1,219 words, split three ways —
  `docs/external/mapbiomas-fuego-reference.md` (the network's spec, pinned at `904fbdf` with
  `origin/master` 68 commits ahead) and `notes/08-corrections_and_delivery.md` (the three
  CORRECTIONs, the July delivery, the decisions list). The step doc survives only as the
  Argentina-vs-reference comparison and the four live open decisions; ~25 citations repointed,
  `00-overview.md`'s closing paragraph rewritten, CLAUDE.md's row replaced by two.
- 2026-09-18 — **Phase 2, `03-colab_multi_export.md`**: marked a how-to; the stale "current
  blocker" removed and the **two-collection writer access** (1999–2009 → `mapbiomas-chaco`) added,
  which was missing from this doc as well as from `03-bpts.md`.
- 2026-09-18 — **Phase 2, `07-vector_to_raster.md`**: 13,298 → 11,014 words in two passes;
  `notes/07-exclusion_rules_choice.md`, `notes/07-verification_log.md` and
  `notes/07-export_post_mortems.md` extracted verbatim (4.0 k); §12.7 re-ordered back before §13 and
  §12.8 folded into the verification note; **94 citations** repointed across 20 files; the stale
  `_v2`-in-progress box replaced by a pointer to `logs/v2-driver/STATUS.md`, and `C.PRODUCT_LULC`
  corrected to the published col-3. **A Python syntax error I introduced in the step-06 commit was
  found and fixed**; every touched `.py`/`.R`/`.sh`/`.ipynb` now parses.
- 2026-09-18 — **`07-vector_to_raster.md` split in two** (`e9e610e`): 11.0 k → 6.6 k + a new
  `07-published_products.md` (4.9 k); ~20 citations repointed across 12 files. Same commit took
  Iván's three comments: 07d is **not** paused (Vera ran it in Brazil), docs/08's four open
  decisions became three settled ones, and `00-overview.md` now says what `08-postprocessing.md` is.
- 2026-09-18 — **Phase 3 done, all eight items** (`b28561a`, `4f1d312`, `504b99c`, `c3f4bcd`,
  `c979ffb`). Workflow docstrings 6,686 → 2,368 words; `collection-01/README.md` 6,166 → 1,423 with
  all 20 bash blocks gone; three new signpost READMEs (`scripts/`, `statistics/`, `validation/`);
  `models/README.md` kept its length as the artifact reference but lost its duplicated tail. The
  plan's `Pipeline` section is reconciled to `TEMPLATE.md`'s **`Run`** — one name.
- 2026-09-18 — **what the Phase 3 verification found, which is the part worth keeping**. Checking
  each deletion against the doc that inherits it turned up five live defects, none of them
  discoverable by reading either file alone: a documented flag that does not exist
  (`--agri-max`); a docstring quoting `_v1` figures and the `_v1` asset as current when the doc
  already flags them as pre-rule; a dead pointer to `TASK-DATA-EXPORT.md`; **`models/README.md`
  giving the elastic-net grid as `{0, .25, .5, .75, 1}` when the code fits `{0.25, 0.5, 0.75}` and
  drops ridge and lasso on purpose**; and two notebooks absent from the notebooks table. Plus 17
  `§N` citations in workflow code converted to names, several pointing at numbering deleted months
  ago and two at a `statistics.md §4.4` that never existed. **The rule that catches these is rule
  1**: a fact with two homes has one that is wrong, and you only find out when you try to delete
  one of them.

- 2026-09-18 — **Phase 0 done**: 3 `git mv`s, `docs/notes/` + `docs/external/` created with
  their conventions, ~120 citations rewritten across 30 files, ROADMAP pointed here.
  Uncommitted at time of writing.
- 2026-09-19 — **Phase 4 done**: `CLAUDE.md` 6,213 → 1,584 words, one line per doc. The index is
  two tables plus a signposts paragraph; the pipeline list and the technology table were deleted
  rather than shortened, because `collection-01/README.md` already owns both — which is Phase 3
  paying off. Every doc indexed and every link checked mechanically; one stale docstring claim
  about CLAUDE.md's own credentials rule fixed in `07-burned_area_polygons.py`.
- 2026-09-19 — **Phase 5 done**: the frozen-pilot header on `collection-00/README_00.md`, and
  nothing else in that directory. Phases 4 and 5 are the last of the main checklist; what remains
  is Phase 6, whose first item (the `notes/` reconcile) still waits on nothing but a session.
