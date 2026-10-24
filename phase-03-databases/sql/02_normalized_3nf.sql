-- ============================================================================
-- 02 — THE 3NF SCHEMA (the fix)
--
-- Normalization, in one sentence per form:
--   1NF: every cell holds ONE value (no comma-separated lists, no prices[]).
--   2NF: 1NF + every non-key column depends on the WHOLE primary key
--        (a column depending on only part of a composite key is partial
--        dependency — our order_items key is (order_id, line_no) and every
--        column needs both).
--   3NF: 2NF + no TRANSITIVE dependencies — non-key columns depend on the key
--        and NOTHING ELSE. Customer city depends on the customer, not on the
--        order, so cities move to their own table.
--
-- The rule of thumb: one table = one thing ('customers', 'products', 'orders').
-- If you can ask "what is this row ABOUT?" and get two answers, split it.
--
-- Read the constraints carefully — they are the actual work. Types don't
-- enforce business rules; CHECK/REFERENCES/UNIQUE/NOT NULL do.
-- ============================================================================

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    full_name   TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE COLLATE NOCASE,  -- one account per email
    created_at  TEXT    NOT NULL
);

-- Addresses live apart from customers: a customer can move, or keep several.
CREATE TABLE addresses (
    address_id  INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    city        TEXT    NOT NULL,
    country     TEXT    NOT NULL,
    is_default  INTEGER NOT NULL DEFAULT 1 CHECK (is_default IN (0, 1))
);

CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name        TEXT    NOT NULL UNIQUE
);

CREATE TABLE products (
    product_id  INTEGER PRIMARY KEY,
    sku         TEXT    NOT NULL UNIQUE,               -- natural business key
    name        TEXT    NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    list_price  REAL    NOT NULL CHECK (list_price > 0)
);

CREATE TABLE orders (
    order_id       INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date     TEXT    NOT NULL,
    -- status is a controlled vocabulary, not free text
    status         TEXT    NOT NULL CHECK (status IN
                      ('placed', 'shipped', 'delivered', 'cancelled', 'returned')),
    payment_method TEXT    NOT NULL CHECK (payment_method IN
                      ('card', 'paypal', 'transfer'))
);

-- The transaction lines. Composite key = one row per order line.
-- unit_price is the price AT SALE TIME — deliberately stored on the line,
-- NOT looked up from products, because prices change and history must not.
CREATE TABLE order_items (
    order_id     INTEGER NOT NULL REFERENCES orders(order_id),
    line_no      INTEGER NOT NULL,
    product_id   INTEGER NOT NULL REFERENCES products(product_id),
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    unit_price   REAL    NOT NULL CHECK (unit_price > 0),
    discount_pct REAL    NOT NULL DEFAULT 0 CHECK (discount_pct BETWEEN 0 AND 1),
    PRIMARY KEY (order_id, line_no)
);

-- Index the foreign keys: every JOIN in this phase starts from them.
CREATE INDEX idx_orders_customer     ON orders(customer_id);
CREATE INDEX idx_orders_date         ON orders(order_date);
CREATE INDEX idx_items_product       ON order_items(product_id);
CREATE INDEX idx_addresses_customer  ON addresses(customer_id);