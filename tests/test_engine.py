import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from aisql.db import build_database, connect_readonly  # noqa: E402
from aisql.engine import SQLAnalyst  # noqa: E402
from aisql.safety import UnsafeSQLError, clean_sql, validate  # noqa: E402
from make_sample_csvs import make  # noqa: E402


@pytest.fixture(scope="session")
def db(tmp_path_factory):
    d = tmp_path_factory.mktemp("olist")
    make(d / "csv")
    build_database(d / "csv", d / "olist.db")
    return str(d / "olist.db")


class ScriptedLLM:
    """Fake model that returns pre-set replies in order."""
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        return self.replies.pop(0)


# ---------------------------------------------------------------- safety
@pytest.mark.parametrize("sql", [
    "DROP TABLE orders", "DELETE FROM orders", "SELECT 1; DROP TABLE orders",
    "UPDATE orders SET order_status='x'", "PRAGMA writable_schema=1", "ATTACH 'x.db' AS x",
    "INSERT INTO orders VALUES (1)", "",
])
def test_validator_blocks_unsafe(sql):
    with pytest.raises(UnsafeSQLError):
        validate(sql)


def test_validator_allows_select_and_cte_and_keywords_in_strings():
    assert validate("SELECT 1").endswith("LIMIT 1000")
    validate("WITH x AS (SELECT 1 AS a) SELECT a FROM x")
    validate("SELECT 'please delete me' AS note")


def test_clean_sql_strips_fences():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"


def test_database_is_read_only_even_without_validator(db):
    con = connect_readonly(db)
    with pytest.raises(sqlite3.OperationalError):
        con.execute("DELETE FROM orders")


def test_products_have_english_category(db):
    con = connect_readonly(db)
    assert con.execute("SELECT COUNT(*) FROM products WHERE category_english IS NULL").fetchone()[0] == 0


# ---------------------------------------------------------------- engine
def test_happy_path(db):
    llm = ScriptedLLM("```sql\nSELECT order_status, COUNT(*) AS n FROM orders GROUP BY 1\n```")
    ans = SQLAnalyst(db, llm).ask("orders by status")
    assert ans.ok and ans.attempts == 1 and "n" in ans.data.columns


def test_self_correction_retry(db):
    llm = ScriptedLLM("SELECT nope FROM orders", "SELECT COUNT(*) AS n FROM orders")
    ans = SQLAnalyst(db, llm).ask("how many orders")
    assert ans.ok and ans.attempts == 2
    assert "failed with" in llm.calls[1][-1]["content"]  # error was fed back


def test_unsafe_sql_is_refused_not_run(db):
    llm = ScriptedLLM("DROP TABLE orders", "DROP TABLE orders")
    ans = SQLAnalyst(db, llm).ask("delete everything")
    assert not ans.ok and "UnsafeSQLError" in ans.error
    assert connect_readonly(db).execute("SELECT COUNT(*) FROM orders").fetchone()[0] > 0


def test_cannot_answer(db):
    ans = SQLAnalyst(db, ScriptedLLM("CANNOT_ANSWER: no weather data")).ask("weather?")
    assert not ans.ok and "weather" in ans.error


def test_row_limit(db):
    ans = SQLAnalyst(db, ScriptedLLM("SELECT * FROM order_items"), max_rows=50).ask("all items")
    assert len(ans.data) == 50


# ---------------------------------------------------------------- eval scorer
def test_scorer_accepts_renamed_columns_and_rejects_wrong_numbers():
    import pandas as pd
    sys.path.insert(0, str(ROOT / "eval"))
    from run_eval import results_match
    gold = pd.DataFrame({"state": ["SP", "RJ"], "revenue": [100.004, 50.0]})
    assert results_match(gold, pd.DataFrame({"customer_state": ["RJ", "SP"], "total": [50.0, 100.0], "x": [1, 2]}))
    assert not results_match(gold, pd.DataFrame({"state": ["SP", "RJ"], "revenue": [100.0, 51.0]}))
    assert not results_match(gold, pd.DataFrame({"state": ["SP"], "revenue": [100.0]}))
