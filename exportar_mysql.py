"""
exportar_mysql.py
-----------------
Genera un archivo .sql para MySQL 8 con la estructura de la base de datos
gipsy_db y todos los datos que tiene la plataforma (instance/gipsy.db).

Uso:
    python exportar_mysql.py              # crea sql/gipsy_db_mysql.sql
Después, en MySQL Workbench: File > Open SQL Script > Ejecutar (rayo).
"""

import os
import sqlite3
import sys

ORIGEN = os.path.join(os.path.dirname(__file__), "instance", "gipsy.db")
DESTINO = os.path.join(os.path.dirname(__file__), "sql", "gipsy_db_mysql.sql")

ESTRUCTURA = """-- =============================================================
-- Base de datos: gipsy_db (MySQL 8)
-- Plataforma de Análisis Predictivo Gipsy - Equipo 4, ITO
-- Contiene DATOS DE EJEMPLO generados por seed.py (no son ventas reales).
-- =============================================================
DROP DATABASE IF EXISTS gipsy_db;
CREATE DATABASE gipsy_db CHARACTER SET utf8mb4 COLLATE utf8mb4_spanish_ci;
USE gipsy_db;

CREATE TABLE rol (
  id_rol INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE usuario (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  usuario VARCHAR(30) NOT NULL UNIQUE,
  contrasena_hash VARCHAR(255) NOT NULL,
  id_rol INT NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  FOREIGN KEY (id_rol) REFERENCES rol(id_rol)
);

CREATE TABLE categoria (
  id_categoria INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(40) NOT NULL UNIQUE
);

CREATE TABLE proveedor (
  id_proveedor INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(80) NOT NULL,
  telefono VARCHAR(15),
  ciudad VARCHAR(50)
);

CREATE TABLE producto (
  id_producto INT AUTO_INCREMENT PRIMARY KEY,
  modelo VARCHAR(30) NOT NULL UNIQUE,
  descripcion VARCHAR(150),
  temporada VARCHAR(20) NOT NULL DEFAULT 'Todo el año',
  id_categoria INT NOT NULL,
  FOREIGN KEY (id_categoria) REFERENCES categoria(id_categoria)
);

CREATE TABLE talla (
  id_talla INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(10) NOT NULL UNIQUE
);

CREATE TABLE color (
  id_color INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE variante (
  id_variante INT AUTO_INCREMENT PRIMARY KEY,
  id_producto INT NOT NULL,
  id_talla INT NOT NULL,
  id_color INT NOT NULL,
  precio_venta DECIMAL(10,2) NOT NULL,
  costo DECIMAL(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0,
  CONSTRAINT ck_stock_no_negativo CHECK (stock >= 0),
  UNIQUE (id_producto, id_talla, id_color),
  FOREIGN KEY (id_producto) REFERENCES producto(id_producto),
  FOREIGN KEY (id_talla) REFERENCES talla(id_talla),
  FOREIGN KEY (id_color) REFERENCES color(id_color)
);

CREATE TABLE importacion (
  id_importacion INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  archivo VARCHAR(150) NOT NULL,
  filas_cargadas INT NOT NULL DEFAULT 0,
  filas_rechazadas INT NOT NULL DEFAULT 0,
  id_usuario INT NOT NULL,
  FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
);

CREATE TABLE venta (
  id_venta INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  total DECIMAL(10,2) NOT NULL DEFAULT 0,
  estado VARCHAR(10) NOT NULL DEFAULT 'Activa',
  origen VARCHAR(10) NOT NULL DEFAULT 'Sistema',
  id_usuario INT NOT NULL,
  id_importacion INT NULL,
  FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario),
  FOREIGN KEY (id_importacion) REFERENCES importacion(id_importacion)
);

CREATE TABLE detalle_venta (
  id_venta INT NOT NULL,
  id_variante INT NOT NULL,
  cantidad INT NOT NULL,
  precio_unitario DECIMAL(10,2) NOT NULL,
  CONSTRAINT ck_dv_cantidad CHECK (cantidad > 0),
  PRIMARY KEY (id_venta, id_variante),
  FOREIGN KEY (id_venta) REFERENCES venta(id_venta),
  FOREIGN KEY (id_variante) REFERENCES variante(id_variante)
);

CREATE TABLE compra (
  id_compra INT AUTO_INCREMENT PRIMARY KEY,
  fecha DATE NOT NULL,
  total DECIMAL(10,2) NOT NULL,
  id_proveedor INT NOT NULL,
  id_usuario INT NOT NULL,
  FOREIGN KEY (id_proveedor) REFERENCES proveedor(id_proveedor),
  FOREIGN KEY (id_usuario) REFERENCES usuario(id_usuario)
);

CREATE TABLE detalle_compra (
  id_compra INT NOT NULL,
  id_variante INT NOT NULL,
  cantidad INT NOT NULL,
  costo_unitario DECIMAL(10,2) NOT NULL,
  CONSTRAINT ck_dc_cantidad CHECK (cantidad > 0),
  PRIMARY KEY (id_compra, id_variante),
  FOREIGN KEY (id_compra) REFERENCES compra(id_compra),
  FOREIGN KEY (id_variante) REFERENCES variante(id_variante)
);

CREATE TABLE prediccion (
  id_prediccion INT AUTO_INCREMENT PRIMARY KEY,
  id_variante INT NOT NULL,
  periodo_inicio DATE NOT NULL,
  periodo_fin DATE NOT NULL,
  cantidad_estimada INT NOT NULL,
  algoritmo VARCHAR(40) NOT NULL,
  mae DECIMAL(8,2),
  fecha_generacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (id_variante) REFERENCES variante(id_variante)
);

CREATE INDEX idx_venta_fecha ON venta(fecha);
CREATE INDEX idx_prediccion_periodo ON prediccion(periodo_inicio, periodo_fin);
"""

