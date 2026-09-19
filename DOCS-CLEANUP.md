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
   - *The order of the steps and their dependencies* → **a `Pipeline` section in the step doc**
     (prose + commands, no *why*). Order is not expressible inside any one script.
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

> **What the citation sweep turned up — `docs/NN` was never a stable address.**
> `docs/10` meant **two different documents** depending on the citing file: validation in
> `validation/*`, `scripts/10_burned_area_by_fire_year.py` and
> `notebooks/validation_year_selection.qmd`; the factsheet spec everywhere else. And every
> `docs/11` in code (6 in `workflow/07-month_of_burn.py`, 3 in `scripts/objects_region_tag.R`)
> pointed at **the old statistics numbering** — confirmed from git: the `feat(11)` commits are
> statistics work, and `git log --diff-filter=R` shows `docs/10-validation.md` →
> `docs/11-validation.md` in `df0d545`. A renumber had silently broken every citation to both.
>
> **This is the strongest argument for the whole reorganisation**: a numbered sequence is a
> moving address, and moving addresses rot in silence. Names do not. Do not reintroduce numbers
> for anything outside the 01–08 chain.
>
> ⚠️ **Those 9 `docs/11` citations now point at the right document but keep their OLD section
> numbers** — e.g. `07-month_of_burn.py:58` cites "§2, §6" for the agriculture filter, which is
> not §2 of today's statistics doc. They were rewritten to the correct *file* (strictly better
> than pointing at nothing) and the **§ numbers must be re-checked during the statistics pass**
> in Phase 2. The files: `workflow/07-month_of_burn.py`, `scripts/objects_region_tag.R`.

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
> **Three amendments from the Phase 1 review (2026-09-18).**
>
> **(a) A class of explanation never reaches the ATBD, so the docs keep it permanently.** §2's
> "reduction 2" assumed the explanation all moves out. It does not: collection 0's ATBD gives the
> logistic regression's equation and term list — the formal object — and says nothing about why a
> coefficient set is the only model deployable as an asset over the whole Landsat archive, or why
> a probability-mode random forest is not exportable from GEE. That argument is **Foundations**,
> and it stays in the doc. Reduction 2 removes the docs' restatement of the *formalism*, not the
> implementation rationale. The Foundations ↔ ATBD line is **blurry on purpose** — some
> redundancy is accepted, and Phase 6 draws it per paragraph with the ATBD in front of it, not
> per section now.
>
> **(b) A notebook is not a home for settled rationale.** Notebooks hold exploration while a
> question is open; once the answer changes what production does, the answer moves into the doc
> **in that same commit** and the notebook becomes the evidence. Three docs said "the design
> rationale lives in the notebook" — that pointer is reversed. Add this to §2 rule 1.
>
> **(c) Reduction 1 keeps the outcome, not just a pointer.** When history goes to `notes/`, the
> doc keeps the **result** plus at most one clause of route — a reader must not open a second
> file to learn what production does. `TEMPLATE.md` §2 has the worked example.

- [x] `docs/00-overview.md` written (819 words) from Iván's framing: the spectral → temporal →
      spatial order, the two parts of the spatial stage (region growing, then object
      classification), **the unifying principle** — quantities are preserved as long as possible
      so every later stage weighs the evidence instead of inheriting a verdict — and the
      step→stage table. Steps 07–08 are marked as publication, not a fourth analysis.
- [ ] Consider promoting the template to `.claude/skills/step-doc/SKILL.md` so every future doc
      starts from the same rules instead of from that day's prompt.

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

