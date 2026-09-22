#!/usr/bin/env Rscript
# collection-01/validation/06_stehman_compute.R
#
# Paso 6 de la validación — corre `mapaccuracy::stehman2014()` (docs/10-validation.md §9) sobre
# el input que arma `05_stehman_export.py` (`outputs/stehman_input_fy<FY>.csv`) y los pesos de
# `01_strata_export.py --weights` (`outputs/strata_weights_fy<FY>.csv`). Excluye las filas
# `uninterpretable == TRUE` (no entran al estimador, se reportan aparte).
#
# Área del píxel: 900 m² (grilla del producto, ~30 m — C.SNIC_TRANSFORM en
# collection-01/utils/constants.py, EPSG:4326, nominal 30 m). Aproximación, no exacta en
# EPSG:4326 lat/lon — consistente con cómo el resto del repo trata esta grilla.
#
# USO
# ---
#   Rscript collection-01/validation/06_stehman_compute.R

suppressPackageStartupMessages(library(mapaccuracy))

PIXEL_AREA_HA <- 900 / 10000  # 30 m x 30 m = 900 m^2 = 0.09 ha
FIRE_YEARS <- c(2003, 2013, 2022)
OUT_DIR <- "collection-01/validation/outputs"  # correr desde la raíz del repo

results <- list()

for (fy in FIRE_YEARS) {
  pts <- read.csv(file.path(OUT_DIR, sprintf("stehman_input_fy%d.csv", fy)))
  w   <- read.csv(file.path(OUT_DIR, sprintf("strata_weights_fy%d.csv", fy)))
  # pandas escribe "True"/"False" (Python), no "TRUE"/"FALSE" (R) — read.csv los deja como string
  pts$uninterpretable <- pts$uninterpretable == "True"

  n_total <- nrow(pts)
  n_uninterp <- sum(pts$uninterpretable)
  usable <- pts[!pts$uninterpretable, ]

  Nh_strata <- setNames(w$n_pixels, as.character(w$stratum))

  e <- stehman2014(
    s = as.character(usable$stratum),
    r = usable$ref_burned,
    m = usable$map_burned,
    Nh_strata = Nh_strata
  )

  z <- qnorm(0.975)
  total_px <- sum(Nh_strata)

  est_area_ha <- e$area["burned"] * total_px * PIXEL_AREA_HA
  est_ci_ha   <- z * e$SEa["burned"] * total_px * PIXEL_AREA_HA
  mapped_area_ha <- unname(w$n_pixels[w$stratum == 1]) * PIXEL_AREA_HA

  cat(sprintf("\n=== fy%d ===\n", fy))
  cat(sprintf("interpretados: %d   no-interpretables (excluidos): %d   usables: %d\n",
              n_total, n_uninterp, nrow(usable)))
  cat(sprintf("usables por estrato: %s\n",
              paste(sprintf("S%s=%d", names(table(usable$stratum)), table(usable$stratum)),
                    collapse = ", ")))
  cat(sprintf("Nh (pixeles) por estrato: %s   (total %s px)\n",
              paste(sprintf("S%s=%s", names(Nh_strata), format(Nh_strata, big.mark = ",")),
                    collapse = ", "),
              format(total_px, big.mark = ",")))
  cat(sprintf("area mapeada (S1, nuestra propia llamada):      %s ha\n",
              format(round(mapped_area_ha), big.mark = ",")))
  cat(sprintf("area estimada (error-adjusted, Stehman 2014):   %s ha  +/- %s ha (IC 95%%)\n",
              format(round(est_area_ha), big.mark = ","), format(round(est_ci_ha), big.mark = ",")))
  cat(sprintf("overall accuracy:  %.4f  (SE %.4f)\n", e$OA, e$SEoa))
  cat(sprintf("user's accuracy (burned):     %.4f  (SE %.4f)\n",
              e$UA["burned"], e$SEua["burned"]))
  cat(sprintf("producer's accuracy (burned): %.4f  (SE %.4f)\n",
              e$PA["burned"], e$SEpa["burned"]))
  cat("matriz de confusion (proporcion de area; filas=mapa, columnas=referencia):\n")
  print(round(e$matrix, 5))

  results[[as.character(fy)]] <- list(
    fire_year = fy, n_total = n_total, n_uninterpretable = n_uninterp, n_usable = nrow(usable),
    Nh_strata = Nh_strata, mapped_area_ha = mapped_area_ha,
    estimated_area_ha = unname(est_area_ha), estimated_area_ci95_ha = unname(est_ci_ha),
    OA = e$OA, SEoa = e$SEoa,
    UA_burned = unname(e$UA["burned"]), SEua_burned = unname(e$SEua["burned"]),
    PA_burned = unname(e$PA["burned"]), SEpa_burned = unname(e$SEpa["burned"])
  )
}

summary_df <- do.call(rbind, lapply(results, function(r) data.frame(
  fire_year = r$fire_year, n_usable = r$n_usable, n_uninterpretable = r$n_uninterpretable,
  mapped_area_ha = round(r$mapped_area_ha), estimated_area_ha = round(r$estimated_area_ha),
  ci95_ha = round(r$estimated_area_ci95_ha),
  OA = round(r$OA, 4), UA_burned = round(r$UA_burned, 4), PA_burned = round(r$PA_burned, 4)
)))
out_csv <- file.path(OUT_DIR, "stehman_results_summary.csv")
write.csv(summary_df, out_csv, row.names = FALSE)
cat(sprintf("\n[escrito] %s\n", out_csv))
