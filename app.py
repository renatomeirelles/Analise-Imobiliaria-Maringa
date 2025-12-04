
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# =========================
# Carregar dados
# =========================
df = pd.read_excel("data/imoveis_georreferenciados_novembro.xlsx")
df.columns = df.columns.str.strip()
df = df.dropna(subset=["latitude", "longitude"])

gdf_imoveis = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
    crs="EPSG:4326"
)

gdf_bairros = gpd.read_file("data/municipio_completo.shp")
gdf_bairros = gdf_bairros.to_crs("EPSG:4326")

# =========================
# Interface Streamlit
# =========================
st.title("🏠 Análise Imobiliária Maringá")

tipo_mapa = st.selectbox(
    "Selecione o tipo de mapa:",
    ["Coroplético", "Pontos", "Cluster", "Calor"]
)

st.write("Mapa interativo dos imóveis em Maringá")

# Exemplo simples: mostrar pontos
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=13)

for _, row in df.iterrows():
    folium.CircleMarker(
        location=[row["latitude"], row["longitude"]],
        radius=3,
        color="#3388ff",
        fill=True,
        fill_color="#3388ff",
        fill_opacity=0.6,
        popup=f"{row['Tipo']} — R$ {row['Preço']:,.2f}"
    ).add_to(m)

st_folium(m, width=700, height=500)
