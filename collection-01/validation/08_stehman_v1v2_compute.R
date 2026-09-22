#!/usr/bin/env Rscript
# collection-01/validation/08_stehman_v1v2_compute.R
#
# `stehman2014()` (mapaccuracy) corrido POR SEPARADO para v1 y v2 (el post-procesado
# FINAL_PRODUCTS de cada versión, ver docstring de 07_stehman_v1v2_compare.py), sobre el mismo
# input de `06_stehman_compute.R` pero con `map_burned_v1`/`map_burned_v2` en vez de la columna
# `map_burned` cruda (`outputs/stehman_input_v1v2_fy<FY>.csv`, paso 7).
#
# Pedido de Iván (WhatsApp, 2026-09-21): la versión Stehman-ponderada (área ajustada, OA/UA/PA
# con su varianza de diseño) para comparar v1 vs v2, en vez del hit-rate simple por estrato de
# `stratum_accuracy_v1_v2.csv`. NO pooled entre años-fuego — cada año tiene su propio `Nh`/área.
#
# `Nh_strata` sale de `outputs/strata_weights_fy<FY>.csv` (paso 1, `--weights`) — es el mismo
# censo de píxeles para las dos versiones, el estrato no cambió, sólo la llamada del mapa.
#
# USO
# ---
#   Rscript collection-01/validation/08_stehman_v1v2_compute.R

suppressPackageStartupMessages(library(mapaccuracy))

PIXEL_AREA_HA <- 900 / 10000  # 30 m x 30 m = 900 m^2 = 0.09 ha — ver 06_stehman_compute.R
FIRE_YEARS <- c(2003, 2013, 2022)
VERSIONS <- c("v1", "v2")
OUT_DIR <- "collection-01/validation/outputs"  # correr desde la raíz del repo

results <- list()

for (fy in FIRE_YEARS) {
  pts <- read.csv(file.path(OUT_DIR, sprintf("stehman_input_v1v2_fy%d.csv", fy)))
  w   <- read.csv(file.path(OUT_DIR, sprintf("strata_weights_fy%d.csv", fy)))
  Nh_strata <- setNames(w$n_pixels, as.character(w$stratum))
  total_px <- sum(Nh_strata)
  z <- qnorm(0.975)

  for (ver in VERSIONS) {
    e <- stehman2014(
      s = as.character(pts$stratum),
      r = pts$ref_burned,
      m = pts[[sprintf("map_burned_%s", ver)]],
      Nh_strata = Nh_strata
    )

    est_area_ha <- e$area["burned"] * total_px * PIXEL_AREA_HA
    est_ci_ha   <- z * e$SEa["burned"] * total_px * PIXEL_AREA_HA

    cat(sprintf("\n=== fy%d — %s ===\n", fy, ver))
    cat(sprintf("n usable: %d\n", nrow(pts)))
    cat(sprintf("area estimada (error-adjusted, Stehman 2014): %s ha +/- %s ha (IC 95%%)\n",
                format(round(est_area_ha), big.mark = ","), format(round(est_ci_ha), big.mark = ",")))
    cat(sprintf("overall accuracy:  %.4f  (SE %.4f)\n", e$OA, e$SEoa))
    cat(sprintf("user's accuracy (burned):     %.4f  (SE %.4f)\n",
                e$UA["burned"], e$SEua["burned"]))
    cat(sprintf("producer's accuracy (burned): %.4f  (SE %.4f)\n",
                e$PA["burned"], e$SEpa["burned"]))

    results[[paste(fy, ver)]] <- data.frame(
      fire_year = fy, version = ver, n_usable = nrow(pts),
      estimated_area_ha = round(unname(est_area_ha)),
      ci95_ha = round(unname(est_ci_ha)),
      OA = round(e$OA, 4), SEoa = round(e$SEoa, 4),
      UA_burned = round(unname(e$UA["burned"]), 4), SEua_burned = round(unname(e$SEua["burned"]), 4),
      PA_burned = round(unname(e$PA["burned"]), 4), SEpa_burned = round(unname(e$SEpa["burned"]), 4)
    )
  }
}

summary_df <- do.call(rbind, results)
out_csv <- file.path(OUT_DIR, "stehman_results_summary_v1_v2.csv")
write.csv(summary_df, out_csv, row.names = FALSE)
cat(sprintf("\n[escrito] %s\n", out_csv))
