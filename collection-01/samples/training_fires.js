/*
  training_fires.js — ARCHIVAL TEMPLATE

  Shows the expected schema for the training_fires FeatureCollection.
  One such asset exists per region under:
    projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/<region>/training_fires

  Properties per feature (fire event):
    fire_id         (string or int) — unique within the region
    description     (string)        — place + year, e.g. "San Rafael 2019"
    pre_lwr         (date string)   — start of pre-fire window; null = pre_upr minus 1 year
    pre_upr         (date string)   — end of pre-fire window (inclusive)
    post_lwr        (date string)   — start of post-fire window
    post_upr_long   (date string)   — end of post-fire window for woody veg
    post_upr_short  (date string)   — end of post-fire window for herbaceous veg

  For PAT, this file is cumulative and includes fires from collection-00.

  IMPORTANT: this script is a reference/template only. It is not used by
  the collection-01 pipeline (workflow/01-training_data_export.py reads
  the GEE assets directly). Do not modify this file to re-run data collection —
  update the GEE asset instead.
*/

// Example (not executable — adjust and run in GEE Code Editor):
var training_fires_example = ee.FeatureCollection([
  ee.Feature(null, {
    'fire_id':        'fire_01',
    'description':    'Example fire – Patagonia 2018',
    'pre_lwr':        null,          // if null, computed as pre_upr - 1 year
    'pre_upr':        '2018-10-15',
    'post_lwr':       '2018-11-01',
    'post_upr_long':  '2019-06-30',  // for forest/shrubland (slow recovery)
    'post_upr_short': '2019-03-31',  // for grassland/agriculture (fast recovery)
  }),
]);

// Export to GEE asset (example path):
Export.table.toAsset({
  collection: training_fires_example,
  description: 'training_fires_PAT',
  assetId: 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/PAT/training_fires',
});
