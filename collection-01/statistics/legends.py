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
