# Guía de arquitectura — para entender (y poder modificar) este proyecto

Este documento explica CÓMO está armado el sistema y, más importante,
POR QUÉ se organizó así. No es documentación "para expertos": está
pensada para que puedas modificar el código con confianza aunque
todavía estés aprendiendo a programar.

> **Estado de este documento:** describe la versión actual del ERP
> (interfaz en **PySide6**, módulo de **Inteligencia Artificial**,
> rediseño UX, tutorial interactivo y herramienta de simulación de
> ventas). Si vienes de una versión anterior de esta guía: la interfaz
> ya **no** es Tkinter, y el proyecto ya no es solo "compras → ventas".

## Mapa rápido: ¿dónde vive cada cosa?

| Carpeta / archivo                 | Qué contiene                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------- |
| `main.py`                         | Punto de entrada: crea tablas, carga datos de ejemplo, muestra login y ventana principal.      |
| `app/modelos.py`, `app/basedatos.py` | Las tablas (SQLAlchemy) y la conexión a SQLite.                                             |
| `app/logica_*.py`                 | Reglas de negocio (compras, inventario/FIFO, producción, ventas, costos, reportes, búsqueda…). |
| `app/seguridad.py`, `app/sesion.py` | Hash de contraseñas, permisos por rol (RBAC) y "quién está conectado".                        |
| `app/ia/`                         | Motores de IA: predicción de demanda, predicción de merma y reposición inteligente.            |
| `app/ui/`                         | Toda la interfaz PySide6: vistas, diálogos, design system (`widgets.py`), estilos, tutorial.   |
| `herramientas/`                   | Generador de ventas simuladas (fuera de la app; el ERP nunca lo importa).                      |
| `models/`                         | Modelos de IA ya entrenados (`.pkl`) y su `metadata.json`.                                     |
| `datos_simulados/`                | Salida de ejemplo del simulador (CSV de ventas, diagnóstico y gráfico).                        |
| `tests/`                          | Pruebas automáticas (lógica, IA y humo de interfaz).                                           |

## 1. La idea central: 3 capas (más un módulo de IA que las consume)

Casi cualquier programa que guarda información en una base de datos y
tiene una pantalla se puede pensar en 3 capas:

```
┌─────────────────────────────────────┐
│   INTERFAZ (lo que ve el usuario)    │   → carpeta app/ui/   (PySide6)
│   Botones, tablas, ventanas...       │
└───────────┬─────────────────┬────────┘
            │ llama a         │ llama a
┌───────────▼───────────┐  ┌──▼─────────────────────────┐
│   LÓGICA DE NEGOCIO   │  │   MOTORES DE IA            │
│   logica_*.py         │◄─┤   app/ia/                  │
│   "¿Qué reglas tiene  │  │   Predicen y recomiendan;  │
│    el negocio?"       │  │   nunca escriben por sí    │
│   (FIFO, RBAC, costos,│  │   solos en el negocio      │
│    reportes, búsqueda)│  └──┬─────────────────────────┘
└───────────┬───────────┘     │ leen datos de...
            │ usa objetos de..│
┌───────────▼─────────────────▼────────┐
│   MODELOS + BASE DE DATOS            │   → modelos.py, basedatos.py
│   Las tablas y cómo se guardan       │
└──────────────────────────────────────┘
```

El proyecto sigue usando **exactamente 3 capas**. La carpeta `app/ia/`
no es una cuarta capa "en medio": es un consumidor más de los datos
del negocio, que la interfaz consulta cuando quiere una predicción o
una recomendación (ver sección 9). Las funciones de `logica_*.py`
siguen hablando DIRECTAMENTE con la base de datos usando SQLAlchemy:
no hay capa "Repository" ni `Generic[T]`, que son de los conceptos que
más cuesta entender al aprender.

**Un poco de historia (útil para no confundirse con versiones viejas):**
la primera versión usaba PySide6 con 4 capas (Vista → Service →
Repository → Model). Una versión intermedia, pensada para aprender,
se simplificó a Tkinter y 3 capas. La versión actual **vuelve a
PySide6** (necesario para el overlay con transparencia real del
tutorial, las tablas ordenables, los gráficos y los cálculos de IA en
hilos aparte) **pero conserva las 3 capas simples**. Lo que se ganó al
volver a PySide6 no se pagó con más complejidad en la lógica.

## 2. ¿Por qué un archivo `logica_X.py` por módulo, y no clases?

En vez de una clase `CompraService` con métodos, `logica_compras.py`
tiene funciones sueltas: `registrar_compra()`, `listar_ordenes_compra()`,
`crear_proveedor()`, `actualizar_proveedor()`, etc.

¿Por qué? Porque estas funciones no necesitan "recordar" nada entre
llamadas (no tienen estado propio) — cada una abre su sesión de base
de datos (`nueva_sesion()`), hace su trabajo, y termina. Cuando una
función no necesita guardar estado, usar una función simple es más
fácil de leer que crear una clase solo para agrupar métodos.

Los archivos de lógica actuales son:

