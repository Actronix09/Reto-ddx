"""
Interfaz del mapa de calor: elige selección y partido desde el navegador.

Uso:
    streamlit run app.py
"""

from io import BytesIO

import matplotlib.pyplot as plt
import streamlit as st

from heatmap_goles import (FONDO, RUTA_DB, aviso_autogoles, cargar_datos, construir_figura,
                           nombre_partido, partidos_de, selecciones)

st.set_page_config(page_title="Mapa de calor · Qatar 2022", layout="wide")

if not RUTA_DB.exists():
    st.error(f"No encuentro la base en {RUTA_DB}")
    st.stop()


@st.cache_data
def datos():
    return cargar_datos(RUTA_DB)


tiros, partidos = datos()

with st.sidebar:
    st.header("Mapa de calor")
    seleccion = st.selectbox("Selección", [None] + selecciones(partidos),
                             format_func=lambda s: "Todas" if s is None else s)

    lista = partidos_de(partidos, seleccion)
    etiquetas = {fila.match_id: f"{fila.game_date[:10]} · {nombre_partido(fila)} · {fila.competition_stage}"
                 for _, fila in lista.iterrows()}
    partido = st.selectbox("Partido", [None] + list(etiquetas),
                           format_func=lambda m: "Todos los partidos" if m is None else etiquetas[m])

    que = st.radio("Mostrar", ["Goles", "Todos los tiros"], horizontal=True)
    modo = st.radio("Estilo", ["kde", "zonas"], horizontal=True,
                    format_func=lambda m: "Mancha" if m == "kde" else "Zonas")
    por_equipo = st.toggle("Un panel por equipo", disabled=seleccion is None and partido is None)

fig = construir_figura(tiros, partidos, partido, seleccion, solo_goles=que == "Goles",
                       modo=modo, por_equipo=por_equipo)
st.pyplot(fig, width="stretch")

if partido is not None:
    aviso = aviso_autogoles(tiros, lista[lista["match_id"] == partido].iloc[0])
    if aviso:
        st.info(aviso)

imagen = BytesIO()
fig.savefig(imagen, format="png", dpi=150, facecolor=FONDO)
plt.close(fig)
st.download_button("Descargar PNG", imagen.getvalue(), file_name="mapa_de_calor.png", mime="image/png")
