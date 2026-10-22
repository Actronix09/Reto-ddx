"""
Mapa de calor de goles de un partido.

Lee las coordenadas de los goles (o tiros) desde una base de datos y dibuja
un mapa de calor sobre una cancha de fútbol con matplotlib.

Como todavía no tenemos el esquema real de la base de datos, todo lo que
depende de él está concentrado en la sección CONFIGURACIÓN: la consulta SQL,
el nombre de las columnas y el sistema de coordenadas. Cuando llegue la base,
solo hay que ajustar esa sección.

Uso:
    # Probar con datos inventados (crea demo.db)
    python heatmap_goles.py --demo

    # Con la base real
    python heatmap_goles.py --db "sqlite:///partidos.db" --partido 123
    python heatmap_goles.py --db "postgresql://user:pass@host/db" --partido 123 --modo zonas
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Arc, Circle, Rectangle

# ---------------------------------------------------------------------------
# CONFIGURACIÓN (ajustar cuando tengamos la base de datos real)
# ---------------------------------------------------------------------------

# Consulta que devuelve un renglón por gol. ":partido" se sustituye por el id.
CONSULTA = """
    SELECT x, y, equipo, minuto, jugador
    FROM eventos
    WHERE partido_id = :partido
      AND tipo = 'gol'
"""

# Nombre de las columnas en el resultado de la consulta -> nombre interno.
COLUMNAS = {
    "x": "x",
    "y": "y",
    "equipo": "equipo",
    "minuto": "minuto",
    "jugador": "jugador",
}

# Tamaño del sistema de coordenadas que usa la base de datos:
#   Opta / porcentaje -> (100, 100)
#   StatsBomb         -> (120, 80)
#   Metros            -> (105, 68)
ESCALA_ORIGEN = (100, 100)

# Si en la base el eje Y crece hacia abajo (común en proveedores de datos),
# lo invertimos para dibujar con el origen abajo a la izquierda.
INVERTIR_Y = False

# Dimensiones de la cancha con la que dibujamos (metros, FIFA estándar).
LARGO, ANCHO = 105.0, 68.0

# Rampa secuencial de un solo tono (azul claro -> oscuro).
RAMPA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SUPERFICIE = "#fafaf9"
LINEAS = "#b5b3ad"
TEXTO = "#2b2a27"
TEXTO_SECUNDARIO = "#6b6963"


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def cargar_goles(url_db: str, partido: int | str) -> pd.DataFrame:
    """Ejecuta CONSULTA y regresa un DataFrame con columnas internas y coordenadas en metros."""
    if url_db.startswith("sqlite:///"):
        # SQLite no necesita SQLAlchemy.
        with sqlite3.connect(url_db.removeprefix("sqlite:///")) as conn:
            df = pd.read_sql_query(CONSULTA, conn, params={"partido": partido})
    else:
        from sqlalchemy import create_engine, text

        engine = create_engine(url_db)
        with engine.connect() as conn:
            df = pd.read_sql_query(text(CONSULTA), conn, params={"partido": partido})

    df = df.rename(columns={origen: interno for interno, origen in COLUMNAS.items()})
    faltantes = {"x", "y"} - set(df.columns)
    if faltantes:
        raise ValueError(f"La consulta no regresó las columnas {faltantes}; revisa COLUMNAS.")

    return a_metros(df)


def a_metros(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las coordenadas del proveedor a metros sobre una cancha de LARGO x ANCHO."""
    df = df.dropna(subset=["x", "y"]).copy()
    largo_origen, ancho_origen = ESCALA_ORIGEN
    df["x"] = df["x"].astype(float) / largo_origen * LARGO
    df["y"] = df["y"].astype(float) / ancho_origen * ANCHO
    if INVERTIR_Y:
        df["y"] = ANCHO - df["y"]
    return df


# ---------------------------------------------------------------------------
# Densidad
# ---------------------------------------------------------------------------

def densidad_kde(x: np.ndarray, y: np.ndarray, resolucion: float = 0.5, sigma: float = 6.0):
    """Densidad suavizada con kernel gaussiano (sin depender de scipy).

    sigma está en metros: más grande = manchas más anchas. Con pocos goles
    (lo normal en un partido) conviene un sigma generoso.
    """
    gx = np.arange(0, LARGO + resolucion, resolucion)
    gy = np.arange(0, ANCHO + resolucion, resolucion)
    malla_x, malla_y = np.meshgrid(gx, gy)
    z = np.zeros_like(malla_x)
    for xi, yi in zip(x, y):
        z += np.exp(-((malla_x - xi) ** 2 + (malla_y - yi) ** 2) / (2 * sigma**2))
    return gx, gy, z