| Archivo                     | Responsabilidad                                                                  |
| --------------------------- | -------------------------------------------------------------------------------- |
| `logica_autenticacion.py`   | Login, logout, crear/desactivar/reactivar usuarios.                              |
| `logica_compras.py`         | Órdenes de compra, proveedores (crear y editar), últimos precios por proveedor.  |
| `logica_inventario.py`      | Lotes, movimientos, FIFO, ajustes, productos bajo mínimo, lotes por vencer, edición de producto. |
| `logica_produccion.py`      | Crear / iniciar / cerrar órdenes de producción.                                  |
| `logica_ventas.py`          | Registrar ventas, clientes (crear y editar).                                     |
| `logica_costos.py`          | Lee los costos calculados al cerrar producción (resumen y KPIs).                 |
| `logica_reportes.py`        | Arma los datos de los 5 reportes y los exporta a PDF, Excel y CSV.               |
| `logica_busqueda.py`        | Búsqueda global (solo lectura) que usa el header superior.                       |
| `logica_configuracion.py`   | Parámetros sueltos (capital inicial, datos de la empresa, progreso del tutorial).|

Esto también aplica a `logica_reportes.py`: sus funciones consultan la
base de datos y devuelven los datos listos para ser formateados — sin
guardar estado entre llamadas.

## 3. ¿Por qué SQLAlchemy con `Column` y no con `Mapped[...]`?

SQLAlchemy (la librería que conecta Python con la base de datos) tiene
dos estilos de escritura:

```python
# Estilo "moderno" (2.0 typed)
nombre: Mapped[str] = mapped_column(String(150), nullable=False)

# Estilo "clásico" — el que usa este proyecto
nombre = Column(String(150), nullable=False)
```

Ambos funcionan igual de bien. El estilo clásico es el que vas a
encontrar en el 90% de los tutoriales de SQLAlchemy en español y en
inglés, así que si necesitas buscar ayuda en internet, es más fácil
encontrar ejemplos parecidos a este código.

Las tablas del sistema (todas en `modelos.py`) son: `Usuario`,
`LogAcceso`, `Proveedor`, `OrdenCompra`, `DetalleCompra`, `Producto`,
`LoteInventario`, `MovimientoInventario`, `Receta`, `IngredienteReceta`,
`OrdenProduccion`, `Merma`, `Cliente`, `OrdenVenta`, `DetalleVenta`,
`CostoProduccion` y `ParametroSistema`. **El módulo de IA no agregó
ninguna tabla nueva**: lee las que ya existían (ver sección 9).

## 4. El flujo de un lote: FIFO explicado con un ejemplo

FIFO significa "First In, First Out": el lote que ENTRÓ primero es el
que SALE primero. Se usa tanto para producción como para ventas.

Ejemplo concreto: compras Lúpulo dos veces.

```
Lunes:    compras 5 kg de lúpulo   → se crea el LOTE-A (5 kg)
Miércoles: compras 5 kg más         → se crea el LOTE-B (5 kg)
```

Si el jueves produces una cerveza que necesita 7 kg de lúpulo, el
sistema (función `consumir_fifo` en `logica_inventario.py`) hace esto:

1. Mira los lotes disponibles ordenados por fecha: primero LOTE-A, luego LOTE-B.
2. Saca 5 kg del LOTE-A (lo deja en 0, lo marca "AGOTADO").
3. Como todavía faltan 2 kg, saca 2 kg del LOTE-B (queda con 3 kg disponibles).

Esto es EXACTAMENTE lo que hace la función `consumir_fifo()` — vale la
pena leerla con calma, tiene comentarios paso a paso. Si no alcanza el
stock, lanza `StockInsuficiente` y **no se guarda nada a medias**.

Los lotes también pueden tener **fecha de vencimiento** (opcional). La
función `lotes_proximos_a_vencer()` alimenta las alertas del Dashboard
y la campana de notificaciones del header.

## 5. ¿Dónde se decide qué puede hacer cada usuario? (RBAC)

Todo el control de permisos vive en **un solo archivo**: `seguridad.py`.
Hay dos diccionarios:

- `MODULOS_POR_ROL`: qué botones del menú lateral ve cada rol.
- `ACCIONES_POR_ROL`: dentro de un módulo, qué puede hacer cada rol
  (por ejemplo, "VENTAS" puede "crear" ventas, pero no "cerrar" órdenes
  de producción).

Y dos funciones para consultarlos: `modulos_visibles(rol)` y
`puede(rol, modulo, accion)`.

Los módulos del menú son: `dashboard`, `compras`, `inventario`,
`produccion`, `ventas`, `costos` (se muestra como **«Reportes de
ventas»**), `centro_inteligencia` y `admin`. Un detalle importante del
módulo de IA: la **Predicción de Demanda ya no es un módulo aparte**
del menú; vive como pestaña dentro de `centro_inteligencia`, y los roles
que antes tenían acceso a "predicción" ahora lo tienen ahí. Las acciones
propias de ese módulo son `ver`, `predecir`, `entrenar` (definida solo
para ADMIN) y `generar_compra` (ADMIN y COMPRAS). Ojo: hoy la acción
`entrenar` solo se comprueba en el botón de entrenar el modelo de
**merma**; el botón «Entrenar / actualizar modelo» de la pestaña de
demanda (`vista_prediccion.py`) no la consulta todavía (ver sección 17).

