# ERP Cervecería del Valle Sagrado — v6 (con módulo de tutorial)

Sistema de gestión (ERP) de escritorio para la Cervecería del Valle
Sagrado (Cusco), escrito en **Python + PySide6 + SQLAlchemy**.

Esta es una versión **reescrita para ser fácil de leer, modificar y
mantener por una sola persona**, incluso si recién está aprendiendo a
programar. Si quieres entender CÓMO está armado el proyecto (y por
qué), lee primero **`GUIA_ARQUITECTURA.md`** — está pensada como una
guía de estudio, no solo como referencia técnica.

## ¿Qué hace el sistema?

Automatiza el ciclo completo de una cervecera artesanal:

```
Compras  →  Inventario (por lotes, regla FIFO)  →  Producción (con receta)
                                                          ↓
                                              Costos (calculados solos)
                                                          ↑
                                                       Ventas
                                                          ↓
                                                     Reportes (PDF / Excel)
```

Módulos incluidos:

| Módulo         | Qué permite hacer                                                                                        |
| -------------- | -------------------------------------------------------------------------------------------------------- |
| Ingreso        | Login con usuario/contraseña, control de acceso por rol (RBAC)                                           |
| Compras        | Registrar órdenes de compra a proveedores; actualiza el stock                                            |
| Inventario     | Ver stock por producto, ver lotes (FIFO), historial, catálogo                                            |
| Producción     | Crear/iniciar/cerrar órdenes de producción según una receta                                              |
| Ventas         | Registrar ventas a clientes; descuenta stock automáticamente                                             |
| Costos         | Ver el costo real y el margen de cada lote producido                                                     |
| Administración | Crear/desactivar/reactivar usuarios, asignar roles, ver historial de accesos (solo ADMIN)                |
| Reportes       | Generar reportes de ventas, costos e inventario; exportar a **PDF** (ReportLab) y **Excel** (openpyxl)  |

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

| Paquete         | Para qué se usa                                      |
| --------------- | ---------------------------------------------------- |
| `PySide6`       | Framework GUI de escritorio (Qt6)                    |
| `SQLAlchemy`    | Conexión y ORM de la base de datos (SQLite)          |
| `reportlab`     | Generación de reportes en formato PDF                |
| `openpyxl`      | Exportación de datos a archivos Excel (.xlsx)        |
| `pytest`        | Ejecución de las pruebas automáticas                 |

```bash
# 3) Ejecutar el programa
python main.py
```

La primera vez que se ejecuta, el programa crea automáticamente el
archivo `cervecera.db` (la base de datos) y lo llena con datos de
ejemplo: usuarios, 4 proveedores, 8 productos (5 insumos + 3 cervezas:
Anka Chida, Killa Negra e Inti IPA), 4 clientes, 3 recetas, compras ya
registradas, un lote de producción ya completado (con su venta y su
costo calculado), dos lotes de producción **en desarrollo** (uno
"EN_PROCESO" y otro recién "INICIADA"), y un capital inicial de
referencia de S/ 15,000.

## Usuarios de prueba

| Usuario    | Contraseña | Rol             |
| ---------- | ---------- | --------------- |
| admin      | admin123   | ADMIN (ve todo) |
| compras    | compras123 | COMPRAS         |
| inventario | inv123     | INVENTARIO      |
| produccion | prod123    | PRODUCCION      |
| ventas     | ventas123  | VENTAS          |
| costos     | costos123  | COSTOS          |

## Notas de uso

- Al registrar una compra, puedes indicar una **fecha de vencimiento** por producto (formato `AAAA-MM-DD`, por ejemplo `2026-12-31`). Es
opcional: si se deja vacía, el lote queda sin fecha de vencimiento.
- **Ctrl+A** selecciona todo el texto dentro de cualquier campo de entrada o combobox del programa.
- En el módulo de **Reportes**, puedes elegir el tipo de reporte
(ventas, costos o inventario), aplicar filtros de fecha y exportar
el resultado directamente a PDF o a Excel con un clic.
- **Sistema de Tutorial**: En el primer acceso de un usuario, se muestra automáticamente un tutorial interactivo que guía por las principales funcionalidades. Puedes acceder a él en cualquier momento desde el botón "❓  Ayuda y tutorial" en la barra lateral.

## Correr las pruebas automáticas

El proyecto incluye pruebas de la lógica de negocio (no de la
interfaz gráfica, que es difícil de probar de forma automática):

```bash
pytest
```

Si alguna vez modificas `logica_inventario.py`, `logica_compras.py`, `logica_ventas.py`, `logica_produccion.py` o `logica_reportes.py`, vuelve a correr `pytest` para asegurarte de que no rompiste nada.

## Estructura del proyecto (resumen rápido)