> **What the calibration pass settled, and the two open questions (2026-09-18).**
>
> **(a) The heading-number rot is INSIDE the docs too, not just across them.** Phase 0 found that
> `docs/NN` was never a stable address; the same is true of `§N` *within* a doc. `docs/05 §3` meant
> **two different sections** depending on the citer — the metrics section under an old numbering
> (9 citations: `objects_data_functions.R`, `06-object_model.R`, `04-snic.py`, `constants.py`,
> `objects-analysis.qmd`, `04-snic.md`, `objects_upload.py:184`) and the *object ids* section under
> today's (`objects_upload.py:173`). `§7b` and `§7c` were cited 7 times and have never existed.
> Since `TEMPLATE.md` rule 4 drops heading numbers anyway, **all 30-odd inbound citations were
> rewritten to named sections** — `docs/05 "Metrics"`, `docs/05 "Label"`, `docs/05 "Run"` — and the
> history citations now point at the `notes/` file directly. **Iván adopted this as a rule**
> (2026-09-18): it is now §2 rule 2 above and `TEMPLATE.md` rule 5, and it binds every remaining
> Phase 2 pass.
>
> **(b) What counted as history here** — the rule applied, for sign-off: a passage left the doc if
> it was *dated*, a *benchmark*, a *rejected alternative*, or a *bug post-mortem*. It stayed if it
> describes what the code does today, even when the reason is historical (the dilation-as-window
> equivalence stays, because it **is** the live algorithm; the halo that OOM'd is one clause).
>
> **(c) The word count is a target, not a limit — settled 2026-09-18.** The doc landed ~15 % over
> the 1500 figure and stays there: what remains is live algorithm (the enlarged-context distance
> table, the metric definitions, the `pid`/`oid` scheme), all of it cited from code. Iván's ruling:
> the cap is soft. `TEMPLATE.md` §1 now says so, with the test that matters — *is the excess
> history, or the live algorithm?* — and this doc as the worked precedent. **Do not cut a live rule
> out of a step doc to hit a number.**

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

> **What the step-03 pass found (2026-09-18).**
>
> **(a) A doc can be missing a live rule that every consumer already depends on.** The step-03
> output does **not** live in one collection: the `mapbiomas-argentina` asset home ran out of
> space, so **1999–2009 export to `mapbiomas-chaco`** (`C.bpts_target_col`, a legacy-rooted
> project whose paths carry no `/assets/` segment). That landed in `bd7b033` in the code and the
> constants' comments, and the doc — which states the output collection in its second paragraph —
> was never updated. The step-04 lesson was *an open question the code has since answered*; this
> is its sibling: **a change the code made that the doc never heard about**. Both are found the
> same way, by reading `git log` for the step's script before trusting the doc's facts.
>
> **(b) The `n` band's twin rule survived reduction because it is the product contract.** The
> band table, the decode column and the −1/−2 sentinels stay in the doc at full length: they are
> what a downstream reader needs to interpret the asset, and no code file states them in one
> place. What left was every *measurement* of those bands.
>
> **(c) 2,746 words, the largest step doc so far, and it stays** (`TEMPLATE.md` §1). Step 03 is
> two algorithms in one export — a per-observation model and a per-pixel time-series reduction —
> and after the four extractions what remains is mechanism: the coefficient-to-band construction,
> the window definitions, the padding, the two arrays, the argmax bundle, the encoding, and five
> GEE array rules that are still load-bearing in the code. There is no history left to move.

- [x] `04-snic.md` (2,694 → 2,115 words) — §1 (the shelved SNIC-3D) →
      `notes/04-snic3d_firebreaks.md`; §5c (the FY2000 vectorize benchmark) →
      `notes/04-vectorization_benchmark.md`, both verbatim. §7 "Open questions" dissolved: three
      of its five items had been **answered by the code** since (see the box below). ~35 inbound
      citations repointed from `§N` to named sections across 13 files.

> **What the step-04 pass found, beyond the extraction (2026-09-18).**
>
> **(a) A doc's "Open questions" section rots faster than anything else in it.** Three of §7's five
> items were settled in code and nowhere else: whole-country SNIC @512 *does* complete (28
> fire-years are mapped), the object filter *is* the step-06 BART, and the steppe-padding question
> was answered **negatively downstream** — step 05 drops `candseed == 3` east of −70.6°, which is a
> live rule that existed only as a `[OPEN]` question in step 04's doc and a code comment in step
> 05's script. The two genuinely live items (the trimmed edge fire-years; `veg_fire = MB(Y1−1)`)
> became `Gotchas`. **An open question that the code has since answered is not history — it is a
> live rule with no home**, so look for its answer in the code before extracting it to `notes/`.
>
> **(b) Named citations need short headings, so the pass renames them.** `docs/04 §4.3` became
> `docs/04 "Patagonia dieback padding"`; a heading like "Patagonia slow-dieback forward padding
> (`candseed = 3`)" is unquotable in a code comment. Six `###` headings were shortened for that
> reason alone, which is worth doing while rewriting rather than after.
>
> **(c) Naming is not immunity — three citations named sections that had been DELETED.**
> `§"Ground seeds & candidates in the data"` (2 call sites), `§"Tune seeds…"` and `§"Do it now?"`
> all pointed at headings that existed in earlier versions of the doc and were removed long before
> this pass; one of them was already a misquote of its own heading ("…in the burned/unburned
> data"). A name survives *insertion above it*, which is the failure mode `§N` has; it does not
> survive deletion. The difference is that it then fails **loudly** — unfindable rather than
> silently pointing at the wrong section — which is why they were caught here at all. Same fix as
> for a dead `§N`: repoint it at what the reader actually needs.
>
> **(d) Over target at 2,115 words, and it stays** (`TEMPLATE.md` §1, the step-05 precedent). What
> is left is live mechanism — the fire-year construction, the per-pixel K selection, the dieback
> rule, the two-stage asset handoff — every piece of it cited from `constants.py` or a script.

> ## 🔻 IVÁN, REVIEW FROM THIS ITEM BELOW 🔻
> **Iván's comments up to and including the step-06 item were addressed on 2026-09-18** (his
> review of the items below it was still in progress, so nothing from the `validation/docs/design.md`
> item down was touched). What each comment asked and what came of it is recorded under its own item.

>
> Everything from here down was done in **one unattended session on 2026-09-18** (you were at the
> GIM), so the per-item review the protocol calls for has not happened. Each item was committed
> separately, so any one of them can be reverted on its own. The per-pass boxes below say what was
> decided and what needs your sign-off.

- [x] `06-object_model.md` (7,958 → **4,592**) — **split into three docs on your suggestion**
      (mid-session: *"perhaps doc 06 can be separated in data collection and modelling"*):
      `06-object_labels.md` (1,010 — collection in GEE, the join, the fitting set),
      `06-object_model.md` (4,592 — the classifier and the upload) and `06-object_inspection.md`
      (995 — the QGIS review layer). Seven `notes/` entries extracted verbatim, 4.6 k words. ~45
      inbound citations repointed from `§N` to named sections across 20 files; two dead *named*
      citations found; CLAUDE.md's one step-06 row replaced by three. **Two live defects the doc
      had never recorded — see the box.**

> **What the step-06 pass found (2026-09-18).**
>
> **(a) The doc was wrong about what the upload does, and the error had already cost a product
> 5.1 Mha.** It said the max-vertices dialog setting makes GEE "subdivide the geometry *inside* the
> feature, so `oid` and the properties survive". It does not: it writes **several features sharing
> one `oid`**, each repeating the whole object's attributes. That is documented in `docs/07`
> ("`oid` is unique per OBJECT, not per row") because that is where it hurt — a naive
> `aggregate_sum('area_ha')` over-counted the polygon layer by 5,118,513 ha — but step 06 *owns the
> upload*, and its own doc asserted the opposite. Likewise **`objects_raw_2021` carries 1,249
> duplicated features** that no metadata count reveals; that too was recorded only in `docs/07`,
> under the consumer that had to guard against it. Both are now `Gotchas` in `06-object_model.md`.
> **The general lesson is new and worth keeping**: the step-03 pass found *a change the code made
> that the doc never heard about*, and the step-04 pass found *an open question the code had since
> answered*. This is the third of the family — **a defect that a DOWNSTREAM doc discovered and
> recorded, in the wrong doc.** It is the hardest of the three to find, because nothing in the step
> doc looks stale and nothing in `git log` for the step's own scripts shows it. The way it was
> found: `grep` for the step's output asset (`objects_raw`) across the whole repo, not just its own
> directory. **Add that to the per-doc protocol** — grep the step's *outputs*, not only its inputs
> and its scripts.

> **Iván asked (2026-09-18): did this duplication ever bite, is the GEE asset still duplicated, and
> wasn't it solved afterwards? Measured, and the answer is no — it is still there.**
>
> It bit exactly once and was contained: two `07e` exports landed with the 1,249 extra FY2021 rows and
> were thrown away; the third carried the `distinct('oid')` guard, and every product since is built
> through it. Nothing published is wrong. But the *asset* was never fixed — `updateTime` is still
> `2026-07-28T20:12:31Z`, the hand ingest — and `fires(2021)` with the guard disabled still
> materialises **54,514 rows for 53,263 distinct `oid`**, the July figure to the row. What was
> "noticed afterwards" was the guard, not a repair.
>
> Three things are new, and all three are now in `docs/06` "Gotchas" (the table),
> `docs/07` "`objects_raw_2021` is duplicated in storage", the `07-burned_area_polygons.py` docstring,
> `notes/07-export_post_mortems.md` (a dated entry, July text untouched) and the BACKLOG item:
>
> - **What we uploaded is clean.** `objects_raw_2021.shp/.dbf` is 66,393 records for 66,393 distinct
>   `oid`, matching `objects_2021_pred.csv` row for row. The duplication is on GEE's side of the
>   ingest, so the re-ingest is just the ingest again — there is nothing to rebuild first.
> - **The surplus is query-dependent**, which one export could not reveal: 1,251 rows under
>   `fire == 1 & area_ha >= 1`, **241** under `area_ha >= 1` alone, **none** under `fire == 1` alone or
>   an unfiltered read. "How many duplicates does this asset hold" has no answer, so **no count is an
>   acceptance gate** for the re-ingest.
> - **A bare `.map()` does not materialise**, so the July lesson needed tightening — and the old
>   BACKLOG note ("insert a `.map()` before trusting a feature count") would have produced a false
>   clean bill. `map(f => f.set(…))` and a map that rebuilds the feature from its geometry both come
>   back at the clean 53,263 under the filter that yields 1,251; it takes a `Feature.select()` in the
>   map — what `fires()`'s `one()` does.


> **(b) The three-way split, and why it is three and not two.** Your message said two, "depending on
> length". The labels/model line is yours and is the `01-training_data.md` ↔ `02-model_fitting.md`
> shape one step later. The third file is the **`02-diagnostic_plots.md` precedent you set in Phase
> 1** — the QGIS layer produces nothing the pipeline consumes, `objects-inspect-cache/` is
> explicitly regenerable, and it exists so a human can look: a diagnostic tool, not a step. If you
> want two, folding `06-object_inspection.md` back in is a `cat` and three link fixes. **This is the
> one thing in this pass that is genuinely your call rather than mine.**
>
> **(c) 4,592 words is still the largest step doc, and I do not think more should come out.** The
> first rewrite landed at 6.0 k; three tightening passes bought only ~300 words, which is the signal
> `TEMPLATE.md` §1 describes — the excess was not padding. What is left after the three-way split is
> the model, the 20 predictors, the leak rule, the call columns, the thresholds, the CV design, the
> importance analysis and the upload: eight live topics, every one cited from code. The real
> reduction came from moving 4.6 k words of measurement into `notes/` and 2.0 k into the two sibling
> docs.
>
> **(d) Two more dead *named* citations**, continuing the step-04 finding that naming is not
> immunity: `README.md` cited `docs/06 "Looking at it on a map without uploading to GEE"`, a heading
> that never existed under that name (it was "11. Inspecting it in QGIS, without uploading to GEE"),
> and `docs/05`'s Related list cited "§4 on why no predictor may proxy for the year". Both now point
> at real names. The count of *numbered* citations repointed in this pass was ~45, the most of any
> pass so far, because step 06 is cited from step 07's four scripts as well as its own.
>
> **(e) `notes/` conventions held with no friction.** Seven entries, all verbatim, all with pinned
> provenance headers naming sections this same pass deleted — which `notes/README.md` says is
> correct and not to be repaired. Nothing needed inventing.

> **Signed off by Iván (2026-09-18)** — the three-way split, the notes and the pass itself. The two
> comments he left inside the docs are done: the duplication question is answered in the box above,
> and **"Why no predictor may identify the year" was cut 475 → 247 words**, keeping the rule, the two
> predictors it cost, what the rule leaves in the set (`doy_sin`/`doy_cos`, `date_span`, no absolute
> time coordinate) and the do-not-publish warning on the residual trend, with every measurement now
> only in [`notes/06-predictor_selection.md`](collection-01/docs/notes/06-predictor_selection.md).
>
> The read-through of the three files turned up **one wrong number and two more dead *named*
> citations** (the step-04 finding again — naming is not immunity):
>
> - **the QGIS layer has 34 curated fields, not 32.** `FIELDS` in `objects_inspect_export.R` is
>   29 names + `VEG_GROUP_COLS`, and the landed `2020_objects_pred.gpkg` has 36 columns = 34 + `fid`
>   + `geom`. The doc's own group table already listed 34; only the summary row, `README.md` (two
>   places) and CLAUDE.md said 32. Fixed in all four.
> - **`06-object_model.md` cited `04` "Seeds and candidates"** — the heading is "Seed and candidate",
>   singular. Repointed.
> - **`06-object_model.md` and `objects_upload.py` cited `05` "Object ids"** — a heading that does not
>   exist; `oid` is defined in docs/05's `Foundations`. Repointed both.
>
> Everything else verified against code rather than read: `PREDICTORS` is 20 (15 + 5),
> `clean_tagged()` reproduces **5255 / 2788 fire / 2467 non-fire** and every cut in the cascade
> (−234 / −10 / −1315 / −1) exactly, the four deployed cuts match
> `config/object_model_thresholds.csv` to the digit, `size_class` is 6 display classes against
> `th_band`'s 4, and every named cross-doc citation in the three files now resolves.


