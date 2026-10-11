-- 1. Latest-vintage global trend (USGS world total excludes US production per source footnotes)
SELECT reporting_year, world_total_ex_us, publication_year, source_edition
FROM usgs.v_world_total_latest ORDER BY reporting_year;

-- 2. Latest-vintage country comparison for a selected year
SELECT country, production_value, value_status, source_edition, publication_year
FROM usgs.v_country_annual_latest
WHERE reporting_year = :reporting_year AND production_value IS NOT NULL
ORDER BY production_value DESC;

-- 3. Country year-over-year growth (only adjacent years with numeric prior/current values)
SELECT reporting_year, country, production_value, yoy_growth_pct, source_edition
FROM usgs.v_country_annual_metrics
WHERE country = :country ORDER BY reporting_year;

-- 4. Supply concentration by year: top 3 / top 5 shares among numeric country rows.
-- This is concentration among reported country values, not a share of USGS world total.
WITH ranked AS (
  SELECT reporting_year, country, production_value,
         ROW_NUMBER() OVER (PARTITION BY reporting_year ORDER BY production_value DESC) AS rank,
         SUM(production_value) OVER (PARTITION BY reporting_year) AS reported_country_sum
  FROM usgs.v_country_annual_latest
  WHERE production_value IS NOT NULL AND production_value >= 0
)
SELECT reporting_year,
       100.0 * SUM(production_value) FILTER (WHERE rank <= 3) / NULLIF(MAX(reported_country_sum),0) AS top3_share_pct,
       100.0 * SUM(production_value) FILTER (WHERE rank <= 5) / NULLIF(MAX(reported_country_sum),0) AS top5_share_pct
FROM ranked GROUP BY reporting_year ORDER BY reporting_year;

-- 5. Inspect source vintages/revisions for one country-year
SELECT reporting_year, country, production_value, production_raw_value, value_status,
       publication_year, source_edition, source_filename, source_url, pdf_page, printed_page
FROM usgs.production_vintage
WHERE country = :country AND reporting_year = :reporting_year
ORDER BY publication_year;

-- 6. Coverage and missingness summary by publication edition
SELECT source_edition, publication_year, COUNT(*) AS rows,
       COUNT(*) FILTER (WHERE value_status='numeric') AS numeric_rows,
       COUNT(*) FILTER (WHERE value_status='zero') AS explicit_zero_rows,
       COUNT(*) FILTER (WHERE value_status='withheld') AS withheld_rows,
       COUNT(*) FILTER (WHERE validation_status='verified') AS verified_rows
FROM usgs.production_vintage GROUP BY source_edition, publication_year ORDER BY publication_year;
