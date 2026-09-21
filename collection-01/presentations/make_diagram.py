#!/usr/bin/env python
"""Diagrama de metodología (Colección 1) como .pptx de formas nativas.

Se importa en Google Slides con Archivo -> Importar diapositivas y queda todo
editable a mano: cada caja es una forma, cada texto un cuadro de texto.

    python make_diagram.py salida.pptx

Una diapositiva por paleta (magma y rocket).  Fondo de banda al 20 % y sin
sombra: fijados el 2026-09-20, ver PALETTES / LEVELS si hiciera falta volver a
abrir la comparación.
"""
import sys
from pptx import Presentation
from pptx.util import Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from lxml import etree

# --------------------------------------------------------------------- lienzo
W, H = 720.0, 405.0          # pt — igual que Google Slides 16:9 (10 x 5.625 in)
FONT = "Roboto"              # está en Google Slides y en esta máquina

# ------------------------------------------------------------------- paletas
# Tres paradas medias de cada mapa (0.26 / 0.50 / 0.72): nunca el extremo
# oscuro ni el claro.  Los fondos se derivan por mezcla con blanco, ver LEVELS.
PALETTES = {
    "magma":  ["#54137D", "#B73779", "#F9795D"],
    "rocket": ["#641F54", "#CB1B4F", "#F47A54"],
}
# (fondo de banda, fondo de chip) como fracción del color puro sobre blanco.
# El chip va unos veinte puntos por encima de su banda o se confunden.
LEVELS = {
    "suave":  (0.12, 0.24),
    "medio":  (0.20, 0.34),
    "fuerte": (0.30, 0.46),
}
LEVEL = "medio"
SHADE = False

C_PROD = "#3A3A3A"           # productos: el gris de MapBiomas, sin tocar
C_INK = "#1A1A1A"
C_DETAIL = "#4A4A4A"         # subtítulo dentro de una caja
C_MUTED = "#6B6B6B"          # texto accesorio sobre la banda
C_ARROW = "#7A7A7A"

# ------------------------------------------------------------------ tamaños
S_STAGE = 13.0               # nombre de etapa, en el margen izquierdo
S_TITLE = 11.0               # título de caja
S_DETAIL = 9.5               # subtítulo de caja
S_OUT = 11.5                 # título de caja de resultado
S_PROD = 10.0                # chip de producto
S_NOTE = 9.0                 # nota al pie de la banda de productos


def rgb(h):
    return RGBColor.from_string(h.lstrip("#"))


def tint(h, f):
    """Mezcla `h` con blanco: f=1 es el color puro, f=0 es blanco."""
    r, g, b = (int(h.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02X%02X%02X" % tuple(round(c * f + 255 * (1 - f)) for c in (r, g, b))


def palette(name, level=LEVEL):
    st = PALETTES[name]
    fb, fc = LEVELS[level]
    return dict(stages=st,
                bands=[tint(c, fb) for c in st] + [tint(C_PROD, fb)],
                chips=[tint(c, fc) for c in st] + [tint(C_PROD, fc)])


# ------------------------------------------------------------------ primitivas
def flatten(shape):
    """Saca el <p:style> que python-pptx hereda del tema de Office.

    Ese estilo trae un <a:effectRef idx="2">, que es una sombra.  Un
    <a:effectLst/> vacío en spPr debería ganarle, pero LibreOffice —y también
    Slides— dibuja la sombra del tema igual.  Sin <p:style> la caja queda
    realmente plana, y la sombra pasa a ser una decisión explícita de shadow()."""
    el = shape._element
    st = el.find(qn("p:style"))
    if st is not None:
        el.remove(st)
    return shape


def shadow(shape, blur=3.5, dist=1.25, alpha=0.18):
    """Sombra suave hacia abajo.  `rect` ya dejó un <a:effectLst/> vacío en el
    lugar que exige el esquema, así que basta con poblarlo."""
    lst = shape._element.spPr.find(qn("a:effectLst"))
    shdw = etree.SubElement(lst, qn("a:outerShdw"))
    shdw.set("blurRad", str(int(blur * 12700)))
    shdw.set("dist", str(int(dist * 12700)))
    shdw.set("dir", "5400000")          # 90°, hacia abajo
    shdw.set("rotWithShape", "0")
    clr = etree.SubElement(shdw, qn("a:srgbClr"))
    clr.set("val", "000000")
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))
    return shape


def rect(slide, x, y, w, h, *, fill=None, line=None, lw=1.0, radius=0.10):
    s = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, Pt(x), Pt(y), Pt(w), Pt(h))
    s.adjustments[0] = radius
    if fill:
        s.fill.solid()
        s.fill.fore_color.rgb = rgb(fill)
    else:
        s.fill.background()
    if line:
        s.line.color.rgb = rgb(line)
        s.line.width = Pt(lw)
    else:
        s.line.fill.background()
    flatten(s)
    s.shadow.inherit = False            # deja el <a:effectLst/> que usa shadow()
    tf = s.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Pt(6)
    tf.margin_top = tf.margin_bottom = Pt(3)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return s


