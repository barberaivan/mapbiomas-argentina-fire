# ROADMAP

**What to do next, in order.** This file is the *when*; `collection-01/docs/NN-*.md` are the *how*.
Read it at the start of every session, before planning anything.

**How to use it**

- Work top-down. `Now` is in flight, `Next` is ordered and its blockers are named, `Later` is
  scheduled but not yet startable.
- Each item says whether it is **run** (execute what exists) or **edit → run** (code must change
  first). That distinction is the whole point of the file — several things below look like a re-run
  and are not.
- **Update this file as you go**: tick an item when it lands, and delete it on the next pass. Git
  history is the archive; a long done-list costs every future session context it could spend on the
  work.
- [`BACKLOG.md`](BACKLOG.md) is the *unscheduled* pile, per topic, with the post-mortems. An item
  moves BACKLOG → ROADMAP when it is scheduled, never the other way.

**Dates.** MapBiomas Argentina col-3 (with fire col-1) launches **24 Sep 2026**. 

## Next

**Ordenar y limpiar el repo — el plan vive en [`DOCS-CLEANUP.md`](DOCS-CLEANUP.md)** (raíz del
repo): el orden de las fases, la plantilla, a dónde va cada archivo y el protocolo de sesión.
Lo que sigue abajo es el material de origen de ese plan, no la lista de tareas.

Ordenar y limpiar el repo. Debe quedar listo para que alguien pueda entenderlo,
y quizás reproducirlo. No se puede reproducir estrictamente porque muchos assets 
que se usan no son públicos, pero el objetivo es que si alguien quiere aplicar este
procedimiento en otro país pueda hacerlo.

Tengo dudas sobre el diseño de la documentación, y quizás sobre el orden del código.

La estructura general implica que workflow/ hace todo lo grueso, lo más importante.
En scripts/ viven herramientas accesorias; no es que sean dispensables, son realmente
necesarias para el pipeline, pero no implican generalmente cómputo pesado ni conceptualmente
complejo. Es más bien descargar/formatear/ordenar, y código que se usa para exploración.

docs/ inicialmente tenía la documentación de cada paso del workflow. La idea es que alguien
externo primero lea el ATBD para entender conceptualmente cómo va la cosa. Ahí se detalla el
algoritmo, pero casi no hay detalle de código. Por su parte, es difícil llenar el gap entre
ATBD y código: hay muchos aspectos clave de implementación que hacen posible o no el cómputo
que no son obvias, y esa explicación vive en docs/. De todos modos, los docs deben ser un 
autosuficientes en un punto, para que uno pueda leer un breve párrafo ahí de qué va la idea,
el para qué, sin tener que ir al ATBD. Los docs casi no deberían tener código, salvo algunas 
menciones a paquetes, librería, funciones, sofware que son realmente clave, pero no chunks 
largos de código.

Pero tengo problemas para pensar dónde debería estar cada cosa. El README general está bien, 
es re conciso, pero el README de col1 es super extenso. Quizás está bien.
A la vez, no sé dónde debería vivir todo lo que indica cómo se corren las cosas.
Acá hay mucho sobre cómo ejecutar comandos en bash, porque la forma en que ejecuté todo 
fue a través de Claude Code corriendo cosas en bash. Pero no sé si eso es esencial del repo.
En el README hay mucho de eso, pero quizás podría no estar.

Nunca me enfrenté a una codebase tan grande, entonces no sé qué tiene sentido documentar.
También hay que tener en cuenta que esto no es desarrollo de software para producción.
Las cosas se corren una sola vez, y parte de la ejecución se repite en la col siguiente,
pero no es código que se corre repetidas veces: es hacer el mapa, y listo. 
Pero es valiso saber cómo repetirlo porque siempre se itera: algo sale mal, o algo se mejora
en el futuro. Pero por ej, un código de ejemplo sobre cómo correr un código puede estar 
en el header, y que en docs/ siempre haya una sección de pipeline que encadene la secuencia
de ejecución en prosa y en comandos, sin explicar por qué (eso está en otra secc del 
docs).

Empezando a pensar sobre esto, tuve esta charla con otro Claude:

[YO]
Estoy con un repo grande de MapBiomas fuego. El algoritmo es complejo, tiene muchos pasos que usan GEE, python, R, computo en la nube, local y toda esa mezcla. También hay análisis exploratorios, idas y vueltas.
Lo que hago para mantener el orden y la reproducibilidad es usar una carpeta docs/ con un .md por paso importante del algoritmo, idealmente independientes entre sí. Esto se escribe casi enteramente por Claude Code (Opus 5) según mis instrucciones.
Pero claude aun es muy malo escribiendo en cuanto a que no distingue jerarquia de la ideas, por más que algo intente explicarle sobre eso. Escribe textos muy largos.
Claro que se le puede pedir que revise, resuma. Pero hay mejores prácticas? Qué se anda diciendo del tema?
Quizás es sólo itersr un poco: documentá esto, estas son las ideas claves. Revisar, más prompts indicando y ya.

