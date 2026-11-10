"""
Vistas de la plataforma: panel, inventario, ventas, usuarios,
importación del historial y predicciones.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from . import db, importador, modulo_predictivo
from .auth import requiere_rol
from .models import (Categoria, Color, DetalleVenta, Importacion, Prediccion,
                     Producto, Rol, Talla, Usuario, Variante, Venta)

bp = Blueprint("views", __name__)

DIAS_BAJA_ROTACION = 60


# ----------------------------------------------------------------- consultas
def predicciones_actuales():
    """Predicciones del periodo más reciente, con stock y cantidad sugerida."""
    ultimo = db.session.query(func.max(Prediccion.periodo_inicio)).scalar()
    if ultimo is None:
        return None, []
    filas = []
    for p in Prediccion.query.filter_by(periodo_inicio=ultimo).all():
        v = p.variante
        filas.append({
            "variante": v,
            "stock": v.stock,
            "estimado": p.cantidad_estimada,
            "sugerido": max(p.cantidad_estimada - v.stock, 0),
            "alerta": v.stock < p.cantidad_estimada,
            "pred": p,
        })
    filas.sort(key=lambda f: (-f["sugerido"], -f["estimado"]))
    return ultimo, filas


def baja_rotacion(dias: int = DIAS_BAJA_ROTACION):
    """Variantes con existencias que no se han vendido en los últimos `dias` días (HU08)."""
    ultimas = dict(
        db.session.query(DetalleVenta.id_variante, func.max(Venta.fecha))
        .join(Venta, Venta.id_venta == DetalleVenta.id_venta)
        .filter(Venta.estado == "Activa")
        .group_by(DetalleVenta.id_variante)
        .all()
    )
    limite = datetime.now() - timedelta(days=dias)
    resultado = []
    for v in Variante.query.filter(Variante.stock > 0).all():
        ultima = ultimas.get(v.id_variante)
        if isinstance(ultima, str):  # SQLite puede devolver texto
            ultima = datetime.fromisoformat(ultima)
        if ultima is None or ultima < limite:
            resultado.append({"variante": v, "ultima": ultima})
    resultado.sort(key=lambda r: r["ultima"] or datetime.min)
    return resultado


# --------------------------------------------------------------------- panel
@bp.route("/")
@login_required
def panel():
    """Pantalla 2: resumen del día."""
    hoy = date.today()
    inicio = datetime.combine(hoy, datetime.min.time())
    ventas_hoy = (db.session.query(func.coalesce(func.sum(Venta.total), 0))
                  .filter(Venta.fecha >= inicio, Venta.estado == "Activa").scalar())
    periodo, preds = predicciones_actuales()
    alertas = [f for f in preds if f["alerta"]]
    rezagadas = baja_rotacion()
    return render_template("panel.html", ventas_hoy=ventas_hoy, alertas=alertas,
                           rezagadas=rezagadas, periodo=periodo)


# ---------------------------------------------------------------- inventario
@bp.route("/inventario")
@login_required
def inventario():
    """Pantalla 4: consulta de existencias con filtros (HU04)."""
    q = (Variante.query.join(Producto).join(Talla).join(Color)
         .join(Categoria, Producto.id_categoria == Categoria.id_categoria))
    filtros = {k: request.args.get(k, "") for k in ("modelo", "categoria", "talla", "color")}
    if filtros["modelo"]:
        q = q.filter(Producto.modelo.ilike(f"%{filtros['modelo']}%"))
    if filtros["categoria"]:
        q = q.filter(Categoria.id_categoria == int(filtros["categoria"]))
    if filtros["talla"]:
        q = q.filter(Talla.id_talla == int(filtros["talla"]))
    if filtros["color"]:
        q = q.filter(Color.id_color == int(filtros["color"]))
    variantes = q.order_by(Producto.modelo, Talla.id_talla, Color.nombre).all()
    return render_template("inventario.html", variantes=variantes, filtros=filtros,
                           categorias=Categoria.query.order_by(Categoria.nombre).all(),
                           tallas=Talla.query.order_by(Talla.id_talla).all(),
                           colores=Color.query.order_by(Color.nombre).all())


@bp.route("/inventario/nuevo", methods=["POST"])
@requiere_rol("Administrador")
def nuevo_producto():
    """Alta de producto y variante (HU02). Si la variante ya existe, suma el stock."""
    f = request.form
    try:
        modelo = f["modelo"].strip().upper()
        precio, costo, stock = Decimal(f["precio"]), Decimal(f["costo"]), int(f["stock"])
        if not modelo or precio <= 0 or costo < 0 or stock < 0:
            raise ValueError
    except (KeyError, ValueError, ArithmeticError):
        flash("Revisa los datos del producto: modelo, precio, costo y stock son obligatorios.", "error")
        return redirect(url_for("views.inventario"))

    producto = Producto.query.filter_by(modelo=modelo).first()
    if producto is None:
        producto = Producto(modelo=modelo, descripcion=f.get("descripcion", "").strip(),
                            temporada=f.get("temporada", "Todo el año"),
                            id_categoria=int(f["categoria"]))
        db.session.add(producto)
        db.session.flush()
    color_nombre = f["color"].strip().capitalize()
    color = Color.query.filter_by(nombre=color_nombre).first() or Color(nombre=color_nombre)
    db.session.add(color)
    db.session.flush()
    variante = Variante.query.filter_by(id_producto=producto.id_producto, id_talla=int(f["talla"]),
                                        id_color=color.id_color).first()
    if variante:
        variante.stock += stock
        flash(f"La variante {variante.etiqueta} ya existía: se sumaron {stock} piezas.", "ok")
    else:
        variante = Variante(id_producto=producto.id_producto, id_talla=int(f["talla"]),
                            id_color=color.id_color, precio_venta=precio, costo=costo, stock=stock)
        db.session.add(variante)
        flash(f"Producto {modelo} registrado.", "ok")
    db.session.commit()
    return redirect(url_for("views.inventario"))


# -------------------------------------------------------------------- ventas
@bp.route("/ventas")
@requiere_rol("Vendedor", "Gerente")
def ventas():
    """Pantalla 5: registro de ventas y últimas ventas del sistema."""
    variantes = (Variante.query.join(Producto).filter(Variante.stock > 0)
                 .order_by(Producto.modelo).all())
    recientes = (Venta.query.filter_by(origen="Sistema")
                 .order_by(Venta.fecha.desc()).limit(15).all())
    return render_template("ventas.html", variantes=variantes, recientes=recientes)


@bp.route("/ventas/nueva", methods=["POST"])
@requiere_rol("Vendedor", "Gerente")
def nueva_venta():
    """Registra una venta y descuenta el inventario (HU03). No vende sin existencia."""
    piezas = {}
    for id_var, cant in zip(request.form.getlist("variante"), request.form.getlist("cantidad")):
        if id_var and cant and int(cant) > 0:
            piezas[int(id_var)] = piezas.get(int(id_var), 0) + int(cant)
    if not piezas:
        flash("Agrega al menos una prenda con cantidad.", "error")
        return redirect(url_for("views.ventas"))

    venta = Venta(id_usuario=current_user.id_usuario, origen="Sistema")
    total = Decimal(0)
    for id_var, cant in piezas.items():
        v = db.session.get(Variante, id_var)
        if v is None or v.stock < cant:
            db.session.rollback()
            flash(f"Sin existencia suficiente de {v.etiqueta if v else 'la prenda'}.", "error")
            return redirect(url_for("views.ventas"))
        v.stock -= cant
        venta.detalles.append(DetalleVenta(id_variante=id_var, cantidad=cant,
                                           precio_unitario=v.precio_venta))
        total += v.precio_venta * cant
    venta.total = total
    db.session.add(venta)
    db.session.commit()
    flash(f"Venta registrada por ${total:,.2f}.", "ok")
    return redirect(url_for("views.ventas"))


@bp.route("/ventas/<int:id_venta>/cancelar", methods=["POST"])
@requiere_rol("Gerente")
def cancelar_venta(id_venta):
    """Solo el gerente cancela; el stock se regresa (HU05)."""
    venta = db.get_or_404(Venta, id_venta)
    if venta.estado == "Activa":
        for d in venta.detalles:
            d.variante.stock += d.cantidad
        venta.estado = "Cancelada"
        db.session.commit()
        flash(f"Venta {id_venta} cancelada y stock devuelto.", "ok")
    return redirect(url_for("views.ventas"))


# ------------------------------------------------------------------ usuarios
@bp.route("/usuarios", methods=["GET", "POST"])
@requiere_rol("Administrador")
def usuarios():
    """Pantalla 6: administración de usuarios (HU09)."""
    if request.method == "POST":
        f = request.form
        if not (f.get("nombre") and f.get("usuario") and len(f.get("contrasena", "")) >= 6):
            flash("Nombre, usuario y una contraseña de al menos 6 caracteres son obligatorios.", "error")
        elif Usuario.query.filter_by(usuario=f["usuario"].strip()).first():
            flash("Ese nombre de usuario ya existe.", "error")
        else:
            u = Usuario(nombre=f["nombre"].strip(), usuario=f["usuario"].strip(), id_rol=int(f["rol"]))
            u.set_contrasena(f["contrasena"])
            db.session.add(u)
            db.session.commit()
            flash(f"Usuario {u.usuario} creado.", "ok")
        return redirect(url_for("views.usuarios"))
    return render_template("usuarios.html", usuarios=Usuario.query.order_by(Usuario.nombre).all(),
                           roles=Rol.query.all())


@bp.route("/usuarios/<int:id_usuario>/estado", methods=["POST"])
@requiere_rol("Administrador")
def cambiar_estado(id_usuario):
    """Activa o desactiva un usuario (baja lógica)."""
    u = db.get_or_404(Usuario, id_usuario)
    if u.id_usuario == current_user.id_usuario:
        flash("No puedes desactivar tu propio usuario.", "error")
    else:
        u.activo = not u.activo
        db.session.commit()
    return redirect(url_for("views.usuarios"))


# ------------------------------------------------------------------ importar
@bp.route("/importar", methods=["GET", "POST"])
@requiere_rol("Administrador")
def importar():
    """Pantalla 7: importar historial de ventas desde Excel o CSV (HU11, HU12)."""
    resumen = None
    if request.method == "POST":
        archivo = request.files.get("archivo")
        if not archivo or not archivo.filename:
            flash("Selecciona un archivo .xlsx o .csv.", "error")
        else:
            try:
                df = importador.leer_archivo(archivo, archivo.filename)
                validos, rechazados = importador.limpiar(df)
                imp = importador.guardar(validos, rechazados, archivo.filename, current_user.id_usuario)
                motivos = rechazados["motivo"].value_counts().to_dict() if len(rechazados) else {}
                resumen = {"imp": imp, "motivos": motivos}
            except Exception as error:  # archivo dañado o sin columnas
                db.session.rollback()
                flash(f"No se pudo importar el archivo: {error}", "error")
    historial = Importacion.query.order_by(Importacion.fecha.desc()).limit(10).all()
    return render_template("importar.html", resumen=resumen, historial=historial,
                           columnas=importador.COLUMNAS)


# -------------------------------------------------------------- predicciones
@bp.route("/predicciones")
@requiere_rol("Gerente")
def predicciones():
    """Pantalla 3: predicciones, alertas de desabasto y baja rotación (HU06, HU07, HU08)."""
    periodo, filas = predicciones_actuales()
    return render_template("predicciones.html", periodo=periodo, filas=filas,
                           rezagadas=baja_rotacion(), dias=DIAS_BAJA_ROTACION)


@bp.route("/predicciones/actualizar", methods=["POST"])
@requiere_rol("Gerente")
def actualizar_predicciones():
    """Entrena el modelo con el historial actual y regenera las predicciones (HU13)."""
    try:
        r = modulo_predictivo.generar_predicciones(db.engine)
        flash(f"Predicciones de {r['periodo']} generadas con {r['algoritmo']} "
              f"(MAE {r['mae']} piezas) para {r['predicciones']} variantes.", "ok")
    except ValueError as error:
        flash(str(error), "error")
    return redirect(url_for("views.predicciones"))
