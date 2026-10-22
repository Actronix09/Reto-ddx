"""
Mapa de calor de goles de un partido del Mundial Qatar 2022 (RETO d/dx · MINUTO 90).

Lee los tiros de la tabla `eventos_tiros` de la base SQLite y dibuja un mapa
de calor sobre la cancha con matplotlib.

Las coordenadas vienen de StatsBomb: cancha de 120 x 80, todos los eventos
orientados hacia el ataque del equipo que los hace (x = 120 es la portería
rival, y = 0 la banda izquierda vista desde su propia portería).

Uso:
    python heatmap_goles.py --listar                     # ids de los 64 partidos
    python heatmap_goles.py --partido 3869685            # la final
    python heatmap_goles.py --partido 3869685 --por-equipo --modo zonas
    python heatmap_goles.py --partido 3869685 --tiros    # todos los tiros, no solo goles
    python heatmap_goles.py                              # todos los goles del torneo

Datos: StatsBomb Open Data.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Arc, Circle, Rectangle

RUTA_DB = Path(__file__).parent / "RETO_ddx_MINUTO_90_completo" / "sql" / "minuto_90.sqlite"

# Cancha StatsBomb (unidades = yardas)
LARGO, ANCHO = 120.0, 80.0

# Rampa secuencial de un solo tono (azul claro -> oscuro).
RAMPA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SUPERFICIE = "#fafaf9"
LINEAS = "#b5b3ad"
TEXTO = "#2b2a27"
TEXTO_SECUNDARIO = "#6b6963"

# Más goles que esto y ya no se escribe el minuto junto a cada uno
MAX_ETIQUETAS = 15


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def cargar_partido(conn: sqlite3.Connection, partido: int) -> pd.Series:
    df = pd.read_sql_query("SELECT * FROM partidos WHERE match_id = ?", conn, params=(partido,))
    if df.empty:
        raise SystemExit(f"No existe el partido {partido}. Usa --listar para ver los ids.")
    return df.iloc[0]


def cargar_tiros(conn: sqlite3.Connection, partido: int | None, solo_goles: bool) -> pd.DataFrame:
    """Tiros (o solo goles) de un partido, o de todo el torneo si `partido` es None."""
    consulta = "SELECT match_id, minuto, equipo, rival, jugador, x, y, xg, gol, tipo_tiro FROM eventos_tiros WHERE 1=1"
    params: list = []
    if partido is not None:
        consulta += " AND match_id = ?"
        params.append(partido)
    if solo_goles:
        consulta += " AND gol = 1"

    df = pd.read_sql_query(consulta, conn, params=params).dropna(subset=["x", "y"])
    # StatsBomb tiene el eje Y hacia abajo; lo invertimos para que la banda
    # izquierda del atacante quede arriba al dibujar hacia la derecha.
    df["y"] = ANCHO - df["y"]
    return df


def listar_partidos(conn: sqlite3.Connection) -> None:
    df = pd.read_sql_query(
        """SELECT match_id, substr(game_date, 1, 10) AS fecha, competition_stage AS fase,
                  home_team || ' ' || home_score || '-' || away_score || ' ' || away_team AS partido
           FROM partidos ORDER BY game_date""",
        conn,
    )
    print(df.to_string(index=False))


# ---------------------------------------------------------------------------
# Densidad
# ---------------------------------------------------------------------------

def densidad_kde(x: np.ndarray, y: np.ndarray, resolucion: float = 0.5, sigma: float = 6.0):
    """Densidad suavizada con kernel gaussiano (sin depender de scipy).

    sigma está en yardas: más grande = manchas más anchas. Con pocos goles
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
    """Conteo por zona rectangular de la cancha (por defecto, cuadros de 10 x 10)."""
    conteo, bordes_x, bordes_y = np.histogram2d(x, y, bins=bins, range=[[0, LARGO], [0, ANCHO]])
    return bordes_x, bordes_y, conteo.T


# ---------------------------------------------------------------------------
# Dibujo
# ---------------------------------------------------------------------------

