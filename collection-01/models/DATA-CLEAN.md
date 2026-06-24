We need to filter observations based on the post-fire burn date, corrected by sight. 

The downloaded data, from the training_observations assets in GEE downloaded the pre- and post-fire periods based on post_upr_long. An exception is the fire_ids 1 to 30 in PAT, which were exported to asset with a longer time span.

So the observations must be filtered again before feeding models. A first hard filter is:

For unburned points:
    use all data between pre_lwr and post_upr_long. if post_upr_long is missing, use post_upr_short.
    These all generate **unburned observations**.

For burned points:
    all observations in the pre-fire period (between pre_lwr and pre_upr, included) are labeled as **unburned**.
    all observations in the post-fire period (between post_lwr and post_upr_long, included) are **initially** labelled as **burned**.

The problem is that many fires have bad post-fire period, so we manually defined which observations to keep or remove there. In a few cases, we also noted removals needed for unburned points, or removing the whole data from a given fire. This manual edits needed by fire are described in the following excel file:

collection-01/data/data_cleaning.xlsx

It has a sheet by region, named. They have the fire_id column, where they are treated like numbers without left-zero (removed the fire_ prefix too). The obs column has instructions about what to do. If not explicitly stated, it always refers to an action needed for the **initially** burned observations: those for burned points in the post-fire period. 

So we need a data cleaning step before 02-models_fit.R. The cleaninig should add a column in the training_observations-REGION csv files indicating whether each observation is used for fitting or not (boolean 'fit' column).

The script doing this cleaning should be in scripts/data_cleaning.R.
There Claude must translate into code the instruction for each fire listed in the sheets. Fires that do not appear in the sheets need no extra handling.
**Important** Claude must tell the user when an instruction is not clear, and ask for guidance.

The model_fit script in workflow/ should first check that the dataset being used has the fit column added. If absent, it should throw an error "The required dataset did not pass the cleaning step; run it in scripts/data_cleaning.R".

Once this is implemented, this process should be documented in the corresponding md in docs/.

The plots should be created again, to check the filtering worked: run scrips/ts_plot_by_fire.R.
