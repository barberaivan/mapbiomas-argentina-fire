/*
  Create a feature collection with a rectangular roi by fire, and the
  dates defining the pre- and post-fire periods.
*/

// Edit this to choose the date range for each fire.
var roi = corcovado_18;
var id = 'fire_30'; // to get dNBR based on dates
var year = ee.Number(2018).toInt();
var startDate = ee.Date.fromYMD(year.add(-2), 07, 01);
var endDate = ee.Date.fromYMD(year.add(1), 07, 01);

Map.centerObject(roi, 12);
// Map.setCenter(large_area);

// Import Landsat imagery ---------------------------------------------------

var funk = require("users/mapbiomas-arg/fuego:functions.js");

var landsat = funk.getLandsat(roi, startDate, endDate, funk.addNBR);

// Impost MODIS burned area -------------------------------------------------

// Inputs for MODIS
var roi = large_area;
var startYear = 2001;   // MCD64A1 starts in 2000/2001 depending on region
var endYear   = 2025;

// Use the latest collection (v6.1). If unavailable in your GEE, switch to 'MODIS/006/MCD64A1'.
var mcd64 = ee.ImageCollection('MODIS/061/MCD64A1')
  .filterBounds(roi)
  .filterDate(ee.Date.fromYMD(startYear,1,1), ee.Date.fromYMD(endYear+1,1,1))
  .select('BurnDate');  // BurnDate > 0 means burned within that month

// Helper: make a 0/1 mask per month where burned
var monthlyBurnMask = mcd64.map(function(img){
  // Any positive BurnDate means burned
  return img.gt(0).selfMask()
    .copyProperties(img, ['system:time_start']);
});

// Aggregate by year: for each year, mark pixels that burned at any month in that year.
var years = ee.List.sequence(startYear, endYear);
var perYearImages = ee.ImageCollection.fromImages(
  years.map(function(y){
    y = ee.Number(y);
    var start = ee.Date.fromYMD(y,1,1);
    var stop  = start.advance(1, 'year');

    // If a pixel burned any month in this year -> set it to that year value
    var burnedThisYear = monthlyBurnMask
      .filterDate(start, stop)
      .max();                     // 1 where burned at least once in the year
    var yearImg = burnedThisYear
      .updateMask(burnedThisYear) // keep only burned pixels
      .multiply(y)                // put the calendar year as the pixel value
      .toInt16()
      .rename('burn_year')
      .set('year', y);
    return yearImg;
  })
);

// First detected burn year (earliest year)
var firstBurnYear = perYearImages.reduce(ee.Reducer.max())  // min year across stack
  .rename('burn_year')
  .clip(roi);

// Optional: Most recent burn year (if pixels reburned)
// var lastBurnYear = perYearImages.reduce(ee.Reducer.max()).rename('burn_year').clip(roi);

// Styling
var vis = {
  min: startYear,
  max: endYear,
  palette: [
    // pick a simple ramp; tweak as you like
    '440154','3b528b','21918c','5ec962','fde725'
  ]
};

// Add to map. Unburned pixels are masked; clicking shows the year.
// Map.centerObject(roi, 8);
Map.addLayer(firstBurnYear, vis, 'MODIS First Burn Year', true);

// MapBiomas classification -------------------------------------------
var vegtype_all = funk.mapBiomasReclass();
var bandName = ee.String('classification_').cat(year.add(-1).format());
var vegtype = vegtype_all.select(bandName);

// Mapbiomas
var vegvis = {
  min: 0,
  max: 3,
  palette: ["black", "green", "lightgreen", "orange"]
};
Map.addLayer(vegtype, vegvis, "Vegetation type " + year.add(-1).getInfo(), false);

// Landsat NBR ts------------------------------------------------------

Map.addLayer(landsat.select("nbr"), {}, "NBR ts", false);

// Feature collection -------------------------------------------------

