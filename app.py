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
# Banner customizado
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
# Sidebar com seletores
# =========================
tipo_estatistica = st.sidebar.selectbox(
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

tipo_mapa = st.sidebar.selectbox("Selecione o tipo de mapa:", ["Coroplético", "Pontos", "Cluster", "Calor"])
grafico_tipo = st.sidebar.selectbox("Selecione o gráfico:", ["Histograma", "Barras por bairro", "Boxplot por tipo"])

# =========================
# Filtros e coluna alvo
# =========================
estatistica_norm = "preco_medio_total"
...
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
# Mapa em cima
# =========================
m = folium.Map(location=[-23.4205, -51.9331], zoom_start=12,
               tiles=tiles_url, attr=attr, control_scale=True)

# --- mesma lógica dos mapas que você já tem (Coroplético, Pontos, Cluster, Calor) ---
# copie aqui o bloco dos mapas sem alteração

st_folium(m, width=700, height=500, returned_objects=[], use_container_width=True)

# =========================
# Gráfico embaixo
# =========================
fig = None
if grafico_tipo == "Histograma":
    fig, ax = plt.subplots(figsize=(6,5))
    ax.hist(df_filtrado[coluna_valor], bins=30, color="#00CED1", edgecolor="white")
    ax.set_title(f"Distribuição de {tipo_estatistica}")
    ax.set_xlabel("Valor (R$)")
    ax.set_ylabel("Quantidade de imóveis")

elif grafico_tipo == "Barras por bairro":
    gdf_imoveis = gpd.GeoDataFrame(
        df_filtrado,
        geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
        crs="EPSG:4326",
    )
    gdf_join = gpd.sjoin(gdf_imoveis, gdf_bairros[["geometry", "NOME"]],
                         how="left", predicate="within")
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