```
main.py                      → punto de entrada del programa
app/
  basedatos.py                → conexión a la base de datos (SQLite)
  modelos.py                  → todas las tablas (Usuario, Producto, etc.)
  seguridad.py                → hash de contraseñas + permisos por rol
  sesion.py                   → quién inició sesión ahora mismo
  datos_iniciales.py          → datos de ejemplo para el primer arranque
  logica_autenticacion.py     → login, logout, crear usuarios
  logica_compras.py           → registrar compras
  logica_inventario.py        → lotes, movimientos, regla FIFO
  logica_produccion.py        → crear/cerrar órdenes de producción
  logica_ventas.py            → registrar ventas
  logica_costos.py            → costo y margen de lotes producidos
  logica_reportes.py          → generar datos para reportes; exportar PDF y Excel
  logica_configuracion.py     → parámetros sueltos (ej: capital inicial)
  ui/                         → todas las pantallas (PySide6)
    estilos.py                → paleta de colores y estilos CSS (un solo lugar)
    logo.py                   → carga el logo de la empresa
    widgets.py                → componentes reutilizables
    tutorial.py               → sistema de tutorial interactivo
    tutorial_data.py          → datos y textos del tutorial
    tutorial_overlay.py       → overlay transparente para el tutorial
    login.py                  → pantalla de ingreso de sesión
    dialogo_creditos.py       → diálogo de créditos y autoría
    dialogo_reporte.py        → diálogo de configuración de reportes
    ventana_principal.py      → ventana principal (sidebar + vistas)
    vista_dashboard.py        → panel de inicio/dashboard
    vista_compras.py          → módulo de compras
    vista_inventario.py       → módulo de inventario
    vista_produccion.py       → módulo de producción
    vista_ventas.py           → módulo de ventas
    vista_costos.py           → módulo de costos
    vista_admin.py            → módulo de administración
    assets/                   → imágenes (logo_grande.png, logo_chico.png)
tests/
  test_logica.py              → pruebas automáticas
```

Para el detalle de POR QUÉ está organizado así, ver `GUIA_ARQUITECTURA.md`.

## Metodología de simulación de demanda cervecera

Ya revisé la estructura del proyecto (`app/ia/*`, `modelos.py`, `logica_ventas.py`). Voy a construir un generador de datos simulados calibrado con volatilidad real del mercado cervecero.

Sí se puede, pero conviene hacerlo con una aclaración metodológica importante, porque de lo contrario es el primer punto que te van a cuestionar en una sustentación.

### La idea: tomar la estructura, no el nivel

El precio de la acción de Backus no es la demanda de cerveza. Correlacionar ambos directamente sería indefendible. Lo que sí es legítimo tomar prestado del mercado bursátil cervecero es su estructura estocástica, que la demanda de un bien de consumo comparte:

- σ diaria de log-retornos → magnitud del choque aleatorio diario
- Agrupamiento GARCH (α, β) → semanas revueltas seguidas de semanas revueltas
- Curtosis > 3 → pedidos atípicos ocasionales

Sobre esa base armé el generador. Estructura del modelo:

```text
D_t ~ Poisson(λ_t)
λ_t = base · Tend_t · Sem_t · Anual_t · Fest_t · Promo_t · exp(e_t − σ²/2)
```

`e_t` sale de un GARCH(1,1) cuyos parámetros se estiman por máxima verosimilitud sobre los retornos reales de BACKUSI1.LM, CCU, ABEV, BUD, HEIA.AS, TAP y SAM (Boston Beer, la referencia artesanal más cercana a tu caso). La corrección `−σ²/2` mantiene `E[shock] = 1`, así subir la volatilidad no infla las ventas medias. `Fest_t` incluye Inti Raymi, mes jubilar del Cusco, Fiestas Patrias, carnavales y campaña navideña, que es lo que hace que la serie se vea local y no genérica.

La σ bursátil (~1.8% diaria) se multiplica por un factor de escala de 18× porque la demanda diaria de una artesanal es muchísimo más volátil que el retorno de una acción líquida. Ese factor es el parámetro que expone el `--volatilidad baja|media|alta|extrema`.

### Uso

```bash
pip install yfinance                                    # opcional
python -m herramientas.generar_ventas_simuladas --dias 730 --solo-csv        # vista previa
python -m herramientas.generar_ventas_simuladas --dias 730 --con-inventario --reemplazar
python -m herramientas.generar_ventas_simuladas --limpiar                    # deshacer
```

Descomprime `herramientas/` en la raíz del proyecto (junto a `main.py`). Las órdenes generadas llevan `[SIMULADO]` en `observaciones` y los lotes prefijo `SIM-`, así que tus 103 ventas reales de `datos_iniciales.py` nunca se tocan. Si no hay internet o Yahoo no cubre un ticker de la BVL, cae a perfiles de respaldo y lo avisa; los perfiles descargados quedan cacheados en JSON.

### Validado de extremo a extremo

Lo probé contra tu base real: sembré con `datos_iniciales.py`, generé 730 días para los 67 productos terminados (1 849 órdenes, 46 992 líneas, ~15 s) y entrené tu `demanda_training.entrenar()` sobre el resultado. Resultados sobre 900 días, mismo producto:

| Escenario | MAE XGBoost | MAE Baseline | MAPE |
| --------- | ----------- | ------------ | ---- |
| `--volatilidad baja` | 5.50 | 6.96 | 28% |
| `--volatilidad media` | 8.78 | 8.61 | 56% |

Ese contraste es el hallazgo más útil para tu informe: con volatilidad baja el XGBoost le gana claramente al baseline porque aprende día de semana y festivos; con volatilidad alta el ruido domina y ambos convergen. No es un fallo del modelo, es el límite teórico de la serie, y sirve para demostrar que el módulo se comporta como debe cuando hay señal y cuando no.

Una limitación que sí deberías declarar: la calibración bursátil aporta realismo estadístico, no validez predictiva. Los datos siguen siendo sintéticos y ningún MAE obtenido sobre ellos es evidencia del desempeño en producción — sirven para verificar el pipeline, no para validar el modelo.

