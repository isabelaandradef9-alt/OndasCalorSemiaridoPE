import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import plotly.express as px
import folium
from streamlit_folium import st_folium
import os

st.set_page_config(layout="wide", page_title="Ondas de Calor – Semiárido")

# ===============================
# DADOS
# ===============================
@st.cache_data
def load_data():
    df = pd.read_csv("data/ondas_calor_completo.csv")

    # converter datas
    df["start"] = pd.to_datetime(df["start"], errors="coerce")
    df["end"]   = pd.to_datetime(df["end"], errors="coerce")

    # remover eventos inválidos
    df = df.dropna(subset=["start", "microrregiao"])

    # criar variáveis temporais a partir do INÍCIO do evento
    df["ano"] = df["start"].dt.year
    df["mes"] = df["start"].dt.month

    return df
    
df = load_data()

@st.cache_data
def load_geodata():
    gdf_micro = gpd.read_file("data/microrregioes.shp")
    gdf_muni  = gpd.read_file("data/municipios.shp")

    # garantir CRS (folium usa EPSG:4326)
    gdf_micro = gdf_micro.to_crs(epsg=4326)
    gdf_muni  = gdf_muni.to_crs(epsg=4326)

    return gdf_micro, gdf_muni


gdf_micro, gdf_muni = load_geodata()

# ===============================
# SIDEBAR
# ===============================
st.sidebar.title("Filtros")

escala = st.sidebar.radio("Escala espacial", ["Microrregião", "Município"])
percentil = st.sidebar.selectbox("Percentil", [90, 95, 97.5])

meses = st.sidebar.multiselect(
    "Meses",
    options=list(range(1,13)),
    default=[1,2,3,4,5,6,7,8,9,10,11,12]
)

ano_min = int(df["ano"].min())
ano_max = int(df["ano"].max())

anos = st.sidebar.slider(
    "Período",
    ano_min,
    ano_max,
    (ano_min, ano_max)
)

# ===============================
# FILTRAGEM
# ===============================
df_f = df[
    (df["percentil"] == percentil) &
    (df["mes"].isin(meses)) &
    (df["ano"].between(anos[0], anos[1]))
]

if escala == "Microrregião":
    geo = gdf_micro
    chave = "microrregiao"
else:
    geo = gdf_muni
    chave = "municipio"

stats = (
    df_f
    .groupby(chave)
    .agg(
        eventos=("evento_id", "nunique"),
        duracao_media=("duracao", "mean"),
        intensidade_media=("intensidade", "mean")
    )
    .reset_index()
)

geo = geo.merge(stats, left_on="NM_MICRO" if escala=="Microrregião" else "NM_MUNICIP",
                right_on=chave, how="left")

# ===============================
# MAPA
# ===============================
st.title("Ondas de Calor no Semiárido Brasileiro")

m = folium.Map(location=[-8.5, -38.5], zoom_start=6, tiles="cartodbpositron")

geo = geo.reset_index()

folium.Choropleth(
    geo_data=geo,
    data=geo,
    columns=["index", "eventos"],
    key_on="feature.id",
    fill_color="YlOrRd",
    fill_opacity=0.7,
    line_opacity=0.3,
    legend_name="Número de eventos de onda de calor"
).add_to(m)

st_folium(m, width=1200, height=600)

# ===============================
# INDICADORES
# ===============================
c1, c2, c3 = st.columns(3)

c1.metric("Eventos (médio)", round(stats.eventos.mean(), 1))
c2.metric("Duração média (dias)", round(stats.duracao_media.mean(), 1))
c3.metric("Intensidade média (°C)", round(stats.intensidade_media.mean(), 1))
