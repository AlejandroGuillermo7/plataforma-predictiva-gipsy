"""
seed.py
-------
Crea la base de datos y la llena con DATOS DE EJEMPLO para demostrar la
plataforma. No son ventas reales de Gipsy: cuando se tenga el historial real,
se carga desde la pantalla "Importar historial".

Uso:
    python seed.py            # crea las tablas y los datos de ejemplo (borra lo anterior)
    python seed.py --vacio    # solo crea las tablas, catálogos y usuarios
"""

import random
import sys
from datetime import date, datetime, timedelta

from app import create_app, db
from app.models import (Categoria, Color, DetalleVenta, Importacion, Producto,
                        Proveedor, Rol, Talla, Usuario, Variante, Venta)
from app.modulo_predictivo import generar_predicciones

USUARIOS = [  # nombre, usuario, contraseña, rol
    ("Administrador del sistema", "admin", "admin123", "Administrador"),
    ("Gerente de Gipsy", "gerente", "gerente123", "Gerente"),
    ("Vendedora 1", "vendedor", "vendedor123", "Vendedor"),
]

# modelo, descripción, categoría, temporada, colores, precio
PRODUCTOS = [
    ("B-12", "Blusa básica de algodón", "Blusa", "Todo el año", ["Blanco", "Negro"], 250),
    ("B-20", "Blusa de manga corta", "Blusa", "Primavera-Verano", ["Rosa", "Azul"], 230),
    ("F-05", "Falda midi", "Falda", "Primavera-Verano", ["Negro", "Azul"], 320),
    ("V-07", "Vestido casual", "Vestido", "Primavera-Verano", ["Negro", "Rojo"], 450),
    ("V-15", "Vestido de fiesta", "Vestido", "Todo el año", ["Negro", "Vino"], 690),
    ("P-03", "Pantalón de vestir", "Pantalón", "Todo el año", ["Beige", "Negro"], 380),
    ("S-08", "Suéter tejido", "Suéter", "Otoño-Invierno", ["Gris", "Vino"], 420),
]
TALLAS = ["CH", "M", "G", "XG"]
PESO_TALLA = {"CH": 0.8, "M": 1.3, "G": 1.0, "XG": 0.4}


def factor_temporada(temporada: str, mes: int) -> float:
    """Multiplica la demanda según la temporada de la prenda."""
    if temporada == "Primavera-Verano":
        return 1.6 if mes in (3, 4, 5, 6, 7, 8) else 0.5
    if temporada == "Otoño-Invierno":
        return 1.8 if mes in (10, 11, 12, 1, 2) else 0.3
    return 1.2 if mes in (5, 12) else 1.0  # mayo (Día de las Madres) y diciembre


def crear_catalogos():
    roles = {n: Rol(nombre=n) for n in ("Administrador", "Gerente", "Vendedor")}
    db.session.add_all(roles.values())
    for nombre, usuario, contrasena, rol in USUARIOS:
        u = Usuario(nombre=nombre, usuario=usuario, rol=roles[rol])
        u.set_contrasena(contrasena)
        db.session.add(u)
    db.session.add_all([Talla(nombre=t) for t in TALLAS])
    db.session.add_all([Categoria(nombre=c) for c in ("Blusa", "Falda", "Vestido", "Pantalón", "Suéter", "Sin categoría")])
    db.session.add(Proveedor(nombre="Proveedor de ejemplo", ciudad="Ciudad de México"))
    db.session.commit()


def crear_productos(rng: random.Random):
    tallas = {t.nombre: t for t in Talla.query.all()}
    variantes = []
    for modelo, desc, cat, temporada, colores, precio in PRODUCTOS:
        categoria = Categoria.query.filter_by(nombre=cat).one()
        p = Producto(modelo=modelo, descripcion=desc, temporada=temporada, categoria=categoria)
        db.session.add(p)
        for nombre_color in colores:
            color = Color.query.filter_by(nombre=nombre_color).first() or Color(nombre=nombre_color)
            db.session.add(color)
            for t in TALLAS:
                v = Variante(producto=p, talla=tallas[t], color=color, precio_venta=precio,
                             costo=round(precio * 0.5, 2), stock=rng.randint(2, 14))
                db.session.add(v)
                variantes.append((v, temporada, PESO_TALLA[t]))
    db.session.commit()
    return variantes


def crear_ventas(variantes, rng: random.Random):
    """Simula ventas diarias desde enero de 2025 hasta hoy."""
    admin = Usuario.query.filter_by(usuario="admin").one()
    vendedor = Usuario.query.filter_by(usuario="vendedor").one()
    imp = Importacion(archivo="historial_ejemplo.xlsx", id_usuario=admin.id_usuario)
    db.session.add(imp)
    db.session.flush()

    # Una variante deja de venderse en junio de 2026 para mostrar la "baja rotación"
    rezagada = next(v for v, _, _ in variantes if v.producto.modelo == "P-03" and v.talla.nombre == "XG")
    inicio, fin = date(2025, 1, 1), date.today()
    corte_sistema = date(2026, 10, 1)  # a partir de aquí son ventas capturadas en el sistema
    dia, total_ventas, cargadas = inicio, 0, 0
    while dia <= fin:
        for v, temporada, peso in variantes:
            if v is rezagada and dia >= date(2026, 6, 1):
                continue
            tasa = 0.11 * peso * factor_temporada(temporada, dia.month)
            if rng.random() < tasa:
                cantidad = 1 if rng.random() < 0.8 else 2
                historica = dia < corte_sistema
                hora = datetime(dia.year, dia.month, dia.day, rng.randint(10, 19), rng.randint(0, 59))
                if hora > datetime.now():  # hoy: solo ventas que ya pudieron ocurrir
                    hora = datetime.now() - timedelta(minutes=rng.randint(5, 120))
                venta = Venta(fecha=hora, total=v.precio_venta * cantidad,
                              origen="Historico" if historica else "Sistema",
                              id_usuario=(admin if historica else vendedor).id_usuario,
                              id_importacion=imp.id_importacion if historica else None)
                venta.detalles.append(DetalleVenta(variante=v, cantidad=cantidad, precio_unitario=v.precio_venta))
                db.session.add(venta)
                total_ventas += 1
                cargadas += historica
        dia += timedelta(days=1)
    imp.filas_cargadas = cargadas
    db.session.commit()
    return total_ventas


def main():
    app = create_app()
    with app.app_context():
        db.drop_all()
        db.create_all()
        crear_catalogos()
        print("Tablas, catálogos y usuarios creados.")
        if "--vacio" in sys.argv:
            return
        rng = random.Random(7)
        variantes = crear_productos(rng)
        n = crear_ventas(variantes, rng)
        print(f"{len(variantes)} variantes y {n} ventas de ejemplo creadas.")
        r = generar_predicciones(db.engine)
        print(f"Predicciones de {r['periodo']}: {r['algoritmo']} (MAE {r['mae']} piezas), "
              f"comparación: {r['errores']}")
    print("Listo. Usuarios: admin/admin123, gerente/gerente123, vendedor/vendedor123")


if __name__ == "__main__":
    main()
