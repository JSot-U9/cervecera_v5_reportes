# ERP Cervecería del Valle Sagrado

Sistema de gestión (ERP) de escritorio para la Cervecería del Valle
Sagrado (Cusco), escrito en **Python + PySide6 + SQLAlchemy**, con un
módulo de **Inteligencia Artificial** (XGBoost) para predecir demanda y
merma y recomendar reposición de insumos.

Esta es una versión **escrita para ser fácil de leer, modificar y
mantener por una sola persona**, incluso si recién está aprendiendo a
programar. Si quieres entender CÓMO está armado el proyecto (y por
qué), lee primero **[`GUIA_ARQUITECTURA.md`](GUIA_ARQUITECTURA.md)** —
está pensada como una guía de estudio, no solo como referencia técnica.

## ¿Qué hace el sistema?

Automatiza el ciclo completo de una cervecera artesanal y, encima de
él, ayuda a decidir qué comprar y cuánto producir:

```
Compras  →  Inventario (por lotes, regla FIFO)  →  Producción (con receta)
                                                          ↓
                                              Costos (calculados solos)
                                                          ↑
                                                       Ventas
                                                          ↓
                                            Reportes (PDF / Excel / CSV)

   Centro de Inteligencia (IA):  Demanda prevista + Merma esperada
                                 └──►  Reposición recomendada de insumos
                                       (el usuario decide si genera la compra)
```

## Módulos incluidos

| Módulo (menú lateral)         | Qué permite hacer                                                                                                  |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Ingreso                       | Login con usuario/contraseña, control de acceso por rol (RBAC)                                                     |
| Inicio (Dashboard)            | Indicadores generales, tarjetas «Requiere tu atención» (stock crítico, lotes por vencer) y acciones rápidas por rol |
| Compras                       | Órdenes de compra a proveedores (actualiza el stock) y gestión de proveedores (crear y editar)                     |
| Inventario                    | Stock actual, lotes FIFO, movimientos, catálogo de productos, ajustes de stock y **detalle de producto** (doble clic) |
| Producción                    | Crear / iniciar / cerrar órdenes de producción según una receta; registra merma y calcula costos                   |
| Realizar ventas               | Registrar ventas a clientes (descuenta stock por FIFO) y gestión de clientes (crear y editar)                      |
| Reportes de ventas (`costos`) | Costo real y margen de cada lote producido                                                                         |
| Centro de Inteligencia        | Reposición inteligente, predicción de merma, demanda prevista (resumen) y predicción de demanda (detalle)          |
| Administración                | Usuarios (crear, desactivar, reactivar, asignar roles), datos de la empresa y registro de accesos (solo ADMIN)     |
| ❓ Ayuda y tutorial            | Tour general y recorridos por módulo, con práctica guiada en Compras                                               |

Además, **cada módulo operativo tiene un botón «📊 Reporte»** que genera
el reporte correspondiente (costos, stock, compras, ventas o
producción) con vista previa en tabla y exportación a **PDF**
(ReportLab), **Excel** (openpyxl) o **CSV**.

## Novedades respecto a versiones anteriores

- **Interfaz migrada a PySide6.** Ya no es Tkinter: tablas ordenables,
  overlay con transparencia real para el tutorial y cálculos pesados en
  hilos aparte para no congelar la ventana.
