
import requests
import pandas as pd
import streamlit as st
from datetime import date

BASE = "https://api-comexstat.mdic.gov.br"

st.set_page_config(page_title="Comex Bot", page_icon="📊", layout="wide")
st.title("📊 Comex Bot — Exportações por Município")
st.caption("Consulta a API oficial do Comex Stat/MDIC e calcula automaticamente US$/kg.")

@st.cache_data(ttl=86400)
def get_json(path, params=None):
    r = requests.get(BASE + path, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=86400)
def cities():
    j = get_json("/tables/cities")
    return pd.DataFrame(j.get("data", []))

@st.cache_data(ttl=86400)
def countries():
    j = get_json("/general/filters/country", {"language":"pt"})
    data = j.get("data", [])
    # API pode devolver uma lista simples ou uma lista aninhada.
    rows = []
    def walk(x):
        if isinstance(x, dict) and "id" in x and "text" in x:
            rows.append({"id": str(x["id"]), "text": x["text"]})
        elif isinstance(x, list):
            for y in x: walk(y)
        elif isinstance(x, dict):
            for y in x.values(): walk(y)
    walk(data)
    return pd.DataFrame(rows).drop_duplicates("id")

@st.cache_data(ttl=86400)
def query_api(payload):
    r = requests.post(
        BASE + "/cities?language=pt",
        json=payload,
        headers={"Content-Type":"application/json"},
        timeout=180,
    )
    r.raise_for_status()
    j = r.json()
    if not j.get("success", True):
        raise RuntimeError(j.get("message") or "A API retornou erro.")
    return j

def normalize_result(j):
    data = j.get("data", {})
    rows = data.get("list", []) if isinstance(data, dict) else data
    if not rows:
        return pd.DataFrame()
    df = pd.json_normalize(rows)

    # Nomes possíveis usados pela API.
    rename = {
        "year":"Ano", "month":"Mês", "country":"País", "city":"Município",
        "state":"UF", "heading":"SH4", "sh4":"SH4",
        "metricFOB":"FOB (US$)", "metricKG":"Kg líquido",
        "fob":"FOB (US$)", "kg":"Kg líquido",
    }
    df = df.rename(columns=rename)

    # Alguns retornos trazem as métricas dentro de campos com nomes diferentes.
    for c in df.columns:
        lc = c.lower()
        if "fob" in lc and "FOB (US$)" not in df.columns:
            df["FOB (US$)"] = pd.to_numeric(df[c], errors="coerce")
        if ("kg" in lc or "quilograma" in lc) and "Kg líquido" not in df.columns:
            df["Kg líquido"] = pd.to_numeric(df[c], errors="coerce")

    if "FOB (US$)" in df.columns:
        df["FOB (US$)"] = pd.to_numeric(df["FOB (US$)"], errors="coerce")
    if "Kg líquido" in df.columns:
        df["Kg líquido"] = pd.to_numeric(df["Kg líquido"], errors="coerce")

    if "FOB (US$)" in df.columns and "Kg líquido" in df.columns:
        df["US$/ton"] = (
    df["FOB (US$)"].div(df["Kg líquido"].replace(0, pd.NA)) * 1000
)

    return df

try:
    city_df = cities()
except Exception as e:
    st.error(f"Não consegui carregar a tabela de municípios: {e}")
    st.stop()

try:
    country_df = countries()
except Exception:
    country_df = pd.DataFrame(columns=["id","text"])

st.sidebar.header("Filtros")

c1, c2 = st.sidebar.columns(2)
year_from = c1.number_input("Ano inicial", 1997, date.today().year, date.today().year)
month_from = c2.number_input("Mês inicial", 1, 12, max(1, date.today().month-1))

c3, c4 = st.sidebar.columns(2)
year_to = c3.number_input("Ano final", 1997, date.today().year, date.today().year)
month_to = c4.number_input("Mês final", 1, 12, max(1, date.today().month-1))

city_options = ["Todos"] + sorted(city_df.get("text", pd.Series(dtype=str)).dropna().astype(str).tolist())
city = st.sidebar.selectbox("Município", city_options)

country_options = ["Todos"]
country_map = {}
if not country_df.empty:
    for _, r in country_df.iterrows():
        label = str(r["text"])
        country_options.append(label)
        country_map[label] = str(r["id"])
country = st.sidebar.selectbox("País de destino", country_options)

sh4 = st.sidebar.text_input("Posição SH4", placeholder="Ex.: 4412").strip()
month_detail = st.sidebar.checkbox("Detalhar mês a mês", value=True)

consult = st.sidebar.button("🔎 CONSULTAR", type="primary", use_container_width=True)

if consult:
    if (year_from, month_from) > (year_to, month_to):
        st.error("O período inicial não pode ser maior que o final.")
        st.stop()

    filters = []
    if country != "Todos":
        filters.append({"filter":"country", "values":[country_map[country]]})

    # O endpoint de municípios usa o código IBGE do município.
    if city != "Todos":
        row = city_df[city_df["text"].astype(str) == city].iloc[0]
        city_id = str(row["id"])
        filters.append({"filter":"city", "values":[city_id]})

    if sh4:
        sh4_clean = "".join(ch for ch in sh4 if ch.isdigit())
        if len(sh4_clean) != 4:
            st.error("Informe o SH4 com exatamente 4 dígitos.")
            st.stop()
        filters.append({"filter":"heading", "values":[sh4_clean]})

    payload = {
        "flow":"export",
        "monthDetail":month_detail,
        "period":{
            "from":f"{int(year_from):04d}-{int(month_from):02d}",
            "to":f"{int(year_to):04d}-{int(month_to):02d}"
        },
        "filters":filters,
        "details":["country","city","heading"],
        "metrics":["metricFOB","metricKG"]
    }

    with st.spinner("Consultando o Comex Stat..."):
        try:
            result = query_api(payload)
            df = normalize_result(result)
        except Exception as e:
            st.error(f"Erro na consulta: {e}")
            st.stop()

    if df.empty:
        st.warning("Nenhum resultado encontrado com esses filtros.")
        st.stop()

    st.success(f"{len(df):,} linhas retornadas.".replace(",", "."))

    # Garante que o cálculo agregado também exista.
    if "FOB (US$)" in df.columns and "Kg líquido" in df.columns:
        total_fob = df["FOB (US$)"].sum(skipna=True)
        total_kg = df["Kg líquido"].sum(skipna=True)
        avg = (total_fob / total_kg * 1000) if total_kg else None

        a,b,c = st.columns(3)
        a.metric("FOB total", f"US$ {total_fob:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
        b.metric("Kg líquido", f"{total_kg:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
        c.metric("US$/ton", "—" if avg is None else f"US$ {avg:,.4f}".replace(",", "X").replace(".", ",").replace("X","."))

    st.dataframe(df, use_container_width=True, hide_index=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("⬇️ Baixar CSV", csv, "comex_resultado.csv", "text/csv")

    xlsx_path = "comex_resultado.xlsx"
    df.to_excel(xlsx_path, index=False)
    with open(xlsx_path, "rb") as f:
        st.download_button(
            "⬇️ Baixar Excel",
            f.read(),
            "comex_resultado.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
else:
    st.info("Escolha os filtros à esquerda e clique em CONSULTAR.")
    st.markdown("""
### O que este bot faz
- Exportações por município
- Filtro por período/mês
- Filtro por país de destino
- Filtro por município
- Filtro por posição SH4
- Retorna FOB e quilograma líquido
- Calcula **US$/kg = FOB ÷ kg**
- Permite baixar CSV e Excel

Os dados são consultados diretamente na API do Comex Stat.
""")
