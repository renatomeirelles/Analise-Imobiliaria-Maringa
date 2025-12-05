import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
import matplotlib.patches as mpatches

# =========================
# Carregar dados
# =========================
df = pd.read_excel("data/imoveis_georreferenciados_novembro.xlsx")
df.columns = df.columns.str.strip()
df = df.dropna(subset=["latitude", "longitude"])

gdf_bairros = gpd.read_file("data/municipio_completo.shp")
gdf_bairros = gdf_bairros.to_crs("EPSG:4326")

# Criar coluna valor_m2 se existir Tamanho(m²)
if "Tamanho(m²)" in df.columns:
    df["valor_m2"] = df["Preço"] / df["Tamanho(m²)"]

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
estilo_mapa = st.selectbox("Selecione o estilo de fundo:", ["Claro", "Escuro"])

# =========================
# Filtros e coluna alvo
# =========================
if tipo_estatistica == "Preço médio total":
    df_filtrado = df.copy()
    coluna_valor = "Preço"
elif tipo_estatistica == "Preço médio por m²":
    df_filtrado = df[df["valor_m2"].notnull()]
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
# Exibir resumo estatístico
# =========================
num_imoveis = len(df_filtrado)
media_imoveis = df_filtrado[coluna_valor].mean()

st.markdown(f"**🔢 Imóveis encontrados:** {num_imoveis}")
st.markdown(f"**📊 Média ({tipo_estatistica}):** R$ {media_imoveis:,.2f}")

# =========================
# Mapa base
# =========================
tiles = "CartoDB positron" if estilo_mapa == "Claro" else "CartoDB dark_matter"
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=13, tiles=tiles, control_scale=True)

# =========================
# Paleta e faixas fixas
# =========================
bins = [120000, 300000, 500000, 800000, 1000000, 1500000, 2500000, 5000000, 10500000]
cores = ['#FF0000', '#FFA500', '#FFFF00', '#00FF00', '#00CED1', '#0000FF', '#8A2BE2', '#FF69B4', '#A52A2A']

# =========================
# Mapa Coroplético com spatial join
# =========================
if tipo_mapa == "Coroplético":
    # Converte imóveis em GeoDataFrame
    gdf_imoveis = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
        crs="EPSG:4326"
    )

    # Faz o spatial join: cada imóvel recebe o bairro do shapefile
    gdf_join = gpd.sjoin(gdf_imoveis, gdf_bairros, how="left", predicate="within")

    # Agrupa pelo bairro oficial do shapefile
    preco_bairro = gdf_join.groupby("NOME")[coluna_valor].agg(["mean", "min", "max"]).reset_index()
    preco_bairro.columns = ["Bairro", "media", "min", "max"]
    media_total = gdf_join[coluna_valor].mean()
    preco_bairro["variacao"] = ((preco_bairro["media"] - media_total) / media_total) * 100

    # Junta com shapefile
    gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

    def cor_por_faixa(valor):
        if pd.isna(valor) or valor <= 0:
            return "#D3D3D3"
        for i in range(len(bins)-1):
            if bins[i] <= valor <= bins[i+1]:
                return cores[i]
        return cores[-1]

    gdf_plot["cor"] = gdf_plot["media"].apply(cor_por_faixa)

    folium.GeoJson(
        gdf_plot,
        style_function=lambda feature: {
            "fillColor": feature["properties"]["cor"],
            "color": "white",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NOME", "media", "min", "max", "variacao"],
            aliases=["Bairro", "Média", "Mínimo", "Máximo", "Variação (%)"],
            localize=True
        )
    ).add_to(m)

    # Legenda manual
    legendas = [mpatches.Patch(color=cores[i],
                label=f"{bins[i]:,.0f} a {bins[i+1]:,.0f}") for i in range(len(bins)-1)]
    legendas.append(mpatches.Patch(color="#D3D3D3", label="Sem dados"))

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
    cluster = MarkerCluster(control=False).add_to(m)
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
st_folium(m, width=750, height=550, returned_objects=[], use_container_width=True)
