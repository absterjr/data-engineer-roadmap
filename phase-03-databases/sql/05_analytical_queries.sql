-- ============================================================================
-- 05 — ANALYTICAL QUERIES against the star schema
--
-- Notice the shape of every query: fact first, dimensions joined for
-- context, GROUP BY on dimension attributes. The joins are on integer
-- surrogate keys, and there are never more than three of them.
--
-- Run:  python scripts/run_sql.py sql/05_analytical_queries.sql
-- ============================================================================

-- Q1. Monthly revenue, orders, and average order value.
--     dim_date supplies year/month so the fact table needs no date math.
SELECT d.year,
       d.month,
       d.month_name,
       ROUND(SUM(f.net_revenue), 2)                    AS revenue,
       COUNT(DISTINCT f.order_id)                      AS orders,
       ROUND(SUM(f.net_revenue) / COUNT(DISTINCT f.order_id), 2) AS avg_order_value
FROM fact_sales f
JOIN dim_date d ON d.date_key = f.date_key
WHERE f.order_status NOT IN ('cancelled', 'returned')
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;

-- Q2. Revenue by category per quarter, with quarter-over-quarter growth.
--     A window function (LAG) on top of a two-join query — the star's
--     simplicity is what makes adding the window function easy.
WITH quarterly AS (
    SELECT d.year,
           d.quarter,
           p.category,
           SUM(f.net_revenue) AS revenue
    FROM fact_sales f
    JOIN dim_date d    ON d.date_key = f.date_key
    JOIN dim_product p ON p.product_key = f.product_key
    WHERE f.order_status NOT IN ('cancelled', 'returned')
    GROUP BY d.year, d.quarter, p.category
)
SELECT year,
       quarter,
       category,
       ROUND(revenue, 2) AS revenue,
       ROUND(100.0 * (revenue - LAG(revenue) OVER (PARTITION BY category ORDER BY year, quarter))
             / LAG(revenue) OVER (PARTITION BY category ORDER BY year, quarter), 1) AS qoq_growth_pct
FROM quarterly
ORDER BY category, year, quarter;

-- Q3. Top 10 customers by net revenue, with country.
SELECT c.full_name,
       c.email,
       c.country,
       ROUND(SUM(f.net_revenue), 2) AS revenue,
       COUNT(DISTINCT f.order_id)   AS orders
FROM fact_sales f
JOIN dim_customer c ON c.customer_key = f.customer_key
WHERE f.order_status NOT IN ('cancelled', 'returned')
GROUP BY c.customer_key, c.full_name, c.email, c.country
ORDER BY revenue DESC
LIMIT 10;

-- Q4. Weekend vs weekday revenue share.
SELECT CASE d.is_weekend WHEN 1 THEN 'weekend' ELSE 'weekday' END AS bucket,
       ROUND(SUM(f.net_revenue), 2) AS revenue,
       ROUND(100.0 * SUM(f.net_revenue)
             / (SELECT SUM(net_revenue) FROM fact_sales
                WHERE order_status NOT IN ('cancelled', 'returned')), 1) AS share_pct
FROM fact_sales f
JOIN dim_date d ON d.date_key = f.date_key
WHERE f.order_status NOT IN ('cancelled', 'returned')
GROUP BY d.is_weekend;

-- Q5. Discount leakage: how much gross revenue each category gives away.
SELECT p.category,
       ROUND(SUM(f.gross_amount), 2)    AS gross,
       ROUND(SUM(f.discount_amount), 2) AS discount_given,
       ROUND(100.0 * SUM(f.discount_amount) / SUM(f.gross_amount), 2) AS leakage_pct
FROM fact_sales f
JOIN dim_product p ON p.product_key = f.product_key
WHERE f.order_status NOT IN ('cancelled', 'returned')
GROUP BY p.category
ORDER BY leakage_pct DESC;

-- Q6. Order-status mix per month — cancellations/returns as a share of
--     order lines. (In the legacy table this question is UNANSWERABLE:
--     there is no status column to filter or group by.)
SELECT d.year,
       d.month,
       f.order_status,
       COUNT(*) AS lines,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY d.year, d.month), 1) AS share_pct
FROM fact_sales f
JOIN dim_date d ON d.date_key = f.date_key
GROUP BY d.year, d.month, f.order_status
ORDER BY d.year, d.month, f.order_status;