VISTAS = """
-- Vista: variantes con riesgo de desabasto en el periodo pronosticado más reciente (HU07)
CREATE VIEW v_alerta_desabasto AS
SELECT v.id_variante, p.modelo, t.nombre AS talla, c.nombre AS color,
       v.stock, pr.cantidad_estimada,
       pr.cantidad_estimada - v.stock AS sugerido_comprar
FROM variante v
JOIN producto p    ON p.id_producto = v.id_producto
JOIN talla t       ON t.id_talla = v.id_talla
JOIN color c       ON c.id_color = v.id_color
JOIN prediccion pr ON pr.id_variante = v.id_variante
WHERE pr.periodo_inicio = (SELECT MAX(periodo_inicio) FROM prediccion)
  AND v.stock < pr.cantidad_estimada;

-- Vista: variantes con existencias sin ventas en los últimos 60 días (HU08)
CREATE VIEW v_baja_rotacion AS
SELECT v.id_variante, p.modelo, t.nombre AS talla, c.nombre AS color,
       v.stock, MAX(ve.fecha) AS ultima_venta
FROM variante v
JOIN producto p ON p.id_producto = v.id_producto
JOIN talla t    ON t.id_talla = v.id_talla
JOIN color c    ON c.id_color = v.id_color
LEFT JOIN detalle_venta dv ON dv.id_variante = v.id_variante
LEFT JOIN venta ve ON ve.id_venta = dv.id_venta AND ve.estado = 'Activa'
WHERE v.stock > 0
GROUP BY v.id_variante, p.modelo, t.nombre, c.nombre, v.stock
HAVING ultima_venta IS NULL OR ultima_venta < NOW() - INTERVAL 60 DAY;

-- Consultas de ejemplo para revisar la base de datos:
-- SELECT * FROM v_alerta_desabasto;
-- SELECT * FROM v_baja_rotacion;
-- SELECT origen, COUNT(*) AS ventas, SUM(total) AS importe FROM venta GROUP BY origen;
"""

# Orden de carga: primero las tablas de las que dependen las demás
TABLAS = ["rol", "usuario", "categoria", "proveedor", "producto", "talla", "color",
          "variante", "importacion", "venta", "detalle_venta", "compra",
          "detalle_compra", "prediccion"]


def valor_sql(v) -> str:
    """Convierte un valor de Python a su representación en SQL."""
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return str(v)
    texto = str(v).replace("\\", "\\\\").replace("'", "''")
    return f"'{texto}'"


def main():
    if not os.path.exists(ORIGEN):
        sys.exit("No existe instance/gipsy.db. Ejecuta primero: python seed.py")
    conexion = sqlite3.connect(ORIGEN)
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    with open(DESTINO, "w", encoding="utf-8") as sql:
        sql.write(ESTRUCTURA)
        sql.write("\n-- ------------------------- DATOS -------------------------\n")
        sql.write("SET FOREIGN_KEY_CHECKS = 0;\n")
        for tabla in TABLAS:
            cursor = conexion.execute(f"SELECT * FROM {tabla}")
            columnas = ", ".join(d[0] for d in cursor.description)
            filas = cursor.fetchall()
            if not filas:
                continue
            sql.write(f"\n-- {tabla}: {len(filas)} registros\n")
            for i in range(0, len(filas), 500):
                bloque = filas[i:i + 500]
                valores = ",\n".join("(" + ", ".join(valor_sql(v) for v in f) + ")" for f in bloque)
                sql.write(f"INSERT INTO {tabla} ({columnas}) VALUES\n{valores};\n")
        sql.write("SET FOREIGN_KEY_CHECKS = 1;\n")
        sql.write(VISTAS)
    print(f"Archivo generado: {DESTINO}")


if __name__ == "__main__":
    main()
