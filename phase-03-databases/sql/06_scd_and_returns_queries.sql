-- ============================================================================
-- 06 — SCD + RETURNS QUERIES
--
-- These answer the questions the original star could NOT answer honestly:
-- point-in-time addresses (Type 2 SCD) and returns at their own grain.
--
-- Run:  python scripts/run_sql.py sql/06_scd_and_returns_queries.sql
-- ============================================================================

-- S1. How many customers moved, and how many versions does each mover have?
--     is_current = 0 versions ARE the history. One row per version.
SELECT COUNT(*) AS mover_versions,
       COUNT(DISTINCT customer_id) AS movers
FROM dim_customer_scd
WHERE is_current = 0;

-- S2. Point-in-time: where did a customer who moved live on 2025-03-01?
--     Picks a real mover dynamically (any customer with > 1 version), so
--     the query survives reseeding. A current-state dimension alone cannot
--     answer this question AT ALL — it knows only where they live NOW.
SELECT customer_id, full_name, city, country, valid_from, valid_to
FROM dim_customer_scd
WHERE customer_id = (
    SELECT customer_id FROM dim_customer_scd
    GROUP BY customer_id HAVING COUNT(*) > 1
    ORDER BY customer_id LIMIT 1
)
  AND valid_from <= '2025-03-01'
  AND (valid_to IS NULL OR valid_to >= '2025-03-01');

-- S3. THE MONEY DEMO: 2024 revenue by customer city, two ways, side by side.
--     current_dim_revenue uses today's address for everyone (the answer a
--     non-versioned dimension gives). scd_revenue uses the address the
--     customer had AT ORDER TIME. Only cities where the two disagree are
--     shown — those rows are exactly the mover revenue, and the difference
--     is the money being attributed to the wrong city.
WITH cur AS (
    SELECT dc.city, ROUND(SUM(f.net_revenue), 2) AS revenue
    FROM fact_sales f
    JOIN dim_date d     ON d.date_key = f.date_key
    JOIN dim_customer dc ON dc.customer_key = f.customer_key
    WHERE d.year = 2024
      AND f.order_status NOT IN ('cancelled', 'returned')
    GROUP BY dc.city
),
scd AS (
    SELECT scd.city, ROUND(SUM(f.net_revenue), 2) AS revenue
    FROM fact_sales f
    JOIN dim_date d        ON d.date_key = f.date_key
    JOIN dim_customer dc   ON dc.customer_key = f.customer_key
    JOIN dim_customer_scd scd
          ON scd.customer_id = dc.customer_id
         AND d.full_date >= scd.valid_from
         AND (scd.valid_to IS NULL OR d.full_date <= scd.valid_to)
    WHERE d.year = 2024
      AND f.order_status NOT IN ('cancelled', 'returned')
    GROUP BY scd.city
)
SELECT COALESCE(c.city, s.city) AS city,
       COALESCE(c.revenue, 0)   AS current_dim_revenue,
       COALESCE(s.revenue, 0)   AS scd_revenue,
       ROUND(COALESCE(s.revenue, 0) - COALESCE(c.revenue, 0), 2) AS scd_minus_current
FROM cur c
FULL OUTER JOIN scd s ON s.city = c.city
WHERE ABS(COALESCE(c.revenue, 0) - COALESCE(s.revenue, 0)) > 0.005
ORDER BY ABS(COALESCE(c.revenue, 0) - COALESCE(s.revenue, 0)) DESC;

-- R1. Returns at their own grain: refunds per month, and as a share of
--     that month's sales revenue. (The subquery aggregates the month's
--     revenue once, before the join — the rate is refunds/revenue, NOT
--     refunds/(revenue x number of return lines).)
SELECT d.year, d.month,
       COUNT(*) AS return_lines,
       ROUND(SUM(r.refund_amount), 2) AS refunds,
       ROUND(100.0 * SUM(r.refund_amount) / MAX(s.month_revenue), 2) AS refund_rate_pct
FROM fact_returns r
JOIN dim_date d ON d.date_key = r.date_key
JOIN (
    SELECT d2.year, d2.month, SUM(f.net_revenue) AS month_revenue
    FROM fact_sales f
    JOIN dim_date d2 ON d2.date_key = f.date_key
    WHERE f.order_status NOT IN ('cancelled', 'returned')
    GROUP BY d2.year, d2.month
) s ON s.year = d.year AND s.month = d.month
GROUP BY d.year, d.month
ORDER BY d.year, d.month;

-- R2. Which categories get returned the most? Refund value AND rate
--     (MAX() fixes the join fan-out: the category revenue repeats once
--     per return row, and the rate must use it exactly once).
SELECT dp.category,
       ROUND(SUM(r.refund_amount), 2) AS refunds,
       ROUND(100.0 * SUM(r.refund_amount) / MAX(s.cat_revenue), 2) AS refund_rate_pct
FROM fact_returns r
JOIN dim_product dp ON dp.product_key = r.product_key
JOIN (
    SELECT p.category, SUM(f.net_revenue) AS cat_revenue
    FROM fact_sales f
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE f.order_status NOT IN ('cancelled', 'returned')
    GROUP BY p.category
) s ON s.category = dp.category
GROUP BY dp.category
ORDER BY refund_rate_pct DESC;

-- R3. Partial returns exist: how many returned lines were PARTIAL
--     (fewer units returned than sold)? Joined through fact_sales —
--     warehouse-to-warehouse, never back to the source schema.
SELECT SUM(CASE WHEN r.quantity < f.quantity THEN 1 ELSE 0 END) AS partial_lines,
       SUM(CASE WHEN r.quantity = f.quantity THEN 1 ELSE 0 END) AS full_lines,
       COUNT(*) AS total_lines
FROM fact_returns r
JOIN fact_sales f ON f.order_id = r.order_id AND f.line_no = r.line_no;