def densidad_zonas(x: np.ndarray, y: np.ndarray, bins=(12, 8)):
    """Conteo de goles por zona rectangular de la cancha."""
    conteo, bordes_x, bordes_y = np.histogram2d(x, y, bins=bins, range=[[0, LARGO], [0, ANCHO]])
    return bordes_x, bordes_y, conteo.T


# ---------------------------------------------------------------------------
# Dibujo
# ---------------------------------------------------------------------------

def dibujar_cancha(ax: plt.Axes) -> None:
    """Dibuja las líneas de una cancha de LARGO x ANCHO metros."""
    estilo = dict(color=LINEAS, linewidth=1.2, fill=False, zorder=3)
    ax.add_patch(Rectangle((0, 0), LARGO, ANCHO, **estilo))
    ax.plot([LARGO / 2] * 2, [0, ANCHO], color=LINEAS, linewidth=1.2, zorder=3)
    ax.add_patch(Circle((LARGO / 2, ANCHO / 2), 9.15, **estilo))
    ax.add_patch(Circle((LARGO / 2, ANCHO / 2), 0.4, color=LINEAS, zorder=3))

    for lado in (0, LARGO):
        sentido = 1 if lado == 0 else -1
        # Área grande, área chica y portería
        ax.add_patch(Rectangle((lado, ANCHO / 2 - 20.16), sentido * 16.5, 40.32, **estilo))
        ax.add_patch(Rectangle((lado, ANCHO / 2 - 9.16), sentido * 5.5, 18.32, **estilo))
        ax.add_patch(Rectangle((lado, ANCHO / 2 - 3.66), -sentido * 1.5, 7.32, **estilo))
        # Punto penal y media luna
        penal = lado + sentido * 11
        ax.add_patch(Circle((penal, ANCHO / 2), 0.4, color=LINEAS, zorder=3))
        angulo = 0 if lado == 0 else 180
        ax.add_patch(Arc((penal, ANCHO / 2), 18.3, 18.3, angle=angulo,
                         theta1=-53, theta2=53, color=LINEAS, linewidth=1.2, zorder=3))

    ax.set_xlim(-3, LARGO + 3)
    ax.set_ylim(-3, ANCHO + 3)
    ax.set_aspect("equal")
    ax.axis("off")


def mapa_de_calor(df: pd.DataFrame, titulo: str, modo: str = "kde", ax: plt.Axes | None = None):
    """Dibuja el mapa de calor de los goles de `df` sobre una cancha."""
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 7.5))
    fig = ax.figure
    fig.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)

    cmap = LinearSegmentedColormap.from_list("goles", RAMPA)
    cmap.set_under(alpha=0)  # las zonas sin goles dejan ver la cancha

    x, y = df["x"].to_numpy(), df["y"].to_numpy()

    if len(df) == 0:
        ax.text(LARGO / 2, ANCHO / 2, "Sin goles registrados", ha="center", va="center",
                color=TEXTO_SECUNDARIO, fontsize=14, zorder=5)
    elif modo == "zonas":
        bx, by, conteo = densidad_zonas(x, y)
        malla = ax.pcolormesh(bx, by, conteo, cmap=cmap, vmin=0.5, vmax=max(conteo.max(), 1),
                              edgecolors=SUPERFICIE, linewidth=2, zorder=1)
        # Número solo en las zonas con goles
        for i in range(conteo.shape[0]):
            for j in range(conteo.shape[1]):
                if conteo[i, j] > 0:
                    oscuro = conteo[i, j] > conteo.max() / 2
                    ax.text((bx[j] + bx[j + 1]) / 2, (by[i] + by[i + 1]) / 2, int(conteo[i, j]),
                            ha="center", va="center", fontsize=11, zorder=5,
                            color="white" if oscuro else TEXTO)
        barra = fig.colorbar(malla, ax=ax, shrink=0.6, pad=0.02)
        barra.set_label("Goles por zona", color=TEXTO_SECUNDARIO)
        barra.set_ticks(range(1, int(max(conteo.max(), 1)) + 1))
    else:
        gx, gy, z = densidad_kde(x, y)
        z = z / z.max()
        malla = ax.pcolormesh(gx, gy, z, cmap=cmap, vmin=0.05, vmax=1, shading="auto", zorder=1)
        barra = fig.colorbar(malla, ax=ax, shrink=0.6, pad=0.02)
        barra.set_label("Concentración relativa de goles", color=TEXTO_SECUNDARIO)
        barra.set_ticks([0.05, 1])
        barra.set_ticklabels(["Baja", "Alta"])

    dibujar_cancha(ax)

    # Ubicación exacta de cada gol encima del mapa (en zonas ya se ve el conteo)
    if len(df) and modo == "kde":
        ax.scatter(x, y, s=70, color=TEXTO, edgecolors=SUPERFICIE, linewidths=2, zorder=6)
        if "minuto" in df.columns:
            for _, gol in df.iterrows():
                ax.annotate(f"{int(gol['minuto'])}'", (gol["x"], gol["y"]), xytext=(6, 6),
                            textcoords="offset points", fontsize=9, color=TEXTO, zorder=7)

    ax.set_title(titulo, color=TEXTO, fontsize=15, loc="left", pad=12)
    return fig, ax


