# `validation/docs/notes/` — the validation lab notebook

Same role and same rules as [`collection-01/docs/notes/`](../../../docs/notes/README.md), kept here
because validation is **episodic** and its documentation is colocated with its code
(`DOCS-CLEANUP.md` "What `docs/` holds"): dated status snapshots, superseded recipes, OOM
post-mortems.

- Every file opens with a provenance header that **pins the commit**. The header is a past-tense
  claim and will stop resolving once `design.md` is rewritten — that is expected, not a broken link.
- Text is moved **verbatim**; rewriting is a separate pass.
- A note keeps the heading numbers it was extracted with, and is cited by **filename**.

What is here is, specifically, **code and status that the Python implementation superseded**. The
design itself stays in [`../design.md`](../design.md); where the two disagree, the code wins.
