// Years to compute annual summaries of fire indices (low, high)
var startYearSumm = 1998; 
var endYearSumm   = 2025;

// Years range to compute variables which depend on previous year
var startYear = 1999;
var endYear   = 2025;

// name of burn indices
var ind_names = ee.List(['nbr', 'nbr2', 'mirbi', 'ndvi']);

// name of ancillary indices
var anc_names = ee.List(['brightness', 'ndsi']);

// Pilot region of interest
var roi = ee.FeatureCollection('projects/mapbiomas-argentina/assets/FIRE/AUXILIARY_DATA/VECTOR/pilot_study_area')
            .geometry();

// Observation-level burn probability model coefficients.
// Copied from collection-00/models_fit/exports/model_obs_coefficients.js
// "X" indicates interaction terms (products of covariates)
var coeffs_obs = {
  intercept: [2.443044, 36.633336, 42.867916],
  nbr: [-1.176125, -24.565937, -12.654252],
  nbr_low: [-2.038075, -0.100298, 5.528407],
  nbr_high: [-1.507005, 6.90052, 6.908675],
  nbr2: [-38.220437, -135.688518, -187.755613],
  nbr2_low: [4.253466, 19.545896, 64.194893],
  nbr2_high: [11.986093, 21.159345, 20.680531],
  mirbi: [-6.591767, -3.030612, 38.772078],
  mirbi_low: [3.345914, 44.812767, 14.554647],
  mirbi_high: [17.955595, 7.758012, -1.675076],
  ndvi: [-7.625792, 2.136236, -30.072544],
  ndvi_low: [14.777565, 21.402175, 47.900069],
  ndvi_high: [-1.38376, -5.691276, -18.499887],
  nbrXnbr_low: [-0.481026, -49.39064, -22.252251],
  nbrXnbr_high: [26.755295, 36.564112, 18.149935],
  nbr_lowXnbr_d: [18.65208, 22.077173, 37.31922],
  nbr_highXnbr_d: [-0.140568, 13.112801, 1.112679],
  nbr2Xnbr2_low: [5.744593, -42.295323, 39.196301],
  nbr2Xnbr2_high: [-39.362817, -202.141589, -146.016125],
  nbr2_lowXnbr2_d: [20.173122, 139.537228, 231.213628],
  nbr2_highXnbr2_d: [-52.984306, -150.965011, -294.562475],
  mirbiXmirbi_low: [-2.821569, 11.783884, 16.909559],
  mirbiXmirbi_high: [9.844322, 2.880117, -2.933253],
  mirbi_lowXmirbi_d: [0.706911, 18.428344, -3.77818],
  mirbi_highXmirbi_d: [6.197133, -5.246822, -4.37654],
  ndviXndvi_low: [-10.783606, -16.85004, -60.669529],
  ndviXndvi_high: [3.550034, 16.105786, 26.501313],
  ndvi_lowXndvi_d: [-21.986419, 24.82941, -21.86235],
  ndvi_highXndvi_d: [6.564133, -15.110189, -12.852904],
  nbrXnbr2: [18.823133, 132.821178, 104.876102],
  nbrXmirbi: [16.177124, 2.907338, 5.197801],
  nbrXndvi: [-4.631629, -18.826568, -32.448955],
  nbr2Xmirbi: [-20.715533, -69.788475, -62.437832],
  nbr2Xndvi: [3.534876, 78.181418, 109.933314],
  mirbiXndvi: [-0.895843, 11.866238, -3.113444],
  nbr_dXnbr2_d: [-11.755506, -75.678749, -107.259241],
  nbr_dXmirbi_d: [2.279522, 9.515167, 3.631281],
  nbr_dXndvi_d: [9.257225, -1.34884, 4.990263],
  nbr2_dXmirbi_d: [-10.613425, 3.057345, 35.278682],
  nbr2_dXndvi_d: [-21.630229, -85.932549, -52.667039],
  mirbi_dXndvi_d: [7.516508, 2.339998, 5.479024]
};

// Number or raw observations of burn probability from
// neighbouring years to append to focal array.
var M = ee.Number(4);

// Number of observations to compute burn prob median.
var K = ee.Number(5);

