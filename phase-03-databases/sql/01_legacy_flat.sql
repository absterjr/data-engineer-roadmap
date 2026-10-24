-- ============================================================================
-- 01 — THE LEGACY FLAT TABLE (the anti-pattern)
--
-- This is how the data "naturally" arrives when nobody models it: one wide
-- table, one row per order line, with the customer's and product's details
-- COPY-PASTED into every row.
--
-- It reads fine for a demo. It rots in production: three classic anomalies
-- (update, insert, delete), no keys, no constraints, and definitions that
-- drift because the same fact lives in a thousand rows.
--
-- Kept here as the STARTING POINT of the rebuild task. Every column below
-- that is not about the specific order line is a future data-quality
-- incident waiting to happen.
-- ============================================================================

CREATE TABLE legacy_orders (
    order_id         TEXT,      -- 'ORD-2024-000001' — text, no primary key
    order_date       TEXT,      -- ISO text, unvalidated
    customer_name    TEXT,      -- duplicated on EVERY line of EVERY order
    customer_email   TEXT,      -- the closest thing to a key (not enforced!)
    customer_city    TEXT,      -- legal to have two cities for one email
    customer_country TEXT,
    product_sku      TEXT,      -- duplicated per line
    product_name     TEXT,
    category         TEXT,      -- duplicated per line AND per product
    unit_price       REAL,
    quantity         INTEGER,   -- no CHECK: -5 is accepted
    discount_pct     REAL,      -- 0.1 = 10%; nothing stops 10
    payment_method   TEXT       -- duplicated per order
    -- no status column at all: cancelled orders simply cannot be excluded
);