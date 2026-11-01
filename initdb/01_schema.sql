CREATE TABLE current_stock (
    id       SERIAL PRIMARY KEY,
    date     DATE,
    quantity INTEGER
);

CREATE TABLE purchase_orders (
    id          SERIAL PRIMARY KEY,
    order_date  DATE,
    supply_date DATE,
    quantity    INTEGER
);

CREATE TABLE sku (
    id   SERIAL PRIMARY KEY,
    name TEXT
);

CREATE TABLE avg_sales (
    id      SERIAL PRIMARY KEY,
    receipt NUMERIC
);

-- Seed one default row in each table
INSERT INTO current_stock  (date, quantity) VALUES (NULL, NULL);
INSERT INTO purchase_orders (order_date, supply_date, quantity) VALUES (NULL, NULL, NULL);
INSERT INTO avg_sales (receipt) VALUES (NULL);
