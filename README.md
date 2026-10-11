# Lithium Decision Intelligence Platform — Production Analytics MVP

A source-vintage-aware Data Analytics MVP using validated USGS Mineral Commodity Summaries (MCS) lithium mine-production tables for reporting years 2010–2025. This is **not** an ML training project. The AI Strategy Desk can be added as a later layer after production, EV, trade and price datasets are integrated.

## What is included

- `data/raw/usgs_lithium_country_year_structured_2010_2025_validated.csv` — copied validated source-vintage dataset; do not overwrite it during analysis.
- `docs/usgs_lithium_data_quality_report_validated.txt` — extraction validation report.
- `sql/schema.sql` — `usgs.production_vintage` table and indexes.
- `sql/views.sql` — latest country-year, latest world total, and YoY metric views.
- `sql/queries/analytics.sql` — trend, country comparison, YoY, concentration, vintage audit, and quality queries.
- `scripts/ingest_production.py` — idempotent CSV-to-PostgreSQL ingestion; creates schema/table/views and reports counts only after commit.
- `scripts/eda_production.py` — reproducible CSV-based EDA outputs.
- `app/streamlit_app.py` — first Streamlit + Plotly dashboard.

## Dataset facts inspected before implementation

- 314 source-vintage rows, 31 columns, reporting years 2010–2025, 16 publication editions (MCS2011–MCS2026).
- Entity types: 269 country rows, 31 world-total rows, 14 `Other countries` aggregate rows.
- Statuses: 264 `numeric`, 20 explicit `zero`, 30 `withheld`; all 314 rows have `validation_status=verified` in the supplied validation report.
- `production_value` is NULL for the 30 withheld rows; explicit zero rows are numeric 0. No absent country-year is filled in.
- The validation report's phrase “Numeric values: 284” counts the 264 numeric-token rows plus 20 explicit-zero rows as numeric values. In this CSV, 284 values are non-NULL; 30 withheld values are NULL.
- All 314 coordinate-based PDF cell checks passed per the supplied report. This describes source transcription validation, not complete coverage of every country in every year.
- The original extraction was left untouched; this project copies the validated structured CSV.
## Database Configuration

The database configuration is defined in `config.py` in the project root. It loads connection settings from the local `.env` file.

Copy `.env.example` to `.env`, then enter your PostgreSQL username, password, and database name in `.env`.

- **Default username:** `postgres`
- **Default database name:** `postgres`
- **Host:** `localhost`
- **Port:** `5433`

For the existing local project database, set `PGDATABASE=lithium_mvp` in `.env`.

Never commit `.env` or share real database credentials.

## Docker Setup

Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and start it before building the Docker image. A `Dockerfile` must be present in the project root to build the image.
## 1. Windows setup

Open PowerShell and change into the project directory after extracting the ZIP:

```powershell
cd C:\path\to\lithium_decision_intelligence
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Edit `.env` with your actual PostgreSQL credentials. The existing setup previously noted for this project used host `localhost`, port `5433`, and database `lithium`; verify these are still correct. Do not commit `.env` or share its password.

If PowerShell blocks activation, run this once in the current PowerShell window, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 2. PostgreSQL setup and ingestion

Confirm PostgreSQL is running and the database already exists. The script deliberately does not create or drop the database.

```powershell
psql -h localhost -p 5433 -U postgres -d lithium -c "SELECT current_database(), version();"
python scripts\ingest_production.py
```

If your PostgreSQL username differs, change `PGUSER` in `.env`. Use your real password in `PGPASSWORD`.

The script will:
1. read and validate expected columns in the CSV;
2. create the `usgs` schema and source-vintage table if needed;
3. load rows into a staging table and upsert by `(source_edition, reporting_year, country, entity_type)`;
4. create/refresh analytical views in the same transaction;
5. print actual stored counts only if the transaction succeeds.

A failed import raises an error and rolls back the transaction. Re-running is safe and does not erase earlier editions. A repeated import updates the same source-edition key rather than adding duplicate rows.

Verify after a successful import:

```powershell
psql -h localhost -p 5433 -U postgres -d lithium -c "SELECT COUNT(*) AS rows, COUNT(*) FILTER (WHERE validation_status='verified') AS verified_rows, COUNT(DISTINCT source_edition) AS editions FROM usgs.production_vintage;"
psql -h localhost -p 5433 -U postgres -d lithium -c "SELECT * FROM usgs.v_world_total_latest ORDER BY reporting_year;"
```

## 3. Run CSV-based EDA

This works without PostgreSQL and does not modify the raw/validated input CSV:

```powershell
python scripts\eda_production.py
```

Outputs are written under `data/processed/`: latest numeric country-year observations, country YoY growth, supply concentration, reported-country sum by year, and a Plotly HTML trend chart. Reported-country sums are not presented as the USGS world total.

## 4. Launch dashboard

Run ingestion first, then:

```powershell
streamlit run app\streamlit_app.py
```

The app uses the PostgreSQL views and shows a clear connection error if PostgreSQL is not reachable or the import has not succeeded. It does not claim the database is populated merely because the code exists.

## Analytical definitions / caveats

- **Reporting year** and **publication year** are separate fields.
- The main table retains every source edition; the analytical country view selects the latest available publication vintage for each country/reporting-year pair.
- The world-total view separately selects the latest available world-total vintage for each reporting year. USGS world totals in these tables exclude U.S. production per edition-specific footnotes.
- `W`/withheld stays NULL. An em dash is zero only where the USGS table footnote defines it as zero.
- Missing country rows are not converted to zero. The set of reported countries changes by year and edition.
- YoY growth is calculated only when both adjacent reporting years are present, both values are numeric, and the prior value is non-zero.
- Concentration shares are computed against the sum of numeric country rows available in that year's latest-vintage view. This is **not** the USGS rounded world total and may be affected by country coverage differences.
- Production values across editions can be revised. Use `usgs.production_vintage` to audit source history.

## Suggested next phase (not included in this MVP)

Add EV adoption, lithium trade, prices, and reserves as separate source-vintage datasets with their own source metadata and validation. Only then build integrated lag analysis, scenarios, and an AI Strategy Desk. Do not blend units or infer missing observations without documented rules.
