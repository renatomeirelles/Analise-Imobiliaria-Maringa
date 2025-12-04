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

gdf_bairros = gpd.read_file("data/municipio_completo.shp")
gdf_bairros = gdf_bairros.to_crs("EPSG:4326")

# =========================
# Interface Streamlit
# =========================
st.title("🏠 Análise Imobiliária Maringá")

tipo_estatistica = st.selectbox("Selecione a estatística:",
    [
        "Preço médio total",
        "Preço médio por m²",
        "Preço médio apartamentos",
        "Preço médio por m² apartamentos",
        "Preço médio casas",
        "Preço médio por m² casas",
        "Preço médio condomínios",
        "Preço médio por m² condomínios"
    ]
)

tipo_mapa = st.selectbox("Selecione o tipo de mapa:", ["Coroplético", "Pontos", "Cluster", "Calor"])

# =========================
# Cálculo estatístico
# =========================
if "por m²" in tipo_estatistica:
    df["valor_m2"] = df["Preço"] / df["Área"]

if tipo_estatistica == "Preço médio total":
    df_filtrado = df.copy()
    coluna_valor = "Preço"
elif tipo_estatistica == "Preço médio por m²":
    df_filtrado = df.copy()
    coluna_valor = "valor_m2"
elif "apartamentos" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("apartamento")]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"
elif "casas" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("casa")]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"
elif "condomínios" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("condomínio")]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"

# =========================
# Mapa base
# =========================
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=13)

# =========================
# Mapa Coroplético
# =========================
if tipo_mapa == "Coroplético":
    preco_bairro = df_filtrado.groupby("Bairro")[coluna_valor].agg(["mean", "min", "max"]).reset_index()
    preco_bairro.columns = ["Bairro", "media", "min", "max"]
    media_total = df_filtrado[coluna_valor].mean()
    preco_bairro["variacao"] = ((preco_bairro["media"] - media_total) / media_total) * 100

    gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

    bins = [120000, 300000, 500000, 800000, 1000000, 1500000, 2500000, 5000000, 10500000]
    folium.Choropleth(
        geo_data=gdf_plot,
        data=gdf_plot,
        columns=["NOME", "media"],
        key_on="feature.properties.NOME",
        fill_color="YlOrRd",
        fill_opacity=0.7,
        line_opacity=0.2,
        bins=bins,
        legend_name="Preço médio por bairro (R$)"
    ).add_to(m)

    for _, row in gdf_plot.iterrows():
        if pd.notnull(row["media"]):
            tooltip = f"""
            <b>{row['NOME']}</b><br>
            Média: R$ {row['media']:,.0f}<br>
            Mínimo: R$ {row['min']:,.0f}<br>
            Máximo: R$ {row['max']:,.0f}<br>
            Variação: {row['variacao']:.1f}%
            """
            folium.GeoJson(
                row["geometry"],
                tooltip=folium.Tooltip(tooltip, sticky=True)
            ).add_to(m)

# =========================
# Mapa Pontos
# =========================
elif tipo_mapa == "Pontos":
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

# =========================
# Mapa Cluster
# =========================
elif tipo_mapa == "Cluster":
    from folium.plugins import MarkerCluster
    cluster = MarkerCluster().add_to(m)
    for _, row in df_filtrado.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row['Tipo']} — R$ {row['Preço']:,.2f}"
        ).add_to(cluster)

# =========================
# Mapa Calor
# =========================
elif tipo_mapa == "Calor":
    from folium.plugins import HeatMap
    HeatMap(df_filtrado[["latitude", "longitude"]].values, radius=15).add_to(m)

# =========================
# Exibir mapa
# =========================
st_folium(m, width=750, height=550)
