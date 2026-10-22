# Mapa de calor de goles · RETO d/dx MINUTO 90

Script en Python que dibuja un mapa de calor de los goles (o de todos los tiros) del Mundial
Qatar 2022 sobre una cancha negra con líneas blancas, usando matplotlib. Los dos equipos comparten
la cancha, cada uno atacando hacia un lado y pintado con los colores de su selección. Incluye
una interfaz web (Streamlit) para elegir selección y partido.

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

## Interfaz

```bash
streamlit run app.py
```

Se abre en el navegador. En la barra lateral se elige:

- **Selección**: "Todas" o una de las 32. Al elegir una, la lista de partidos se reduce a los suyos.
- **Partido**: "Todos los partidos" o uno en concreto.
- **Mostrar**: solo goles o todos los tiros.
- **Estilo**: mancha suavizada o conteo por zonas.
- **Un panel por equipo**: separa a los dos equipos en dos canchas.

El botón **Descargar PNG** guarda la imagen que se está viendo.

## Línea de comandos

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

# Todo el torneo de una selección: sus tiros a la derecha, los de sus rivales a la izquierda
python heatmap_goles.py --seleccion Argentina

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
| `--listar` | Muestra los 64 partidos con su `match_id`, fecha, fase y marcador (solo los de `--seleccion`, si se da). |
| `--partido ID` | Partido a graficar. Si se omite, usa todo el torneo. |
| `--seleccion NOMBRE` | Selección, con su nombre en inglés (`Argentina`, `South Korea`...). Sin `--partido` muestra todo su torneo; con `--partido` la pone atacando a la derecha. |
| `--modo kde` | *(por defecto)* Mancha suavizada; marca cada gol con el minuto en que se anotó. |
| `--modo zonas` | Divide la cancha en cuadros de 10 × 10 y muestra cuántos goles hubo en cada uno. |
| `--por-equipo` | Dos paneles, uno por selección, ambos atacando hacia la derecha. |
| `--tiros` | Usa todos los tiros, no solo los goles. Los goles van como puntos rellenos y los demás tiros como círculos huecos. |
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
   datos, se gira 180° al segundo equipo para que ataque hacia la izquierda. A la derecha va la
   selección elegida o, si no se eligió, el local. En la vista de una selección sin partido, el
   otro lado son los tiros de todos sus rivales. Debajo de la cancha se indica hacia dónde ataca
   cada uno. Con `--por-equipo` no se gira.
4. **Densidad.**
   - `kde`: suma una campana gaussiana (σ = 6 yardas) en la posición de cada gol y divide entre
     el máximo de los dos equipos. Es concentración relativa dentro del mismo mapa, y como los dos
     comparten escala, el que más tiró se ve más intenso.
   - `zonas`: un histograma 2D de 12 × 8 cuadros; cada cuadro muestra su conteo (`a/b` si los dos
     equipos tienen tiros en el mismo cuadro).
5. **Colores por equipo.** Cada selección tiene un color principal y uno alterno en
   `COLORES_EQUIPO`. Si el principal del rival se parece demasiado al del otro equipo (distancia
   de color menor a `UMBRAL_COLOR`), se usa su alterno, y si ese tampoco sirve, uno de `RESPALDO`.
   En la final, por ejemplo, Argentina va en celeste y Francia en rojo. Cada mancha va de
   transparente al color del equipo, así que las zonas sin tiros dejan ver la cancha.
6. **Dibujo.** Cancha negra con líneas blancas. Los goles anotados desde el mismo punto (por
   ejemplo, penales) comparten una sola etiqueta con sus minutos.

### Ajustes rápidos en el código

Todo está al inicio de `heatmap_goles.py`:

- `CANCHA`, `LINEAS`, `FONDO`, `TEXTO`: colores de la cancha y del texto.
- `COLORES_EQUIPO`, `RESPALDO`, `UMBRAL_COLOR`: colores de cada selección y qué tan distintos deben ser.
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
