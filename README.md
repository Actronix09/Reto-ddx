# Mapa de calor de goles · RETO d/dx MINUTO 90

Script en Python que dibuja un mapa de calor de los goles (o de todos los tiros) de un
partido del Mundial Qatar 2022, sobre una cancha de fútbol, usando matplotlib.

## Instalación

Se necesita Python 3.10 o más reciente.

```bash
python -m venv .venv
source .venv/bin/activate        # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Los datos del reto deben estar en la carpeta `RETO_ddx_MINUTO_90_completo/` junto al script;
el script lee la base `RETO_ddx_MINUTO_90_completo/sql/minuto_90.sqlite`. Si está en otro lado,
usa `--db ruta/a/minuto_90.sqlite`.

## Uso

Primero busca el `match_id` del partido que quieres ver:

```bash
python heatmap_goles.py --listar
```

```
 match_id      fecha            fase                       partido
  3857286 2022-11-20     Group Stage             Qatar 0-2 Ecuador
  3857271 2022-11-21     Group Stage              England 6-2 Iran
  ...
```

Luego genera el mapa:

```bash
# Goles de la final, los dos equipos en la misma cancha
python heatmap_goles.py --partido 3869685

# Un mapa por cada equipo
python heatmap_goles.py --partido 3869685 --por-equipo

# Todos los tiros del partido (los goles se marcan encima)
python heatmap_goles.py --partido 3869685 --tiros

# Conteo por zonas en lugar de mancha suavizada
python heatmap_goles.py --partido 3869685 --modo zonas

# Todos los goles del torneo
python heatmap_goles.py --modo zonas

# Guardar la imagen en vez de abrir una ventana (png, svg o pdf)
python heatmap_goles.py --partido 3869685 --salida final.png
```

### Opciones

| Opción | Qué hace |
|---|---|
| `--listar` | Muestra los 64 partidos con su `match_id`, fecha, fase y marcador. |
| `--partido ID` | Partido a graficar. Si se omite, usa todos los goles del torneo. |
| `--modo kde` | *(por defecto)* Mancha suavizada; marca cada gol con el minuto en que se anotó. |
| `--modo zonas` | Divide la cancha en cuadros de 10 × 10 y muestra cuántos goles hubo en cada uno. |
| `--por-equipo` | Dos paneles, uno por selección, ambos atacando hacia la derecha. |
| `--tiros` | Usa todos los tiros, no solo los goles. Los goles van en negro y los demás tiros como círculos huecos. |
| `--salida ARCHIVO` | Guarda la imagen en ese archivo. Sin esta opción se abre una ventana. |
| `--db RUTA` | Ruta a `minuto_90.sqlite`, si no está en la ubicación por defecto. |

## Cómo funciona

1. **Lectura de datos.** Consulta la tabla `eventos_tiros` de la base SQLite y, si se pide un
   partido, la tabla `partidos` para el título (equipos, marcador y fase). Sin `--tiros`,
   solo toma las filas con `gol = 1`.
2. **Coordenadas.** Los datos son de StatsBomb: cancha de 120 × 80, y cada evento viene
   orientado hacia el ataque del equipo que lo hace (`x = 120` es la portería rival). La
   cancha se dibuja en esas mismas unidades, así que cada gol cae en su lugar exacto respecto
   a las áreas. El eje Y se invierte porque StatsBomb lo mide hacia abajo.
3. **Los dos equipos en una cancha.** Como los dos equipos atacan hacia la derecha en los
   datos, en la vista normal se gira 180° al visitante para que ataque hacia la izquierda,
   y debajo de la cancha se indica hacia dónde ataca cada uno. Con `--por-equipo` no se gira.
4. **Densidad.**
   - `kde`: suma una campana gaussiana (σ = 6 yardas) en la posición de cada gol y normaliza
     el resultado entre 0 y 1. Por eso la escala dice "Baja / Alta" y no un número: es
     concentración relativa dentro del mismo mapa.
   - `zonas`: un histograma 2D de 12 × 8 cuadros; cada cuadro muestra su conteo.
5. **Dibujo.** Rampa de color de un solo tono (azul claro → oscuro); las zonas sin goles quedan
   transparentes para que se vea la cancha. Los goles anotados desde el mismo punto (por ejemplo,
   penales) comparten una sola etiqueta con sus minutos.

### Ajustes rápidos en el código

Todo está al inicio de `heatmap_goles.py`:

- `RAMPA`, `SUPERFICIE`, `LINEAS`, `TEXTO`: colores del mapa.
- `MAX_ETIQUETAS`: a partir de cuántos goles se dejan de escribir los minutos (15).
- `sigma` en `densidad_kde()`: qué tan anchas son las manchas.
- `bins` en `densidad_zonas()`: tamaño de la cuadrícula.

## Detalles de los datos a tener en cuenta

- **Los autogoles no aparecen**, porque no son tiros. Cuando el marcador del partido suma más
  goles de los que hay en `eventos_tiros`, el script lo avisa en la terminal. Pasa en
  Canada–Morocco, Costa Rica–Germany y Argentina–Australia.
- **El minuto empieza en 0**, como en StatsBomb: un gol del minuto 80 de la transmisión
  aparece como `79'`.
- **Las tandas de penales no están** en `eventos_tiros`, así que no se mezclan con los goles
  del partido. El marcador del título incluye la prórroga, pero no la tanda.
- Los nombres de los equipos vienen en inglés, como en la fuente.

## Créditos y uso de los datos

Datos: **StatsBomb Open Data** (competición 43, temporada 106), reorganizados por NEXT LEVEL DX
para el RETO d/dx. El crédito ya va impreso en cada imagen.

Los datos son solo para el reto y deben borrarse a más tardar el **31 de octubre de 2026**.
Por eso las carpetas `RETO_ddx_MINUTO_90_*` están en `.gitignore` y no se suben al repositorio.