Si algún día necesitas un rol nuevo, o cambiar qué puede hacer un rol
existente, **solo tienes que tocar `seguridad.py`** — ningún otro
archivo necesita cambiar. Y esto no es solo teoría: estas partes ya se
apoyan en esas mismas funciones, sin tener un segundo sistema de permisos:

- el **sidebar** (qué botones aparecen);
- los **botones 🧠** que enlazan a la IA desde Inventario, Compras,
  Producción y Ventas (solo aparecen si el rol ve `centro_inteligencia`);
- las **acciones rápidas** y tarjetas del Dashboard;
- los **tutoriales** (qué recorridos y qué pasos tiene sentido mostrar);
- los **reportes** (cada módulo ofrece su propio botón «📊 Reporte»).

## 6. El ciclo de vida de una orden de producción

```
crear_orden()        →  estado: INICIADA
       ↓
iniciar_proceso()    →  estado: EN_PROCESO
       ↓
cerrar_orden()        →  estado: COMPLETADA
                          Y ADEMÁS, en un solo paso:
                            1. descuenta los insumos (FIFO)
                            2. registra la merma (si hubo)
                            3. crea el lote de producto terminado
                            4. calcula costo total, costo unitario y margen
```

Todo el paso 3 (`cerrar_orden`) vive en `logica_produccion.py`. Es la
función más larga del proyecto, pero está dividida con comentarios
numerados (1, 2, 3, 4) que corresponden exactamente a los 4 pasos de
arriba.

**Detalle de la pantalla de cierre:** el diálogo `VentanaCerrarOrden`
**sugiere la merma** como «cantidad planeada − cantidad real producida»
mientras el usuario escribe la cantidad real, y deja de sugerir en
cuanto el usuario escribe su propio valor (se respeta lo que puso).

**Conexión con la IA:** la merma *esperada* (antes de producir) no sale
de este diálogo, sino del motor de merma: se consulta desde el Centro de
Inteligencia y desde el botón «🧠 Merma esperada» de Producción (ver
sección 10). La lógica de `cerrar_orden()` no depende de la IA.

## 7. ¿Cómo se conecta una pantalla con la lógica de negocio?

Ejemplo real, con el botón "＋ Nueva venta" en `vista_ventas.py`:

```python
# 1) El botón se crea en la barra de la vista, solo si el rol puede crear ventas
if puede_crear:
    barra.agregar_boton("＋  Nueva venta", self._abrir_nueva_venta)

# 2) Esa ventana arma una lista de productos en pantalla, y cuando el
#    usuario presiona "Registrar venta", llama a la función de lógica:
orden = registrar_venta(cliente_id=..., items=self.items_agregados,
                        usuario_id=sesion_actual.usuario_id)

# 3) registrar_venta() (en logica_ventas.py) es la que realmente
#    habla con la base de datos. Si falta stock lanza StockInsuficiente
#    y la pantalla muestra el error, sin haber guardado nada.
```

Fíjate que `vista_ventas.py` NUNCA escribe código de SQLAlchemy
directamente para guardar la venta — solo junta los datos que el
usuario ingresó y se los pasa a `logica_ventas.registrar_venta()`. En
PySide6 el "cuando el usuario hace clic" se expresa con **señales**
(`boton.clicked.connect(funcion)`), que es lo que hace `agregar_boton`
por dentro. Esta separación es útil porque, si algún día cambias de
librería de interfaz, casi no tendrías que tocar los `logica_*.py`
(de hecho ya pasó una vez: Tkinter ⇄ PySide6).

Dos patrones de las vistas que conviene reconocer:

- **Carga diferida (lazy):** `ventana_principal.py` no construye todas
  las vistas al arrancar; guarda solo una *fábrica* por módulo y crea la
  vista la primera vez que el usuario navega a ella.
- **`tutorial_targets`:** cada vista expone un diccionario con sus
  controles reales (por ejemplo `tutorial_targets["btn_reporte"]`), que
  usa el tutorial interactivo (ver sección 12).

## 8. El módulo de Reportes: cómo funciona

Los reportes ya **no** son una pantalla aparte (`vista_reportes.py` no
existe): cada módulo operativo tiene su botón **«📊 Reporte»**, que
abre un diálogo (`app/ui/dialogo_reporte.py`) ya fijado al reporte de
ese módulo. El patrón sigue siendo el de 3 capas:

```
Botón «📊 Reporte» en Compras / Inventario / Producción / Ventas / Costos
  └─ abre DialogoReporte(modulo=...)   →  vista previa en tabla + KPIs
        │   el usuario elige el formato y "Guardar"
        ▼
logica_reportes.py
  └─ datos_<tipo>()  consulta la BD y devuelve un dict estándar
        │
        ├─► guardar_pdf()   →  archivo .pdf   (ReportLab)
        ├─► guardar_xlsx()  →  archivo .xlsx  (openpyxl)
        └─► guardar_csv()   →  archivo .csv
```

