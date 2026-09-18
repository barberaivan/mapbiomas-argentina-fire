# `docs/notes/` — the lab notebook

The record of **building** the pipeline, not documentation *of* it: benchmarks, roads taken and
abandoned, bug post-mortems, dated status snapshots, "measured on <date>" results.

It exists so the step docs in `docs/` can say what is true **today** and nothing else. Two
readers, two files: another country reads `docs/NN-*.md`; collection 2 reads this folder so it
does not re-make collection 1's mistakes.

**No length limit here.** Nothing is deleted to make a step doc shorter — it is moved here.

## Conventions

- One file per topic, named `NN-<topic>.md`, keeping the step number it came from.
- Every file opens with a provenance header:

  ```markdown
  > **Extracted from** `collection-01/docs/07-vector_to_raster.md` §13.6, on 2026-09-18.
  > Lab notebook — the record of building the step, not documentation of it.
  ```

- Text is moved **verbatim**. Rewriting is a separate pass.
- Tidying this folder — merging, pruning, deciding what becomes an ADR — is deliberately
  deferred; see `DOCS-CLEANUP.md` Phase 6.

See `DOCS-CLEANUP.md` §2 for why this folder exists.
