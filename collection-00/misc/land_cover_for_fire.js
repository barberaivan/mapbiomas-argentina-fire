/*
  Reclassifing land cover to use as a predictor in burn probability models.
  
  The burn probability at the observation level (pixel-date) is defined as a function
  of the observation-level NBR, the vegetation type, and some spectral index 
  informing the productivity ans seasonality of the cell (e.g., cold NBR in 
  previous year).
  
  Here we explore the MapBiomas layer to find a reasonable reclassification.
  We should separate at least woody and non-woody types.
  
  1.1 Bosque Cerrado (ID=3)
  1.2 Arbustal (ID=66) 
  1.3 Leñosas Inundables (ID=6)

  2.1 Pastizales(ID=12) 
  2.2 Humedales (ID=11) 
  2.3 Turberas (ID=75)
  2.4 Estepa (ID=63)
  
  3.1 Mosaico de Usos(ID=21) 
  3.2 Plantaciones Forestales (ID=9)
  
  4.1 Roca alto andina (ID=29)
  4.2 Desiertos y Eriales (ID=25)
  4.2 Areas Urbanas (ID=24)
  
  5.1. Ríos, lago y océano (ID=33)
  5.2 Glaciar / Nieve y hielo (ID=34)
  6   No observado (ID=27)
  
  ----
  
  Clases para fuego:
  1: leñoso
  2: no leñoso
  3: no quemable
  
  En este code está la leyenda final para Patagonia:
  https://code.earthengine.google.com/7a8655b4dcf17e7191ff1fb66aa7fbf9
*/


var funk = require("users/mapbiomas-arg/fuego:functions.js");

// Load MapBiomas image (multi-band: one per year)
var mapbiomas = ee.Image("projects/mapbiomas-argentina/assets/LAND-COVER/COLLECTION-2/GENERAL/CLASSIFICATION/FINAL_CLASSIFICATION/PAT/PAT-INTEGRACION-FINAL-v4");

// Old and new values
var from = [3, 66, 6, 12, 11, 75, 63, 21, 9, 29, 25, 24, 33, 34, 27];
var to   = [1, 4,  1,  2,  2,  2,  2,  2, 1,  3,  3,  3,  3,  3,  3];

// Get all band names
var bnames = mapbiomas.bandNames();

// Reclassify each band
var reclassifiedBands = bnames.map(function(year) {
  var band = mapbiomas.select([year])
    .remap(from, to)
    .rename([year]); // keep the band name
  return band;
});

// Merge all reclassified bands back into one multiband image
var veg = ee.ImageCollection(reclassifiedBands).toBands().rename(bnames);

// Select the correct band
var year = ee.Number(2014);
var bname = ee.String("classification_").cat(year.format());
var fire_land = veg.select(bname);
var landcover = mapbiomas.select(bname);

// Visualize
Map.addLayer(fire_land, {min: 1, max: 4, palette: ['green','orange','black', "lightgreen"]}, "FireLand");
Map.addLayer(landcover.randomVisualizer(), {}, "MapBiomas", false);

// See NBR and NDVI ts
var start = ee.Date.fromYMD(year.add(-1), 01, 01);
var end = ee.Date.fromYMD(year.add(2), 01, 01);
var ts = funk.getLandsat(roi3, start, end, funk.addFireIndices);

Map.addLayer(ts.select("nbr"), {}, "NBR", false);
Map.addLayer(ts.select("nbr2"), {}, "NBR2", false);
Map.addLayer(ts.select("ndvi"), {}, "NDVI", false);
Map.addLayer(ts.select("mirbi"), {}, "MIRBI", false);
Map.addLayer(ts.select("bai"), {}, "BAI", false);
Map.addLayer(ts.select("evi"), {}, "EVI", false);


