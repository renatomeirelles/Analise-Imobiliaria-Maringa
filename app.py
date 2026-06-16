# =========================
# Imports e configuração inicial
# =========================
import streamlit as st
import pandas as pd
import geopandas as gpd
import folium
from streamlit_folium import st_folium
from folium.plugins import MarkerCluster, HeatMap
import matplotlib.pyplot as plt
import seaborn as sns
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
/* Layout geral */
.block-container {
    padding-top: 2.5rem;   /* espaço superior para não cobrir título */
    padding-bottom: 0.5rem;
    max-width: 1400px;
}

/* Estilo de texto */
label, .stSelectbox label {
    color: white !important;
    font-weight: 600;
}
h1, h2, h3 {
    color: white !important;
    margin-bottom: 0.6rem;
}

/* Sidebar escura (sem esconder ou fixar) */
[data-testid="stSidebar"] {
    background-color: #111 !important;
    color: white !important;
}
[data-testid="stSidebar"] * {
    color: white !important;   /* força texto branco dentro da sidebar */
}

/* Métricas na sidebar */
.sidebar-metric {
    color: white !important;
    font-size: 15px;
    font-weight: 500;
}

/* Esconde apenas a barra superior (toolbar) */
[data-testid="stToolbar"] {
    display: none !important;
}

/* Espaçamento compacto */
.stColumns { gap: 0.25rem !important; }

/* Título principal com fundo escuro */
.titulo-com-fundo {
    background-color: #111;
    padding: 1rem;
    border-radius: 6px;
    text-align: center;
    color: white;
    font-weight: 700;
    font-size: 28px;
    margin-top: 1rem;
    margin-bottom: 0.8rem;
}

/* Títulos Mapa e Gráfico com fundo escuro */
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

# =========================
# Título principal com fundo escuro
# =========================
st.markdown(
    '<div class="titulo-com-fundo">Análise Estatística e Espacial da Oferta de Imóveis Residenciais</div>',
    unsafe_allow_html=True
)

# =========================
# Títulos de Mapa e Gráfico com fundo escuro e alinhados
# =========================
st.markdown("""
<div class="titulo-duplo">
    <h3>Mapa</h3>
    <h3>Gráfico</h3>
</div>
""", unsafe_allow_html=True)

# =========================
# Sidebar com filtros (corrigido)
# =========================
st.sidebar.title("🎛️ Filtros")

# Filtro de estatística
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
    index=0,
    key="estatistica_selectbox"
)

# Filtro de mapa
tipo_mapa = st.sidebar.selectbox(
    "Selecione o tipo de mapa:",
    ["Coroplético", "Pontos", "Cluster", "Calor"],
    index=0,
    key="mapa_selectbox"
)

# Filtro de gráfico
grafico_tipo = st.sidebar.selectbox(
    "Selecione o gráfico:",
    ["Histograma", "Barras por bairro", "Boxplot por tipo"],
    index=0,
    key="grafico_selectbox"
)

# Exemplo de métricas para garantir que a sidebar sempre tenha conteúdo
st.sidebar.markdown("## 📊 Estatísticas")
st.sidebar.markdown("🔢 Imóveis encontrados: --")
st.sidebar.markdown("📈 Média: --")

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
# Configuração de tiles Jawg Dark
# =========================
access_token = "ZK6EgfhFT6px8F8MsRfOp2S5aUMPOvNr5CEEtLmjOYjHDC2MzgI0ZJ1cJjj0C98Y"
tiles_url = f"https://tile.jawg.io/jawg-dark/{{z}}/{{x}}/{{y}}{{r}}.png?access-token={access_token}"
attr = '<a href="https://jawg.io" target="_blank">&copy; <b>Jawg</b>Maps</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'

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
# Filtros (corrigido, agora em coluna à direita)
# =========================
col_map, col_chart, col_filters = st.columns([6, 6, 4], gap="small")

with col_filters:
    st.markdown("## 🎛️ Filtros")

    # Filtro de estatística
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

    # Filtro de mapa
    tipo_mapa = st.selectbox(
        "Selecione o tipo de mapa:",
        ["Coroplético", "Pontos", "Cluster", "Calor"],
        index=0,
        key="mapa_selectbox"
    )

    # Filtro de gráfico
    grafico_tipo = st.selectbox(
        "Selecione o gráfico:",
        ["Histograma", "Barras por bairro", "Boxplot por tipo"],
        index=0,
        key="grafico_selectbox"
    )

    # Métricas
    st.markdown("## 📊 Estatísticas")
    st.markdown(f'<div class="sidebar-metric">🔢 Imóveis encontrados: {num_imoveis}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-metric">📈 Média ({tipo_estatistica}): R$ {media_imoveis:,.2f}</div>', unsafe_allow_html=True)

