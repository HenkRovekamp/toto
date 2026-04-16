# Plan: Migrate Riders to Supabase

## Approach
Direct PostgreSQL connection — no supabase-py SDK. Use psycopg2, consistent with existing SQL patterns. No Row Level Security.

## Supabase project
- API URL: https://kwpntdrjjvonudcmigsd.supabase.co
- Connection string: Settings ? Database ? Connection string (PostgreSQL URI)

## Step 1 — Create table in Supabase SQL editor
```sql
CREATE TABLE IF NOT EXISTS riders (
    rider_url   TEXT PRIMARY KEY,
    name        TEXT,
    nationality TEXT,
    birthdate   TEXT,
    height      FLOAT,
    weight      FLOAT,
    team_name   TEXT,
    team_url    TEXT,
    scraped_at  TIMESTAMPTZ DEFAULT now()
);
```

## Step 2 — Dependencies & config
- Add `psycopg2-binary` to `requirements.txt`
- Create `.env` with `SUPABASE_PG_URI=postgresql://...` (from Supabase dashboard)
- `.env` is already gitignored

## Step 3 — Migration script (one-off)
Create `scripts/migrate_to_supabase.py`:
- Read all rows from `data/cycling.duckdb`
- Batch upsert via psycopg2 in chunks of 500
- `INSERT ... ON CONFLICT (rider_url) DO UPDATE SET ...`

## Step 4 — Update app.py
- Replace `duckdb.connect(local_file)` with `psycopg2.connect(SUPABASE_PG_URI)`
- Queries stay identical (standard SQL)
- Load URI from `.env` via `python-dotenv`

## Decisions
- `main.py` scraper stays DuckDB-only — no changes
- Migration is one-off; re-run after scraping more riders
- Local DuckDB remains source of truth for scraping
