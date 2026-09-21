# HANDOFF — diagrama de metodología, Colección 1

Estado al **2026-09-20**. La charla de lanzamiento es el **jueves 24 de septiembre**: 15 min,
metodología + hallazgos del factsheet. Lo que sigue es sólo el diagrama del método.

## Decidido, no volver a discutir

- **Estructura: bandas.** Cuatro franjas horizontales (espectral / temporal / espacial /
  productos), nombre de etapa en el margen izquierdo, flujo insumo → proceso → resultado de
  izquierda a derecha. Se descartaron una serpentina y una espina horizontal.
- **Fondo de banda medio (20 %) y sin sombra.**
- **Tres roles, tres tratamientos**: insumo = relleno tenue; proceso = contorno de color sobre
  blanco; resultado = relleno sólido con texto blanco. Es lo que arregla la slide 13 original,
  donde las doce cajas eran idénticas.
- **Sin las preguntas por etapa y sin las notas de resolución sub-anual / anual.** Iván las dice.
- **Se agregó el clasificador de objetos**, que faltaba en la slide 13. **Se sacó «Productos
  internos»**, que es detalle interno.
- **Google Slides es el destino**, no PowerPoint ni PDF directo.

## Abierto

1. **magma o rocket.** Único punto pendiente del diseño. Iván se inclinaba a decidirlo mirando
   `diagrama-03-magma-rocket.html`. Mi recomendación fue magma, por consistencia con la Fig 01 del
   factsheet; rocket hace mejor puente con el rojo de la carátula.
2. **Versión en pasos**: una diapositiva por banda, cuatro o cinco, todas alineadas al píxel.
   En Slides **no usar animaciones** — se pierden al exportar a PDF. Son diapositivas sucesivas,
   y por eso conviene generarlas del `.py` y no duplicando a mano.
3. **Versión para el ATBD** — ver abajo.

## La versión del ATBD es otra figura, no la misma

`ATBD/main.tex`, sección *The burned-area mapping algorithm*, todavía incluye
`figures/algorithm_c00_placeholder.png`, que es **el esquema de la Colección 0** y dice en el
caption que es provisorio. Reemplazarlo pide un diagrama distinto en dos sentidos:

- **Mucho más angosto.** A4 con márgenes de 2,5 cm → `\textwidth` = 160 mm = 454 pt, y la figura
  entra al 0,82 → **≈ 372 pt de ancho**, contra los 720 pt de la diapositiva. La disposición de
  cuatro bandas anchas no sobrevive: hay que ir a un formato alto, probablemente dos columnas por
  etapa apiladas verticalmente (que es, de hecho, la forma de la slide 13 original).
- **Más detallado, no menos.** Un lector de ATBD sí quiere lo que se sacó de la charla: los
  productos internos, semillas contra candidatos, el umbral por banda de tamaño, la distinción
  sub-anual / anual. El texto puede ir a 8 pt porque se lee de cerca.
- Salida **PDF vectorial**, no PNG: `\includegraphics{figura.pdf}` a escala 1.0. Diseñarla al
  ancho final de impresión y no dejar que `width=\columnwidth` la estire, o el texto de las cajas
  queda de otro cuerpo que el del pie de figura.

## Cómo se construye (esto es lo que costó descubrir)

`python-pptx` → `.pptx` de formas nativas → LibreOffice a PDF → PNG → **mirar el render**. Iterar
sobre la imagen: la geometría no se acierta de memoria.

```bash
python make_diagram.py diagrama_metodo.pptx
libreoffice --headless --convert-to pdf --outdir . diagrama_metodo.pptx
pdftoppm -r 150 -png diagrama_metodo.pdf d
```

`python-pptx` **no está en el venv de GEE y no hay que instalarlo ahí**. Se usó un venv aparte,
descartable: `python3 -m venv /tmp/…/venv && venv/bin/pip install python-pptx lxml`.

### Trampas encontradas

- **La sombra fantasma.** `python-pptx` le cuelga a cada forma un `<p:style>` con
  `<a:effectRef idx="2">`, que es una sombra del tema de Office. `shape.shadow.inherit = False`
  escribe un `<a:effectLst/>` vacío que **LibreOffice y Slides ignoran**: la sombra se sigue
  dibujando. Hay que **borrar el `<p:style>` entero** — es lo que hace `flatten()`. Sin eso no
  existe un «sin sombra» de verdad.
- **Lienzo 720 × 405 pt**, que es el 16:9 de Google Slides (10 × 5,625 in). Los cuerpos
  tipográficos son absolutos: 11 pt en una página de 720 pt es el 11 pt que se ve en Slides.
- **Roboto**, no Arial. Está en Google Slides y en esta máquina, así que el render de LibreOffice
  es fiel. Arial funciona pero se ve viejo.
- **Los fondos se calculan, no se eligen a ojo.** `tint(color, f)` mezcla con blanco. El chip de
  insumo va **~20 puntos porcentuales por encima de su banda** o se confunden: 20 % / 34 % es el
  par elegido.
- **Colores de etapa**: tres paradas medias del mapa (0,26 / 0,50 / 0,72), nunca los extremos, o
  queda casi negro o casi blanco. `rocket` es de seaborn, no de matplotlib.
- Sobre fondos teñidos hubo que oscurecer el texto accesorio a `#6B6B6B` y los subtítulos de caja
  a `#4A4A4A`; los grises claros originales dejaban de leerse.
- La banda de productos se queda en **gris `#3A3A3A`** a propósito: es lo que publica la red, no
  lo que hace Argentina.
- **Importar en Slides funciona** (*Archivo → Importar diapositivas*): verificado por Iván, todo
  llega como formas y cuadros de texto editables.

## No ir por Typst

`CONTEXT-typst.md` y los `.typ` de esta carpeta son una migración anterior de la slide 13 a
Typst + Touying + Fletcher, con versión en pasos incluida. **Funciona, pero Iván la descartó
explícitamente**: quiere editar a mano en Google Slides. No resucitarla salvo que él la pida.

## Archivos

| archivo | qué es |
|---|---|
| `make_diagram.py` | el generador. Paletas, niveles de fondo y geometría están arriba del archivo |
| `diagrama_metodo.pptx` | 2 diapositivas: magma y rocket. Lo que se importa en Slides |
| `diagrama-03-magma-rocket.html` | las dos finalistas, con los ajustes finales |

El HTML es autocontenido (PNG en base64, 0,6 MB) y regenerable desde el `.py`. Hubo dos páginas
más —la comparación de estructuras y la matriz de paletas— que Iván borró una vez tomada la
decisión; si hiciera falta reabrir alguna, se rearman corriendo el generador con la matriz
completa y volviendo a embeber los renders.

## Contexto que conviene leer, y el que no

- `ATBD/main.tex`, sección *The burned-area mapping algorithm*: de ahí salieron la jerarquía y las
  tres preguntas. Es la fuente del contenido, no el `docs/00-overview.md`.
- `borrador_factsheet.pdf` y `mail factsheet.txt`: el factsheet y los comentarios de Iván sobre
  color. Las figuras ya son magma/plasma, por eso la paleta del diagrama sale de esa familia.
- `taller_mayo_2026_col_01.pdf` **slide 13**: el diagrama original. Útil como referencia de
  contenido; su diseño ya está superado.
- Las figuras del factsheet están a **tamaño impreso**: proyectadas, ejes y leyendas no se leen.
  Si entran al deck hay que re-renderizarlas a tamaño diapositiva. Es un pendiente aparte.
