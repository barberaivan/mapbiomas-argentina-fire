"""
collection-01/statistics/legends.py

The three lookup tables the statistics decode against, as LITERALS.  A CSV carries no
metadata of its own, so every one of these has to live next to the code that writes the
numbers — never implicit in a downstream group_by.

  BURNABLE / NON_BURNABLE   the col-3 class verdicts (docs/09 §6)
  ECO13_NAMES               GEOCODE -> name for the 13-class ecoregions (docs/09 §5.1)
  STATUS_NAMES              the burnable-status codes this package writes (docs/09 §4.2)

WHY THE NAMES ARE LITERALS AND NOT READ OFF THE ASSET: two ecoregion assets carry the
same ids with different name encodings (`Stats-Arg_ecorregions` is Latin-1 damage stored
as UTF-8), so a decode that reads "the" asset is one asset-id typo away from mojibake in
a designer's CSV.  These 13 strings come from ARG-Political_Level_2-13Ecorregiones_3857,
checked 2026-09-14.
"""

# --- col-3 burnable verdicts (docs/09 §6) -----------------------------------------
# "Burnable" is a property of the LAND-COVER CLASS, not a computation.  Anchored on our
# own col-2 remap (config/veg_fire_remap.csv), which sends 24/25/33/34 -> non-burnable and
# 27 -> non-observed in every one of the 5 regions.  22 and 26 had no col-2 precedent and
# were decided non-burnable (Iván, 2026-09-11).
BURNABLE = [
    1, 3, 4, 6,                      # bosques
    9, 14, 15, 18, 19, 21, 36,       # agropecuario / silvicultura
    10, 11, 12, 63, 66, 73, 77,      # herbáceas, arbustales, turberas
]
NON_BURNABLE = [
    22,      # áreas sin vegetación
    24,      # áreas urbanas
    25,      # otras áreas no vegetadas
    26, 33,  # cuerpos de agua / ríos, lagunas, lagos y océano
    34,      # hielo y nieve permanente
]
# 0 and 27 ("no observado") are in NEITHER list on purpose: the remap leaves them MASKED,
# so they never enter the mode and never land in the numerator or the denominator.
NO_OBSERVADO = [0, 27]

# --- the status codes written by burnable_export.py (docs/09 §4.2) ----------------
# 0/1 are the answer; 2 and 3 exist so the two things that could silently corrupt the
# denominator are VISIBLE as their own rows instead of being folded into 0.
STATUS_NAMES = {
    0: "no_burnable",
    1: "burnable",
    2: "never_observed",   # masked in every year 1998-2024
    3: "tie",              # burnable in exactly half the observed years; ee.Reducer.mode()
                           # would silently send these to 0 (the smaller value)
}

# --- the 13-class ecoregions (docs/09 §5.1) ---------------------------------------
ECO13_NAMES = {
    1:  "Altos Andes",
    2:  "Bosques Patagónicos",
    3:  "Campos y Malezales",
    4:  "Chaco",
    5:  "Delta e Islas del Paraná",
    6:  "Espinal",
    7:  "Estepa Patagónica",
    8:  "Monte",
    9:  "Pampa",
    10: "Puna",
    11: "Selva Paranense",
    12: "Yungas",
    13: "Islas del Atlántico Sur",
}

# The exact 16 -> 13 aggregation, kept here for December's finer cut (docs/09 §5.2).
# Measured, not assumed: every 16-class falls 100 % inside one 13-class.  The only
# non-obvious row is 9 (Esteros del Iberá) -> 4 (Chaco).
ECO16_TO_13 = {1: 1, 2: 2, 3: 3, 4: 4, 5: 4, 6: 5, 7: 6, 8: 7,
               9: 4, 10: 8, 11: 8, 12: 9, 13: 10, 14: 11, 15: 12, 16: 13}


