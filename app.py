# =========================
# Imports e configuração inicial
# =========================
import json

import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import pydeck as pdk
import seaborn as sns
import streamlit as st
from matplotlib.ticker import FuncFormatter
from pathlib import Path

# Configuração da página
st.set_page_config(
    page_title="Análise Estatística e Espacial",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tema escuro para gráficos
plt.style.use("dark_background")
sns.set(style="darkgrid")

# =========================
# CSS otimizado e seguro
# =========================
st.markdown("""
<style>
.block-container {
    padding-top: 2.5rem;
    padding-bottom: 0.5rem;
    max-width: 1400px;
}
label, .stSelectbox label {
    color: white !important;
    font-weight: 600;
}
h1, h2, h3 {
    color: white !important;
    margin-bottom: 0.6rem;
}
.sidebar-metric {
    color: white !important;
    font-size: 15px;
    font-weight: 500;
}
[data-testid="stToolbar"] {
    display: none !important;
}
.stColumns { gap: 0.25rem !important; }
.titulo-com-fundo {
    background-color: #111;
    padding: 1rem 1rem;
    border-radius: 6px;
    text-align: center;
    color: white;
    font-weight: 700;
    font-size: 28px;
    margin-top: 1rem;
    margin-bottom: 0.8rem;
}
.titulo-duplo {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
}
.titulo-duplo h3 {
    background-color: #111;
    color: white;
    font-size: 18px;
    font-weight: 600;
    padding: 0.4rem 0.8rem;
    border-radius: 6px;
    margin: 0;
}
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="titulo-com-fundo">Análise Estatística e Espacial da Oferta de Imóveis Residenciais</div>',
    unsafe_allow_html=True
)

st.markdown("""
<div class="titulo-duplo">
    <h3>Mapa</h3>
    <h3>Gráfico</h3>
</div>
""", unsafe_allow_html=True)

# =========================
# Filtros
# =========================
col_map, col_chart, col_filters = st.columns([6, 6, 4], gap="small")

with col_filters:
    st.markdown("## 🎛️ Filtros")

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
        index=0,
        key="estatistica_selectbox"
    )

    tipo_mapa = st.selectbox(
        "Selecione o tipo de mapa:",
        ["Coroplético", "Pontos", "Densidade 3D (hexbin)", "Calor"],
        index=0,
        key="mapa_selectbox"
    )

    grafico_tipo = st.selectbox(
        "Selecione o gráfico:",
        ["Histograma", "Barras por bairro", "Boxplot por tipo"],
        index=0,
        key="grafico_selectbox"
    )

    st.markdown("## 📊 Estatísticas")
    st.markdown('<div class="sidebar-metric">🔢 Imóveis encontrados: --</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-metric">📈 Média: --</div>', unsafe_allow_html=True)

# =========================
# Funções de carga de dados
# =========================
@st.cache_data(show_spinner=True)
def load_df(path: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(path)
        df.columns = df.columns.str.strip()
        df = df.dropna(subset=["latitude", "longitude"])
        if "Tamanho(m²)" in df.columns and (df["Tamanho(m²)"] > 0).any():
            df["valor_m2"] = df["Preço"] / df["Tamanho(m²)"]
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

@st.cache_data(show_spinner=True)
def load_bairros(path: str) -> gpd.GeoDataFrame:
    try:
        gdf = gpd.read_file(path)
        gdf.columns = gdf.columns.str.strip()
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar shapefile: {e}")
        return gpd.GeoDataFrame()

# =========================
# Carregar dados com proteção
# =========================
df_path = "data/imoveis_georreferenciados_novembro.xlsx"
shp_path = "data/municipio_completo.shp"

data_ok = True
if not Path(df_path).exists():
    st.error(f"Arquivo de dados não encontrado: {df_path}")
    data_ok = False

shp_components = [shp_path.replace(".shp", ext) for ext in [".shp", ".dbf", ".shx", ".prj"]]
if not all(Path(p).exists() for p in shp_components):
    st.error("Shapefile incompleto. Necessário .shp, .dbf, .shx e .prj na pasta data/.")
    data_ok = False

try:
    if data_ok:
        df = load_df(df_path)
        gdf_bairros = load_bairros(shp_path)
except Exception as e:
    st.exception(e)
    data_ok = False

if not data_ok:
    st.info("Ajuste os arquivos e recarregue a página.")
    st.stop()

# =========================
# Paleta e faixas para o mapa coroplético
# =========================
cores_hex = ['#FF0000', '#FFA500', '#FFFF00', '#00FF00', '#00CED1',
             '#0000FF', '#8A2BE2', '#FF69B4', '#A52A2A']

def hex_para_rgba(hex_color, alpha=180):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return [r, g, b, alpha]

cores_rgba = [hex_para_rgba(c) for c in cores_hex]

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
# Filtros e coluna alvo
# =========================
estatistica_norm = "preco_medio_total"

if tipo_estatistica == "Preço médio total":
    df_filtrado = df.copy()
    coluna_valor = "Preço"
    estatistica_norm = "preco_medio_total"

elif tipo_estatistica == "Preço médio por m²":
    if "valor_m2" not in df.columns:
        st.warning("Não foi possível calcular valor por m². Verifique 'Tamanho(m²)'.")
        df_filtrado = df.copy()
        coluna_valor = "Preço"
        estatistica_norm = "preco_medio_total"
    else:
        df_filtrado = df[df["valor_m2"].notnull()]
        coluna_valor = "valor_m2"
        estatistica_norm = "preco_medio_por_m2"

elif "apartamentos" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("apartamento", na=False)]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"
    if coluna_valor == "valor_m2":
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
    estatistica_norm = "preco_medio_por_m2_apartamentos" if "m²" in tipo_estatistica else "preco_medio_apartamentos"

elif "casas" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("casa", na=False)]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"
    if coluna_valor == "valor_m2":
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
    estatistica_norm = "preco_medio_por_m2_casas" if "m²" in tipo_estatistica else "preco_medio_casas"

elif "condomínios" in tipo_estatistica.lower():
    df_filtrado = df[df["Tipo"].str.lower().str.contains("condomínio", na=False)]
    coluna_valor = "valor_m2" if "m²" in tipo_estatistica else "Preço"
    if coluna_valor == "valor_m2":
        df_filtrado = df_filtrado[df_filtrado["valor_m2"].notnull()]
    estatistica_norm = "preco_medio_por_m2_condominios" if "m²" in tipo_estatistica else "preco_medio_condominios"

# Coluna auxiliar com nome fixo, usada nos tooltips do pydeck
df_filtrado = df_filtrado.copy()
df_filtrado["valor_tooltip"] = df_filtrado[coluna_valor]

# =========================
# Métricas
# =========================
num_imoveis = len(df_filtrado)
media_imoveis = df_filtrado[coluna_valor].mean() if num_imoveis else 0

with col_filters:
    st.markdown("## 📊 Estatísticas")
    st.markdown(f'<div class="sidebar-metric">🔢 Imóveis encontrados: {num_imoveis}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-metric">📈 Média ({tipo_estatistica}): R$ {media_imoveis:,.2f}</div>', unsafe_allow_html=True)

# =========================
# Auxiliares de gráfico (matplotlib)
# =========================
def style_axes(ax):
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    for spine in ax.spines.values():
        spine.set_color("#bfbfbf")
    ax.grid(True, color="#444444", alpha=0.3)
    ax.tick_params(colors="white")

currency_formatter = FuncFormatter(lambda x, pos: f"R$ {x:,.0f}".replace(",", "."))

col_map, col_chart = st.columns([7, 5], gap="small")

# =========================
# Mapa (pydeck / deck.gl)
# =========================
with col_map:
    st.markdown("### 🗺️ Mapa")

    view_state = pdk.ViewState(
        latitude=-23.4205,
        longitude=-51.9331,
        zoom=12,
        pitch=45 if tipo_mapa == "Densidade 3D (hexbin)" else 0,
    )

    bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])
    layers = []
    tooltip = None

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
            predicate="within"
        )
        preco_bairro = gdf_join.groupby("NOME")[coluna_valor].mean().reset_index()
        preco_bairro.columns = ["Bairro", "media"]

        gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

        def cor_por_faixa(valor):
            if pd.isna(valor) or valor <= 0:
                return [43, 43, 43, 120]
            for i in range(len(bins) - 1):
                if bins[i] <= valor <= bins[i + 1]:
                    return cores_rgba[i]
            return cores_rgba[-1]

        gdf_plot["fill_color"] = gdf_plot["media"].apply(cor_por_faixa)
        gdf_plot["media_fmt"] = gdf_plot["media"].apply(
            lambda v: f"R$ {v:,.2f}" if pd.notna(v) else "sem dados"
        )
        geojson = json.loads(gdf_plot[["geometry", "NOME", "media_fmt", "fill_color"]].to_json())

        layers.append(
            pdk.Layer(
                "GeoJsonLayer",
                geojson,
                stroked=True,
                filled=True,
                get_fill_color="properties.fill_color",
                get_line_color=[58, 58, 58],
                line_width_min_pixels=1,
                pickable=True,
            )
        )
        tooltip = {"html": "<b>{NOME}</b><br/>Média: {media_fmt}"}

    elif tipo_mapa == "Pontos":
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                df_filtrado,
                get_position=["longitude", "latitude"],
                get_radius=35,
                get_fill_color=[0, 206, 209, 160],
                pickable=True,
            )
        )
        tooltip = {"html": "{Tipo} — R$ {valor_tooltip}"}

    elif tipo_mapa == "Densidade 3D (hexbin)":
        # Equivalente ao "Cluster" antigo, mas com visual deck.gl:
        # agrega os pontos em hexágonos e usa altura/cor para densidade.
        layers.append(
            pdk.Layer(
                "HexagonLayer",
                df_filtrado,
                get_position=["longitude", "latitude"],
                radius=150,
                elevation_scale=15,
                elevation_range=[0, 1500],
                extruded=True,
                coverage=1,
                pickable=True,
            )
        )
        tooltip = {"html": "Imóveis nesta região: {elevationValue}"}

    elif tipo_mapa == "Calor":
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                df_filtrado,
                get_position=["longitude", "latitude"],
                get_weight="valor_tooltip",
                radius_pixels=40,
            )
        )

    deck = pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        map_provider="carto",
        map_style="dark",
        tooltip=tooltip,
    )
    st.pydeck_chart(deck, height=480)

# =========================
# Gráfico (matplotlib)
# =========================
with col_chart:
    st.markdown("### 📉 Gráfico")
    fig = None

    if grafico_tipo == "Histograma":
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor("#111111")
        ax.set_facecolor("#111111")
        ax.hist(df_filtrado[coluna_valor], bins=30, color="#00CED1", edgecolor="white")
        ax.set_title(f"Distribuição de {tipo_estatistica}", fontsize=11, pad=6)
        ax.set_xlabel("Valor (R$)")
        ax.set_ylabel("Quantidade de imóveis")
        ax.xaxis.set_major_formatter(currency_formatter)
        style_axes(ax)
        fig.tight_layout()

    elif grafico_tipo == "Barras por bairro":
        gdf_imoveis = gpd.GeoDataFrame(
            df_filtrado,
            geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
            crs="EPSG:4326"
        )
        gdf_join = gpd.sjoin(
            gdf_imoveis,
            gdf_bairros[["geometry", "NOME"]],
            how="left",
            predicate="within"
        )
        media_bairro = (
            gdf_join.groupby("NOME")[coluna_valor]
            .mean()
            .sort_values(ascending=False)
            .head(15)
        )
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor("#111111")
        ax.set_facecolor("#111111")
        media_bairro.plot(kind="barh", ax=ax, color="#00CED1")
        ax.set_title(f"Média de {tipo_estatistica} por bairro (top 15)", fontsize=11, pad=6)
        ax.set_xlabel("Valor médio (R$)")
        ax.xaxis.set_major_formatter(currency_formatter)
        ax.invert_yaxis()
        style_axes(ax)
        fig.tight_layout()

    elif grafico_tipo == "Boxplot por tipo":
        fig, ax = plt.subplots(figsize=(6, 4))
        fig.patch.set_facecolor("#111111")
        ax.set_facecolor("#111111")
        sns.boxplot(data=df_filtrado, x="Tipo", y=coluna_valor, ax=ax, palette="Set2")
        ax.set_title(f"Distribuição de {tipo_estatistica} por tipo de imóvel", fontsize=11, pad=6)
        ax.set_xlabel("Tipo de imóvel")
        ax.set_ylabel("Valor (R$)")
        ax.tick_params(axis="x", rotation=30)
        ax.yaxis.set_major_formatter(currency_formatter)
        style_axes(ax)
        fig.tight_layout()

    if fig is not None:
        st.pyplot(fig, clear_figure=True)