Hay **5 reportes**: costos, stock, compras, ventas y producción. Todos
los `datos_*()` devuelven la misma estructura:

```python
{"titulo": str, "columnas": [...], "filas": [[...], ...], "kpis": [{"etiqueta": ..., "valor": ...}, ...]}
```

Como PDF, Excel y CSV parten de ese mismo diccionario, **agregar un
formato nuevo** es escribir una función generadora más; la consulta a
la BD no cambia. Y **agregar un reporte nuevo** es escribir un
`datos_<tipo>()` y registrarlo en `REPORTES` / `NOMBRES_LEGIBLES`.

Detalles útiles del PDF: se genera siempre en **vertical (A4)**, con
anchos de columna calculados según el contenido y texto que hace salto
de línea dentro de su celda. Además se puede **guardar donde quieras**
con el diálogo nativo de Qt (`QFileDialog`), y abrir el archivo
generado con la aplicación del sistema.

## 9. El módulo de Inteligencia Artificial (`app/ia/`)

Es la parte más nueva del proyecto y la que más conviene entender antes
de tocarla. Tiene **tres motores** que se apoyan uno en otro:

```
 Predicción de DEMANDA  ──┐
 (¿cuánto se venderá?)    ├──►  REPOSICIÓN INTELIGENTE
 Predicción de MERMA    ──┤     (¿cuánto insumo conviene comprar?)
 (¿cuánto se perderá?)    │
 Stock actual de insumos ─┘
```

### 9.1 Un patrón de archivos que se repite

Cada motor de predicción se divide en los mismos pasos, cada uno en su
propio archivo, para que sepas dónde buscar:

| Paso                   | Demanda                   | Merma                    | Qué hace                                                        |
| ---------------------- | ------------------------- | ------------------------ | --------------------------------------------------------------- |
| Datos                  | `demanda_data.py`         | `merma_data.py`          | Consulta las tablas del ERP y arma el DataFrame.                |
| Características        | `demanda_features.py`     | `merma_features.py`      | Crea variables (lags, promedios, calendario) **sin fuga de datos futuros**. |
| Modelos                | `demanda_model.py`        | `merma_model.py`         | XGBoost + un *baseline* simple, con la misma interfaz `fit/predict`. |
| Entrenamiento          | `demanda_training.py`     | `merma_training.py`      | Pipeline completo, división temporal 70/15/15, guarda modelo y metadata. |
| Predicción             | `demanda_prediction.py`   | `merma_prediction.py`    | Usa el modelo entrenado y devuelve un resultado listo para mostrar. |
| Métricas               | `demanda_metrics.py`      | (reutiliza `demanda_metrics.py`) | MAE, RMSE y MAPE (son genéricas, sirven para ambos).    |

Ideas que sostienen todo el módulo:

- **Sin data leakage.** La división es cronológica (nunca aleatoria), y
  las características solo usan información disponible *antes* del día
  (o la orden) que se predice.
- **Siempre hay un baseline.** Cada modelo de IA se compara contra uno
  muy simple (promedio de los últimos 7 días; promedio histórico de la
  receta). Si el modelo de IA no le gana al baseline, eso también es un
  resultado que vale la pena mirar.
- **Degradación elegante.** Si no hay suficiente historial (o no hay
  modelo entrenado, o el modelo falla al cargarse), el motor **no se
  rompe**: cae al baseline y lo dice en el campo `mensaje`/`advertencia`
  del resultado, que la interfaz muestra al usuario. Los umbrales
  están al inicio de cada `*_data.py` (`MIN_DIAS_HISTORIAL`,
  `MIN_DIAS_BASELINE`, `MIN_ORDENES_ML`, `MIN_ORDENES_BASELINE`).
- **Los motores predicen, las personas deciden.** Nada de `app/ia/`
  crea una compra ni cierra una producción por sí solo.

### 9.2 Predicción de demanda

- Consulta `OrdenVenta` + `DetalleVenta` + `Producto` y arma una serie
  diaria por producto (`obtener_serie_diaria`).
- Características: calendario (`dia_semana`, `mes`, `es_fin_semana`…),
  rezagos (`lag_1`, `lag_7`, `lag_14`, `lag_28`) y ventanas móviles
  (`media_7/14/28`, `std_7`).
- Se entrena **un solo XGBoost con todos los productos juntos** (no un
  modelo por producto). Como usa los rezagos de cada serie, se adapta
  al nivel de venta de cada producto.
- `predecir_demanda(producto_id, horizonte)` (horizontes de 7, 14 o 30
  días) devuelve fechas, cantidades previstas, total, promedio diario,
  mínimo, máximo, historial y las métricas del último entrenamiento.
- `entrenar()` acepta un `callback_progreso` para que la interfaz pueda
  mostrar el avance mientras entrena.

### 9.3 Predicción de merma

- Cada fila del dataset es **una orden de producción completada**; la
  variable a predecir es `merma_pct` (porcentaje de merma sobre lo
  planeado).
