-- ============================================================================
-- 04 — ETL: 3NF source -> star schema
--
-- This is ELT's T: the warehouse tables already exist (03); these INSERT
-- statements move data from the normalized source into dimensional shape.
--
-- Order matters: dimensions first, then the fact (the fact's foreign keys
-- must exist before it can reference them).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- 1. dim_date — one row per day, generated with a RECURSIVE CTE.
--
-- The CTE seeds itself with the first order date, then keeps adding one day
-- to itself until it reaches the last order date. This is a classic pattern:
-- generate a complete calendar so 'days with no sales' exist in the warehouse
-- and monthly charts don't skip them.
-- ----------------------------------------------------------------------------
INSERT INTO dim_date (
    date_key, full_date, year, quarter, month, month_name,
    day_of_month, day_of_week, day_name, is_weekend
)
WITH RECURSIVE calendar(dt) AS (
    SELECT MIN(order_date) FROM orders
    UNION ALL
    SELECT date(dt, '+1 day') FROM calendar
    WHERE dt < (SELECT MAX(order_date) FROM orders)
)
SELECT
    CAST(strftime('%Y%m%d', dt) AS INTEGER),          -- 20250615: sortable int key
    dt,
    CAST(strftime('%Y', dt) AS INTEGER),
    (CAST(strftime('%m', dt) AS INTEGER) + 2) / 3,    -- month 1-3 -> Q1, 4-6 -> Q2...
    CAST(strftime('%m', dt) AS INTEGER),
    CASE CAST(strftime('%m', dt) AS INTEGER)
        WHEN 1 THEN 'January'   WHEN 2 THEN 'February' WHEN 3 THEN 'March'
        WHEN 4 THEN 'April'     WHEN 5 THEN 'May'      WHEN 6 THEN 'June'
        WHEN 7 THEN 'July'      WHEN 8 THEN 'August'   WHEN 9 THEN 'September'
        WHEN 10 THEN 'October'  WHEN 11 THEN 'November' WHEN 12 THEN 'December'
    END,
    CAST(strftime('%d', dt) AS INTEGER),
    CAST(strftime('%w', dt) AS INTEGER),              -- 0 = Sunday
    CASE strftime('%w', dt)
        WHEN '0' THEN 'Sunday'    WHEN '1' THEN 'Monday'   WHEN '2' THEN 'Tuesday'
        WHEN '3' THEN 'Wednesday' WHEN '4' THEN 'Thursday' WHEN '5' THEN 'Friday'
        WHEN '6' THEN 'Saturday'
    END,
    CASE WHEN strftime('%w', dt) IN ('0', '6') THEN 1 ELSE 0 END
FROM calendar;

-- ----------------------------------------------------------------------------
-- 2. dim_customer — flatten the customer + their DEFAULT address.
--
-- Surrogate key = ROW_NUMBER() over a stable order. The natural key
-- (customer_id) is kept as a column so every warehouse row can be traced
-- back to the source system.
-- ----------------------------------------------------------------------------
INSERT INTO dim_customer (customer_key, customer_id, full_name, email, city, country)
SELECT
    ROW_NUMBER() OVER (ORDER BY c.customer_id),
    c.customer_id,
    c.full_name,
    c.email,
    a.city,
    a.country
FROM customers c
LEFT JOIN addresses a
       ON a.customer_id = c.customer_id
      AND a.is_default = 1;

-- ----------------------------------------------------------------------------
-- 3. dim_product — flatten category into the dimension (star, not snowflake).
-- ----------------------------------------------------------------------------
INSERT INTO dim_product (product_key, product_id, sku, name, category, list_price)
SELECT
    ROW_NUMBER() OVER (ORDER BY p.product_id),
    p.product_id,
    p.sku,
    p.name,
    cat.name,
    p.list_price
FROM products p
JOIN categories cat ON cat.category_id = p.category_id;

-- ----------------------------------------------------------------------------
-- 4. fact_sales — one row per order line, at the declared grain.
--
-- Measures are computed HERE, once, from the source numbers:
--   gross_amount    = quantity * unit_price
--   net_revenue     = gross_amount * (1 - discount_pct)
-- Handling the arithmetic in the ETL (instead of every query) is how a
-- warehouse guarantees every report agrees with every other report.
-- ----------------------------------------------------------------------------
INSERT INTO fact_sales (
    order_id, line_no, date_key, customer_key, product_key,
    quantity, unit_price, discount_pct,
    gross_amount, discount_amount, net_revenue, order_status
)
SELECT
    o.order_id,
    oi.line_no,
    CAST(strftime('%Y%m%d', o.order_date) AS INTEGER),
    dc.customer_key,
    dp.product_key,
    oi.quantity,
    oi.unit_price,
    oi.discount_pct,
    ROUND(oi.quantity * oi.unit_price, 2),
    ROUND(oi.quantity * oi.unit_price * oi.discount_pct, 2),
    ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct), 2),
    o.status
FROM order_items oi
JOIN orders o       ON o.order_id = oi.order_id
JOIN dim_customer dc ON dc.customer_id = o.customer_id
JOIN dim_product dp  ON dp.product_id = oi.product_id;