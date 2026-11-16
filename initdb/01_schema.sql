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
