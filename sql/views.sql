-- One latest available publication vintage per reporting-year/country.
-- World totals and the 'Other countries' aggregate are excluded from this country-level view.
-- NULL production remains NULL (e.g. USGS W = withheld); no missing country-years are imputed.
CREATE OR REPLACE VIEW usgs.v_country_annual_latest AS
WITH ranked AS (
    SELECT p.*,
           ROW_NUMBER() OVER (
             PARTITION BY reporting_year, country
             ORDER BY publication_year DESC, source_edition DESC
           ) AS vintage_rank
    FROM usgs.production_vintage p
    WHERE entity_type = 'country'
)
SELECT reporting_year, country, production_value, production_raw_value, value_status,
       original_unit, estimate_status, estimated_marker_present,
       publication_year, source_edition, source_filename, source_url,
       pdf_page, printed_page, footnote_marker, footnote_definition,
       validation_status, source_sha256
FROM ranked
WHERE vintage_rank = 1;

CREATE OR REPLACE VIEW usgs.v_world_total_latest AS
WITH ranked AS (
    SELECT p.*,
           ROW_NUMBER() OVER (
             PARTITION BY reporting_year
             ORDER BY publication_year DESC, source_edition DESC
           ) AS vintage_rank
    FROM usgs.production_vintage p
    WHERE entity_type = 'world_total'
)
SELECT reporting_year, production_value AS world_total_ex_us, production_raw_value,
       value_status, original_unit, publication_year, source_edition, source_filename,
       source_url, pdf_page, printed_page, footnote_definition, validation_status
FROM ranked
WHERE vintage_rank = 1;

CREATE OR REPLACE VIEW usgs.v_country_annual_metrics AS
WITH country_values AS (
  SELECT reporting_year, country, production_value, value_status, publication_year, source_edition
  FROM usgs.v_country_annual_latest
), lagged AS (
  SELECT *, LAG(production_value) OVER (PARTITION BY country ORDER BY reporting_year) AS prior_year_value,
            LAG(reporting_year) OVER (PARTITION BY country ORDER BY reporting_year) AS prior_reporting_year
  FROM country_values
)
SELECT reporting_year, country, production_value, value_status, publication_year, source_edition,
       CASE WHEN prior_reporting_year = reporting_year - 1 AND prior_year_value IS NOT NULL
                  AND prior_year_value <> 0 AND production_value IS NOT NULL
            THEN 100.0 * (production_value - prior_year_value) / prior_year_value END AS yoy_growth_pct
FROM lagged;