- [x] `validation/docs/design.md` (5,285 → 4,849, and **the premise of this item was wrong** — see
      the box). Three `notes/` entries extracted verbatim into a new
      `validation/docs/notes/`: the dated implementation status, and **both GEE-JS appendices**,
      which are superseded by the Python (`01_strata_export.py` is a direct port of A;
      `02_sample_pool.py` replaced B, which does not scale). That removes the 21 % code-block
      problem entirely. Title de-numbered, all 16 headings de-numbered and ~35 internal + ~20
      inbound `§N` citations converted to names across 8 files. An attribution box and a **status
      box** were added; the design prose itself was **not cut**. A correctness finding is recorded
      in the doc and below.

> **What the validation pass found (2026-09-18).**

[Claude, I left instructions for you at validation/docs/design.md]

> **(a) The item's premise — "NOT WRITTEN BY IVÁN" — is wrong, and the correct split matters.**
> `git log --follow` says the design doc was written by **Iván** on 2026-08-21 (`8b2e859`), two days
> *before* the first implementation commit. What is **Ramón Peña Agrest's** is all four
> `validation/*.py`, the Colab notebook, and the §0 implementation-status section he added to the
> doc while fixing the OOMs (`bccc973`, `60df891`). So the sign-off rule applies to §0 and to the
> code, not to the design — which is why the design prose was left alone here and only §0 and the
> appendices were moved. Both authorships are now stated in the doc's header box, which the item
> asked for. **The plan's own text should be corrected**; it is the one place in this file that
> asserts a provenance nobody had checked, which is the exact failure mode it warns about elsewhere.
>
> **(b) ⚠️ The strata rasters were built against the `_v1` map, and the product is now `_v2`.**
> This is the substantive finding and it was not recorded anywhere. The strata and the nine frozen
> lists were exported 2026-08-31, when `C.MONTH_OF_BURN_COL` resolved to `collection1_fire_mask_v1`;
> `C.PRODUCT_VERSION = 2` landed 2026-09-11 in `8cf4b7f`, applying exclusion rules A and B
> (`docs/07` "The `_v2` re-export"). **The sample is still valid** — the estimators need only that
> the strata partition the population with known weights, and a stratum may be defined by anything,
> including a superseded map. **One rule breaks**: "Estimators and outputs" says the map class is
> the frozen `burned` band and is never looked up later, and against v2 it must be. The stored
> `col`/`row` addresses make that possible. Recorded in the doc twice — the status box and an
> inline warning at the rule it breaks — and flagged as *to settle before interpretation*, not
> fixed, because whether to rebuild the strata on v2 (new lists, discarding the frozen ones) is a
> team decision.

