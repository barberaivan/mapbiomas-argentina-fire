# Packages ----------------------------------------------------------

library(glm2)

# Functions ---------------------------------------------------------

source("functions.R")

# Data and constants ------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))

# filter obs labelled as burned or unburned (1 and 0)
data <- data_full[data_full$burned < 2, ]

# Leave-fire-out validation -----------------------------------------

# constants
thresholds <- c(0.01, seq(0.05, 0.95, by = 0.05), 0.99)
nthres <- length(thresholds)
fire_ids <- unique(data$fire_id)
nfires <- length(fire_ids)
nveg <- length(veg_levels)

# large array with errors
# dim1: probability thresholds (thresholds)
# dim2: error metrics = c("omission", "comission", "kappa_error")
# dim3: vegetation type
# dim4: iteration (fire out) = unique(data$fire_id)
errarr <- array(
  NA, 
  dim = c(nthres, 3, nveg, nfires),
  dimnames = list(
    threshold = thresholds,
    metric = c("omission", "comission", "kappa_error"), 
    veg = veg_levels,
    fire_id = fire_ids
  )
)

for (f in 1:nfires) {
  fire_id = fire_ids[f]
  print(fire_id)

  # Split data
  dtrain <- data[data$fire_id != fire_id, ]
  dtest <- data[data$fire_id == fire_id, ]

  # Fit model
  mod <- glm2(
    burned ~ 
      (
        # NBR
        nbr + nbr_low + nbr_high + 
        nbr:nbr_low + nbr:nbr_high + 
        nbr_d:nbr_low + nbr_d:nbr_high +
        
        # NBR2
        nbr2 + nbr2_low + nbr2_high + 
        nbr2:nbr2_low + nbr2:nbr2_high + 
        nbr2_d:nbr2_low + nbr2_d:nbr2_high +
        
        # MIRBI
        mirbi + mirbi_low + mirbi_high + 
        mirbi:mirbi_low + mirbi:mirbi_high + 
        mirbi_d:mirbi_low + mirbi_d:mirbi_high +
        
        # NDVI
        ndvi + ndvi_low + ndvi_high + 
        ndvi:ndvi_low + ndvi:ndvi_high + 
        ndvi_d:ndvi_low + ndvi_d:ndvi_high + 
          
        # Pairwise interactions (focal)
        nbr:nbr2 + nbr:mirbi + nbr:ndvi +
        nbr2:mirbi + nbr2:ndvi +
        mirbi:ndvi +
        
        # Pairwise interactions (delta)
        nbr_d:nbr2_d + nbr_d:mirbi_d + nbr_d:ndvi_d +
        nbr2_d:mirbi_d + nbr2_d:ndvi_d +
        mirbi_d:ndvi_d
      ) * veg_fac,
    data = dtrain,
    family = "binomial",
    control = glm.control(maxit = 100, epsilon = 1e-6)
  )

  # Predict over test data
  p <- predict(mod, dtest, type = "response")
  ys <- sapply(thresholds, function (th) {
    as.numeric(p >= th)
  })
  
  # Loop over thresholds
  for (t in 1:nthres) {
    # Loop over veg types
    for (v in 1:3) {
      rr <- dtest$veg == v
      if (sum(rr) > 0) {
        err <- error_metrics(dtest$burned[rr], ys[rr, t]) 
        errarr[t, , v, f] <- err
      }
    }
  }  
}

saveRDS(errarr, file.path("exports", "model_obs_lfo_error_array.rds"))

# summarize and longanize
summ_fun <- function(x) {
  c(
    "mean" = mean(x, na.rm = T),
    "median" = median(x, na.rm = T),
    "lower" = quantile(x, prob = 0.1, method = 8, na.rm = T),
    "upper" = quantile(x, prob = 0.9, method = 8, na.rm = T)
  ) |> unname()
}

errarr_summ <- apply(errarr, 1:3, summ_fun)
dimnames(errarr_summ) <- list(
  summ = c("mean", "median", "lower", "upper"),
  threshold = thresholds,
  metric = c("omission", "comission", "kappa_error"),
  veg = veg_levels
)

# widenize a bit
arrlong <- as.data.frame.table(errarr_summ, responseName = "value")
errortab <- pivot_wider(
  arrlong, names_from = "summ", values_from = "value"
)
errortab$threshold <- as.numeric(as.character(errortab$threshold))

errplot <-
ggplot(
  errortab, 
  aes(
    threshold, median, ymin = lower, ymax = upper, 
    group = metric, color = metric, fill = metric
  )
) + 
  geom_ribbon(color = NA, alpha = 0.3) + 
  geom_line() +
  facet_wrap(vars(veg)) +
  scale_color_viridis(discrete = T, option = "A", direction = -1, end = 0.8) +
  scale_fill_viridis(discrete = T, option = "A", direction = -1, end = 0.8) +
  xlab("Burn probabiity threshold") + 
  ylab("Classification error") +
  scale_y_continuous(limits = c(0, 1), breaks = seq(0, 1, 0.2)) +
  theme(
    legend.title = element_blank(),
    legend.position = "bottom",
    strip.background = element_rect(fill = "white"),
    panel.grid.minor = element_blank()
  ) +
  nice_theme()

ggsave(
  file.path("exports", "model_obs_cross_validation.png"), errplot, 
  width = 18, height = 9, units = "cm"
)
