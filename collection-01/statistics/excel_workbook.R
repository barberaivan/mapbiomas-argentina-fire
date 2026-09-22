#!/usr/bin/env Rscript
# =============================================================================
# collection-01/statistics/excel_workbook.R  —  THE PUBLISHED xlsx
#
# Builds `mapbiomas-arg-fire-stats.xlsx`, the table workbook published on the
# MapBiomas web page alongside the maps. One sheet per topic, all of them in
# SPANISH with legible column names and a cell comment on every header
# explaining what the column is — the audience is an Excel user, not a script.
#
# It reads only the tables `factsheet_tables.R` and `fire_counts.R` already
# wrote (statistics/docs/statistics.md §5.1) and reshapes them for a human
# reading a spreadsheet: no year filter is dropped, no region is left out just
# because the factsheet's figures only show a handful. See
# statistics/docs/statistics.md "## Excel table for the web page" for what
# each sheet is and why; doubts and decisions made without Iván are in
# statistics/NOTES_FOR_IVAN_TABLES.txt.
#
# Usage (from the repo ROOT, after factsheet_tables.R and fire_counts.R):
#   Rscript collection-01/statistics/excel_workbook.R
# =============================================================================

suppressPackageStartupMessages({
  library(data.table)
  library(openxlsx)
})

DIR      <- "collection-01/data/statistics"
OUT_XLSX <- file.path(DIR, "mapbiomas-arg-fire-stats.xlsx")
NAT      <- "Argentina"

rd  <- function(f) fread(file.path(DIR, f), encoding = "UTF-8")
msg <- function(...) cat(sprintf(...), "\n", sep = "")

# ── ecoregion order for every sheet: Argentina first, then north -> south ────
# `palette_order` is the same north-warm/south-cool order the factsheet map
# legend uses (factsheet_style.R), so a reader who has seen the factsheet finds
# the regions in the order they expect. Islas del Atlántico Sur is not in any
# source table (statistics.md §3.2, mapping gap) and so is silently absent here
# too — never reported as "0 % quemado".
meta <- rd("ecoregions13_meta.csv")
ORDEN <- rbind(data.table(ecoregion = NAT, orden = 0L),
               meta[, .(ecoregion, orden = palette_order)])

# =============================================================================
# helpers to write one sheet: data + Spanish headers + a comment per header
# =============================================================================
write_sheet <- function(wb, sheet, df, comments, widths = NULL) {
  addWorksheet(wb, sheet)
  writeData(wb, sheet, df, headerStyle = createStyle(textDecoration = "bold",
                                                      fgFill = "#E8EEF2", wrapText = TRUE))
  for (j in seq_along(names(df))) {
    cn <- names(df)[j]
    stopifnot("falta comentario para columna" = cn %in% names(comments))
    writeComment(wb, sheet, col = j, row = 1,
                 comment = createComment(comments[[cn]], author = "MapBiomas Fuego Argentina",
                                         width = 3, height = 6, visible = FALSE))
  }
  setColWidths(wb, sheet, cols = seq_along(names(df)),
               widths = if (is.null(widths)) "auto" else widths)
  freezePane(wb, sheet, firstRow = TRUE)
  df
}

wb <- createWorkbook()

# =============================================================================
# 1. Área quemada por ecorregión y año — NO está en el factsheet como tabla:
#    las figuras del factsheet muestran esto en gráficos, para 5 regiones nada
#    más (Argentina + 4). Acá van las 12 ecorregiones + el total nacional,
#    los 27 años, con el área quemable (constante) y el % quemado al lado.
# =============================================================================
ann <- rd("factsheet_annual.csv")
s1 <- ann[, .(ecoregion, year,
              `Área quemada (ha)`      = round(burned_ha, 1),
              `Área quemada (Mha)`     = round(burned_ha / 1e6, 4),
              `Área quemable (ha)`     = round(burnable_ha, 1),
              `Porcentaje quemado (%)` = round(pct, 3))]