def graficar_partido(df: pd.DataFrame, partido, modo: str, por_equipo: bool, salida: str | None):
    """Una figura con todos los goles, o un panel por equipo si `por_equipo`."""
    if por_equipo and "equipo" in df.columns and df["equipo"].nunique() > 1:
        equipos = sorted(df["equipo"].dropna().unique())
        fig, ejes = plt.subplots(len(equipos), 1, figsize=(11, 7 * len(equipos)))
        for ax, equipo in zip(ejes, equipos):
            goles = df[df["equipo"] == equipo]
            mapa_de_calor(goles, f"{equipo} · {len(goles)} goles", modo, ax)
    else:
        fig, _ = mapa_de_calor(df, f"Partido {partido} · {len(df)} goles", modo)

    fig.tight_layout()
    if salida:
        fig.savefig(salida, dpi=150, facecolor=SUPERFICIE)
        print(f"Mapa guardado en {salida}")
    else:
        plt.show()


# ---------------------------------------------------------------------------
# Datos de prueba
# ---------------------------------------------------------------------------

def crear_db_demo(ruta: str = "demo.db") -> str:
    """Crea una base SQLite con goles inventados para probar el script."""
    rng = np.random.default_rng(7)
    filas = []
    for equipo, n in (("Local", 4), ("Visitante", 3)):
        # Coordenadas en escala 0-100, atacando hacia la derecha, cerca del área
        xs = rng.normal(88, 5, n).clip(70, 99)
        ys = rng.normal(50, 12, n).clip(20, 80)
        minutos = sorted(rng.integers(1, 91, n))
        filas += [(1, "gol", float(x), float(y), equipo, int(m), f"Jugador {i + 1}")
                  for i, (x, y, m) in enumerate(zip(xs, ys, minutos))]

    with sqlite3.connect(ruta) as conn:
        conn.execute("DROP TABLE IF EXISTS eventos")
        conn.execute("""CREATE TABLE eventos (
            partido_id INTEGER, tipo TEXT, x REAL, y REAL,
            equipo TEXT, minuto INTEGER, jugador TEXT)""")
        conn.executemany("INSERT INTO eventos VALUES (?, ?, ?, ?, ?, ?, ?)", filas)
    return f"sqlite:///{ruta}"


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mapa de calor de goles de un partido")
    parser.add_argument("--db", help="URL de la base, p. ej. sqlite:///partidos.db o postgresql://...")
    parser.add_argument("--partido", default=1, help="Id del partido")
    parser.add_argument("--modo", choices=["kde", "zonas"], default="kde",
                        help="kde = mancha suavizada, zonas = conteo por cuadrícula")
    parser.add_argument("--por-equipo", action="store_true", help="Un mapa por cada equipo")
    parser.add_argument("--salida", help="Archivo de imagen (png/svg/pdf). Si se omite, abre una ventana")
    parser.add_argument("--demo", action="store_true", help="Usar una base de prueba con datos inventados")
    args = parser.parse_args()

    if args.demo:
        args.db = crear_db_demo()
    if not args.db:
        parser.error("indica --db o usa --demo")

    df = cargar_goles(args.db, args.partido)
    graficar_partido(df, args.partido, args.modo, args.por_equipo, args.salida)


if __name__ == "__main__":
    main()
