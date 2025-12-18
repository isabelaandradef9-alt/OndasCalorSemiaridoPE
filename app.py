# ============================================================
# DASHBOARD INTERATIVO – ONDAS DE CALOR
# Semiárido Pernambucano
# ============================================================

import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import folium
from streamlit_folium import st_folium
import plotly.express as px
import os

# ============================================================
# CONFIG
# ============================================================

st.set_page_config(
    page_title="Ondas de Calor – Semiárido PE",
    layout="wide"
)

# ============================================================
# DADOS (usa DF já carregado, sem estourar RAM)
# ============================================================

@st.cache_data
def carregar_dados():

    dfs = []

    for micro, df_micro in DF_SERIES.items():
        df_tmp = df_micro.copy()

        # -------------------------------
        # Identificar coluna de data
        # -------------------------------
        possiveis_datas = [
            "data", "date", "DATA", "time",
            "system:time_start", "timestamp"
        ]

        col_data = None
        for c in possiveis_datas:
            if c in df_tmp.columns:
                col_data = c
                break

        if col_data is None:
            raise ValueError(
                f"❌ Nenhuma coluna de data encontrada para {micro}\n"
                f"Colunas: {list(df_tmp.columns)}"
            )

        # Converter data
        df_tmp["data"] = pd.to_datetime(df_tmp[col_data], unit="ms", errors="coerce")
        df_tmp = df_tmp.dropna(subset=["data"])

        # -------------------------------
        # Padronizar variável térmica
        # -------------------------------
        if "valor" not in df_tmp.columns:
            for c in df_tmp.columns:
                if "lst" in c.lower() or "temp" in c.lower():
                    df_tmp["valor"] = df_tmp[c]
                    break

        if "valor" not in df_tmp.columns:
            raise ValueError(f"❌ Nenhuma coluna de LST encontrada em {micro}")

        # Metadados espaciais
        df_tmp["NM_MICRO"] = micro
        df_tmp["mes"] = df_tmp["data"].dt.month

        dfs.append(df_tmp[["data", "valor", "mes", "NM_MICRO"]])

    # Concatena tudo
    df_final = pd.concat(dfs, ignore_index=True)

    return df_final

@st.cache_data
def carregar_shp():
    return gpd.read_file(
        os.path.join(PASTAS["MUNI"], "PE_Municipios_Semiarido.shp")
    )

# ============================================================
# FUNÇÕES DE ONDAS DE CALOR
# ============================================================

def identificar_eventos(df, percentil):
    limiar = np.percentile(df["valor"], percentil)

    df = df.sort_values("data").copy()
    df["acima"] = df["valor"] >= limiar
    df["grupo"] = (df["acima"] != df["acima"].shift()).cumsum()

    eventos = (
        df[df["acima"]]
        .groupby("grupo")
        .agg(
            inicio=("data", "min"),
            fim=("data", "max"),
            duracao=("data", "count"),
            intensidade_media=("valor", lambda x: (x - limiar).mean()),
            intensidade_max=("valor", lambda x: (x - limiar).max())
        )
        .query("duracao >= 3")
        .reset_index(drop=True)
    )

    return eventos

def resumo_eventos(eventos):
    if eventos.empty:
        return pd.Series({
            "num_eventos": 0,
            "duracao_media": 0,
            "duracao_max": 0,
            "intensidade_media": 0
        })

    return pd.Series({
        "num_eventos": len(eventos),
        "duracao_media": eventos["duracao"].mean(),
        "duracao_max": eventos["duracao"].max(),
        "intensidade_media": eventos["intensidade_media"].mean()
    })

# ============================================================
# INTERFACE
# ============================================================

st.title("🔥 Ondas de Calor no Semiárido Pernambucano")

df = carregar_dados()

st.sidebar.header("Filtros")

percentil = st.sidebar.selectbox(
    "Percentil (limiar extremo)",
    [90, 95, 97.5]
)

meses = st.sidebar.multiselect(
    "Meses analisados",
    options=list(range(1, 13)),
    default=[1, 2, 3]
)

# ============================================================
# PROCESSAMENTO
# ============================================================

df_filtro = df[df["mes"].isin(meses)]

resumo = []

for micro, grupo in df_filtro.groupby("NM_MICRO"):
    eventos = identificar_eventos(grupo, percentil)
    stats = resumo_eventos(eventos)
    stats["NM_MICRO"] = micro
    resumo.append(stats)

df_resumo = pd.DataFrame(resumo)

# ============================================================
# MAPA
# ============================================================

gdf = carregar_shp()
gdf = gdf.merge(df_resumo, on="NM_MICRO", how="left")

m = folium.Map(location=[-8.5, -37.5], zoom_start=7)

folium.Choropleth(
    geo_data=gdf,
    data=gdf,
    columns=["NM_MICRO", "num_eventos"],
    key_on="feature.properties.NM_MICRO",
    fill_color="Reds",
    fill_opacity=0.8,
    line_opacity=0.3,
    legend_name="Número de Ondas de Calor"
).add_to(m)

st.subheader("🗺️ Distribuição Espacial")
st_folium(m, width=1100, height=600)

# ============================================================
# INDICADORES
# ============================================================

st.subheader("📊 Indicadores Sintéticos")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Eventos", int(df_resumo["num_eventos"].sum()))
c2.metric("Duração Média (dias)", round(df_resumo["duracao_media"].mean(), 1))
c3.metric("Duração Máxima (dias)", int(df_resumo["duracao_max"].max()))
c4.metric("Intensidade Média (°C)", round(df_resumo["intensidade_media"].mean(), 2))

# ============================================================
# SAZONALIDADE
# ============================================================

st.subheader("📈 Sazonalidade da LST")

df_mes = df.groupby("mes")["valor"].mean().reset_index()

fig = px.line(
    df_mes,
    x="mes",
    y="valor",
    markers=True,
    labels={"mes": "Mês", "valor": "Temperatura Média (°C)"}
)

st.plotly_chart(fig, use_container_width=True)

# ============================================================
# TABELA
# ============================================================

st.subheader("📋 Resumo por Microrregião")
st.dataframe(df_resumo)