s1 <- merge(s1, ORDEN, by = "ecoregion")
setorder(s1, orden, year)
setnames(s1, "ecoregion", "Ecorregión")
setnames(s1, "year", "Año")
s1[, orden := NULL]
setcolorder(s1, c("Año", "Ecorregión", "Área quemada (ha)", "Área quemada (Mha)",
                  "Área quemable (ha)", "Porcentaje quemado (%)"))

write_sheet(wb, "Área quemada por ecorregión", s1, widths = c(8, 26, 16, 14, 16, 18), comments = list(
  "Año" =
    "Año CALENDARIO (enero a diciembre), no año de fuego. La serie completa es 1999-2025, 27 años.",
  "Ecorregión" =
    "Una de las 12 ecorregiones de Burkart et al. (1999) que el producto mapea, o 'Argentina' (el total nacional, la suma de las 12). No incluye Islas del Atlántico Sur: la grilla de mapeo no llega a esa región (no es que no se haya quemado, es que no se pudo observar), así que reportar un 0 ahí sería mostrar un agujero del mapa como un hecho sobre el fuego.",
  "Área quemada (ha)" =
    "Hectáreas quemadas ese año en esa ecorregión. Sale de los mapas anuales de área quemada, agregados por ecorregión.",
  "Área quemada (Mha)" =
    "La misma columna anterior, en millones de hectáreas (Mha = 1.000.000 ha), para números más cómodos de leer y comparar.",
  "Área quemable (ha)" =
    "Área que PUEDE arder en esa ecorregión (excluye agua, ciudad, glaciar, roca, etc.). Es una sola cifra CONSTANTE por ecorregión -no cambia año a año-, calculada una sola vez sobre 1998-2024: por eso se repite igual en las 27 filas de cada ecorregión.",
  "Porcentaje quemado (%)" =
    "Área quemada dividido área quemable, x100. Como el área quemable es constante y no la del año, un valor por encima del promedio histórico de esa ecorregión es un año de fuego más intenso que lo usual, no un cambio en cuánto territorio puede arder."
))
msg("[hoja 1] Área quemada por ecorregión: %d filas", nrow(s1))

# =============================================================================
# 2. Tendencia del área quemada — la curva suavizada (GAM) de la figura de
#    series del factsheet, pero para las 12 ecorregiones (el factsheet sólo
#    grafica Argentina + 4). Un valor por año entero, no la grilla fina que
#    usa el gráfico.
# =============================================================================
trend <- rd("factsheet_trend_fits.csv")
tr <- trend[abs(year - round(year)) < 1e-6]
tr[, year := round(year)]
bha <- unique(ann[, .(ecoregion, burnable_ha)])
tr <- merge(tr, bha, by = "ecoregion")
# Un % de área quemada negativo no existe, así que TODO lo negativo se acota
# en cero -no sólo el límite inferior en Mha, también el propio % (`lo` puede
# dar negativo en años de tendencia muy plana; es un límite estadístico del
# GAM, no un dato real, y mostrarlo negativo confunde más de lo que aclara).
s2 <- tr[, .(ecoregion, year,
             `Tendencia del % quemado`            = round(pmax(0, fit), 3),
             `Tendencia del área quemada (Mha)`    = round(pmax(0, fit) / 100 * burnable_ha / 1e6, 4),
             `Límite inferior del % quemado`       = round(pmax(0, lo), 3),
             `Límite superior del % quemado`       = round(pmax(0, hi), 3),
             `Límite inferior del área quemada (Mha)` = round(pmax(0, lo) / 100 * burnable_ha / 1e6, 4),
             `Límite superior del área quemada (Mha)` = round(pmax(0, hi) / 100 * burnable_ha / 1e6, 4))]
s2 <- merge(s2, ORDEN, by = "ecoregion")
setorder(s2, orden, year)
setnames(s2, "ecoregion", "Ecorregión"); setnames(s2, "year", "Año")
s2[, orden := NULL]
setcolorder(s2, c("Año", "Ecorregión", "Tendencia del % quemado",
                  "Tendencia del área quemada (Mha)", "Límite inferior del % quemado",
                  "Límite superior del % quemado", "Límite inferior del área quemada (Mha)",
                  "Límite superior del área quemada (Mha)"))

