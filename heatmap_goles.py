"""
Mapa de calor de goles del Mundial Qatar 2022 (RETO d/dx · MINUTO 90).

Lee los tiros de la tabla `eventos_tiros` de la base SQLite y dibuja un mapa
de calor sobre una cancha negra con matplotlib. Los dos equipos comparten la
cancha: uno ataca hacia la derecha y el otro hacia la izquierda, cada uno con
los colores de su selección.

Las coordenadas vienen de StatsBomb: cancha de 120 x 80, todos los eventos
orientados hacia el ataque del equipo que los hace (x = 120 es la portería
rival, y = 0 la banda izquierda vista desde su propia portería).

Uso:
    python heatmap_goles.py --listar                     # ids de los 64 partidos
    python heatmap_goles.py --partido 3869685            # la final
    python heatmap_goles.py --seleccion Argentina        # todo el torneo de una selección
    python heatmap_goles.py --partido 3869685 --por-equipo --modo zonas
    python heatmap_goles.py --partido 3869685 --tiros    # todos los tiros, no solo goles
    python heatmap_goles.py                              # todos los goles del torneo

Interfaz con selectores de selección y partido: streamlit run app.py

Datos: StatsBomb Open Data.
"""

from __future__ import annotations

import argparse
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import patheffects
from matplotlib.colors import LinearSegmentedColormap, to_rgb
from matplotlib.patches import Arc, Circle, Rectangle

RUTA_DB = Path(__file__).parent / "RETO_ddx_MINUTO_90_completo" / "sql" / "minuto_90.sqlite"

# Cancha StatsBomb (unidades = yardas)
LARGO, ANCHO = 120.0, 80.0

FONDO = "#121212"        # alrededor de la cancha
CANCHA = "#000000"
LINEAS = "#ffffff"
TEXTO = "#f2f2f2"
TEXTO_SECUNDARIO = "#9a9a9a"
NEUTRO = "#f5a623"       # torneo completo, sin selección elegida

# Color principal y alterno de cada selección, aclarados para que se vean sobre
# negro. Se evita el blanco porque se confunde con las líneas de la cancha.
COLORES_EQUIPO = {
    "Argentina": ("#75aadb", "#f6b40e"),
    "Australia": ("#ffcd00", "#00a651"),
    "Belgium": ("#e30613", "#fdda24"),
    "Brazil": ("#ffdf00", "#00b347"),
    "Cameroon": ("#00a651", "#fcd116"),
    "Canada": ("#e4002b", "#8fa8c8"),
    "Costa Rica": ("#e4002b", "#3a6fe0"),
    "Croatia": ("#ff2e3b", "#3a6fe0"),
    "Denmark": ("#e4173e", "#c8c8c8"),
    "Ecuador": ("#ffd100", "#3a7fe0"),
    "England": ("#e0253b", "#6cace4"),
    "France": ("#2d6ae0", "#ed2939"),
    "Germany": ("#ffce00", "#dd0000"),
    "Ghana": ("#fcd116", "#00a35c"),
    "Iran": ("#239f40", "#e8303a"),
    "Japan": ("#3a6fe0", "#ff3b3b"),
    "Mexico": ("#00a859", "#e4002b"),
    "Morocco": ("#e0303a", "#00a651"),
    "Netherlands": ("#ff7f00", "#3a6fe0"),
    "Poland": ("#e8193f", "#c8c8c8"),
    "Portugal": ("#e8332a", "#00a651"),
    "Qatar": ("#b0254f", "#d9d9d9"),
    "Saudi Arabia": ("#00a651", "#d9d9d9"),
    "Senegal": ("#00a651", "#fdef42"),
    "Serbia": ("#d6363c", "#3a6fe0"),
    "South Korea": ("#e4002b", "#3a6fe0"),
    "Spain": ("#e3001b", "#ffc400"),
    "Switzerland": ("#ff1e1e", "#c8c8c8"),
    "Tunisia": ("#e70013", "#c8c8c8"),
    "United States": ("#3a6fe0", "#e4002b"),
    "Uruguay": ("#5cbfeb", "#f6b40e"),
    "Wales": ("#e4002b", "#00b140"),
}
# Por si los dos colores de un equipo chocan con los del rival
RESPALDO = ["#b36bff", "#36c5f0", "#ff7f00", "#2fd67b", "#ffd400", "#ff4f81"]
# Distancia mínima ("redmean", de 0 a ~765) para considerar distintos dos colores
UMBRAL_COLOR = 200

