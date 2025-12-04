import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap

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

# Filtros
tipo_imovel = st.selectbox("Selecione o tipo de imóvel:", df["Tipo"].unique())
faixa_preco = st.slider("Selecione a faixa de preço:",
                        int(df["Preço"].min()), int(df["Preço"].max()),
                        (int(df["Preço"].min()), int(df["Preço"].max())))

df_filtrado = df[(df["Tipo"] == tipo_imovel) &
                 (df["Preço"].between(faixa_preco[0], faixa_preco[1]))]

# Dropdown de mapas
tipo_mapa = st.selectbox(
    "Selecione o tipo de mapa:",
    ["Coroplético", "Pontos", "Cluster", "Calor"]
)

m = folium.Map(location=[-23.4205, -51.9331], zoom_start=13)

if tipo_mapa == "Pontos":
    for _, row in df_filtrado.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color="#3388ff",
            fill=True,
            fill_color="#3388ff",
            fill_opacity=0.6,
            popup=f"{row['Tipo']} — R$ {row['Preço']:,.2f}"
        ).add_to(m)

elif tipo_mapa == "Cluster":
    cluster = MarkerCluster().add_to(m)
    for _, row in df_filtrado.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row['Tipo']} — R$ {row['Preço']:,.2f}"
        ).add_to(cluster)

elif tipo_mapa == "Calor":
    HeatMap(df_filtrado[["latitude", "longitude"]].values, radius=15).add_to(m)

elif tipo_mapa == "Coroplético":
    # Calcula preço médio por bairro
    preco_medio = df_filtrado.groupby("Bairro")["Preço"].mean().reset_index()
    folium.Choropleth(
        geo_data=gdf_bairros,
        data=preco_medio,
        columns=["Bairro", "Preço"],
        key_on="feature.properties.NOME",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        legend_name="Preço médio por bairro"
    ).add_to(m)

st_folium(m, width=700, height=500)
