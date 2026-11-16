# DB Management

Lightweight Flask/psycopg2 inventory dashboard. Existing table names and independent
primary keys are retained. Never infer product relationships from record IDs.

## Architecture and schema

`sku.id` is the internal product key; `sku.sku_number` is a unique, trimmed,
nonempty business identifier (VARCHAR(255), case-sensitive). `name` remains TEXT,
as in the actual initialization schema, rather than the documented VARCHAR(255).
All three inventory tables gain `product_id INTEGER` referencing `sku(id)` with
`ON DELETE RESTRICT`. Their own SERIAL primary keys remain unchanged.

`current_stock` stores snapshot history, not stock movements. The dashboard shows
all snapshots, ordered by date descending, unknown dates last, with ID as a stable
tie-breaker. It does not sum snapshots or claim an undated row is current. Before
forecasting, decide snapshot cadence, same-day ordering, units, and adjustments.

`avg_sales.receipt` remains an opaque NUMERIC legacy metric. All entries are shown;
no averaging, sales-event interpretation, positivity constraint, or latest-value
assumption is imposed. Define its units, time window, and meaning before adding
sales events or forecasting. Future dated sales events should be modeled separately.

The first migration adds:

- `sku.sku_number`, `sku_number_unique` (unique constraint and backing index), and
  `sku_number_nonblank` check.
- `product_id` on `current_stock`, `purchase_orders`, and `avg_sales`.
- Foreign keys `current_stock_product_fk`, `purchase_orders_product_fk`, and
  `avg_sales_product_fk`.
- Checks `current_stock_quantity_nonnegative` and
  `purchase_orders_quantity_nonnegative`. NULL remains unknown, not zero.
- Indexes `current_stock_product_date_idx (product_id, date DESC, id DESC)`,
  `purchase_orders_product_idx (product_id)`, `avg_sales_product_idx (product_id)`.

Foreign keys and quantity checks start NOT VALID: new/updated rows are checked,
but old rows are preserved even if they violate a new quantity rule. Nullable SKU
numbers and product references are a temporary reconciliation state. PostgreSQL
UNIQUE permits multiple NULLs. Migration 002 validates checks and makes SKU numbers
and all product references NOT NULL; it fails transactionally if reconciliation
is incomplete. Until then, write paths must explicitly require these fields.

The backend reads four independent collections with relational JOINs and one
unassigned-record count in a read-only repeatable-read transaction. This prevents
Cartesian multiplication and inconsistent snapshots. Connections close on success
and failure. Unassigned rows are counted, never displayed under an invented product.

## Existing repository differences

The former backend joined `s.id = child.id`, despite comments describing product
relationships. Both init SQL files duplicated CREATE TABLE and placeholder inserts.
The original schema uses SERIAL IDs and TEXT product names. Initialization now mounts
only `initdb/01_schema.sql`; the duplicate file is retired and placeholder inserts
are removed. Existing volumes are untouched. Init SQL creates the original base
schema only; fresh installations also require the migrations below.

## Configuration and local startup

Keep the existing database password from your local configuration or password
manager. The former configuration used a development fallback; changing an
environment variable does not change the password inside an existing database.
No credential is supplied or logged by the application. Compose does not require
a password merely to run commands against an existing container. A fresh database
still requires POSTGRES_PASSWORD, and Flask TCP connections require the existing
database credentials.

```bash
cp .env.example .env
# Edit .env locally; set POSTGRES_PASSWORD to the EXISTING database password.
set -a
source .env
set +a
docker compose up -d db
docker compose ps
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Compose and the application read `.env` automatically; exported environment variables take priority.
Before migration 001, the dashboard uses a read-only legacy view with a migration
notice and unassigned record counts. No product associations are inferred.
Defaults: localhost:5432, appdb, appuser. `.env` and `.venv/` are ignored by Git.
Do not run `docker compose down -v`, delete volumes, or run init SQL on an existing DB.

## Manual migration (never automatically applied)

Back up first. From the repository root, with the environment configured above:

```bash
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /tmp/db-management-before-migration.dump
# Inspect current schema and rows before applying anything:
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\\d sku" -c "\\d current_stock" -c "\\d purchase_orders" -c "\\d avg_sales"'
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < migrations/001_product_relationships.sql
```

Run each numbered migration once, in order. They are transactional, intentionally
not idempotent: a repeated run fails rather than hides schema drift. No migration
creates products, changes existing IDs, or automatically associates rows. Schedule
a maintenance window for ALTER TABLE locks and index creation on large datasets.

Open an SQL session for verified manual reconciliation:

```bash
docker compose exec db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Review unassigned rows with the queries below. Create real products only after
confirming their SKU/name, or set verified SKU numbers on existing products. Use
`INSERT INTO sku (sku_number, name) VALUES (...) RETURNING id` to obtain the actual
internal ID. For each independently verified inventory row, use a transaction and
an explicit mapping, e.g. `UPDATE current_stock SET product_id = <verified_product_id>
WHERE id = <verified_stock_record_id> AND product_id IS NULL`. Check affected row
counts. Repeat independently for purchase_orders and avg_sales. Angle-bracket
values are placeholders, not executable SQL. Never map by equality of IDs.

