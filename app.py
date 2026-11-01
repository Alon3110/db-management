import os
import psycopg2
from flask import Flask, render_template

app = Flask(__name__)

DB_CONFIG = {
    "host":     os.environ.get("POSTGRES_HOST", "localhost"),
    "port":     int(os.environ.get("POSTGRES_PORT", 5432)),
    "dbname":   os.environ.get("POSTGRES_DB",   "appdb"),
    "user":     os.environ.get("POSTGRES_USER",  "appuser"),
    "password": os.environ.get("POSTGRES_PASSWORD", "changeme"),
}


def get_rows():
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, date, quantity FROM current_stock ORDER BY id")
        stock_rows = cur.fetchall()

        cur.execute("SELECT id, order_date, supply_date, quantity FROM purchase_orders ORDER BY id")
        po_rows = cur.fetchall()

        cur.execute("SELECT id, receipt FROM avg_sales ORDER BY id")
        avg_rows = cur.fetchall()

        cur.execute("SELECT id, name FROM sku ORDER BY id")
        sku_rows = cur.fetchall()

        cur.close()
    finally:
        conn.close()

    # Zip the four tables together by position; pad with None if lengths differ
    length = max(len(stock_rows), len(po_rows), len(avg_rows), len(sku_rows))
    rows = []
    for i in range(length):
        s  = stock_rows[i] if i < len(stock_rows) else (None, None, None)
        po = po_rows[i]    if i < len(po_rows)    else (None, None, None, None)
        av = avg_rows[i]   if i < len(avg_rows)   else (None, None)
        sk = sku_rows[i]   if i < len(sku_rows)   else (None, None)
        rows.append({
            "sku_name":     sk[1],
            "stock_date":   s[1],
            "stock_qty":    s[2],
            "po_order":     po[1],
            "po_supply":    po[2],
            "po_qty":       po[3],
            "avg_receipt":  av[1],
        })
    return rows


@app.route("/")
def index():
    rows = get_rows()
    return render_template("index.html", rows=rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
