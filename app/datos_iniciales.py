"""
datos_iniciales.py
===================
Carga datos de ejemplo la PRIMERA vez que se ejecuta el programa.
Si ya existen usuarios en la base de datos, esta función no hace nada.

Tablas pobladas:
  - Usuario            → 6  (uno por rol)
  - Proveedor          → 8
  - Producto (insumo)  → 13
  - Producto (term.)   → 5
  - Cliente            → 10
  - Receta             → 5
  - IngredienteReceta  → 17
  - OrdenCompra / Lote / Movimiento  → 10 órdenes de compra
  - OrdenProduccion / CostoProduccion → 10 órdenes (7 cerradas, 2 en proceso, 1 iniciada)
  - OrdenVenta / DetalleVenta         → 15 ventas
"""

from app.basedatos import nueva_sesion
from app.modelos import (
    Usuario, Proveedor, Producto, Cliente, Receta, IngredienteReceta,
)
from app.seguridad import hash_contrasena
from app.logica_configuracion import establecer_parametro
from app.logica_compras import registrar_compra
from app.logica_produccion import crear_orden, iniciar_proceso, cerrar_orden
from app.logica_ventas import registrar_venta


def cargar_datos_iniciales():
    with nueva_sesion() as db:
        if db.query(Usuario).count() > 0:
            return  # ya inicializado

        # ══════════════════════════════════════════════════════════
        # USUARIOS (6 — uno por rol)
        # ══════════════════════════════════════════════════════════
        db.add_all([
            Usuario(usuario="admin",      nombre_completo="Administrador del Sistema",
                    rol="ADMIN",      contrasena_hash=hash_contrasena("admin123")),
            Usuario(usuario="compras",    nombre_completo="Jefa de Compras — Lucía Quispe",
                    rol="COMPRAS",    contrasena_hash=hash_contrasena("compras123")),
            Usuario(usuario="inventario", nombre_completo="Almacenero — Marco Condori",
                    rol="INVENTARIO", contrasena_hash=hash_contrasena("inv123")),
            Usuario(usuario="produccion", nombre_completo="Maestro Cervecero — Renzo Mamani",
                    rol="PRODUCCION", contrasena_hash=hash_contrasena("prod123")),
            Usuario(usuario="ventas",     nombre_completo="Vendedora — Sofía Tupac",
                    rol="VENTAS",     contrasena_hash=hash_contrasena("ventas123")),
            Usuario(usuario="costos",     nombre_completo="Contador — Adrián Flores",
                    rol="COSTOS",     contrasena_hash=hash_contrasena("costos123")),
        ])

        # ══════════════════════════════════════════════════════════
        # PROVEEDORES (8)
        # ══════════════════════════════════════════════════════════
        proveedores = [
            Proveedor(razon_social="Maltas del Sur S.A.C.",
                      ruc="20123456789", contacto="Juan Quispe",
                      telefono="984000001", email="maltas@maldelsur.pe"),
            Proveedor(razon_social="Lúpulos Andinos E.I.R.L.",
                      ruc="20987654321", contacto="María Flores",
                      telefono="984000002", email="ventas@lupulosandinos.pe"),
            Proveedor(razon_social="Apícola Sagrado Valle S.A.C.",
                      ruc="20456789123", contacto="Rosa Huamán",
                      telefono="984000003", email="apicola@sagradovalle.pe"),
            Proveedor(razon_social="Envases y Etiquetas Cusco E.I.R.L.",
                      ruc="20789123456", contacto="Luis Mamani",
                      telefono="984000004", email="ventas@envases-cusco.pe"),
            Proveedor(razon_social="Granos Andinos S.A.C.",
                      ruc="20321456987", contacto="Carlos Vargas",
                      telefono="984000005", email="granos@granosandinos.pe"),
            Proveedor(razon_social="Química y Aditivos del Sur E.I.R.L.",
                      ruc="20654987321", contacto="Ana Ccoa",
                      telefono="984000006", email="ventas@quimicasur.pe"),
            Proveedor(razon_social="Agua Pura Andina S.A.C.",
                      ruc="20147258369", contacto="Roberto Huanca",
                      telefono="984000007", email="agua@aguaandina.pe"),
            Proveedor(razon_social="Materiales e Insumos Cusco S.R.L.",
                      ruc="20369258147", contacto="Patricia Quispe",
                      telefono="984000008", email="ventas@maticusco.pe"),
        ]
        db.add_all(proveedores)

        # ══════════════════════════════════════════════════════════
        # PRODUCTOS INSUMOS (13)
        # ══════════════════════════════════════════════════════════
        insumos = [
            Producto(codigo="INS-001", nombre="Malta de cebada base",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=50),
            Producto(codigo="INS-002", nombre="Lúpulo Cascade (amargor y aroma)",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=5),
            Producto(codigo="INS-003", nombre="Levadura Safale S-04 (fermentación alta)",
                     tipo="Insumo", unidad_medida="g",  stock_minimo=500),
            Producto(codigo="INS-004", nombre="Cáscara de naranja deshidratada",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=3),
            Producto(codigo="INS-005", nombre="Miel de abeja pura (flora andina)",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=10),
            Producto(codigo="INS-006", nombre="Malta de trigo (cerveza de trigo)",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=20),
            Producto(codigo="INS-007", nombre="Lúpulo Chinook (resina y pino)",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=3),
            Producto(codigo="INS-008", nombre="Azúcar morena de caña",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=10),
            Producto(codigo="INS-009", nombre="Cacao en polvo sin azúcar",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=5),
            Producto(codigo="INS-010", nombre="Canela molida de Cusco",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=1),
            Producto(codigo="INS-011", nombre="Maíz morado deshidratado (chicha morada)",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=8),
            Producto(codigo="INS-012", nombre="Quinua tostada andina",
                     tipo="Insumo", unidad_medida="kg", stock_minimo=5),
            Producto(codigo="INS-013", nombre="Levadura Lallemand Abbaye (estilo belga)",
                     tipo="Insumo", unidad_medida="g",  stock_minimo=300),
        ]

        # ══════════════════════════════════════════════════════════
        # PRODUCTOS TERMINADOS (5)
        # ══════════════════════════════════════════════════════════
        terminados = [
            Producto(codigo="PRD-001", nombre="Anka Chida",
                     descripcion="Cerveza artesanal ámbar estilo American Amber Ale.",
                     tipo="Producto terminado", unidad_medida="L",
                     precio_venta=45.0, stock_minimo=20),
            Producto(codigo="PRD-002", nombre="Killa Negra",
                     descripcion="Cerveza artesanal tipo Stout con miel andina.",
                     tipo="Producto terminado", unidad_medida="L",
                     precio_venta=52.0, stock_minimo=15),
            Producto(codigo="PRD-003", nombre="Inti IPA",
                     descripcion="India Pale Ale con notas cítricas de naranja andina.",
                     tipo="Producto terminado", unidad_medida="L",
                     precio_venta=48.0, stock_minimo=15),
            Producto(codigo="PRD-004", nombre="Cusqueña Dorada (Weizen)",
                     descripcion="Cerveza de trigo estilo Weizen, ligera y refrescante.",
                     tipo="Producto terminado", unidad_medida="L",
                     precio_venta=42.0, stock_minimo=20),
            Producto(codigo="PRD-005", nombre="Pachamamita Oscura",
                     descripcion="Porter oscura con cacao y canela de Cusco.",
                     tipo="Producto terminado", unidad_medida="L",
                     precio_venta=55.0, stock_minimo=10),
        ]
        db.add_all(insumos + terminados)
        db.flush()  # Obtener IDs antes de usarlos en Receta

        # ══════════════════════════════════════════════════════════
        # CLIENTES (10)
        # ══════════════════════════════════════════════════════════
        clientes = [
            Cliente(tipo="NATURAL",  nombre="Pedro Condori Mamani",
                    documento="12345678",    telefono="984111001"),
            Cliente(tipo="JURIDICA", nombre="Distribuidora Qosqo S.R.L.",
                    documento="20111222333", telefono="984222002",
                    email="compras@distqosqo.pe"),
            Cliente(tipo="NATURAL",  nombre="Ana Sofía Tupac Yupanqui",
                    documento="45678912",    telefono="984111003"),
            Cliente(tipo="JURIDICA", nombre="Restobar Machupicchu Beer House E.I.R.L.",
                    documento="20333444555", telefono="984222004",
                    email="bar@mpicchuhouse.pe"),
            Cliente(tipo="NATURAL",  nombre="Carlos Eduardo Vargas Huanca",
                    documento="87654321",    telefono="984111005"),
            Cliente(tipo="JURIDICA", nombre="Restaurant El Qorikancha S.A.C.",
                    documento="20444555666", telefono="984222006",
                    email="chef@qorikancha.pe"),
            Cliente(tipo="JURIDICA", nombre="Bodega Andina Hermanos Quispe",
                    documento="20555666777", telefono="984222007",
                    email="ventas@bodegaandina.pe"),
            Cliente(tipo="NATURAL",  nombre="Milagros del Pilar Ccoa Flores",
                    documento="32165498",    telefono="984111008"),
            Cliente(tipo="JURIDICA", nombre="Hotel Los Apus Boutique S.A.C.",
                    documento="20666777888", telefono="984222009",
                    email="concierge@losapus.pe"),
            Cliente(tipo="NATURAL",  nombre="Jorge Alfredo Mamani Condori",
                    documento="65498732",    telefono="984111010"),
        ]
        db.add_all(clientes)

        # ══════════════════════════════════════════════════════════
        # RECETAS (5)
        # ══════════════════════════════════════════════════════════
        mp = {p.codigo: p for p in insumos}
        pt = {p.codigo: p for p in terminados}

        receta_anka     = Receta(producto_terminado_id=pt["PRD-001"].id,
                                  descripcion="Lote estándar Anka Chida 100L.",
                                  rendimiento=100.0, unidad_rendimiento="L")
        receta_killa    = Receta(producto_terminado_id=pt["PRD-002"].id,
                                  descripcion="Stout con miel, lote 80L.",
                                  rendimiento=80.0,  unidad_rendimiento="L")
        receta_inti     = Receta(producto_terminado_id=pt["PRD-003"].id,
                                  descripcion="IPA cítrica con naranja, lote 80L.",
                                  rendimiento=80.0,  unidad_rendimiento="L")
        receta_weizen   = Receta(producto_terminado_id=pt["PRD-004"].id,
                                  descripcion="Weizen con malta de trigo, lote 80L.",
                                  rendimiento=80.0,  unidad_rendimiento="L")
        receta_pachama  = Receta(producto_terminado_id=pt["PRD-005"].id,
                                  descripcion="Porter oscura con cacao y canela, lote 60L.",
                                  rendimiento=60.0,  unidad_rendimiento="L")
        db.add_all([receta_anka, receta_killa, receta_inti, receta_weizen, receta_pachama])
        db.flush()

        db.add_all([
            # Anka Chida (ámbar)
            IngredienteReceta(receta_id=receta_anka.id,
                               insumo_id=mp["INS-001"].id, cantidad=25.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_anka.id,
                               insumo_id=mp["INS-002"].id, cantidad=0.3,  unidad="kg"),
            IngredienteReceta(receta_id=receta_anka.id,
                               insumo_id=mp["INS-003"].id, cantidad=150.0, unidad="g"),
            # Killa Negra (stout + miel)
            IngredienteReceta(receta_id=receta_killa.id,
                               insumo_id=mp["INS-001"].id, cantidad=22.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_killa.id,
                               insumo_id=mp["INS-005"].id, cantidad=6.0,  unidad="kg"),
            IngredienteReceta(receta_id=receta_killa.id,
                               insumo_id=mp["INS-003"].id, cantidad=120.0, unidad="g"),
            # Inti IPA (cítrica)
            IngredienteReceta(receta_id=receta_inti.id,
                               insumo_id=mp["INS-001"].id, cantidad=20.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_inti.id,
                               insumo_id=mp["INS-002"].id, cantidad=0.6,  unidad="kg"),
            IngredienteReceta(receta_id=receta_inti.id,
                               insumo_id=mp["INS-004"].id, cantidad=1.5,  unidad="kg"),
            IngredienteReceta(receta_id=receta_inti.id,
                               insumo_id=mp["INS-003"].id, cantidad=120.0, unidad="g"),
            # Cusqueña Dorada / Weizen (trigo)
            IngredienteReceta(receta_id=receta_weizen.id,
                               insumo_id=mp["INS-001"].id, cantidad=12.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_weizen.id,
                               insumo_id=mp["INS-006"].id, cantidad=14.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_weizen.id,
                               insumo_id=mp["INS-013"].id, cantidad=100.0, unidad="g"),
            # Pachamamita (porter cacao + canela)
            IngredienteReceta(receta_id=receta_pachama.id,
                               insumo_id=mp["INS-001"].id, cantidad=18.0, unidad="kg"),
            IngredienteReceta(receta_id=receta_pachama.id,
                               insumo_id=mp["INS-009"].id, cantidad=2.0,  unidad="kg"),
            IngredienteReceta(receta_id=receta_pachama.id,
                               insumo_id=mp["INS-010"].id, cantidad=0.3,  unidad="kg"),
            IngredienteReceta(receta_id=receta_pachama.id,
                               insumo_id=mp["INS-003"].id, cantidad=90.0, unidad="g"),
        ])
        db.commit()

        # Guardamos IDs para usarlos fuera de la sesión
        ids = {
            "prov_maltas":    proveedores[0].id,
            "prov_lupulos":   proveedores[1].id,
            "prov_apicola":   proveedores[2].id,
            "prov_envases":   proveedores[3].id,
            "prov_granos":    proveedores[4].id,
            "prov_quimica":   proveedores[5].id,
            "prov_agua":      proveedores[6].id,
            "prov_matinsumos": proveedores[7].id,
            "rec_anka":       receta_anka.id,
            "rec_killa":      receta_killa.id,
            "rec_inti":       receta_inti.id,
            "rec_weizen":     receta_weizen.id,
            "rec_pachama":    receta_pachama.id,
            **{f"cli_{i}": c.id for i, c in enumerate(clientes)},
            **{f"ins_{k.lower().replace('-', '_')}": v.id for k, v in mp.items()},
            **{f"prd_{k.lower().replace('-', '_')}": v.id for k, v in pt.items()},
        }

    # ══════════════════════════════════════════════════════════
    # COMPRAS (10 órdenes) — stock generoso para toda la producción
    # ══════════════════════════════════════════════════════════

    # C1 — Compra grande inicial: malta, lúpulo, levadura
    registrar_compra(
        proveedor_id=ids["prov_maltas"],
        items=[
            {"producto_id": ids["ins_ins_001"], "cantidad": 200.0, "precio_unitario": 4.20},
            {"producto_id": ids["ins_ins_002"], "cantidad": 10.0,  "precio_unitario": 60.0},
            {"producto_id": ids["ins_ins_003"], "cantidad": 2000.0,"precio_unitario": 0.15},
        ],
        documento_referencia="F001-000123",
    )
    # C2 — Miel y cáscara de naranja
    registrar_compra(
        proveedor_id=ids["prov_apicola"],
        items=[
            {"producto_id": ids["ins_ins_005"], "cantidad": 30.0,  "precio_unitario": 22.0},
            {"producto_id": ids["ins_ins_004"], "cantidad": 8.0,   "precio_unitario": 18.0},
        ],
        documento_referencia="F002-000045",
    )
    # C3 — Malta de trigo y levadura belga
    registrar_compra(
        proveedor_id=ids["prov_granos"],
        items=[
            {"producto_id": ids["ins_ins_006"], "cantidad": 60.0,  "precio_unitario": 4.80},
            {"producto_id": ids["ins_ins_013"], "cantidad": 500.0, "precio_unitario": 0.20},
        ],
        documento_referencia="F003-000210",
    )
    # C4 — Lúpulo Chinook, azúcar morena
    registrar_compra(
        proveedor_id=ids["prov_lupulos"],
        items=[
            {"producto_id": ids["ins_ins_007"], "cantidad": 6.0,   "precio_unitario": 55.0},
            {"producto_id": ids["ins_ins_008"], "cantidad": 20.0,  "precio_unitario": 3.50},
        ],
        documento_referencia="F004-000088",
    )
    # C5 — Cacao, canela y quinua
    registrar_compra(
        proveedor_id=ids["prov_quimica"],
        items=[
            {"producto_id": ids["ins_ins_009"], "cantidad": 10.0,  "precio_unitario": 25.0},
            {"producto_id": ids["ins_ins_010"], "cantidad": 3.0,   "precio_unitario": 15.0},
            {"producto_id": ids["ins_ins_012"], "cantidad": 15.0,  "precio_unitario": 8.0},
        ],
        documento_referencia="F005-000056",
    )
    # C6 — Maíz morado y segunda compra de malta
    registrar_compra(
        proveedor_id=ids["prov_granos"],
        items=[
            {"producto_id": ids["ins_ins_011"], "cantidad": 20.0,  "precio_unitario": 6.50},
            {"producto_id": ids["ins_ins_001"], "cantidad": 100.0, "precio_unitario": 4.10},
        ],
        documento_referencia="F006-000312",
    )
    # C7 — Reposición de levadura y lúpulo Cascade
    registrar_compra(
        proveedor_id=ids["prov_maltas"],
        items=[
            {"producto_id": ids["ins_ins_003"], "cantidad": 1500.0,"precio_unitario": 0.14},
            {"producto_id": ids["ins_ins_002"], "cantidad": 8.0,   "precio_unitario": 58.0},
        ],
        documento_referencia="F007-000401",
    )
    # C8 — Segunda compra de miel (temporada alta)
    registrar_compra(
        proveedor_id=ids["prov_apicola"],
        items=[
            {"producto_id": ids["ins_ins_005"], "cantidad": 25.0,  "precio_unitario": 21.50},
        ],
        documento_referencia="F008-000189",
    )
    # C9 — Reposición de malta de trigo
    registrar_compra(
        proveedor_id=ids["prov_granos"],
        items=[
            {"producto_id": ids["ins_ins_006"], "cantidad": 40.0,  "precio_unitario": 4.90},
            {"producto_id": ids["ins_ins_007"], "cantidad": 4.0,   "precio_unitario": 56.0},
        ],
        documento_referencia="F009-000225",
    )
    # C10 — Compra de cacao y canela extra
    registrar_compra(
        proveedor_id=ids["prov_quimica"],
        items=[
            {"producto_id": ids["ins_ins_009"], "cantidad": 8.0,   "precio_unitario": 24.0},
            {"producto_id": ids["ins_ins_010"], "cantidad": 2.0,   "precio_unitario": 14.5},
        ],
        documento_referencia="F010-000098",
    )

    # ══════════════════════════════════════════════════════════
    # PRODUCCIÓN (10 órdenes)
    # 7 cerradas, 2 en proceso, 1 iniciada
    # ══════════════════════════════════════════════════════════

    # P1 — Anka Chida lote 1 (CERRADA)
    op1 = crear_orden(receta_id=ids["rec_anka"], cantidad_planeada=100.0,
                      numero_lote="LOTE-2026-001",
                      observaciones="Primer lote de la temporada.")
    iniciar_proceso(op1.id)
    cerrar_orden(op1.id, cantidad_real=96.0, cantidad_merma=4.0,
                 causa_merma="Pérdida normal de trasiego",
                 costo_mano_obra=180.0, costos_indirectos=60.0)

    # P2 — Killa Negra lote 1 (CERRADA)
    op2 = crear_orden(receta_id=ids["rec_killa"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-002",
                      observaciones="Stout con miel de primavera.")
    iniciar_proceso(op2.id)
    cerrar_orden(op2.id, cantidad_real=78.0, cantidad_merma=2.0,
                 causa_merma="Absorción en los granos",
                 costo_mano_obra=160.0, costos_indirectos=50.0)

    # P3 — Inti IPA lote 1 (CERRADA)
    op3 = crear_orden(receta_id=ids["rec_inti"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-003",
                      observaciones="IPA cítrica con naranja del valle.")
    iniciar_proceso(op3.id)
    cerrar_orden(op3.id, cantidad_real=77.0, cantidad_merma=3.0,
                 causa_merma="Arrastre en dry-hop",
                 costo_mano_obra=165.0, costos_indirectos=55.0)

    # P4 — Cusqueña Dorada lote 1 (CERRADA)
    op4 = crear_orden(receta_id=ids["rec_weizen"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-004",
                      observaciones="Weizen para temporada de verano.")
    iniciar_proceso(op4.id)
    cerrar_orden(op4.id, cantidad_real=79.0, cantidad_merma=1.0,
                 causa_merma="Mínima pérdida de trasiego",
                 costo_mano_obra=150.0, costos_indirectos=45.0)

    # P5 — Pachamamita lote 1 (CERRADA)
    op5 = crear_orden(receta_id=ids["rec_pachama"], cantidad_planeada=60.0,
                      numero_lote="LOTE-2026-005",
                      observaciones="Porter con cacao — edición especial.")
    iniciar_proceso(op5.id)
    cerrar_orden(op5.id, cantidad_real=57.0, cantidad_merma=3.0,
                 causa_merma="Absorción del cacao en filtrado",
                 costo_mano_obra=140.0, costos_indirectos=50.0)

    # P6 — Anka Chida lote 2 (CERRADA)
    op6 = crear_orden(receta_id=ids["rec_anka"], cantidad_planeada=100.0,
                      numero_lote="LOTE-2026-006",
                      observaciones="Segunda hornada de Anka Chida.")
    iniciar_proceso(op6.id)
    cerrar_orden(op6.id, cantidad_real=98.0, cantidad_merma=2.0,
                 causa_merma="Pérdida mínima de trasiego",
                 costo_mano_obra=175.0, costos_indirectos=58.0)

    # P7 — Killa Negra lote 2 (CERRADA)
    op7 = crear_orden(receta_id=ids["rec_killa"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-007",
                      observaciones="Segundo lote Killa Negra.")
    iniciar_proceso(op7.id)
    cerrar_orden(op7.id, cantidad_real=76.0, cantidad_merma=4.0,
                 causa_merma="Pérdida por fermentación vigorosa",
                 costo_mano_obra=160.0, costos_indirectos=52.0)

    # P8 — Inti IPA lote 2 (EN_PROCESO)
    op8 = crear_orden(receta_id=ids["rec_inti"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-008",
                      observaciones="Segunda hornada IPA — en fermentación.")
    iniciar_proceso(op8.id)   # queda EN_PROCESO

    # P9 — Weizen lote 2 (EN_PROCESO)
    op9 = crear_orden(receta_id=ids["rec_weizen"], cantidad_planeada=80.0,
                      numero_lote="LOTE-2026-009",
                      observaciones="Segunda Cusqueña Dorada — en proceso.")
    iniciar_proceso(op9.id)   # queda EN_PROCESO

    # P10 — Pachamamita lote 2 (INICIADA — aún no ha comenzado)
    crear_orden(receta_id=ids["rec_pachama"], cantidad_planeada=60.0,
                numero_lote="LOTE-2026-010",
                observaciones="Segunda edición especial Pachamamita — pendiente de inicio.")

    # ══════════════════════════════════════════════════════════
    # VENTAS (15 órdenes)
    # ══════════════════════════════════════════════════════════

    def _v(cliente_idx, items):
        registrar_venta(cliente_id=ids[f"cli_{cliente_idx}"], items=items)

    prd_anka   = ids["prd_prd_001"]
    prd_killa  = ids["prd_prd_002"]
    prd_inti   = ids["prd_prd_003"]
    prd_weizen = ids["prd_prd_004"]
    prd_pachama = ids["prd_prd_005"]

    _v(0, [{"producto_id": prd_anka,   "cantidad": 24.0, "precio_unitario": 45.0}])
    _v(1, [{"producto_id": prd_killa,  "cantidad": 30.0, "precio_unitario": 52.0},
           {"producto_id": prd_anka,   "cantidad": 20.0, "precio_unitario": 45.0}])
    _v(2, [{"producto_id": prd_inti,   "cantidad": 12.0, "precio_unitario": 48.0}])
    _v(3, [{"producto_id": prd_weizen, "cantidad": 40.0, "precio_unitario": 42.0},
           {"producto_id": prd_killa,  "cantidad": 10.0, "precio_unitario": 52.0}])
    _v(4, [{"producto_id": prd_pachama,"cantidad": 15.0, "precio_unitario": 55.0}])
    _v(5, [{"producto_id": prd_anka,   "cantidad": 36.0, "precio_unitario": 45.0},
           {"producto_id": prd_inti,   "cantidad": 20.0, "precio_unitario": 48.0}])
    _v(6, [{"producto_id": prd_killa,  "cantidad": 18.0, "precio_unitario": 52.0}])
    _v(7, [{"producto_id": prd_weizen, "cantidad": 8.0,  "precio_unitario": 42.0}])
    _v(8, [{"producto_id": prd_anka,   "cantidad": 50.0, "precio_unitario": 44.0},
           {"producto_id": prd_pachama,"cantidad": 12.0, "precio_unitario": 55.0}])
    _v(9, [{"producto_id": prd_inti,   "cantidad": 16.0, "precio_unitario": 48.0}])
    _v(0, [{"producto_id": prd_killa,  "cantidad": 6.0,  "precio_unitario": 52.0}])
    _v(3, [{"producto_id": prd_weizen, "cantidad": 25.0, "precio_unitario": 42.0}])
    _v(5, [{"producto_id": prd_pachama,"cantidad": 20.0, "precio_unitario": 55.0},
           {"producto_id": prd_anka,   "cantidad": 15.0, "precio_unitario": 45.0}])
    _v(1, [{"producto_id": prd_inti,   "cantidad": 29.0, "precio_unitario": 48.0},
           {"producto_id": prd_killa,  "cantidad": 15.0, "precio_unitario": 52.0}])
    _v(8, [{"producto_id": prd_anka,   "cantidad": 20.0, "precio_unitario": 45.0},
           {"producto_id": prd_weizen, "cantidad": 6.0, "precio_unitario": 42.0}])

    # Capital inicial de referencia
    establecer_parametro("capital_inicial", "25000.00")

    # ── Datos de la empresa ──────────────────────────────────────────
    # Estos valores aparecen en los reportes (PDF, Excel) y en el
    # título de la ventana. El admin puede editarlos desde
    # Administración → Empresa sin necesidad de tocar el código.
    establecer_parametro("empresa_nombre",    "Cervecería del Valle Sagrado")
    establecer_parametro("empresa_ruc",       "20123456789")
    establecer_parametro("empresa_direccion", "Av. Tullumayo 234, Wanchaq")
    establecer_parametro("empresa_telefono",  "+51 84 223344")
    establecer_parametro("empresa_email",     "contacto@cerveceria-vallsagrado.pe")
    establecer_parametro("empresa_ciudad",    "Cusco, Perú")
    establecer_parametro("empresa_web",       "www.cerveceria-vallsagrado.pe")

    print("[datos_iniciales] Base de datos inicializada con datos completos de ejemplo.")