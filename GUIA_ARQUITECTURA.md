# Guía de arquitectura — para entender (y poder modificar) este proyecto

Este documento explica CÓMO está armado el sistema y, más importante,
POR QUÉ se organizó así. No es documentación "para expertos": está
pensada para que puedas modificar el código con confianza aunque
todavía estés aprendiendo a programar.

## 1. La idea central: 3 capas, y nada más

Casi cualquier programa que guarda información en una base de datos y
tiene una pantalla se puede pensar en 3 capas:

```
┌─────────────────────────────────────┐
│   INTERFAZ (lo que ve el usuario)    │   → carpeta app/ui/
│   Botones, tablas, ventanas...       │
└─────────────────┬─────────────────────┘
                  │  llama a funciones de...
┌─────────────────▼─────────────────────┐
│   LÓGICA DE NEGOCIO                   │   → archivos logica_*.py
│   "¿Qué reglas tiene el negocio?"     │
│   (ej: FIFO, RBAC, cálculo de costos, │
│    generación de reportes PDF/Excel)  │
└─────────────────┬─────────────────────┘
                  │  usa objetos de...
┌─────────────────▼─────────────────────┐
│   MODELOS + BASE DE DATOS             │   → modelos.py, basedatos.py
│   Las tablas y cómo se guardan        │
└─────────────────────────────────────┘
```

Este proyecto usa **exactamente esas 3 capas, ni una más**. La versión
anterior (con PySide6) tenía 4 capas (Vista → Service → Repository →
Model), y la capa "Repository" usaba *generics* de Python (`TypeVar`, `Generic[T]`) — una herramienta muy potente, pero también uno de los
conceptos que más cuesta entender cuando se está aprendiendo. Aquí se
eliminó esa capa: las funciones de `logica_*.py` hablan DIRECTAMENTE
con la base de datos usando SQLAlchemy. Una capa menos que aprender,
una capa menos que mantener.

## 2. ¿Por qué un archivo `logica_X.py` por módulo, y no clases?

En vez de una clase `CompraService` con métodos, `logica_compras.py` tiene funciones sueltas: `registrar_compra()`, `listar_ordenes_compra()`, etc.

¿Por qué? Porque estas funciones no necesitan "recordar" nada entre
llamadas (no tienen estado propio) — cada una abre su sesión de base
de datos, hace su trabajo, y termina. Cuando una función no necesita
guardar estado, usar una función simple es más fácil de leer que
crear una clase solo para agrupar métodos. Si en algún momento sientes
que `logica_X.py` te resulta más natural como clase, siéntete libre
de convertirlo — pero probablemente no lo necesites.

Esto aplica también a `logica_reportes.py`: sus funciones reciben
parámetros de filtro (fechas, tipo de reporte), consultan la base de
datos y devuelven los datos listos para ser formateados — sin guardar
estado entre llamadas.

## 3. ¿Por qué SQLAlchemy con `Column` y no con `Mapped[...]`?

SQLAlchemy (la librería que conecta Python con la base de datos) tiene
dos estilos de escritura:

```python
# Estilo "moderno" (2.0 typed) — el que tenía la versión anterior
nombre: Mapped[str] = mapped_column(String(150), nullable=False)

# Estilo "clásico" — el que usa este proyecto
nombre = Column(String(150), nullable=False)
```

Ambos funcionan igual de bien. El estilo clásico es el que vas a
encontrar en el 90% de los tutoriales de SQLAlchemy en español y en
inglés, así que si necesitas buscar ayuda en internet, es más fácil
encontrar ejemplos parecidos a este código.

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
pena leerla con calma, tiene comentarios paso a paso.

## 5. ¿Dónde se decide qué puede hacer cada usuario? (RBAC)

Todo el control de permisos vive en **un solo archivo**: `seguridad.py`.
Hay dos diccionarios:

- `MODULOS_POR_ROL`: qué botones del menú lateral ve cada rol.
- `ACCIONES_POR_ROL`: dentro de un módulo, qué puede hacer cada rol
(por ejemplo, "VENTAS" puede "crear" ventas, pero no "cerrar" órdenes
de producción).

