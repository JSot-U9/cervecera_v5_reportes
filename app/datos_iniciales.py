"""
datos_iniciales.py
===================
Carga datos de ejemplo la PRIMERA vez que se ejecuta el programa.
Si ya existen usuarios en la base de datos, esta función no hace nada.

El archivo tiene DOS partes:

  PARTE 1 — a mano, tal como en la versión original: 6 usuarios (uno
  por rol, con las credenciales de prueba documentadas en el README),
  8 proveedores, 13 insumos, 5 cervezas, 10 clientes, 5 recetas,
  10 compras, 10 órdenes de producción y 15 ventas. Todo escrito
  línea por línea, fácil de leer y de seguir con la vista.

  PARTE 2 — generada por código: para tener un conjunto de datos de
  prueba más grande (pensado para que CADA tabla del sistema tenga
  al menos 50 filas) sin copiar y pegar decenas de líneas casi
  iguales a mano. No son números al azar: los usuarios, proveedores,
  insumos, cervezas y clientes se arman combinando listas de nombres
  típicos de la zona; las recetas nuevas usan las MISMAS proporciones
  (malta, lúpulo, levadura por litro) que ya se ven en las recetas
  originales de la Parte 1; y las compras se calculan para que
  siempre alcance el stock antes de fabricar y vender — igual que
  tendría que hacerlo una persona registrando esto a mano, solo que
  con un bucle en vez de repetir la misma llamada 40 veces.

Tablas pobladas (Parte 1 + Parte 2):
  - Usuario                          →  6 + 45 =  51
  - Proveedor                        →  8 + 43 =  51
  - Producto (insumo)                → 13 + 40 =  53
  - Producto (producto terminado)    →  5 + 62 =  67
  - Cliente                          → 10 + 43 =  53
  - Receta                           →  5 + 62 =  67
  - IngredienteReceta                → 17 + 62*9 = 575
  - OrdenCompra / Lote / Movimiento  → 10 + 41 =  51
  - OrdenProduccion / CostoProduccion / Merma → 10 + 62 = 72 órdenes,
    de las cuales ~51 quedan CERRADAS (mismas proporciones que la
    Parte 1: ~70% cerradas, ~20% en proceso, ~10% recién iniciadas) —
    así CostoProduccion y Merma (que solo se crean al cerrar una
    orden) también superan las 50 filas.
  - OrdenVenta / DetalleVenta        → 15 + generadas dinámicamente
    según el stock real disponible después de cada producción (≥60 más)
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
from app.logica_inventario import stock_total


# ══════════════════════════════════════════════════════════════════
#  PARTE 2 — bancos de nombres y funciones generadoras
# ══════════════════════════════════════════════════════════════════
# Nada de esto son personas, empresas o productos reales: son listas
# de nombres típicos de la región (Cusco / andinos) que se combinan
# por índice para armar filas variadas sin escribirlas una por una.
# Se combinan siempre con el mismo tipo de operación (i % len(lista),
# con distintos multiplicadores para que no calcen todas en el mismo
# patrón), así que el resultado es siempre el mismo en cada
# instalación — no se usa la librería `random` a propósito, para que
# el dato de ejemplo sea reproducible y fácil de depurar.
# ══════════════════════════════════════════════════════════════════

_NOMBRES = [
    "Juan", "María", "Carlos", "Rosa", "Luis", "Ana", "Pedro", "Sofía",
    "Miguel", "Elena", "Jorge", "Lucía", "Roberto", "Patricia", "Diego",
    "Milagros", "Fernando", "Yolanda", "Ricardo", "Ximena", "Alberto",
    "Gabriela", "Renzo", "Katherine", "Marco", "Adriana", "Raúl",
    "Cecilia", "Iván", "Noelia",
]
_APELLIDOS = [
    "Quispe", "Mamani", "Condori", "Huamán", "Ccoa", "Tupac", "Vargas",
    "Flores", "Huanca", "Apaza", "Ccorimanya", "Salazar", "Puma",
    "Choquehuanca", "Ttito", "Ramos", "Zúñiga", "Alvarez", "Pumayalli",
    "Chávez", "Ancca", "Sallo", "Cusihuaman", "Machaca", "Yupanqui",
    "Illatarco", "Suyo", "Achahui", "Quenaya", "Béjar",
]
_LUGARES_CUSCO = [
    "Valle Sagrado", "Urubamba", "Ollantaytambo", "Pisac", "Chinchero",
    "Anta", "Calca", "Paucartambo", "Quillabamba", "Espinar", "Canchis",
    "Wanchaq", "San Jerónimo", "Poroy", "Písac", "Lamay", "Maras",
    "Huayllabamba", "Yucay", "Santa Ana",
]
_FORMAS_LEGALES = ["S.A.C.", "E.I.R.L.", "S.R.L."]


def _usuarios_adicionales():
    """
    Usuarios extra, más allá de las 6 cuentas de prueba documentadas
    en el README (una por rol — esas NO se tocan). Reflejan una
    empresa que ya creció: varias sucursales de ventas, más de un
    almacén, más de un turno de producción. El login sigue el patrón
    "<rol><número>" para no chocar con los logins fijos ("admin",
    "compras", etc.) que sí están documentados.
    """
    plan = [
        ("ADMIN", 1), ("COMPRAS", 5), ("INVENTARIO", 9),
        ("PRODUCCION", 7), ("VENTAS", 16), ("COSTOS", 7),
    ]
    usuarios = []
    i = 0
    for rol, cantidad in plan:
        for n in range(2, cantidad + 2):   # arranca en "02": "01" es la cuenta de prueba
            nombre = _NOMBRES[i % len(_NOMBRES)]
            apellido = _APELLIDOS[(i * 7 + 3) % len(_APELLIDOS)]
            login = f"{rol.lower()}{n:02d}"
            usuarios.append(Usuario(
                usuario=login,
                nombre_completo=f"{nombre} {apellido}",
                rol=rol,
                contrasena_hash=hash_contrasena(f"{login}123"),
            ))
            i += 1
    return usuarios


_RUBROS_PROVEEDOR = [
    "Maltería", "Lupulera", "Levaduras y Fermentos", "Apícola",
    "Frutas Deshidratadas", "Especias Andinas", "Insumos Químicos",
    "Envases de Vidrio", "Etiquetas y Empaques", "Cartonería Industrial",
    "Transportes", "Refrigeración Industrial", "Repuestos Industriales",
    "Limpieza Industrial", "Gas Industrial", "Seguridad y EPP",
    "Mantenimiento Eléctrico", "Control de Plagas", "Laboratorio y Análisis",
    "Publicidad y Merchandising",
]


def _proveedores_adicionales(cantidad):
    """Proveedores extra, uno por combinación de rubro + lugar + forma legal."""
    proveedores = []
    for i in range(cantidad):
        rubro = _RUBROS_PROVEEDOR[i % len(_RUBROS_PROVEEDOR)]
        lugar = _LUGARES_CUSCO[i % len(_LUGARES_CUSCO)]
        forma = _FORMAS_LEGALES[i % len(_FORMAS_LEGALES)]
        nombre = _NOMBRES[(i * 3) % len(_NOMBRES)]
        apellido = _APELLIDOS[(i * 5 + 1) % len(_APELLIDOS)]
        slug = rubro.lower().replace(" ", "")
        proveedores.append(Proveedor(
            razon_social=f"{rubro} {lugar} {forma}",
            ruc=f"20{700000000 + i:09d}",
            contacto=f"{nombre} {apellido}",
            telefono=f"984{300000 + i:06d}",
            email=f"contacto{i + 1}@{slug}.pe",
        ))
    return proveedores


# ── Insumos nuevos: (slug, nombre, categoría, unidad, stock_mínimo) ──
# La "categoría" es la que usan las funciones de más abajo para armar
# recetas y compras coherentes (por ejemplo: todas las "lupulo" se
# compran en kilos y en cantidades chicas; todas las "envase" se
# compran por unidad y en cantidades grandes).
_INSUMOS_ADICIONALES = [
    ("malta_pilsner",   "Malta Pilsner",                       "malta",    "kg", 40),
    ("malta_munich",    "Malta Munich",                        "malta",    "kg", 30),
    ("malta_caramelo",  "Malta Caramelo 60L",                  "malta",    "kg", 15),
    ("malta_chocolate", "Malta Chocolate",                     "malta",    "kg", 8),
    ("malta_ahumada",   "Malta Ahumada",                       "malta",    "kg", 5),
    ("copos_avena",     "Copos de avena",                      "malta",    "kg", 10),
    ("copos_trigo",     "Copos de trigo",                      "malta",    "kg", 10),
    ("lupulo_citra",      "Lúpulo Citra",                      "lupulo",   "kg", 3),
    ("lupulo_centennial", "Lúpulo Centennial",                 "lupulo",   "kg", 3),
    ("lupulo_saaz",       "Lúpulo Saaz",                       "lupulo",   "kg", 3),
    ("lupulo_mosaic",     "Lúpulo Mosaic",                     "lupulo",   "kg", 3),
    ("lupulo_simcoe",     "Lúpulo Simcoe",                     "lupulo",   "kg", 3),
    ("lupulo_eldorado",   "Lúpulo El Dorado",                  "lupulo",   "kg", 3),
    ("lupulo_amarillo",   "Lúpulo Amarillo",                   "lupulo",   "kg", 3),
    ("lupulo_hallertau",  "Lúpulo Hallertau",                  "lupulo",   "kg", 3),
    ("levadura_kveik",       "Levadura Kveik Voss",             "levadura", "g", 200),
    ("levadura_us05",        "Levadura US-05",                  "levadura", "g", 500),
    ("levadura_nottingham",  "Levadura Nottingham",             "levadura", "g", 500),
    ("levadura_saison",      "Levadura Belle Saison",           "levadura", "g", 200),
    ("levadura_weizen_alemana", "Levadura Wyeast 3068 (trigo alemán)", "levadura", "g", 200),
    ("fresa_deshidratada",      "Fresas deshidratadas",         "especial", "kg", 3),
    ("maracuya_deshidratado",   "Maracuyá deshidratado",        "especial", "kg", 3),
    ("aguaymanto_deshidratado", "Aguaymanto deshidratado",      "especial", "kg", 3),
    ("tumbo_deshidratado",      "Tumbo deshidratado",           "especial", "kg", 3),
    ("jengibre_fresco",         "Jengibre fresco",              "especial", "kg", 2),
    ("cafe_tostado",            "Café tostado en grano",        "especial", "kg", 5),
    ("coco_rallado",            "Coco rallado tostado",         "especial", "kg", 3),
    ("vainilla_vaina",          "Vainilla en vaina",            "especial", "kg", 1),
    ("chips_roble",             "Chips de roble tostado",       "especial", "kg", 5),
    ("botella_620",  "Botellas de vidrio ámbar 620ml",   "envase", "unidad", 500),
    ("botella_330",  "Botellas de vidrio ámbar 330ml",   "envase", "unidad", 500),
    ("lata_355",     "Latas de aluminio 355ml",          "envase", "unidad", 1000),
    ("growler_1l",   "Growlers de vidrio 1L",            "envase", "unidad", 100),
    ("tapa_corona",  "Tapas corona",                     "envase", "unidad", 2000),
    ("etiqueta",     "Etiquetas autoadhesivas",          "envase", "unidad", 1000),
    ("caja_x12",     "Cajas de cartón x12 botellas",     "envase", "unidad", 100),
    ("precinto",     "Precintos de seguridad",           "envase", "unidad", 500),
    ("acido_citrico",         "Ácido cítrico",                       "quimico", "kg", 2),
    ("gelatina_clarificante", "Gelatina clarificante",               "quimico", "kg", 2),
    ("sales_agua",            "Sales minerales para agua de maceración", "quimico", "kg", 3),
]

_LUPULOS_SLUGS   = [s for (s, _, c, _u, _m) in _INSUMOS_ADICIONALES if c == "lupulo"]
_LEVADURAS_SLUGS = [s for (s, _, c, _u, _m) in _INSUMOS_ADICIONALES if c == "levadura"]
_ESPECIALES_SLUGS = [s for (s, _, c, _u, _m) in _INSUMOS_ADICIONALES if c == "especial"]
_MALTAS_SLUGS    = [s for (s, _, c, _u, _m) in _INSUMOS_ADICIONALES if c == "malta"]


def _insumos_adicionales():
    """Crea un Producto (tipo Insumo) por cada fila de _INSUMOS_ADICIONALES, en el mismo orden."""
    productos = []
    for idx, (slug, nombre, categoria, unidad, minimo) in enumerate(_INSUMOS_ADICIONALES, start=14):
        productos.append(Producto(
            codigo=f"INS-{idx:03d}", nombre=nombre,
            tipo="Insumo", unidad_medida=unidad, stock_minimo=minimo,
        ))
    return productos


_NOMBRES_CERVEZA = [
    "Qorikancha", "Wayra", "Apu Dorado", "Tawantinsuyo", "Amaru", "Raymi",
    "Chaska", "Wiraqocha", "Puma Dorado", "Inkari", "Sumaq", "Ayni",
    "Kuntur", "Wari", "Yawar", "Chullpa", "Munay", "Sonqo", "Tinkuy", "Ch'aska",
]
_ESTILOS_CERVEZA = [
    "Golden Ale", "Pale Ale", "Session IPA", "Red Ale", "Brown Ale",
    "Porter", "Scotch Ale", "Saison", "Gose", "Bock", "Cream Ale", "Tripel",
]
_PRESENTACIONES_CERVEZA = [
    "Botella 620ml", "Lata 355ml", "Growler 1L", "Barril 20L", "Edición Limitada",
]


def _terminados_adicionales(cantidad):
    """
    Crea `cantidad` cervezas nuevas combinando nombre + estilo +
    presentación. Todas se miden en litros (igual que las 5 cervezas
    originales): la "presentación" es el nombre comercial de la
    botella o formato, pero lo que se controla en stock es el volumen
    de cerveza, no el número de envases — así se evita mezclar dos
    unidades de medida distintas para el mismo producto.
    """
    productos = []
    for i in range(cantidad):
        nombre_base = _NOMBRES_CERVEZA[i % len(_NOMBRES_CERVEZA)]
        estilo = _ESTILOS_CERVEZA[(i * 3 + 1) % len(_ESTILOS_CERVEZA)]
        presentacion = _PRESENTACIONES_CERVEZA[i % len(_PRESENTACIONES_CERVEZA)]
        nombre = f"{nombre_base} {estilo} — {presentacion}"
        precio = round(38.0 + (i % 12) * 1.8 + (7.0 if "Edición" in presentacion else 0.0), 2)
        minimo = 8 + (i % 5) * 2
        productos.append(Producto(
            codigo=f"PRD-{i + 6:03d}", nombre=nombre,
            descripcion=f"Cerveza artesanal estilo {estilo}, presentación {presentacion}.",
            tipo="Producto terminado", unidad_medida="L",
            precio_venta=precio, stock_minimo=minimo,
        ))
    return productos


def _recetas_adicionales(db, terminados_nuevos, mp, mp2):
    """
    Una receta por cada cerveza nueva. Las proporciones de malta,
    lúpulo y levadura por litro de rendimiento son las MISMAS que ya
    se ven en las 5 recetas originales (Anka Chida, Killa Negra...):
    ≈0.27 kg de malta, ≈0.005 kg de lúpulo y ≈1.5 g de levadura por
    litro. Cada receta suma además un insumo "de autor" (fruta,
    especia o madera, según el índice) y los materiales de embotellado
    (botella, tapa, etiqueta, caja) calculados según el rendimiento del
    lote — así el envase que compramos también se usa de verdad.

    `mp`  = diccionario código -> Producto de los insumos ORIGINALES.
    `mp2` = diccionario slug   -> Producto de los insumos NUEVOS.
    """
    rendimientos_ciclo = [60.0, 70.0, 80.0, 90.0, 100.0]
    recetas = []
    ingredientes_todos = []

    for i, terminado in enumerate(terminados_nuevos):
        rendimiento = rendimientos_ciclo[i % len(rendimientos_ciclo)]
        receta = Receta(
            producto_terminado_id=terminado.id,
            descripcion=f"Lote estándar de {terminado.nombre}, {rendimiento:.0f}L.",
            rendimiento=rendimiento, unidad_rendimiento="L",
        )
        db.add(receta)
        db.flush()  # para tener receta.id antes de crear sus ingredientes

        malta_extra_slug = _MALTAS_SLUGS[i % len(_MALTAS_SLUGS)]
        lupulo_slug = _LUPULOS_SLUGS[i % len(_LUPULOS_SLUGS)]
        levadura_slug = _LEVADURAS_SLUGS[i % len(_LEVADURAS_SLUGS)]
        especial_slug = _ESPECIALES_SLUGS[i % len(_ESPECIALES_SLUGS)]

        cant_malta_base = round(rendimiento * 0.18, 2)
        cant_malta_extra = round(rendimiento * 0.09, 2)
        cant_lupulo = round(rendimiento * 0.005, 3)
        cant_levadura = round(rendimiento * 1.5, 1)
        cant_especial = round(rendimiento * 0.03, 2)
        n_botellas = float(round(rendimiento / 0.62))
        n_cajas = float(max(1, round(n_botellas / 12)))

        lineas = [
            (mp["INS-001"].id, cant_malta_base, "kg"),
            (mp2[malta_extra_slug].id, cant_malta_extra, "kg"),
            (mp2[lupulo_slug].id, cant_lupulo, "kg"),
            (mp2[levadura_slug].id, cant_levadura, "g"),
            (mp2[especial_slug].id, cant_especial, "kg"),
            (mp2["botella_620"].id, n_botellas, "unidad"),
            (mp2["tapa_corona"].id, n_botellas, "unidad"),
            (mp2["etiqueta"].id, n_botellas, "unidad"),
            (mp2["caja_x12"].id, n_cajas, "unidad"),
        ]
        for insumo_id, cantidad, unidad in lineas:
            ingredientes_todos.append(IngredienteReceta(
                receta_id=receta.id, insumo_id=insumo_id,
                cantidad=cantidad, unidad=unidad,
            ))
        recetas.append(receta)

    db.add_all(ingredientes_todos)
    return recetas


_CANTIDAD_COMPRA_POR_CATEGORIA = {
    "malta": 90.0, "lupulo": 10.0, "levadura": 3000.0,
    "especial": 35.0, "envase": 9000.0, "quimico": 15.0,
}
_PRECIO_COMPRA_POR_CATEGORIA = {
    "malta": 4.5, "lupulo": 58.0, "levadura": 0.18,
    "especial": 20.0, "envase": 1.2, "quimico": 12.0,
}
# Excepciones puntuales (unidades más caras o que se compran en lotes chicos)
_CANTIDAD_COMPRA_ESPECIAL = {"caja_x12": 500.0, "precinto": 500.0, "growler_1l": 100.0}
_PRECIO_COMPRA_ESPECIAL = {"growler_1l": 25.0, "caja_x12": 2.0, "precinto": 0.05}


def _compras_adicionales(mp2, mp_original, proveedores_todos):
    """
    Una orden de compra por cada insumo nuevo, para dejar todo el
    inventario con stock ANTES de fabricar las recetas nuevas —
    exactamente el mismo patrón que las 10 compras originales de más
    arriba, solo que en bucle. Las cantidades son generosas a
    propósito: mejor que sobre insumo a que una producción se quede a
    medias por falta de stock (regla FIFO real de logica_inventario.py).
    """
    for i, (slug, nombre, categoria, unidad, minimo) in enumerate(_INSUMOS_ADICIONALES):
        insumo = mp2[slug]
        proveedor = proveedores_todos[i % len(proveedores_todos)]
        cantidad = _CANTIDAD_COMPRA_ESPECIAL.get(slug, _CANTIDAD_COMPRA_POR_CATEGORIA[categoria])
        precio = _PRECIO_COMPRA_ESPECIAL.get(slug, _PRECIO_COMPRA_POR_CATEGORIA[categoria])
        registrar_compra(
            proveedor_id=proveedor.id,
            items=[{"producto_id": insumo.id, "cantidad": cantidad, "precio_unitario": precio}],
            documento_referencia=f"F-GEN-{i + 1:04d}",
        )

    # Top-up de malta de cebada base: las 46 recetas nuevas TAMBIÉN
    # usan este insumo (el mismo de Anka Chida, Killa Negra, etc.), así
    # que hace falta reforzar el stock para que alcance para todo.
    registrar_compra(
        proveedor_id=proveedores_todos[0].id,
        items=[{"producto_id": mp_original["INS-001"].id,
                 "cantidad": 2000.0, "precio_unitario": 4.15}],
        documento_referencia="F-GEN-9999",
    )


def _producciones_adicionales(recetas_nuevas):
    """
    Una orden de producción por cada receta nueva, con la MISMA
    proporción de estados que las 10 órdenes originales: 7 de cada 10
    cerradas, 2 en proceso, 1 recién iniciada.
    """
    contador_lote = 11
    for i, receta in enumerate(recetas_nuevas):
        numero_lote = f"LOTE-2026-{contador_lote:03d}"
        contador_lote += 1
        planeada = receta.rendimiento

        op = crear_orden(
            receta_id=receta.id, cantidad_planeada=planeada,
            numero_lote=numero_lote,
            observaciones=f"Lote generado — {receta.descripcion}",
        )

        posicion = i % 10
        if posicion < 7:                       # 7 de cada 10 -> CERRADA
            iniciar_proceso(op.id)
            factor_real = 0.94 + (i % 4) * 0.01     # entre 0.94 y 0.97
            real = round(planeada * factor_real, 1)
            merma = round(planeada - real, 1)
            cerrar_orden(
                op.id, cantidad_real=real, cantidad_merma=merma,
                causa_merma="Pérdida normal de proceso",
                costo_mano_obra=round(planeada * 1.9, 2),
                costos_indirectos=round(planeada * 0.65, 2),
            )
        elif posicion < 9:                     # 2 de cada 10 -> EN_PROCESO
            iniciar_proceso(op.id)
        # el resto (1 de cada 10) se queda INICIADA, tal cual se crea


def _ventas_adicionales(terminados_nuevos, clientes_todos):
    """
    Vende parte del stock recién producido de cada cerveza nueva,
    repartido entre varios clientes nuevos. Antes de cada venta se
    consulta el stock REAL en la base de datos (con stock_total, la
    misma función que usa el resto del sistema) — no un cálculo hecho
    a mano — para no arriesgarse a pedir más de lo que hay.
    """
    contador_venta = 0
    for i, terminado in enumerate(terminados_nuevos):
        with nueva_sesion() as db:
            disponible = stock_total(db, terminado.id)
        if disponible < 1:
            continue  # esta cerveza todavía no tiene producción cerrada

        precio = round(40.0 + (i % 10) * 1.5, 2)

        cliente = clientes_todos[contador_venta % len(clientes_todos)]
        cantidad = round(disponible * 0.35, 1)
        if cantidad >= 1:
            registrar_venta(
                cliente_id=cliente.id,
                items=[{"producto_id": terminado.id, "cantidad": cantidad,
                        "precio_unitario": precio}],
            )
            contador_venta += 1

        with nueva_sesion() as db:
            disponible2 = stock_total(db, terminado.id)
        if disponible2 >= 2:
            cliente2 = clientes_todos[(contador_venta + 5) % len(clientes_todos)]
            cantidad2 = round(disponible2 * 0.3, 1)
            if cantidad2 >= 1:
                registrar_venta(
                    cliente_id=cliente2.id,
                    items=[{"producto_id": terminado.id, "cantidad": cantidad2,
                            "precio_unitario": round(precio * 0.98, 2)}],
                )
                contador_venta += 1


_TIPOS_CLIENTE_JURIDICO = [
    "Restobar", "Restaurant", "Hotel Boutique", "Distribuidora",
    "Bodega", "Supermercado", "Licorería", "Mercado", "Feria Gastronómica",
    "Club Social", "Grifo y Minimarket", "Pub",
]


def _clientes_adicionales(cantidad):
    """Clientes extra: alterna entre empresas (JURIDICA) y personas (NATURAL)."""
    clientes = []
    for i in range(cantidad):
        if i % 2 == 0:
            tipo_neg = _TIPOS_CLIENTE_JURIDICO[i % len(_TIPOS_CLIENTE_JURIDICO)]
            lugar = _LUGARES_CUSCO[(i * 2) % len(_LUGARES_CUSCO)]
            forma = _FORMAS_LEGALES[i % len(_FORMAS_LEGALES)]
            slug = tipo_neg.lower().replace(" ", "")
            clientes.append(Cliente(
                tipo="JURIDICA", nombre=f"{tipo_neg} {lugar} {forma}",
                documento=f"20{800000000 + i:09d}",
                telefono=f"984{400000 + i:06d}",
                email=f"contacto{i + 1}@{slug}.pe",
            ))
        else:
            nombre_p = _NOMBRES[(i * 3 + 2) % len(_NOMBRES)]
            apellido1 = _APELLIDOS[(i * 5) % len(_APELLIDOS)]
            apellido2 = _APELLIDOS[(i * 11 + 4) % len(_APELLIDOS)]
            clientes.append(Cliente(
                tipo="NATURAL", nombre=f"{nombre_p} {apellido1} {apellido2}",
                documento=f"{40000000 + i:08d}",
                telefono=f"984{500000 + i:06d}",
            ))
    return clientes


# ══════════════════════════════════════════════════════════════════
#  CARGA PRINCIPAL
# ══════════════════════════════════════════════════════════════════

def cargar_datos_iniciales():
    with nueva_sesion() as db:
        if db.query(Usuario).count() > 0:
            return  # ya inicializado

        # ══════════════════════════════════════════════════════════
        # PARTE 1 — USUARIOS (6 — uno por rol, credenciales de prueba)
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

        # ══════════════════════════════════════════════════════════
        # PARTE 2 — datos generados (ver funciones al inicio del archivo)
        # ══════════════════════════════════════════════════════════
        usuarios_extra = _usuarios_adicionales()
        db.add_all(usuarios_extra)

        proveedores_extra = _proveedores_adicionales(43)
        db.add_all(proveedores_extra)

        insumos_extra = _insumos_adicionales()
        db.add_all(insumos_extra)

        terminados_extra = _terminados_adicionales(62)
        db.add_all(terminados_extra)

        clientes_extra = _clientes_adicionales(43)
        db.add_all(clientes_extra)

        db.flush()  # IDs para todo lo de arriba, antes de armar las recetas nuevas

        mp2 = {slug: prod for (slug, *_resto), prod in zip(_INSUMOS_ADICIONALES, insumos_extra)}
        recetas_extra = _recetas_adicionales(db, terminados_extra, mp, mp2)

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

    # ══════════════════════════════════════════════════════════
    # PARTE 2 — compras, producción y ventas generadas
    # ══════════════════════════════════════════════════════════
    proveedores_todos = proveedores + proveedores_extra
    clientes_todos = clientes + clientes_extra

    _compras_adicionales(mp2, mp, proveedores_todos)
    _producciones_adicionales(recetas_extra)
    _ventas_adicionales(terminados_extra, clientes_todos)

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

    print("[datos_iniciales] Base de datos inicializada con datos completos de ejemplo "
          "(50+ filas por tabla).")