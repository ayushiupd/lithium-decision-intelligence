import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_CONFIG

st.set_page_config(
    page_title="Lithium Decision Intelligence",
    page_icon="🔋",
    layout="wide",
)


@st.cache_resource
def get_engine():
    url = URL.create(
        "postgresql+psycopg",
        username=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
    )
    return create_engine(url, pool_pre_ping=True)


@st.cache_data(ttl=120)
def load_data():
    with get_engine().connect() as conn:
        countries = pd.read_sql(text("SELECT * FROM usgs.v_country_annual_latest ORDER BY reporting_year, country"), conn)
        worlds = pd.read_sql(text("SELECT * FROM usgs.v_world_total_latest ORDER BY reporting_year"), conn)
        metrics = pd.read_sql(text("SELECT * FROM usgs.v_country_annual_metrics ORDER BY reporting_year, country"), conn)
        counts = pd.read_sql(text("SELECT COUNT(*) AS rows, COUNT(*) FILTER (WHERE validation_status='verified') AS verified, COUNT(*) FILTER (WHERE value_status='withheld') AS withheld, COUNT(DISTINCT source_edition) AS editions FROM usgs.production_vintage"), conn).iloc[0]
    return countries, worlds, metrics, counts

st.title("🔋 Lithium Decision Intelligence Platform")
st.caption("Production analytics MVP • USGS Mineral Commodity Summaries • 2010–2025 • source-vintage aware")
st.info("This dashboard uses USGS lithium production data only. It does not yet combine EV demand, trade, prices, reserves, or forecasts.")
try:
    country_df, world_df, metrics_df, counts = load_data()
except Exception as exc:
    st.error("Could not connect to the configured PostgreSQL database or read the USGS views.")
    st.code(
    "Configure database credentials in the root config.py / .env file.\n"
    "Default database: postgres\n"
    "Current local database: lithium_mvp")
    st.write("Run `sql/schema.sql` and `sql/views.sql` through `python scripts/ingest_production.py` after configuring `.env`.")
    st.caption(f"Technical detail: {type(exc).__name__}: {exc}")
    st.stop()

numeric_country = country_df[country_df.production_value.notna()].copy()
world_numeric = world_df[world_df.world_total_ex_us.notna()].copy()
latest_year = int(country_df.reporting_year.max()) if not country_df.empty else 2025
latest_rows = numeric_country[numeric_country.reporting_year.eq(latest_year)]
latest_world = world_numeric[world_numeric.reporting_year.eq(latest_year)]

c1,c2,c3,c4 = st.columns(4)
c1.metric("Source-vintage rows", f"{int(counts['rows']):,}")
c2.metric("Verified rows", f"{int(counts['verified']):,}")
c3.metric("Publication editions", f"{int(counts['editions']):,}")
c4.metric("Latest reporting year", str(latest_year))
if not latest_world.empty:
    st.caption(f"Latest published world total excluding U.S. production: {latest_world.iloc[-1].world_total_ex_us:,.0f} metric tons (edition {latest_world.iloc[-1].source_edition}).")

with st.sidebar:
    st.header("Explore production")
    years = sorted(country_df.reporting_year.dropna().astype(int).unique().tolist())
    selected_year = st.select_slider("Reporting year", options=years, value=years[-1] if years else 2025)
    countries = sorted(numeric_country.country.dropna().unique().tolist())
    default_countries = [c for c in ["Australia", "Chile", "China", "Argentina", "Zimbabwe", "Canada"] if c in countries]
    selected_countries = st.multiselect("Countries for trend comparison", countries, default=default_countries)
    top_n = st.slider("Countries in ranking", min_value=3, max_value=10, value=5)

left,right = st.columns([1.25,1])
with left:
    st.subheader("Reported world total by year")
    if world_numeric.empty:
        st.warning("No numeric world totals are available in the imported rows.")
    else:
        fig = px.line(world_numeric, x="reporting_year", y="world_total_ex_us", markers=True,
                      hover_data=["source_edition","publication_year"],
                      labels={"reporting_year":"Reporting year","world_total_ex_us":"Metric tons (ex-U.S.)"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption("World total is rounded and excludes U.S. production per edition-specific USGS footnotes.")
with right:
    st.subheader(f"Country ranking • {selected_year}")
    rank = numeric_country[numeric_country.reporting_year.eq(selected_year)].sort_values("production_value", ascending=False).head(top_n)
    if rank.empty:
        st.warning("No numeric country values for this year.")
    else:
        fig = px.bar(rank.sort_values("production_value"), x="production_value", y="country", orientation="h",
                     color="production_value", labels={"production_value":"Metric tons","country":"Country"})
        st.plotly_chart(fig, use_container_width=True)

st.subheader("Country production trends")
trend = numeric_country[numeric_country.country.isin(selected_countries)]
if not trend.empty:
    fig = px.line(trend, x="reporting_year", y="production_value", color="country", markers=True,
                  hover_data=["source_edition","publication_year","value_status"],
                  labels={"reporting_year":"Reporting year","production_value":"Metric tons of lithium content"})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Select one or more countries with numeric production observations.")

st.subheader("Year-over-year growth")
growth_countries = st.multiselect("Countries for YoY view", countries, default=default_countries[:4], key="growth_countries")
growth = metrics_df[metrics_df.country.isin(growth_countries) & metrics_df.yoy_growth_pct.notna()].copy()
if not growth.empty:
    fig = px.line(growth, x="reporting_year", y="yoy_growth_pct", color="country", markers=True,
                  labels={"reporting_year":"Reporting year","yoy_growth_pct":"YoY growth (%)"})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.caption("YoY growth is shown only when both adjacent reporting years have numeric values and the prior value is non-zero.")

st.subheader("Supply concentration among reported country values")
concentration_rows = []
for year, group in numeric_country.groupby("reporting_year"):
    ordered = group.sort_values("production_value", ascending=False)
    denom = ordered.production_value.sum()
    if denom:
        concentration_rows.append({"reporting_year":year,"Top 3 share (%)":100*ordered.head(3).production_value.sum()/denom,
                                   "Top 5 share (%)":100*ordered.head(5).production_value.sum()/denom})
concentration = pd.DataFrame(concentration_rows)
if not concentration.empty:
    fig = px.line(concentration, x="reporting_year", y=["Top 3 share (%)","Top 5 share (%)"], markers=True)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Concentration denominator is the sum of numeric country rows in the latest available vintage, not the rounded USGS world total. Country coverage varies by year.")

with st.expander("Inspect source-vintage rows"):
    show = country_df[country_df.reporting_year.eq(selected_year)].sort_values("production_value", ascending=False, na_position="last")
    st.dataframe(show[["country","production_value","production_raw_value","value_status","estimate_status","source_edition","publication_year","source_filename","pdf_page","printed_page","source_url","validation_status"]], use_container_width=True, hide_index=True)
with st.expander("Latest USGS world-total source rows"):
    st.dataframe(world_df, use_container_width=True, hide_index=True)
st.caption("No missing country-year values are imputed. W/withheld values remain NULL and are excluded from numeric charts. Historical publication vintages remain stored in PostgreSQL.")
