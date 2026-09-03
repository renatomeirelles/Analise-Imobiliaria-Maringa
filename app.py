import streamlit as st
import pydeck as pdk
import geopandas as gpd
from pathlib import Path

st.set_page_config(page_title="GeoReceita", layout="wide")

# ---------------------------------------------------------
# CAMINHOS DOS DADOS
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CAMINHOS_SHP = {
    "Maringá": DATA_DIR / "Maringa.shp",
    "Bairros": DATA_DIR / "Bairros.shp",
    "Quadras": DATA_DIR / "Quadra.shp",
    "Lotes":   DATA_DIR / "Lotes.shp",
}

# ---------------------------------------------------------
# CARGA E PADRONIZAÇÃO DE CRS (cacheada — só recarrega se o arquivo mudar)
# ---------------------------------------------------------
@st.cache_data
def carregar_camadas():
    gdfs = {}
    for nome, caminho in CAMINHOS_SHP.items():
        gdf = gpd.read_file(caminho)
        if gdf.crs is None:
            raise ValueError(f"Camada '{nome}' não tem CRS definido no .prj.")
        gdf = gdf.to_crs("EPSG:4326")
        gdfs[nome] = gdf.__geo_interface__  # já converte para GeoJSON aqui
    return gdfs

geojsons = carregar_camadas()

# ---------------------------------------------------------
# DEFINIÇÃO DAS CAMADAS
# ---------------------------------------------------------
def cria_layer_maringa():
    return pdk.Layer(
        "GeoJsonLayer", data=geojsons["Maringá"],
        stroked=True, filled=False, get_line_color=[255, 255, 255], line_width_min_pixels=2,
    )

def cria_layer_bairros():
    return pdk.Layer(
        "GeoJsonLayer", data=geojsons["Bairros"],
        stroked=True, filled=True, get_fill_color=[70, 130, 180, 40],
        get_line_color=[70, 130, 180], line_width_min_pixels=1, pickable=True,
    )

def cria_layer_quadras():
    return pdk.Layer(
        "GeoJsonLayer", data=geojsons["Quadras"],
        stroked=True, filled=False, get_line_color=[255, 165, 0], line_width_min_pixels=1, pickable=True,
    )

def cria_layer_lotes():
    return pdk.Layer(
        "GeoJsonLayer", data=geojsons["Lotes"],
        stroked=True, filled=True, get_fill_color=[200, 30, 30, 60],
        get_line_color=[200, 30, 30], line_width_min_pixels=0.5, pickable=True,
    )

CRIADORES_LAYER = {
    "Maringá": cria_layer_maringa,
    "Bairros": cria_layer_bairros,
    "Quadras": cria_layer_quadras,
    "Lotes":   cria_layer_lotes,
}

# ---------------------------------------------------------
# INTERFACE — TÍTULO E SELETOR DE CAMADAS (barra lateral)
# ---------------------------------------------------------
st.title("GeoReceita")
st.caption("Camadas territoriais de Maringá — Bairros, Quadras e Lotes")

st.sidebar.header("Camadas")
camadas_selecionadas = []
for nome in CRIADORES_LAYER:
    padrao = nome in ["Maringá", "Bairros"]  # ligadas por padrão
    if st.sidebar.checkbox(nome, value=padrao):
        camadas_selecionadas.append(nome)

# ---------------------------------------------------------
# MONTAGEM E EXIBIÇÃO DO MAPA
# ---------------------------------------------------------
layers = [CRIADORES_LAYER[nome]() for nome in camadas_selecionadas]

view_state = pdk.ViewState(latitude=-23.42, longitude=-51.94, zoom=11, pitch=0)

deck = pdk.Deck(
    layers=layers,
    initial_view_state=view_state,
    tooltip={
        "html": "<b>{NOME}</b>{QUADRA_GEO}{LOTE}",
        "style": {"backgroundColor": "white", "color": "black"},
    },
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
)

st.pydeck_chart(deck, use_container_width=True, height=700)