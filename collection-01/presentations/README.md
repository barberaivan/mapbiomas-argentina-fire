# Diagrama de metodología, Colección 1

Dos figuras, un solo generador de primitivas. **No son la misma figura**: la de Slides es panorámica
(720×405 pt) y la del ATBD es angosta y va en dos columnas de contenido menos (372×418 pt). Comparten
`make_diagram.py` — la del ATBD lo importa como módulo y sólo pisa tamaños de fuente y geometría.

## Qué generar y cómo

`python-pptx` no está en el venv de GEE y no hay que instalarlo ahí. Venv aparte, descartable:

```bash
python3 -m venv venv && venv/bin/pip install python-pptx lxml
```

**Versión Slides** (charla de lanzamiento, dos diapositivas: magma y rocket):

```bash
python make_diagram.py diagrama_metodo.pptx
libreoffice --headless --convert-to pdf --outdir . diagrama_metodo.pptx
pdftoppm -r 150 -png diagrama_metodo.pdf d   # mirar el render antes de dar por bueno un cambio
```

Se importa en Google Slides con *Archivo → Importar diapositivas*: todo llega como formas y cuadros de
texto editables (verificado por Iván).

**Versión ATBD** (figura angosta, una sola diapositiva, sólo magma, texto en inglés):

```bash
python make_diagram_atbd.py out/algorithm_c01.pptx
libreoffice --headless --convert-to pdf --outdir out out/algorithm_c01.pptx
```

`out/algorithm_c01.pdf` es el PDF vectorial que va a `ATBD/figures/` (reemplaza a
`algorithm_c00_placeholder.png`, que es el esquema de la Colección 0). El lienzo está dimensionado al
ancho final de impresión — 372 pt = 0,82 × 453,5 pt = 0,82 × textwidth de A4 con márgenes de 2,5 cm —
así que en `\includegraphics{}` va **sin `width=`**, a escala 1.0: si se estira, el texto de las cajas
queda de otro cuerpo que el del pie de figura. Verificar con `pdfinfo` que el ancho siga siendo 372 pt
antes de darlo por bueno.

Iterar sobre la imagen, no de memoria: la geometría no se acierta a ojo.

## Decisiones de diseño (no volver a discutir)

- **Estructura: bandas.** Franjas horizontales (espectral / temporal / espacial / productos), flujo
  insumo → proceso → resultado de izquierda a derecha. Se descartaron una serpentina y una espina
  horizontal.
- **Tres roles, tres tratamientos**: insumo = relleno tenue; proceso = contorno de color sobre blanco;
  resultado = relleno sólido con texto blanco.
- **Fondo de banda medio (20 %) y sin sombra.** El chip de insumo va ~20 puntos porcentuales por encima
  de su banda (20 % / 34 %) o se confunden con el fondo.
- **Colores de etapa**: tres paradas medias del mapa (0,26 / 0,50 / 0,72), nunca los extremos, o queda
  casi negro o casi blanco. Sólo magma para el ATBD; Slides todavía compara magma y rocket (`rocket` es
  de seaborn, no de matplotlib).
- **La banda de productos queda en gris `#3A3A3A`** a propósito: es lo que publica la red, no lo que
  hace Argentina.
- **Se agregó el clasificador de objetos**, que faltaba en la slide 13 original. **Se sacó «Productos
  internos»**, que es detalle interno.
- **Google Slides es el destino de la primera figura**, no PowerPoint ni PDF directo.
- **En el ATBD el nombre de etapa va en la esquina superior izquierda de cada banda**, no en una columna
  de margen aparte — libera el ancho que hace falta para las tres columnas en ~372 pt.

## Trampas encontradas (costó descubrirlas)

- **La sombra fantasma.** `python-pptx` le cuelga a cada forma un `<p:style>` con
  `<a:effectRef idx="2">` (sombra del tema de Office). `shape.shadow.inherit = False` deja un
  `<a:effectLst/>` vacío que **LibreOffice y Slides ignoran** — la sombra se sigue dibujando. Hay que
  **borrar el `<p:style>` entero**: es lo que hace `flatten()`.
