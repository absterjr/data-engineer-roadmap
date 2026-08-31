-- ============================================================================
-- FIXED QUERIES — the same questions, clean, indexed, explainable
--
-- Each fix is explained line-by-line in sql/README.md.
--
-- Run with:  python scripts/run_sql.py sql/good_queries.sql
-- ============================================================================

-- Q1. Total revenue by country, year 2011
-- A range predicate instead of LIKE '%2011%' (index-friendly), no redundant
-- DISTINCT, and ORDER BY names the column instead of using an ordinal.
SELECT Country,
       SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
WHERE InvoiceDate >= '2011-01-01'
  AND InvoiceDate <  '2012-01-01'
GROUP BY Country
ORDER BY Revenue DESC;

-- Q2. Top 10 products by revenue
-- Group by StockCode AND Description: the same code can carry several
-- different descriptions (some broken), so grouping by code alone makes
-- SQL pick an arbitrary description. LIMIT 10 answers "top 10".
SELECT StockCode,
       Description,
       SUM(Quantity * UnitPrice) AS Revenue,
       SUM(Quantity)             AS Units,
       COUNT(*)                  AS Orders
FROM online_retail
GROUP BY StockCode, Description
ORDER BY Revenue DESC
LIMIT 10;

-- Q3. Monthly revenue
-- strftime() parses the date instead of slicing text, and we group by the
-- full expression (not the alias), which also works in databases that
-- forbid aliases in GROUP BY.
SELECT strftime('%Y-%m', InvoiceDate) AS Month,
       SUM(Quantity * UnitPrice)      AS Revenue
FROM online_retail
GROUP BY strftime('%Y-%m', InvoiceDate)
ORDER BY Month;

-- BONUS fix: WHERE filters rows, HAVING filters groups.
SELECT Country,
       SUM(Quantity * UnitPrice) AS Revenue
FROM online_retail
GROUP BY Country
HAVING SUM(Quantity * UnitPrice) > 100000
ORDER BY Revenue DESC;

-- The index that makes Q1's range predicate fast (see sql/README.md).
CREATE INDEX IF NOT EXISTS idx_online_retail_invoice_date
    ON online_retail(InvoiceDate);