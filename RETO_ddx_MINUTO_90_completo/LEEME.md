# RETO d/dx · MINUTO 90 — Datos del Mundial Qatar 2022

64 partidos · 32 selecciones · 680 jugadores · fase de grupos a la final.

## Qué hay en cada tabla

| Tabla | Una fila es… | Filas | Para qué sirve |
|---|---|---|---|
| `partidos` | un partido | 64 | Fecha, fase, estadio, árbitro y marcador final |
| `jugador_partido` | un jugador en un partido | 1,995 | Lo que hizo cada jugador en cada juego: xG, tiros, pases progresivos, presiones, minutos |
| `jugador_torneo` | un jugador en todo el torneo | 684 | Totales y valores por 90 minutos, % de pases, % de duelos |
| `valor_jugador_far` | un jugador | 680 | Cuánto valor aportó en ataque y defensa (modelo VAEP) |
| `valor_equipo_far` | una selección | 32 | Valor promedio de ataque y defensa del plantel |
| `prediccion_mundial_2026` | una selección | 48 | Probabilidades **simuladas** de avanzar en el Mundial 2026 |
| `eventos_pases` | un pase | 68,515 | Quién pasa a quién, desde dónde, hacia dónde, minuto y marcador en ese momento → **red de pases** |
| `eventos_tiros` | un tiro | 1,453 | Ubicación, xG, resultado, minuto y marcador → **mapa de tiros con xG** |
| `eventos_acciones` | una acción con balón o defensiva | 229,319 | Ubicación de pases, conducciones, recepciones, presiones, recuperaciones… → **mapa de calor** |

Llaves: `match_id` une todo con `partidos`; `player_id` (tablas de jugadores) = `jugador_id` (tablas de eventos).

## Las columnas que responden la pregunta del reto

**¿Qué pasa con mis jugadores cuando el partido se decide?** Cada evento trae:

- `tramo`: bloque de 15 minutos (`75-90+` es el cierre; `Prórroga` aparte).
- `estado_marcador`: `Ganando`, `Empatando` o `Perdiendo` en ese instante, desde la óptica del equipo.
- `marcador_equipo` y `marcador_rival`: goles justo antes de la acción.

Ejemplo: compara el porcentaje de pases completos de un equipo entre `00-15` y `75-90+`, o cuánto xG genera cuando va perdiendo.

## La cancha

Coordenadas de 120 × 80. `x = 0` es la portería propia del equipo que hace la acción y `x = 120` la portería rival; `y = 0` es la banda izquierda vista desde su portería. Todos los eventos están orientados hacia el ataque del equipo que los hace.

## Formatos

| Carpeta | Úsala con |
|---|---|
| `excel/minuto_90_dataset.xlsx` | Excel, Google Sheets, Looker Studio. Trae todo excepto `eventos_acciones` (no cabe cómodo en Excel; está en CSV). |
| `csv/` | Cualquier herramienta. UTF-8 con BOM. |
| `sql/minuto_90.sqlite` | DB Browser for SQLite, DBeaver, Python, R. Incluye la vista `v_equipo_por_tramo`. |
| `parquet/` | pandas, Power BI, DuckDB. Lo más rápido para los eventos. |
| `json/` | Apps web (tablas chicas y tiros). |

```python
import pandas as pd
pases = pd.read_parquet("parquet/eventos_pases.parquet")
final = pases[(pases.match_id == 3869685) & (pases.equipo == "Argentina") & pases.completado]
red = final.groupby(["jugador", "receptor"]).size().reset_index(name="pases")
```

`mplsoccer` (pip install mplsoccer) dibuja la cancha en el formato 120 × 80.

## Origen de los datos y crédito

- Tablas agregadas (`partidos`, `jugador_*`, `valor_*`, `prediccion_mundial_2026`): preparadas por el aliado de datos de futbol del reto a partir de los eventos del Mundial 2022. `prediccion_mundial_2026` es una simulación de un modelo, no un resultado.
- Tablas de eventos: **StatsBomb Open Data** (competición 43, temporada 106), reorganizadas por NEXT LEVEL DX con las columnas `tramo` y `estado_marcador`. Si publican algo con estos datos, den crédito: *"Datos: StatsBomb Open Data"*.
- Los nombres de equipos y jugadores vienen en inglés, como en la fuente. Ojo: no todas las tablas escriben igual a todos los equipos (por ejemplo `United States` y `USA`). Revisarlo es parte del manejo de datos.

## Uso

Solo para el RETO d/dx. Bórrenlos a más tardar el 31 de octubre de 2026 (bases, sección 08).
