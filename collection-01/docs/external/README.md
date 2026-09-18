# `docs/external/` — readings of code we do not own

Documentation *about* an external dependency, written because that dependency is not adequately
documented at the source. It is derivative, and it carries a risk a step doc does not: **it goes
stale silently** when the other repo changes, and nothing here will notice.

## Rules

- **Pin what was read.** Every file's header box names the repo, the commit and the date it was
  read against. An un-pinned reading of a moving target is worse than no reading.
- **State who wins on conflict.** Normally our own `docs/NN-*.md`.
- **Never the home of anything about our pipeline.** If it describes what *we* do, it belongs in
  `docs/`.

Header box:

```markdown
> Describes code we do not own: `mapbiomas-fire` @ `<commit>`, read on `<date>`.
> Derivative and liable to go stale. Where this disagrees with `docs/07`, `docs/07` wins.
```

Current and expected contents: the MapBiomas Fuego network's shared post-processing (today
inside `docs/08-postprocessing.md`, split pending) and its statistics toolkit
`2-Statistics/toolkit/v03/` (today inside `statistics/docs/statistics.md`).
