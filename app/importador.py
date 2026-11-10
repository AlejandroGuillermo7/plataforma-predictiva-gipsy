"""
Importación y limpieza del historial de ventas (HU11, HU12).

El archivo (Excel o CSV) debe tener las columnas:
    fecha, modelo, talla, color, cantidad, precio
y opcionalmente: categoria
"""

import pandas as pd

from . import db
from .models import (Categoria, Color, DetalleVenta, Importacion, Producto,
                     Talla, Variante, Venta)

COLUMNAS = ["fecha", "modelo", "talla", "color", "cantidad", "precio"]

# Equivalencias para unificar cómo se escriben las tallas
TALLAS = {
    "ch": "CH", "chica": "CH", "s": "CH", "small": "CH",
    "m": "M", "mediana": "M", "med": "M", "medium": "M",
    "g": "G", "grande": "G", "l": "G", "large": "G",
    "xg": "XG", "extra grande": "XG", "xl": "XG",
}


def leer_archivo(archivo, nombre: str) -> pd.DataFrame:
    """Lee un archivo .xlsx o .csv y normaliza el nombre de las columnas."""
    if nombre.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(archivo)
    else:
        df = pd.read_csv(archivo)
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltantes = [c for c in COLUMNAS if c not in df.columns]
    if faltantes:
        raise ValueError(f"Faltan columnas en el archivo: {', '.join(faltantes)}")
    return df


def limpiar(df: pd.DataFrame):
    """Valida y estandariza los datos. Devuelve (válidos, rechazados con motivo).

    Una fila con error se rechaza sola; el resto se sigue cargando (RNF12).
    """
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce", dayfirst=True)
    df["modelo"] = df["modelo"].astype(str).str.strip().str.upper().replace({"NAN": None, "": None})
    df["talla"] = df["talla"].astype(str).str.strip().str.lower().map(TALLAS)
    df["color"] = df["color"].astype(str).str.strip().str.capitalize().replace({"Nan": None, "": None})
    df["cantidad"] = pd.to_numeric(df["cantidad"], errors="coerce")
    df["precio"] = pd.to_numeric(df["precio"], errors="coerce")
    if "categoria" in df.columns:
        df["categoria"] = df["categoria"].astype(str).str.strip().str.capitalize()
    else:
        df["categoria"] = "Sin categoría"

    motivos = pd.Series("", index=df.index)
    motivos[df["fecha"].isna()] = "sin fecha"
    motivos[(motivos == "") & df["modelo"].isna()] = "sin modelo"
    motivos[(motivos == "") & df["talla"].isna()] = "talla desconocida"
    motivos[(motivos == "") & df["color"].isna()] = "sin color"
    motivos[(motivos == "") & ~(df["cantidad"] > 0)] = "cantidad inválida"
    motivos[(motivos == "") & ~(df["precio"] > 0)] = "precio inválido"

    rechazados = df[motivos != ""].assign(motivo=motivos[motivos != ""])
    validos = df[motivos == ""].drop_duplicates()
    validos = validos.assign(cantidad=validos["cantidad"].astype(int))
    return validos, rechazados


def _obtener(modelo, filtro: dict, **extra):
    """Busca un registro y, si no existe, lo crea."""
    obj = modelo.query.filter_by(**filtro).first()
    if obj is None:
        obj = modelo(**filtro, **extra)
        db.session.add(obj)
        db.session.flush()
    return obj


def guardar(validos: pd.DataFrame, rechazados: pd.DataFrame, nombre: str, id_usuario: int) -> Importacion:
    """Guarda las filas válidas como ventas históricas y registra la importación."""
    imp = Importacion(archivo=nombre, filas_cargadas=len(validos),
                      filas_rechazadas=len(rechazados), id_usuario=id_usuario)
    db.session.add(imp)
    db.session.flush()

    for fila in validos.itertuples(index=False):
        categoria = _obtener(Categoria, {"nombre": fila.categoria})
        producto = _obtener(Producto, {"modelo": fila.modelo}, id_categoria=categoria.id_categoria)
        talla = _obtener(Talla, {"nombre": fila.talla})
        color = _obtener(Color, {"nombre": fila.color})
        variante = _obtener(
            Variante,
            {"id_producto": producto.id_producto, "id_talla": talla.id_talla, "id_color": color.id_color},
            precio_venta=fila.precio, costo=round(fila.precio * 0.5, 2), stock=0,
        )
        venta = Venta(fecha=fila.fecha.to_pydatetime(), total=fila.precio * fila.cantidad,
                      origen="Historico", id_usuario=id_usuario, id_importacion=imp.id_importacion)
        venta.detalles.append(DetalleVenta(id_variante=variante.id_variante,
                                           cantidad=fila.cantidad, precio_unitario=fila.precio))
        db.session.add(venta)

    db.session.commit()
    return imp