- Las características son de tipo *expanding*: la orden número 5 de una
  receta solo puede usar el promedio de merma de las órdenes 1 a 4.
- `predecir_merma(receta_id, cantidad_planeada, fecha)` devuelve el
  porcentaje esperado, la cantidad de merma, el rendimiento esperado, el
  promedio histórico de esa receta y una **alerta** si lo previsto supera
  claramente lo histórico.
- Si una receta es nueva (sin producciones previas) usa el promedio
  global del sistema y lo avisa.

### 9.4 Reposición inteligente (el motor "prescriptivo")

`reposicion.py` combina demanda esperada, merma esperada y stock
disponible para recomendar **cuánto insumo reponer**, con una fórmula
deliberadamente simple y transparente:

```
Cantidad a reponer = Demanda esperada en el periodo de cobertura
                   + Stock de seguridad
                   - Stock disponible
```

- La demanda de cada insumo se obtiene traduciendo la demanda prevista
  de cada producto terminado a través de su **receta**, inflada por la
  merma esperada de esa receta.
- Si un insumo no está ligado a ninguna receta con pronóstico, se usa
  su **consumo histórico** de los últimos 90 días.
- El stock de seguridad se calcula con el consumo diario y su
  variabilidad (cubriendo, por defecto, 5 días extra).
- Cada recomendación trae **prioridad** (ALTA / MEDIA / BAJA), el
  **origen** de la demanda (`modelo_demanda`, `historico` o
  `sin_datos`) y un **motivo en texto plano**, para que el usuario
  entienda de dónde sale el número antes de decidir.
- `calcular_recomendacion_individual(insumo_id)` recalcula uno solo
  (la usa el detalle de producto); parte del cálculo sigue siendo global
  porque la demanda de un insumo depende de todas las recetas que lo usan.

### 9.5 Persistencia de modelos

Los modelos entrenados se guardan con `joblib` en `models/demanda/` y
`models/merma/` (un `modelo_xgboost.pkl`, un `modelo_baseline.pkl` y un
`metadata.json` con la fecha, las métricas y las características).
`persistencia_modelos.py` se encarga de que, si el modelo fue guardado
con **otra versión de xgboost**, se **re-guarde una sola vez** con la
versión instalada en esa máquina — así el aviso de versión no aparece en
cada apertura del Centro de Inteligencia. No reentrena nada: solo
reexporta los mismos pesos.

### 9.6 `resultados_recientes.py`: la "memoria" de los motores

Es un pequeño diccionario **en memoria** (no toca la base de datos ni
el disco) donde cada motor deja su último resultado (`reposicion:<id>`,
`demanda:<id>`, `merma:<id>`). Sirve para que otras pantallas —por
ejemplo la pestaña «🧠 Inteligencia» del detalle de producto— muestren
lo último calculado **sin volver a correr el motor**, siempre junto a la
fecha y hora del cálculo. Se pierde al cerrar el programa, a propósito.

### 9.7 Cálculos pesados sin congelar la ventana

Entrenar y predecir toma segundos. Para que la interfaz no se cuelgue,
`widgets.py` ofrece dos ayudantes:

- `ejecutar_con_carga(contenedor, funcion, mensaje=...)`: muestra el
  indicador de carga y corre la función (síncrona, para tareas cortas).
- `ejecutar_en_hilo(contenedor, funcion, al_terminar, ...)`: corre la
  función en un **hilo aparte** (`QThread`) mientras el overlay se anima;
  cuando termina, llama a `al_terminar(resultado, error)` ya en el hilo
  de la interfaz. **La función que corre en el hilo no debe tocar
  widgets**: solo calcular y devolver datos.

## 10. El Centro de Inteligencia y cómo se integra con el resto

`vista_centro_inteligencia.py` reúne los resultados de la IA en un solo
lugar, en cuatro pestañas:

1. **📦 Reposición inteligente** — qué insumos reponer y cuánto; con el
   botón «Generar orden de compra con este insumo», que abre el
   formulario real de Compras ya prellenado (el usuario decide si la
   guarda).
2. **🍺 Predicción de merma** — estimar el rendimiento de una producción
   antes de planearla o cerrarla.
3. **🔮 Demanda prevista (resumen)** — demanda estimada de todos los
   productos a 7/14/30 días, de un vistazo.
4. **📈 Predicción de demanda (detalle)** — la vista `vista_prediccion.py`
   (gráfico histórico + predicción, KPIs, tabla diaria, interpretación y
   el estado del modelo con el botón de entrenar).

Esta vista **no reemplaza** a los módulos tradicionales: concentra sus
resultados y deja que el usuario decida. Desde los módulos operativos
hay enlaces 🧠 (solo para roles con acceso): Inventario → «Riesgo de
quiebre», Compras → «Reposición recomendada», Producción → «Merma
esperada», Ventas → «Demanda prevista». Además, en el **detalle de
producto** hay una pestaña «🧠 Inteligencia» que muestra la reposición
sugerida (si es un insumo) o la demanda y merma esperadas (si es un
producto terminado).

