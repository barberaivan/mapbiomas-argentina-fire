/*
  The fire mapping algorithm has 3 main steps:
  
  1) Get a fire-sensitive and interpretable metric at the observation level
     (pixel-date). This implies going from NBR to burn probability. 
     We use tagged data (burned and unburned) to fit a probabilistic classifier 
     (logistic regression).
     
     In each pixel, we get
     NBR time series -> Burn probability time series (observation -date- level).
     
  2) Temporal segmentation of the burn probability time series at the 
     pixel level. The time series is summarized in metrics relevant
     for fire detection (e.g., maximum increase in burn probability,  
     mean burn prob 60 days after the increase, etc.). This metrics are
     fed into a probabilistic classifier which predicts whether a 
     time series for a given year is burned or not.
     
     In each pixel and year, we get
     Burn probability time series (many observations) -> Burn probability (scalar)
     
  3) Spatial segmentation: region growing algorithm.
     From the annual burn probability layers obtained in (2), we define 
     seeds and candidates for the SNIC algorithm.
  
  Steps (1) and (2) require training data. We will collect training locations 
  (burned and unburned) from 20 known fires (or detected by MODIS). From these 
  locations (points), we will extract the NBR time series, which will be used 
  to fit the observation-level model (1) and the time-series-level model (2).
  
  In training_fires, those 20 fires are chosen, along with the date ranges where
  NBR looks burned and unburned. 
  
  In training_locations_**, locations are collected fire by fire, with a script 
  by fire.
     
  Sampling procedure:
  
  01) Choose a fire from the table (link below), and write your name so everyone knows you're 
      working there. Record the time somewhere to know how long it takes to sample.
      Forest fires are IDs 01 to 10; steppe ones go from 11 to 20. The latter are
      much harder.
  02) Work only in the script of the fire you chose, named as
      "training_locations-fire_**", where ** is the fire number 
      as shown in the table (including zeroes before, e.g. "fire_09").
  03) Edit the inputs "fire_id" and "author" (your full name).
  04) Run the code.
      First, learn to distinguish burned and unburned areas using the false-color
      layer post-fire (shows the burn scar) and pre-fire (no scar). 
      You can also see the dNBR, which is specially useful for steppe fires.
      By using the inspector you can visualize the NBR time series of a pixel 
      you click. Burned areas show a drop in the middle year.
  05) Once you feel able to distinguish burned and unburned areas, add points in
      the corresponding geometries, interactively. Get at least 200 points per class.
  06) After sampling, you DO NOT HAVE to export the feature collection.
  08) Record comments and duration of your work in the table.

  Link to the table of fires:
  https://docs.google.com/spreadsheets/d/1ldCKrxR7Q64XxeXr5LWVpZape9flAbrppcHjQ3xxm9E/edit?usp=sharing
  
  Link to detailed instructions:
  https://docs.google.com/presentation/d/1fdXjeh7q-fqbQgsHaloRDQVIeQFRD5nAdWLhZVj-S3I/edit?usp=sharing
*/