write_sheet(wb, "Tendencia del área quemada", s2, widths = c(8, 26, 16, 18, 16, 16, 20, 20),
            comments = list(
  "Año" = "Año calendario. La tendencia está ajustada sobre toda la serie 1999-2025 y evaluada acá en cada año entero.",
  "Ecorregión" = "Igual que en la hoja anterior: las 12 ecorregiones mapeadas más 'Argentina' (total nacional).",
  "Tendencia del % quemado" =
    "El VALOR SUAVIZADO (no el dato real de ese año) de qué % del área quemable ardió, de un modelo estadístico (GAM) ajustado a toda la serie. Sirve para ver la forma de fondo -sube, baja, se mantiene- sin el ruido de un año particular. El dato real año a año está en la hoja 'Área quemada por ecorregión'.",
  "Tendencia del área quemada (Mha)" =
    "La misma tendencia, convertida a millones de hectáreas multiplicando el % por el área quemable (constante) de esa ecorregión.",
  "Límite inferior del % quemado" =
    "El extremo inferior del intervalo de confianza del 95% de la tendencia, ACOTADO EN CERO: el modelo estadístico (GAM) puede devolver un valor negativo cerca de años con pocos datos o tendencia muy plana, pero un % de área quemada negativo no existe, así que ese negativo se muestra como 0.",
  "Límite superior del % quemado" =
    "El extremo superior del intervalo de confianza del 95% de la tendencia.",
  "Límite inferior del área quemada (Mha)" =
    "El límite inferior de arriba, convertido a Mha y ACOTADO EN CERO (un % negativo no tiene una superficie equivalente).",
  "Límite superior del área quemada (Mha)" =
    "El límite superior de arriba, convertido a Mha."
))
msg("[hoja 2] Tendencia del área quemada: %d filas", nrow(s2))

# =============================================================================
# 3. Distribución intraanual (pirograma) — en qué meses ocurre el fuego, para
#    las 12 ecorregiones + Argentina (el factsheet sólo grafica 4 + el país).
#    Promedios anuales sobre los 27 años ("un mes típico"), como en el
#    factsheet.
# =============================================================================
piro <- rd("factsheet_pirogram.csv")
s3 <- piro[, .(ecoregion, month, month_name, month_fy,
               `Área quemada, promedio anual (ha)`  = round(burned_ha, 1),
               `Área quemada, promedio anual (Mha)` = round(burned_ha / 1e6, 5),
               `Porcentaje del área quemable (%)`   = round(pct, 4),
               `Incendios totales, promedio anual`     = round(n_fires, 2),
               `Incendios ≥ 10 ha, promedio anual`     = round(n_ge10, 2),
               `Incendios ≥ 100 ha, promedio anual`    = round(n_ge100, 2),
               `Porcentaje del área quemada anual de la ecorregión (%)`  = round(share_area, 3),
               `Porcentaje de los incendios anuales de la ecorregión (%)` = round(share_fires, 3),
               `Incendios ≥ 10 ha cada 10.000 km²` = round(dens_ge10_10kkm2, 3))]
s3 <- merge(s3, ORDEN, by = "ecoregion")
setorder(s3, orden, month)
setnames(s3, c("ecoregion", "month", "month_name", "month_fy"),
         c("Ecorregión", "Mes (número, 1 = enero)", "Mes", "Orden mayo→abril (1 = mayo, 12 = abril)"))