// Create a feature collection with manually defined fire events
var training_events = ee.FeatureCollection([
  
  // Boscosos ------------------------------------------
  
  ee.Feature(
    cholila,
    {
      'fire_id': 'fire_01',
      'polygon_id': '2015_50',
      'description': 'cholila',

      'pre_upr': '2015-02-14', 
      'post_lwr': '2015-03-10', 
      'post_upr_long': '2015-12-01',
      'post_upr_short': '2015-12-01' 
    } 
  ),
  
  ee.Feature(
    steffen_martin,
    {
      'fire_id': 'fire_02',
      'polygon_id': '2022_2125136700_r',
      'description': 'steffen_martin',

      'pre_upr': '2021-11-30',
      'post_lwr': '2022-02-01',
      'post_upr_long': '2022-12-01',
      'post_upr_short': '2022-12-01'
    }
  ),
  
  ee.Feature(
    turbio_15,
    {
      'fire_id': 'fire_03',
      'polygon_id': '2015_47',
      'description': 'turbio_15',

      'pre_upr': '2015-02-06',
      'post_lwr': '2015-03-02',
      'post_upr_long': '2015-11-30',
      'post_upr_short': '2015-11-30'
    }
  ),

  ee.Feature(
    norquinco_14,
    {
      'fire_id': 'fire_04',
      'polygon_id': '2014_1',
      'description': 'norquinco_14',

      'pre_upr': '2014-01-10',
      'post_lwr': '2014-01-18',
      'post_upr_long': '2014-11-30',
      'post_upr_short': '2014-10-30'
    }
  ),  
  
  ee.Feature(
    tromen_22,
    {
      'fire_id': 'fire_05',
      'polygon_id': '2022_TromenEste',
      'description': 'tromen_22',

      'pre_upr': '2021-12-15',
      'post_lwr': '2021-12-31',
      'post_upr_long': '2022-10-15',
      'post_upr_short': '2022-10-15'
    }
  ),  
  
  ee.Feature(
    comarca_21,
    {
      'fire_id': 'fire_06',
      'polygon_id': '2021_2146405150_W',
      'description': 'comarca_21',

      'pre_upr': '2021-01-25',
      'post_lwr': '2021-02-07',
      'post_upr_long': '2021-11-30',
      'post_upr_short': '2021-10-30'
    }
  ),  
  
  ee.Feature(
    alerces_15,
    {
      'fire_id': 'fire_07',
      'polygon_id': '2015_53',
      'description': 'alerces_15',

      'pre_upr': '2015-03-18',
      'post_lwr': '2015-03-26',
      'post_upr_long': '2015-12-31',
      'post_upr_short': '2015-12-31'
    }
  ),  
  
  ee.Feature(
    alerces_24,
    {
      'fire_id': 'fire_08',
      'polygon_id': '2024_2143416051',
      'description': 'alerces_24',

      'pre_upr': '2024-01-22',
      'post_lwr': '2024-02-07',
      'post_upr_long': '2024-12-31',
      'post_upr_short': '2024-10-31'
    }
  ),
  
  ee.Feature(
    lolog_08,
    {
      'fire_id': 'fire_09',
      'polygon_id': '2008_5',
      'description': 'lolog_08',

      'pre_upr': '2008-02-27',
      'post_lwr': '2008-04-05',
      'post_upr_long': '2008-12-31',
      'post_upr_short': '2008-10-31'
    }
  ),
  
  ee.Feature(
    patriada_12,
    {
      'fire_id': 'fire_10',
      'polygon_id': '2012_57-2012_58',
      'description': 'patriada_12',

      'pre_upr': '2011-12-31',
      'post_lwr': '2012-01-07',
      'post_upr_long': '2012-12-31',
      'post_upr_short': '2012-10-31'
    }
  ),

  // Esteparios -----------------------------------
  
  ee.Feature(
    comarca_estepa_21,
    {
      'fire_id': 'fire_11',
      'polygon_id': '2021_2146405150_E',
      'description': 'comarca_estepa_21',

      'pre_upr': '2021-01-31',
      'post_lwr': '2021-03-15',
      'post_upr_long': '2021-12-01',
      'post_upr_short': '2021-12-01'
    }
  ),
  
  ee.Feature(
    la_negra_01,
    {
      'fire_id': 'fire_12',
      'polygon_id': null,
      'description': 'la_negra_01',
      
      'pre_upr': '2001-02-16',
      'post_lwr': '2001-02-23',
      'post_upr_long': '2001-05-31',
      'post_upr_short': '2001-03-31'
    }
  ),
  
  ee.Feature(
    coquelen_03,
    {
      'fire_id': 'fire_13',
      'polygon_id': null,
      'description': 'coquelen_03',

      'pre_upr': '2003-02-13',
      'post_lwr': '2003-02-22',
      'post_upr_long': '2003-05-31',
      'post_upr_short': '2003-05-31'
    }
  ),
  
  ee.Feature(
    montenegro_24,
    {
      'fire_id': 'fire_14',
      'polygon_id': null,
      'description': 'montenegro_24',

      'pre_upr': '2024-02-16',
      'post_lwr': '2024-03-03',
      'post_upr_long': '2024-04-30',
      'post_upr_short': '2024-04-30'
    }
  ),

  ee.Feature(
    lonco_vaca_16,
    {
      'fire_id': 'fire_15',
      'polygon_id': null,
      'description': 'lonco_vaca_16',

      'pre_upr': '2015-12-17',
      'post_lwr': '2016-01-02',
      'post_upr_long': '2016-03-21',
      'post_upr_short': '2016-02-28'
    }
  ),
  
  ee.Feature(
    naupa_huen_02,
    {
      'fire_id': 'fire_16',
      'polygon_id': null,
      'description': 'naupa_huen_02',

      'pre_upr': '2001-12-25',
      'post_lwr': '2002-01-18',
      'post_upr_long': '2002-03-31',
      'post_upr_short': '2002-03-31'
    }
  ),
  
  ee.Feature(
    achico_16,
    {
      'fire_id': 'fire_17',
      'polygon_id': null,
      'description': 'achico_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-09',
      'post_upr_long': '2016-04-30',
      'post_upr_short': '2016-04-14'
    }
  ),
  
  ee.Feature(
    sanico_16,
    {
      'fire_id': 'fire_18',
      'polygon_id': null,
      'description': 'sanico_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-09',
      'post_upr_long': '2016-04-21',
      'post_upr_short': '2016-04-21'
    }
  ),
  
  ee.Feature(
    piedra_pintada_16,
    {
      'fire_id': 'fire_19',
      'polygon_id': null,
      'description': 'piedra_pintada_16',

      'pre_upr': '2015-12-31',
      'post_lwr': '2016-01-17',
      'post_upr_long': '2016-05-31',
      'post_upr_short': '2016-04-21'
    }
  ),
  
  ee.Feature(
    trevelin_19,
    {
      'fire_id': 'fire_20',
      'polygon_id': null,
      'description': 'trevelin_19',

      'pre_upr': '2019-02-17',
      'post_lwr': '2019-02-18',
      'post_upr_long': '2019-05-24',
      'post_upr_short': '2019-05-24'
    }
  ),
  
  // First export did not include the following:
  // Esteparios [21-25] --------------------------------
  
  ee.Feature(
    gualjaina_17,
    {
      'fire_id': 'fire_21',
      'polygon_id': null,
      'description': 'gualjaina_17',

      'pre_upr': '2017-01-27',
      'post_lwr': '2017-02-20',
      'post_upr_long': '2017-03-30',
      'post_upr_short': '2017-03-30'
    }
  ),
  
  ee.Feature(
    costa_del_lepa_04,
    {
      'fire_id': 'fire_22',
      'polygon_id': null,
      'description': 'costa_del_lepa_04',

      'pre_upr': '2004-02-01',
      'post_lwr': '2004-02-17',
      'post_upr_long': '2004-03-30',
      'post_upr_short': '2004-03-30'
    }
  ),
  
  ee.Feature(
    quetrequile_16,
    {
      'fire_id': 'fire_23',
      'polygon_id': null,
      'description': 'quetrequile_16',

      'pre_upr': '2016-02-02',
      'post_lwr': '2016-02-10',
      'post_upr_long': '2016-06-30',
      'post_upr_short': '2016-03-30'
    }
  ),
  
  ee.Feature(
    jacobacci_18,
    {
      'fire_id': 'fire_24',
      'polygon_id': null,
      'description': 'jacobacci_18',

      'pre_upr': '2018-01-30',
      'post_lwr': '2018-02-07',
      'post_upr_long': '2018-06-30',
      'post_upr_short': '2018-03-30'
    }
  ),
  
  
  ee.Feature(
    necolman_05,
    {
      'fire_id': 'fire_25',
      'polygon_id': null,
      'description': 'necolman_05',

      'pre_upr': '2005-01-17',
      'post_lwr': '2005-01-18',
      'post_upr_long': '2005-06-30',
      'post_upr_short': '2005-03-30'
    }
  ),
  
  // Boscosos [26-30] --------------------------------------
  
  ee.Feature(
    foyel_02,
    {
      'fire_id': 'fire_26',
      'polygon_id': '2002_19',
      'description': 'foyel_02',

      'pre_upr': '2002-02-12',
      'post_lwr': '2002-02-17',
      'post_upr_long': '2002-12-30',
      'post_upr_short': '2002-03-30'
    }
  ),
  
  ee.Feature(
    foyel_00,
    {
      'fire_id': 'fire_27',
      'polygon_id': '2000_31j',
      'description': 'foyel_00',

      'pre_upr': '1999-10-18',
      'post_lwr': '1999-10-22',
      'post_upr_long': '2000-10-30',
      'post_upr_short': '2000-03-30'
    }
  ),
  
  ee.Feature(
    guacho_21,
    {
      'fire_id': 'fire_28',
      'polygon_id': '2021_1229',
      'description': 'guacho_21',

      'pre_upr': '2021-02-25',
      'post_lwr': '2021-03-05',
      'post_upr_long': '2021-12-30',
      'post_upr_short': '2021-04-30'
    }
  ),
  
  ee.Feature(
    nahuel_huapi_15,
    {
      'fire_id': 'fire_29',
      'polygon_id': '2015_16',
      'description': 'nahuel_huapi_15',

      'pre_upr': '2015-01-04',
      'post_lwr': '2015-01-08',
      'post_upr_long': '2015-12-30',
      'post_upr_short': '2015-06-30'
    }
  ),
  
  ee.Feature(
    corcovado_18,
    {
      'fire_id': 'fire_30',
      'polygon_id': '2018_44',
      'description': 'corcovado_18',

      'pre_upr': '2017-11-29',
      'post_lwr': '2017-12-02',
      'post_upr_long': '2018-12-30',
      'post_upr_short': '2018-04-30'
    }
  )
]);

