import requests
import pandas as pd
import streamlit as st
from datetime import date

# ==========================================================
# COMEX STAT - API OFICIAL MDIC
# ==========================================================

BASE_URL = "https://api-comexstat.mdic.gov.br"
PESO_CONTAINER = 23000

st.set_page_config(
    page_title="Comex Bot",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Comex Bot — Exportações por Município")

st.caption(
    "Consulta diretamente a API oficial do Comex Stat/MDIC."
)


# ==========================================================
# FUNÇÃO PARA CHAMAR A API
# ==========================================================

def api_get(endpoint):
    response = requests.get(
        f"{BASE_URL}{endpoint}",
        timeout=60
    )

    response.raise_for_status()

    data = response.json()

    if data.get("success") is False:
        raise Exception(
            data.get("message", "Erro na API")
        )

    return data


# ==========================================================
# MUNICÍPIOS
# API OFICIAL:
# /tables/cities
# ==========================================================

@st.cache_data(ttl=86400)
def carregar_municipios():

    data = api_get(
        "/tables/cities"
    )

    lista = data.get(
        "data",
        []
    )

    df = pd.DataFrame(lista)

    if df.empty:
        return pd.DataFrame(
            columns=[
                "id",
                "text"
            ]
        )

    return df[
        [
            "id",
            "text"
        ]
    ].copy()


# ==========================================================
# PAÍSES
# API OFICIAL:
# /cities/filters/country
# ==========================================================

@st.cache_data(ttl=86400)
def carregar_paises():

    data = api_get(
        "/cities/filters/country?language=pt"
    )

    valores = data.get(
        "data",
        []
    )

    # A API pode retornar listas dentro de listas
    lista = []

    def extrair(obj):

        if isinstance(obj, list):

            for item in obj:
                extrair(item)

        elif isinstance(obj, dict):

            if (
                "id" in obj
                and "text" in obj
            ):
                lista.append(obj)

    extrair(valores)

    if not lista:

        return pd.DataFrame(
            columns=[
                "id",
                "text"
            ]
        )

    df = pd.DataFrame(
        lista
    )

    return df.drop_duplicates(
        subset=["id"]
    )


# ==========================================================
# CARREGAR MUNICÍPIOS
# ==========================================================

try:

    municipios = carregar_municipios()

except Exception as erro:

    municipios = pd.DataFrame(
        columns=[
            "id",
            "text"
        ]
    )

    st.warning(
        f"Não foi possível carregar os municípios: {erro}"
    )


# ==========================================================
# CARREGAR PAÍSES
# ==========================================================

try:

    paises = carregar_paises()

except Exception as erro:

    paises = pd.DataFrame(
        columns=[
            "id",
            "text"
        ]
    )

    st.warning(
        f"Não foi possível carregar os países: {erro}"
    )


# ==========================================================
# SIDEBAR
# ==========================================================

st.sidebar.header(
    "🔎 Filtros da consulta"
)


# ==========================================================
# OPERAÇÃO
# ==========================================================

operacao = st.sidebar.selectbox(
    "Tipo de operação",
    [
        "Exportação",
        "Importação"
    ]
)


fluxo = (
    "export"
    if operacao == "Exportação"
    else "import"
)


# ==========================================================
# PERÍODO
# ==========================================================

hoje = date.today()

col1, col2 = st.sidebar.columns(2)

ano_inicio = col1.number_input(
    "Ano inicial",
    min_value=1997,
    max_value=hoje.year,
    value=hoje.year,
    step=1
)

mes_inicio = col2.number_input(
    "Mês inicial",
    min_value=1,
    max_value=12,
    value=max(
        1,
        hoje.month - 1
    ),
    step=1
)


col3, col4 = st.sidebar.columns(2)

ano_final = col3.number_input(
    "Ano final",
    min_value=1997,
    max_value=hoje.year,
    value=hoje.year,
    step=1
)

mes_final = col4.number_input(
    "Mês final",
    min_value=1,
    max_value=12,
    value=max(
        1,
        hoje.month - 1
    ),
    step=1
)


# ==========================================================
# VALIDAR PERÍODO
# ==========================================================

periodo_inicio = (
    int(ano_inicio),
    int(mes_inicio)
)

periodo_final = (
    int(ano_final),
    int(mes_final)
)


# ==========================================================
# MUNICÍPIO
# ==========================================================

opcoes_municipios = [
    "Todos os municípios"
]

if not municipios.empty:

    opcoes_municipios += sorted(
        municipios["text"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )


municipio_selecionado = st.sidebar.selectbox(
    "Município",
    opcoes_municipios
)


# ==========================================================
# PAÍS
# ==========================================================

opcoes_paises = [
    "Todos os países"
]

mapa_paises = {}

if not paises.empty:

    for _, linha in paises.iterrows():

        nome = str(
            linha["text"]
        )

        codigo = str(
            linha["id"]
        )

        opcoes_paises.append(
            nome
        )

        mapa_paises[
            nome
        ] = codigo


pais_selecionado = st.sidebar.selectbox(
    "País",
    opcoes_paises
)


# ==========================================================
# SH4
# ==========================================================

sh4 = st.sidebar.text_input(
    "SH4",
    placeholder="Ex.: 4412"
)

sh4 = "".join(
    c for c in sh4
    if c.isdigit()
)


# ==========================================================
# DETALHAMENTO
# ==========================================================

detalhar_mes = st.sidebar.checkbox(
    "Detalhar mês a mês",
    value=True
)


# ==========================================================
# BOTÃO
# ==========================================================

consultar = st.sidebar.button(
    "🔎 CONSULTAR",
    type="primary",
    use_container_width=True
)


# ==========================================================
# CONSULTA
# ==========================================================

if consultar:

    # ------------------------------------------------------
    # VALIDAR PERÍODO
    # ------------------------------------------------------

    if periodo_inicio > periodo_final:

        st.error(
            "O período inicial não pode ser maior "
            "que o período final."
        )

        st.stop()


    # ------------------------------------------------------
    # VALIDAR SH4
    # ------------------------------------------------------

    if sh4 and len(sh4) != 4:

        st.error(
            "O SH4 deve possuir exatamente 4 dígitos."
        )

        st.stop()


    # ------------------------------------------------------
    # FILTROS
    # ------------------------------------------------------

    filtros = []


    # MUNICÍPIO
    if municipio_selecionado != "Todos os municípios":

        municipio = municipios[
            municipios["text"]
            == municipio_selecionado
        ]

        if municipio.empty:

            st.error(
                "Município não encontrado."
            )

            st.stop()


        codigo_municipio = str(
            municipio.iloc[0]["id"]
        )

        filtros.append(
            {
                "filter": "city",
                "values": [
                    codigo_municipio
                ]
            }
        )


    # PAÍS
    if pais_selecionado != "Todos os países":

        codigo_pais = mapa_paises[
            pais_selecionado
        ]

        filtros.append(
            {
                "filter": "country",
                "values": [
                    codigo_pais
                ]
            }
        )


    # SH4
    if sh4:

        filtros.append(
            {
                "filter": "heading",
                "values": [
                    sh4
                ]
            }
        )


    # ------------------------------------------------------
    # PAYLOAD OFICIAL
    # ------------------------------------------------------

    payload = {

        "flow": fluxo,

        "monthDetail": detalhar_mes,

        "period": {

            "from":
                f"{int(ano_inicio):04d}-"
                f"{int(mes_inicio):02d}",

            "to":
                f"{int(ano_final):04d}-"
                f"{int(mes_final):02d}"
        },

        "filters": filtros,

        "details": [
            "country",
            "state",
            "city",
            "heading"
        ],

        "metrics": [
            "metricFOB",
            "metricKG"
        ]
    }


    # ------------------------------------------------------
    # MOSTRAR CONSULTA
    # ------------------------------------------------------

    with st.expander(
        "🔧 Consulta enviada para a API"
    ):

        st.json(
            payload
        )


    # ------------------------------------------------------
    # POST API OFICIAL
    # ------------------------------------------------------

    try:

        with st.spinner(
            "Consultando o Comex Stat..."
        ):

            resposta = requests.post(

                f"{BASE_URL}/cities?language=pt",

                json=payload,

                headers={
                    "Content-Type":
                        "application/json"
                },

                timeout=180
            )


        resposta.raise_for_status()

        resultado = resposta.json()


    except Exception as erro:

        st.error(
            f"Erro ao consultar a API: {erro}"
        )

        st.stop()


    # ------------------------------------------------------
    # VERIFICAR RESPOSTA
    # ------------------------------------------------------

    if resultado.get(
        "success"
    ) is False:

        st.error(
            resultado.get(
                "message",
                "A API retornou um erro."
            )
        )

        st.stop()


    dados = resultado.get(
        "data",
        {}
    )

    lista = dados.get(
        "list",
        []
    )


    if not lista:

        st.warning(
            "A API não encontrou dados para "
            "os filtros selecionados."
        )

        st.stop()


    # ------------------------------------------------------
    # DATAFRAME
    # ------------------------------------------------------

    df = pd.DataFrame(
        lista
    )


    # ------------------------------------------------------
    # CONVERSÕES
    # ------------------------------------------------------

    if "metricFOB" in df.columns:

        df["metricFOB"] = pd.to_numeric(
            df["metricFOB"],
            errors="coerce"
        )


    if "metricKG" in df.columns:

        df["metricKG"] = pd.to_numeric(
            df["metricKG"],
            errors="coerce"
        )


    # ------------------------------------------------------
    # RENOMEAR
    # ------------------------------------------------------

    df = df.rename(
        columns={
            "year": "Ano",
            "month": "Mês",
            "country": "País",
            "state": "UF",
            "city": "Município",
            "heading": "SH4",
            "metricFOB": "FOB (US$)",
            "metricKG": "Kg líquido"
        }
    )


    # ------------------------------------------------------
    # CÁLCULOS
    # ------------------------------------------------------

    if (
        "FOB (US$)" in df.columns
        and "Kg líquido" in df.columns
    ):

        kg = df[
            "Kg líquido"
        ].replace(
            0,
            pd.NA
        )


        # US$/KG

        df["US$/kg"] = (
            df["FOB (US$)"]
            / kg
        )


        # US$/TON

        df["US$/ton"] = (
            df["FOB (US$)"]
            / kg
            * 1000
        )


        # CONTÊINERES
        # 1 contêiner = 23.000 kg

        df["Contêineres"] = (
            df["Kg líquido"]
            / PESO_CONTAINER
        )


    # ------------------------------------------------------
    # TOTALIZADORES
    # ------------------------------------------------------

    total_fob = 0
    total_kg = 0


    if "FOB (US$)" in df.columns:

        total_fob = (
            df["FOB (US$)"]
            .sum()
        )


    if "Kg líquido" in df.columns:

        total_kg = (
            df["Kg líquido"]
            .sum()
        )


    total_containers = (
        total_kg
        / PESO_CONTAINER
    )


    us_ton = (

        total_fob
        / total_kg
        * 1000

        if total_kg > 0

        else 0
    )


    # ======================================================
    # CARDS
    # ======================================================

    st.subheader(
        "📊 Resumo da consulta"
    )


    c1, c2, c3, c4 = st.columns(4)


    c1.metric(
        "💵 FOB",
        f"US$ {total_fob:,.2f}"
    )


    c2.metric(
        "⚖️ Kg líquido",
        f"{total_kg:,.0f}"
    )


    c3.metric(
        "🚢 Contêineres",
        f"{total_containers:,.2f}"
    )


    c4.metric(
        "💰 US$/ton",
        f"US$ {us_ton:,.2f}"
    )


    # ======================================================
    # TABELA
    # ======================================================

    st.subheader(
        "📋 Resultado"
    )


    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


    # ======================================================
    # DOWNLOAD
    # ======================================================

    csv = df.to_csv(
        index=False
    ).encode(
        "utf-8-sig"
    )


    st.download_button(
        "⬇️ Baixar CSV",

        data=csv,

        file_name=
            "comex_resultado.csv",

        mime=
            "text/csv",

        use_container_width=True
    )


else:

    st.info(
        "👈 Selecione os filtros e clique "
        "em **CONSULTAR**."
    )


# ==========================================================
# RODAPÉ
# ==========================================================

st.caption(
    "Fonte: Comex Stat / MDIC — "
    "API oficial. Contêiner = 23.000 kg."
)