s3[, orden := NULL]
setcolorder(s3, c("Ecorregión", "Mes (número, 1 = enero)", "Mes",
                  "Orden mayo→abril (1 = mayo, 12 = abril)",
                  "Área quemada, promedio anual (ha)", "Área quemada, promedio anual (Mha)",
                  "Porcentaje del área quemable (%)", "Incendios totales, promedio anual",
                  "Incendios ≥ 10 ha, promedio anual", "Incendios ≥ 100 ha, promedio anual",
                  "Porcentaje del área quemada anual de la ecorregión (%)",
                  "Porcentaje de los incendios anuales de la ecorregión (%)",
                  "Incendios ≥ 10 ha cada 10.000 km²"))

write_sheet(wb, "Distribución intraanual", s3, widths = c(26, 12, 8, 18, 16, 16, 14, 14, 14, 14, 16, 16, 16),
            comments = list(
  "Ecorregión" = "Las 12 ecorregiones mapeadas + 'Argentina' (total nacional).",
  "Mes (número, 1 = enero)" = "El mes calendario, 1 a 12.",
  "Mes" = "Nombre abreviado del mes calendario (Ene, Feb, ...).",
  "Orden mayo→abril (1 = mayo, 12 = abril)" =
    "Sólo para ORDENAR el mes en un gráfico de 'año de fuego' (1 de mayo a 30 de abril), que es como se arma el pirograma del factsheet para no cortar la temporada de incendios al medio del año. Los DATOS siguen siendo por año calendario; esta columna no cambia ningún valor, sólo el orden de exhibición.",
  "Área quemada, promedio anual (ha)" =
    "Hectáreas quemadas en ese mes, PROMEDIADAS sobre los 27 años de la serie (1999-2025): 'un mes de este tipo, en un año típico'. No es un total acumulado.",
  "Área quemada, promedio anual (Mha)" =
    "La columna anterior en millones de hectáreas.",
  "Porcentaje del área quemable (%)" =
    "La misma área quemada promedio, dividida por el área quemable (constante) de la ecorregión, x100.",
  "Incendios totales, promedio anual" =
    "Cantidad de incendios mapeados que empezaron o pasaron por ese mes (fecha mediana del incendio), promediada sobre los 27 años. Es un CONTEO DE INCENDIOS (polígonos), no de área: un incendio grande y uno chico valen 1 cada uno acá.",
  "Incendios ≥ 10 ha, promedio anual" =
    "Igual que la anterior, sólo incendios de 10 hectáreas o más. Es la curva que dibuja el factsheet, porque no depende de qué tan chico puede ser un incendio para que el mapeo lo detecte.",
  "Incendios ≥ 100 ha, promedio anual" =
    "Igual, sólo incendios de 100 hectáreas o más.",
  "Porcentaje del área quemada anual de la ecorregión (%)" =
    "Qué % del área quemada de TODO EL AÑO de esa ecorregión ocurre en ese mes. Los 12 meses de una misma ecorregión suman 100%: sirve para comparar la FORMA de la temporada de fuego entre ecorregiones de tamaños muy distintos.",
  "Porcentaje de los incendios anuales de la ecorregión (%)" =
    "Igual que la anterior, pero contando incendios (≥10 ha) en vez de hectáreas.",
  "Incendios ≥ 10 ha cada 10.000 km²" =
    "Densidad de incendios ≥10 ha ese mes, normalizada por el tamaño de la ecorregión (en 10.000 km²), para poder comparar ecorregiones de superficie muy distinta. OJO: un incendio se cuenta en TODAS las ecorregiones que toca, así que sumar esta columna sobre las 12 ecorregiones da más que el valor de 'Argentina'."
))
msg("[hoja 3] Distribución intraanual: %d filas", nrow(s3))

# =============================================================================
# 4. Cobertura quemada por año (nacional) — a pedido explícito, sólo a nivel
#    país: cuánto de cada clase de cobertura se quemó y cuánto NO, año a año.
#    No está en el factsheet en esta forma (el factsheet sólo muestra la
#    composición acumulada, hoja siguiente).
# =============================================================================
lulc_pct   <- rd("factsheet_lulc_pct.csv")
lulc_share <- rd("factsheet_lulc_share.csv")
cw <- unique(lulc_share[level == "nivel2", .(clase, nivel1)])

