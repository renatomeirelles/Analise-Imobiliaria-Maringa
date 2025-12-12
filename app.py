def set_background(png_file):
    bin_str = get_base64_of_bin_file(png_file)
    st.markdown(
        f"""
        <style>
        /* Remove espaço branco do topo */
        header {{ visibility: hidden; }}
        .stApp {{
            background-image: url("data:image/png;base64,{bin_str}");
            background-size: cover;
            background-attachment: fixed;
            background-position: center;
        }}
        .block-container {{
            padding-top: 0rem;
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
st.markdown(
    """
    <div class="banner" style="background: rgba(0,0,0,0.55); padding: 18px; border-radius: 10px; margin-bottom: 10px; text-align: center; color: white;">
        <h1 style="font-size:28px; font-weight:700; color:#00CED1; text-shadow:1px 1px 3px #000000; margin:0;">
            Análise Imobiliária – Maringá‑PR
        </h1>
        <p style="margin:4px 0 0 0; font-size:13px; opacity:0.95;">
            Painel interativo de dados estatísticos e espaciais da oferta de imóveis residenciais
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)
with st.sidebar:
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
    )

    tipo_mapa = st.selectbox("Selecione o tipo de mapa:", ["Coroplético", "Pontos", "Cluster", "Calor"])
    grafico_tipo = st.selectbox("Selecione o gráfico:", ["Histograma", "Barras por bairro", "Boxplot por tipo"])

    # Filtros e coluna alvo
    estatistica_norm = "preco_medio_total"
    # (insira aqui o bloco de definição de df_filtrado e coluna_valor como já usamos antes)

    # Métricas na barra lateral
    num_imoveis = len(df_filtrado)
    media_imoveis = df_filtrado[coluna_valor].mean()

    st.markdown("## 📊 Estatísticas")
    st.markdown(f"**🔢 Imóveis encontrados:** {num_imoveis}")
    st.markdown(f"**📈 Média ({tipo_estatistica}):** R$ {media_imoveis:,.2f}")
col_mapa, col_grafico = st.columns([1.2, 0.8])

with col_mapa:
    st.markdown("### 🗺️ Mapa")
    # (insira aqui o bloco completo de mapas como já usamos antes)
    st_folium(m, width=700, height=500, returned_objects=[], use_container_width=True)

with col_grafico:
    st.markdown("### 📉 Gráfico")
    fig = None
    # (insira aqui o bloco completo de gráficos como já usamos antes)
    if fig is not None:
        st.pyplot(fig, clear_figure=True)
