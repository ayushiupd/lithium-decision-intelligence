"""Idempotently ingest validated USGS source-vintage rows into PostgreSQL."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "raw" / "usgs_lithium_country_year_structured_2010_2025_validated.csv"
COLUMNS = [
    "reporting_year", "country", "entity_type", "production_value", "production_raw_value",
    "source_cell_token_as_printed", "value_status", "original_unit", "estimate_status",
    "estimated_marker_present", "publication_year", "source_edition", "source_filename",
    "source_url", "pdf_page", "printed_page", "table_name", "table_heading_as_published",
    "footnote_marker", "footnote_definition", "source_row_text", "validation_status",
    "validation_note", "source_sha256", "source_file_path_in_workspace",
    "prior_raw_extraction_token", "prior_validation_status", "pdf_cell_token_extracted",
    "coordinate_cell_check_passed", "coordinate_check_note", "pdf_table_row_excerpt"
]

def db_url():
    # URL.create safely handles passwords containing special characters.
    return URL.create("postgresql+psycopg", username=os.getenv("PGUSER", "postgres"),
                      password=os.getenv("PGPASSWORD", ""), host=os.getenv("PGHOST", "localhost"),
                     port=int(os.getenv("PGPORT", "5433")),database=os.getenv("PGDATABASE", "lithium_mvp"))

def main():
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV), help="Validated source-vintage CSV path")
    args = parser.parse_args()
    csv_path = Path(args.csv).expanduser().resolve()
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}\nPlace the validated CSV at {DEFAULT_CSV} or pass --csv.")

    df = pd.read_csv(csv_path)
    missing = sorted(set(COLUMNS) - set(df.columns))
    if missing:
        raise SystemExit(f"Input CSV is missing expected columns: {missing}")
    df = df[COLUMNS].copy()
    # Preserve withheld W as NULL production_value; explicit dash/zero rows remain numeric zero.
    df["production_value"] = pd.to_numeric(df["production_value"], errors="coerce")
    for c in ["estimated_marker_present", "coordinate_cell_check_passed"]:
        df[c] = df[c].astype("boolean")
    for c in ["reporting_year", "publication_year", "pdf_page"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in ["printed_page"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.astype(object).where(pd.notna(df), None)

    engine = create_engine(db_url(), pool_pre_ping=True)
    schema_sql = (ROOT / "sql" / "schema.sql").read_text(encoding="utf-8")
    views_sql = (ROOT / "sql" / "views.sql").read_text(encoding="utf-8")
    target_columns = ", ".join(COLUMNS)
    bind_columns = ", ".join(f":{c}" for c in COLUMNS)
    updates = ",\n        ".join(f"{c}=EXCLUDED.{c}" for c in COLUMNS if c not in {"source_edition", "reporting_year", "country", "entity_type"})
    insert_sql = text(f"""
        INSERT INTO usgs.production_vintage ({target_columns})
        VALUES ({bind_columns})
        ON CONFLICT (source_edition, reporting_year, country, entity_type)
        DO UPDATE SET {updates}, ingested_at=now()
    """)
    records = df.to_dict(orient="records")

    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(schema_sql)
            # Parameterized batches preserve NULL, numeric, and boolean types without staging casts.
            for offset in range(0, len(records), 200):
                conn.execute(insert_sql, records[offset:offset + 200])
            conn.exec_driver_sql(views_sql)
            total = conn.execute(text("SELECT COUNT(*) FROM usgs.production_vintage")).scalar_one()
            current_editions = conn.execute(text("SELECT COUNT(DISTINCT source_edition) FROM usgs.production_vintage")).scalar_one()
            verified = conn.execute(text("SELECT COUNT(*) FROM usgs.production_vintage WHERE validation_status='verified'")).scalar_one()
            print(f"Import succeeded. Input rows processed: {len(df):,}")
            print(f"Rows currently stored in usgs.production_vintage: {total:,}")
            print(f"Verified rows currently stored: {verified:,}")
            print(f"Distinct publication editions in table: {current_editions:,}")
            print("Views created/refreshed: usgs.v_country_annual_latest, usgs.v_world_total_latest, usgs.v_country_annual_metrics")
    except Exception:
        print("Import failed; transaction rolled back. Check PostgreSQL service, credentials, port, database, and schema permissions.")
        raise
    finally:
        engine.dispose()

if __name__ == "__main__":
    main()
