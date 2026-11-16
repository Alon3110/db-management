import os
import shlex
from pathlib import Path
from contextlib import closing

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, render_template

def load_local_environment():
    """Load simple KEY=value .env settings; exported environment takes priority."""
    path = Path(__file__).with_name(".env")
    if path.exists():
        for line in path.read_text().splitlines():
            tokens = shlex.split(line, comments=True)
            if tokens and tokens[0] == "export":
                tokens = tokens[1:]
            if len(tokens) == 1 and "=" in tokens[0]:
                key, value = tokens[0].split("=", 1)
                if key.startswith("POSTGRES_"):
                    os.environ.setdefault(key, value)


load_local_environment()
app = Flask(__name__)


def get_db_config():
    return {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": os.environ.get("POSTGRES_PORT", "5432"),
        "dbname": os.environ.get("POSTGRES_DB", "appdb"),
        "user": os.environ.get("POSTGRES_USER", "appuser"),
        "password": os.environ.get("POSTGRES_PASSWORD"),
        "connect_timeout": 5,
    }


def get_inventory():
    # psycopg2's transaction context does not close connections; closing does.
    with closing(psycopg2.connect(**get_db_config())) as conn:
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, sku_number, name FROM sku ORDER BY id")
            products = {row["id"]: dict(row, stock=[], orders=[], sales=[])
                        for row in cur.fetchall()}
            # Independent collections avoid multiplying one-to-many relationships.
            queries = {
                "stock": """SELECT c.* FROM current_stock c JOIN sku s ON s.id = c.product_id
                            ORDER BY c.date DESC NULLS LAST, c.id DESC""",
                "orders": """SELECT p.* FROM purchase_orders p JOIN sku s ON s.id = p.product_id
                             ORDER BY p.order_date DESC NULLS LAST, p.id DESC""",
                "sales": """SELECT a.* FROM avg_sales a JOIN sku s ON s.id = a.product_id
                            ORDER BY a.id""",
            }
            for collection, sql in queries.items():
                cur.execute(sql)
                for row in cur.fetchall():
                    products[row["product_id"]][collection].append(row)
            cur.execute("""SELECT
                (SELECT count(*) FROM current_stock WHERE product_id IS NULL) AS stock,
                (SELECT count(*) FROM purchase_orders WHERE product_id IS NULL) AS orders,
                (SELECT count(*) FROM avg_sales WHERE product_id IS NULL) AS sales""")
            unassigned = cur.fetchone()
    return list(products.values()), unassigned


def get_legacy_inventory():
    """Read the original schema without inventing any product associations."""
    with closing(psycopg2.connect(**get_db_config())) as conn:
        conn.set_session(isolation_level="REPEATABLE READ", readonly=True)
        with conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name FROM sku ORDER BY id")
            products = [dict(row, sku_number=None, stock=[], orders=[], sales=[])
                        for row in cur.fetchall()]
            cur.execute("""SELECT (SELECT count(*) FROM current_stock) AS stock,
                (SELECT count(*) FROM purchase_orders) AS orders,
                (SELECT count(*) FROM avg_sales) AS sales""")
            return products, cur.fetchone()


@app.route("/")
def index():
    try:
        migration_pending = False
        try:
            products, unassigned = get_inventory()
        except psycopg2.errors.UndefinedColumn:
            products, unassigned = get_legacy_inventory()
            migration_pending = True
    except psycopg2.Error:
        # Do not log exception text: connection errors can contain sensitive details.
        app.logger.error("Inventory database unavailable; check connectivity and migration status.")
        return render_template("index.html", products=[], unassigned=None,
                               error="Inventory is temporarily unavailable. Please try again later."), 503
    return render_template("index.html", products=products, unassigned=unassigned, error=None,
                           migration_pending=migration_pending)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