## 11. El rediseño de la interfaz (UX)

El rediseño siguió un flujo *estado → problema → explicación → acción →
resultado*: en vez de solo mostrar tablas, la pantalla dice cómo está
la operación, qué requiere atención y qué se puede hacer ahora.

- **Header superior** (`header.py`): título y *breadcrumb* del módulo (y
  de la pestaña interna activa), **búsqueda global** (atajo **Ctrl+K**),
  campana de notificaciones y usuario. La búsqueda llama a
  `logica_busqueda.buscar_global()` (productos, lotes, producción,
  compras, proveedores, ventas y clientes; mínimo 2 caracteres, hasta 5
  resultados por categoría) y, al elegir uno, lleva a la fila exacta
  resaltándola sin esconder el resto de la tabla.
- **Sidebar por secciones:** Inicio, OPERACIÓN (Compras, Inventario,
  Producción, Realizar ventas), ANÁLISIS (Reportes de ventas),
  INTELIGENCIA (Centro de Inteligencia) y ADMINISTRACIÓN. Es
  desplazable si la ventana es baja. El orden y los nombres viven en
  `DEFINICION_MODULOS` de `ventana_principal.py`.
- **Dashboard** (`vista_dashboard.py`): indicadores generales, tarjetas
  clickeables **«Requiere tu atención»** (stock crítico y lotes por
  vencer, con carga progresiva y botón «ver más») y **«Acciones
  rápidas»** filtradas por rol. Usa solo consultas baratas: el análisis
  pesado de IA **no** se recalcula en cada visita.
- **Detalle de producto** (`vista_detalle_producto.py`): se abre con doble
  clic en una fila de *Stock Actual*; tiene pestañas Información (donde
  se **edita** el producto, si el rol tiene permiso), Lotes, Movimientos, Ventas e Inteligencia.
  Es una página más del mismo `QStackedWidget` de Inventario, así que
  «‹ Volver» regresa al instante y con el filtro donde lo dejaste.
- **Design system** (`widgets.py`): `EncabezadoModulo`, `TarjetaKPI`,
  `TarjetaAccion`, `BarraBusqueda`, `TablaDatos` (filas alternas,
  ordenable, filtro, resaltado), `EstadoVacio`, `Migaja`,
  `CampoFormulario`, `SeccionFormulario`, `MensajeEstado`,
  `DialogoConfirmacion`, `BotonAyuda`, `BarraEstado` e `IndicadorCarga`.
  Antes de escribir un componente nuevo, revisa si ya existe aquí.
- **Validación en línea:** `CampoFormulario` valida mientras se escribe
  (obligatorio, número, sin negativos…) y `conectar_boton_a_validez()`
  bloquea el botón de guardar hasta que todo esté correcto.
- **Indicador de carga:** `IndicadorCarga` es un overlay semitransparente
  con mensaje y barra de progreso indeterminada. Se muestra al cambiar
  de módulo desde el sidebar y durante los cálculos de IA.
- **Atajos:** **F5** refresca la vista activa; **Ctrl+K** enfoca la
  búsqueda global.

## 12. El módulo de tutorial interactivo: cómo funciona

Vive en `app/ui/tutorial*.py`, dividido en 4 archivos con una única
responsabilidad cada uno:

| Archivo                   | Responsabilidad                                                                 |
| ------------------------- | -------------------------------------------------------------------------------- |
| `tutorial_data.py`        | **Contenido declarativo**: la lista de pasos de cada tutorial, el guardado del progreso del usuario y los textos de ayuda contextual. Agregar o cambiar un tutorial es, casi siempre, solo tocar este archivo. |
| `tutorial_overlay.py`     | **Motor visual**: oscurece la pantalla alrededor del control que se explica (velo semitransparente con un "hueco" hecho con `setMask()`) y muestra la tarjeta con el texto. No sabe nada de "Compras" ni de "roles" — solo sabe resaltar un widget. |
| `tutorial.py`             | **Orquestador**: recorre los pasos con el overlay, navega entre módulos y pestañas, y contiene el panel «❓ Ayuda y tutorial» (Centro de Ayuda). |
| `tutorial_practice.py`    | **Modo práctico** de Compras: el usuario realiza las acciones de verdad sobre el formulario real («Nueva orden»), con una lista de verificación; detecta lo que hace y avanza solo, **sin duplicar lógica ni crear datos de demostración**. |

Hay un **tour general** (se muestra automáticamente en el primer
ingreso de cada usuario, se puede omitir y se puede reabrir desde el
botón «❓ Ayuda y tutorial») y un recorrido por módulo: Compras,
Inventario, Producción, Ventas, Costos, Centro de Inteligencia y
Reportes. También hay botones «?» de ayuda contextual (por ejemplo,
«¿Cómo se calculan los costos?»).

**¿Cómo sabe el tutorial qué widget resaltar?** Cada paso resuelve su
objetivo con una función (`target`) que recibe un contexto con la
ventana principal, la vista actual y el diálogo abierto (si lo hay).
Normalmente pide un control por nombre a `self.tutorial_targets` de la
vista (por ejemplo `tutorial_targets["btn_reporte"]`). Si el control no
existe (porque el rol actual no tiene permiso para él), el paso se
muestra sin resaltar nada, en vez de romper la app.

