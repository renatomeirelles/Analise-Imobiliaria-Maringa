import dash
from dash import html, dcc
import pandas as pd
import geopandas as gpd
import folium
from folium.plugins import MarkerCluster, HeatMap
from dash.dependencies import Input, Output
import plotly.express as px
import unicodedata
import warnings
import dash_bootstrap_components as dbc
warnings.filterwarnings("ignore")

from statsmodels.tsa.arima.model import ARIMA

# =========================
# Carregar dados imobiliários
# =========================
df = pd.read_excel("data/imoveis_georreferenciados_novembro.xlsx")
df.columns = df.columns.str.strip()
df = df.dropna(subset=['latitude', 'longitude'])

# Normalizar coluna Tipo
df["Tipo"] = df["Tipo"].apply(
    lambda x: unicodedata.normalize("NFKD", str(x)).encode("ASCII", "ignore").decode("utf-8").lower().strip()
)

gdf_imoveis = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df['longitude'], df['latitude']),
    crs="EPSG:4326"
)

gdf_bairros = gpd.read_file("data/municipio_completo.shp").to_crs("EPSG:4326")

gdf_imoveis_bairros = gpd.sjoin(
    gdf_imoveis,
    gdf_bairros[['geometry', 'NOME']],
    how="left",
    predicate="intersects"
)

# =========================
# Função auxiliar de filtro
# =========================
def filtrar_tipo(tipo):
    if tipo == "total":
        return gdf_imoveis_bairros.copy()
    else:
        return gdf_imoveis_bairros[gdf_imoveis_bairros["Tipo"] == tipo].copy()

# =========================
# Funções auxiliares de mapas
# =========================

def gerar_mapa_coropletico(tipo):
    gdf_filtrado = filtrar_tipo(tipo)
    df_stats = gdf_filtrado.groupby("NOME").agg(
        media_preco=("Preço", "mean"),
        min_preco=("Preço", "min"),
        max_preco=("Preço", "max"),
        media_preco_m2=("Preço por m²", "mean"),
        min_preco_m2=("Preço por m²", "min"),
        max_preco_m2=("Preço por m²", "max")
    ).reset_index()

    media_municipio = gdf_filtrado["Preço"].mean()
    df_stats["variacao"] = ((df_stats["media_preco"] - media_municipio) / media_municipio) * 100
    df_stats = df_stats.round(2)

    gdf_plot = gdf_bairros.merge(df_stats, left_on="NOME", right_on="NOME", how="left")

    mapa = criar_mapa_base()

    faixas = [
        (0, 200000, "#e31a1c"),
        (200001, 400000, "#fd8d3c"),
        (400001, 600000, "#fecc5c"),
        (600001, 800000, "#ffffb2"),
        (800001, 1200000, "#a1d6f7"),
        (1200001, 2000000, "#08519c")
    ]

    def cor_por_valor(valor):
        for minimo, maximo, cor in faixas:
            if minimo <= valor <= maximo:
                return cor
        return "#cccccc"

    for _, row in gdf_plot.iterrows():
        if pd.isna(row["media_preco"]):
            continue
        tooltip = folium.Tooltip(
            f"<b>{row['NOME']}</b><br>"
            f"Média total: R$ {row['media_preco']:,.2f}<br>"
            f"Mínimo total: R$ {row['min_preco']:,.2f}<br>"
            f"Máximo total: R$ {row['max_preco']:,.2f}<br>"
            f"Variação: {row['variacao']:.2f}%<br>"
            f"Média m²: R$ {row['media_preco_m2']:,.2f}<br>"
            f"Mínimo m²: R$ {row['min_preco_m2']:,.2f}<br>"
            f"Máximo m²: R$ {row['max_preco_m2']:,.2f}"
        )
        folium.GeoJson(
            row["geometry"],
            style_function=lambda feature, preco=row["media_preco"]: {
                "fillColor": cor_por_valor(preco),
                "color": "black",
                "weight": 1,
                "fillOpacity": 0.7,
            },
            tooltip=tooltip
        ).add_to(mapa)

    mapa.save("mapa.html")
    return "mapa.html"


def gerar_mapa_pontos(tipo):
    gdf_filtrado = filtrar_tipo(tipo)
    mapa = criar_mapa_base()
    for _, row in gdf_filtrado.iterrows():
        folium.CircleMarker(
            location=[row["latitude"], row["longitude"]],
            radius=4,
            color="blue",
            fill=True,
            fill_opacity=0.6,
            tooltip=f"{row['Tipo']} — R$ {row['Preço']:,.2f} (total) — R$ {row['Preço por m²']:,.2f}/m²"
        ).add_to(mapa)
    mapa.save("mapa.html")
    return "mapa.html"


