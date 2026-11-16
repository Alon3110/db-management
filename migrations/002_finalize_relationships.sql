-- Only after every legacy row has a verified mapping and SKU (see README).
BEGIN;
ALTER TABLE current_stock VALIDATE CONSTRAINT current_stock_product_fk;
ALTER TABLE purchase_orders VALIDATE CONSTRAINT purchase_orders_product_fk;
ALTER TABLE avg_sales VALIDATE CONSTRAINT avg_sales_product_fk;
ALTER TABLE current_stock VALIDATE CONSTRAINT current_stock_quantity_nonnegative;
ALTER TABLE purchase_orders VALIDATE CONSTRAINT purchase_orders_quantity_nonnegative;
ALTER TABLE sku ALTER COLUMN sku_number SET NOT NULL;
ALTER TABLE current_stock ALTER COLUMN product_id SET NOT NULL;
ALTER TABLE purchase_orders ALTER COLUMN product_id SET NOT NULL;
ALTER TABLE avg_sales ALTER COLUMN product_id SET NOT NULL;
COMMIT;