**¿Cómo respeta los roles?** Reutiliza `seguridad.modulos_visibles(rol)`
— la misma función que decide qué botones aparecen en el sidebar — para
filtrar qué tutoriales y qué pasos tienen sentido para cada usuario.

**¿Dónde se guarda el progreso?** En la misma tabla `ParametroSistema`
que ya usa el resto del sistema (ver `logica_configuracion.py`), como
un JSON por usuario y por tutorial. No se creó ninguna tabla nueva.

**Para agregar un tutorial de un módulo nuevo**, solo hace falta:
1. Exponer los controles relevantes en `self.tutorial_targets` desde
   la vista de ese módulo.
2. Escribir la lista de `PasoTutorial` en `tutorial_data.py`, registrarla
   en `TUTORIALES_MODULO` y añadir su clave a `ORDEN_CENTRO_AYUDA`.

No hace falta tocar `tutorial.py` ni `tutorial_overlay.py`.

## 13. ¿Y de dónde salen los colores?

Todo el color de la aplicación (el ámbar de los botones primarios, el
verde bosque del sidebar, el rojo de las alertas...) vive en **un solo
archivo**: `app/ui/estilos.py`. Cada pantalla no define sus propios
colores; en vez de eso, usa "clases" con nombre que apuntan a los
colores definidos ahí.

Con PySide6 esto se hace con una **hoja de estilos QSS** global y una
propiedad dinámica llamada `clase`. Por ejemplo:

```python
poner_clase(boton, "secundario")   # equivale a un estilo con nombre
```

`poner_clase()` marca el widget y el selector QSS
`[clase="secundario"]` de `estilos.py` lo recoge. Si quieres cambiar
el tema completo de la app (por ejemplo, probar con un azul en vez del
ámbar), solo tienes que cambiar las constantes `COLOR_*` al principio de
`estilos.py` — no hace falta tocar ninguna otra pantalla.

## 14. Datos de ejemplo y simulación de ventas

**Datos de ejemplo.** La primera vez que se ejecuta el programa,
`datos_iniciales.py` crea `cervecera.db` y la llena. Tiene dos partes:
una escrita a mano (los 6 usuarios de prueba y un núcleo pequeño y fácil
de leer) y otra **generada por código** para que cada tabla tenga al
menos 50 filas. Si ya existen usuarios, no hace nada.

**Simulador de ventas** (`herramientas/`). Para que el módulo de
Predicción de Demanda tenga un historial largo con el que probarse, hay
una herramienta que **genera ventas simuladas** para todos los productos
terminados. No forma parte de la aplicación (el ERP nunca la importa) y
se ejecuta desde la línea de comandos:

```bash
python -m herramientas.generar_ventas_simuladas --dias 730 --solo-csv          # vista previa, no toca la BD
python -m herramientas.generar_ventas_simuladas --dias 730 --con-inventario --reemplazar
python -m herramientas.generar_ventas_simuladas --limpiar                       # deshacer
```

| Archivo                         | Qué hace                                                                        |
| ------------------------------- | -------------------------------------------------------------------------------- |
| `volatilidad_mercado.py`        | Calibra un "índice de volatilidad" a partir de acciones de cerveceras reales (Backus, CCU, Ambev, etc.; usa `yfinance` y cae a perfiles de respaldo si no hay internet). Cachea el resultado en `cache_volatilidad.json`. |
| `simulador_demanda.py`          | Genera la serie diaria: `D_t ~ Poisson(λ_t)`, con tendencia, estacionalidad semanal y anual, festivos peruanos/cusqueños, promociones y un choque GARCH. |
| `generar_ventas_simuladas.py`   | Programa principal: arma las configuraciones, inserta en la BD, exporta CSV y gráfico. |

Dos reglas de seguridad: las órdenes simuladas llevan `[SIMULADO]` en
`observaciones` y los lotes el prefijo `SIM-`, así que `--limpiar` las
borra sin tocar los datos de ejemplo reales.

**Advertencia metodológica importante:** del mercado bursátil se toma
prestada la *estructura del ruido* (magnitud, agrupamiento de
volatilidad y colas pesadas), **no el nivel** de la serie. Los datos
siguen siendo **sintéticos**: sirven para verificar que el pipeline de
IA funciona, no para demostrar su desempeño en producción. La
explicación completa está en `herramientas/README_SIMULACION.md`.

## 15. Pruebas automáticas

Las pruebas están en `tests/`:

| Archivo                          | Qué cubre                                                                 |
| -------------------------------- | ------------------------------------------------------------------------- |
| `test_logica.py`                 | Lógica de negocio: hash y login, gestión de usuarios, lotes y FIFO, alertas de stock y vencimiento, compras, ventas y ciclo de producción (52 pruebas). |
| `test_persistencia_modelos.py`   | Carga y auto-migración de modelos XGBoost persistidos.                    |
| `test_smoke_ui.py`               | "Pruebas de humo" de la interfaz en modo `offscreen` (vistas, detalle de producto, validación en línea, header). |
| `test_demanda_recursiva.py`      | Pronóstico de demanda a varios días (ver la nota siguiente).              |

