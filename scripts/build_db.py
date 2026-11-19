"""Load the Olist CSVs into data/olist.db.

    python scripts/build_db.py --csv-dir ~/Downloads/olist
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aisql.db import build_database  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--csv-dir", required=True, help="folder with the unzipped Kaggle CSVs")
    p.add_argument("--db", default="data/olist.db")
    a = p.parse_args()
    counts = build_database(Path(a.csv_dir).expanduser(), a.db)
    for t, n in counts.items():
        print(f"{t:<22} {n:>8,} rows")
    print(f"database written to {a.db}")
