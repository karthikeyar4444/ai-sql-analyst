"""Guardrails: only a single read-only SELECT may run, and it is always row-limited.

Two layers of protection:
1. This validator rejects anything that is not one SELECT/WITH statement.
2. The database itself is opened read-only (see db.connect_readonly), so even a query that
   slipped past the validator could not change data.
"""
from __future__ import annotations

import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|"
    r"truncate|grant|revoke|begin|commit|rollback|savepoint|load_extension)\b",
    re.IGNORECASE,
)


class UnsafeSQLError(ValueError):
    pass


def _strip_comments_and_strings(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.S)
    return re.sub(r"'(?:[^']|'')*'", "''", sql)  # ignore keywords inside string literals


def clean_sql(raw: str) -> str:
    """Pull the SQL out of a model reply (handles ```sql fences) and trim it."""
    m = re.search(r"```(?:sql)?\s*(.*?)```", raw, flags=re.S | re.I)
    sql = (m.group(1) if m else raw).strip()
    return sql.rstrip(";").strip()


def validate(sql: str, max_rows: int = 1000) -> str:
    """Return a safe, row-limited version of `sql` or raise UnsafeSQLError."""
    if not sql:
        raise UnsafeSQLError("empty query")
    body = _strip_comments_and_strings(sql)
    if ";" in body:
        raise UnsafeSQLError("only one statement is allowed")
    if not re.match(r"^\s*(select|with)\b", body, re.I):
        raise UnsafeSQLError("only SELECT queries are allowed")
    bad = FORBIDDEN.search(body)
    if bad:
        raise UnsafeSQLError(f"forbidden keyword: {bad.group(0).upper()}")
    # wrap so the limit applies whatever the inner query does
    return f"SELECT * FROM ({sql}) LIMIT {int(max_rows)}"