def gerar_mapa_cluster(tipo):
    gdf_filtrado = filtrar_tipo(tipo)
    mapa = criar_mapa_base()
    cluster = MarkerCluster().add_to(mapa)
    for _, row in gdf_filtrado.iterrows():
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"{row['Tipo']} — R$ {row['Preço']:,.2f} (total) — R$ {row['Preço por m²']:,.2f}/m²"
        ).add_to(cluster)
    mapa.save("mapa.html")
    return "mapa.html"


def gerar_mapa_calor(tipo):
    gdf_filtrado = filtrar_tipo(tipo)
    mapa = criar_mapa_base()
    heat_data = [[row["latitude"], row["longitude"], row["Preço"]] for _, row in gdf_filtrado.iterrows()]
    HeatMap(heat_data, radius=10, blur=15, max_zoom=13).add_to(mapa)
    mapa.save("mapa.html")
    return "mapa.html"

# =========================
# Carregar série temporal IPTU/ITBI (planilha transposta)
# =========================

df_raw = pd.read_excel("data/serie historica iptu itbi.xlsx", header=0)

# Transpor: anos viram índice, indicadores viram colunas
df_final = df_raw.set_index('ANO').T.reset_index()
df_final = df_final.rename(columns={'index':'ano'})

# Converter ano para inteiro
df_final['ano'] = df_final['ano'].astype(int)

# Garantir que IPTU e ITBI sejam numéricos
df_final['IPTU'] = pd.to_numeric(df_final['IPTU'], errors='coerce')
df_final['ITBI'] = pd.to_numeric(df_final['ITBI'], errors='coerce')

# Outras variáveis (PIB, INCC, IPCA etc.) também podem ser convertidas
df_final['PIB Maringá'] = pd.to_numeric(df_final['PIB Maringá'], errors='coerce')
df_final['INCC'] = df_final['INCC'].astype(str).str.replace('%','').str.replace(',','.').astype(float)
df_final['IPCA'] = df_final['IPCA'].astype(str).str.replace('%','').str.replace(',','.').astype(float)

df_final = df_final.dropna(subset=['IPTU','ITBI'])

ACCESS_TOKEN = "ZK6EgfhFT6px8F8MsRfOp2S5aUMPOvNr5CEEtLmjOYjHDC2MzgI0ZJ1cJjj0C98Y"

def criar_mapa_base():
    return folium.Map(
        location=[-23.4205, -51.9331],
        zoom_start=12,
        tiles=f"https://{{s}}.tile.jawg.io/jawg-dark/{{z}}/{{x}}/{{y}}{{r}}.png?access-token={ACCESS_TOKEN}",
        attr="Jawg Maps"
    )

# Funções ARIMA
def prever_arima_iptu(df, steps=2):
    serie = df.set_index('ano')['IPTU']

    model = ARIMA(serie, order=(1,1,1))
    fit = model.fit()

    forecast = fit.forecast(steps=steps)

    anos_future = list(range(df['ano'].max() + 1,
                             df['ano'].max() + 1 + steps))

    previsao = pd.DataFrame({
        'ano': anos_future,
        'IPTU_prev': forecast.round(2)
    })

    # Ajuste extraordinário de +30% para 2026 e anos seguintes
    previsao.loc[previsao['ano'] >= 2026, 'IPTU_prev'] *= 1.30

    return previsao


def prever_arima_itbi(df, steps=2):
    serie = df.set_index('ano')['ITBI']

    model = ARIMA(serie, order=(1,1,1))
    fit = model.fit()

    forecast = fit.forecast(steps=steps)

    anos_future = list(range(df['ano'].max() + 1,
                             df['ano'].max() + 1 + steps))

    return pd.DataFrame({
        'ano': anos_future,
        'ITBI_prev': forecast.round(2)
    })


app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])  # tema escuro

app.layout = dbc.Container([
    dbc.NavbarSimple(
        brand="Inteligência Fiscal e Territorial - Modelagem Econométrica — Maringá",
        color="dark",
        dark=True,
        fluid=True
    ),
])

# Seletores
dbc.Row([
    dbc.Col([
        html.Label("Selecione o tipo de imóvel:", style={"fontWeight": "bold"}),
        dcc.Dropdown(
            id="tipo-imovel",
            options=[
                {"label": "Todos", "value": "total"},
                {"label": "Apartamentos", "value": "apartamento"},
                {"label": "Casas", "value": "casa"},
                {"label": "Condomínios", "value": "condominio"}
            ],
            value="total"
        )
    ], md=6),
    dbc.Col([
        html.Label("Selecione o tipo de mapa:", style={"fontWeight": "bold"}),
        dcc.Dropdown(
            id="tipo-mapa",
            options=[
                {"label": "Coroplético", "value": "coropletico"},
                {"label": "Pontos", "value": "pontos"},
                {"label": "Cluster", "value": "cluster"},
                {"label": "Calor", "value": "calor"}
            ],
            value="coropletico"
        )
    ], md=6),
], className="mb-4"),

