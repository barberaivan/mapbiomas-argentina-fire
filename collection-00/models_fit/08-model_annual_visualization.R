# Functions ---------------------------------------------------------

source("functions.R")

# Data and constants ------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))
data_full$date <- as.Date(data_full$date, format = "%Y-%m-%d")

# filter obs labelled as burned or unburned (1 and 0)
data <- data_full[data_full$burned < 2, ]

data_annual <- read.csv(file.path("data", "processed", "data_annual_level.csv"))
data_annual$veg_fac <- factor(data_annual$veg_fac, levels = veg_levels)

# Load models
mbp <- readRDS(file.path("exports", "model_obs.rds"))
mbp_annual <- readRDS(file.path("exports", "model_annual.rds"))

# Visualize burn prob time series (bpts) -----------------------------
# But now including predicted burn prob, using plot_bpts_fit

plot_bpts_fit(18, 31) # removed problematic point
# 18 31: acá ayudaría considerar estacionalidad.
# no mejoró usando NBR2

plot_bpts_fit(18)

plot_bpts_fit(14, class = "unburned")