def write(shape, lines, *, align=PP_ALIGN.CENTER):
    """lines = [(texto, tamaño, color, bold, italic), ...]"""
    tf = shape.text_frame
    tf.clear()
    for i, (txt, size, colour, bold, italic) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_before = Pt(0)
        p.space_after = Pt(1.5)
        r = p.add_run()
        r.text = txt
        f = r.font
        f.name, f.size, f.bold, f.italic = FONT, Pt(size), bold, italic
        f.color.rgb = rgb(colour)


def label(slide, x, y, w, h, lines, *, align=PP_ALIGN.LEFT):
    tb = slide.shapes.add_textbox(Pt(x), Pt(y), Pt(w), Pt(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    write(tb, lines, align=align)
    return tb


def arrow(slide, x1, y1, x2, y2, *, colour=C_ARROW, lw=1.0, head=True):
    cn = slide.shapes.add_connector(
        MSO_CONNECTOR.STRAIGHT, Pt(x1), Pt(y1), Pt(x2), Pt(y2))
    flatten(cn)
    cn.shadow.inherit = False
    cn.line.color.rgb = rgb(colour)
    cn.line.width = Pt(lw)
    if head:
        ln = cn.line._get_or_add_ln()
        tail = etree.SubElement(ln, qn("a:tailEnd"))
        tail.set("type", "triangle")
        tail.set("w", "med")
        tail.set("len", "med")
    return cn


def elbow(slide, pts, *, colour=C_ARROW, lw=1.0):
    """Polilínea ortogonal: flecha sólo en el último tramo."""
    for i in range(len(pts) - 1):
        (x1, y1), (x2, y2) = pts[i], pts[i + 1]
        arrow(slide, x1, y1, x2, y2, colour=colour, lw=lw,
              head=(i == len(pts) - 2))


# ------------------------------------------------------------- cajas tipadas
# Tres roles, tres tratamientos: insumo = relleno tenue; proceso = contorno de
# color sobre blanco; resultado = relleno sólido.
def chip(slide, x, y, w, h, title, detail, fill, *, shade=SHADE):
    s = rect(slide, x, y, w, h, fill=fill, radius=0.14)
    lines = [(title, S_TITLE, C_INK, True, False)]
    if detail:
        lines.append((detail, S_DETAIL, C_DETAIL, False, False))
    write(s, lines, align=PP_ALIGN.LEFT)
    return shadow(s) if shade else s


def process(slide, x, y, w, h, title, detail, colour, *, shade=SHADE):
    s = rect(slide, x, y, w, h, fill="#FFFFFF", line=colour, lw=1.0, radius=0.14)
    lines = [(title, S_TITLE, C_INK, True, False)]
    if detail:
        lines.append((detail, S_DETAIL, C_DETAIL, False, True))
    write(s, lines)
    return shadow(s) if shade else s


def output(slide, x, y, w, h, title, detail, colour, *, shade=SHADE):
    s = rect(slide, x, y, w, h, fill=colour, radius=0.14)
    lines = [(title, S_OUT, "#FFFFFF", True, False)]
    if detail:
        lines.append((detail, S_DETAIL, "#FFFFFF", False, False))
    write(s, lines)
    return shadow(s) if shade else s


# ------------------------------------------------------------------ contenido
SUBPRODUCTS = ["Área quemada anual", "Mes de quema", "Frecuencia",
               "Acumulado", "Año del último fuego", "Tamaño de la cicatriz"]

# ------------------------------------------------------------------- geometría
# El bloque entero corre hacia arriba: el margen inferior es el más grande, para
# que la banda de productos no quede pegada al borde.
BX, BW = 20.0, 680.0          # banda: 20 -> 700
GX, GW = 32.0, 100.0          # margen izquierdo: sólo el nombre de la etapa
COL_IN, W_IN = 144.0, 170.0   # insumos    144 -> 314
COL_PR, W_PR = 334.0, 160.0   # procesos   334 -> 494
COL_OU, W_OU = 514.0, 174.0   # resultados 514 -> 688
BANDS = [(8.0, 96.0), (116.0, 72.0), (200.0, 96.0), (308.0, 62.0)]
MID_IN = COL_IN + W_IN / 2
MID_PR = COL_PR + W_PR / 2
MID_OU = COL_OU + W_OU / 2


def diagram(slide, pal):
    st, bd, ch = pal["stages"], pal["bands"], pal["chips"]

    for (by, bh), fill in zip(BANDS, bd):
        rect(slide, BX, by, BW, bh, fill=fill, radius=0.06)

    for (by, bh), (name, col) in zip(BANDS, [
            ("1  ESPECTRAL", st[0]), ("2  TEMPORAL", st[1]),
            ("3  ESPACIAL", st[2]), ("PRODUCTOS", C_PROD)]):
        label(slide, GX, by, GW, bh, [(name, S_STAGE, col, True, False)])

    # ---------------------------------------------------------- 1 espectral
    by = BANDS[0][0]
    chip(slide, COL_IN, by + 8, W_IN, 38, "Landsat",
         "6 bandas ópticas · 11 índices", ch[0])
    chip(slide, COL_IN, by + 52, W_IN, 38, "MapBiomas",
         "Cobertura y mosaico del año previo", ch[0])
    process(slide, COL_PR, by + 25, W_PR, 46,
            "Clasificador probabilístico", "regresión logística", st[0])
    output(slide, COL_OU, by + 25, W_OU, 46,
           "Probabilidad de quema", "para cada píxel y fecha", st[0])
    arrow(slide, COL_IN + W_IN, by + 27, COL_PR, by + 40)
    arrow(slide, COL_IN + W_IN, by + 71, COL_PR, by + 56)
    arrow(slide, COL_PR + W_PR, by + 48, COL_OU, by + 48)

    # ----------------------------------------------------------- 2 temporal
    by = BANDS[1][0]
    chip(slide, COL_IN, by + 13, W_IN, 46, "Serie temporal",
         "todas las observaciones del píxel", ch[1])
    process(slide, COL_PR, by + 13, W_PR, 46,
            "Resumen anual de la serie", "por píxel y año", st[1])
    output(slide, COL_OU, by + 13, W_OU, 46, "Métricas anuales",
           "prob. alta · aumento abrupto ·\npersistencia · fecha", st[1])
    arrow(slide, COL_IN + W_IN, by + 36, COL_PR, by + 36)
    arrow(slide, COL_PR + W_PR, by + 36, COL_OU, by + 36)
    gap_y = (BANDS[0][0] + BANDS[0][1] + by) / 2
    elbow(slide, [(MID_OU, BANDS[0][0] + 71), (MID_OU, gap_y),
                  (MID_IN, gap_y), (MID_IN, by + 13)], colour=st[0])

    # ----------------------------------------------------------- 3 espacial
    by = BANDS[2][0]
    chip(slide, COL_IN, by + 10, W_IN, 34, "Semillas",
         "píxeles claramente quemados", ch[2])
    chip(slide, COL_IN, by + 52, W_IN, 34, "Candidatos",
         "píxeles plausiblemente quemados", ch[2])
    process(slide, COL_PR, by + 8, W_PR, 34,
            "Crecimiento de región", "SNIC", st[2])
    process(slide, COL_PR, by + 54, W_PR, 34,
            "Clasificador de objetos", "forma · tamaño · vegetación", st[2])
    output(slide, COL_OU, by + 26, W_OU, 44, "Cicatrices de fuego",
           "1,01 M de incendios, 1999–2025", st[2])
    arrow(slide, COL_IN + W_IN, by + 27, COL_PR, by + 21)
    arrow(slide, COL_IN + W_IN, by + 69, COL_PR, by + 33)
    arrow(slide, MID_PR, by + 42, MID_PR, by + 54)
    arrow(slide, COL_PR + W_PR, by + 71, COL_OU, by + 56)
    gap_y = (BANDS[1][0] + BANDS[1][1] + by) / 2
    elbow(slide, [(MID_OU, BANDS[1][0] + 59), (MID_OU, gap_y),
                  (MID_IN, gap_y), (MID_IN, by + 10)], colour=st[1])

    # ---------------------------------------------------------- 4 productos
    by = BANDS[3][0]
    n, gap = 6, 6.0
    cw = ((COL_OU + W_OU) - COL_IN - (n - 1) * gap) / n
    for i, txt in enumerate(SUBPRODUCTS):
        s = rect(slide, COL_IN + i * (cw + gap), by + 8, cw, 32, fill=ch[3],
                 radius=0.14)
        write(s, [(txt, S_PROD, C_INK, False, False)])
        if SHADE:
            shadow(s)
    label(slide, COL_IN, by + 44, 460, 14,
          [("+ base vectorial: cada incendio como polígono, con su probabilidad",
            S_NOTE, C_MUTED, False, True)])
    arrow(slide, MID_OU, BANDS[2][0] + 70, MID_OU, by + 1, colour=st[2])


# ------------------------------------------------------------------------ main
def main(out):
    prs = Presentation()
    prs.slide_width, prs.slide_height = Emu(int(W * 12700)), Emu(int(H * 12700))
    blank = prs.slide_layouts[6]
    for name in PALETTES:
        diagram(prs.slides.add_slide(blank), palette(name))
    prs.save(out)
    print("escrito:", out, "-", len(PALETTES), "diapositivas")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "diagrama_metodo.pptx")
