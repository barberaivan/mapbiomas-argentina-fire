# collection-01/scripts/make_fires_table_stats.R
#
# Build fires_table_stats.csv from:
#   - collection-01/data/toma_de_muestras.xlsx  (field collection metadata)
#   - collection-01/data/training_observations_{region}_v1.csv  (one per region)
#
# Output: collection-01/data/fires_table_stats.csv
#
# Run from the repo root:
#   Rscript collection-01/scripts/make_fires_table_stats.R
#
# Re-run whenever training observations CSVs are updated.

library(readxl)
library(data.table)
library(dplyr)

xlsx_path <- here::here("collection-01/data/toma_de_muestras.xlsx")
regions   <- c("PAT", "CUYO", "BA", "CHACO", "PAMPA")

samples <- lapply(regions, function(reg) {
  read_excel(xlsx_path, sheet = reg, col_types = "text") |>
    mutate(region = reg)
}) |>
  bind_rows() |>
  mutate(reg_fire_id = paste0(region, "_", fire_id)) |>
  rename(duration_min = `duration (min)`)

obs_data_path <- here::here("collection-01/data")
# Version of the training_observations export to read (PAT re-runs more often).
obs_versions  <- c(PAT = 5, BA = 3, CHACO = 3, CUYO = 3, PAMPA = 3)

obs_summary <- lapply(regions, function(reg) {
  f  <- file.path(obs_data_path, paste0("training_observations_", reg, "_v", obs_versions[reg], ".csv"))
  dt <- fread(f, select = c("fire_id", "point_id"))
  dt[, region      := reg]
  dt[, reg_fire_id := paste0(reg, "_", fire_id)]
  dt[, .(n_points = uniqueN(point_id), n_obs = .N),
     by = .(region, fire_id, reg_fire_id)]
}) |>
  rbindlist()

# ── Canonical name lookups ────────────────────────────────────────────────────
# author = point-sampler; colector = fire-fisher.
# Add entries here whenever new raw spellings appear in toma_de_muestras.xlsx.
author_names <- c(
  "\""                     = NA_character_,              # malformed cell in source xlsx
  "Augusto van der Ploeg"  = "Augusto van der Ploeg",   # Dutch: lowercase van/der
  "Augusto Van der Ploeg"  = "Augusto van der Ploeg",
  "Camila M"               = "Camila Mateo",
  "Camila Mateo"           = "Camila Mateo",
  "Camilo"                 = "Camilo Bagnato",
  "Carla S"                = "Carla Sauval",
  "Cecilia Evequoz"        = "Cecilia Evequoz",
  "Dalma R."               = "Dalma Raymundi",
  "Daniela A."             = "Daniela Arpigiani",
  "Fernando S."            = "Fernando Salvaré",
  "Iván Barberá"           = "Iván Barberá",
  "Jaime Moyano"           = "Jaime Moyano",
  "Jose D.L"               = "José Lencinas",
  "Juan G."                = "Juan Gowda",
  "JuanG"                  = "Juan Gowda",
  "Leo Lizárraga"          = "Leónidas Lizárraga",
  "Leonidas Lizárraga"     = "Leónidas Lizárraga",
  "Lican M."               = "Lican Martinez",
  "LicanMartinez"          = "Lican Martinez",
  "marian.l"               = "Mariana Lipori",
  "Micaela A."             = "Micaela Abrigo",
  "Micaela G."             = "Micaela Gambino",
  "Nehuen B."              = "Nehuen Bedeti",
  "Pablo Baldassini"       = "Pablo Baldassini",
  "Ramón P. A."            = "Ramón Peña Agrest",
  "Ramón Peña Agrest"      = "Ramón Peña Agrest",
  "Roxana Giménez"         = "Roxana Giménez",
  "Roxana Myriam Giménez"  = "Roxana Giménez",
  "Tomas Vujanic"          = "Tomas Vujanic"
)

colector_names <- c(
  "buenrramon"      = "Ramón Peña Agrest",
  "Camila Mateo"    = "Camila Mateo",
  "ceci"            = "Cecilia Evequoz",
  "ivan"            = "Iván Barberá",
  "jime"            = "Jimena Albornoz",
  "juan"            = "Juan Argañaraz",
  "lechu"           = "Andrés Leszczuk",
  "leo"             = "Leónidas Lizárraga",
  "lican"           = "Lican Martinez",
  "Ramón Peña Agrest" = "Ramón Peña Agrest"
)

fires_table <- samples |>
  left_join(obs_summary |> select(reg_fire_id, n_points, n_obs),
            by = "reg_fire_id") |>
  mutate(
    author   = coalesce(author_names[author],   author),
    colector = coalesce(colector_names[colector], colector)
  ) |>
  select(region, fire_id, reg_fire_id, description, author, colector,
         duration_min, n_points, n_obs)

out <- here::here("collection-01/data/fires_table_stats.csv")
fwrite(fires_table, out)
cat("Written:", nrow(fires_table), "rows →", out, "\n")