Keep unresolved placeholder/unknown rows unassigned; do not discard them merely to
pass migration 002. Resolve negative legacy quantities with business approval.
When every mapping and SKU has been verified:

```bash
docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < migrations/002_finalize_relationships.sql
python app.py
```

Visit http://localhost:5000/. The dashboard also works between migrations, with
an unassigned-record notice. A refresh reads committed changes; no cached inventory.
A generic HTTP 503 indicates connection/schema failure. Check server configuration
and migration status. Debug mode is disabled.

## Verification SQL

Run these in the SQL session before and after migration, retaining counts and IDs
for comparison. Migration 001 should change neither.

```sql
SELECT 'sku' AS table_name, count(*), array_agg(id ORDER BY id) AS ids FROM sku
UNION ALL SELECT 'current_stock', count(*), array_agg(id ORDER BY id) FROM current_stock
UNION ALL SELECT 'purchase_orders', count(*), array_agg(id ORDER BY id) FROM purchase_orders
UNION ALL SELECT 'avg_sales', count(*), array_agg(id ORDER BY id) FROM avg_sales;

SELECT * FROM sku WHERE sku_number IS NULL;
SELECT * FROM current_stock WHERE product_id IS NULL;
SELECT * FROM purchase_orders WHERE product_id IS NULL;
SELECT * FROM avg_sales WHERE product_id IS NULL;

SELECT s.id, s.sku_number, s.name,
  (SELECT count(*) FROM current_stock c WHERE c.product_id = s.id) AS snapshots,
  (SELECT count(*) FROM purchase_orders p WHERE p.product_id = s.id) AS orders,
  (SELECT count(*) FROM avg_sales a WHERE a.product_id = s.id) AS sales_metrics
FROM sku s ORDER BY s.id;

SELECT s.sku_number, p.* FROM purchase_orders p
JOIN sku s ON s.id = p.product_id ORDER BY s.id, p.id;
SELECT s.sku_number, c.* FROM current_stock c
JOIN sku s ON s.id = c.product_id ORDER BY s.id, c.date DESC NULLS LAST, c.id DESC;
SELECT s.sku_number, a.* FROM avg_sales a
JOIN sku s ON s.id = a.product_id ORDER BY s.id, a.id;

SELECT conrelid::regclass AS table_name, conname, convalidated,
       pg_get_constraintdef(oid) FROM pg_constraint
WHERE conrelid IN ('sku'::regclass, 'current_stock'::regclass,
                  'purchase_orders'::regclass, 'avg_sales'::regclass);
```

Before migration 001, omit queries involving the newly added columns.

## Tests and remaining work

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Tests cover independent collections, multiple orders, missing values, HTML escaping,
product grouping, generic failures, and connection closure. They use mocks and do
not insert into the existing database. Database startup, actual PostgreSQL migration
execution and browser verification must be checked manually or against a disposable
PostgreSQL 16 instance; these are not proven by unit tests. Do not test writes against
the existing database without approval. Rollback-only writes consume sequence values
and are not entirely side-effect-free.

Before CRUD: finish reconciliation and migration 002, define SKU case rules and
renaming policy, validate inputs with parameterized SQL for all supplied values,
add authentication/authorization and CSRF protection, choose archive vs deletion,
and define order lifecycle/receipt tracking. Existing queries contain no user input.
Before thousands of products: paginate products and stock/order histories, add query
limits and evaluate plans. The current page intentionally loads full histories.
Before forecasting: define sales semantics, dates, units, stockouts, returns,
supplier lead times and data quality; do not derive demand from undefined receipt
values or sums of snapshots. Use a production WSGI server for deployment.
