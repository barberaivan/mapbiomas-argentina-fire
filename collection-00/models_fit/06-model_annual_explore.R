# Fit burn probability models at the annual level. Compare a few
# alternative models

# Functions -------------------------------------------------------

source("functions.R")

# Data ------------------------------------------------------------

data <- read.csv(file.path("data", "processed", "data_annual_level.csv"))
data$veg_fac <- factor(data$veg_fac, levels = veg_levels)
data$burned_fac <- factor(
  as.character(data$burned), 
  levels = as.character(0:1), 
  labels = c("Unburned", "Burned")
)

# Remove problematic data -----------------------------------------

out <- (
  data$fire_id == "fire_18" & data$point_id == 31 |
  data$fire_id == "fire_18" & data$point_id == 96
)

data <- data[!out, ]    
    
# Explore univariate effects --------------------------------------

boxplot(pmax ~ burned, data = data, main = "pmax")
boxplot(pdiff_max ~ burned, data = data, main = "pdiff_max")
boxplot(Pmax ~ burned, data = data, main = "Pmax")
boxplot(Pdiff_max ~ burned, data = data, main = "Pdiff_max")
boxplot(Pdiff_mean ~ burned, data = data, main = "Pdiff_mean")

p_names <- c("pmax", "Pmax", "pdiff_max", "Pdiff_max", "Pdiff_mean")

for (v in 1:3) {
  print(cor(data[data$veg == v, p_names]))
}

fi_names <- c(
  "nbr_low", "nbr_high", 
  "nbr2_low", "nbr2_high", 
  "mirbi_low", "mirbi_high", 
  "ndvi_low", "ndvi_high"
)

for (v in 1:3) {
  print(cor(data[data$veg == v, fi_names]))
}

# Explore models --------------------------------------------------

mp <- glm(
  burned ~ 
    (
      pmax + pdiff_max +
      nbr_low + nbr_high +
      
      pmax : pdiff_max +
      pmax : nbr_low +
      pmax : nbr_high + 
      
      pdiff_max : nbr_low + 
      pdiff_max : nbr_high
    ) * veg_fac,
  data = data, family = "binomial"
)

mP <- glm(
  burned ~ 
    (
      Pmax + Pdiff_max +
      nbr_low + nbr_high +
      
      Pmax : Pdiff_max +
      Pmax : nbr_low +
      Pmax : nbr_high + 
      
      Pdiff_max : nbr_low + 
      Pdiff_max : nbr_high
    ) * veg_fac,
  data = data, family = "binomial"
)

mpP <- glm(
  burned ~ 
    (
      pmax + pdiff_max +
      Pmax + Pdiff_max +
      nbr_low + nbr_high +
      
      pmax : Pmax + 
      pdiff_max : Pdiff_max +
      pmax : Pdiff_max + 
      Pmax : pdiff_max +
        
      pmax : pdiff_max +
      pmax : nbr_low +
      pmax : nbr_high + 
        
      Pmax : Pdiff_max +
      Pmax : nbr_low +
      Pmax : nbr_high + 
      
      pdiff_max : nbr_low + 
      pdiff_max : nbr_high +

      Pdiff_max : nbr_low + 
      Pdiff_max : nbr_high
    ) * veg_fac,
  data = data, family = "binomial"
)

mpPfull <- glm(
  burned ~ 
    (
      # Probability terms with two-way interactions
      (pmax + pdiff_max + Pmax + Pdiff_max) ^ 2 +
      
      # Previous year fire indices
      nbr_low + nbr_high +
      nbr2_low + nbr2_high + 
      mirbi_low + mirbi_high +
      ndvi_low + ndvi_high +
      
      # Interaction terms: probability × fire indices
      pmax : (nbr_low + nbr_high + nbr2_low + nbr2_high + mirbi_low + mirbi_high + ndvi_low + ndvi_high) +
      pdiff_max : (nbr_low + nbr_high + nbr2_low + nbr2_high + mirbi_low + mirbi_high + ndvi_low + ndvi_high) +
      Pmax : (nbr_low + nbr_high + nbr2_low + nbr2_high + mirbi_low + mirbi_high + ndvi_low + ndvi_high) +
      Pdiff_max : (nbr_low + nbr_high + nbr2_low + nbr2_high + mirbi_low + mirbi_high + ndvi_low + ndvi_high)
    ) * veg_fac,
  data = data, family = "binomial"
)

mpP2 <- glm(
  burned ~ 
    (
      # Probability terms with two-way interactions
      (pmax + pdiff_max + Pmax + Pdiff_max) ^ 2 +
      
      # Previous year fire indices
      nbr_low + nbr_high +
      nbr2_low + nbr2_high + 
      mirbi_low + mirbi_high +
      ndvi_low + ndvi_high
    ) * veg_fac,
  data = data, family = "binomial"
)

mpP3 <- glm(
  burned ~ 
    (
      # Probability terms with two-way interactions
      (pmax + pdiff_max + Pmax + Pdiff_max) ^ 2 +
      
      # Previous year fire indices
      (
        nbr_low + nbr_high +
        nbr2_low + nbr2_high + 
        mirbi_low + mirbi_high +
        ndvi_low + ndvi_high
      ) ^ 2
    ) * veg_fac,
  data = data, family = "binomial"
)

AIC(mp); AIC(mP); AIC(mpP); AIC(mpPfull); AIC(mpP2); AIC(mpP3)
length(coef(mpP3))


data$fitted_mpP3 <- fitted(mpP3)
ggplot(
  data, 
  aes(fitted_mpP3, color = burned_fac, fill = burned_fac)
) +
  geom_density(alpha = 0.2) +
  scale_fill_viridis(discrete = T, option = "C", end = 0.7) +
  scale_color_viridis(discrete = T, option = "C", end = 0.7) +
  theme(
    legend.title = element_blank(),
    legend.position = c(0.7, 0.5)
  ) +
  ylab("Density") +
  xlab("Fitted probability")

ggsave(
  file.path("exports", "model_annual_fitted_prob_distribution.png"),
  width = 12, height = 10, units = "cm"
)

par(mfrow = c(2, 1))
plot(
  ecdf(fitted_mpP[data$burned == 1]), main = "Burned",
  xlab = "Fitted probability", ylab = "Cumulative probability"
)
abline(v = c(0.9, 0.95, 0.98), col = 4, lty = 2)

plot(
  ecdf(fitted_mpP[data$burned == 0]), main = "Unburned",
  xlab = "Fitted probability", ylab = "Cumulative probability"
)
abline(v = c(0.02, 0.05, 0.1), col = 4, lty = 2)
par(mfrow = c(1, 1))