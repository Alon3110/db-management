-- Run once against the existing schema. No legacy IDs imply a product mapping.
BEGIN;
ALTER TABLE sku ADD COLUMN sku_number VARCHAR(255);
ALTER TABLE sku ADD CONSTRAINT sku_number_unique UNIQUE (sku_number);
-- NULL is temporarily allowed for legacy products awaiting a verified SKU.
ALTER TABLE sku ADD CONSTRAINT sku_number_nonblank
    CHECK (sku_number IS NULL OR (sku_number = btrim(sku_number) AND sku_number <> ''));

ALTER TABLE current_stock ADD COLUMN product_id INTEGER;
ALTER TABLE purchase_orders ADD COLUMN product_id INTEGER;
ALTER TABLE avg_sales ADD COLUMN product_id INTEGER;

-- NOT VALID preserves legacy data while enforcing constraints on new/updated rows.
ALTER TABLE current_stock ADD CONSTRAINT current_stock_product_fk
    FOREIGN KEY (product_id) REFERENCES sku(id) ON DELETE RESTRICT NOT VALID;
ALTER TABLE purchase_orders ADD CONSTRAINT purchase_orders_product_fk
    FOREIGN KEY (product_id) REFERENCES sku(id) ON DELETE RESTRICT NOT VALID;
ALTER TABLE avg_sales ADD CONSTRAINT avg_sales_product_fk
    FOREIGN KEY (product_id) REFERENCES sku(id) ON DELETE RESTRICT NOT VALID;
ALTER TABLE current_stock ADD CONSTRAINT current_stock_quantity_nonnegative
    CHECK (quantity >= 0) NOT VALID;
ALTER TABLE purchase_orders ADD CONSTRAINT purchase_orders_quantity_nonnegative
    CHECK (quantity >= 0) NOT VALID;

CREATE INDEX current_stock_product_date_idx ON current_stock (product_id, date DESC, id DESC);
CREATE INDEX purchase_orders_product_idx ON purchase_orders (product_id);
CREATE INDEX avg_sales_product_idx ON avg_sales (product_id);
COMMIT;
