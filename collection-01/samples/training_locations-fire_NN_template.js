/*
  training_locations-fire_NN_template.js — ARCHIVAL TEMPLATE

  Interactive GEE Code Editor script for picking burned and unburned training
  points for ONE fire event. Replace NN with the fire number (e.g., 01, 02).

  Workflow:
    1. Set FIRE_ID and REGION below.
    2. Run the script to load the reference imagery (false-color burn composite).
    3. Use the Geometry Imports panel in GEE Code Editor to draw points:
       - Add a FeatureCollection import named "burned"   for burned pixels.
       - Add a FeatureCollection import named "unburned" for unburned pixels.
    4. Run the export task to save to the GEE asset.

  Rules for point selection:
    - Burned points: clearly burned areas visible in post-fire imagery.
    - Unburned points: stable non-burned areas with similar vegetation type.
    - Avoid mixed pixels, cloud shadows, and water.
    - Aim for geographic and spectral diversity within the fire perimeter.

  IMPORTANT: this script is a reference/template only. It is not part of
  the collection-01 processing pipeline; it documents the manual data-collection
  procedure used to build the training assets.
*/

// ─── Configuration ───────────────────────────────────────────────────────────
var FIRE_ID = 'fire_01';   // replace NN
var REGION  = 'PAT';       // BA | CHACO | PAMPA | CUYO | PAT

// ─── Load training fires metadata for the pre/post dates ─────────────────────
var TRAINING_FIRES_PATH =
  'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/' + REGION + '/training_fires';

var meta = ee.FeatureCollection(TRAINING_FIRES_PATH)
  .filter(ee.Filter.eq('fire_id', FIRE_ID))
  .first();

var pre_upr  = ee.String(meta.get('pre_upr'));
var post_lwr = ee.String(meta.get('post_lwr'));
var post_upr = ee.String(meta.get('post_upr_long'));

// ─── Visualize pre/post Landsat false-color composites ───────────────────────
var funk = require("users/mapbiomas-arg/fuego:collection-00/utils:functions.js");

var roi = ee.Geometry.BBox(-75, -55, -53, -22);  // Argentina bounding box

var preComposite = funk.getLandsat(roi, pre_upr.slice(0,4).cat('-01-01'), pre_upr, funk.addNBR)
  .median()
  .visualize({bands: ['nir', 'swir1', 'swir2'], min: 0, max: 0.4});

var postComposite = funk.getLandsat(roi, post_lwr, post_upr, funk.addNBR)
  .median()
  .visualize({bands: ['nir', 'swir1', 'swir2'], min: 0, max: 0.4});

Map.addLayer(preComposite,  {}, 'Pre-fire composite');
Map.addLayer(postComposite, {}, 'Post-fire composite (red = burn)');

// ─── Mark point class and export ─────────────────────────────────────────────
// "burned" and "unburned" are FeatureCollection geometry imports drawn in GEE Code Editor

var setClass = function(classLabel) {
  return function(f) { return f.set('class', classLabel); };
};

var allPoints = burned.map(setClass('burned'))
  .merge(unburned.map(setClass('unburned')));

Export.table.toAsset({
  collection: allPoints,
  description: 'training_locations_' + REGION + '_' + FIRE_ID,
  assetId: 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-1/TRAINING-DATA/'
           + REGION + '/training_locations-' + FIRE_ID,
});
