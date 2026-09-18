# TEMPLATE — the shape of a step doc

A **guide, not a form.** The docs in this folder describe genuinely different things — a GEE
export, a lookup table, a local cleaning gate, a model fit — and forcing one skeleton on all of
them would pad some and crush others. What is fixed is the **spine** (four sections every doc
has) and the **rules about where a fact lives**. Everything else is offered when the step has
one, and left out when it does not.

`01-training_data.md` is the model doc. Read it before writing a new one.

---

## 1. The spine

In this order. **Bold = always present.**

| Section | Quota | Holds | Must not hold |
|---|---|---|---|
| **Title + orientation** | 1 paragraph, ≤ 5 lines | what this step produces, and where it sits in the chain | history, caveats, commands |
| Foundations | 1–3 paragraphs | why this *kind* of approach — including the implementation constraints that forced it | parameter values, per-run results |
| **Inputs → Outputs** | a flow line + a small table | what goes in, what comes out, where it lands | how it is computed |
| **How it works** | as long as it takes | the mechanics, with detail nested under what it details | commands, benchmarks |
| Run | one block | the canonical invocation + the flags that change the *outcome* | the exhaustive flag list (that is `--help`) |
| Key decisions | ≤ 5 bullets, one short paragraph each | settled choices + one-line reason + pointer to `notes/` | the story of how they were reached |
| Gotchas | bullets | the traps that cost someone a day | anything already stated above |
| **Files** | a table | production/reference files and their role | descriptions that restate the doc |
| **Related** | bullets | notebooks, `notes/` entries, sibling docs | anything not actually linked |

Whole doc: **800–1500 words.** Over that, something belongs in `notes/`.

Not every step has a Foundations or Key decisions section. `02-data_cleaning.md` has neither —
its "why" is one clause in the orientation paragraph, and nothing about it was a choice worth
recording. **An absent section is the right answer when the step has nothing to put in it**; a
section written to fill the table is worse than no section.

---

## 2. The four homes of "why"

This is the part that decides whether a doc stays readable. A given "why" goes to exactly one:

| home | holds | lifetime | reader |
|---|---|---|---|
| **Foundations** (this doc) | why this *kind* of method, and the implementation constraints behind it | survives into the next collection | another country, a reviewer |
| **Key decisions** (this doc) | the settled choices *within* the method | may change per collection | collection 2, you in a year |
| **`docs/notes/`** | how we got there — benchmarks, abandoned roads, post-mortems, dated results | permanent archive, never pruned | collection 2 |
| **the ATBD** | what the algorithm *is*: the formal object — equations, term lists, the model's structure | per collection | anyone, formally |

**The Foundations ↔ ATBD line is blurry, deliberately.** Collection 0's ATBD states the logistic
regression's equation and its J=40 terms, and says nothing about why a coefficient set is the
only model you can actually deploy as an asset over Argentina's whole Landsat archive. That
second argument is Foundations. But a Foundations paragraph may also restate, more concretely or
with more reference to the code, something the ATBD says abstractly — **that redundancy is
accepted.** Do not try to draw the line while writing a doc; Phase 6's reduction 2 decides it
per paragraph, with the ATBD in front of it.

### Two rules that follow

**Keep the outcome, move the route.** When history goes to `notes/`, the doc keeps the *result*
and at most one clause of how it was reached. Not "see `notes/`" — the reader must not have to
open a second file to learn what production does.

> ✅ `P=50 is deployed: predictive skill is flat from the full 129-term fit down to P≈50 and drops
> below it (sweep and evidence: `notes/02-lr_term_reduction.md`).`
> ❌ two paragraphs on the 427-term design, the collinearity, the pruning sweep and the P grid.

**A notebook is not a home for settled rationale.** Notebooks hold exploration while a question
is open. Once the answer changes what production does, **the answer moves into the doc in that
same commit**, and the notebook becomes the evidence behind it. A doc must never say "the
rationale lives in the notebook".

---

## 3. Rules

1. **The first paragraph is self-sufficient.** A reader gets what the step is for without
   opening the ATBD or `00-overview.md`.
2. **`00-overview.md` states the spectral / temporal / spatial framing once.** A Foundations
   section assumes it and argues only its own step. Do not restate the framing per doc.
3. **Detail nests under what it details.** A doc is not a flat list of `##` sections: if a
   passage explains one numbered rule or one sub-step, it is a `###` under it.
4. **Name a heading for what it does, not for its number.** The filename already carries the
   number, so `## Export`, not `## Step 01 — export` — which implies a step 02 that never comes.
5. **No long code blocks.** Named packages, functions, GEE methods — yes. Blocks — no, except
   the one `Run` block.
6. **Parameters, paths, thresholds and asset ids live in `config/` and `utils/constants.py`.**
   Docs link to them and never restate a value that code owns.
7. **How to invoke one script lives in its docstring / `--help`.** The doc's `Run` block carries
   the sequence and the outcome-changing flags, nothing more.
8. **Nothing is deleted, it is moved** — to `docs/notes/`, with the provenance header in
   `notes/README.md`.

---

## 4. Skeleton

```markdown
# NN — <what it makes>

<One paragraph: what this step produces, what it consumes, where it sits. Self-sufficient.>

## Foundations                  <!-- optional -->
<Why this kind of approach. The constraints that forced it. 1–3 paragraphs.-->

## Inputs → Outputs
`<A> + <B>` → **`<step>`** → `<output>`
| Input / Output | What it is | Where |
|---|---|---|

## How it works
### <sub-detail nests here>

## Run                          <!-- optional -->
```bash
```

## Key decisions                <!-- optional -->
- **<choice>.** <one-line reason>. <pointer to notes/ if there is history>

## Gotchas                      <!-- optional -->

## Files
| File | Role |
|---|---|

## Related
```

See `DOCS-CLEANUP.md` §2 for why this folder is shaped this way.
