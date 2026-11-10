"""
Modelos de la base de datos (las 14 tablas del modelo relacional del proyecto).
Cada clase corresponde a una tabla; los nombres coinciden con el diccionario
de datos del reporte.
"""

from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import CheckConstraint, UniqueConstraint, func
from werkzeug.security import check_password_hash, generate_password_hash

from . import db, login_manager


class Rol(db.Model):
    __tablename__ = "rol"
    id_rol = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), unique=True, nullable=False)


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuario"
    id_usuario = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    usuario = db.Column(db.String(30), unique=True, nullable=False)
    contrasena_hash = db.Column(db.String(255), nullable=False)
    id_rol = db.Column(db.Integer, db.ForeignKey("rol.id_rol"), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    rol = db.relationship("Rol")

    def get_id(self):
        return str(self.id_usuario)

    def set_contrasena(self, contrasena: str) -> None:
        """Guarda la contraseña cifrada (nunca en texto plano)."""
        self.contrasena_hash = generate_password_hash(contrasena)

    def verificar_contrasena(self, contrasena: str) -> bool:
        return check_password_hash(self.contrasena_hash, contrasena)

    def tiene_rol(self, *roles: str) -> bool:
        return self.rol.nombre in roles


@login_manager.user_loader
def cargar_usuario(id_usuario):
    return db.session.get(Usuario, int(id_usuario))


class Categoria(db.Model):
    __tablename__ = "categoria"
    id_categoria = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(40), unique=True, nullable=False)


class Proveedor(db.Model):
    __tablename__ = "proveedor"
    id_proveedor = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    telefono = db.Column(db.String(15))
    ciudad = db.Column(db.String(50))


class Producto(db.Model):
    __tablename__ = "producto"
    id_producto = db.Column(db.Integer, primary_key=True)
    modelo = db.Column(db.String(30), unique=True, nullable=False)
    descripcion = db.Column(db.String(150))
    temporada = db.Column(db.String(20), nullable=False, default="Todo el año")
    id_categoria = db.Column(db.Integer, db.ForeignKey("categoria.id_categoria"), nullable=False)
    categoria = db.relationship("Categoria")


class Talla(db.Model):
    __tablename__ = "talla"
    id_talla = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(10), unique=True, nullable=False)


class Color(db.Model):
    __tablename__ = "color"
    id_color = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), unique=True, nullable=False)


class Variante(db.Model):
    """Combinación única de producto, talla y color. Es la unidad de inventario."""
    __tablename__ = "variante"
    __table_args__ = (
        UniqueConstraint("id_producto", "id_talla", "id_color"),
        CheckConstraint("stock >= 0", name="ck_stock_no_negativo"),
    )
    id_variante = db.Column(db.Integer, primary_key=True)
    id_producto = db.Column(db.Integer, db.ForeignKey("producto.id_producto"), nullable=False)
    id_talla = db.Column(db.Integer, db.ForeignKey("talla.id_talla"), nullable=False)
    id_color = db.Column(db.Integer, db.ForeignKey("color.id_color"), nullable=False)
    precio_venta = db.Column(db.Numeric(10, 2), nullable=False)
    costo = db.Column(db.Numeric(10, 2), nullable=False)
    stock = db.Column(db.Integer, nullable=False, default=0)
    producto = db.relationship("Producto")
    talla = db.relationship("Talla")
    color = db.relationship("Color")

    @property
    def etiqueta(self) -> str:
        return f"{self.producto.modelo} · {self.talla.nombre} · {self.color.nombre}"


class Importacion(db.Model):
    __tablename__ = "importacion"
    id_importacion = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
    archivo = db.Column(db.String(150), nullable=False)
    filas_cargadas = db.Column(db.Integer, nullable=False, default=0)
    filas_rechazadas = db.Column(db.Integer, nullable=False, default=0)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)


class Venta(db.Model):
    __tablename__ = "venta"
    id_venta = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.now)
    total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    estado = db.Column(db.String(10), nullable=False, default="Activa")  # Activa / Cancelada
    origen = db.Column(db.String(10), nullable=False, default="Sistema")  # Sistema / Historico
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)
    id_importacion = db.Column(db.Integer, db.ForeignKey("importacion.id_importacion"))
    usuario = db.relationship("Usuario")
    detalles = db.relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")


class DetalleVenta(db.Model):
    __tablename__ = "detalle_venta"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_dv_cantidad"),)
    id_venta = db.Column(db.Integer, db.ForeignKey("venta.id_venta"), primary_key=True)
    id_variante = db.Column(db.Integer, db.ForeignKey("variante.id_variante"), primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    precio_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    venta = db.relationship("Venta", back_populates="detalles")
    variante = db.relationship("Variante")


class Compra(db.Model):
    __tablename__ = "compra"
    id_compra = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.Date, nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)
    id_proveedor = db.Column(db.Integer, db.ForeignKey("proveedor.id_proveedor"), nullable=False)
    id_usuario = db.Column(db.Integer, db.ForeignKey("usuario.id_usuario"), nullable=False)


class DetalleCompra(db.Model):
    __tablename__ = "detalle_compra"
    __table_args__ = (CheckConstraint("cantidad > 0", name="ck_dc_cantidad"),)
    id_compra = db.Column(db.Integer, db.ForeignKey("compra.id_compra"), primary_key=True)
    id_variante = db.Column(db.Integer, db.ForeignKey("variante.id_variante"), primary_key=True)
    cantidad = db.Column(db.Integer, nullable=False)
    costo_unitario = db.Column(db.Numeric(10, 2), nullable=False)


class Prediccion(db.Model):
    __tablename__ = "prediccion"
    id_prediccion = db.Column(db.Integer, primary_key=True)
    id_variante = db.Column(db.Integer, db.ForeignKey("variante.id_variante"), nullable=False)
    periodo_inicio = db.Column(db.Date, nullable=False)
    periodo_fin = db.Column(db.Date, nullable=False)
    cantidad_estimada = db.Column(db.Integer, nullable=False)
    algoritmo = db.Column(db.String(40), nullable=False)
    mae = db.Column(db.Numeric(8, 2))
    fecha_generacion = db.Column(db.DateTime, nullable=False, server_default=func.now())
    variante = db.relationship("Variante")
