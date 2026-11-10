# Plataforma de Análisis Predictivo – Gipsy

Sistema web para apoyar las decisiones de compra e inventario de la tienda de ropa **Gipsy** (Oaxaca), con base en el historial de ventas.

Proyecto integrador de **Gestión de Proyectos de Software** – Instituto Tecnológico de Oaxaca, Equipo 4.
Metodología de gestión: PRINCE2 · Modelo de desarrollo: Scrum.

## Módulos

| Módulo | Rol | Qué hace |
| --- | --- | --- |
| Inicio de sesión | Todos | Acceso con usuario y contraseña cifrada; cada rol ve solo su menú |
| Panel | Todos | Ventas del día, alertas de desabasto y prendas de baja rotación |
| Inventario | Todos (alta: administrador) | Existencias por producto, talla y color, con filtros |
| Ventas | Vendedor, gerente | Registra ventas y descuenta el stock; el gerente puede cancelar |
| Importar historial | Administrador | Carga ventas pasadas desde Excel o CSV, con limpieza y validación |
| Predicciones | Gerente | Entrena el modelo, muestra la venta estimada y cuánto comprar |
| Usuarios | Administrador | Alta, roles y baja lógica de usuarios |

El modelo predictivo (`app/modulo_predictivo.py`) compara **regresión lineal** y **Random Forest**, elige el de menor error (MAE) y pronostica las piezas que se venderán de cada variante el mes siguiente.

## Instalación

Requisitos: Python 3.10 o superior.

```bash
git clone https://github.com/AlejandroGuillermo7/plataforma-predictiva-gipsy.git
cd plataforma-predictiva-gipsy
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python seed.py      # crea la base de datos con datos de ejemplo
python run.py       # abre http://127.0.0.1:5000
```

### Usuarios de prueba

| Usuario | Contraseña | Rol |
| --- | --- | --- |
| admin | admin123 | Administrador |
| gerente | gerente123 | Gerente |
| vendedor | vendedor123 | Vendedor |

> **Los datos que crea `seed.py` son de ejemplo**, no ventas reales de Gipsy. Para usar el historial real: `python seed.py --vacio` y después cargar el archivo en **Importar historial**. En `ejemplos/historial_ejemplo.csv` hay un archivo con el formato esperado (incluye filas con errores a propósito, para ver cómo se rechazan).

## Base de datos

Por defecto se usa **SQLite** (archivo `instance/gipsy.db`), que no requiere instalar nada. Para usar **PostgreSQL**:

```bash
pip install psycopg2-binary
# crear la base de datos gipsy_db en PostgreSQL y luego:
set DATABASE_URL=postgresql+psycopg2://usuario:contrasena@localhost/gipsy_db   # Windows
export DATABASE_URL=postgresql+psycopg2://usuario:contrasena@localhost/gipsy_db  # Mac/Linux
python seed.py
python run.py
```

### Ver la base de datos en MySQL

`sql/gipsy_db_mysql.sql` contiene la estructura completa (14 tablas, llaves, restricciones y vistas) con los datos de ejemplo. En MySQL Workbench: **File → Open SQL Script → ejecutar**. Para regenerarlo con los datos actuales del sistema: `python exportar_mysql.py`.

## Pruebas

```bash
pytest
```

Incluye pruebas unitarias del modelo predictivo y pruebas de integración (inicio de sesión, permisos por rol, ventas, cancelaciones e importación).

## Estructura

```
app/
  __init__.py           configuración de Flask y base de datos
  models.py             tablas del modelo relacional
  auth.py               inicio de sesión y control por rol
  views.py              pantallas del sistema
  importador.py         importación y limpieza del historial
  modulo_predictivo.py  entrenamiento y pronóstico
  templates/            pantallas HTML
  static/estilos.css
seed.py                 datos de ejemplo
run.py                  arranque
tests/                  pruebas con pytest
ejemplos/               archivo de ejemplo para importar
```

## Equipo 4

- Francisco Javier González Santiago (Product Owner, representante)
- Alejandro Guillermo Enríquez Rodríguez (Scrum Master)
- Luis Andrik Hernández Velasco
- Erick Yahir Gaytán Rodríguez
- Haniel Eliud Pérez Cruz