# Cards de estatísticas
dbc.Row([
    dbc.Col(
        dbc.Card([
            dbc.CardHeader("Resumo"),
            dbc.CardBody([
                html.P(id="info-filtro")   # <- ID para o resumo dinâmico
            ])
        ], color="secondary", outline=True),
        md=4
    ),

    dbc.Col(
        dbc.Card([
            dbc.CardHeader("Previsão IPTU"),
            dbc.CardBody([
                html.P(id="previsao-iptu")   # <- ID para previsão IPTU
            ])
        ], color="info", outline=True),
        md=4
    ),

    dbc.Col(
        dbc.Card([
            dbc.CardHeader("Previsão ITBI"),
            dbc.CardBody([
                html.P(id="previsao-itbi")   # <- ID para previsão ITBI
            ])
        ], color="success", outline=True),
        md=4
    )
], className="mb-4"),

    # Mapa + gráfico de distribuição
    dbc.Row([
        dbc.Col(html.Iframe(id="mapa", style={"width":"100%", "height":"700px"}), md=8),
        dbc.Col(dcc.Graph(id="grafico-distribuicao"), md=4)
    ], className="mb-4"),

    # Gráfico temporal IPTU/ITBI
    dbc.Row([
        dbc.Col(dcc.Graph(id="grafico-temporal"), md=12)
    ], className="mb-4")
], fluid=True)

# =========================
# Callback para atualizar mapa, estatísticas, gráfico e previsões ARIMA
# =========================
@app.callback(
    [
        Output("mapa", "srcDoc"),
        Output("info-filtro", "children"),
        Output("grafico-distribuicao", "figure"),
        Output("previsao-iptu", "children"),
        Output("previsao-itbi", "children"),
        Output("grafico-temporal", "figure")
    ],
    [Input("tipo-imovel", "value"), Input("tipo-mapa", "value")]
)
def atualizar_dashboard(tipo_imovel, tipo_mapa):
    # --- Mapa ---
    if tipo_mapa == "coropletico":
        mapa_path = gerar_mapa_coropletico(tipo_imovel)
    elif tipo_mapa == "pontos":
        mapa_path = gerar_mapa_pontos(tipo_imovel)
    elif tipo_mapa == "cluster":
        mapa_path = gerar_mapa_cluster(tipo_imovel)
    else:
        mapa_path = gerar_mapa_calor(tipo_imovel)

    with open(mapa_path, "r", encoding="utf-8") as f:
        mapa_html = f.read()

    # --- Estatísticas resumo ---
    gdf_filtrado = filtrar_tipo(tipo_imovel)
    qtd = len(gdf_filtrado)
    media_total = gdf_filtrado["Preço"].mean()
    media_m2 = gdf_filtrado["Preço por m²"].mean()

    info_resumo = [
        html.P(f"Imóveis encontrados: {qtd}"),
        html.P(f"Média total: R$ {media_total:,.2f}"),
        html.P(f"Média m²: R$ {media_m2:,.2f}")
    ]

    # --- Gráfico distribuição ---
    fig_dist = px.histogram(
        gdf_filtrado, x="Preço", nbins=30,
        title="Distribuição de preços"
    )
    fig_dist.update_layout(template="plotly_dark")

    # --- Previsões ARIMA ---
    prev_iptu = prever_arima_iptu(df_final, steps=2)
    prev_itbi = prever_arima_itbi(df_final, steps=2)

    previsao_iptu = [
        html.P(f"{row['ano']}: R$ {row['IPTU_prev']:,.2f}") for _, row in prev_iptu.iterrows()
    ]
    previsao_itbi = [
        html.P(f"{row['ano']}: R$ {row['ITBI_prev']:,.2f}") for _, row in prev_itbi.iterrows()
    ]

    # --- Gráfico temporal (histórico + previsão) ---
    df_iptu = pd.concat([
        df_final[['ano','IPTU']].rename(columns={'IPTU':'valor'}).assign(tipo='Histórico IPTU'),
        prev_iptu.rename(columns={'IPTU_prev':'valor'}).assign(tipo='Previsto IPTU')
    ])

    df_itbi = pd.concat([
        df_final[['ano','ITBI']].rename(columns={'ITBI':'valor'}).assign(tipo='Histórico ITBI'),
        prev_itbi.rename(columns={'ITBI_prev':'valor'}).assign(tipo='Previsto ITBI')
    ])

    df_plot = pd.concat([df_iptu, df_itbi])

    fig_temp = px.line(df_plot, x="ano", y="valor", color="tipo",
                       title="Histórico e Previsões IPTU/ITBI")
    fig_temp.update_layout(template="plotly_dark")

    return mapa_html, info_resumo, fig_dist, previsao_iptu, previsao_itbi, fig_temp


# =========================
# Rodar o servidor
# =========================
if __name__ == "__main__":
    app.run(debug=True)

