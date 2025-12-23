# Functions -------------------------------------------------------

source("functions.R")

# Data ------------------------------------------------------------

# database of training fires
tf <- read.csv(file.path("data", "raw", "training_fires.csv"))
tf$pre_upr <- as.Date(tf$pre_upr, format = "%Y-%m-%d")
tf$post_lwr <- as.Date(tf$post_lwr, format = "%Y-%m-%d")
tf$post_upr_short <- as.Date(tf$post_upr_short, format = "%Y-%m-%d")
tf$post_upr_long <- as.Date(tf$post_upr_long, format = "%Y-%m-%d")

# Prepare data to fit models ---------------------------------------

# land cover and nbr ts file names
land_names <- list.files(file.path("data", "raw"), "landcover")
fi_names <- list.files(file.path("data", "raw"), "fire_indices_")

# fire ids
fire_ids <- sprintf("%02d", 1:30)

# Import and prepare data
data_full_list <- lapply(fire_ids, function(id) {
  print(id)
  dat <- prep_data(id)
  dat <- dat[dat$veg > 0, ]
  print(table(dat$burned))
  return(dat)
}) # has extra values after burn period, to see how models behave

data_full <- do.call(rbind, data_full_list)

# Add delta variables (low - focal)
ind_names <- c("nbr", "nbr2", "mirbi", "ndvi")
n_ind <- length(ind_names)
m <- matrix(NA, nrow(data_full), n_ind)
colnames(m) <- ind_names
for (v in ind_names) {
  lowname <- paste(v, "_low", sep = "")
  m[, v] <- data_full[, lowname] - data_full[, v]
}
m <- as.data.frame(m)
colnames(m) <- paste(ind_names, "_d", sep = "")
data_full <- cbind(data_full, m)

# Cast vegetation type to factor
data_full$veg_fac <- factor(veg_levels[data_full$veg], levels = veg_levels)

write.table(
  data_full, 
  file.path("data", "processed", "data_obs_level.csv"),
  row.names = F, sep = ","
)

# Checks ------------------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))

# Subset labelled data (0 and 1)
data <- data_full[data_full$burned < 2, ]

for (f in unique(data$fire_id)) {
  dsub <- data[data$fire_id == f, ]
  par(mfrow = c(2, 2))
  for (v in ind_names) {
    boxplot(dsub[, v] ~ burned, data = dsub, main = paste(v, f))
  }  
  par(mfrow = c(1, 1))
}

# Data collection info ----------------------------------------------

# N fires: 30
length(unique(paste(data$fire_id, data$point_id)))
# N points: 12889

nrow(data)
# N obs: 589797

# N obs / N points =
# 589797 / 12889 = 45.76

table(data$burned)
# N obs burned: 99414
# N obs unburned: 490383

# Total time collecting samples (points):
# 2158 min
# 2158 / 60 = 35.97 h

# Total time collecting fires:
# 306 min = 10.2 * 30
# 306 / 60 = 5.1 h

# Total time:
# (2158 + 306) / 60 = 41.07 h

# Points / h (including fires search)
# 12884 / 41.06667 = 313.7337

# Observations / h (including fires search)
# 589797 / 41.06667 = 14361.94

# Quotient speed / samples
# 14361.94 / 313.7337 = 45.77749
# multitemporal samples increases speed by a factor of ~45
 
# Points / h
# 12889 / 35.97 = 358.3264

# For 589797 points,
# 589797 / 358.3264 = 1645.977 h collecting points
# With fires search:
# 1645.977+ 5.1 * 0.2 = 1646.997
# 1646.997 / 24 = 68.63 días

# quotient 
# 1646.997 / 41.07