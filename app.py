import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium

# =========================
# Configuração de tiles Jawg Dark
# =========================
access_token = "SEU_TOKEN_JAWG_AQUI"  # substitua pelo seu token Jawg
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
# Paleta e faixas (fiel ao notebook)
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
# Aparência customizada
# =========================
st.markdown(
    """
    <style>
    body {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .banner {
        background-image: url('https://images.unsplash.com/photo-1508923567004-3a6b8004f3d3');
        background-size: cover;
        background-position: center;
        padding: 40px;
        border-radius: 8px;
        margin-bottom: 20px;
        text-align: center;
        color: white;
    }
    .banner h1 {
        font-size: 42px;
        font-weight: bold;
        color: #00CED1;
        text-shadow: 2px 2px 4px #000000;
    }
    .sub-metrics {
        display: flex;
        gap: 16px;
        margin: 8px 0 12px 0;
    }
    .sub-metric {
        background: #262730;
        border: 1px solid #3a3a3a;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 14px;
    }
    </style>
    <div class="banner">
        <h1>📈 Análise Imobiliária Maringá</h1>
        <p>Estudo estatístico e geográfico dos valores de imóveis</p>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# Interface Streamlit
# =========================
tipo_estatistica = st.selectbox(
    "Selecione a estatística:",
    [
        "Preço médio total",
        "Preço médio por m²",
        "Preço médio apartamentos",
        "Preço médio por m² apartamentos",
        "Preço médio casas",
        "Preço médio por m² casas",
        "Preço médio condomínios",
        "Preço médio por m² condomínios",
    ],
)

tipo_mapa = st.selectbox("Selecione o tipo de mapa:", ["Coroplético", "Pontos", "Cluster", "Calor"])

# =========================
# Filtros e coluna alvo
# =========================
if tipo_estatistica == "Preço médio total":
    df_filtrado = df.copy()
    coluna_valor = "Preço"
    estatistica_norm = "preco_medio_total"
elif tipo_estatistica == "Preço médio por m²":
    df_filtrado = df[df["valor_m2"].notnull()]
    coluna_valor = "valor_m2"
    estatistica_norm = "preco_medio_por_m2"
elif "apartamentos" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("apartamento", na=False)]
    if "m²" in tipo_estatistica:
        coluna_valor = "valor_m2"
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
        estatistica_norm = "preco_medio_por_m2_apartamentos"
    else:
        coluna_valor = "Preço"
        estatistica_norm = "preco_medio_apartamentos"
elif "casas" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("casa", na=False)]
    if "m²" in tipo_estatistica:
        coluna_valor = "valor_m2"
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
        estatistica_norm = "preco_medio_por_m2_casas"
    else:
        coluna_valor = "Preço"
        estatistica_norm = "preco_medio_casas"
elif "condomínios" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("condomínio", na=False)]
    if "m²" in tipo_estatistica:
        coluna_valor = "valor_m2"
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
        estatistica_norm = "preco_medio_por_m2_condominios"
    else:
        coluna_valor = "Preço"
        estatistica_norm = "preco_medio_condominios"

# =========================
# Exibir resumo estatístico
# =========================
num_imoveis = len(df_filtrado)
media_imoveis = df_filtrado[coluna_valor].mean()

st.markdown(
    f"""
    <div class="sub-metrics">
      <div class="sub-metric">🔢 Imóveis encontrados: <b>{num_imoveis}</b></div>
      <div class="sub-metric">📊 Média ({tipo_estatistica}): <b>R$ {media_imoveis:,.2f}</b></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# Mapa base (Jawg Dark)
# =========================
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=12, tiles=tiles_url, attr=attr, control_scale=True)

# =========================
# Escolher faixas corretas
# =========================
bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])

# =========================
# Mapa Coroplético com spatial join
# =========================
if tipo_mapa == "Coroplético":
    gdf_imoveis = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
        crs="EPSG:4326",
    )

    gdf_join = gpd.sjoin(gdf_imoveis, gdf_bairros[["geometry", "NOME"]], how="left", predicate="within")

    preco_bairro = gdf_join.groupby("NOME")[coluna_valor].agg(["mean", "min", "max"]).reset_index()
    preco_bairro.columns = ["Bairro", "media", "min", "max"]

    media_total = gdf_join[coluna_valor].mean()
    preco_bairro["variacao"] = ((preco_bairro["media"] - media_total) / media_total) * 100

    gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

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
            "color": "white",
            "weight": 0.5,
            "fillOpacity": 0.7,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NOME", "media", "min", "max", "variacao"],
            aliases=["Bairro", "Média", "Mínimo", "Máximo", "Variação (%)"],
            localize=True,
        ),
    ).add_to(m)

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
                background-color:white; padding:10px; border:1px solid gray;
                font-size:12px; box-shadow:0 1px 4px rgba(0,0,0,0.12); max-width:220px;'>
      <div style='font-weight:600; margin-bottom:6px;'>{titulo_legenda}</div>
      {legend_lines}
      <div style='margin:2px 0;'>
        <span style='display:inline-block;width:20px;height:10px;background:#D3D3D3;margin-right:5px;border:1px solid #999'></span>Sem dados
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legenda_html))

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
            popup=f"{row.get('Tipo', 'Imóvel')} — R$ {row['Preço']:,.2f}",
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
            popup=f"{row.get('Tipo', 'Imóvel')} — R$ {row['Preço']:,.2f}",
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
st_folium(m, width=900, height=650, returned_objects=[], use_container_width=True)
