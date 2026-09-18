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
    01..08-<step>.md           one per step.  Target 800–1500 words.
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
| `03-bpts` | yes | |
| `03-colab_multi_export` | **no** — pure how-to, admin | keep, but mark as a how-to, not a step |
| `04-snic`, `05-object_metrics`, `06-object_model`, `07-vector_to_raster` | yes | |
| `08-postprocessing` | **half** — §6 is our step 08; §§1–5 are a reading of the network's repo | **split**, see below |
| `09-statistics` | **no** — episodic, consumes the map | → `statistics/docs/statistics.md`, still to `TEMPLATE.md` |
| `10-factsheet_design` | **no** — a per-launch deliverable spec, in Spanish | → `statistics/docs/factsheet-sep2026-spec.md`; stays Spanish |
| `11-validation` | **no** — episodic, consumes the map | → `validation/docs/design.md`; drops the number (it was "Step 10" in its own title and is cited as `docs/10` in code — both go away) |

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
      `Key decisions` and `Gotchas` offered when the step has one. 800–1500 words.
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

- [ ] `03-bpts.md` (5.7 k) — §§9–11 are status/handoff/decision records.
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
- [ ] `06-object_model.md` (8.0 k).
- [ ] `validation/docs/design.md` (5.3 k, was `docs/11`).
      ⚠️ **NOT WRITTEN BY IVÁN — someone else on the team authored the validation design.**
      Two consequences that apply to nothing else in this plan:
      **(a) review before editing.** Every other doc here can be cut on the author's own
      judgement; this one cannot. Read it for *correctness and current applicability* first —
      what it claims, what was actually implemented, and where the two have drifted — and get
      the author's or Iván's sign-off before cutting anything. A shortening pass that silently
      drops someone else's design decision is worse than a long doc.
      **(b) attribute it.** The header box should name the author and the date, the way
      `docs/external/` pins what it read. Right now the repo does not record that this doc has a
      different provenance from its neighbours, which is exactly how an assumption gets
      inherited without anyone noticing it was ever a choice.
      Then the ordinary pass: it is the only doc where code blocks dominate (21 %, the two GEE-JS
      appendices) — decide per appendix whether it becomes a real file in `validation/` or stays
      inline. Inline GEE JS is a fifth home for code that cannot be run or linted.
- [ ] `08-postprocessing.md` (5.3 k) — **when this splits, revisit the closing paragraphs of
      `00-overview.md`**, which describe today's 08 as "mostly our reading of the reference
      implementation". After the split that is `docs/external/`, and what stays numbered is only
      Argentina's route — which docs/07 already implements, so decide there whether a step-08 doc
      survives at all or folds into 07. — **split first** (§3): our step 08 stays numbered, the
      reading of the network's repo moves to `docs/external/` with a pinned commit. The four
      `CORRECTION —` sections are `notes/`.
- [ ] `03-colab_multi_export.md` (0.6 k) — small; mark as how-to.
- [ ] `07-vector_to_raster.md` (13.3 k) — **two sessions**. Also re-order §12.7–12.8 vs §13.
- [ ] `statistics/docs/statistics.md` (16.8 k, was `docs/09`) — **two sessions. FROZEN, with its
      move, until the launch lands (24 Sep 2026).**
- [ ] `statistics/docs/factsheet-sep2026-spec.md` (8.8 k, was `docs/10`) — **FROZEN until the
      launch lands.** Stays Spanish. Lightest pass of all: it is a spec, and it is already done
      its job; strip status chatter, leave the figure-by-figure content.

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
- 2026-09-18 — **Phase 0 done**: 3 `git mv`s, `docs/notes/` + `docs/external/` created with
  their conventions, ~120 citations rewritten across 30 files, ROADMAP pointed here.
  Uncommitted at time of writing.
