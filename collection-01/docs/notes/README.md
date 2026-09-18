# `docs/notes/` — the lab notebook

The record of **building** the pipeline, not documentation *of* it: benchmarks, roads taken and
abandoned, bug post-mortems, dated status snapshots, "measured on <date>" results.

It exists so the step docs in `docs/` can say what is true **today** and nothing else. Two
readers, two files: another country reads `docs/NN-*.md`; collection 2 reads this folder so it
does not re-make collection 1's mistakes.

**No length limit here.** Nothing is deleted to make a step doc shorter — it is moved here.

## Conventions

- One file per topic, named `NN-<topic>.md`, keeping the step number it came from.
- Every file opens with a provenance header that **pins the commit**:

  ```markdown
  > **Extracted from** `collection-01/docs/07-vector_to_raster.md` §13.6
  > @ `abc1234` (2026-09-18) — that section no longer exists under that name.
  > Lab notebook — the record of building the step, not documentation of it.
  ```

- Text is moved **verbatim**. Rewriting is a separate pass.

### The header is a past-tense claim, and it will stop resolving

A provenance header says where this text *was*, not where to find something now. Once the step
doc is rewritten, the section it names is usually gone — that is expected and is not a broken
link to repair. **Do not update a header to point at today's nearest heading**: that would assert
a correspondence nobody checked, which is precisely the rot `DOCS-CLEANUP.md`'s Phase 0 citation
sweep found in the `docs/NN` citations. Pin the commit instead, so the address stays resolvable by `git show`.

The same applies inside a note: quoted doc text and cited line numbers are snapshots. A note that
quotes a doc paragraph keeps that paragraph even after the doc drops it — that is the point.

**What does need maintaining** is a note's claims about *code*: a file path, a constant, a script
name. Those are live, and a note that names a script that no longer exists is misleading rather
than archival. Reconciling them across the whole folder is a Phase 6 item.

- Tidying this folder — merging, pruning, deciding what becomes an ADR, and the reconciliation
  above — is deliberately deferred; see `DOCS-CLEANUP.md` Phase 6.

See `DOCS-CLEANUP.md` "The target shape" for why this folder exists.
