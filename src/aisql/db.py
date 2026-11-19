"""Build the SQLite database from the Olist CSVs and describe its schema for the LLM."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

# Kaggle file -> clean table name
FILES = {
    "olist_customers_dataset.csv": "customers",
    "olist_sellers_dataset.csv": "sellers",
    "olist_products_dataset.csv": "products",
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "payments",
    "olist_order_reviews_dataset.csv": "reviews",
    "product_category_name_translation.csv": "category_translation",
}
COLUMN_FIXES = {"product_name_lenght": "product_name_length",
                "product_description_lenght": "product_description_length"}
INDEXES = [
    ("orders", "order_id"), ("orders", "customer_id"), ("order_items", "order_id"),
    ("order_items", "product_id"), ("order_items", "seller_id"), ("payments", "order_id"),
    ("reviews", "order_id"), ("customers", "customer_id"), ("products", "product_id"),
    ("sellers", "seller_id"),
]

# Plain-English notes the model sees next to the schema (business meaning, joins, gotchas)
NOTES = """
- Brazilian e-commerce marketplace (Olist), orders from 2016-09 to 2018-10. Money is in Brazilian reais (BRL).
- orders.customer_id is unique per order; customers.customer_unique_id identifies a real person
  (use COUNT(DISTINCT c.customer_unique_id) for "how many customers").
- Revenue = SUM(order_items.price); freight is order_items.freight_value. payments.payment_value = what the customer paid.
- An order can have several rows in order_items (one per item) and several rows in payments.
- products.category_english is the English category name; prefer it over product_category_name (Portuguese).
- Dates are TEXT 'YYYY-MM-DD HH:MM:SS'. Use strftime('%Y-%m', col) for months, julianday() for day differences.
- Delivered orders: orders.order_status = 'delivered'. Late delivery: order_delivered_customer_date > order_estimated_delivery_date.
- customers.customer_state / sellers.seller_state are 2-letter Brazilian state codes (e.g. 'SP' = Sao Paulo).
""".strip()


def build_database(csv_dir: str | Path, db_path: str | Path) -> dict:
    csv_dir, db_path = Path(csv_dir), Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    counts = {}
    for fname, table in FILES.items():
        path = csv_dir / fname
        if not path.exists():
            raise FileNotFoundError(f"missing {path} - did you unzip the Kaggle download there?")
        df = pd.read_csv(path).rename(columns=COLUMN_FIXES)
        if table == "category_translation":
            df.iloc[:, 0] = df.iloc[:, 0].str.lstrip("﻿")
        df.to_sql(table, con, index=False)
        counts[table] = len(df)

    # Add the English category straight onto products so simple questions need no extra join
    con.executescript("""
        ALTER TABLE products ADD COLUMN category_english TEXT;
        UPDATE products SET category_english = COALESCE(
            (SELECT t.product_category_name_english FROM category_translation t
             WHERE t.product_category_name = products.product_category_name),
            products.product_category_name);
    """)
    for table, col in INDEXES:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_{col} ON {table}({col})")
    con.commit()
    con.close()
    return counts


def connect_readonly(db_path: str | Path) -> sqlite3.Connection:
    """Open the database so that no statement can modify it."""
    uri = f"file:{Path(db_path).resolve()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, check_same_thread=False)
    con.execute("PRAGMA query_only = ON")
    return con


def describe_schema(con: sqlite3.Connection, sample_values: int = 3) -> str:
    """Compact schema text: tables, columns, types, row counts and a few example values."""
    lines = []
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    for t in tables:
        n = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        lines.append(f"TABLE {t} ({n:,} rows)")
        for _, col, ctype, *_ in con.execute(f"PRAGMA table_info({t})"):
            ex = ""
            if ctype == "TEXT" and not col.endswith("_id") and "message" not in col and "title" not in col:
                is_date = any(k in col for k in ("date", "timestamp", "_at"))
                vals = [r[0] for r in con.execute(
                    f"SELECT DISTINCT {col} FROM {t} WHERE {col} IS NOT NULL "
                    f"LIMIT {1 if is_date else sample_values}")]
                ex = f"  e.g. {', '.join(repr(v)[:40] for v in vals)}" if vals else ""
            lines.append(f"  - {col} {ctype}{ex}")
    return "\n".join(lines) + "\n\nNOTES:\n" + NOTES
