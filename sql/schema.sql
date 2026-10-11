-- Run against the existing PostgreSQL database named lithium.
CREATE SCHEMA IF NOT EXISTS usgs;

CREATE TABLE IF NOT EXISTS usgs.production_vintage (
    production_id BIGSERIAL PRIMARY KEY,
    reporting_year INTEGER NOT NULL CHECK (reporting_year BETWEEN 1900 AND 2100),
    country TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (entity_type IN ('country','world_total','aggregate_other')),
    production_value NUMERIC(14,2),
    production_raw_value TEXT NOT NULL,
    source_cell_token_as_printed TEXT NOT NULL,
    value_status TEXT NOT NULL CHECK (value_status IN ('numeric','withheld','zero','unavailable','other')),
    original_unit TEXT NOT NULL,
    estimate_status TEXT NOT NULL,
    estimated_marker_present BOOLEAN NOT NULL,
    publication_year INTEGER NOT NULL,
    source_edition TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    source_url TEXT NOT NULL,
    pdf_page INTEGER,
    printed_page NUMERIC(10,2),
    table_name TEXT,
    table_heading_as_published TEXT,
    footnote_marker TEXT,
    footnote_definition TEXT,
    source_row_text TEXT,
    validation_status TEXT NOT NULL,
    validation_note TEXT,
    source_sha256 TEXT NOT NULL,
    source_file_path_in_workspace TEXT,
    prior_raw_extraction_token TEXT,
    prior_validation_status TEXT,
    pdf_cell_token_extracted TEXT,
    coordinate_cell_check_passed BOOLEAN,
    coordinate_check_note TEXT,
    pdf_table_row_excerpt TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_production_source_vintage UNIQUE (source_edition, reporting_year, country, entity_type)
);

CREATE INDEX IF NOT EXISTS ix_production_vintage_year ON usgs.production_vintage(reporting_year);
CREATE INDEX IF NOT EXISTS ix_production_vintage_country_year ON usgs.production_vintage(country, reporting_year);
CREATE INDEX IF NOT EXISTS ix_production_vintage_edition ON usgs.production_vintage(source_edition, publication_year);