- **Módulo de IA (`app/ia/`).** Predicción de demanda por producto
  (7, 14 o 30 días), predicción de merma por receta y reposición
  inteligente de insumos, con modelos XGBoost comparados contra un
  *baseline* simple. Reúne todo en el **Centro de Inteligencia** y lo
  enlaza (🧠) desde Inventario, Compras, Producción y Ventas.
  Ver la sección [Módulo de IA](#módulo-de-ia-centro-de-inteligencia).
- **Rediseño UX.** Header superior con título, *breadcrumb*, **búsqueda
  global (Ctrl+K)** y campana de notificaciones; menú lateral agrupado
  (OPERACIÓN / ANÁLISIS / INTELIGENCIA / ADMINISTRACIÓN); Dashboard
  accionable; pantalla de **detalle de producto** con pestañas
  (Información, Lotes, Movimientos, Ventas, Inteligencia); componentes
  nuevos en el design system (estados vacíos, tarjetas de acción,
  migas de pan).
- **Validación en línea** en los formularios: los errores aparecen
  mientras se escribe y el botón de guardar se bloquea hasta corregirlos.
- **Indicador de carga** al cambiar de módulo y durante los cálculos de IA.
- **Tutorial interactivo real:** resalta los controles verdaderos de la
  pantalla, se puede omitir y reabrir, respeta los roles y guarda el
  progreso de cada usuario. Incluye una práctica guiada en Compras que
  usa el formulario real (sin crear datos de demostración).
- **Reportes ampliados:** 5 tipos de reporte, tres formatos de
  exportación (PDF / Excel / CSV) y vista previa en tabla antes de guardar.
- **Edición** de proveedores, clientes y productos (antes solo se podía crear).
- **Datos de la empresa configurables** (Administración → Empresa):
  aparecen en los reportes y en el título de la ventana.
- **Simulador de ventas** (`herramientas/`) para probar la predicción de
  demanda con un historial largo (ver [más abajo](#simulación-de-ventas-para-probar-la-predicción)).
- **Datos de ejemplo ampliados**: cada tabla del sistema arranca con al
  menos 50 filas.

## Instalación

Necesitas Python 3.10 o superior.

```bash
# 1) Crear un entorno virtual (recomendado, no obligatorio)
python -m venv venv
source venv/bin/activate        # en Windows: venv\Scripts\activate

# 2) Instalar las dependencias
pip install -r requirements.txt
```

Las dependencias incluyen:

| Paquete                 | Para qué se usa                                                          |
| ----------------------- | ------------------------------------------------------------------------ |
| `PySide6`               | Framework GUI de escritorio (Qt6)                                        |
| `SQLAlchemy`            | Conexión y ORM de la base de datos (SQLite)                              |
| `reportlab`             | Generación de reportes en formato PDF                                    |
| `openpyxl`              | Exportación de datos a archivos Excel (.xlsx)                            |
| `pytest`                | Ejecución de las pruebas automáticas                                     |
| `xgboost`               | Modelos de predicción de demanda y de merma                              |
| `scikit-learn`          | Utilidades de aprendizaje automático                                     |
| `pandas`, `numpy`       | Preparación de datos y características de los modelos                    |
| `joblib`                | Guardar y cargar los modelos entrenados                                  |
| `matplotlib`            | Gráfico de histórico + predicción en la pantalla de Predicción de demanda |
| `yfinance` *(opcional)* | Solo para el simulador de ventas; si falta, usa perfiles de respaldo     |

```bash
# 3) Ejecutar el programa
python main.py
```

La primera vez que se ejecuta, el programa crea automáticamente el
archivo `cervecera.db` (la base de datos, ignorada por Git) y lo llena
con datos de ejemplo. El conjunto completo incluye, entre otros: 51
usuarios (6 de prueba, ver abajo, más usuarios de relleno), 51
proveedores, 120 productos (53 insumos y 67 productos terminados), 53
clientes, 67 recetas, 51 compras, 72 órdenes de producción (con lotes
completados, algunos «EN_PROCESO» y otros recién «INICIADA»), 103 ventas,
los costos de producción ya calculados y un capital inicial de referencia
de S/ 25,000.

## Usuarios de prueba

| Usuario    | Contraseña | Rol             |
| ---------- | ---------- | --------------- |
| admin      | admin123   | ADMIN (ve todo) |
| compras    | compras123 | COMPRAS         |
| inventario | inv123     | INVENTARIO      |
| produccion | prod123    | PRODUCCION      |
| ventas     | ventas123  | VENTAS          |
| costos     | costos123  | COSTOS          |

Qué módulos ve cada rol (todos ven Inicio):

| Rol        | Módulos visibles                                                        |
| ---------- | ----------------------------------------------------------------------- |
| ADMIN      | Todos                                                                   |
| COMPRAS    | Compras, Centro de Inteligencia                                         |
| INVENTARIO | Inventario                                                              |
| PRODUCCION | Producción, Inventario (solo lectura), Centro de Inteligencia           |
| VENTAS     | Realizar ventas, Centro de Inteligencia                                 |
| COSTOS     | Reportes de ventas, Centro de Inteligencia                              |

Los permisos completos (qué acciones puede hacer cada rol dentro de un
módulo) viven en un solo archivo: `app/seguridad.py`.

## Notas de uso

- Al registrar una compra, puedes indicar una **fecha de vencimiento**
  por producto (formato `AAAA-MM-DD`, por ejemplo `2026-12-31`). Es
  opcional: si se deja vacía, el lote queda sin fecha de vencimiento.
  Los lotes que vencen en los próximos 30 días aparecen en las alertas
  del Dashboard y en la campana del header.
- **Ctrl+K** abre la búsqueda global (productos, lotes, producción,
  compras, proveedores, ventas y clientes); al elegir un resultado, te
  lleva a la fila exacta. **F5** refresca la pantalla activa.
- En **Inventario**, haz **doble clic** sobre un producto de la pestaña
  «Stock Actual» para abrir su detalle; «‹ Volver» regresa a la tabla
  donde estabas.
- Cada módulo operativo tiene un botón **«📊 Reporte»**: elige el
  formato (PDF, Excel o CSV), revisa la vista previa y guarda el archivo
  donde quieras.
- **Sistema de Tutorial:** en el primer acceso de un usuario se muestra
  automáticamente un tour interactivo que guía por las principales
  funcionalidades (se puede omitir). Puedes volver a él, o abrir el
  recorrido de un módulo específico, en cualquier momento desde el botón
  «❓ Ayuda y tutorial» de la barra lateral.
- Los botones **🧠** de Inventario, Compras, Producción y Ventas llevan
  directo a la parte correspondiente del Centro de Inteligencia (solo
  aparecen si tu rol tiene acceso a él).

## Módulo de IA (Centro de Inteligencia)

El Centro de Inteligencia tiene cuatro pestañas:

| Pestaña                              | Qué responde                                                                                              |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| 📦 Reposición inteligente            | ¿Qué insumos conviene reponer y cuánto? Puede abrir la orden de compra ya prellenada (decide el usuario). |
| 🍺 Predicción de merma               | ¿Cuánta merma se espera de una producción antes de planearla o cerrarla?                                   |
| 🔮 Demanda prevista (resumen)        | ¿Cuánto se venderá de cada producto en 7 / 14 / 30 días? (todos a la vez)                                  |
| 📈 Predicción de demanda (detalle)   | Gráfico histórico + predicción, KPIs y tabla diaria de un producto, y estado del modelo entrenado.         |

Cómo funciona, en corto:

- **Demanda:** un modelo XGBoost entrenado con las ventas de todos los
  productos (calendario, rezagos y promedios móviles), comparado contra
  el promedio de los últimos 7 días.
- **Merma:** un XGBoost sobre las órdenes de producción completadas,
  comparado contra el promedio histórico de la receta.
- **Reposición:** `Cantidad a reponer = demanda esperada en el periodo
  + stock de seguridad − stock disponible`. La demanda de cada insumo se
  obtiene a través de las recetas, ajustada por la merma esperada, y cada
  recomendación explica su **motivo** en texto plano. **Nada se compra
  automáticamente.**
- **Sin historial suficiente**, los motores no fallan: usan el
  *baseline* y avisan al usuario en pantalla.
- Los modelos entrenados se guardan en `models/demanda/` y
  `models/merma/`. Se pueden **reentrenar desde la interfaz** con datos
  actuales del ERP.

Métricas de los modelos incluidos en el repositorio (conjunto de prueba,
según su `metadata.json`; cambian al reentrenar):

| Modelo   | Datos de entrenamiento                                    | XGBoost (MAE / MAPE) | Baseline (MAE / MAPE) |
| -------- | --------------------------------------------------------- | -------------------- | --------------------- |
| Demanda  | 33 908 filas, 67 productos (datos de 2024-09 a 2026-09)   | 15.09 / 36.3 %       | 25.43 / 71.5 %        |
| Merma    | 35 órdenes de producción                                  | 1.39 / 26.3 %        | 1.01 / 24.2 %         |

Con tan pocas órdenes, el modelo de merma **no supera** todavía a su
baseline: es el comportamiento esperado con poca historia, y el sistema
está diseñado para mostrarlo con honestidad. En ambos casos, los datos
de entrenamiento incluidos son de ejemplo o simulados, así que estas
cifras verifican que el pipeline funciona; **no** demuestran el
desempeño con datos reales de producción.

## Simulación de ventas para probar la predicción

Para evaluar el módulo de Predicción de Demanda sin esperar meses de
operación real, `herramientas/` incluye un **generador de ventas
simuladas**, calibrado con la volatilidad del mercado cervecero. No
forma parte del ERP (la aplicación nunca lo importa). El detalle
completo está en `herramientas/README_SIMULACION.md`.

### La idea: tomar la estructura, no el nivel

El precio de la acción de una cervecera no es la demanda de cerveza, y
correlacionarlos directamente sería indefendible. Lo que sí es legítimo
tomar prestado del mercado bursátil es su **estructura estocástica**,
que la demanda de un bien de consumo comparte:

- σ diaria de los log-retornos → magnitud del choque aleatorio diario.
- Agrupamiento GARCH (α, β) → semanas revueltas seguidas de semanas revueltas.
- Curtosis > 3 → pedidos atípicos ocasionales.

Modelo del generador:

```text
D_t ~ Poisson(λ_t)
λ_t = base · Tend_t · Sem_t · Anual_t · Fest_t · Promo_t · exp(e_t − σ²/2)
```

`e_t` sale de un GARCH(1,1) cuyos parámetros se estiman por máxima
verosimilitud sobre los retornos reales de BACKUSI1.LM, CCU, ABEV, BUD,
HEIA.AS, TAP y SAM (Boston Beer, la referencia artesanal más cercana).
La corrección `−σ²/2` mantiene `E[shock] = 1`, así que subir la
volatilidad no infla las ventas medias. `Fest_t` incluye Inti Raymi, el
mes jubilar del Cusco, Fiestas Patrias, carnavales y campaña navideña,
que es lo que hace que la serie sea local y no genérica.

La σ bursátil (~1.8 % diaria) se multiplica por un factor de escala de
18× porque la demanda diaria de una artesanal es mucho más volátil que
el retorno de una acción líquida. Ese factor es el parámetro que expone
`--volatilidad baja|media|alta|extrema`.

### Uso

```bash
pip install yfinance                                                       # opcional
python -m herramientas.generar_ventas_simuladas --dias 730 --solo-csv      # vista previa (no toca la BD)
python -m herramientas.generar_ventas_simuladas --dias 730 --con-inventario --reemplazar
python -m herramientas.generar_ventas_simuladas --limpiar                  # deshacer
```

Las órdenes generadas llevan `[SIMULADO]` en `observaciones` y los lotes
el prefijo `SIM-`, así que las ventas reales de `datos_iniciales.py`
nunca se tocan. Si no hay internet o Yahoo no cubre un ticker de la BVL,
el generador cae a perfiles de respaldo y lo avisa; los perfiles
descargados quedan cacheados en `herramientas/cache_volatilidad.json`.
Una salida de ejemplo (CSV, diagnóstico y gráfico) está en
`datos_simulados/`.

### Validado de extremo a extremo

Durante el desarrollo se sembró la base con `datos_iniciales.py`, se
generaron 730 días para los 67 productos terminados (1 849 órdenes,
46 992 líneas, ~15 s) y se entrenó `demanda_training.entrenar()` sobre
el resultado. Resultados sobre 900 días, mismo producto:

| Escenario             | MAE XGBoost | MAE Baseline | MAPE |
| --------------------- | ----------- | ------------ | ---- |
| `--volatilidad baja`  | 5.50        | 6.96         | 28%  |
| `--volatilidad media` | 8.78        | 8.61         | 56%  |

Ese contraste es el hallazgo más útil: con volatilidad baja el XGBoost
le gana claramente al baseline porque aprende día de semana y festivos;
con volatilidad alta el ruido domina y ambos convergen. No es un fallo
del modelo, es el límite teórico de la serie, y sirve para demostrar que
el módulo se comporta como debe cuando hay señal y cuando no.

> **Limitación que conviene declarar:** la calibración bursátil aporta
> realismo estadístico, no validez predictiva. Los datos siguen siendo
> sintéticos y ningún MAE obtenido sobre ellos es evidencia del
> desempeño en producción — sirven para verificar el pipeline, no para
> validar el modelo.

## Correr las pruebas automáticas

El proyecto incluye pruebas de la lógica de negocio, de los módulos de
IA y "pruebas de humo" de la interfaz gráfica:

```bash
pytest                              # en Linux sin pantalla: QT_QPA_PLATFORM=offscreen pytest
```

| Archivo                          | Qué cubre                                                              |
| -------------------------------- | ---------------------------------------------------------------------- |
| `tests/test_logica.py`           | Lógica de negocio: login, usuarios, FIFO, compras, ventas, producción, costos (52 pruebas) |
| `tests/test_persistencia_modelos.py` | Carga y auto-migración de modelos XGBoost persistidos (4 pruebas)  |
| `tests/test_smoke_ui.py`         | Interfaz en modo `offscreen`: vistas, detalle de producto, validación en línea, header (17 pruebas) |
| `tests/test_demanda_recursiva.py`| Pronóstico de demanda a varios días (7 pruebas, **ver limitaciones**)  |

Si modificas `logica_inventario.py`, `logica_compras.py`,
`logica_ventas.py`, `logica_produccion.py` o `logica_reportes.py`,
vuelve a correr `pytest` para asegurarte de que no rompiste nada.

## Estructura del proyecto (resumen rápido)

```
main.py                      → punto de entrada del programa
requirements.txt             → dependencias
GUIA_ARQUITECTURA.md         → guía de por qué el proyecto está organizado así
app/
  basedatos.py                → conexión a la base de datos (SQLite)
  modelos.py                  → todas las tablas (Usuario, Producto, etc.)
  seguridad.py                → hash de contraseñas + permisos por rol (RBAC)
  sesion.py                   → quién inició sesión ahora mismo
  datos_iniciales.py          → datos de ejemplo para el primer arranque
  logica_autenticacion.py     → login, logout, crear/desactivar usuarios
  logica_compras.py           → compras y proveedores
  logica_inventario.py        → lotes, movimientos, regla FIFO, edición de producto
  logica_produccion.py        → crear/cerrar órdenes de producción
  logica_ventas.py            → ventas y clientes
  logica_costos.py            → costo y margen de lotes producidos
  logica_reportes.py          → datos de reportes; exportar PDF, Excel y CSV
  logica_busqueda.py          → búsqueda global (header)
  logica_configuracion.py     → parámetros (capital inicial, datos de la empresa)
  ia/                         → módulo de Inteligencia Artificial
    demanda_data.py             → serie diaria de ventas desde la BD
    demanda_features.py         → lags, ventanas móviles, calendario
    demanda_model.py            → XGBoost + baseline (promedio 7 días)
    demanda_training.py         → pipeline de entrenamiento (70/15/15 temporal)
    demanda_prediction.py       → predicción a 7 / 14 / 30 días
    demanda_metrics.py          → MAE, RMSE, MAPE
    merma_data.py               → dataset de órdenes de producción completadas
    merma_features.py           → características "expanding" (sin fuga de datos)
    merma_model.py              → XGBoost + baseline por receta
    merma_training.py           → pipeline de entrenamiento de merma
    merma_prediction.py         → merma esperada de una nueva producción
    reposicion.py               → reposición inteligente de insumos
    persistencia_modelos.py     → carga de modelos (auto-migra versión de xgboost)
    resultados_recientes.py     → último resultado de cada motor, en memoria
  ui/                         → todas las pantallas (PySide6)
    estilos.py                → paleta de colores y hoja de estilos QSS (un solo lugar)
    logo.py                   → carga el logo de la empresa
    widgets.py                → design system: componentes reutilizables
    header.py                 → header superior (breadcrumb, búsqueda global, campana)
    filas_inventario.py       → filas de lotes/movimientos compartidas por varias vistas
    tutorial.py               → orquestador del tutorial y Centro de Ayuda
    tutorial_data.py          → pasos y textos de los tutoriales; progreso
    tutorial_overlay.py       → overlay con transparencia real (resalta controles)
    tutorial_practice.py      → práctica guiada en Compras
    login.py                  → pantalla de ingreso de sesión
    dialogo_creditos.py       → diálogo de créditos y autoría
    dialogo_reporte.py        → diálogo de reportes (vista previa y exportación)
    ventana_principal.py      → ventana principal (sidebar + header + vistas)
    vista_dashboard.py        → panel de inicio
    vista_compras.py          → módulo de compras y proveedores
    vista_inventario.py       → módulo de inventario
    vista_detalle_producto.py → detalle de un producto (pestañas, incluida «Inteligencia»)
    pestana_inteligencia_producto.py → pestaña «🧠 Inteligencia» del detalle
    vista_produccion.py       → módulo de producción
    vista_ventas.py           → módulo de ventas y clientes
    vista_costos.py           → «Reportes de ventas» (costos y márgenes)
    vista_centro_inteligencia.py → Centro de Inteligencia (4 pestañas)
    vista_prediccion.py       → predicción de demanda (detalle), dentro del Centro
    vista_admin.py            → administración (usuarios, empresa, accesos)
    assets/                   → imágenes (logo_grande.png, logo_chico.png)
models/
  demanda/, merma/            → modelos entrenados (.pkl) y metadata.json
herramientas/                 → generador de ventas simuladas (opcional, fuera de la app)
  generar_ventas_simuladas.py, simulador_demanda.py, volatilidad_mercado.py,
  cache_volatilidad.json, README_SIMULACION.md
datos_simulados/              → ejemplo de salida del simulador (CSV, diagnóstico, gráfico)
tests/                        → pruebas automáticas
```

Para el detalle de POR QUÉ está organizado así, ver `GUIA_ARQUITECTURA.md`.

## Limitaciones conocidas

- **Pronóstico de demanda a varios días:** hoy `construir_features_futuro()`
  rellena los días futuros con `0.0` y el modelo predice todo de una vez,
  por lo que desde el 2.º día los rezagos futuros valen cero y la
  demanda proyectada (y con ella la reposición) puede quedar sesgada a la
  baja. `tests/test_demanda_recursiva.py` describe el comportamiento
  esperado (pronóstico recursivo) pero aún no pasa: importa una función
  (`features_de_un_dia`) que no existe todavía. Es la mejora pendiente de
  mayor impacto en la IA.
- **Permiso `entrenar`:** solo protege el botón de entrenar el modelo de
  merma; el botón de entrenar el modelo de demanda aún no lo consulta.
- **Reportes sin filtros de fecha:** cada reporte incluye todo el historial.
- **Datos sintéticos:** los datos de ejemplo y las ventas simuladas sirven
  para probar el sistema; las métricas de IA sobre ellos no equivalen a
  desempeño en producción.
- **Pendientes de rediseño UX:** badges de estado aún más consistentes,
  atajos de teclado adicionales, simulador de escenarios y asistente en
  lenguaje natural.