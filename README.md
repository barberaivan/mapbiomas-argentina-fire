# MapBiomas Argentina Fire

Annual burned area mapping for Argentina using Landsat satellite imagery, produced by the [MapBiomas Argentina](https://argentina.mapbiomas.org/) team.

---

## Collections

| Collection | Folder | Status | Coverage | Model |
|------------|--------|--------|----------|-------|
| Collection 0 | `collection-00/` | Complete | Patagonia | Logistic regression (GEE JS + R) |
| Collection 1 | `collection-01/` | In development | All regions | Random Forest (GEE Python API) |

See each collection's README for reproduction instructions:
- [`collection-00/README_00.md`](collection-00/README_00.md)
- [`collection-01/README.md`](collection-01/README.md)

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
