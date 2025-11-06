# Functions -------------------------------------------------------

source("functions.R")

# Data and constants ------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))
data_full$date <- as.Date(data_full$date, format = "%Y-%m-%d")

# filter obs labelled as burned or unburned (1 and 0)
data <- data_full[data_full$burned < 2, ]

# Load bp model at obs level
mbp <- readRDS(file.path("exports", "model_obs.rds"))

# database of training fires
tf <- read.csv(file.path("data", "raw", "training_fires.csv"))
tf$pre_upr <- as.Date(tf$pre_upr, format = "%Y-%m-%d")
tf$post_lwr <- as.Date(tf$post_lwr, format = "%Y-%m-%d")
tf$post_upr_short <- as.Date(tf$post_upr_short, format = "%Y-%m-%d")
tf$post_upr_long <- as.Date(tf$post_upr_long, format = "%Y-%m-%d")

# Make data at annual level ------------------------------------------

fire_ids <- tf$fire_id

data_annual_list <- vector("list", length(fire_ids))
names(data_annual_list) <- fire_ids

for (fid in fire_ids) {
  # fid = "fire_10"
  message(fid)
  point_ids <- unique(data_full$point_id[data_full$fire_id == fid])
  np <- length(point_ids)

  ll <- vector("list", np)
  for (p in seq_len(np)) {
    message(point_ids[p])
    ll[[p]] <- prep_annual_point(fid, point_ids[p])
  }

  # Remove NULL elements
  ll <- ll[!sapply(ll, is.null)]

  # Combine into a single data frame
  one_fire <- do.call(rbind, ll)
  row.names(one_fire) <- NULL

  # Check nulls
  print(paste("non-null:", np))
  print(paste("null:", np - length(ll)))
  
  data_annual_list[[fid]] <- one_fire
}

data_annual <- do.call(rbind, data_annual_list)

# write
write.table(
  data_annual, 
  file.path("data", "processed", "data_annual_level.csv"),
  row.names = F, sep = ","
)

nrow(data_annual) 
# 38047 obs

table(data_annual$burned) / sum(table(data_annual$burned))
# unburned  burned 
# 0.7969354 0.2030646 
