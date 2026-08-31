-- ============================================================================
-- WINDOW FUNCTIONS — the Phase 1 skill that GROUP BY cannot cover
--
-- GROUP BY collapses rows; window functions keep every row and compute
-- something "across a window" of related rows. Each query here mirrors a
-- question from src/queries.py (Q6-Q8), so you can cross-check the numbers.
--
-- Run with:  python scripts/run_sql.py sql/window_functions.sql
-- ============================================================================

-- Q6. Top 3 products per country, per month (ROW_NUMBER + PARTITION BY)
--     1. roll products up to (country, month, product) revenue
--     2. number them inside each (country, month) window, biggest first
--     3. keep rn <= 3, then roll up to country total
WITH product_month AS (
    SELECT Country,
           strftime('%Y-%m', InvoiceDate) AS Month,
           StockCode,
           SUM(Quantity * UnitPrice) AS Revenue
    FROM online_retail
    GROUP BY Country, Month, StockCode
),
ranked AS (
    SELECT Country, Revenue,
           ROW_NUMBER() OVER (PARTITION BY Country, Month
                              ORDER BY Revenue DESC) AS rn
    FROM product_month
)
SELECT Country, SUM(Revenue) AS Top3Revenue
FROM ranked
WHERE rn <= 3
GROUP BY Country
ORDER BY Top3Revenue DESC;

-- Q7. Cumulative revenue month over month (SUM OVER, running total)
--     The window is the whole result, ordered by month, growing row by row.
SELECT strftime('%Y-%m', InvoiceDate) AS Month,
       SUM(Quantity * UnitPrice)                        AS Revenue,
       SUM(SUM(Quantity * UnitPrice)) OVER (ORDER BY strftime('%Y-%m', InvoiceDate))
                                                        AS RunningTotal
FROM online_retail
GROUP BY strftime('%Y-%m', InvoiceDate);

-- Q8. Share of total revenue by country (SUM OVER () with no PARTITION)
--     OVER () = one window containing ALL rows = the grand total.
SELECT Country,
       ROUND(100.0 * SUM(Quantity * UnitPrice)
             / SUM(SUM(Quantity * UnitPrice)) OVER (), 2) AS SharePct
FROM online_retail
GROUP BY Country
ORDER BY SharePct DESC;

-- BONUS. RANK vs DENSE_RANK vs ROW_NUMBER with ties.
--     Products rounded to the nearest dollar create ties on purpose:
--     RANK skips (1,2,3,3,5...) while DENSE_RANK does not (1,2,3,3,4...).
--     The top 12 happen to have no ties, so the next query zooms in on
--     a place where a tie actually happens.
SELECT StockCode,
       ROUND(SUM(Quantity * UnitPrice)) AS RevenueRounded,
       ROW_NUMBER() OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS rn,
       RANK()        OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS rk,
       DENSE_RANK()  OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS drk
FROM online_retail
GROUP BY StockCode
ORDER BY RevenueRounded DESC
LIMIT 12;

-- The same three functions at an actual tie: two products both round to
-- $12,701. ROW_NUMBER still splits them (1,2), RANK and DENSE_RANK tie them.
SELECT StockCode,
       ROUND(SUM(Quantity * UnitPrice)) AS RevenueRounded,
       ROW_NUMBER() OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS rn,
       RANK()        OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS rk,
       DENSE_RANK()  OVER (ORDER BY ROUND(SUM(Quantity * UnitPrice)) DESC) AS drk
FROM online_retail
GROUP BY StockCode
HAVING ROUND(SUM(Quantity * UnitPrice)) = 12701;

-- TRAP: window functions are computed AFTER GROUP BY but BEFORE ORDER BY,
-- and they cannot appear in WHERE (they don't exist when WHERE runs).
-- You must nest: SELECT ... FROM ( ... window query ... ) WHERE rn <= 3;