def dibujar_cancha(ax: plt.Axes) -> None:
    """Dibuja las líneas de una cancha StatsBomb de 120 x 80."""
    estilo = dict(color=LINEAS, linewidth=1.2, fill=False, zorder=3)
    medio = ANCHO / 2
    ax.add_patch(Rectangle((0, 0), LARGO, ANCHO, **estilo))
    ax.plot([LARGO / 2] * 2, [0, ANCHO], color=LINEAS, linewidth=1.2, zorder=3)
    ax.add_patch(Circle((LARGO / 2, medio), 10, **estilo))
    ax.add_patch(Circle((LARGO / 2, medio), 0.4, color=LINEAS, zorder=3))

    for lado in (0, LARGO):
        sentido = 1 if lado == 0 else -1
        # Área grande, área chica y portería
        ax.add_patch(Rectangle((lado, medio - 22), sentido * 18, 44, **estilo))
        ax.add_patch(Rectangle((lado, medio - 10), sentido * 6, 20, **estilo))
        ax.add_patch(Rectangle((lado, medio - 4), -sentido * 1.5, 8, **estilo))
        # Punto penal y media luna
        penal = lado + sentido * 12
        ax.add_patch(Circle((penal, medio), 0.4, color=LINEAS, zorder=3))
        angulo = 0 if lado == 0 else 180
        ax.add_patch(Arc((penal, medio), 20, 20, angle=angulo,
                         theta1=-53, theta2=53, color=LINEAS, linewidth=1.2, zorder=3))

    ax.set_xlim(-3, LARGO + 3)
    ax.set_ylim(-3, ANCHO + 3)
    ax.set_aspect("equal")
    ax.axis("off")


