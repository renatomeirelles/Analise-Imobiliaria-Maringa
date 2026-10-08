# =========================
# BLOCO 1 — Imports e configuração inicial
# =========================
import json
import warnings
from datetime import datetime
from html import escape
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import h3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st
from statsmodels.tsa.arima.model import ARIMA

# Obs.: osmnx e shapely.box são importados só dentro da função que busca
# edifícios ao vivo no OpenStreetMap (BLOCO 8). Assim o app inicia mais rápido.

warnings.filterwarnings("ignore")

# Configuração da página
st.set_page_config(
    page_title="Plataforma de Inteligência Territorial",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# True  = no celular a barra de filtros fica fixa embaixo da tela (estilo app)
# False = a barra de filtros fica no topo, também no celular
BARRA_FIXA_NO_CELULAR = True


# =========================
# BLOCO 1B — Funções auxiliares de formatação
# =========================
def _num_br(v, casas=2):
    """Número no padrão brasileiro: 1.234.567,89"""
    s = f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_brl(v, casas=2, sufixo=""):
    if v is None or pd.isna(v):
        return "sem dados"
    return f"R$ {_num_br(v, casas)}{sufixo}"


def fmt_int(v):
    if v is None or pd.isna(v):
        return "—"
    return _num_br(v, 0)


def fmt_pct(v):
    if v is None or pd.isna(v):
        return "sem dados"
    seta = "▲ " if v > 0 else ("▼ " if v < 0 else "")
    return f"{seta}{_num_br(abs(v), 1)}%"


# =========================
# BLOCO 2 — CSS e título
# =========================
CSS_BASE = """
.block-container {
    padding-top: 2.5rem;
    padding-bottom: 0.5rem;
    max-width: 1500px;
}
label, .stSelectbox label {
    color: white !important;
    font-weight: 600;
}
h1, h2, h3 {
    color: white !important;
    margin-bottom: 0.6rem;
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
    font-size: clamp(18px, 4.2vw, 28px);
    margin-top: 1rem;
    margin-bottom: 0.8rem;
}
.stat-pequena {
    color: white !important;
    font-size: 13px;
    font-weight: 500;
    line-height: 1.4;
}
.stat-pequena b {
    font-size: 16px;
}

/* Barra de filtros (botões que abrem as opções) */
.st-key-barra_filtros {
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 0.4rem 0.5rem;
    margin-bottom: 0.6rem;
}
.st-key-barra_filtros [data-testid="stPopover"],
.st-key-barra_filtros [data-testid="stPopover"] > div {
    width: 100%;
}
.st-key-barra_filtros button {
    width: 100%;
    font-weight: 600;
}

/* Ajustes gerais para celular */
@media (max-width: 768px) {
    .block-container {
        padding-left: 0.7rem;
        padding-right: 0.7rem;
        padding-top: 1.5rem;
    }
}
"""

# No celular: a barra de filtros vira uma barra fixa na parte de baixo da tela,
# com os botões lado a lado (o Streamlit empilharia as colunas por padrão).
CSS_BARRA_FIXA = """
@media (max-width: 768px) {
    .st-key-barra_filtros {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        z-index: 100;
        margin: 0;
        border-radius: 14px 14px 0 0;
        border-bottom: none;
        padding: 0.45rem 0.6rem calc(0.45rem + env(safe-area-inset-bottom, 0px));
        box-shadow: 0 -4px 14px rgba(0, 0, 0, 0.5);
    }
    .st-key-barra_filtros [data-testid="stHorizontalBlock"] {
        flex-direction: row !important;
        flex-wrap: nowrap !important;
        gap: 0.4rem !important;
    }
    .st-key-barra_filtros [data-testid="stColumn"],
    .st-key-barra_filtros [data-testid="column"] {
        min-width: 0 !important;
        width: auto !important;
        flex: 1 1 0 !important;
    }
    .st-key-barra_filtros button {
        font-size: 12px;
        padding: 0.35rem 0.2rem;
    }
    .block-container {
        padding-bottom: 6rem !important;
    }
}
"""

st.markdown(
    "<style>" + CSS_BASE + (CSS_BARRA_FIXA if BARRA_FIXA_NO_CELULAR else "") + "</style>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="titulo-com-fundo">Plataforma de Inteligência Territorial</div>',
    unsafe_allow_html=True
)

# =========================
# BLOCO 3 — Barra de filtros e layout (mapa | gráfico)
# No computador: barra no topo. No celular: barra fixa embaixo da tela.
# =========================
ESTATISTICAS = [
    "Preço médio total",
    "Preço médio por m²",
    "Preço médio apartamentos",
    "Preço médio por m² apartamentos",
    "Preço médio casas",
    "Preço médio por m² casas",
    "Preço médio condomínios",
    "Preço médio por m² condomínios",
]
TIPOS_MAPA = ["Coroplético", "Pontos", "Densidade 3D (hexbin)", "Calor", "Edifícios 3D (OSM)"]
TIPOS_GRAFICO = ["Histograma", "Barras por bairro", "Boxplot por tipo"]

with st.container(key="barra_filtros"):
    bc1, bc2, bc3 = st.columns(3, gap="small")

    with bc1:
        with st.popover("📊 Estatística"):
            tipo_estatistica = st.radio(
                "Selecione a estatística:", ESTATISTICAS, index=0, key="estatistica_radio"
            )

    with bc2:
        with st.popover("🗺️ Mapa"):
            tipo_mapa = st.radio(
                "Selecione o tipo de mapa:", TIPOS_MAPA, index=0, key="mapa_radio"
            )
            metrica_hexbin = st.radio(
                "No hexbin 3D, medir por:",
                ["Quantidade de imóveis", "Valor médio"],
                index=0,
                key="metrica_hexbin_radio",
                help="Só se aplica quando o tipo de mapa é 'Densidade 3D (hexbin)'.",
            )

    with bc3:
        with st.popover("📉 Gráfico"):
            grafico_tipo = st.radio(
                "Selecione o gráfico:", TIPOS_GRAFICO, index=0, key="grafico_radio"
            )

col_map, col_chart = st.columns([8, 4], gap="small")

# =========================
# BLOCO 4 — Funções de carga de dados
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
# BLOCO 5 — Carregar dados com proteção
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
# BLOCO 6 — Paleta e faixas para o mapa coroplético
# =========================
cores_hex = ['#eff8ff', '#a9d3f5', '#5ba3e0', '#2477c2', '#0d54a0',
             '#0a3d7a', '#072a56', '#041a38', '#00060f']

def hex_para_rgba(hex_color, alpha=180):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return [r, g, b, alpha]

cores_rgba = [hex_para_rgba(c) for c in cores_hex]

cor_range_teal = [
    [8, 48, 51],
    [10, 80, 85],
    [0, 130, 132],
    [0, 170, 172],
    [0, 206, 209],
    [140, 240, 240],
]

def valor_para_cor_teal(valor, vmin, vmax, alpha=200):
    if pd.isna(valor):
        return [43, 43, 43, 120]
    if vmax == vmin:
        t = 0.0
    else:
        t = (valor - vmin) / (vmax - vmin)
    t = max(0.0, min(1.0, t))
    idx = min(int(t * (len(cor_range_teal) - 1)), len(cor_range_teal) - 1)
    return cor_range_teal[idx] + [alpha]

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
# BLOCO 7 — Filtros e coluna alvo
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

# Coluna auxiliar com nome fixo, usada nos mapas (tooltip/cartão de detalhes)
df_filtrado = df_filtrado.copy()
df_filtrado["valor_tooltip"] = df_filtrado[coluna_valor]
sufixo_unid = "/m²" if coluna_valor == "valor_m2" else ""

# =========================
# BLOCO 7B — Funções de cálculo (com cache)
# O join espacial (imóvel → bairro) e a montagem do GeoJSON eram refeitos a
# cada clique. Agora ficam em cache: só recalculam quando a estatística muda.
# =========================
def cor_por_faixa(valor, bins):
    if pd.isna(valor) or valor <= 0:
        return [43, 43, 43, 120]
    for i in range(len(bins) - 1):
        if bins[i] <= valor <= bins[i + 1]:
            return cores_rgba[i]
    return cores_rgba[-1]


@st.cache_data(show_spinner=False)
def agregar_por_bairro(df_in, coluna, _gdf_bairros):
    """Média, mínimo, máximo, quantidade e variação vs. município, por bairro."""
    gdf_imoveis = gpd.GeoDataFrame(
        df_in,
        geometry=gpd.points_from_xy(df_in["longitude"], df_in["latitude"]),
        crs="EPSG:4326",
    )
    gdf_join = gpd.sjoin(
        gdf_imoveis,
        _gdf_bairros[["geometry", "NOME"]],
        how="left",
        predicate="within",
    )
    stats = gdf_join.groupby("NOME")[coluna].agg(
        qtd="count", media="mean", minimo="min", maximo="max"
    ).reset_index()
    media_municipio = df_in[coluna].mean()
    stats["variacao"] = ((stats["media"] - media_municipio) / media_municipio) * 100
    return stats.round(2)


CAMPOS_TOOLTIP_COROPLETICO = ("NOME", "media_fmt", "minimo_fmt", "maximo_fmt", "variacao_fmt", "qtd_fmt")


@st.cache_data(show_spinner=False)
def montar_geojson_coropletico(stats, _gdf_bairros, bins, sufixo):
    gdf_plot = _gdf_bairros[["geometry", "NOME"]].merge(stats, on="NOME", how="left")
    gdf_plot["fill_color"] = gdf_plot["media"].apply(lambda v: cor_por_faixa(v, bins))
    gdf_plot["media_fmt"] = gdf_plot["media"].apply(lambda v: fmt_brl(v, sufixo=sufixo))
    gdf_plot["minimo_fmt"] = gdf_plot["minimo"].apply(lambda v: fmt_brl(v, sufixo=sufixo))
    gdf_plot["maximo_fmt"] = gdf_plot["maximo"].apply(lambda v: fmt_brl(v, sufixo=sufixo))
    gdf_plot["variacao_fmt"] = gdf_plot["variacao"].apply(fmt_pct)
    gdf_plot["qtd_fmt"] = gdf_plot["qtd"].apply(fmt_int)
    geojson = json.loads(
        gdf_plot[[
            "geometry", "NOME", "media_fmt", "minimo_fmt", "maximo_fmt",
            "variacao_fmt", "qtd_fmt", "fill_color"
        ]].to_json()
    )
    # Copia os campos do tooltip para o nível da feature também. Assim o balão
    # funciona qualquer que seja a forma como a versão do Streamlit/pydeck lê os
    # campos (direto ou dentro de "properties").
    for feat in geojson["features"]:
        for campo in CAMPOS_TOOLTIP_COROPLETICO:
            feat[campo] = feat["properties"].get(campo)
    return geojson


# =========================
# BLOCO 8 — Mapa (pydeck / deck.gl) com tooltip
# =========================
with col_map:
    st.markdown("### 🗺️ Mapa")
    st.caption(f"📊 {tipo_estatistica}  ·  🗺️ {tipo_mapa}")

    view_state = pdk.ViewState(
        latitude=-23.4205,
        longitude=-51.9331,
        zoom=12,
        pitch=45 if tipo_mapa in ("Densidade 3D (hexbin)", "Edifícios 3D (OSM)") else 0,
    )

    bins = faixas_dict.get(estatistica_norm, faixas_base['preco'])
    layers = []
    tooltip = None

    if tipo_mapa == "Coroplético":
        df_stats = agregar_por_bairro(
            df_filtrado[["latitude", "longitude", coluna_valor]], coluna_valor, gdf_bairros
        )
        geojson = montar_geojson_coropletico(df_stats, gdf_bairros, tuple(bins), sufixo_unid)
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
                auto_highlight=True,
            )
        )
        # Tooltip do mapa (balão ao passar o mouse / tocar no bairro)
        tooltip = {
            "html": (
                "<b>{NOME}</b><br/>"
                "Imóveis: {qtd_fmt}<br/>"
                "Média: {media_fmt}<br/>"
                "Mínimo: {minimo_fmt}<br/>"
                "Máximo: {maximo_fmt}<br/>"
                "Variação vs. município: {variacao_fmt}"
            ),
            "style": {"backgroundColor": "#111111", "color": "white", "fontSize": "13px"},
        }

    elif tipo_mapa == "Pontos":
        # Envia ao navegador só as colunas necessárias (antes ia a planilha inteira)
        pontos = df_filtrado[["longitude", "latitude", "Tipo", "valor_tooltip"]].copy()
        pontos["valor_fmt"] = pontos["valor_tooltip"].apply(lambda v: fmt_brl(v, sufixo=sufixo_unid))
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                pontos,
                get_position=["longitude", "latitude"],
                get_radius=35,
                get_fill_color=[0, 206, 209, 160],
                pickable=True,
            )
        )
        tooltip = {
            "html": "{Tipo} — {valor_fmt}",
            "style": {"backgroundColor": "#111111", "color": "white", "fontSize": "13px"},
        }

    elif tipo_mapa == "Densidade 3D (hexbin)":
        # Agregação própria em células H3 (em vez da agregação nativa do
        # deck.gl, que se mostrou pouco confiável nesse ambiente). Isso
        # garante o MESMO visual de "barra" tanto pra quantidade quanto
        # pro valor médio.
        H3_RESOLUCAO = 9  # hexágonos maiores/mais visíveis que antes

        dados_hex = df_filtrado[["latitude", "longitude", "valor_tooltip"]].dropna().copy()
        dados_hex["hex"] = [
            h3.latlng_to_cell(lat, lon, H3_RESOLUCAO)
            for lat, lon in zip(dados_hex["latitude"], dados_hex["longitude"])
        ]

        agg_hex = dados_hex.groupby("hex").agg(
            qtd=("valor_tooltip", "size"),
            media=("valor_tooltip", "mean"),
        ).reset_index()

        coluna_metrica = "qtd" if metrica_hexbin == "Quantidade de imóveis" else "media"
        vmin_hex = agg_hex[coluna_metrica].min()
        vmax_hex = agg_hex[coluna_metrica].max()

        if pd.notna(vmax_hex) and vmax_hex > vmin_hex:
            agg_hex["elevation"] = (agg_hex[coluna_metrica] - vmin_hex) / (vmax_hex - vmin_hex) * 3000 + 80
        else:
            agg_hex["elevation"] = 400

        agg_hex["fill_color"] = agg_hex[coluna_metrica].apply(
            lambda v: valor_para_cor_teal(v, vmin_hex, vmax_hex)
        )

        if metrica_hexbin == "Quantidade de imóveis":
            agg_hex["label"] = agg_hex["qtd"].apply(lambda v: f"{fmt_int(v)} imóveis")
        else:
            agg_hex["label"] = agg_hex["media"].apply(lambda v: fmt_brl(v, sufixo=sufixo_unid))
        layers.append(
            pdk.Layer(
                "H3HexagonLayer",
                agg_hex,
                get_hexagon="hex",
                get_fill_color="fill_color",
                get_elevation="elevation",
                elevation_scale=2,
                extruded=True,
                pickable=True,
            )
        )
        tooltip = {
            "html": "{label}",
            "style": {"backgroundColor": "#111111", "color": "white", "fontSize": "13px"},
        }

    elif tipo_mapa == "Edifícios 3D (OSM)":
        # Contornos de prédios/casas extrudados por altura estimada (tag
        # 'height' quando existe; senão, andares x 3m; senão, um padrão).
        # Sem Blender — mesma técnica dos showcases oficiais do deck.gl.
        #
        # Lê primeiro de um arquivo local (data/edificios_maringa.geojson),
        # gerado uma vez com o script baixar_predios.py. Isso evita depender
        # de uma chamada ao vivo pro Overpass API dentro do servidor
        # hospedado — que se mostrou instável/bloqueada nesse ambiente.
        EDIFICIOS_LOCAL_PATH = Path("data/edificios_maringa.geojson")

        def estimar_altura(row):
            altura_tag = row.get("height")
            if pd.notna(altura_tag):
                try:
                    return float(str(altura_tag).lower().replace("m", "").strip())
                except ValueError:
                    pass
            andares = row.get("building:levels")
            if pd.notna(andares):
                try:
                    return float(andares) * 3.0
                except ValueError:
                    pass
            return 9.0  # padrão: ~3 andares, quando não há dado na base

        @st.cache_data(show_spinner="Carregando edifícios...")
        def carregar_predios_local(path_str):
            gdf = gpd.read_file(path_str)
            if "altura" not in gdf.columns:
                gdf["altura"] = gdf.apply(estimar_altura, axis=1)
            return gdf[["geometry", "altura"]].reset_index(drop=True)

        @st.cache_data(show_spinner="Buscando edifícios no OpenStreetMap (só na primeira vez)...")
        def carregar_predios_osm_ao_vivo(_gdf_bairros_bounds):
            # Imports aqui dentro: osmnx é pesado e só é preciso neste caminho.
            # Se quiser usar a busca ao vivo, adicione "osmnx" ao requirements.txt.
            import osmnx as ox
            from shapely.geometry import box

            minx, miny, maxx, maxy = _gdf_bairros_bounds
            area = box(minx, miny, maxx, maxy)
            gdf_predios = ox.features_from_polygon(area, tags={"building": True})
            gdf_predios = gdf_predios[gdf_predios.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
            gdf_predios["altura"] = gdf_predios.apply(estimar_altura, axis=1)
            return gdf_predios[["geometry", "altura"]].reset_index(drop=True)

        try:
            if EDIFICIOS_LOCAL_PATH.exists():
                gdf_predios = carregar_predios_local(str(EDIFICIOS_LOCAL_PATH))
            else:
                st.caption(
                    "⚠️ Arquivo local de edifícios não encontrado — tentando buscar ao vivo no "
                    "OpenStreetMap (pode falhar ou demorar). Veja como gerar o arquivo local "
                    "com o script baixar_predios.py."
                )
                bounds = tuple(gdf_bairros.total_bounds)
                gdf_predios = carregar_predios_osm_ao_vivo(bounds)

            if gdf_predios.empty:
                st.info("Nenhum contorno de edifício encontrado para esta área.")
            else:
                vmin_h, vmax_h = gdf_predios["altura"].min(), gdf_predios["altura"].max()
                gdf_predios["fill_color"] = gdf_predios["altura"].apply(
                    lambda v: valor_para_cor_teal(v, vmin_h, vmax_h)
                )
                gdf_predios["altura_fmt"] = gdf_predios["altura"].apply(lambda v: f"{v:.0f} m (estimado)")

                geojson_predios = json.loads(
                    gdf_predios[["geometry", "altura", "altura_fmt", "fill_color"]].to_json()
                )
                for feat in geojson_predios["features"]:
                    feat["altura_fmt"] = feat["properties"].get("altura_fmt")
                layers.append(
                    pdk.Layer(
                        "GeoJsonLayer",
                        geojson_predios,
                        stroked=False,
                        filled=True,
                        extruded=True,
                        get_elevation="properties.altura",
                        get_fill_color="properties.fill_color",
                        pickable=True,
                    )
                )
                tooltip = {
                    "html": "Altura estimada: {altura_fmt}",
                    "style": {"backgroundColor": "#111111", "color": "white", "fontSize": "13px"},
                }
        except Exception as e:
            st.warning(
                "Não foi possível carregar os edifícios do OpenStreetMap agora "
                f"(a base pode estar indisponível ou a área é grande demais): {e}"
            )

    elif tipo_mapa == "Calor":
        dados_calor = df_filtrado[["longitude", "latitude", "valor_tooltip"]].dropna()
        layers.append(
            pdk.Layer(
                "HeatmapLayer",
                dados_calor,
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

    # Renderização com o motor próprio do pydeck: o balão (tooltip) é desenhado
    # pelo deck.gl dentro do mapa. Se algo falhar, volta ao mapa nativo.
    # Para desligar: troque True por False.
    RENDER_MAPA_PROPRIO = True

    if RENDER_MAPA_PROPRIO:
        try:
            import streamlit.components.v1 as components
            components.html(deck.to_html(as_string=True), height=520, scrolling=False)
        except Exception as e:
            st.warning(f"Renderização alternativa indisponível ({e}); usando o mapa padrão.")
            st.pydeck_chart(deck, height=520)
    else:
        st.pydeck_chart(deck, height=520)

    # =========================
    # BLOCO 9 — Estatísticas resumidas abaixo do mapa
    # =========================
    num_imoveis = len(df_filtrado)
    media_imoveis = df_filtrado[coluna_valor].mean() if num_imoveis else 0

    stat1, stat2 = st.columns(2, gap="small")
    with stat1:
        st.markdown(
            f'<div class="stat-pequena">🔢 Imóveis encontrados<br><b>{fmt_int(num_imoveis)}</b></div>',
            unsafe_allow_html=True
        )
    with stat2:
        st.markdown(
            f'<div class="stat-pequena">📈 Valor médio<br><b>{fmt_brl(media_imoveis, sufixo=sufixo_unid)}</b></div>',
            unsafe_allow_html=True
        )

# =========================
# BLOCO 10 — Gráfico (Plotly — interativo, com hover)
# =========================
with col_chart:
    st.markdown("### 📉 Gráfico")

    if grafico_tipo == "Histograma":
        fig = px.histogram(
            df_filtrado, x=coluna_valor, nbins=30,
            title=f"Distribuição de {tipo_estatistica}",
            labels={coluna_valor: "Valor (R$)"},
        )
        fig.update_traces(marker_color="#00CED1")
        fig.update_layout(template="plotly_dark", height=420, yaxis_title="Qtd. de imóveis")

    elif grafico_tipo == "Barras por bairro":
        # Reaproveita a agregação em cache (a mesma usada pelo mapa coroplético)
        stats_barras = agregar_por_bairro(
            df_filtrado[["latitude", "longitude", coluna_valor]], coluna_valor, gdf_bairros
        )
        media_bairro = (
            stats_barras[["NOME", "media"]]
            .sort_values("media", ascending=True)
            .tail(15)
            .rename(columns={"media": coluna_valor})
        )
        fig = px.bar(
            media_bairro, x=coluna_valor, y="NOME", orientation="h",
            title="Top 15 bairros",
            labels={coluna_valor: "Valor médio (R$)", "NOME": ""},
        )
        fig.update_traces(marker_color="#00CED1")
        fig.update_layout(template="plotly_dark", height=420)

    elif grafico_tipo == "Boxplot por tipo":
        fig = px.box(
            df_filtrado, x="Tipo", y=coluna_valor,
            title="Distribuição por tipo de imóvel",
            labels={coluna_valor: "Valor (R$)", "Tipo": ""},
            color="Tipo",
        )
        fig.update_layout(template="plotly_dark", height=420, showlegend=False)

    st.plotly_chart(fig, use_container_width=True)

# =========================
# BLOCO 11 — Série histórica IPTU/ITBI + previsão ARIMA + relação ITBI x IPTU
# =========================
st.markdown("---")
st.markdown("### 📈 Histórico e Previsão — IPTU e ITBI")

SERIE_HIST_PATH = "data/serie historica iptu itbi.xlsx"

REAJUSTE_ALIQUOTA_IPTU = {"ano_inicio": 2026, "fator": 1.20}


@st.cache_data(show_spinner=True)
def carregar_serie_historica(path):
    df_raw = pd.read_excel(path, header=0)
    df_final = df_raw.set_index("ANO").T.reset_index().rename(columns={"index": "ano"})
    df_final["ano"] = df_final["ano"].astype(int)

    def para_numero(serie):
        if pd.api.types.is_numeric_dtype(serie):
            return pd.to_numeric(serie, errors="coerce")
        limpo = (
            serie.astype(str)
            .str.replace("R$", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
            .str.strip()
        )
        return pd.to_numeric(limpo, errors="coerce")

    df_final["IPTU"] = para_numero(df_final["IPTU"])
    df_final["ITBI"] = para_numero(df_final["ITBI"])
    df_final = df_final.sort_values("ano").reset_index(drop=True)
    return df_final


def prever_arima(df, coluna, steps=2, reajuste=None):
    serie = df[["ano", coluna]].dropna(subset=[coluna]).set_index("ano")[coluna]
    ultimo_ano_real = int(serie.index.max())

    model = ARIMA(serie, order=(1, 1, 1))
    fit = model.fit()
    forecast = fit.forecast(steps=steps)
    anos_future = list(range(ultimo_ano_real + 1, ultimo_ano_real + 1 + steps))
    valores = forecast.round(2).to_numpy()

    if reajuste is not None:
        valores = [
            round(v * reajuste["fator"], 2) if ano >= reajuste["ano_inicio"] else round(v, 2)
            for ano, v in zip(anos_future, valores)
        ]

    return pd.DataFrame({"ano": anos_future, f"{coluna}_prev": valores}), ultimo_ano_real


@st.cache_data(show_spinner=True)
def calcular_previsoes(path):
    """Mesma lógica de antes; só fica em cache para não refazer o ARIMA a cada interação."""
    df_s = carregar_serie_historica(path)
    prev_i, ult_i = prever_arima(df_s, "IPTU", reajuste=REAJUSTE_ALIQUOTA_IPTU)
    prev_b, ult_b = prever_arima(df_s, "ITBI")
    return df_s, prev_i, ult_i, prev_b, ult_b


# Variáveis usadas também pelo relatório (ficam None se a série não puder ser carregada)
df_serie = prev_iptu = prev_itbi = None
fig_temp = fig_razao = fig_disp = None

if not Path(SERIE_HIST_PATH).exists():
    st.warning(f"Arquivo de série histórica não encontrado: {SERIE_HIST_PATH}")
else:
    try:
        df_serie, prev_iptu, ultimo_ano_iptu, prev_itbi, ultimo_ano_itbi = calcular_previsoes(SERIE_HIST_PATH)

        def conectar_previsao(df_prev, coluna_prev, coluna_hist, tipo_label):
            ultimo_hist = (
                df_serie[["ano", coluna_hist]]
                .dropna(subset=[coluna_hist])
                .rename(columns={coluna_hist: "valor"})
                .tail(1)
                .assign(tipo=tipo_label)
            )
            prev_plot = df_prev.rename(columns={coluna_prev: "valor"}).assign(tipo=tipo_label)
            return pd.concat([ultimo_hist, prev_plot])

        partes_plot = [
            df_serie[["ano", "IPTU"]].rename(columns={"IPTU": "valor"}).assign(tipo="Histórico IPTU"),
            conectar_previsao(prev_iptu, "IPTU_prev", "IPTU", "Previsto IPTU"),
            df_serie[["ano", "ITBI"]].rename(columns={"ITBI": "valor"}).assign(tipo="Histórico ITBI"),
            conectar_previsao(prev_itbi, "ITBI_prev", "ITBI", "Previsto ITBI"),
        ]
        df_plot_serie = pd.concat(partes_plot)

        fig_temp = px.line(
            df_plot_serie, x="ano", y="valor", color="tipo",
            title="Histórico e Previsões IPTU/ITBI"
        )
        fig_temp.update_layout(
            template="plotly_dark",
            height=420,
            xaxis=dict(showgrid=True, gridcolor="#333333", gridwidth=1),
            yaxis=dict(showgrid=True, gridcolor="#333333", gridwidth=1),
            plot_bgcolor="#0e0e0e",
        )
        # Destaca a zona de previsão com um fundo levemente diferente (cinza).
        inicio_previsao = min(ultimo_ano_iptu, ultimo_ano_itbi)
        fim_previsao = int(df_plot_serie["ano"].max())
        fig_temp.add_vrect(
            x0=inicio_previsao, x1=fim_previsao,
            fillcolor="#888888", opacity=0.15, line_width=0, layer="below",
        )

        col_graf, col_cards = st.columns([10, 2], gap="medium")
        with col_graf:
            st.plotly_chart(fig_temp, use_container_width=True)
        with col_cards:
            st.markdown(
                """
                <style>
                .card-previsao {
                    background-color: #1a1a1a;
                    border-radius: 8px;
                    padding: 0.7rem 0.9rem;
                    margin-top: 1rem;
                    font-size: 12.5px;
                }
                .card-previsao b { font-size: 13px; }
                .card-previsao ul {
                    padding-left: 1rem;
                    margin: 0.3rem 0 0.6rem 0;
                }
                .card-previsao li {
                    white-space: nowrap;
                    margin-bottom: 0.15rem;
                }
                </style>
                """,
                unsafe_allow_html=True
            )
            previsao_html = "<div class='card-previsao'>"
            previsao_html += "<b>Previsão IPTU</b><ul>"
            for _, row in prev_iptu.iterrows():
                previsao_html += f"<li>{int(row['ano'])}: R$ {row['IPTU_prev']:,.0f}</li>"
            previsao_html += "</ul><b>Previsão ITBI</b><ul>"
            for _, row in prev_itbi.iterrows():
                previsao_html += f"<li>{int(row['ano'])}: R$ {row['ITBI_prev']:,.0f}</li>"
            previsao_html += "</ul></div>"
            st.markdown(previsao_html, unsafe_allow_html=True)

        # -------------------------
        # Relação ITBI x IPTU
        # -------------------------
        st.markdown("### ⚖️ Relação ITBI × IPTU")
        try:
            base_rel = df_serie[["ano", "IPTU", "ITBI"]].dropna()
            base_rel = base_rel[base_rel["IPTU"] > 0].copy()
            base_rel["razao"] = base_rel["ITBI"] / base_rel["IPTU"] * 100

            prev_rel = prev_iptu.merge(prev_itbi, on="ano")
            prev_rel["razao"] = prev_rel["ITBI_prev"] / prev_rel["IPTU_prev"] * 100
            ligacao = base_rel.tail(1)[["ano", "razao"]]
            prev_linha = pd.concat([ligacao, prev_rel[["ano", "razao"]]])

            fig_razao = go.Figure()
            fig_razao.add_trace(go.Scatter(
                x=base_rel["ano"], y=base_rel["razao"],
                mode="lines+markers", name="Histórico",
                line=dict(color="#00CED1"),
            ))
            fig_razao.add_trace(go.Scatter(
                x=prev_linha["ano"], y=prev_linha["razao"],
                mode="lines+markers", name="Previsto",
                line=dict(color="#FFA500", dash="dash"),
            ))
            fig_razao.update_layout(
                template="plotly_dark", height=380,
                title="ITBI como % do IPTU, por ano",
                xaxis_title="Ano", yaxis_title="ITBI ÷ IPTU (%)",
            )

            fig_disp = px.scatter(
                base_rel, x="IPTU", y="ITBI", text="ano", trendline="ols",
                title="Dispersão ITBI × IPTU (histórico) com reta de regressão",
                labels={"IPTU": "IPTU (R$)", "ITBI": "ITBI (R$)"},
            )
            fig_disp.update_traces(textposition="top center", selector=dict(mode="markers+text"))
            fig_disp.update_layout(template="plotly_dark", height=380)

            col_r1, col_r2 = st.columns(2, gap="medium")
            with col_r1:
                st.plotly_chart(fig_razao, use_container_width=True)
            with col_r2:
                st.plotly_chart(fig_disp, use_container_width=True)
        except Exception as e:
            st.warning(f"Não foi possível montar o gráfico ITBI × IPTU: {e}")

    except Exception as e:
        st.error(f"Não foi possível calcular a previsão IPTU/ITBI: {e}")



# =========================
# BLOCO 12 — Relatório (HTML para imprimir/salvar em PDF + Excel)
# =========================
def _tabela_html(df_tab):
    return df_tab.to_html(index=False, border=0, classes="tabela", escape=True)


def _agora_br():
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return datetime.now().strftime("%d/%m/%Y %H:%M")


def _fig_claro(fig):
    """Cópia da figura em tema claro (melhor para impressão)."""
    f = go.Figure(fig)
    f.update_layout(template="plotly_white", plot_bgcolor="white", paper_bgcolor="white")
    f.update_xaxes(gridcolor="#dddddd")
    f.update_yaxes(gridcolor="#dddddd")
    return f


def gerar_relatorio_html(estatistica, n_imoveis, media_geral, stats_bairros, sufixo,
                         serie, prev_i, prev_b, figs_serie):
    partes = []
    primeiro = True

    def fig_html(fig):
        nonlocal primeiro
        h = fig.to_html(full_html=False, include_plotlyjs="cdn" if primeiro else False)
        primeiro = False
        return h

    # Bairros
    tab = stats_bairros.sort_values("media", ascending=False).copy()
    top = tab.head(15).sort_values("media", ascending=True)
    fig_b = px.bar(top, x="media", y="NOME", orientation="h",
                   title="15 bairros com maior valor médio",
                   labels={"media": "Valor médio (R$)", "NOME": ""})
    fig_b.update_traces(marker_color="#0d54a0")
    fig_b.update_layout(template="plotly_white", height=460)

    tab_fmt = pd.DataFrame({
        "Bairro": tab["NOME"],
        "Imóveis": tab["qtd"].apply(fmt_int),
        "Média": tab["media"].apply(lambda v: fmt_brl(v, sufixo=sufixo)),
        "Mínimo": tab["minimo"].apply(lambda v: fmt_brl(v, sufixo=sufixo)),
        "Máximo": tab["maximo"].apply(lambda v: fmt_brl(v, sufixo=sufixo)),
        "Variação vs. município": tab["variacao"].apply(fmt_pct),
    })

    partes.append("<h2>1. Mercado imobiliário por bairro</h2>")
    partes.append(f"<p>Estatística: <b>{escape(estatistica)}</b> · Imóveis considerados: <b>{fmt_int(n_imoveis)}</b> "
                  f"· Valor médio no município: <b>{fmt_brl(media_geral, sufixo=sufixo)}</b></p>")
    partes.append(fig_html(fig_b))
    partes.append(_tabela_html(tab_fmt))

    # Série histórica
    if serie is not None and prev_i is not None and prev_b is not None:
        hist = serie[["ano", "IPTU", "ITBI"]].copy()
        hist["razao"] = hist.apply(
            lambda r: (r["ITBI"] / r["IPTU"] * 100) if pd.notna(r["IPTU"]) and r["IPTU"] > 0 and pd.notna(r["ITBI"]) else None,
            axis=1,
        )
        hist_fmt = pd.DataFrame({
            "Ano": hist["ano"].astype(int),
            "IPTU": hist["IPTU"].apply(fmt_brl),
            "ITBI": hist["ITBI"].apply(fmt_brl),
            "ITBI ÷ IPTU": hist["razao"].apply(lambda v: "—" if v is None or pd.isna(v) else f"{_num_br(v, 1)}%"),
        })
        prev_fmt = pd.DataFrame({
            "Ano": prev_i["ano"].astype(int),
            "IPTU previsto": prev_i["IPTU_prev"].apply(lambda v: fmt_brl(v, casas=0)),
            "ITBI previsto": prev_b["ITBI_prev"].apply(lambda v: fmt_brl(v, casas=0)),
        })
        partes.append("<h2>2. Série histórica e previsão — IPTU e ITBI</h2>")
        for f in figs_serie:
            if f is not None:
                partes.append(fig_html(_fig_claro(f)))
        partes.append("<h3>Histórico</h3>" + _tabela_html(hist_fmt))
        partes.append("<h3>Previsão</h3>" + _tabela_html(prev_fmt))
        partes.append(
            "<p class='nota'>Metodologia: previsão por modelo ARIMA(1,1,1) sobre a série anual. "
            f"Reajuste de alíquota do IPTU de +{int(round((REAJUSTE_ALIQUOTA_IPTU['fator'] - 1) * 100))}% "
            f"aplicado às previsões a partir de {REAJUSTE_ALIQUOTA_IPTU['ano_inicio']}.</p>"
        )

    corpo = "\n".join(partes)
    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Relatório — Plataforma de Inteligência Territorial</title>
<style>
body {{ font-family: Arial, Helvetica, sans-serif; color:#111; max-width: 980px; margin: 24px auto; padding: 0 16px; }}
h1 {{ margin-bottom: 4px; }} h2 {{ margin-top: 32px; border-bottom: 2px solid #0d54a0; padding-bottom: 4px; }}
.sub {{ color:#555; margin-top:0; }}
.tabela {{ border-collapse: collapse; width: 100%; font-size: 13px; margin: 12px 0; }}
.tabela th {{ background:#0d54a0; color:#fff; text-align:left; padding:6px 8px; }}
.tabela td {{ border-bottom:1px solid #ddd; padding:5px 8px; }}
.nota {{ font-size: 12px; color:#555; }}
@media print {{ h2 {{ page-break-before: auto; }} }}
</style></head><body>
<h1>Plataforma de Inteligência Territorial</h1>
<p class="sub">Relatório gerado em {_agora_br()} (horário de Brasília)</p>
{corpo}
</body></html>"""


def gerar_relatorio_xlsx(stats_bairros, serie, prev_i, prev_b):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        bairros = stats_bairros.sort_values("media", ascending=False).rename(columns={
            "NOME": "Bairro", "qtd": "Imóveis", "media": "Média", "minimo": "Mínimo",
            "maximo": "Máximo", "variacao": "Variação vs. município (%)",
        })
        bairros.to_excel(xw, sheet_name="Bairros", index=False)
        if serie is not None:
            serie[["ano", "IPTU", "ITBI"]].to_excel(xw, sheet_name="Serie historica", index=False)
        if prev_i is not None and prev_b is not None:
            prev_i.merge(prev_b, on="ano").to_excel(xw, sheet_name="Previsao", index=False)
    return buf.getvalue()


st.markdown("---")
st.markdown("### 📄 Relatório")
st.caption("O relatório reflete a estatística escolhida na barra de filtros no momento em que você clicar em gerar.")

if st.button("Gerar relatório", key="btn_relatorio"):
    try:
        with st.spinner("Montando relatório..."):
            stats_rel = agregar_por_bairro(
                df_filtrado[["latitude", "longitude", coluna_valor]], coluna_valor, gdf_bairros
            )
            st.session_state["relatorio_html"] = gerar_relatorio_html(
                tipo_estatistica, len(df_filtrado), df_filtrado[coluna_valor].mean(), stats_rel,
                sufixo_unid, df_serie, prev_iptu, prev_itbi, [fig_temp, fig_razao, fig_disp],
            ).encode("utf-8")
            st.session_state["relatorio_xlsx"] = gerar_relatorio_xlsx(stats_rel, df_serie, prev_iptu, prev_itbi)
            st.session_state["relatorio_nome"] = tipo_estatistica
    except Exception as e:
        st.error(f"Não foi possível gerar o relatório: {e}")

if "relatorio_html" in st.session_state:
    st.success(f"Relatório pronto ({st.session_state.get('relatorio_nome', '')}).")
    dl1, dl2 = st.columns(2, gap="small")
    with dl1:
        st.download_button(
            "⬇️ Baixar relatório (HTML — abra e imprima/salve em PDF)",
            data=st.session_state["relatorio_html"],
            file_name="relatorio_inteligencia_territorial.html",
            mime="text/html",
            key="dl_relatorio_html",
        )
    with dl2:
        st.download_button(
            "⬇️ Baixar dados (Excel)",
            data=st.session_state["relatorio_xlsx"],
            file_name="dados_inteligencia_territorial.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="dl_relatorio_xlsx",
        )