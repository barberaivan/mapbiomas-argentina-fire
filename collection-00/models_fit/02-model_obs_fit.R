# Fit burn probability model at the observation level (pixel-date)

# Packages --------------------------------------------------------

library(glm2)

# Functions -------------------------------------------------------

source("functions.R")

# Data ------------------------------------------------------------

data_full <- read.csv(file.path("data", "processed", "data_obs_level.csv"))

# filter obs labelled as burned or unburned (1 and 0)
data <- data_full[data_full$burned < 2, ]

# Model fit -------------------------------------------------------

mbp <- glm2(
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
  data = data,
  family = "binomial",
  control = glm.control(maxit = 100, epsilon = 1e-6)
) 
# takes long.
# Main effects of x_cold and x_d are exchangeable.
# Interaction terms between indices improved AIC.

# Save
saveRDS(mbp, file.path("exports", "model_obs.rds"))

# Reparameterize model by veg type ----------------------------------
# To make coefficient-bands in GEE. [forest, shrubland, steppe]

form <- burned ~
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

mv1 <- glm2(
  form, data = data[data$veg == 1, ], family = "binomial",
  control = glm.control(maxit = 100, epsilon = 1e-6)
)

mv2 <- glm2(
  form, data = data[data$veg == 2, ], family = "binomial",
  control = glm.control(maxit = 100, epsilon = 1e-6)
)

mv3 <- glm2(
  form, data = data[data$veg == 3, ], family = "binomial",
  control = glm.control(maxit = 100, epsilon = 1e-6)
)

params <- cbind(coef(mv1), coef(mv2), coef(mv3))
colnames(params) <- veg_levels
params_out <- cbind(
  data.frame(variable = row.names(params)),
  as.data.frame(params)
)

write.table(
  params_out, 
  file.path("exports", "model_obs_coefficients.csv"), 
  row.names = F, sep = ","
)

# Export as JSON to copy in a constants file in GEE ----------------

params <- cbind(coef(mv1), coef(mv2), coef(mv3))
colnames(params) <- c("forest", "shrubland", "steppe")

# Add variable names
params_out <- cbind(variable = rownames(params), as.data.frame(params))

# Clean variable names for JS
params_out$variable <- params_out$variable |>
  gsub("\\(Intercept\\)", "intercept", x = _) |>  # rename intercept
  gsub(":", "X", x = _) |>                        # replace ':' with 'X'
  gsub("\\.", "_", x = _)                         # replace '.' with '_' (safe JS)

# Build JS-style lines
js_lines <- apply(params_out, 1, function(r) {
  key <- r["variable"]
  vals <- paste(round(as.numeric(r[-1]), 6), collapse = ", ")
  sprintf("  %s: [%s]", key, vals)
})

# Combine lines into a valid JS object
js_text <- paste0(
  "var coeffs_obs = {\n",
  paste(js_lines, collapse = ",\n"),
  "\n};\n"
)

# Write to file
writeLines(js_text, file.path("exports", "model_obs_coefficients.js"))