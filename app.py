import dash
from dash import html, dcc
from dash.dependencies import Input, Output
import dash_deck
import pydeck as pdk
import geopandas as gpd
from pathlib import Path

app = dash.Dash(__name__)

# ---------------------------------------------------------
# CAMINHOS DOS DADOS
# ---------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

CAMINHOS_SHP = {
    "Maringá": DATA_DIR / "Maringa.shp",
    "Bairros": DATA_DIR / "Bairros.shp",
    "Quadras": DATA_DIR / "Quadra.shp",
    "Lotes":   DATA_DIR / "Lotes.shp",
}

# ---------------------------------------------------------
# CARGA E PADRONIZAÇÃO DE CRS (todas as camadas em WGS84 - EPSG:4326)
# ---------------------------------------------------------
def carregar_camadas():
    gdfs = {}
    for nome, caminho in CAMINHOS_SHP.items():
        gdf = gpd.read_file(caminho)
        if gdf.crs is None:
            raise ValueError(f"Camada '{nome}' não tem CRS definido no .prj — verifique o arquivo.")
        gdf = gdf.to_crs("EPSG:4326")
        gdfs[nome] = gdf
    return gdfs

gdfs = carregar_camadas()

# ---------------------------------------------------------
# CONVERSÃO PARA O FORMATO QUE O PYDECK ESPERA (GeoJSON)
# ---------------------------------------------------------
def gdf_para_geojson(gdf):
    return gdf.__geo_interface__

geojson_maringa = gdf_para_geojson(gdfs["Maringá"])
geojson_bairros = gdf_para_geojson(gdfs["Bairros"])
geojson_quadras = gdf_para_geojson(gdfs["Quadras"])
geojson_lotes   = gdf_para_geojson(gdfs["Lotes"])

# ---------------------------------------------------------
# DEFINIÇÃO DAS CAMADAS (estilo básico, cor por camada)
# ---------------------------------------------------------
def cria_layer_maringa():
    return pdk.Layer(
        "GeoJsonLayer", data=geojson_maringa, id="layer-maringa",
        stroked=True, filled=False, get_line_color=[255, 255, 255], line_width_min_pixels=2,
    )

def cria_layer_bairros():
    return pdk.Layer(
        "GeoJsonLayer", data=geojson_bairros, id="layer-bairros",
        stroked=True, filled=True, get_fill_color=[70, 130, 180, 40],
        get_line_color=[70, 130, 180], line_width_min_pixels=1, pickable=True,
    )

def cria_layer_quadras():
    return pdk.Layer(
        "GeoJsonLayer", data=geojson_quadras, id="layer-quadras",
        stroked=True, filled=False, get_line_color=[255, 165, 0], line_width_min_pixels=1, pickable=True,
    )

def cria_layer_lotes():
    return pdk.Layer(
        "GeoJsonLayer", data=geojson_lotes, id="layer-lotes",
        stroked=True, filled=True, get_fill_color=[200, 30, 30, 60],
        get_line_color=[200, 30, 30], line_width_min_pixels=0.5, pickable=True,
    )

CRIADORES_LAYER = {
    "Maringá": cria_layer_maringa,
    "Bairros": cria_layer_bairros,
    "Quadras": cria_layer_quadras,
    "Lotes":   cria_layer_lotes,
}

# ---------------------------------------------------------
# VIEW STATE E MONTAGEM DO DECK
# ---------------------------------------------------------
view_state = pdk.ViewState(latitude=-23.42, longitude=-51.94, zoom=11, pitch=0)

def monta_deck(camadas_ativas):
    layers = [CRIADORES_LAYER[nome]() for nome in camadas_ativas]
    return pdk.Deck(
        layers=layers,
        initial_view_state=view_state,
        tooltip={
            "html": "<b>{NOME}</b>{QUADRA_GEO}{LOTE}",
            "style": {"backgroundColor": "white", "color": "black"},
        },
        map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
    )

# ---------------------------------------------------------
# INTERFACE
# ---------------------------------------------------------
app.layout = html.Div(
    [
        html.Div(
            [
                html.H1("GeoReceita"),
                html.P("Camadas territoriais de Maringá — Bairros, Quadras e Lotes"),
                dcc.Checklist(
                    id="seletor-camadas",
                    options=[{"label": f" {nome}", "value": nome} for nome in CRIADORES_LAYER],
                    value=["Maringá", "Bairros"],  # camadas ligadas por padrão
                    inline=True,
                    style={"marginTop": "10px"},
                ),
            ],
            style={"padding": "20px 30px", "backgroundColor": "#ffffff"},
        ),
        dash_deck.DeckGL(
            monta_deck(["Maringá", "Bairros"]).to_json(),
            id="mapa-deck",
            style={"width": "100%", "height": "calc(100vh - 150px)"},
        ),
    ],
    style={"margin": "0", "padding": "0", "fontFamily": "Arial, sans-serif"},
)

# ---------------------------------------------------------
# CALLBACK — atualiza o mapa quando o usuário liga/desliga camadas
# ---------------------------------------------------------
@app.callback(
    Output("mapa-deck", "data"),
    Input("seletor-camadas", "value"),
)
def atualizar_camadas(camadas_selecionadas):
    return monta_deck(camadas_selecionadas).to_json()


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)