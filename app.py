import requests
import pandas as pd
import streamlit as st
from datetime import date


BASE = "https://api-comexstat.mdic.gov.br"


# =========================================================
# CONFIGURAÇÃO
# =========================================================

st.set_page_config(
    page_title="Comex Bot",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Comex Bot — Exportações por Município")
st.caption(
    "Consulta a API oficial do Comex Stat/MDIC "
    "e calcula automaticamente US$/kg, US$/ton e contêineres."
)


# =========================================================
# FUNÇÃO PARA CONSULTAR API
# =========================================================

@st.cache_data(ttl=86400)
def get_json(path, params=None):
    r = requests.get(
        BASE + path,
        params=params,
        timeout=60
    )

    r.raise_for_status()

    return r.json()


# =========================================================
# MUNICÍPIOS
# =========================================================

@st.cache_data(ttl=86400)
def cities():

    j = get_json("/tables/cities")

    return pd.DataFrame(
        j.get("data", [])
    )


# =========================================================
# PAÍSES
# =========================================================

@st.cache_data(ttl=86400)
def countries():

    j = get_json(
        "/general/filters/country",
        {"language": "pt"}
    )

    data = j.get("data", [])

    rows = []

    def walk(x):

        if isinstance(x, dict):

            if "id" in x and "text" in x:

                rows.append({
                    "id": str(x["id"]),
                    "text": str(x["text"])
                })

            else:

                for y in x.values():
                    walk(y)

        elif isinstance(x, list):

            for y in x:
                walk(y)

    walk(data)

    return pd.DataFrame(rows).drop_duplicates("id")


# =========================================================
# CONSULTA PRINCIPAL
# =========================================================

@st.cache_data(ttl=86400)
def query_api(payload):

    r = requests.post(
        BASE + "/cities?language=pt",
        json=payload,
        headers={
            "Content-Type": "application/json"
        },
        timeout=180
    )

    r.raise_for_status()

    j = r.json()

    if not j.get("success", True):

        raise RuntimeError(
            j.get("message")
            or "A API retornou erro."
        )

    return j


# =========================================================
# NORMALIZAR RESULTADO
# =========================================================

def normalize_result(j):

    data = j.get("data", {})

    rows = (
        data.get("list", [])
        if isinstance(data, dict)
        else data
    )

    if not rows:

        return pd.DataFrame()

    df = pd.json_normalize(rows)

    rename = {

        "year": "Ano",
        "month": "Mês",
        "country": "País",
        "city": "Município",
        "state": "UF",
        "heading": "SH4",
        "sh4": "SH4",

        "metricFOB": "FOB (US$)",
        "metricKG": "Kg líquido",

        "fob": "FOB (US$)",
        "kg": "Kg líquido",
    }

    df = df.rename(columns=rename)

    # Procurar FOB caso venha com outro nome
    for c in df.columns:

        lc = str(c).lower()

        if (
            "fob" in lc
            and "FOB (US$)" not in df.columns
        ):

            df["FOB (US$)"] = pd.to_numeric(
                df[c],
                errors="coerce"
            )

        if (
            ("kg" in lc or "quilograma" in lc)
            and "Kg líquido" not in df.columns
        ):

            df["Kg líquido"] = pd.to_numeric(
                df[c],
                errors="coerce"
            )

    # Converter valores para número
    if "FOB (US$)" in df.columns:

        df["FOB (US$)"] = pd.to_numeric(
            df["FOB (US$)"],
            errors="coerce"
        )

    if "Kg líquido" in df.columns:

        df["Kg líquido"] = pd.to_numeric(
            df["Kg líquido"],
            errors="coerce"
        )

    # =====================================================
    # US$/TON
    # =====================================================

    if (
        "FOB (US$)" in df.columns
        and "Kg líquido" in df.columns
    ):

        kg = df["Kg líquido"].replace(0, pd.NA)

        df["US$/ton"] = (
            df["FOB (US$)"]
            .div(kg)
            * 1000
        )

    return df


# =========================================================
# CARREGAR MUNICÍPIOS
# =========================================================

try:

    city_df = cities()

except Exception as e:

    st.error(
        f"Não consegui carregar a tabela de municípios: {e}"
    )

    st.stop()


# =========================================================
# CARREGAR PAÍSES
# =========================================================

try:

    country_df = countries()

except Exception:

    country_df = pd.DataFrame(
        columns=["id", "text"]
    )


# =========================================================
# SIDEBAR
# =========================================================

st.sidebar.header("🔎 Filtros")


c1, c2 = st.sidebar.columns(2)

year_from = c1.number_input(
    "Ano inicial",
    1997,
    date.today().year,
    date.today().year
)

month_from = c2.number_input(
    "Mês inicial",
    1,
    12,
    max(1, date.today().month - 1)
)


c3, c4 = st.sidebar.columns(2)

year_to = c3.number_input(
    "Ano final",
    1997,
    date.today().year,
    date.today().year
)

month_to = c4.number_input(
    "Mês final",
    1,
    12,
    max(1, date.today().month - 1)
)


# =========================================================
# MUNICÍPIO
# =========================================================

city_options = [
    "Todos"
] + sorted(
    city_df
    .get(
        "text",
        pd.Series(dtype=str)
    )
    .dropna()
    .astype(str)
    .tolist()
)


city = st.sidebar.selectbox(
    "Município",
    city_options
)


# =========================================================
# PAÍS
# =========================================================

country_options = ["Todos"]

country_map = {}


if not country_df.empty:

    for _, r in country_df.iterrows():

        label = str(r["text"])

        country_options.append(label)

        country_map[label] = str(r["id"])


country = st.sidebar.selectbox(
    "País de destino",
    country_options
)


# =========================================================
# SH4
# =========================================================

sh4 = st.sidebar.text_input(
    "Posição SH4",
    placeholder="Ex.: 4412"
).strip()


# =========================================================
# DETALHAMENTO
# =========================================================

month_detail = st.sidebar.checkbox(
    "Detalhar mês a mês",
    value=True
)


# =========================================================
# BOTÃO CONSULTAR
# =========================================================

consult = st.sidebar.button(
    "🔎 CONSULTAR",
    type="primary",
    use_container_width=True
)


# =========================================================
# EXECUTAR CONSULTA
# =========================================================

if consult:

    # -----------------------------------------------------
    # VALIDAR PERÍODO
    # -----------------------------------------------------

    if (year_from, month_from) > (year_to, month_to):

        st.error(
            "O período inicial não pode ser maior que o final."
        )

        st.stop()


    # -----------------------------------------------------
    # FILTROS
    # -----------------------------------------------------

    filters = []


    # País
    if country != "Todos":

        filters.append({
            "filter": "country",
            "values": [
                country_map[country]
            ]
        })


    # Município
    if city != "Todos":

        city_rows = city_df[
            city_df["text"]
            .astype(str)
            == city
        ]

        if city_rows.empty:

            st.error(
                "Não foi possível localizar o código do município."
            )

            st.stop()

        row = city_rows.iloc[0]

        city_id = str(row["id"])

        filters.append({
            "filter": "city",
            "values": [city_id]
        })


    # SH4
    if sh4:

        sh4_clean = "".join(
            ch for ch in sh4
            if ch.isdigit()
        )

        if len(sh4_clean) != 4:

            st.error(
                "Informe o SH4 com exatamente 4 dígitos."
            )

            st.stop()

        filters.append({
            "filter": "heading",
            "values": [sh4_clean]
        })


    # -----------------------------------------------------
    # PAYLOAD
    # -----------------------------------------------------

    payload = {

        "flow": "export",

        "monthDetail": month_detail,

        "period": {

            "from": (
                f"{int(year_from):04d}-"
                f"{int(month_from):02d}"
            ),

            "to": (
                f"{int(year_to):04d}-"
                f"{int(month_to):02d}"
            )
        },

        "filters": filters,

        "details": [
            "country",
            "city",
            "heading"
        ],

        "metrics": [
            "metricFOB",
            "metricKG"
        ]
    }


    # -----------------------------------------------------
    # CONSULTAR API
    # -----------------------------------------------------

    with st.spinner(
        "Consultando o Comex Stat..."
    ):

        try:

            result = query_api(payload)

            df = normalize_result(result)

        except Exception as e:

            st.error(
                f"Erro na consulta: {e}"
            )

            st.stop()


    # -----------------------------------------------------
    # VERIFICAR RESULTADO
    # -----------------------------------------------------

    if df.empty:

        st.warning(
            "Nenhum resultado encontrado com esses filtros."
        )

        st.stop()


    # -----------------------------------------------------
    # MENSAGEM DE SUCESSO
    # -----------------------------------------------------

    st.success(
        f"{len(df):,} linhas retornadas."
        .replace(",", ".")
    )


    # =====================================================
    # CÁLCULOS
    # =====================================================

    if (
        "FOB (US$)" not in df.columns
        or "Kg líquido" not in df.columns
    ):

        st.error(
            "A API não retornou as colunas "
            "'FOB (US$)' e/ou 'Kg líquido'."
        )

        st.stop()


    # -----------------------------------------------------
    # GARANTIR NÚMEROS
    # -----------------------------------------------------

    df["FOB (US$)"] = pd.to_numeric(
        df["FOB (US$)"],
        errors="coerce"
    )

    df["Kg líquido"] = pd.to_numeric(
        df["Kg líquido"],
        errors="coerce"
    )


    # -----------------------------------------------------
    # TOTAIS
    # -----------------------------------------------------

    total_fob = df["FOB (US$)"].sum(
        skipna=True
    )

    total_kg = df["Kg líquido"].sum(
        skipna=True
    )


    # =====================================================
    # NOVA COLUNA CONTÊINER
    # =====================================================

    # Cada contêiner = 23.000 kg

    df["Contêiner"] = (
        df["Kg líquido"] / 23000
    )


    # =====================================================
    # US$/TON
    # =====================================================

    if total_kg and total_kg > 0:

        avg = (
            total_fob
            / total_kg
            * 1000
        )

    else:

        avg = None


    # =====================================================
    # RESUMO
    # =====================================================

    a, b, c, d = st.columns(4)


    # FOB
    a.metric(
        "FOB total",

        f"US$ {total_fob:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


    # KG
    b.metric(
        "Kg líquido",

        f"{total_kg:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


    # US$/TON
    c.metric(

        "US$/ton",

        "-"
        if avg is None
        else
        (
            f"US$ {avg:,.4f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    )


    # CONTÊINERES
    total_container = (
        total_kg / 23000
        if total_kg
        else 0
    )


    d.metric(
        "Contêineres",
        f"{total_container:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )


    # =====================================================
    # TABELA
    # =====================================================

    st.subheader(
        "📋 Resultado da consulta"
    )


    st.dataframe(
        df,
        width="stretch",
        hide_index=True
    )


    # =====================================================
    # DOWNLOAD CSV
    # =====================================================

    csv = (
        df
        .to_csv(index=False)
        .encode("utf-8-sig")
    )


    st.download_button(

        "📥 Baixar CSV",

        csv,

        "comex_resultado.csv",

        "text/csv"
    )


    # =====================================================
    # DOWNLOAD EXCEL
    # =====================================================

    xlsx_path = "comex_resultado.xlsx"


    df.to_excel(
        xlsx_path,
        index=False
    )


    with open(
        xlsx_path,
        "rb"
    ) as f:

        st.download_button(

            "⬇️ Baixar Excel",

            f.read(),

            "comex_resultado.xlsx",

            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )