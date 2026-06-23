# Fixing the Insync ↔ git conflict

> **Status: TODO (planned, not yet applied).** Recorded 2026-06-22 so we don't lose the plan.

## The problem

This repo lives **inside** the Insync folder (`~/Insync/MapBiomas/mapbiomas-arg-fire`), so
Insync syncs *everything* in it — including `.git/` and all git-tracked code. Two sync systems
then fight over the same files:

- **git** moves history through commits / `push` / `pull`.
- **Insync** copies raw file *contents* through Drive, with no concept of a commit.

When machine A commits + pushes, Insync *also* copies A's changed files onto machine B's disk
before B has pulled. B's working tree then no longer matches its own `HEAD`: files show up as
"modified" or "untracked" out of nowhere, branches diverge, and Insync starts making
conflict-copies. The smoking gun was the `... (2).csv` / `... (2).qmd` files in the repo —
that ` (2)` suffix is **Insync's conflict-copy naming**, i.e. Insync duplicating files because
git had changed them underneath it.

`git pull` before working *reduces* the divergence but does **not** fix it: Insync can still
overwrite or duplicate a tracked file between the pull and the commit. The root cause is the
overlap, not the discipline.

## The fix (chosen approach)

Keep the repo physically where it is, but make the two systems stop overlapping:

- **git owns the code** — synced only through the remote (`pull` / `push`). The remote is
  already the backup, so nothing is lost by Insync not syncing the code.
- **Insync owns only the heavy data** — kept in a **separate sibling folder**, gitignored,
  referenced from the repo via a symlink.

Insync ignore rules are **hierarchical**: ignoring the repo folder also ignores everything
inside it. So the data **must** live outside the repo, in its own synced folder.

### Target layout

```
~/Insync/MapBiomas/
├── mapbiomas-arg-fire/                      ← the git repo   (Insync: IGNORE the whole folder)
│   └── collection-01/data  ──symlink──┐     (already gitignored)
└── mapbiomas-data/  ←──────────────────┘    ← heavy data    (Insync: SYNC → Drive)
```

`collection-01/data/` is already in `.gitignore` ("Downloaded / derived data (large files)"),
and scripts use that path — a symlink resolves transparently, so **no code changes** are needed.
The symlink sits inside the ignored repo, so Insync never follows it: no sync loop.

## Steps (do in this order — data safety first)

**1. Move the data out and symlink it back** (repo-side; reversible, touches nothing tracked):

```bash
cd ~/Insync/MapBiomas
mkdir -p mapbiomas-data
# move existing contents (if any) into the new synced folder
mv mapbiomas-arg-fire/collection-01/data/* mapbiomas-data/ 2>/dev/null
rmdir mapbiomas-arg-fire/collection-01/data
# relative symlink: collection-01/data -> ../../mapbiomas-data
ln -s ../../mapbiomas-data mapbiomas-arg-fire/collection-01/data
```

`collection-01/data/` is gitignored, so the symlink is ignored by git automatically — nothing
to commit.

**2. Let Insync sync `mapbiomas-data/` up to Drive and CONFIRM it is there** — before step 3,
so the data has a synced home before the repo goes dark.

**3. Tell Insync to ignore the repo.** In Insync 3: **Preferences/Settings → Ignore List**
(gitignore-style patterns). Add a rule for the repo folder (e.g. `mapbiomas-arg-fire/`), and as
belt-and-suspenders also `.git/`. (Menu names drift between Insync versions; the feature is the
**Ignore List** / ignore rules, *not* "Selective Sync", which only chooses which Drive folders
download.)

> ⚠️ The repo is currently synced to Drive, so once it is ignored Insync may drop the cloud copy
> of the code. That is fine — **GitHub is the code backup** (that is the whole point of code
> living in git, not Drive). Don't be alarmed if the repo's Drive copy disappears.

## Per-machine routine afterwards

- Work on **one machine at a time**; **commit + push before switching** machines.
- On the next machine: **`git pull` first**, then work.
- With the code out of Insync's hands, this routine genuinely keeps you in sync.

## Cleanup (after the move is confirmed working)

- Remove the Insync conflict-copies still in the repo: the `... (2).csv`, `... (2).qmd`,
  `... (2).rds` files.
- Drop the safety stash once the remote is confirmed good:
  `git stash list` → `git stash drop stash@{0}` (currently:
  `laptop-local-divergence-safety-2026-06-22`). Inspect first with
  `git stash show -p stash@{0}` if unsure anything local was lost.

## Why this is the normal way

Cloud file-sync (Drive / Dropbox / OneDrive / Insync) corrupting or fighting `.git` is a
well-known, long-standing gotcha. The near-universal practice:

- **Code → a git host** (GitHub etc.). That *is* the sync and the backup.
- **Data → cloud file-sync**, in its own folder, gitignored, referenced by symlink or a config
  path.

A separate folder for the heavy stuff is exactly how people handle "I still want it on Drive".
(Tools like DVC / git-LFS / git-annex version big data alongside git, but they are overkill
here — a gitignored data folder synced by Insync covers the share-via-Drive need.)