lp2 <- lulc_pct[level == "nivel2" & ecoregion == NAT]
lp2 <- merge(lp2, cw, by = "clase")
lp2[, unburned_ha := area_ha - burned_ha]
s4 <- lp2[, .(year, clase, nivel1,
              `Área de la clase (ha)`     = round(area_ha, 1),
              `Área quemada (ha)`         = round(burned_ha, 1),
              `Área no quemada (ha)`      = round(unburned_ha, 1),
              `Porcentaje de la clase quemado (%)` = round(pct, 4))]
setorder(s4, year, -`Área quemada (ha)`)
setnames(s4, c("year", "clase", "nivel1"), c("Año", "Clase de cobertura (nivel 2)", "Familia (nivel 1)"))
setcolorder(s4, c("Año", "Clase de cobertura (nivel 2)", "Familia (nivel 1)",
                  "Área de la clase (ha)", "Área quemada (ha)", "Área no quemada (ha)",
                  "Porcentaje de la clase quemado (%)"))

write_sheet(wb, "Cobertura quemada por año", s4, widths = c(8, 30, 30, 18, 16, 18, 20), comments = list(
  "Año" = "Año calendario del incendio, no de la cobertura (ver la columna 'Área de la clase' para el porqué).",
  "Clase de cobertura (nivel 2)" =
    "La clase de cobertura de la Colección 3 de MapBiomas en su NIVEL 2 (la clase 'nativa', la que ve un usuario de la plataforma; ej. 'Bosque cerrado', 'Pastura'). Sólo se incluyen las clases QUEMABLES: agua, glaciar, ciudad, suelo desnudo, etc. se excluyen porque el fuego mapeado ahí es error de mapeo, no vegetación quemándose (es un 0,09% de todo lo quemado en 27 años).",
  "Familia (nivel 1)" =
    "El grupo grande al que pertenece esa clase (Bosques / Vegetación natural herbácea y arbustiva / Áreas de uso agropecuario), la agrupación de nivel 1 de la misma leyenda de MapBiomas.",
  "Área de la clase (ha)" =
    "Cuántas hectáreas había de esa clase, ese año, en todo el país. OJO: es la cobertura del año ANTERIOR al incendio (Y-1), no la del año del incendio: un fuego quema lo que había antes de arder, no en qué se convirtió el terreno después. Es la misma convención que usa el factsheet para 'qué se quemó'.",
  "Área quemada (ha)" =
    "De esa área de la clase (ver columna anterior), cuántas hectáreas se quemaron ese año.",
  "Área no quemada (ha)" =
    "Área de la clase menos área quemada: lo que había de esa clase y NO se quemó ese año.",
  "Porcentaje de la clase quemado (%)" =
    "Área quemada dividido área de la clase, x100: qué fracción de ESA clase (no del total del país) ardió ese año."
))
msg("[hoja 4] Cobertura quemada por año: %d filas", nrow(s4))

# =============================================================================
# 5. Composición de lo quemado (nacional, acumulado 1999-2025) — la tabla
#    detrás de la lámina 1 del factsheet (la torta y la barra de cobertura):
#    de todo lo que se quemó en el país en 27 años, qué % era cada clase.
#    Sin columna de año: es un acumulado de toda la serie.
# =============================================================================
ls2 <- lulc_share[level == "nivel2" & ecoregion == NAT]
s5 <- ls2[, .(clase, nivel1,
              `Área quemada acumulada 1999-2025 (ha)`  = round(burned_ha, 1),
              `Área quemada acumulada 1999-2025 (Mha)` = round(burned_ha / 1e6, 4),
              `Porcentaje de lo quemado (%)`           = round(share, 3))]
setorder(s5, -`Porcentaje de lo quemado (%)`)
setnames(s5, c("clase", "nivel1"), c("Clase de cobertura (nivel 2)", "Familia (nivel 1)"))

