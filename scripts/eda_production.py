"""Generate reproducible EDA outputs from the latest available USGS vintage per country-year."""
from pathlib import Path
import pandas as pd
import plotly.express as px

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "raw" / "usgs_lithium_country_year_structured_2010_2025_validated.csv"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

def main():
    df = pd.read_csv(INPUT)
    df = df[df.entity_type.eq("country")].copy()
    # One latest publication vintage per country/reporting year. Keep withheld as NA.
    df = df.sort_values(["reporting_year", "country", "publication_year", "source_edition"])
    latest = df.drop_duplicates(["reporting_year", "country"], keep="last").copy()
    numeric = latest[latest.production_value.notna()].copy()
    numeric.to_csv(OUT / "country_year_latest_numeric.csv", index=False)

    global_summary = numeric.groupby("reporting_year", as_index=False).agg(
        numeric_country_rows=("country", "nunique"), reported_country_sum=("production_value", "sum"),
        source_vintages=("source_edition", "nunique"))
    global_summary.to_csv(OUT / "reported_country_sum_by_year.csv", index=False)

    yoy = numeric.sort_values(["country", "reporting_year"]).copy()
    yoy["prior_year"] = yoy.groupby("country").reporting_year.shift(1)
    yoy["prior_production"] = yoy.groupby("country").production_value.shift(1)
    yoy["yoy_growth_pct"] = ((yoy.production_value / yoy.prior_production) - 1) * 100
    yoy.loc[(yoy.reporting_year - yoy.prior_year != 1) | (yoy.prior_production == 0), "yoy_growth_pct"] = pd.NA
    yoy.to_csv(OUT / "country_yoy_growth.csv", index=False)

    conc = []
    for year, g in numeric.groupby("reporting_year"):
        vals = g.sort_values("production_value", ascending=False)
        denom = vals.production_value.sum()
        rec = {"reporting_year": int(year), "numeric_countries": int(vals.country.nunique()), "reported_country_sum": denom}
        for n in (3, 5):
            rec[f"top{n}_share_pct"] = vals.head(n).production_value.sum() / denom * 100 if denom else pd.NA
        conc.append(rec)
    concentration = pd.DataFrame(conc)
    concentration.to_csv(OUT / "supply_concentration.csv", index=False)

    fig = px.line(global_summary, x="reporting_year", y="reported_country_sum", markers=True,
                  title="Sum of numeric country rows by reporting year (latest available vintages)",
                  labels={"reporting_year":"Reporting year", "reported_country_sum":"Metric tons of lithium content"})
    fig.write_html(OUT / "reported_country_sum_trend.html", include_plotlyjs="cdn")
    print(f"Latest-vintage rows: {len(latest):,}; numeric rows: {len(numeric):,}; withheld/missing numeric values retained separately: {latest.production_value.isna().sum():,}")
    print(f"EDA outputs written to: {OUT}")
    print("Note: reported-country sums are not the USGS world total; country coverage and source vintages vary.")

if __name__ == "__main__":
    main()
