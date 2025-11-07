// Years to compute annual summaries of fire indices (low, high)
var startYearSumm = 1998; 
var endYearSumm   = 2025;

// Years range to compute variables which depend on previous year
var startYear = 1999;
var endYear   = 2025;

// name of burn indices
var ind_names = ee.List(['nbr', 'nbr2', 'mirbi', 'ndvi']);

// Pilot region of interest
var roi = ee.FeatureCollection('projects/mapbiomas-argentina/assets/FIRE/AUXILIARY_DATA/VECTOR/pilot_study_area')
            .geometry();

// Observation-level burn probability model coefficients.
// Copied from collection-00/models_fit/exports/model_obs_coefficients.js
// "X" indicates interaction terms (products of covariates)
var coeffs_obs = {
  intercept: [2.443044, 36.634741, 42.894873],
  nbr: [-1.176125, -24.553033, -12.599637],
  nbr_low: [-2.038075, -0.098726, 5.527255],
  nbr_high: [-1.507005, 6.901637, 6.937125],
  nbr2: [-38.220437, -135.700138, -187.91508],
  nbr2_low: [4.253466, 19.549125, 64.256384],
  nbr2_high: [11.986093, 21.160656, 20.735547],
  mirbi: [-6.591767, -3.025376, 38.791169],
  mirbi_low: [3.345914, 44.799664, 14.508298],
  mirbi_high: [17.955595, 7.763748, -1.619163],
  ndvi: [-7.625792, 2.118677, -30.078641],
  ndvi_low: [14.777565, 21.402839, 47.841464],
  ndvi_high: [-1.38376, -5.692875, -18.530176],
  nbrXnbr_low: [-0.481026, -49.386315, -22.166214],
  nbrXnbr_high: [26.755295, 36.560523, 18.191645],
  nbr_lowXnbr_d: [18.65208, 22.080363, 37.237001],
  nbr_highXnbr_d: [-0.140568, 13.108307, 1.13462],
  nbr2Xnbr2_low: [5.744593, -42.274616, 39.55358],
  nbr2Xnbr2_high: [-39.362817, -202.15334, -146.709788],
  nbr2_lowXnbr2_d: [20.173122, 139.528691, 230.733678],
  nbr2_highXnbr2_d: [-52.984306, -150.974108, -294.745385],
  mirbiXmirbi_low: [-2.821569, 11.779008, 16.890819],
  mirbiXmirbi_high: [9.844322, 2.883425, -2.898376],
  mirbi_lowXmirbi_d: [0.706911, 18.425811, -3.810546],
  mirbi_highXmirbi_d: [6.197133, -5.246466, -4.34515],
  ndviXndvi_low: [-10.783606, -16.859419, -60.45392],
  ndviXndvi_high: [3.550034, 16.107081, 26.557359],
  ndvi_lowXndvi_d: [-21.986419, 24.825491, -21.907598],
  ndvi_highXndvi_d: [6.564133, -15.105243, -12.881441],
  nbrXnbr2: [18.823133, 132.803936, 104.799056],
  nbrXmirbi: [16.177124, 2.914541, 5.176391],
  nbrXndvi: [-4.631629, -18.822216, -32.743726],
  nbr2Xmirbi: [-20.715533, -69.78805, -62.52999],
  nbr2Xndvi: [3.534876, 78.200686, 110.046213],
  mirbiXndvi: [-0.895843, 11.85494, -3.042545],
  nbr_dXnbr2_d: [-11.755506, -75.654166, -107.023794],
  nbr_dXmirbi_d: [2.279522, 9.502961, 3.606056],
  nbr_dXndvi_d: [9.257225, -1.353102, 5.15203],
  nbr2_dXmirbi_d: [-10.613425, 3.064429, 35.409331],
  nbr2_dXndvi_d: [-21.630229, -85.950222, -52.680432],
  mirbi_dXndvi_d: [7.516508, 2.349257, 5.457352]
};

// Number or raw observations of burn probability from
// neighbouring years to append to focal array.
var M = ee.Number(4);

// Number of observations to compute burn prob median.
var K = ee.Number(5);

// -------------------------------------------------------------

exports = {
  years_long: years_long,
  roi: roi,
  coeffs_obs: coeffs_obs,
  ind_names: ind_names,
  startYear: startYear,
  endYear: endYear, 
  M: M,
  K: K
};