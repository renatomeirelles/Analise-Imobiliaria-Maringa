# =========================
# Imports e configuração inicial
# =========================
import json
import warnings
import re
import unicodedata

import geopandas as gpd
import h3
import osmnx as ox
import pandas as pd
import plotly.express as px
import pydeck as pdk
import streamlit as st
from pathlib import Path
from shapely.geometry import box
from statsmodels.tsa.arima.model import ARIMA

warnings.filterwarnings("ignore")

# Configuração da página
st.set_page_config(
    page_title="Plataforma de Inteligência Territorial",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =========================
# CSS
# =========================
st.markdown("""
<style>
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
    font-size: 28px;
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
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div class="titulo-com-fundo">Plataforma de Inteligência Territorial</div>',
    unsafe_allow_html=True
)

# =========================
# Layout: filtros (esquerda) | mapa (centro, maior) | gráfico (direita, menor)
# =========================
col_filters, col_map, col_chart = st.columns([3, 6, 3], gap="small")

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
        ["Coroplético", "Pontos", "Densidade 3D (hexbin)", "Calor", "Edifícios 3D (OSM)"],
        index=0,
        key="mapa_selectbox"
    )

    metrica_hexbin = st.selectbox(
        "No hexbin 3D, medir por:",
        ["Quantidade de imóveis", "Valor médio"],
        index=0,
        key="metrica_hexbin_selectbox",
        help="Só se aplica quando o tipo de mapa é 'Densidade 3D (hexbin)'."
    )

    grafico_tipo = st.selectbox(
        "Selecione o gráfico:",
        ["Histograma", "Barras por bairro", "Boxplot por tipo"],
        index=0,
        key="grafico_selectbox"
    )

    st.markdown("### 🗂️ Camadas extras")
    mostrar_maringa = st.checkbox("Limite de Maringá", value=True, key="chk_maringa")
    mostrar_quadras = st.checkbox("Quadras", value=False, key="chk_quadras")
    mostrar_lotes = st.checkbox("Lotes", value=False, key="chk_lotes")

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
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar shapefile: {e}")
        return gpd.GeoDataFrame()

@st.cache_data(show_spinner=True)
def load_shapefile_generico(path: str) -> gpd.GeoDataFrame:
    try:
        gdf = gpd.read_file(path)
        gdf.columns = gdf.columns.str.strip()
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs("EPSG:4326")
        return gdf
    except Exception as e:
        st.error(f"Erro ao carregar shapefile: {e}")
        return gpd.GeoDataFrame()

# =========================
# Carregar dados com proteção
# =========================
df_path = "data/imoveis_georreferenciados_novembro.xlsx"
shp_path = "data/Bairros.shp"
maringa_path = "data/Maringa.shp"
quadras_path = "data/Quadra.shp"
lotes_path = "data/Lotes.shp"

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

# --- Camadas extras (Maringá, Quadras, Lotes) — não bloqueiam o app se faltar ---
gdf_maringa = load_shapefile_generico(maringa_path)
gdf_quadras = load_shapefile_generico(quadras_path)
gdf_lotes = load_shapefile_generico(lotes_path)

if not gdf_quadras.empty:
    gdf_quadras["geometry"] = gdf_quadras.geometry.simplify(0.00003, preserve_topology=True)
if not gdf_lotes.empty:
    gdf_lotes["geometry"] = gdf_lotes.geometry.simplify(0.00005, preserve_topology=True)

# ============================================
# Índice de Desalinhamento Alíquota x Mercado
# ============================================
import re
import unicodedata

@st.cache_data(show_spinner="Calculando índice de desalinhamento alíquota x mercado...")
def calcular_indice_desalinhamento(_df, _gdf_bairros):
    from rapidfuzz import process, fuzz

    # --- Anexo VIII da lei — Relação 1 (0,6%) ---
    RAW_RELACAO1 = """
28 Aclimação, Jardim
30 Bandeiras, Parque das
20 Beth, Jardim
43 Califórnia, Jardim
19 Campo Belo, Jardim
25 Cidade Alta, Conjunto Residencial
46 Chácaras do Jardim Alvorada
17 Chácaras da Vila Emília
37 Dourado, Jardim
17 Emília, Vila
43 Estilos, Chácaras
43 Everest, Jardim
19 Guairacá, Jardim
25 Honorato Vecchi, Residencial Pioneiro
44 Inocente Vilanova Jr., Conjunto Residencial
17 Itapuã, Jardim
25 Ipanema, Jardim
37 Lea Leal, Conjunto Habitacional
36 Liberdade parte IV, Loteamento
31 Licce, Jardim
48 Laranjeiras, Parque
21 Los Angeles, Jardim
21 Lucianópolis, Jardim
21 Mandacaru, Jardim
21 Maravilha, Jardim
19 Moradias Atenas
19 Moradias Atenas Parte 2
37 Morangueira, Chácaras
21 Monte Carlo, Jardim
36 Nova América, Jardim
17 Novo Horizonte parte V, Jardim
Oásis, Jardim
25 Odwaldo Bueno Netto, Residencial Pioneiro
30 Palmeiras, Parque das
36 Parigot de Souza, Conjunto Residencial Governador
37 Patrícia, Parque Residencial
48 Planville, Conjunto Residencial
30 Quebec, Parque Residencial
36 Regente, Parque Residencial
21 Santa Isabel, Vila
44 Santa Rosa, Jardim
25 São Paulo, Jardim
21 Seminário, Jardim
19 Três Lagoas, Jardim
48 Tropical, Jardim
37 Tupinambá, Jardim
21 Vardelina, Vila
44 Veredas, Jardim
44 Veredas II, Jardim
37 Virgínia, Vila
30 Vitória, Jardim
"""

    # --- Anexo VIII da lei — Relação 2 (0,3%) ---
    RAW_RELACAO2 = """
39 Aeroporto, Chácaras
38 Aeroporto parte I, Parque Residencial
38 Aeroporto parte II, Parque Residencial
38 Aeroporto parte III, Parque Residencial
33 Albino Meneguetti, Conjunto Habitacional
46 Alvorada parte III, Jardim
46 Andrade, Jardim
19 Andréa, Parque Residencial
20 Ângelo Planas, Conjunto Residencial
22 Atami, Jardim
36 Atlanta, Jardim
43 Aurora, Jardim
33 Alto Alegre
31 Avenida, Parque
37 Batel, Loteamento
53 Bela Vista, Loteamento Fechado
53 Bela Vista II, Loteamento Fechado
33 Belo Horizonte, Jardim
38 Bertioga, Jardim
37 Branca de Jesus Camargo Vieira, Conjunto Residencial
37 Campos Elíseos, Jardim
39 Catedral, Jardim
53 Centenário, Condomínio Chácaras
38 Céu Azul, Conjunto Habitacional
39 Cidade Alta, Conjunto
37 Colina Verde, Jardim
49 Colombo
Continental, Jardim
30 Copacabana II, Jardim
30 Copacabana, Residencial
38 Del Prata, Conjunto Habitacional
43 Do Carmo, Jardim
33 Dona Angelina, Conjunto Residencial
46 Ebenezer parte II, Loteamento
46 Ebenezer, Loteamento
33 Escalada, Residencial
29 Esperança parte III, Vila
38 Europa, Conjunto Habitacional
34 Floriano, Distrito de
33 Golden I, Jardim
33 Golden II, Jardim
34 Gonçalo Vieira dos Santos, Conjunto Habitacional
37 Grajaú
31 Grevíleas parte I, Parque
31 Grevíleas parte III, Parque
31 Grevíleas parte II, Parque
36 Guaiapó, Conjunto Residencial
30 Herman Moraes de Barros, Conjunto Habitacional
43 Hortência parte I, Parque
19 Hortência parte II, Parque
36 Ibirapuera, Parque Residencial
33 Iguatemi, Conjunto Habitacional
33 Iguatemi, Distrito de
33 Iguatemi, Residencial
43 Indaiá, Jardim
33 Índio, Jardim
47 Industrial, Jardim
25 Ipanema, Jardim
47 Itaipu, Parque
36 Itatiaia, Conjunto Habitacional
37 João-de-Barro Champagnat, Habitacional
39 João-de-Barro Cidade Alta I, Conjunto Habitacional
39 João-de-Barro Cidade Alta II, Conjunto Habitacional
39 João-de-Barro Cidade Canção, Conjunto Residencial
25 João-de-Barro I, Conjunto Residencial
34 João-de-Barro II, Conjunto Habitacional
37 João-de-Barro Itaparica, Conjunto Habitacional
38 João-de-Barro Porto Seguro I, Conjunto Residencial
38 João-de-Barro Porto Seguro II, Conjunto Residencial
19 João-de-Barro Thais, Conjunto Residencial
33 João Paulo I, Conjunto Residencial
34 José Israel Factori, Conjunto Residencial
34 José Pires de Oliveira, Pioneiro
31 Kakogawa, Jardim
19 Kosmos, Jardim
48 Laranjeiras, Parque das
39 Madrid
33 Marajoara, Jardim
43 Montreal, Jardim
34 Natalin Feltrin, Conjunto Habitacional
43 Ney Braga, Conjunto Residencial Governador
46 Novo Alvorada
21 Núcleo Social Papa João XXIII
19 Olímpico, Jardim
19 Ouro Cola, Jardim
25 Paraíso, Jardim
43 Pássaros, Jardim dos
37 Paulino C. Filho, Conjunto Residencial
36 Paulista, Jardim
36 Paulista II, Jardim
36 Paulista III, Jardim
37 Piatã, Loteamento, Jardim
Portal das Torres
33 Primavera, Jardim
39 Pro-Lar, Jardim
48 Rebouças, Jardim
56 Recanto dos Guerreiros
16 Recanto Kakogawa
36 Requião I, Conjunto Habitacional
46 Rodolpho Bernardi, Conjunto Residencial
38 Sanenge III, Conjunto Habitacional
43 Sanenge, Conjunto Habitacional
46 Santa Clara, Jardim
43 Santa Cruz, Jardim
25 Santa Felicidade, Núcleo Habitacional
53 Santa Maria, Loteamento Fechado
53 Santa Marina, Loteamento Fechado
33 Santa Terezinha, Conjunto
49 São Domingos, Jardim
46 Sumaré, Loteamento
37 São Francisco, Jardim
21 São Jorge, Jardim
43 São Miguel, Jardim
43 São Miguel 2.º Parte, Jardim
33 São Pedro, Jardim
39 São Silvestre, Jardim
33 Serena, Vila
39 Sol Nascente, Conjunto Habitacional
25 Tarumã, Loteamento Parque
25 Tarumã, Residencial
37 Tuiuti, Parque Residencial
20 Universo, Jardim
21 Vardelina, Vila
33 Villa Bella, Residencial
53 Zona de Urbanização Específica
"""

    def extrai_nomes(raw_text):
        nomes = []
        for linha in raw_text.strip().split("\n"):
            linha = linha.strip()
            if not linha or linha.startswith("("):
                continue
            nomes.append(re.sub(r"^\d+\s+", "", linha))
        return nomes

    aliquota_por_nome_lei = {}
    for nome in extrai_nomes(RAW_RELACAO1):
        aliquota_por_nome_lei[nome] = 0.006
    for nome in extrai_nomes(RAW_RELACAO2):
        aliquota_por_nome_lei[nome] = 0.003

    CLASSIFICADORES = [
        "conjunto residencial governador", "parque residencial",
        "residencial pioneiro", "loteamento fechado", "conjunto residencial",
        "conjunto habitacional", "nucleo habitacional", "distrito de",
        "zona de urbanizacao especifica", "parque das", "loteamento",
        "residencial", "conjunto", "habitacional", "chacaras",
        "gleba", "parque", "jardim", "vila", "nucleo",
    ]

    def normaliza(txt):
        txt = str(txt).lower()
        txt = ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
        txt = re.sub(r"[^\w\s]", " ", txt)
        return re.sub(r"\s+", " ", txt).strip()

    def extrai_core(txt):
        t = normaliza(txt)
        for c in sorted(CLASSIFICADORES, key=len, reverse=True):
            t = re.sub(rf"\b{re.escape(c)}\b", "", t)
        t = re.sub(r"\s+", " ", t).strip()
        return t if t else normaliza(txt)

    nomes_shapefile_norm = sorted(_gdf_bairros["NOME"].dropna().apply(normaliza).unique().tolist())
    core_shapefile = {nome: extrai_core(nome) for nome in nomes_shapefile_norm}

    resultados = []
    for nome_lei, aliquota in aliquota_por_nome_lei.items():
        core_lei = extrai_core(nome_lei)
        match, score, idx = process.extractOne(
            core_lei, list(core_shapefile.values()), scorer=fuzz.partial_ratio
        )
        nome_correspondente = list(core_shapefile.keys())[idx]
        resultados.append({"nome_norm": nome_correspondente, "aliquota": aliquota, "score": score})

    df_match = pd.DataFrame(resultados)
    LIMIAR = 85
    aliquota_confirmada = df_match[df_match["score"] >= LIMIAR][["nome_norm", "aliquota"]]
    aliquota_por_bairro_norm = aliquota_confirmada.groupby("nome_norm")["aliquota"].min().to_dict()

    # --- Preço médio/m² por bairro (usando NOME normalizado) ---
    gdf_imoveis_idx = gpd.GeoDataFrame(
        _df, geometry=gpd.points_from_xy(_df["longitude"], _df["latitude"]), crs="EPSG:4326"
    )
    gdf_bairros_norm = _gdf_bairros[["geometry", "NOME"]].copy()
    gdf_bairros_norm["NOME_norm"] = gdf_bairros_norm["NOME"].apply(normaliza)

    gdf_join = gpd.sjoin(gdf_imoveis_idx, gdf_bairros_norm, how="left", predicate="within")
    col_nome = "NOME_norm" if "NOME_norm" in gdf_join.columns else "NOME_norm_right"

    resumo = gdf_join.groupby(col_nome).agg(
        preco_m2_medio=("valor_m2", "mean"),
        n_imoveis=(col_nome, "size"),
    ).reset_index().rename(columns={col_nome: "NOME_norm"})

    resumo = resumo[resumo["n_imoveis"] >= 5].copy()
    resumo["classificado_pela_lei"] = resumo["NOME_norm"].isin(aliquota_por_bairro_norm.keys())
    resumo["aliquota"] = resumo["NOME_norm"].map(aliquota_por_bairro_norm).fillna(0.01)
    resumo["percentil_preco"] = resumo["preco_m2_medio"].rank(pct=True) * 100

    centro_esperado = {0.003: 16.5, 0.006: 50.0, 0.01: 83.5}
    resumo["centro_esperado"] = resumo["aliquota"].map(centro_esperado)
    resumo["indice_desalinhamento"] = (resumo["percentil_preco"] - resumo["centro_esperado"]).round(1)

    return resumo.set_index("NOME_norm").to_dict(orient="index")

indice_desalinhamento_por_bairro = calcular_indice_desalinhamento(df, gdf_bairros)

# =========================
# Paleta e faixas para o mapa coroplético
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
# Mapa (pydeck / deck.gl)
# =========================
with col_map:
    st.markdown("### 🗺️ Mapa")

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

        df_stats = gdf_join.groupby("NOME")[coluna_valor].agg(
            media="mean", minimo="min", maximo="max"
        ).reset_index()
        media_municipio = df_filtrado[coluna_valor].mean()
        df_stats["variacao"] = ((df_stats["media"] - media_municipio) / media_municipio) * 100
        df_stats = df_stats.round(2)

        gdf_plot = gdf_bairros.merge(df_stats, left_on="NOME", right_on="NOME", how="left")

        def cor_por_faixa(valor):
            if pd.isna(valor) or valor <= 0:
                return [43, 43, 43, 120]
            for i in range(len(bins) - 1):
                if bins[i] <= valor <= bins[i + 1]:
                    return cores_rgba[i]
            return cores_rgba[-1]

        gdf_plot["fill_color"] = gdf_plot["media"].apply(cor_por_faixa)

        def fmt_moeda(v):
            return f"R$ {v:,.2f}" if pd.notna(v) else "sem dados"

        gdf_plot["media_fmt"] = gdf_plot["media"].apply(fmt_moeda)
        gdf_plot["minimo_fmt"] = gdf_plot["minimo"].apply(fmt_moeda)
        gdf_plot["maximo_fmt"] = gdf_plot["maximo"].apply(fmt_moeda)
        gdf_plot["variacao_fmt"] = gdf_plot["variacao"].apply(
            lambda v: f"{v:.2f}%" if pd.notna(v) else "sem dados"
        )

        # --- NOVO: Alíquota e Índice de Desalinhamento no tooltip ---
        def normaliza_local(txt):
            txt = str(txt).lower()
            txt = ''.join(c for c in unicodedata.normalize('NFD', txt) if unicodedata.category(c) != 'Mn')
            txt = re.sub(r"[^\w\s]", " ", txt)
            return re.sub(r"\s+", " ", txt).strip()

        gdf_plot["_nome_norm"] = gdf_plot["NOME"].apply(normaliza_local)

        def busca_indice(nome_norm):
            info = indice_desalinhamento_por_bairro.get(nome_norm)
            if info is None:
                return "sem classificação", "—"
            aliquota_fmt = f"{info['aliquota']*100:.1f}%"
            indice_fmt = f"{info['indice_desalinhamento']:+.1f}"
            return aliquota_fmt, indice_fmt

        gdf_plot[["aliquota_fmt", "indice_desalinhamento_fmt"]] = gdf_plot["_nome_norm"].apply(
            lambda n: pd.Series(busca_indice(n))
        )

        geojson = json.loads(
            gdf_plot[[
                "geometry", "NOME", "media_fmt", "minimo_fmt", "maximo_fmt", "variacao_fmt",
                "aliquota_fmt", "indice_desalinhamento_fmt", "fill_color"
            ]].to_json()
        )

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
        tooltip = {
            "html": (
                "<b>{NOME}</b><br/>"
                "Média: {media_fmt}<br/>"
                "Mínimo: {minimo_fmt}<br/>"
                "Máximo: {maximo_fmt}<br/>"
                "Variação vs. município: {variacao_fmt}<br/>"
                "<hr style='margin:4px 0;'/>"
                "Alíquota IPTU: {aliquota_fmt}<br/>"
                "Índice de desalinhamento: {indice_desalinhamento_fmt}"
            )
        }

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
        H3_RESOLUCAO = 9
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
            agg_hex["label"] = agg_hex["qtd"].apply(lambda v: f"{int(v)} imóveis")
        else:
            agg_hex["label"] = agg_hex["media"].apply(lambda v: f"R$ {v:,.2f}")
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
        tooltip = {"html": "{label}"}

    elif tipo_mapa == "Edifícios 3D (OSM)":
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
            return 9.0

        @st.cache_data(show_spinner="Carregando edifícios...")
        def carregar_predios_local(path_str):
            gdf = gpd.read_file(path_str)
            if "altura" not in gdf.columns:
                gdf["altura"] = gdf.apply(estimar_altura, axis=1)
            return gdf[["geometry", "altura"]].reset_index(drop=True)

        @st.cache_data(show_spinner="Buscando edifícios no OpenStreetMap (só na primeira vez)...")
        def carregar_predios_osm_ao_vivo(_gdf_bairros_bounds):
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
                tooltip = {"html": "Altura estimada: {altura_fmt}"}
        except Exception as e:
            st.warning(
                "Não foi possível carregar os edifícios do OpenStreetMap agora "
                f"(a base pode estar indisponível ou a área é grande demais): {e}"
            )

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

    if mostrar_maringa and not gdf_maringa.empty:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer", json.loads(gdf_maringa.to_json()),
                stroked=True, filled=False, get_line_color=[255, 255, 255], line_width_min_pixels=2,
            )
        )
    if mostrar_quadras and not gdf_quadras.empty:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer", json.loads(gdf_quadras.to_json()),
                stroked=True, filled=False, get_line_color=[255, 165, 0], line_width_min_pixels=1,
            )
        )
    if mostrar_lotes and not gdf_lotes.empty:
        layers.append(
            pdk.Layer(
                "GeoJsonLayer", json.loads(gdf_lotes.to_json()),
                stroked=True, filled=True, get_fill_color=[200, 30, 30, 60],
                get_line_color=[200, 30, 30], line_width_min_pixels=0.5,
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
    # Estatísticas resumidas, pequenas, logo abaixo do mapa
    # (só quantidade de imóveis e valor médio, como pedido)
    # =========================
    num_imoveis = len(df_filtrado)
    media_imoveis = df_filtrado[coluna_valor].mean() if num_imoveis else 0

    stat1, stat2 = st.columns(2, gap="small")
    with stat1:
        st.markdown(
            f'<div class="stat-pequena">🔢 Imóveis encontrados<br><b>{num_imoveis}</b></div>',
            unsafe_allow_html=True
        )
    with stat2:
        st.markdown(
            f'<div class="stat-pequena">📈 Valor médio<br><b>R$ {media_imoveis:,.2f}</b></div>',
            unsafe_allow_html=True
        )

# =========================
# Gráfico (Plotly — interativo, com hover)
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
            .sort_values(ascending=True)
            .tail(15)
            .reset_index()
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
# Série histórica IPTU/ITBI + previsão ARIMA
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


if not Path(SERIE_HIST_PATH).exists():
    st.warning(f"Arquivo de série histórica não encontrado: {SERIE_HIST_PATH}")
else:
    try:
        df_serie = carregar_serie_historica(SERIE_HIST_PATH)
        prev_iptu, ultimo_ano_iptu = prever_arima(df_serie, "IPTU", reajuste=REAJUSTE_ALIQUOTA_IPTU)
        prev_itbi, ultimo_ano_itbi = prever_arima(df_serie, "ITBI")

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

        # =========================
        # NOVO: Índice de Descolamento IPTU x ITBI
        # =========================
        st.markdown("---")
        st.markdown("### 🧭 Índice de Descolamento IPTU x ITBI")
        st.caption(
            "Compara o ritmo de crescimento da arrecadação de IPTU (base administrativa, "
            "a Planta Genérica de Valores) com o do ITBI (base de mercado, valor real de "
            "transação). Quando o ITBI cresce mais rápido que o IPTU, é sinal de que a base "
            "tributária está ficando defasada em relação ao mercado."
        )

        df_razao = df_serie.dropna(subset=["IPTU", "ITBI"]).copy()
        df_razao = df_razao[df_razao["IPTU"] > 0]
        df_razao["razao_itbi_iptu"] = df_razao["ITBI"] / df_razao["IPTU"]

        fig_razao = px.line(
            df_razao, x="ano", y="razao_itbi_iptu",
            title="Razão ITBI / IPTU ao longo do tempo",
            markers=True,
        )
        fig_razao.update_layout(
            template="plotly_dark",
            height=350,
            xaxis=dict(showgrid=True, gridcolor="#333333", gridwidth=1),
            yaxis=dict(showgrid=True, gridcolor="#333333", gridwidth=1, title="ITBI / IPTU"),
            plot_bgcolor="#0e0e0e",
        )

        # --- Taxa de crescimento anualizada (CAGR) de cada tributo, no período disponível ---
        def cagr(df, coluna):
            serie = df[["ano", coluna]].dropna(subset=[coluna]).sort_values("ano")
            if len(serie) < 2:
                return None
            ano_ini, ano_fim = serie["ano"].iloc[0], serie["ano"].iloc[-1]
            val_ini, val_fim = serie[coluna].iloc[0], serie[coluna].iloc[-1]
            n_anos = ano_fim - ano_ini
            if n_anos <= 0 or val_ini <= 0:
                return None
            return (val_fim / val_ini) ** (1 / n_anos) - 1

        cagr_iptu = cagr(df_serie, "IPTU")
        cagr_itbi = cagr(df_serie, "ITBI")

        col_razao, col_cagr = st.columns([7, 3], gap="medium")
        with col_razao:
            st.plotly_chart(fig_razao, use_container_width=True)
        with col_cagr:
            st.metric("Crescimento anual médio — IPTU", f"{cagr_iptu*100:.1f}%" if cagr_iptu is not None else "—")
            st.metric("Crescimento anual médio — ITBI", f"{cagr_itbi*100:.1f}%" if cagr_itbi is not None else "—")
            if cagr_iptu is not None and cagr_itbi is not None:
                diferenca = (cagr_itbi - cagr_iptu) * 100
                if diferenca > 0.5:
                    st.warning(f"ITBI cresce {diferenca:.1f} p.p./ano mais rápido que o IPTU — indício de defasagem crescente.")
                elif diferenca < -0.5:
                    st.info(f"IPTU cresce {-diferenca:.1f} p.p./ano mais rápido que o ITBI — a base tributária está acompanhando ou superando o mercado.")
                else:
                    st.success("IPTU e ITBI crescem em ritmo semelhante — sem sinal de descolamento agregado.")

    except Exception as e:
        st.error(f"Não foi possível calcular a previsão IPTU/ITBI: {e}")