- **Roboto**, no Arial: está en Google Slides y en esta máquina, el render de LibreOffice es fiel.
- **Los fondos se calculan, no se eligen a ojo**: `tint(color, f)` mezcla con blanco, ver `LEVELS` y
  `PALETTES` arriba de `make_diagram.py`.
- Sobre fondos teñidos el texto accesorio se oscurece a `#6B6B6B` y los subtítulos de caja a `#4A4A4A`;
  los grises claros originales dejan de leerse.
- **Los conectores entre bandas no pueden entrar por el centro de la columna de insumo**: ahí vive el
  título de la banda de abajo (`ELBOW_IN_X` en `make_diagram_atbd.py`, corrido a la derecha del texto).
- **Las cajas apiladas no pueden tocar el borde de la banda de fondo** ni quedar tan pegadas entre sí
  que el conector entre ellas se vuelva un segmento de pocos puntos: en el ATBD, `CONTENT_INSET`
  separa las columnas del borde y `STACK_H`/`STACK_OFF2` fijan alto y separación de los pares
  apilados (chips y procesos de las bandas espectral y espacial).
- Importar en Slides funciona (*Archivo → Importar diapositivas*): todo llega editable.

## No ir por Typst

`CONTEXT-typst.md` y los `.typ` de esta carpeta son una migración anterior de la slide 13 a
Typst + Touying + Fletcher, con versión en pasos incluida. Funciona, pero Iván la descartó
explícitamente: quiere editar a mano en Google Slides. No resucitarla salvo que él la pida.

## Abierto (versión Slides)

1. **magma o rocket.** Único punto pendiente de esa versión. Ver `diagrama-03-magma-rocket.html`.
2. **Versión en pasos**: una diapositiva por banda, alineadas al píxel. En Slides no usar animaciones
   (se pierden al exportar a PDF) — son diapositivas sucesivas, conviene generarlas del `.py`.

La versión del ATBD está aprobada (2026-09-21): contenido, geometría y conectores revisados por Iván.
Falta que él copie `out/algorithm_c01.pdf` a `ATBD/figures/` y actualice la referencia en
`ATBD/main.tex` — no tocar `ATBD/` desde acá.

## Archivos

| archivo | qué es |
|---|---|
| `make_diagram.py` | generador de la versión Slides (16:9). Paletas, niveles de fondo y geometría arriba del archivo |
| `make_diagram_atbd.py` | generador de la versión angosta para el ATBD; importa las primitivas de `make_diagram.py` |
| `diagrama_metodo.pptx` | 2 diapositivas (magma y rocket), lo que se importa en Slides |
| `diagrama-03-magma-rocket.html` | las dos finalistas de paleta para Slides, autocontenido (PNG en base64) |
| `out/algorithm_c01.pdf` / `.pptx` | figura del ATBD, 372×418 pt, magma, aprobada |
| `CONTEXT-typst.md`, `*.typ` | migración a Typst descartada, ver arriba |
| `taller_mayo_2026_col_01.pdf/.pptx` | slide 13 original — referencia de contenido, diseño superado |
| `borrador_factsheet.pdf` | factsheet y comentarios de color de Iván; la paleta del diagrama sale de ahí (magma/plasma) |

## Contexto que conviene leer, y el que no

- `ATBD/main.tex`, sección *The burned-area mapping algorithm*: de ahí salieron la jerarquía y las tres
  preguntas. Es la fuente del contenido, no `docs/00-overview.md`.
- `taller_mayo_2026_col_01.pdf` slide 13: el diagrama original, útil como referencia de contenido.
- Las figuras del factsheet están a tamaño impreso: proyectadas, ejes y leyendas no se leen. Si entran
  al deck hay que re-renderizarlas a tamaño diapositiva — pendiente aparte.
