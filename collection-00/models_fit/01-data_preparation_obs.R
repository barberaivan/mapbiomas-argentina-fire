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

# Subset labelled data (0 and 1)
data <- data_full[data_full$burned < 2, ]

nrow(data)
table(data$burned)
table(data$burned) / sum(table(data$burned))
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
# N points: 12889
length(unique(paste(data$fire_id, data$point_id)))

# N obs: 589154
nrow(data)

# N obs burned: 99414
# N obs unburned: 489740
table(data$burned)

# Total time collecting samples (points):
# 2158 min
# 2158 / 60 = 35.97 h

# Total time collecting fires:
# 306 min = 10.2 * 30
# 306 / 60 = 5.1 h

# Tiempo total dedicado:
# (2158 + 306) / 60 = 41.07 h

# Muestras por hora (incluyendo búsqueda de incendios)
# 12884 / 41.06667 = 313.7337

# Observaciones por hora (incluyendo búsqueda de incendios)
# 593535 / 41.06667 = 14452.96

# Cociente velocidad obs / muestras
# 14452.96 / 313.7337 = 46.0676
# ~46 veces más rápido tomar muestras multitemporales