Se corren con `pytest`. Para las pruebas de interfaz sin pantalla, usa
`QT_QPA_PLATFORM=offscreen pytest`.

> **Nota sobre `test_demanda_recursiva.py`:** este archivo describe el
> comportamiento *deseado* del pronóstico a 7/14/30 días (que cada día
> futuro use la predicción del día anterior en sus rezagos) e importa
> una función (`features_de_un_dia`) que **todavía no existe** en
> `demanda_features.py`; por eso hoy falla al importarse. En el código
> actual, `construir_features_futuro()` rellena los días futuros con
> `0.0` y el modelo predice todo de una vez, así que a partir del 2.º
> día los rezagos futuros valen cero. Es la principal deuda técnica
> conocida del módulo de IA: corregirla mejoraría la demanda proyectada
> y, con ella, la reposición de insumos.

## 16. Cosas que se simplificaron a propósito

| Se decidió...                                          | En vez de...                                | Por qué                                                                                                                                                                                    |
| ------------------------------------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Hash de contraseñas con `hashlib` (librería estándar)  | Argon2 (librería externa)                   | Menos dependencias que instalar; PBKDF2 es un algoritmo real y ampliamente usado (es el que usa Django por defecto).                                                                       |
| Funciones sueltas en `logica_*.py`                     | Clases `Service` + `Repository` genéricas   | Menos capas, menos conceptos avanzados (generics) que aprender.                                                                                                                            |
| SQLAlchemy estilo `Column` clásico                     | Estilo `Mapped[...]` (SQLAlchemy 2.0 typed) | Es el estilo que más se enseña en tutoriales; más fácil de buscar ayuda.                                                                                                                   |
| SQLite (un archivo `cervecera.db`)                     | MySQL / PostgreSQL                          | No hay que instalar ni configurar un servidor. Cambiarlo es, en teoría, cambiar `RUTA_BASE_DATOS` en `basedatos.py`.                                                                       |
| Un archivo `modelos.py` con todas las tablas           | Un archivo por tabla                        | Para un proyecto de este tamaño, es más fácil encontrar todo en un solo lugar. Si el proyecto creciera mucho más, dividirlo volvería a tener sentido.                                      |
| ReportLab + openpyxl + CSV, generados por separado     | Gráficos embebidos en los reportes          | Separar la generación del reporte de la interfaz es más simple: el usuario guarda el archivo y lo abre con el visor que prefiera. (Matplotlib solo se usa en el gráfico de Predicción.)     |
| Un solo modelo XGBoost de demanda para todos los productos | Un modelo por producto                  | Más datos para entrenar, un solo archivo `.pkl` que mantener, y los rezagos ya adaptan el nivel de cada producto.                                                                           |
| Reposición con una fórmula simple y un motivo en texto | Optimización avanzada (EOQ, programación lineal…) | El usuario puede entender y auditar el número antes de decidir.                                                                                                                       |
| Resultados de IA en memoria (`resultados_recientes.py`)| Una tabla nueva en la base de datos         | Son "fotos del momento": se recalculan cuando se necesitan y no hay que migrar el esquema.                                                                                                  |
| Progreso del tutorial en `ParametroSistema`            | Una tabla `ProgresoTutorial`                | Reutiliza una tabla que ya existía; cero migraciones.                                                                                                                                      |

## 17. Ideas para seguir extendiendo el proyecto

Estas son mejoras que puedes intentar tú mismo para practicar
(de más fácil a más difícil). Varias ideas de versiones anteriores ya
se hicieron: editar productos, más tipos de reporte, y avisos de stock
bajo (campana del header y Dashboard).

1. **Historial de compras/ventas por cliente o proveedor** (un filtro
   en la pestaña de órdenes).
2. **Filtros de fecha en los reportes** (hoy cada reporte incluye todo
   el historial; `datos_*()` podrían recibir `desde` y `hasta`).
3. **Reportes con gráficos incrustados en el PDF** (ReportLab soporta
   gráficos de barras nativamente con `reportlab.graphics.charts`).
4. **Corregir el pronóstico recursivo de demanda** (ver la nota de la
   sección 15) — es la mejora con más impacto en la calidad de la IA.
5. **Un modelo de demanda por producto** o incluir `producto_id` /
   festivos como característica, y comparar contra el modelo global.
6. **Pendientes de la lista de rediseño UX:** badges de estado aún más
   consistentes, atajos de teclado adicionales, un simulador de
   escenarios y un asistente en lenguaje natural.
7. **Aplicar el permiso `entrenar` también al modelo de demanda** (hoy
   solo protege el botón de merma) y **reentrenar de forma programada**
   (hoy se entrena a mano desde la interfaz).
8. **Pruebas para reportes, búsqueda global y motores de IA** (las
   pruebas actuales cubren sobre todo la lógica de negocio y la interfaz).