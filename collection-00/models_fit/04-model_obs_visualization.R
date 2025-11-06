# Functions ---------------------------------------------------------

source("functions.R")

# Data and constants ------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))
data_full$date <- as.Date(data_full$date, format = "%Y-%m-%d")

# filter obs labelled as burned or unburned (1 and 0)
data <- data_full[data_full$burned < 2, ]

# Load model
mbp <- readRDS(file.path("exports", "model_obs.rds"))

# Visualize model predictions: obs -------------------------------------

plot_bpts(27, 3, cumulative = F, fire_index = "mirbi")

plot_bpts(18, 31, cumulative = F, fire_index = "mirbi")
plot_bpts(18, 31, cumulative = F, fire_index = "nbr2")
# 18-31 not resolved with NBR2, maybe remove. Fast recovery, only one obs
# looks burned more than previous year.

plot_bpts(18, 154, cumulative = F, fire_index = "nbr2")
# NBR looks burned previous winter, but NBR2 does not. It works well here.
# Burn prob is not fooled by NBR.

plot_bpts(18, 164, cumulative = F, fire_index = "nbr")
plot_bpts(18, 164, cumulative = F, fire_index = "nbr2")
plot_bpts(18, 164, cumulative = F, fire_index = "mirbi")
plot_bpts(18, 164, cumulative = F, fire_index = "ndvi")
# NBR and NDVI work better than NBR2 and MIRBI here.

plot_bpts(18, 161, cumulative = F, fire_index = "nbr2")
# burn prob prediction is horrible. Burned in previous year, despite 
# all indices show a strong decline

plot_bpts(18, 96, cumulative = F, fire_index = "nbr")
# Fire is not evident in fire indexes

plot_bpts(18, 55, cumulative = F, fire_index = "nbr")


# Other complicate points:
# 24 58
# Slow decline: fire_02, 158, burned, forest
# fire_05 75 fin de año
# fire_05 49 bajada NBR en primavera