[CLAUDE]
Tu intuición de iterar es correcta, pero hay tres cosas que reducen mucho las vueltas: fijar la estructura antes de que escriba, darle un ejemplo bueno y revisar en un contexto limpio. El problema de fondo es que Claude Code escribe con toda la sesión en contexto, y desde ahí todo le parece igual de importante.
Lo que mejor funciona
Plantilla fija con límites por sección. No le pidas "sé conciso"; dale un esqueleto con cupos. Por ejemplo: Propósito (2 líneas), Entradas → Salidas (tabla), Cómo correrlo (comandos), Decisiones clave y por qué (máx. 5 ítems), Pendientes. La jerarquía la impone la plantilla, no su criterio.
Un doc modelo. Tomá el paso mejor documentado, pulilo a mano y referencialo como ejemplo. Un buen ejemplo le enseña más que cualquier descripción de "jerarquía de ideas".
Vos das las ideas clave, rankeadas. "Las 3 cosas que alguien tiene que entender de este paso son X > Y > Z". Él expande, pero no decide qué importa.
Separar el doc del paso de la historia. Las idas y vueltas exploratorias son las que más inflan. Mandalas a otro lado: un decisions/ estilo ADR (una nota corta por decisión: contexto, opción elegida, alternativas descartadas) o un log de exploración. El doc del paso solo dice qué se hace hoy y enlaza al porqué.
Revisión con contexto limpio. Un subagente o una sesión nueva que solo vea el .md, con la instrucción de actuar como editor: "cortá 30–40%, cada párrafo empieza con su idea principal, eliminá lo que un lector nuevo no necesita". Quien escribió el texto está anclado a él y le cuesta cortarlo.
Documentar referenciando el código, no repitiéndolo. Parámetros, rutas y assets de GEE conviene dejarlos en config o docstrings, y que el .md los enlace. Así el doc queda más corto y no se desactualiza.
Para no repetir instrucciones: todo esto va en un skill (.claude/skills/doc-paso/SKILL.md) o un slash command /doc-paso, con la plantilla, el ejemplo y las reglas de estilo. Así cada doc arranca desde las mismas reglas en vez de depender de lo que le digas ese día.
Qué se dice del tema: lo más citado es Diátaxis, que distingue tutorial, how-to, referencia y explicación. Muchos docs largos lo son porque mezclan los cuatro tipos. Tu doc por paso es mayormente referencia más how-to; la explicación va aparte. También aparece mucho la pirámide de Minto (conclusión primero): una buena regla es pedirle que escriba primero un resumen de 3 líneas y que después solo desarrolle lo que ese resumen necesita.
En la práctica, igual vas a iterar, pero con plantilla, ejemplo y editor separado suele alcanzar con una pasada de revisión en vez de cinco.

--- end of transcript ---

Sobre esto: "Diátaxis, que distingue tutorial, how-to, referencia y explicación". Ni idea. 
Cómo se comporta este repo en ese sentido.

Quizás puedas hacer un overview del repo, leer docs principales, no una super-revisión.
No quiero que te ensucies el contexto, pero necesito que tengas una idea general de cómo 
está organizado todo. Un gran problema quizás haya sido delegar mucho la documentación
a Claude, y avanzar con desarrollo antes de limpiar esa doc.

## After

- **El ATBD de Argentina Fuego Col1**, que nadie más puede escribir por nosotros.
- **Seguir explorando análisis para el lanzamiento de diciembre**. 
    Ahí hay 4 factsheet-related notebooks; factsheet_sep2026 es el que soporta el factsheet
    del lanzamiento de Col3 ARG en septiembre.
- **Comunicar problema de leyenda**:

Arreglada la leyenda de nivel 2 de la red (17 sep). Falta avisarles.

`00_Tools/Legends.js::lulc_argentina_nivel2` **de la red** traía los valores de los códigos
11, 12 y 63 corridos un lugar respecto de sus claves, y `statistics/legends.py` lo copió
verbatim, así que estaba en **todas nuestras tablas de nivel 2**.

| código | decía | **es** | % de lo quemado |
|---|---|---|---|
| 11 | Mosaicos de arbustos y herbaceas | **Herbaceas Inundables** | 21,2 |
| 12 | Herbaceas Inundables | **Herbaceas** | 21,7 |
| 63 | Herbaceas | **Mosaicos de arbustos y herbaceas** | 4,1 |

**Hecho**: corregido **de los dos lados** (collection-01/statistics/docs/statistics.md §5.10.1), que es lo que importa, porque el
join numerador-denominador es POR NOMBRE y arreglar uno solo los habría emparejado mal sin que
ninguna compuerta lo viera. `legends.py` para el denominador (nuestro, decodifica por código)
y `factsheet_tables.R::fix_n2()` al leer los CSV del toolkit (que llegan con el nombre ya
decodificado por ese mismo archivo). **No se re-exportó nada de GEE**: los `_raw` estaban en
disco, los nueve `--check` re-decodifican sin red y pasan, `factsheet_tables.R` tarda 4,5 s.
Los cuatro cuadernos re-renderizados.

**Ningún número se movió, y el nivel 1 no se tocó** (las tres son la misma familia): el 25 % de
bosque del factsheet y todo el bloque de bosques de §5.9 están intactos. Cambió la etiqueta de
la mitad de nivel 2. Control después del arreglo: Pampa 62 % *Herbaceas*, Delta 75 %
*Herbaceas Inundables*, Puna 51 % *Mosaicos*.

**Lo que falta, y no es código**:

**Avisarle a la red.** El archivo es de ellos y lo lee todo país que decodifique la leyenda
argentina. Conviene mirar si la misma rotación está en el bloque de otro país.
**Revisar si algo ya publicado cita uno de los tres nombres**: el ATBD, láminas viejas, el
borrador del paper.