write_sheet(wb, "Composición de lo quemado", s5, widths = c(30, 30, 22, 22, 18), comments = list(
  "Clase de cobertura (nivel 2)" =
    "La clase de cobertura en su nivel 2 (la clase nativa de la leyenda de MapBiomas), la del año ANTERIOR al fuego -lo que ardió, no en qué se convirtió el terreno-. Sólo clases quemables (ver hoja anterior).",
  "Familia (nivel 1)" =
    "El grupo grande al que pertenece esa clase (Bosques / Vegetación natural herbácea y arbustiva / Áreas de uso agropecuario).",
  "Área quemada acumulada 1999-2025 (ha)" =
    "Hectáreas de esa clase quemadas, SUMADAS sobre los 27 años de la serie. Es una superficie por año acumulada: una hectárea que se quemó cuatro veces en la serie está contada cuatro veces, no una. No es 'la superficie que ardió alguna vez' (esa es menor).",
  "Área quemada acumulada 1999-2025 (Mha)" =
    "La columna anterior en millones de hectáreas.",
  "Porcentaje de lo quemado (%)" =
    "Qué % de TODO lo quemado en el país en 27 años era esta clase. El denominador es el total quemado del país (todas las clases quemables suman 100% acá), no el área total de esa clase -esta tabla dice QUÉ SE QUEMÓ, no QUÉ % DE LA CLASE SE QUEMÓ (eso está en la hoja 'Cobertura quemada por año')."
))
msg("[hoja 5] Composición de lo quemado: %d filas", nrow(s5))

# =============================================================================
# 6. Notas — de qué se trata el archivo, para quien lo abre sin contexto
# =============================================================================
notas <- data.table(Nota = c(
  "MapBiomas Fuego Argentina — Colección 1 (1999-2025)",
  sprintf("Archivo generado el %s por collection-01/statistics/excel_workbook.R", format(Sys.Date(), "%Y-%m-%d")),
  "",
  "Fuentes: los mapas anuales de área quemada de MapBiomas Fuego Argentina, Colección 1, y el mapa de cobertura y uso del suelo de MapBiomas Argentina, Colección 3.",
  "El detalle técnico completo -de dónde sale cada número, cómo se calculó- está en collection-01/statistics/docs/statistics.md, sección 'Excel table for the web page'.",
  "",
  "Cobertura territorial: 12 de las 13 ecorregiones de Burkart et al. (1999). Islas del Atlántico Sur no está incluida en ninguna hoja: la grilla de procesamiento no llega a esa región (no hay datos, no es que no se haya quemado).",
  "Todas las fechas son AÑO CALENDARIO (enero a diciembre). El mapeo interno usa un 'año de fuego' (1 de mayo a 30 de abril) para no cortar una temporada de incendios al medio, pero eso nunca es lo que se reporta -salvo la columna de orden de la hoja 'Distribución intraanual', que es sólo para ordenar un gráfico.",
  "El 'área quemable' de cada ecorregión es una cifra CONSTANTE en el tiempo (no cambia año a año): es el área que puede arder, calculada una sola vez. Por eso un % quemado puede, en principio, superar el 100% si una región llegara a quemarse más que su propia área quemable típica -no sería un error.",
  "Donde se cruza fuego con cobertura del suelo (hojas 'Cobertura quemada por año' y 'Composición de lo quemado'), la cobertura es la del AÑO ANTERIOR al incendio: se reporta qué había antes de arder, no en qué se convirtió el terreno después.",
  "",
  "Dudas, decisiones tomadas sin consultar y cosas para revisar: collection-01/statistics/NOTES_FOR_IVAN_TABLES.txt"
))
addWorksheet(wb, "Notas")
writeData(wb, "Notas", notas, colNames = FALSE)
setColWidths(wb, "Notas", cols = 1, widths = 110)
addStyle(wb, "Notas", createStyle(wrapText = TRUE, valign = "top"),
         rows = seq_len(nrow(notas)), cols = 1)

saveWorkbook(wb, OUT_XLSX, overwrite = TRUE)
msg("\n[out] %s", OUT_XLSX)
