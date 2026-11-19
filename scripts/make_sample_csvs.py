"""Write SYNTHETIC CSVs with the exact Olist file names and columns, for tests and CI only.

Never report accuracy numbers from this data - use the real Kaggle download.

    python scripts/make_sample_csvs.py --out tests/sample_csvs
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "DF"]
CATS = {"beleza_saude": "health_beauty", "informatica_acessorios": "computers_accessories",
        "esporte_lazer": "sports_leisure", "moveis_decoracao": "furniture_decor",
        "cama_mesa_banho": "bed_bath_table", "relogios_presentes": "watches_gifts"}


def make(out: Path, n_orders: int = 400, seed: int = 1) -> None:
    rng = np.random.default_rng(seed)
    out.mkdir(parents=True, exist_ok=True)
    uid = lambda p, i: f"{p}{i:05d}"

    n_people = int(n_orders * 0.9)
    customers = pd.DataFrame({
        "customer_id": [uid("c", i) for i in range(n_orders)],
        "customer_unique_id": [uid("u", rng.integers(n_people)) for _ in range(n_orders)],
        "customer_zip_code_prefix": rng.integers(1000, 99999, n_orders),
        "customer_city": rng.choice(["sao paulo", "rio de janeiro", "belo horizonte", "curitiba"], n_orders),
        "customer_state": rng.choice(STATES, n_orders, p=[.4, .15, .12, .08, .08, .07, .05, .05]),
    })
    sellers = pd.DataFrame({
        "seller_id": [uid("s", i) for i in range(40)],
        "seller_zip_code_prefix": rng.integers(1000, 99999, 40),
        "seller_city": rng.choice(["sao paulo", "curitiba", "campinas"], 40),
        "seller_state": rng.choice(STATES[:5], 40),
    })
    pt = list(CATS)
    products = pd.DataFrame({
        "product_id": [uid("p", i) for i in range(120)],
        "product_category_name": rng.choice(pt, 120),
        "product_name_lenght": rng.integers(10, 60, 120),
        "product_description_lenght": rng.integers(50, 2000, 120),
        "product_photos_qty": rng.integers(1, 6, 120),
        "product_weight_g": rng.integers(100, 20000, 120),
        "product_length_cm": rng.integers(10, 80, 120),
        "product_height_cm": rng.integers(2, 60, 120),
        "product_width_cm": rng.integers(8, 60, 120),
    })
    purchase = pd.Timestamp("2017-01-01") + pd.to_timedelta(rng.integers(0, 600, n_orders), unit="D") \
        + pd.to_timedelta(rng.integers(0, 86400, n_orders), unit="s")
    status = rng.choice(["delivered", "shipped", "canceled", "invoiced"], n_orders, p=[.9, .05, .03, .02])
    est = purchase + pd.to_timedelta(rng.integers(15, 30, n_orders), unit="D")
    deliv = purchase + pd.to_timedelta(rng.integers(3, 35, n_orders), unit="D")
    fmt = lambda s: pd.Series(s).dt.strftime("%Y-%m-%d %H:%M:%S")
    orders = pd.DataFrame({
        "order_id": [uid("o", i) for i in range(n_orders)],
        "customer_id": customers["customer_id"],
        "order_status": status,
        "order_purchase_timestamp": fmt(purchase),
        "order_approved_at": fmt(purchase + pd.Timedelta(hours=2)),
        "order_delivered_carrier_date": fmt(purchase + pd.Timedelta(days=2)),
        "order_delivered_customer_date": np.where(status == "delivered", fmt(deliv), None),
        "order_estimated_delivery_date": fmt(est),
    })
    items = []
    for oid in orders["order_id"]:
        for k in range(1, rng.integers(1, 4) + 1):
            items.append({"order_id": oid, "order_item_id": k,
                          "product_id": uid("p", rng.integers(120)), "seller_id": uid("s", rng.integers(40)),
                          "shipping_limit_date": "2017-06-01 00:00:00",
                          "price": round(float(rng.gamma(2, 60)), 2),
                          "freight_value": round(float(rng.uniform(5, 40)), 2)})
    items = pd.DataFrame(items)
    tot = items.groupby("order_id")[["price", "freight_value"]].sum().sum(axis=1)
    payments = pd.DataFrame({
        "order_id": orders["order_id"], "payment_sequential": 1,
        "payment_type": rng.choice(["credit_card", "boleto", "voucher", "debit_card"], n_orders, p=[.74, .19, .05, .02]),
        "payment_installments": rng.integers(1, 10, n_orders),
        "payment_value": orders["order_id"].map(tot).round(2),
    })
    reviews = pd.DataFrame({
        "review_id": [uid("r", i) for i in range(n_orders)], "order_id": orders["order_id"],
        "review_score": rng.choice([1, 2, 3, 4, 5], n_orders, p=[.1, .04, .08, .2, .58]),
        "review_comment_title": None, "review_comment_message": None,
        "review_creation_date": fmt(deliv), "review_answer_timestamp": fmt(deliv + pd.Timedelta(days=1)),
    })
    trans = pd.DataFrame({"product_category_name": list(CATS), "product_category_name_english": list(CATS.values())})

    for df, name in [(customers, "olist_customers_dataset"), (sellers, "olist_sellers_dataset"),
                     (products, "olist_products_dataset"), (orders, "olist_orders_dataset"),
                     (items, "olist_order_items_dataset"), (payments, "olist_order_payments_dataset"),
                     (reviews, "olist_order_reviews_dataset"), (trans, "product_category_name_translation")]:
        df.to_csv(out / f"{name}.csv", index=False)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="tests/sample_csvs")
    a = p.parse_args()
    make(Path(a.out))
    print(f"synthetic CSVs written to {a.out}")