// Annual-level burn probability model coefficients.
// Copied from collection-00/models_fit/exports/model_annual_coefficients.js
// "X" indicates interaction terms (products of covariates)
var coeffs_annual = {
  intercept: [12.986781, -12.170663, 43.059434],
  pmax: [31.641039, -14.837419, -57.707323],
  pdiff_max: [37.388353, 33.342909, 33.221271],
  Pmax: [2.660937, 3.040699, 4.243461],
  Pdiff_max: [-44.564994, 9.241259, 51.710544],
  nbr_low: [42.680014, -54.409093, -4.281971],
  nbr_high: [-45.100833, 116.385806, 0.052722],
  nbr2_low: [-55.010202, -75.072874, -139.554957],
  nbr2_high: [-51.21337, -140.491964, -280.950459],
  mirbi_low: [2.6044, -0.883278, 17.715951],
  mirbi_high: [23.800432, 1.946816, 24.603156],
  ndvi_low: [13.379401, 115.435809, -10.554327],
  ndvi_high: [57.23839, -45.936147, 106.052506],
  pmaxXpdiff_max: [17.938024, 34.281414, 21.785901],
  pmaxXPmax: [-31.955269, 10.069079, 49.135686],
  pmaxXPdiff_max: [0.824444, -15.447682, 2.433426],
  pdiff_maxXPmax: [-46.757978, -49.257464, -42.270194],
  pdiff_maxXPdiff_max: [-13.49848, -19.07696, -22.738512],
  PmaxXPdiff_max: [56.42568, 23.803661, -26.816266],
  nbr_lowXnbr_high: [-3.192075, 3.216595, -6.892588],
  nbr_lowXnbr2_low: [-42.072366, 33.880032, 0.497004],
  nbr_lowXnbr2_high: [5.179274, -132.024396, -71.497808],
  nbr_lowXmirbi_low: [23.653675, -30.962335, -15.940774],
  nbr_lowXmirbi_high: [-8.547919, -8.787553, -3.283593],
  nbr_lowXndvi_low: [-13.338463, 12.824367, 8.417573],
  nbr_lowXndvi_high: [-2.845756, 42.988754, 0.40673],
  nbr_highXnbr2_low: [179.484111, -138.264535, -11.808987],
  nbr_highXnbr2_high: [-13.544764, -190.149405, 90.052898],
  nbr_highXmirbi_low: [-43.515327, 40.218239, -12.1831],
  nbr_highXmirbi_high: [38.030562, 18.441056, 24.897582],
  nbr_highXndvi_low: [48.667684, 159.495993, 0.554314],
  nbr_highXndvi_high: [-23.1451, -24.577264, -24.530355],
  nbr2_lowXnbr2_high: [-36.93441, 316.826399, 421.498114],
  nbr2_lowXmirbi_low: [-38.96789, -67.806476, -18.046777],
  nbr2_lowXmirbi_high: [-1.699182, 31.220057, -32.682654],
  nbr2_lowXndvi_low: [39.049556, -145.921288, -101.352477],
  nbr2_lowXndvi_high: [-150.6494, 42.358771, -20.249387],
  nbr2_highXmirbi_low: [-20.048405, -65.611246, -80.839805],
  nbr2_highXmirbi_high: [-21.229379, 24.636238, -78.079494],
  nbr2_highXndvi_low: [-57.281575, 2.341375, 35.706697],
  nbr2_highXndvi_high: [44.735222, 202.090477, -80.03767],
  mirbi_lowXmirbi_high: [2.261067, 0.47404, 9.465524],
  mirbi_lowXndvi_low: [-6.223749, 27.719721, 2.973032],
  mirbi_lowXndvi_high: [52.642022, 4.404663, 46.806123],
  mirbi_highXndvi_low: [1.886125, 14.89702, 10.283635],
  mirbi_highXndvi_high: [-42.758847, -36.822515, 3.212716],
  ndvi_lowXndvi_high: [-35.289104, -160.219312, 37.883526]
};

// -------------------------------------------------------------

exports = {
  roi: roi,
  coeffs_obs: coeffs_obs,
  ind_names: ind_names,
  anc_names: anc_names,
  startYearSumm: startYearSumm, 
  endYearSumm: endYearSumm,
  startYear: startYear,
  endYear: endYear, 
  M: M,
  K: K,
  coeffs_annual: coeffs_annual
};