# --- the col-3 land-cover legend, all three levels (docs/09 §5.4) ----------------
# VERBATIM from the network's own `00_Tools/Legends.js::lulc_argentina_nivel{0,1,2}`,
# which is what the toolkit decodes its burned-area CSVs with.  Copied here so the
# DENOMINATOR (our per-class area export) and the NUMERATOR (their burned-area table)
# carry the same class names and can be joined on them — a second, independently typed
# legend is exactly how the join silently stops matching.
LULC_NIVEL_0 = {
    0: "No observado", 27: "No observado",
    1: "Natural", 3: "Natural", 4: "Natural", 6: "Natural",
    10: "Natural", 66: "Natural", 77: "Natural", 63: "Natural", 12: "Natural",
    11: "Natural", 73: "Natural",
    14: "Antrópico", 18: "Antrópico", 19: "Antrópico", 36: "Antrópico", 15: "Antrópico",
    9: "Antrópico", 21: "Antrópico",
    22: "Natural", 24: "Antrópico", 25: "Natural",
    26: "Natural", 34: "Natural", 33: "Natural",
}
LULC_NIVEL_1 = {
    0: "No observado", 27: "No observado",
    1: "Bosques", 3: "Bosques", 4: "Bosques", 6: "Bosques",
    10: "Vegetación natural herbácea y arbustiva",
    66: "Vegetación natural herbácea y arbustiva",
    77: "Vegetación natural herbácea y arbustiva",
    63: "Vegetación natural herbácea y arbustiva",
    12: "Vegetación natural herbácea y arbustiva",
    11: "Vegetación natural herbácea y arbustiva",
    73: "Vegetación natural herbácea y arbustiva",
    # NOTE their own asymmetry, copied rather than tidied: code 14 is "Agropecuario"
    # at nivel 1 while every other code of the family is "Áreas de uso agropecuario".
    # 14 is a parent code and does not appear in col-3 pixels, so it never shows up in a
    # table; fixing it here would be a silent divergence from the numerator's decode.
    14: "Agropecuario", 18: "Áreas de uso agropecuario", 19: "Áreas de uso agropecuario",
    36: "Áreas de uso agropecuario", 15: "Áreas de uso agropecuario",
    9: "Áreas de uso agropecuario", 21: "Áreas de uso agropecuario",
    22: "Áreas sin vegetación", 24: "Áreas sin vegetación", 25: "Áreas sin vegetación",
    26: "Cuerpos de agua", 34: "Cuerpos de agua", 33: "Cuerpos de agua",
}
LULC_NIVEL_2 = {
    0: "No observado", 27: "No observado",
    1: "Bosques", 3: "Bosque cerrado", 4: "Bosque abierto", 6: "Bosque inundable",
    10: "Vegetación natural herbácea y arbustiva",
    66: "Matorrales y arbustales cerrados", 77: "Matorrales y arbustales abiertos",
    63: "Herbaceas", 12: "Herbaceas Inundables",
    11: "Mosaicos de arbustos y herbaceas", 73: "Turberas",
    14: "Agropecuario", 18: "Agricultura", 19: "Cultivos temporarios",
    36: "Cultivos perennes", 15: "Pastura", 9: "Silvicultura", 21: "Mosaico de usos",
    22: "Áreas sin vegetación", 24: "Áreas urbanas", 25: "Otras áreas no vegetadas",
    26: "Cuerpos de agua", 34: "Glaciares descubiertos y nieve perenne",
    33: "Ríos, lagunas, lagos y océano",
}
LULC_CODES = sorted(LULC_NIVEL_2)


def decode_lulc(code):
    """`ecoregion13 * 100 + lulc_class` -> (eco_id, eco_name, class_id, n0, n1, n2)."""
    code = int(code)
    eco, cls = divmod(code, 100)
    if eco not in ECO13_NAMES:
        raise ValueError(
            f"code {code} decodes to ecoregion {eco}, which does not exist — the packing "
            "or the paint is wrong, do not use the table"
        )
    if cls not in LULC_NIVEL_2:
        raise ValueError(
            f"code {code} decodes to land-cover class {cls}, which is NOT in the col-3 "
            "legend above. A class that falls through into a decode default is a silent "
            "error; add it to all three levels (from the network's Legends.js) first"
        )
    return (eco, ECO13_NAMES[eco], cls,
            LULC_NIVEL_0[cls], LULC_NIVEL_1[cls], LULC_NIVEL_2[cls])