Si algún día necesitas un rol nuevo, o cambiar qué puede hacer un rol
existente, **solo tienes que tocar `seguridad.py`** — ningún otro
archivo necesita cambiar.

El módulo de Reportes también respeta RBAC: solo los roles con acceso
configurado en `MODULOS_POR_ROL` verán el botón de reportes en el menú.

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

## 7. ¿Cómo se conecta una pantalla con la lógica de negocio?

Ejemplo real, con el botón "+ Nueva venta" en `vista_ventas.py`:

```python
# 1) El botón, al hacer clic, abre una ventana (VentanaNuevaVenta)
barra.agregar_boton("+ Nueva venta", self._abrir_nueva_venta)

# 2) Esa ventana arma una lista de productos en pantalla, y cuando el
#    usuario presiona "Registrar venta", llama a la función de lógica:
orden = registrar_venta(cliente_id=..., items=self.items_agregados, ...)

# 3) registrar_venta() (en logica_ventas.py) es la que realmente
#    habla con la base de datos.
```

Fíjate que `vista_ventas.py` NUNCA escribe código de SQLAlchemy
directamente para guardar la venta — solo junta los datos que el
usuario ingresó y se los pasa a `logica_ventas.registrar_venta()`.
Esta separación es útil porque, si algún día cambias Tkinter por otra
librería de interfaz gráfica, casi no tendrías que tocar los archivos `logica_*.py`.

## 8. El módulo de Reportes: cómo funciona

El módulo de reportes sigue exactamente el mismo patrón de 3 capas:

```
vista_reportes.py
  └─ el usuario elige tipo de reporte, rango de fechas y formato
        │
        ▼
logica_reportes.py
  └─ consulta la BD, arma el conjunto de datos y llama al generador
        │
        ├─► ReportLab  →  archivo .pdf
        └─► openpyxl   →  archivo .xlsx
```

Hay dos tipos de exportación disponibles:

- **PDF** (via `reportlab`): produce un documento con encabezado, tabla
de datos y pie de página con la fecha de generación. Útil para imprimir
o archivar.
- **Excel** (via `openpyxl`): produce una hoja de cálculo lista para
que el usuario aplique sus propios filtros y gráficos. Útil para
análisis ad-hoc.

Las funciones de `logica_reportes.py` devuelven los datos como listas
de diccionarios — la misma estructura que va tanto al PDF como al Excel.
Si en el futuro quisieras agregar un tercer formato (por ejemplo, CSV),
solo habría que agregar una función generadora nueva; la consulta a la
BD no cambia.

## 9. Cosas que se simplificaron a propósito

| Se decidió...                                          | En vez de...                                | Por qué                                                                                                                                                                                    |
| ------------------------------------------------------ | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Hash de contraseñas con `hashlib` (librería estándar)  | Argon2 (librería externa)                   | Menos dependencias que instalar; PBKDF2 es un algoritmo real y ampliamente usado (es el que usa Django por defecto).                                                                       |
| Funciones sueltas en `logica_*.py`                     | Clases `Service` + `Repository` genéricas   | Menos capas, menos conceptos avanzados (generics) que aprender.                                                                                                                            |
| SQLAlchemy estilo `Column` clásico                     | Estilo `Mapped[...]` (SQLAlchemy 2.0 typed) | Es el estilo que más se enseña en tutoriales; más fácil de buscar ayuda.                                                                                                                   |
| Tkinter (incluido con Python)                          | PySide6 (hay que instalarlo aparte)         | No requiere instalar un framework de interfaz gráfica externo.                                                                                                                             |
| Un archivo `modelos.py` con todas las tablas           | Un archivo por tabla                        | Para un proyecto de este tamaño, es más fácil encontrar todo en un solo lugar que saltar entre 9 archivos pequeños. Si el proyecto creciera mucho más, dividirlo volvería a tener sentido. |
| ReportLab + openpyxl para reportes                     | Matplotlib embebido en Tkinter              | Separar la generación del reporte de la interfaz gráfica es más simple: el usuario descarga el archivo y lo abre con el visor que prefiera.                                               |

