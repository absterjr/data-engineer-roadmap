-- ============================================================================
-- BAD QUERIES — Day 4 rebuild task
--
-- These RUN. Some even give the right numbers. That is exactly the trap:
-- they are slow, fragile, or silently hiding a correctness problem.
--
-- Find the problems yourself first, then read sql/README.md for the full
-- explanation of what is wrong and how each one was fixed.
--
-- Run with:  python scripts/run_sql.py sql/bad_queries.sql
-- ============================================================================

-- Q1. Total revenue by country, year 2011
SELECT DISTINCT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE InvoiceDate LIKE '%2011%'
GROUP BY Country
ORDER BY 2 DESC;

-- Q2. Top 10 products by revenue
SELECT StockCode, Description, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY StockCode
ORDER BY Revenue DESC;

-- Q3. Monthly revenue
SELECT substr(InvoiceDate, 1, 7) AS Month, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY 1
ORDER BY 1;

-- BONUS. This one does not even run. Why not?
SELECT Country, SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE SUM(Quantity * UnitPrice) > 100000
GROUP BY Country;