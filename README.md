# MapBiomas Argentina Fire

Annual burned area mapping for Argentina using Landsat satellite imagery, produced by the [MapBiomas Argentina](https://argentina.mapbiomas.org/) team.

---

## Collections

| Collection | Folder | Status | Coverage | Model |
|------------|--------|--------|----------|-------|
| Collection 0 | `collection-00/` | Complete | Patagonia | Logistic regression (GEE JS + R) |
| Collection 1 | `collection-01/` | In development | All regions | Regularized logistic regression (GEE Python API + R `glmnet`) |

See each collection's README for reproduction instructions:
- [`collection-00/README_00.md`](collection-00/README_00.md)
- [`collection-01/README.md`](collection-01/README.md)

---

## Getting started (first-time setup)

This repository holds **code only**. The heavy data — training samples, fitted models, CV
metrics, prediction plots — is **not** in git. It lives in a separate folder called
**`mapbiomas-arg-fire-store`** (the "store"), and a small script links it into the repo.

> **Why?** Code belongs in git/GitHub (which versions and backs it up); large data files do
> not. Keeping them apart avoids a bloated, slow git history and the sync conflicts that arise
> when a cloud-sync tool and git fight over the same files.

Setup is **three steps**:

### 1. Get the code

```bash
git clone <this-repo-url>
cd mapbiomas-arg-fire
```

### 2. Get the data store

Download it once and remember where you put it.

**Google Drive** (anyone): open the store folder →
**<https://drive.google.com/drive/folders/1hmWZWkX1iHcGAGvqtv-5JSynvLnPx7wX>** →
download it. Your browser saves it as a `.zip`; unzip it somewhere stable (e.g. your home
folder). You should end up with a folder named **`mapbiomas-arg-fire-store`** containing
`collection-00/` and `collection-01/` inside.

### 3. Link the store into the repo

From the repo root, run `setup.sh` **once**, giving it the path to the store you just got and —
optionally — the path to your GEE Python interpreter:

```bash
# store only (Python falls back to system `python3`)
./setup.sh /full/path/to/mapbiomas-arg-fire-store

# store + the GEE venv you run pipeline scripts with (recommended)
./setup.sh /full/path/to/mapbiomas-arg-fire-store /full/path/to/venv/bin/python
```

That's it. The script creates the symlinks and remembers both paths (in a local, gitignored
`.local-paths` file), so any later re-run is just `./setup.sh` with no argument.

> **Why give it the Python path?** Each machine's venv lives somewhere different, so the docs
> never hardcode it — they say "run with `$PYTHON`". `setup.sh` records your interpreter as
> `$PYTHON` in `.local-paths` (for your shell — `source .local-paths`) **and** in
> `.claude/settings.local.json` (so Claude Code's Bash uses the same one). Both files are
> gitignored, so two machines can each point `$PYTHON` at their own venv with nothing committed.

To confirm it worked:

```bash
ls collection-01/data          # should list training_observations_*.csv etc.
ls collection-01/models-store  # should list class_*_fit.rds etc.
```

> **Heads-up for contributors:** because the data is outside git, **uncommitted code is backed
> up nowhere** — get in the habit of `git commit && git push` often. Work on one machine at a
> time, and `git pull` before you start. Collaborators without write access to the store upload
> any exported files to it manually.
>
> *Symlinks require Linux or macOS (or Windows with WSL / Developer Mode enabled).*

For how to **run the pipeline** once set up, see [`collection-01/README.md`](collection-01/README.md).

---

## Regions

| Code | Region |
|------|--------|
| BA | Bosque Atlántico |
| CHACO | Chaco |
| PAMPA | Pampas |
| CUYO | Monte, Puna y Altos Andes |
| PAT | Patagonia |

---

## Documentation

- **ATBD** (methodology): [`collection-00/docs/.../mapbiomas_fire_argentina_atbd_pilot_2025.pdf`](collection-00/docs/documentation_pilot_latex/build/mapbiomas_fire_argentina_atbd_pilot_2025.pdf) — primary reference for collection 0; collection 1 ATBD in preparation.
