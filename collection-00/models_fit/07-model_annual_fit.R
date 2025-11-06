# Fit burn probability model at the annual level

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
    
# Model fit -------------------------------------------------------

mbp_annual <- glm(
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

# Save
saveRDS(mbp_annual, file.path("exports", "model_annual.rds"))

# Reparameterize model by veg type ----------------------------------
# To make coefficients-bands in GEE.

form <- burned ~
  # Probability terms with two-way interactions
  (pmax + pdiff_max + Pmax + Pdiff_max) ^ 2 +
      
  # Previous year fire indices
  (
    nbr_low + nbr_high +
    nbr2_low + nbr2_high + 
    mirbi_low + mirbi_high +
    ndvi_low + ndvi_high
  ) ^ 2

# Refit by veg type [forest, shrubland, steppe]
mv1 <- glm(
  form,
  data = data[data$veg == 1, ], family = "binomial"
)

mv2 <- glm(
  form,
  data = data[data$veg == 2, ], family = "binomial"
)

mv3 <- glm(
  form,
  data = data[data$veg == 3, ], family = "binomial"
)

params <- cbind(coef(mv1), coef(mv2), coef(mv3))
colnames(params) <- veg_levels
params_out <- cbind(
  data.frame(variable = row.names(params)),
  as.data.frame(params)
)

write.table(
  params_out, 
  file.path("exports", "model_annual_coefficients.csv"), 
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
  "var coeffs_annual = {\n",
  paste(js_lines, collapse = ",\n"),
  "\n};\n"
)

# Write to file
writeLines(js_text, file.path("exports", "model_annual_coefficients.js"))