# =========================
# Métricas na sidebar (texto branco)
# =========================
num_imoveis = len(df_filtrado)
media_imoveis = df_filtrado[coluna_valor].mean() if num_imoveis else 0

with st.sidebar:
    st.markdown("## 📊 Estatísticas")
    st.markdown(f'<div class="sidebar-metric">🔢 Imóveis encontrados: {num_imoveis}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sidebar-metric">📈 Média ({tipo_estatistica}): R$ {media_imoveis:,.2f}</div>', unsafe_allow_html=True)

# =========================
# Layout em duas colunas: mapa (maior) + gráfico (menor)
# =========================
col_map, col_chart = st.columns([7, 5], gap="small")

# Função para estilo dos gráficos
def style_axes(ax):
    ax.title.set_color("white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    for spine in ax.spines.values():
        spine.set_color("#bfbfbf")
    ax.grid(True, color="#444444", alpha=0.3)
    ax.tick_params(colors="white")

currency_formatter = FuncFormatter(lambda x, pos: f"R$ {x:,.0f}".replace(",", "."))

# --- Mapa (coluna esquerda) ---
with col_map:
    m = folium.Map(
        location=[-23.4205, -51.9331],
        zoom_start=12,
        tiles=tiles_url,
        attr=attr,
        control_scale=True
    )

    bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])

    if tipo_mapa == "Coroplético":
        gdf_imoveis = gpd.GeoDataFrame(
            df_filtrado,
            geometry=gpd.points_from_xy(df_filtrado["longitude"], df_filtrado["latitude"]),
            crs="EPSG:4326",
        )
        try:
            gdf_join = gpd.sjoin(
                gdf_imoveis,
                gdf_bairros[["geometry", "NOME"]],
                how="left",
                predicate="within"
            )
        except Exception:
            gdf_join = gpd.sjoin(
                gdf_imoveis,
                gdf_bairros[["geometry", "NOME"]],
                how="left",
                predicate="intersects"
            )

        preco_bairro = (
            gdf_join.groupby("NOME")[coluna_valor]
            .agg(["mean", "min", "max"])
            .reset_index()
        )
        preco_bairro.columns = ["Bairro", "media", "min", "max"]

        media_total = gdf_join[coluna_valor].mean()
        preco_bairro["variacao"] = ((preco_bairro["media"] - media_total) / media_total) * 100

        gdf_plot = gdf_bairros.merge(preco_bairro, left_on="NOME", right_on="Bairro", how="left")

        def cor_por_faixa(valor):
            if pd.isna(valor) or valor <= 0:
                return "#2b2b2b"
            for i in range(len(bins) - 1):
                if bins[i] <= valor <= bins[i + 1]:
                    return cores[i]
            return cores[-1]

        gdf_plot["cor"] = gdf_plot["media"].apply(cor_por_faixa)

        folium.GeoJson(
            gdf_plot,
            style_function=lambda feature: {
                "fillColor": feature["properties"]["cor"],
                "color": "#3a3a3a",
                "weight": 0.6,
                "fillOpacity": 0.75,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["NOME", "media", "min", "max", "variacao"],
                aliases=["Bairro", "Média", "Mínimo", "Máximo", "Variação (%)"],
                localize=True,
                style=(
                    "background-color: white; border: 1px solid #ccc; border-radius: 4px; "
                    "padding: 3px; font-size: 10px;"
                ),
            ),
        ).add_to(m)

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

    st_folium(m, height=480)


# --- Gráfico (coluna direita) ---
with col_chart:
    fig = None

    if grafico_tipo == "Histograma":
        fig, ax = plt.subplots(figsize=(5, 4.5))
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
            crs="EPSG:4326",
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

        fig, ax = plt.subplots(figsize=(5, 4.5))
        fig.patch.set_facecolor("#111111")
        ax.set_facecolor("#111111")
        media_bairro.plot(kind="barh", ax=ax, color="#00CED1")
        ax.set_title(f"Média de {tipo_estatistica} por bairro (top 15)", fontsize=11, pad=6)
        ax.set_xlabel("Valor médio (R$)")
        ax.xaxis.set_major_formatter(currency_formatter)
        ax.set_yticks(range(len(media_bairro.index)))
        ax.set_yticklabels(media_bairro.index)
        ax.invert_yaxis()
        style_axes(ax)
        fig.tight_layout()

    elif grafico_tipo == "Boxplot por tipo":
        fig, ax = plt.subplots(figsize=(5, 4.5))
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