# Más goles que esto y ya no se escribe el minuto junto a cada uno
MAX_ETIQUETAS = 15


# ---------------------------------------------------------------------------
# Datos
# ---------------------------------------------------------------------------

def cargar_datos(db: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Todos los tiros del torneo y la tabla de partidos."""
    with sqlite3.connect(db) as conn:
        tiros = pd.read_sql_query(
            "SELECT match_id, minuto, equipo, rival, jugador, x, y, xg, gol, tipo_tiro FROM eventos_tiros",
            conn,
        ).dropna(subset=["x", "y"])
        partidos = pd.read_sql_query("SELECT * FROM partidos ORDER BY game_date", conn)
    # StatsBomb tiene el eje Y hacia abajo; lo invertimos para que la banda
    # izquierda del atacante quede arriba al dibujar hacia la derecha.
    tiros["y"] = ANCHO - tiros["y"]
    return tiros, partidos


def selecciones(partidos: pd.DataFrame) -> list[str]:
    return sorted(set(partidos["home_team"]) | set(partidos["away_team"]))


def partidos_de(partidos: pd.DataFrame, seleccion: str | None) -> pd.DataFrame:
    """Partidos de una selección (o todos si es None), en orden cronológico."""
    if seleccion is None:
        return partidos
    return partidos[(partidos["home_team"] == seleccion) | (partidos["away_team"] == seleccion)]


def nombre_partido(info: pd.Series) -> str:
    return f"{info['home_team']} {info['home_score']}-{info['away_score']} {info['away_team']}"


def listar_partidos(partidos: pd.DataFrame) -> None:
    df = pd.DataFrame({
        "match_id": partidos["match_id"],
        "fecha": partidos["game_date"].str[:10],
        "fase": partidos["competition_stage"],
        "partido": partidos.apply(nombre_partido, axis=1),
    })
    print(df.to_string(index=False))


def aviso_autogoles(tiros: pd.DataFrame, info: pd.Series) -> str | None:
    """Los autogoles no son tiros, así que no aparecen en eventos_tiros."""
    marcador = int(info["home_score"]) + int(info["away_score"])
    goles = int(tiros.loc[tiros["match_id"] == info["match_id"], "gol"].sum())
    if goles < marcador:
        return (f"El marcador suma {marcador} goles pero hay {goles} en eventos_tiros; "
                "la diferencia son autogoles, que no tienen tiro.")
    return None


# ---------------------------------------------------------------------------
# Colores
# ---------------------------------------------------------------------------

def distancia_color(a: str, b: str) -> float:
    """Distancia "redmean" entre dos colores: barata y cercana a la percepción."""
    r1, g1, b1 = np.array(to_rgb(a)) * 255
    r2, g2, b2 = np.array(to_rgb(b)) * 255
    rm = (r1 + r2) / 2
    return float(np.sqrt((2 + rm / 256) * (r1 - r2) ** 2 + 4 * (g1 - g2) ** 2
                         + (2 + (255 - rm) / 256) * (b1 - b2) ** 2))


def color_distinto(opciones, contra: str) -> str:
    """El primer color de `opciones` que se distingue de `contra`."""
    for color in opciones:
        if distancia_color(color, contra) >= UMBRAL_COLOR:
            return color
    return max(RESPALDO, key=lambda c: distancia_color(c, contra))


def colores_enfrentamiento(equipo: str, rival: str) -> tuple[str, str]:
    """Color principal para `equipo`; el rival usa el suyo o el alterno si se parecen."""
    propio = COLORES_EQUIPO.get(equipo, (NEUTRO,))[0]
    return propio, color_distinto(COLORES_EQUIPO.get(rival, ()) + tuple(RESPALDO), propio)


def rampa(color: str) -> LinearSegmentedColormap:
    """De transparente al color del equipo, más claro en lo más denso."""
    r, g, b = to_rgb(color)
    claro = tuple(c + (1 - c) * 0.45 for c in (r, g, b))
    cmap = LinearSegmentedColormap.from_list(color, [(r, g, b, 0), (r, g, b, 0.65), (*claro, 0.95)])
    cmap.set_under(alpha=0)  # las zonas vacías dejan ver la cancha
    return cmap


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

@dataclass
class Capa:
    """Los tiros de un equipo, ya orientados hacia donde ataca en la imagen."""
    nombre: str
    datos: pd.DataFrame
    color: str
    hacia_derecha: bool = True


def reflejar(df: pd.DataFrame) -> pd.DataFrame:
    """Gira 180° las coordenadas para que el equipo ataque hacia la izquierda."""
    df = df.copy()
    df["x"] = LARGO - df["x"]
    df["y"] = ANCHO - df["y"]
    return df


def dibujar_cancha(ax: plt.Axes) -> None:
    """Dibuja una cancha StatsBomb de 120 x 80: fondo negro y líneas blancas."""
    ax.add_patch(Rectangle((-3, -3), LARGO + 6, ANCHO + 6, color=CANCHA, zorder=0))
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
    ax.set_ylim(-8, ANCHO + 3)
    ax.set_aspect("equal")
    ax.axis("off")


def mapa_de_calor(capas: list[Capa], titulo: str, unidad: str, modo: str = "kde",
                  ax: plt.Axes | None = None):
    """Dibuja el mapa de calor de cada capa con su color sobre la misma cancha.

    Todas las capas comparten escala, así que el equipo con más tiros se ve
    más intenso. Los goles se marcan encima y el resto de los tiros como
    círculos huecos.
    """
    if ax is None:
        _, ax = plt.subplots(figsize=(11, 7.8))
    fig = ax.figure
    fig.set_facecolor(FONDO)
    ax.set_facecolor(FONDO)
    dibujar_cancha(ax)

    total = sum(len(c.datos) for c in capas)
    contorno = [patheffects.withStroke(linewidth=2.5, foreground=CANCHA)]

    if total == 0:
        ax.text(LARGO / 2, ANCHO / 2, f"Sin {unidad} registrados", ha="center", va="center",
                color=TEXTO_SECUNDARIO, fontsize=14, zorder=5)
    elif modo == "zonas":
        conteos = [densidad_zonas(c.datos["x"].to_numpy(), c.datos["y"].to_numpy()) for c in capas]
        maximo = max(conteo.max() for _, _, conteo in conteos)
        for capa, (bx, by, conteo) in zip(capas, conteos):
            ax.pcolormesh(bx, by, conteo, cmap=rampa(capa.color), vmin=0.5, vmax=max(maximo, 1),
                          edgecolors=CANCHA, linewidth=2, zorder=1)
        # Número solo en las zonas con algo; si coinciden los dos equipos, "a/b"
        bx, by, _ = conteos[0]
        apilado = np.stack([conteo for _, _, conteo in conteos])
        for i in range(apilado.shape[1]):
            for j in range(apilado.shape[2]):
                celda = apilado[:, i, j]
                if celda.sum() > 0:
                    texto = "/".join(str(int(n)) for n in celda) if (celda > 0).sum() > 1 else str(int(celda.sum()))
                    ax.text((bx[j] + bx[j + 1]) / 2, (by[i] + by[i + 1]) / 2, texto,
                            ha="center", va="center", fontsize=11, color=TEXTO, zorder=5,
                            path_effects=contorno)
    else:
        densidades = [densidad_kde(c.datos["x"].to_numpy(), c.datos["y"].to_numpy()) for c in capas]
        maximo = max(z.max() for _, _, z in densidades)
        for capa, (gx, gy, z) in zip(capas, densidades):
            if len(capa.datos):
                # rasterized evita las líneas de costura entre celdas al guardar en PDF/SVG
                ax.pcolormesh(gx, gy, z / maximo, cmap=rampa(capa.color), vmin=0.05, vmax=1,
                              shading="auto", zorder=1, rasterized=True)

    # Ubicación exacta de cada tiro encima del mapa (en zonas ya se ve el conteo)
    solo_goles = unidad == "goles"
    if total and modo == "kde":
        etiquetar = sum(int(c.datos["gol"].sum()) for c in capas) <= MAX_ETIQUETAS
        for capa in capas:
            fallados = capa.datos[capa.datos["gol"] == 0]
            ax.scatter(fallados["x"], fallados["y"], s=36, facecolors="none", edgecolors=capa.color,
                       linewidths=1.2, zorder=5)
            goles = capa.datos[capa.datos["gol"] == 1]
            ax.scatter(goles["x"], goles["y"], s=70, color=capa.color, edgecolors=LINEAS,
                       linewidths=1.5, zorder=6)
            if etiquetar:
                # Goles desde el mismo punto (p. ej. penales) comparten una sola etiqueta
                for (x0, y0), grupo in goles.groupby([goles["x"].round(), goles["y"].round()]):
                    minutos = ", ".join(f"{m}'" for m in sorted(grupo["minuto"].astype(int)))
                    ax.annotate(minutos, (x0, y0), xytext=(6, 6), textcoords="offset points",
                                fontsize=9, color=TEXTO, zorder=7, path_effects=contorno)

    # Debajo de la cancha: quién ataca hacia dónde, en el color de cada equipo
    for capa in capas:
        n = f"{len(capa.datos)} {unidad}"
        if capa.hacia_derecha:
            ax.text(LARGO, -4, f"{capa.nombre} · {n} · ataca →", ha="right", va="top",
                    color=capa.color, fontsize=11, fontweight="bold")
        else:
            ax.text(0, -4, f"← ataca · {capa.nombre} · {n}", ha="left", va="top",
                    color=capa.color, fontsize=11, fontweight="bold")

    leyenda = "Intensidad = concentración relativa" if modo == "kde" else "Número = tiros por zona de 10 × 10"
    if modo == "kde" and not solo_goles:
        leyenda += "  ·  ● gol   ○ tiro"
    elif modo == "zonas" and solo_goles:
        leyenda = leyenda.replace("tiros", "goles")
    ax.text(LARGO / 2, -4, leyenda, ha="center", va="top", color=TEXTO_SECUNDARIO, fontsize=9)

    ax.set_title(titulo, color=TEXTO, fontsize=15, loc="left", pad=12)
    return fig, ax


def construir_figura(tiros: pd.DataFrame, partidos: pd.DataFrame, partido: int | None = None,
                     seleccion: str | None = None, solo_goles: bool = True, modo: str = "kde",
                     por_equipo: bool = False) -> plt.Figure:
    """Arma la figura según lo elegido.

    - Partido: los dos equipos en la misma cancha. Ataca a la derecha la
      selección elegida o, si no hay, el local.
    - Solo selección: todo su torneo; sus tiros atacan a la derecha y los de
      sus rivales a la izquierda.
    - Nada: todos los goles del torneo.
    Con `por_equipo` cada equipo va en su propio panel, atacando a la derecha.
    """
    df = tiros[tiros["gol"] == 1] if solo_goles else tiros
    unidad = "goles" if solo_goles else "tiros"

    if partido is not None:
        info = partidos[partidos["match_id"] == partido]
        if info.empty:
            raise ValueError(f"No existe el partido {partido}. Usa --listar para ver los ids.")
        info = info.iloc[0]
        df = df[df["match_id"] == partido]
        derecha, izquierda = info["home_team"], info["away_team"]
        if seleccion == izquierda:
            derecha, izquierda = izquierda, derecha
        color_der, color_izq = colores_enfrentamiento(derecha, izquierda)
        capas = [Capa(derecha, df[df["equipo"] == derecha], color_der),
                 Capa(izquierda, df[df["equipo"] == izquierda], color_izq)]
        titulo = f"{nombre_partido(info)} · {info['competition_stage']} · {len(df)} {unidad}"
    elif seleccion is not None:
        jugados = len(partidos_de(partidos, seleccion))
        propio = COLORES_EQUIPO.get(seleccion, (NEUTRO,))[0]
        capas = [Capa(seleccion, df[df["equipo"] == seleccion], propio),
                 Capa("Rivales", df[df["rival"] == seleccion], color_distinto(RESPALDO, propio))]
        titulo = (f"{seleccion} · {jugados} partidos · {len(capas[0].datos)} {unidad} a favor, "
                  f"{len(capas[1].datos)} en contra")
    else:
        capas = [Capa("Todos los equipos", df, NEUTRO)]
        titulo = f"Mundial Qatar 2022 · {len(df)} {unidad}"

    if por_equipo and len(capas) == 2:
        fig, ejes = plt.subplots(2, 1, figsize=(11, 14))
        for ax, capa in zip(ejes, capas):
            mapa_de_calor([capa], capa.nombre, unidad, modo, ax)
        fig.suptitle(titulo, color=TEXTO, fontsize=17, x=0.02, ha="left")
    else:
        if len(capas) == 2:
            capas[1].datos = reflejar(capas[1].datos)
            capas[1].hacia_derecha = False
        fig, _ = mapa_de_calor(capas, titulo, unidad, modo)

    fig.text(0.99, 0.01, "Datos: StatsBomb Open Data", ha="right", va="bottom",
             color=TEXTO_SECUNDARIO, fontsize=8)
    # Reservar espacio arriba para el título general de la vista por equipo
    fig.tight_layout(rect=(0, 0, 1, 0.97 if fig.get_suptitle() else 1))
    return fig


# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mapa de calor de goles (Mundial Qatar 2022)")
    parser.add_argument("--db", default=RUTA_DB, type=Path, help="Ruta a minuto_90.sqlite")
    parser.add_argument("--partido", type=int, help="match_id; si se omite, todo el torneo")
    parser.add_argument("--seleccion", help="Nombre de la selección en inglés, p. ej. Argentina")
    parser.add_argument("--listar", action="store_true",
                        help="Muestra los partidos y sus ids (solo los de --seleccion, si se da)")
    parser.add_argument("--modo", choices=["kde", "zonas"], default="kde",
                        help="kde = mancha suavizada, zonas = conteo por cuadrícula")
    parser.add_argument("--por-equipo", action="store_true", help="Un mapa por cada equipo")
    parser.add_argument("--tiros", action="store_true", help="Incluir todos los tiros, no solo goles")
    parser.add_argument("--salida", help="Archivo de imagen (png/svg/pdf). Si se omite, abre una ventana")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"No encuentro la base en {args.db}")
    tiros, partidos = cargar_datos(args.db)
    if args.seleccion and args.seleccion not in selecciones(partidos):
        parser.error(f"No existe la selección {args.seleccion!r}. Opciones: {', '.join(selecciones(partidos))}")

    if args.listar:
        listar_partidos(partidos_de(partidos, args.seleccion))
        return

    try:
        fig = construir_figura(tiros, partidos, args.partido, args.seleccion,
                               solo_goles=not args.tiros, modo=args.modo, por_equipo=args.por_equipo)
    except ValueError as error:
        raise SystemExit(str(error))
    if args.partido is not None:
        aviso = aviso_autogoles(tiros, partidos[partidos["match_id"] == args.partido].iloc[0])
        if aviso:
            print(f"Aviso: {aviso}")

    if args.salida:
        fig.savefig(args.salida, dpi=150, facecolor=FONDO)
        print(f"Mapa guardado en {args.salida}")
    else:
        plt.show()


if __name__ == "__main__":
    main()
