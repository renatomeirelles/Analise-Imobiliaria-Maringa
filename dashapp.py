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
import os
warnings.filterwarnings("ignore")

from statsmodels.tsa.arima.model import ARIMA

# =========================
# Caminho base do projeto
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# =========================
# Carregar dados imobiliários
# =========================
print(">>> Carregando dados de imóveis...")
df_path = os.path.join(BASE_DIR, "data", "imoveis_georreferenciados_novembro.xlsx")
print("Arquivo esperado:", df_path)
df = pd.read_excel(df_path)
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

print(">>> Carregando shapefile de bairros...")
shp_path = os.path.join(BASE_DIR, "data", "municipio_completo.shp")
print("Arquivo esperado:", shp_path)
gdf_bairros = gpd.read_file(shp_path).to_crs("EPSG:4326")

gdf_imoveis_bairros = gpd.sjoin(
    gdf_imoveis,
    gdf_bairros[['geometry', 'NOME']],
    how="left",
    predicate="intersects"
)

# =========================
# Série temporal IPTU/ITBI
# =========================
print(">>> Carregando série histórica IPTU/ITBI...")
serie_path = os.path.join(BASE_DIR, "data", "serie historica iptu itbi.xlsx")
print("Arquivo esperado:", serie_path)
df_raw = pd.read_excel(serie_path, header=0)

df_final = df_raw.set_index('ANO').T.reset_index()
df_final = df_final.rename(columns={'index':'ano'})
df_final['ano'] = df_final['ano'].astype(int)
df_final['IPTU'] = pd.to_numeric(df_final['IPTU'], errors='coerce')
df_final['ITBI'] = pd.to_numeric(df_final['ITBI'], errors='coerce')
df_final['PIB Maringá'] = pd.to_numeric(df_final['PIB Maringá'], errors='coerce')
df_final['INCC'] = df_final['INCC'].astype(str).str.replace('%','').str.replace(',','.').astype(float)
df_final['IPCA'] = df_final['IPCA'].astype(str).str.replace('%','').str.replace(',','.').astype(float)
df_final = df_final.dropna(subset=['IPTU','ITBI'])

print(">>> Dados carregados com sucesso. Registros:", len(df), "anos série:", df_final['ano'].min(), "-", df_final['ano'].max())


# =========================
# Funções ARIMA
# =========================
def prever_arima_iptu(df, steps=2):
    serie = df.set_index('ano')['IPTU']
    model = ARIMA(serie, order=(1,1,1))
    fit = model.fit()
    forecast = fit.forecast(steps=steps)
    anos_future = list(range(df['ano'].max() + 1, df['ano'].max() + 1 + steps))
    previsao = pd.DataFrame({'ano': anos_future, 'IPTU_prev': forecast.round(2)})
    previsao.loc[previsao['ano'] >= 2026, 'IPTU_prev'] *= 1.30
    return previsao

def prever_arima_itbi(df, steps=2):
    serie = df.set_index('ano')['ITBI']
    model = ARIMA(serie, order=(1,1,1))
    fit = model.fit()
    forecast = fit.forecast(steps=steps)
    anos_future = list(range(df['ano'].max() + 1, df['ano'].max() + 1 + steps))
    return pd.DataFrame({'ano': anos_future, 'ITBI_prev': forecast.round(2)})
# =========================
# Layout da aplicação
# =========================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.CYBORG])  # tema escuro

app.layout = dbc.Container([
    # Navbar
    dbc.NavbarSimple(
        brand="Inteligência Fiscal e Territorial - Modelagem Econométrica — Maringá",
        color="dark",
        dark=True,
        fluid=True
    ),

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
                    html.P(id="info-filtro")
                ])
            ], color="secondary", outline=True),
            md=4
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader("Previsão IPTU"),
                dbc.CardBody([
                    html.P(id="previsao-iptu")
                ])
            ], color="info", outline=True),
            md=4
        ),
        dbc.Col(
            dbc.Card([
                dbc.CardHeader("Previsão ITBI"),
                dbc.CardBody([
                    html.P(id="previsao-itbi")
                ])
            ], color="success", outline=True),
            md=4
        )
    ], className="mb-4"),

    # Mapa + gráfico de distribuição
    dbc.Row([
        dbc.Col(
            html.Iframe(
                id="mapa",
                srcDoc="",   # inicializa vazio para receber conteúdo do callback
                style={"width": "100%", "height": "700px"}
            ),
            md=8
        ),
        dbc.Col(
            dcc.Graph(id="grafico-distribuicao"),
            md=4
        )
    ], className="mb-4"),

    # Gráfico temporal IPTU/ITBI
    dbc.Row([
        dbc.Col(
            dcc.Graph(id="grafico-temporal"),
            md=12
        )
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
    print(">>> Atualizando dashboard:", tipo_imovel, tipo_mapa)

    # --- Mapa ---
    if tipo_mapa == "coropletico":
        # Como não temos função coroplética implementada, vamos usar pontos
        mapa_html = gerar_mapa_pontos(tipo_imovel)
    elif tipo_mapa == "pontos":
        mapa_html = gerar_mapa_pontos(tipo_imovel)
    elif tipo_mapa == "cluster":
        mapa_html = gerar_mapa_cluster(tipo_imovel)
    else:
        mapa_html = gerar_mapa_calor(tipo_imovel)

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
    app.run_server(debug=True)