def decode(code):
    """Unpack `ecoregion13 * 10 + status` -> (eco_id, eco_name, status_id, status_name)."""
    code = int(code)
    eco, status = divmod(code, 10)
    if eco not in ECO13_NAMES or status not in STATUS_NAMES:
        raise ValueError(
            f"code {code} decodes to ecoregion {eco} / status {status}, which is not a "
            "valid combination — the packing or the paint is wrong, do not use the table"
        )
    return eco, ECO13_NAMES[eco], status, STATUS_NAMES[status]


# --- el cruce estado x ecorregión x cobertura ANTES x cobertura DESPUÉS (docs/09 §5.7) ---
# El empaquetado de `lulc_change_export.py`:
#
#     state * 1000000 + eco * 10000 + prev * 100 + post
#
# `prev` es la clase col-3 del año Y-1 y `post` la de Y+offset.  Tope
# 3*1000000 + 13*10000 + 77*100 + 77 = 3137777: NO entra en uint16, así que la banda es
# int32 — el error silencioso de este análisis sería empaquetarlo como el de
# `lulc_area_export` (eco*100 + clase) y ver el desbordamiento como clases inexistentes.
CHANGE_CODE_BASE = 10000
CHANGE_STATE_BASE = 1000000

# LOS CUATRO ESTADOS DE FUEGO (docs/09 §5.7.1).  Son cuatro y no dos porque la regla de
# exclusión de Ferro et al. (2026) —"sólo píxeles que NO ardieron en el año anterior ni en el
# siguiente, para evitar errores de clasificación de la cobertura"— se aplica a LOS DOS
# grupos, no sólo al control:
#
#   * un píxel del control que ardió en Y+1 tiene la cobertura de Y+1 mirando una cicatriz
#     igual que uno tratado, y meterlo en el control lo acerca al tratamiento por
#     construcción — el cociente q saldría atenuado;
#   * un píxel tratado que además ardió en Y-1 tiene la cobertura "antes" YA alterada por
#     fuego, así que su transición no es "de lo que había a lo que quedó".
#
# Los dos contaminados se apartan como estados propios en vez de descartarse en silencio: la
# tabla los trae, `factsheet_tables.R` informa cuánta superficie es cada uno, y el titular del
# análisis 6 (que es "de TODO lo que ardió, cuánto cambió") suma 1 + 3.
FIRE_STATE_NAMES = {
    0: "control",          # sin fuego en TODA la ventana [Y-1, Y+offset]
    1: "burned_clean",     # ardió en Y y en NINGÚN otro año de la ventana — el tratamiento
    2: "window_fire",      # no ardió en Y, pero sí en otro año de la ventana (control sucio)
    3: "burned_repeat",    # ardió en Y y TAMBIÉN en otro año de la ventana (tratamiento sucio)
}


def decode_lulc_change(code):
    """`state * 1000000 + eco * 10000 + prev * 100 + post`
    -> (state_id, state_name, eco_id, eco_name, prev_id, post_id).

    Los nombres de cada clase se resuelven con `LULC_NIVEL_{0,1,2}` como siempre; acá sólo
    se desempaqueta, y se valida con la misma dureza que `decode_lulc`: una clase que no
    está en la leyenda es un error, nunca un default.
    """
    code = int(code)
    state, rest = divmod(code, CHANGE_STATE_BASE)
    eco, rest = divmod(rest, CHANGE_CODE_BASE)
    prev, post = divmod(rest, 100)
    if state not in FIRE_STATE_NAMES:
        raise ValueError(
            f"code {code} decodes to fire state {state}, which does not exist — the packing "
            "is wrong, do not use the table")
    if eco not in ECO13_NAMES:
        raise ValueError(
            f"code {code} decodes to ecoregion {eco}, which does not exist — the packing "
            "or the paint is wrong, do not use the table")
    for name, cls in (("prev", prev), ("post", post)):
        if cls not in LULC_NIVEL_2:
            raise ValueError(
                f"code {code} decodes to {name} land-cover class {cls}, which is NOT in the "
                "col-3 legend. A class that falls through into a decode default is a silent "
                "error; add it to all three levels (from the network's Legends.js) first")
    return state, FIRE_STATE_NAMES[state], eco, ECO13_NAMES[eco], prev, post