Map.addLayer(training_events, {}, "events", false);

// Visualize landsat dNBR using focal dates ---------------------------

var feat = training_events.filterMetadata("fire_id", "equals", id).first();
var pre = landsat.filterDate(
    ee.Date(feat.get("pre_upr")).advance(-3, "month"),
    ee.Date(feat.get("pre_upr")).advance(1, "day")
  ).median();
  
var post_long = landsat.filterDate(
    feat.get("post_lwr"),
    feat.get("post_upr_long")
  ).median();
  
var post_short = landsat.filterDate(
    feat.get("post_lwr"),
    feat.get("post_upr_short")
  ).median();

var dnbr_long = pre.select("nbr").subtract(post_long.select("nbr"));
var dnbr_short = pre.select("nbr").subtract(post_short.select("nbr"));
var dnbr_vis = {
  min: -0.3,
  max: 0.3,
  palette: ["blue", "white", "red"]
};
Map.addLayer(dnbr_long, dnbr_vis, "dNBR long");
Map.addLayer(dnbr_short, dnbr_vis, "dNBR short");

// Fires Barbera 25 ---------------------------------------------------

Map.addLayer(fires_barbera, {color: "red"}, "fires barbera", false);
// Map.addLayer(fires_barbera.filterMetadata("year", "equals", 2012), {color: "red"}, "fires barbera", false);

// Exports ----------------------------------------------------------------

// // Asset
// Export.table.toAsset({
//   collection: training_events,
//   description: 'events_export',
//   assetId: 'projects/mapbiomas-argentina/assets/FIRE/COLLECTION-0/TRAINING-DATA/training_fires'
// });
// // Table for Drive
// Export.table.toDrive({
//   collection: training_events,
//   description: 'training_fires',
//   folder: 'earth_engine_exports',
//   fileFormat: 'CSV'
// });