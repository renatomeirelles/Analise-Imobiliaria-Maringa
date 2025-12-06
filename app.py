# =========================
# Imports e configuração
# =========================
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
import base64
import matplotlib.pyplot as plt
import seaborn as sns

# Tema escuro para gráficos
plt.style.use("dark_background")
sns.set(style="darkgrid")

# =========================
# Função para aplicar imagem de fundo via base64
# =========================
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_background(png_file):
    bin_str = get_base64_of_bin_file(png_file)
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }}
        .block-container {{
            padding-top: 1rem;
            padding-bottom: 1rem;
            max-width: 1400px;
        }}
        label, .stSelectbox label {{
            color: white !important;
            font-weight: 600;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# Chama logo no início
set_background("maringa.jpg")

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

if "Tamanho(m²)" in df.columns and (df["Tamanho(m²)"] > 0).any():
    df["valor_m2"] = df["Preço"] / df["Tamanho(m²)"]

# =========================
# Paleta e faixas para mapa
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
# Banner customizado (novo título e subtítulo)
# =========================
st.markdown(
    """
    <div class="banner" style="background: rgba(0,0,0,0.55); padding: 28px; border-radius: 10px; margin-bottom: 14px; text-align: center; color: white;">
        <h1 style="font-size:36px; font-weight:800; color:#00CED1; text-shadow:2px 2px 4px #000000; margin:0;">
            Análise Imobiliária – Maringá‑PR
        </h1>
        <p style="margin:6px 0 0 0; font-size:15px; opacity:0.95;">
            Análise de dados estatísticos e espaciais da oferta de imóveis residenciais
        </p>
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

# =========================
# Filtros e coluna alvo
# =========================
estatistica_norm = "preco_medio_total"  # valor padrão

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
# Resumo estatístico
# =========================
num_imoveis = len(df_filtrado)
media_imoveis = df_filtrado[coluna_valor].mean()

st.markdown(
    f"""
    <div class="sub-metrics" style="display:flex; gap:16px; margin:10px 0 14px 0; flex-wrap:wrap;">
      <div class="sub-metric" style="background:#1e1e1e; color:#ffffff; border:1px solid #444; padding:10px 14px; border-radius:8px; font-size:14px;">
        🔢 Imóveis encontrados: <b>{num_imoveis}</b>
      </div>
      <div class="sub-metric" style="background:#1e1e1e; color:#ffffff; border:1px solid #444; padding:10px 14px; border-radius:8px; font-size:14px;">
        📊 Média ({tipo_estatistica}): <b>R$ {media_imoveis:,.2f}</b>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# Layout lado a lado com dropdowns separados
# =========================
col1, col2 = st.columns([1.2, 0.8])  # mapa maior, gráfico menor

with col1:
    tipo_mapa = st.selectbox("Selecione o tipo de mapa:", ["Coroplético", "Pontos", "Cluster", "Calor"])

with col2:
    grafico_tipo = st.selectbox("Selecione o gráfico:", ["Histograma", "Barras por bairro", "Boxplot por tipo"])

    # =========================
    # Gráfico selecionado
    # =========================
    fig = None
    if grafico_tipo == "Histograma":
        fig, ax = plt.subplots(figsize=(6,5))
        ax.hist(df_filtrado[coluna_valor], bins=30, color="#00CED1", edgecolor="white", density=False)
        ax.set_title(f"Distribuição de {tipo_estatistica}")
        ax.set_xlabel("Valor (R$)")
        ax.set_ylabel("Quantidade de imóveis")

    elif grafico_tipo == "Barras por bairro":
        gdf_imoveis = gpd.GeoDataFrame(
            df_filtrado,
            geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
            crs="EPSG:4326",
        )
        gdf_join = gpd.sjoin(gdf_imoveis, gdf_bairros[["geometry", "NOME"]], how="left", predicate="within")
        media_bairro = gdf_join.groupby("NOME")[coluna_valor].mean().sort_values(ascending=False).head(15)
        fig, ax = plt.subplots(figsize=(6,5))
        media_bairro.plot(kind="barh", ax=ax, color="#00CED1")
        ax.set_title(f"Média de {tipo_estatistica} por bairro (top 15)")
        ax.set_xlabel("Valor médio (R$)")
        ax.invert_yaxis()

    elif grafico_tipo == "Boxplot por tipo":
        fig, ax = plt.subplots(figsize=(6,5))
        sns.boxplot(data=df_filtrado, x="Tipo", y=coluna_valor, ax=ax, palette="Set2")
        ax.set_title(f"Distribuição de {tipo_estatistica} por tipo de imóvel")
        ax.set_xlabel("Tipo de imóvel")
        ax.set_ylabel("Valor (R$)")
        ax.tick_params(axis="x", rotation=30)

    if fig is not None:
        st.pyplot(fig, clear_figure=True)

# =========================
# Mapa base (Jawg Dark)
# =========================
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=12, tiles=tiles_url, attr=attr, control_scale=True)

# =========================
# Faixas fixas conforme métrica
# =========================
bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])
# =========================
# Mapas
# =========================
if tipo_mapa == "Coroplético":
    gdf_imoveis = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
        crs="EPSG:4326",
    )

    gdf_join = gpd.sjoin(
        gdf_imoveis,
        gdf_bairros[["geometry", "NOME"]],
        how="left",
        predicate="within",
    )

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
            "color": "#f0f0f0",
            "weight": 0.6,
            "fillOpacity": 0.75,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["NOME", "media", "min", "max", "variacao"],
            aliases=["Bairro", "Média", "Mínimo", "Máximo", "Variação (%)"],
            localize=True,
            style=(
                "background-color: white; "
                "border: 1px solid #ccc; "
                "border-radius: 4px; "
                "padding: 3px; "
                "font-size: 10px;"
            ),
        ),
    ).add_to(m)

    # Legenda lateral compacta
    titulo_legenda = "Faixas de preço por m² (R$)" if "m²" in tipo_estatistica else "Faixas de preço (R$)"
    legend_lines = "".join(
        [
            f"<div style='margin:2px 0;'>"
            f"<span style='display:inline-block;width:16px;height:10px;background:{cores[i]};"
            f"margin-right:5px;border:1px solid #999'></span>{bins[i]:,} – {bins[i+1]:,}"
            f"</div>"
            for i in range(len(bins) - 1)
        ]
    )
    legenda_html = f"""
    <div style='position: fixed; bottom: 8px; left: 8px; z-index:9999;
                background-color: rgba(255,255,255,0.9); padding:6px; border:1px solid #bbb;
                font-size:10px; box-shadow:0 1px 4px rgba(0,0,0,0.12); max-width:200px; border-radius:6px;'>
      <div style='font-weight:600; margin-bottom:4px;'>{titulo_legenda}</div>
      {legend_lines}
      <div style='margin:2px 0;'>
        <span style='display:inline-block;width:16px;height:10px;background:#D3D3D3;margin-right:5px;border:1px solid #999'></span>Sem dados
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legenda_html))

elif tipo_mapa == "Pontos":
    for _, row in df_filtrado.iterrows():
        valor_popup = row[coluna_valor]
        rotulo = "Preço por m²" if coluna_valor == "valor_m2" else "Preço"
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=3,
            color="#00CED1",
            fill=True,
            fill_color="#00CED1",
            fill_opacity=0.6,
            popup=f"{row.get('Tipo', 'Imóvel')} — {rotulo}: R$ {valor_popup:,.2f}",
        ).add_to(m)

elif tipo_mapa == "Cluster":
    cluster = MarkerCluster(control=False).add_to(m)
    for _, row in df_filtrado.iterrows():
        valor_popup = row[coluna_valor]
        rotulo = "Preço por m²" if coluna_valor == "valor_m2" else "Preço"
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row.get('Tipo', 'Imóvel')} — {rotulo}: R$ {valor_popup:,.2f}",
        ).add_to(cluster)

elif tipo_mapa == "Calor":
    HeatMap(df_filtrado[["latitude", "longitude"]].values, radius=15).add_to(m)

# =========================
# Exibir mapa (na coluna da esquerda)
# =========================
with col1:
    st_folium(m, width=700, height=550, returned_objects=[], use_container_width=True)
