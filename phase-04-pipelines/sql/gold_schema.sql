-- ============================================================================
-- gold_schema — the weather warehouse (dim_city + dim_date + fact_daily_weather)
--
-- GOLD is the layer queries actually touch. Design mirrors Phase 3's star:
-- dimensions for the who/when, one fact at a clean grain:
--
--   fact_daily_weather grain: ONE ROW PER (CITY, DAY).
--
-- The composite PRIMARY KEY (city_key, date_key) is what makes loading
-- IDEMPOTENT: the UPSERT in load.py says "add it, or update it" — run the
-- load 100 times, the row count never changes. (A plain INSERT would
-- duplicate rows on every re-run — see broken/broken_pipeline.py.)
--
-- NOTE: CREATE TABLE IF NOT EXISTS, deliberately no DROPs — the warehouse
-- ACCUMULATES across runs and backfills. Wiping it is an explicit
-- `--reset`, never a side effect of loading. (A schema file that drops
-- its own tables turns every load into a destructive operation.)
-- ============================================================================

CREATE TABLE IF NOT EXISTS dim_city (
    city_key  INTEGER PRIMARY KEY,
    city_name TEXT    NOT NULL UNIQUE,
    country   TEXT    NOT NULL,
    lat       REAL    NOT NULL,
    lon       REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_date (
    date_key   INTEGER PRIMARY KEY,   -- 20261001: sortable integer key
    full_date  TEXT    NOT NULL UNIQUE,
    year       INTEGER NOT NULL,
    month      INTEGER NOT NULL,
    day        INTEGER NOT NULL,
    day_name   TEXT    NOT NULL,
    is_weekend INTEGER NOT NULL CHECK (is_weekend IN (0, 1))
);

CREATE TABLE IF NOT EXISTS fact_daily_weather (
    city_key    INTEGER NOT NULL REFERENCES dim_city(city_key),
    date_key    INTEGER NOT NULL REFERENCES dim_date(date_key),
    temp_mean_c REAL,
    precip_mm   REAL,
    wind_max_kph REAL,
    PRIMARY KEY (city_key, date_key)
);

CREATE INDEX IF NOT EXISTS idx_fact_weather_date ON fact_daily_weather(date_key);