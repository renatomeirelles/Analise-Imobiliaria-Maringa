import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap

# =========================
# Configuração de tiles Jawg Dark
# =========================
access_token = "ZK6EgfhFT6px8F8MsRfOp2S5aUMPOvNr5CEEtLmjOYjHDC2MzgI0ZJ1cJjj0C98Y"
tiles_url = f"https://tile.jawg.io/jawg-dark/{{z}}/{{x}}/{{y}}{{r}}.png?access-token={access_token}"
attr = '<a href="https://jawg.io" target="_blank">&copy; <b>Jawg</b>Maps</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

# =========================
# Carregar dados
# =========================
df = pd.read_excel("data/imoveis_georreferenciados_novembro.xlsx")
df.columns = df.columns.str.strip()
df = df.dropna(subset=["latitude", "longitude"])

gdf_bairros = gpd.read_file("data/municipio_completo.shp")
gdf_bairros = gdf_bairros.to_crs("EPSG:4326")

if "Tamanho(m²)" in df.columns:
    df["valor_m2"] = df["Preço"] / df["Tamanho(m²)"]

# =========================
# Paleta e faixas
# =========================
cores = ['#FF0000', '#FFA500', '#FFFF00', '#00FF00', '#00CED1',
         '#0000FF', '#8A2BE2', '#FF69B4', '#A52A2A']

faixas_base = {
    'preco': [120000, 300000, 500000, 800000, 1000000,
              1500000, 2500000, 5000000, 10500000],
    'm2':    [1000, 2500, 4000, 6000, 8000,
              12000, 18000, 25000, 33000],
}

faixas_dict = {
    'preco_medio_total': faixas_base['preco'],
    'preco_medio_por_m2': faixas_base['m2'],
    'preco_medio_apartamentos': faixas_base['preco'],
    'preco_medio_por_m2_apartamentos': faixas_base['m2'],
    'preco_medio_casas': faixas_base['preco'],
    'preco_medio_por_m2_casas': faixas_base['m2'],
    'preco_medio_condominios': faixas_base['preco'],
    'preco_medio_por_m2_condominios': faixas_base['m2'],
}

# =========================
# Aparência customizada (CORRIGIDO)
# =========================
st.markdown(
    """
    <style>
    .stApp {
        background-image: url("maringa.jpg");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
        color: #FAFAFA;
    }
    .banner {
        background: rgba(0,0,0,0.65);
        padding: 40px;
        border-radius: 10px;
        margin-bottom: 20px;
        text-align: center;
        color: white;
    }
    .banner h1 {
        font-size: 42px;
        font-weight: 800;
        color: #00CED1;
        text-shadow: 2px 2px 4px #000000;
        margin: 0;
    }
    .banner p {
        margin: 8px 0 0 0;
        font-size: 16px;
        opacity: 0.95;
    }
    .title-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }
    .sub-metrics {
        display: flex;
        gap: 16px;
        margin: 10px 0 14px 0;
        flex-wrap: wrap;
    }
    .sub-metric {
        background: #ffffff;
        color: #000000;
        border: 1px solid #ccc;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 14px;
    }
    </style>
    <div class="banner">
        <div class="title-row">
            <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Line_chart_icon.svg/120px-Line_chart_icon.svg.png" width="54">
            <h1>Análise Estatística Imobiliária - Maringá</h1>
        </div>
        <p>Estudo estatístico e geográfico dos valores de imóveis</p>
    </div>
    """,
    unsafe_allow_html=True,
)
# =========================
# Faixas fixas conforme métrica
# =========================
bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])

# =========================
# Mapas
# =========================
if tipo_mapa == "Coroplético":
    # GeoDataFrame de imóveis
    gdf_imoveis = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
        crs="EPSG:4326",
    )

    # Join espacial para obter bairro oficial
    gdf_join = gpd.sjoin(gdf_imoveis, gdf_bairros[["geometry", "NOME"]], how="left", predicate="within")

    # Agregação por bairro
    preco_bairro = gdf_join.groupby("NOME")[coluna_valor].agg(["mean", "min", "max"]).reset_index()
    preco_bairro.columns = ["Bairro", "media", "min", "max"]

    # Variação percentual relativa à média global
    media_total = gdf_join[coluna_valor].mean()
    preco_bairro["variacao"] = ((preco_bairro["media"] - media_total) / media_total) * 100

    # Merge com shapefile
    gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

    # Cores por faixa fixa
    def cor_por_faixa(valor):
        if pd.isna(valor) or valor <= 0:
            return "#D3D3D3"
        for i in range(len(bins) - 1):
            if bins[i] <= valor <= bins[i + 1]:
                return cores[i]
        return cores[-1]

    gdf_plot["cor"] = gdf_plot["media"].apply(cor_por_faixa)

    folium.GeoJson(
        gdf_plot,
        style_function=lambda feature: {
            "fillColor": feature["properties"]["cor"],
            "color": "#f0f0f0",
            "weight": 0.6,
            "fillOpacity": 0.75,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NOME", "media", "min", "max", "variacao"],
            aliases=["Bairro", "Média", "Mínimo", "Máximo", "Variação (%)"],
            localize=True,
        ),
    ).add_to(m)

    # Legenda lateral
    titulo_legenda = "Faixas de preço por m² (R$)" if "m²" in tipo_estatistica else "Faixas de preço (R$)"
    legend_lines = "".join(
        [
            f"<div style='margin:2px 0;'>"
            f"<span style='display:inline-block;width:20px;height:10px;background:{cores[i]};"
            f"margin-right:5px;border:1px solid #999'></span>{bins[i]:,} – {bins[i+1]:,}"
            f"</div>"
            for i in range(len(bins) - 1)
        ]
    )
    legenda_html = f"""
    <div style='position: fixed; top: 8px; right: 8px; z-index:9999;
                background-color: rgba(255,255,255,0.95); padding:10px; border:1px solid #bbb;
                font-size:12px; box-shadow:0 1px 4px rgba(0,0,0,0.12); max-width:240px; border-radius:8px;'>
      <div style='font-weight:600; margin-bottom:6px;'>{titulo_legenda}</div>
      {legend_lines}
      <div style='margin:2px 0;'>
        <span style='display:inline-block;width:20px;height:10px;background:#D3D3D3;margin-right:5px;border:1px solid #999'></span>Sem dados
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legenda_html))

elif tipo_mapa == "Pontos":
    for _, row in df_filtrado.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color="#00CED1",
            fill=True,
            fill_color="#00CED1",
            fill_opacity=0.6,
            popup=f"{row.get('Tipo', 'Imóvel')} — R$ {row['Preço']:,.2f}",
        ).add_to(m)

elif tipo_mapa == "Cluster":
    cluster = MarkerCluster(control=False).add_to(m)
    for _, row in df_filtrado.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row.get('Tipo', 'Imóvel')} — R$ {row['Preço']:,.2f}",
        ).add_to(cluster)

elif tipo_mapa == "Calor":
    HeatMap(df_filtrado[["latitude", "longitude"]].values, radius=15).add_to(m)

# =========================
# Exibir mapa
# =========================
st_folium(m, width=900, height=650, returned_objects=[], use_container_width=True)