def mapa_de_calor(df: pd.DataFrame, titulo: str, modo: str = "kde", ax: plt.Axes | None = None):
    """Dibuja el mapa de calor de los tiros de `df` sobre una cancha.

    La densidad se calcula con todas las filas de `df`; los goles (gol = 1)
    se marcan encima en negro y el resto de los tiros como círculos huecos.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 7.5))
    fig = ax.figure
    fig.set_facecolor(SUPERFICIE)
    ax.set_facecolor(SUPERFICIE)

    cmap = LinearSegmentedColormap.from_list("goles", RAMPA)
    cmap.set_under(alpha=0)  # las zonas vacías dejan ver la cancha

    x, y = df["x"].to_numpy(), df["y"].to_numpy()
    solo_goles = bool(df["gol"].all())
    unidad = "goles" if solo_goles else "tiros"

    if len(df) == 0:
        ax.text(LARGO / 2, ANCHO / 2, "Sin goles registrados", ha="center", va="center",
                color=TEXTO_SECUNDARIO, fontsize=14, zorder=5)
    elif modo == "zonas":
        bx, by, conteo = densidad_zonas(x, y)
        malla = ax.pcolormesh(bx, by, conteo, cmap=cmap, vmin=0.5, vmax=max(conteo.max(), 1),
                              edgecolors=SUPERFICIE, linewidth=2, zorder=1)
        # Número solo en las zonas con algo
        for i in range(conteo.shape[0]):
            for j in range(conteo.shape[1]):
                if conteo[i, j] > 0:
                    oscuro = conteo[i, j] > conteo.max() / 2
                    ax.text((bx[j] + bx[j + 1]) / 2, (by[i] + by[i + 1]) / 2, int(conteo[i, j]),
                            ha="center", va="center", fontsize=11, zorder=5,
                            color="white" if oscuro else TEXTO)
        barra = fig.colorbar(malla, ax=ax, shrink=0.6, pad=0.02)
        barra.set_label(f"{unidad.capitalize()} por zona", color=TEXTO_SECUNDARIO)
        maximo = int(max(conteo.max(), 1))
        barra.set_ticks(np.unique(np.linspace(1, maximo, min(maximo, 6)).round().astype(int)))
    else:
        gx, gy, z = densidad_kde(x, y)
        z = z / z.max()
        # rasterized evita las líneas de costura entre celdas al guardar en PDF/SVG
        malla = ax.pcolormesh(gx, gy, z, cmap=cmap, vmin=0.05, vmax=1, shading="auto", zorder=1,
                              rasterized=True)
        barra = fig.colorbar(malla, ax=ax, shrink=0.6, pad=0.02)
        barra.set_label(f"Concentración relativa de {unidad}", color=TEXTO_SECUNDARIO)
        barra.set_ticks([0.05, 1])
        barra.set_ticklabels(["Baja", "Alta"])

    dibujar_cancha(ax)

    # Ubicación exacta de cada tiro encima del mapa (en zonas ya se ve el conteo)
    if len(df) and modo == "kde":
        fallados = df[df["gol"] == 0]
        # Relleno claro para que se vean también sobre el azul oscuro
        ax.scatter(fallados["x"], fallados["y"], s=36, facecolors=SUPERFICIE, edgecolors=TEXTO_SECUNDARIO,
                   linewidths=1, zorder=5, label="Tiro")
        goles = df[df["gol"] == 1]
        ax.scatter(goles["x"], goles["y"], s=70, color=TEXTO, edgecolors=SUPERFICIE,
                   linewidths=2, zorder=6, label="Gol")
        if len(goles) <= MAX_ETIQUETAS:
            # Goles desde el mismo punto (p. ej. penales) comparten una sola etiqueta
            for (x0, y0), grupo in goles.groupby([goles["x"].round(), goles["y"].round()]):
                minutos = ", ".join(f"{m}'" for m in sorted(grupo["minuto"].astype(int)))
                ax.annotate(minutos, (x0, y0), xytext=(6, 6),
                            textcoords="offset points", fontsize=9, color=TEXTO, zorder=7)
        if not solo_goles:
            ax.legend(loc="upper left", bbox_to_anchor=(0, 0), ncol=2, frameon=False,
                      labelcolor=TEXTO_SECUNDARIO)

    ax.set_title(titulo, color=TEXTO, fontsize=15, loc="left", pad=12)
    return fig, ax


def reflejar(df: pd.DataFrame) -> pd.DataFrame:
    """Gira 180° las coordenadas para que el equipo ataque hacia la izquierda."""
    df = df.copy()
    df["x"] = LARGO - df["x"]
    df["y"] = ANCHO - df["y"]
    return df


def titulo_partido(info: pd.Series, unidad: str, n: int) -> str:
    return (f"{info['home_team']} {info['home_score']}-{info['away_score']} {info['away_team']}"
            f" · {info['competition_stage']} · {n} {unidad}")


def graficar_partido(df: pd.DataFrame, info: pd.Series, modo: str, por_equipo: bool):
    """Un panel por equipo (ambos atacando a la derecha) o los dos en la misma cancha."""
    unidad = "goles" if df["gol"].all() else "tiros"
    local, visitante = info["home_team"], info["away_team"]

    if por_equipo:
        fig, ejes = plt.subplots(2, 1, figsize=(11, 14))
        for ax, equipo in zip(ejes, (local, visitante)):
            datos = df[df["equipo"] == equipo]
            mapa_de_calor(datos, f"{equipo} · {len(datos)} {unidad} · ataca →", modo, ax)
        fig.suptitle(titulo_partido(info, unidad, len(df)), color=TEXTO, fontsize=17, x=0.02, ha="left")
        return fig

    # Misma cancha: el local ataca a la derecha y el visitante a la izquierda
    datos = pd.concat([df[df["equipo"] == local], reflejar(df[df["equipo"] == visitante])])
    fig, ax = mapa_de_calor(datos, titulo_partido(info, unidad, len(df)), modo)
    ax.text(LARGO, -2, f"{local} ataca →", ha="right", va="top", color=TEXTO_SECUNDARIO, fontsize=10)
    ax.text(0, -2, f"← {visitante} ataca", ha="left", va="top", color=TEXTO_SECUNDARIO, fontsize=10)
    return fig


def avisar_autogoles(df: pd.DataFrame, info: pd.Series) -> None:
    """Los autogoles no son tiros, así que no aparecen en eventos_tiros."""
    marcador = int(info["home_score"]) + int(info["away_score"])
    if int(df["gol"].sum()) < marcador:
        print(f"Aviso: el marcador suma {marcador} goles pero hay {int(df['gol'].sum())} en "
              "eventos_tiros; la diferencia son autogoles, que no tienen tiro.")


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mapa de calor de goles (Mundial Qatar 2022)")
    parser.add_argument("--db", default=RUTA_DB, type=Path, help="Ruta a minuto_90.sqlite")
    parser.add_argument("--partido", type=int, help="match_id; si se omite, todo el torneo")
    parser.add_argument("--listar", action="store_true", help="Muestra los partidos y sus ids")
    parser.add_argument("--modo", choices=["kde", "zonas"], default="kde",
                        help="kde = mancha suavizada, zonas = conteo por cuadrícula")
    parser.add_argument("--por-equipo", action="store_true", help="Un mapa por cada equipo")
    parser.add_argument("--tiros", action="store_true", help="Incluir todos los tiros, no solo goles")
    parser.add_argument("--salida", help="Archivo de imagen (png/svg/pdf). Si se omite, abre una ventana")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"No encuentro la base en {args.db}")

    with sqlite3.connect(args.db) as conn:
        if args.listar:
            listar_partidos(conn)
            return

        df = cargar_tiros(conn, args.partido, solo_goles=not args.tiros)
        if args.partido is None:
            unidad = "tiros" if args.tiros else "goles"
            fig, _ = mapa_de_calor(df, f"Mundial Qatar 2022 · {len(df)} {unidad}", args.modo)
        else:
            info = cargar_partido(conn, args.partido)
            avisar_autogoles(df, info)
            fig = graficar_partido(df, info, args.modo, args.por_equipo)

    fig.text(0.99, 0.01, "Datos: StatsBomb Open Data", ha="right", va="bottom",
             color=TEXTO_SECUNDARIO, fontsize=8)
    # Reservar espacio arriba para el título general de la vista por equipo
    fig.tight_layout(rect=(0, 0, 1, 0.97 if fig.get_suptitle() else 1))
    if args.salida:
        fig.savefig(args.salida, dpi=150, facecolor=SUPERFICIE)
        print(f"Mapa guardado en {args.salida}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
