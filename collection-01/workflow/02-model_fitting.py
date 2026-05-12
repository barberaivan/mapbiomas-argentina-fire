"""
collection-01/workflow/02-model_fitting.py

Fit a Random Forest classifier (ee.Classifier.smileRandomForest) per region
and fire-vegetation class using the observation-level training asset from step 01.
Saves each fitted classifier as a GEE asset.

Hyperparameters come from utils/constants.RF_PARAMS, populated after
notebooks/03-rf_hyperparameter_tuning.qmd.

TODO: implement after step 01 assets are validated.
"""