## 10. Ideas para seguir extendiendo el proyecto

Estas son mejoras que puedes intentar tú mismo para practicar
(de más fácil a más difícil):

1. **Editar productos existentes** (hoy solo se pueden crear, no editar).
2. **Historial de compras/ventas por cliente o proveedor** (un filtro
en la pestaña de órdenes).
3. **Más tipos de reporte** (por ejemplo, un reporte de mermas o un
resumen de compras por proveedor) — la estructura de `logica_reportes.py`
ya está lista para agregar nuevas consultas.
4. **Reporte con gráficos incrustados en el PDF** (ReportLab soporta
gráficos de barras nativamente con `reportlab.graphics.charts`).
5. **Notificaciones automáticas** cuando un producto queda por debajo
del stock mínimo (ya existe la función `productos_bajo_minimo()` en
`logica_inventario.py` — solo falta decidir cómo avisar).

## 12. El módulo de tutorial interactivo: cómo funciona

Vive en `app/ui/tutorial*.py`, dividido en 4 archivos con una única
responsabilidad cada uno:

| Archivo                  | Responsabilidad                                                                 |
| ------------------------- | -------------------------------------------------------------------------------- |
| `tutorial_data.py`        | **Contenido declarativo**: la lista de pasos de cada tutorial, el guardado del progreso del usuario y los textos de ayuda contextual. Agregar o cambiar un tutorial es, casi siempre, solo tocar este archivo. |
| `tutorial_overlay.py`     | **Motor visual**: oscurece la pantalla alrededor del control que se explica y muestra la tarjeta con el texto. No sabe nada de "Compras" ni de "roles" — solo sabe resaltar un widget de Tkinter. |
| `tutorial.py`             | **Orquestador**: recorre los pasos de un tutorial con el overlay, maneja la navegación entre módulos, y contiene el panel «❓ Ayuda y tutorial». |

**¿Cómo sabe el tutorial qué widget resaltar?** Cada vista (`VistaCompras`,
`VistaInventario`, etc.) expone un diccionario `self.tutorial_targets`
con sus controles reales (por ejemplo `tutorial_targets["btn_reporte"]`
apunta al botón de reporte real). Los pasos de `tutorial_data.py` piden
esos controles por nombre — si algún control no existe (por ejemplo,
porque el rol actual no tiene permiso para crearlo), el paso
simplemente se muestra sin resaltar nada, en vez de romper la app.

**¿Cómo respeta los roles?** Reutiliza `seguridad.modulos_visibles(rol)`
— la misma función que decide qué botones aparecen en el sidebar — para
filtrar qué tutoriales y qué pasos del tour general tienen sentido para
cada usuario. No existe un segundo sistema de permisos.

**¿Dónde se guarda el progreso?** En la misma tabla `ParametroSistema`
que ya usa el resto del sistema (ver `logica_configuracion.py`), como
un JSON por usuario y por tutorial. No se creó ninguna tabla nueva.

**Para agregar un tutorial de un módulo nuevo**, solo hace falta:
1. Exponer los controles relevantes en `self.tutorial_targets` desde
   la vista de ese módulo.
2. Escribir la lista de `PasoTutorial` en `tutorial_data.py` y
   registrarla en `TUTORIALES_MODULO`.

No hace falta tocar `tutorial.py` ni `tutorial_overlay.py`.

## 13. ¿Y de dónde salen los colores?

Todo el color de la aplicación (el ámbar del menú, el marrón del
sidebar, el rojo de las alertas...) vive en **un solo archivo**: `app/ui/estilos.py`. Cada pantalla no define sus propios colores;
en vez de eso, usa "estilos con nombre" (por ejemplo, `style="Sidebar.TButton"`) que apuntan a los colores definidos ahí.

Si quieres cambiar el tema completo de la app (por ejemplo, probar
con un verde en vez del ámbar), solo tienes que cambiar las
constantes `COLOR_*` al principio de `estilos.py` — no hace falta
tocar ninguna otra pantalla.
