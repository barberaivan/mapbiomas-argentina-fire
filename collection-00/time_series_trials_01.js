/*
  Mapping burned area using the time series of fire-sensitive 
  variables. 
  
  Input: a full Landsat time series of a target year (calendar or
    fire season), probably including the first months of the following
    year. With at least one fire-sensitive index, like NBR, and the time
    (date) of each observation. 
    
  Features: metrics summarizing the time series, designed to detect changes
    in the fire-sensitive indices related to fire.
    
  Output: probability of each cell being burned during the year, likely as
    a multi-layer image of probabilities, according to different models. 
*/

var funk = require("users/mapbiomas-arg/fuego:functions.js");

var start_all = ee.Date("2013-12-01");
var end_all = ee.Date("2017-12-31");

var landsat_all = funk.getLandsat(roi, start_all, end_all, funk.addNBR)
  .select("nbr");

// Dates for target fire
var pre_lwr = ee.Date("2014-10-25");
var pre_upr = ee.Date("2015-01-30");

var post_lwr1 = ee.Date("2015-03-01");
var post_upr1 = ee.Date("2015-07-01");

var post_lwr2 = ee.Date("2015-07-01");
var post_upr2 = ee.Date("2016-01-01");

// dNBR soon and late
var nbr_pre = landsat_all.filterDate(pre_lwr, pre_upr).median();
var nbr_post1 = landsat_all.filterDate(post_lwr1, post_upr1).median();
var nbr_post2 = landsat_all.filterDate(post_lwr2, post_upr2).median();

var dNBR1 = nbr_pre.subtract(nbr_post1);
var dNBR2 = nbr_pre.subtract(nbr_post2);


// Extract ts metrics -------------------------------------------------

// Function to add fractional year as a band, named "time"
function addFractionalYear(img) {
  var date = img.date();
  var year = ee.Number(date.get('year'));
  var doy = ee.Number(date.getRelative('day', 'year'));  // 0-based
  var begin = ee.Date.fromYMD(year, 01, 01); // get days in year
  var end = begin.advance(1, "year");
  var days_in_year = end.difference(begin, "days");
  var doy_rel = doy.divide(days_in_year);
  var fracYear = year.add(doy_rel); // year + fraction
  var fracImg = ee.Image(fracYear).rename('time').toFloat();
  
  // set property to order images
  return img.addBands(fracImg).set('fracYear', fracYear);
}


// Add date 
var landsat_date = landsat_all.map(addFractionalYear)
  .sort("fracYear");

// Filter focal year
var landsat = landsat_date.filterDate("2014-07-01", "2015-12-31");

// Convert to array image
var arrayImage = landsat.toArray(); // [imageIndex, band]

var arrayImage2 = landsat.toArrayPerBand(0); // [imageIndex, band]

// Takes image collection, where the images have bands "nbr" and "time" (millis)
function ts_features(imcol) {
  
  var arr = imcol.select(["nbr", "time"]).toArray().rename("arr");
  
  // raw time series 
  var nbr0 = arr.select("arr").arraySlice(1, 0, 1).arrayProject([0]);   // [T]
  var tim0 = arr.select("arr").arraySlice(1, 1, 2).arrayProject([0]);   // [T]
  
  // keep useful pixels
  var length = nbr0.arrayLength(0);
  var valid = length.gte(5);  // need at least 5 values
  var nbr = nbr0.updateMask(valid);
  var tim = tim0.updateMask(valid);
  
  // Ordenar por tiempo (por si acaso)
  var sortIdx = tim.arraySort();                      // [T]
  var nbrS = nbr.arraySort(sortIdx);
  var timS = tim.arraySort(sortIdx);

// Differences
var nbrLag  = nbrS.arraySlice(0, 0, -1);
var nbrLead = nbrS.arraySlice(0, 1, null);
var nbr_diff = nbrLead.subtract(nbrLag);  // [T-1]

// Largest drop (minimum value)
var maxDrop = nbr_diff.arrayReduce(ee.Reducer.min(1), [0])
  .arrayGet([0])
  .rename('max_drop');

// Index of largest drop
var idxDrop = nbr_diff.multiply(-1).arrayArgmax()
  .arrayGet([0])
  .int16()
  .rename('idx_drop_scalar');

// Date at that index (scalar index into timS)
var dateDrop = idxDrop.add(1);

// Extract date directly by slicing timS
var tAtDrop = timS.arraySlice(0, dateDrop, dateDrop.add(1))
  .arrayGet([0])
  .rename('date_drop');
  
  
  // Delta NBR as median(pre) - median(post)
  var window = 4; // number of observations before/after

// Define start of pre-window (at least 0)
var preStart = dateDrop.subtract(window).max(ee.Image(0));
var preEnd   = dateDrop;  // slice end is exclusive

// Slice NBR before the drop
var nbrBefore = nbrS.arraySlice(0, preStart, preEnd);

// Define end of post-window (at most length of series)
var postStart = dateDrop.add(1);
var postEnd   = postStart.add(window).min(length);

// Slice NBR after the drop
var nbrAfter = nbrS.arraySlice(0, postStart, postEnd);

// Compute median of each window
var medianBefore = nbrBefore.arrayReduce(ee.Reducer.median(), [0]).arrayGet([0]);
var medianAfter  = nbrAfter.arrayReduce(ee.Reducer.median(), [0]).arrayGet([0]);

// Delta NBR
var dNBR = medianBefore.subtract(medianAfter).rename('dnbr');
// Return multi-band scalar image
return ee.Image.cat([maxDrop, tAtDrop, dNBR])
  .copyProperties(arr, arr.propertyNames());
}

var ts_vars = ee.Image(ts_features(landsat));

// Visualization -------------------------------------------------------

var dnbr_vis = {
  min: -0.5, 
  max: 0.5, 
  palette: ['blue', 'white', 'red']
};

var drop_vis = {
  min: -0.7, 
  max: -0.1, 
  palette: ['orange', 'black']
};

Map.addLayer(landsat_all, {}, "landsat_col", false);
Map.addLayer(dNBR1, dnbr_vis, "dNBR1");
Map.addLayer(dNBR2, dnbr_vis, "dNBR2");

Map.addLayer(arrayImage, {}, "array", false);

Map.addLayer(ts_vars.select("max_drop"), drop_vis, "max drop");
Map.addLayer(ts_vars.select("date_drop"), {}, "date drop");
Map.addLayer(ts_vars.select("dnbr"), {}, "dnbr");