[I knew it, not a problem, but it must be documented, as you did.]

>
> **(c) Both appendices were a second home for code that already exists in Python**, which is a
> stronger reason to move them than "inline JS cannot be linted". Appendix A's own header even says
> so from the other side: `01_strata_export.py` opens with *"Traducción directa a Python del
> Appendix A"*. And Appendix A had gone stale in the way a duplicate does — it hardcodes
> `collection1_fire_mask_v1` while the Python reads `C.MONTH_OF_BURN_COL`, so the code followed the
> `_v2` rename and the doc did not. **That is how (b) was found.**
[Claude, remove that appendix a, that's not needed.]

> **(d) One artefact is superseded and still in the repo**: `colab_sample_pool_export.ipynb`
> (Ramón, 2026-08-28) implements the Appendix-B recipe that the 2026-08-31 post-mortem rejected.
> It is now named as such in the doc's `Files` table rather than silently sitting there. Deleting
> or rewriting it is Ramón's call.

[Claude, just leave in a note all the paths that the validation took and hit problems, like that
in appendix B. Just mention like a list of abandoned paths, brief, not to take again. 
No need for such long notes. There may be notes, but smaller]


> **(e) `validation/docs/notes/` is new.** `notes/` conventions are defined for
> `collection-01/docs/notes/`; validation's docs are colocated with its code, so its lab notebook
> is too. Its `README.md` points at the main one rather than restating the rules. Same question
> will arise for `statistics/` — flagging it now so the frozen statistics pass does not have to
> decide it under time pressure.

[Claude, ok with that above]

>
> **(f) Two Phase-0 leftovers fixed in passing**: `statistics/docs/statistics.md` still linked
> `10-factsheet_design.md` (renamed in Phase 0), and CLAUDE.md's factsheet and validation rows had
> been **merged into one table cell** by a missing newline (`… comes from || \`…/design.md\` | step
> 11 — …`), so the validation row had not been rendering as a row at all since the move.

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

> **What the step-08 and colab passes found (2026-09-18).**
>
> **(a) A step doc can be a duplicate of its neighbour and read as perfectly current.** Every
> substantive claim in §6 of `08-postprocessing.md` — the LULC mask being upstream, paint
> reproducing the pixel set, the scars being a fresh labelling pass, the verified calendar
> partition, the `candseed == 3` parent date — is also in `docs/07`, measured, and CLAUDE.md's
> docs/07 row already listed all five. Nothing in it was stale and nothing was history, so neither
> the reduction-1 test nor a currency check would have flagged it. **What flagged it was asking
> the plan's own question** — *does a step-08 doc survive at all?* — which is worth generalising:
> when two docs cover adjacent stages, check for duplication explicitly, because a per-doc pass
> structurally cannot see it.
>
> **(b) The external reading was pinned, and the pin is already the story.** `mapbiomas-fire` was
> cloned locally at `904fbdf` (2026-09-15); on the day it was pinned `origin/master` was **68
> commits ahead** and none of those had been read against the text. That is stated in the header
> box rather than fixed by pulling: pulling would have made the doc's claims unverified against a
> repo nobody had reviewed, which is worse than an honest pin. `docs/external/README.md`'s rule
> should probably say so explicitly — *pin what you read, do not pull to look current*.
>
> **(c) The colab how-to had two false statements, and the harmful one was an omission.** It still
> flagged "export the region raster ← **current blocker**" for something done on 2026-06-24, which
> is merely embarrassing. The real defect: step 4 tells a contributor to get writer access to *the*
> output collection, singular — but `C.bpts_target_col()` routes **1999–2009 to
> `mapbiomas-chaco`**, so anyone claiming an early year would have failed on permissions with no
> idea why. That routing is the same fact the step-03 pass found missing from `03-bpts.md`; it had
> been missing from **two** docs, and fixing one did not fix the other. **When a pass adds a
> previously-undocumented rule, grep for every other doc that should have had it.**
>
> **(d) Four Phase-0 broken links fixed in passing**, all in the moved statistics docs:
> `statistics.md` still linked `07-vector_to_raster.md`, `08-postprocessing.md`, `../../ROADMAP.md`
> and `11-validation.md` as if it were still in `docs/`. A `.md`-link resolver over
> `collection-01/` now reports clean except one archived link inside a `notes/` file, which stays.

- [x] `07-vector_to_raster.md` (13,298 → **11,014**) — **two passes, as the plan asked**
      (extraction `5653986`, rewrite in the commit below). 4.0 k words verbatim to three `notes/`
      entries; every heading de-numbered; §12.7 moved back where it belongs and §12.8 dropped into
      the verification note, which is the re-order the plan asked for; **94 inbound `§N` citations**
      repointed across 20 files — the most of any pass. **Two currency defects and one self-inflicted
      bug — see the box. It is still by far the largest doc, and I did not split it.**

> **What the step-07 pass found (2026-09-18).**
>
> **(a) I broke a production file in the step-06 commit and pushed it.**
> `workflow/07-burned_area_polygons.py` did not parse from `54e3e8d` until the commit below: a
> citation rewrite put a double-quoted section name **inside** a double-quoted Python string
> (`"… (docs/06 "The three call columns")"`). It is fixed, and there is a lesson worth keeping in
> the protocol: **naming sections instead of numbering them puts quotes into citations, and
> citations live inside string literals as often as inside comments.** A `§` never had this
> problem. Every `.py`, `.R`, `.sh` and `.ipynb` the whole cleanup has touched has now been parsed —
> all clean — and **that sweep should be the last step of every remaining pass**, not an
> afterthought here.
>
> **(b) The doc's status box said the `_v2` rebuild was in progress; it is not, and one part is
> paused.** `logs/v2-driver/STATUS.md` (last tick 2026-09-18 20:15) reports 07a, 07b, 07c and 07e
> complete on v2 and **07d paused — deprioritised 14 Sep because the statistics come first and do
> not need it**. So the nine published subproducts are not on v2 while the month collection they
> derive from is. The doc now points at the board as the source of truth instead of restating a
> state that goes stale in a day. **A status table inside a doc competes with a status file that is
> written every 15 minutes, and loses.**
>
> **(c) `C.PRODUCT_LULC` had moved and the doc still named the old asset.** It says
> "currently `…collection3_integration_v1_buffer`, set 2026-07-29"; the constant is now the
> published `mapbiomas_argentina_collection3_pb`. The distinction matters, because the **v1**
> coverage products on the asset store really were built against the preliminary layer — that is
> part of what the v2 re-export is *for*. Same family as the step-03 and step-08 findings: a
> constant moved, the code followed, the doc did not.
>
> **(d) `docs/07 §5` meant two different sections depending on who was citing it** —
> `07-calendar_scars.R` and `watch_07c.py` both used it for the scar build, while §5 of the doc was
> "The LULC mask… embedded upstream". Third instance of the same rot, after `docs/05 §3` and
> `docs/10`. Nothing new to decide; recording it because three instances in one repo is the
> argument, not one.
>
> **(e) ⚠️ IT IS STILL 11.0 k WORDS, AND THAT IS THE ONE THING I WOULD NOT SIGN OFF ON.** The
> extraction found only 4.0 k of history, because almost nothing in this doc is history: it is the
> exclusion ruleset with three independent implementations, five sub-steps with their own scripts
> and traps, nine encodings the platform decodes, and a user-facing layer with two storage defects.
> Three tightening passes after the extraction bought ~300 words. **The remedy is structural, and
> it is your call because the plan did not ask for a split here** (unlike `08`, and unlike `06`
> where you asked mid-session). The line I would draw, if you want one:
>
> | | holds | ≈ words |
> |---|---|---|
> | `07-vector_to_raster.md` | what is mapped and how the pixels are made: the decisions, the exclusion ruleset, the calendar partition, the grid, dieback, 07a, 07b, 07c | 6.2 k |
> | `07-published_products.md` | what is packaged from them: "Products, and the shape they take", 07d's nine subproducts, 07e's polygon layer | 4.4 k |
>
> The doc itself already draws that line — 07d and 07e need no vectors and no local work, and it
> says of 07e that it "depends only on step 06, not on 07a–07d, so it can be rebuilt at any time
> and in any order". Say the word and it is a 20-minute job; I did not do it unasked on the doc
> that specifies the published product.

- [ ] `statistics/docs/statistics.md` (16.8 k, was `docs/09`) — **two sessions. FROZEN, with its
      move, until the launch lands (24 Sep 2026).**
- [ ] `statistics/docs/factsheet-sep2026-spec.md` (8.8 k, was `docs/10`) — **FROZEN until the
      launch lands.** Stays Spanish. Lightest pass of all: it is a spec, and it is already done
      its job; strip status chatter, leave the figure-by-figure content.

> ## Phase 2 is done except the two frozen docs
>
> **Everything not frozen is ticked** (2026-09-18, one unattended session). The two that remain are
> the statistics pair, frozen by this plan until the launch lands on **24 Sep 2026** — six days
> away at the time of writing. They were not touched, beyond repointing citations that pointed *at*
> the docs being rewritten (Phase 0 left four broken links in `statistics.md`, which were fixed
> because a dead relative link is not a rewrite) and the ~6 `docs/07 §N` references inside them.
>
> **Three things to carry into those two passes**, all learned here:
>
> 1. **Parse everything you touched, last.** `.py`, `.R`, `.sh`, `.ipynb`. Citing by name puts
>    quotes inside string literals, and one such rewrite shipped a file that did not parse for four
>    commits.
> 2. **Grep the step's OUTPUTS, not only its inputs and its scripts.** Two of the three real defects
>    found in this session were recorded in a *downstream* doc, under the consumer that had to work
>    around them.
> 3. **Check what the constants say before trusting a value in the doc.** `C.PRODUCT_LULC`,
>    `C.MONTH_OF_BURN_COL` and `C.bpts_target_col` had all moved under docs that still named the old
>    asset. `statistics.md` cites LULC, the product version and the toolkit's assets throughout, so
>    it is the most exposed doc in the repo to exactly this.
>
> The Phase-0 warning about the **9 `docs/11` citations that kept their old section numbers** is
> still live and lands in the `statistics.md` pass: `workflow/07-month_of_burn.py` and
> `scripts/objects_region_tag.R` point at the right file with the wrong `§`.

### Phase 3 — how-to consolidation and the signposts (rule 1)

- [ ] Workflow docstrings: strip explanation and measured results, leave *what it does (3 lines)
      + usage + `docs/NN "<section name>"` (§2 rule 2 — by name, never by number)*. Touches
      `.py`/`.R` only, independent of Phase 2 — can run in parallel.
- [ ] Each step doc gets its `Pipeline` section (the sequence, in commands, no why).
- [ ] `scripts/run_*.sh` launchers: one line each in the relevant step doc's `Pipeline`, nothing more.
- [ ] **`scripts/README.md`** — NEW, the one real signpost gap: 66 files, no README. Group them by
      purpose (download/format, launchers, GEE watchers, exploration, tests) and point each group
      at its step doc. ~15 lines, no explanation.
- [ ] `validation/README.md`, `statistics/README.md` — 5 lines each: what this is, that it is
      **episodic** (not every collection runs it), → its own `docs/`.
- [ ] `models/README.md` (1.1 k words), `samples/README.md` — check they are signposts, not encyclopedias.
- [ ] **`collection-01/README.md` → map + links, NO commands** (currently ~half bash). ≤ 1.2 k words.
- [ ] Root `README.md` — check it stays a tutorial and does not duplicate the pipeline.

### Phase 4 — the index

> **Depends on Phase 3.** `CLAUDE.md` is an index of the READMEs and docs; shortening it before
> they are stable means writing it twice. It is last for that reason, not by accident.

- [ ] `CLAUDE.md` → one line per doc. Today the `docs/09` row alone is ~900 words **inside one
      table cell**, and the file violates its own rule ("keep CLAUDE.md as the index, not the
      encyclopedia") while costing context on every session. Target ≤ 1.5 k words.

### Phase 5 — collection 0

**Decided 2026-09-18: `collection-00/` is FROZEN.** It is the completed Patagonia pilot and it
has a real ATBD. No pass, no template, no extraction.

- [ ] One-line header on `collection-00/README_00.md`: completed pilot, see the ATBD, not
      maintained. Nothing else in `collection-00/` is touched.

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
- 2026-09-18 — **Phase 2, `validation/docs/design.md`**: 5,285 → 4,849 words; new
  `validation/docs/notes/` with the implementation log and **both GEE-JS appendices** (superseded by
  the Python); headings and ~55 citations de-numbered across 8 files; attribution box added (design
  Iván, implementation Ramón — the item's premise was wrong); **the strata were built on the `_v1`
  map and the product is `_v2`** — recorded, not fixed, because rebuilding is a team call.
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
  `_v2`-in-progress box replaced by a pointer to `logs/v2-driver/STATUS.md` (07d is **paused**), and
  `C.PRODUCT_LULC` corrected to the published col-3. **A Python syntax error I introduced in the
  step-06 commit was found and fixed**; every touched `.py`/`.R`/`.sh`/`.ipynb` now parses.
  The doc remains 11 k words — the split proposal is in its box, for Iván.
- 2026-09-18 — **Phase 0 done**: 3 `git mv`s, `docs/notes/` + `docs/external/` created with
  their conventions, ~120 citations rewritten across 30 files, ROADMAP pointed here.
  Uncommitted at time of writing.
