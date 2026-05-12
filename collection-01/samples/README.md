# samples/ — Archival JS templates

These scripts are **not part of the collection-01 pipeline** and are not
meant to be re-run as-is.

They document the interactive data-collection procedure used to build the
training locations in GEE Code Editor, so that other groups can deploy a
similar workflow for a new region or collection.

## What is here

| File | Purpose |
|---|---|
| `training_fires.js` | Template showing the properties expected in each region's `training_fires` FeatureCollection |
| `training_locations-fire_NN_template.js` | Template for an interactive GEE script that lets an analyst pick burned and unburned points for one fire event |

## How collection-01 training assets were created

1. Open `training_fires.js` in GEE Code Editor, populate fire metadata
   (date ranges, description), and export as a GEE asset under
   `FIRE/COLLECTION-1/TRAINING-DATA/<region>/training_fires`.
2. For each fire, open `training_locations-fire_NN_template.js`, update the
   fire number and the `training_fires` asset path, then interactively draw
   burned and unburned points using the GEE Geometry Imports panel.
   Export as `FIRE/COLLECTION-1/TRAINING-DATA/<region>/training_locations-fire_NN`.

## Where the resulting assets live

```
projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/
├── BA/
│   ├── training_fires
│   └── training_locations-fire_01, fire_02, ...
├── CHACO/
├── PAMPA/
├── CUYO/
└── PAT/    ← also includes fires from collection-00 (see training_fires)
```

For Patagonia (PAT), some training locations come from collection-00:
`projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/`.
The `PAT/training_fires` asset is cumulative and already includes those fires.
