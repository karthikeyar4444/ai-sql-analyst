"""Question -> SQL -> safe execution -> result, with one self-correction retry."""
from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass, field

import pandas as pd

from .db import connect_readonly, describe_schema
from .llm import LLM
from .safety import UnsafeSQLError, clean_sql, validate

SYSTEM_PROMPT = """You are a senior data analyst who writes SQLite queries for an e-commerce database.

DATABASE SCHEMA
{schema}

RULES
- Write ONE SQLite SELECT query (a WITH ... SELECT is fine). Never modify data.
- Use only tables and columns that exist in the schema above.
- Give columns clear aliases (e.g. total_revenue, order_count). Round money and averages to 2 decimals.
- For "top N" questions use ORDER BY ... DESC LIMIT N. For trends over time, order by the time column.
- If the question cannot be answered from this data, reply exactly: CANNOT_ANSWER: <short reason>
- Reply with the SQL only, inside a ```sql code block, no explanation."""

SUMMARY_PROMPT = """You are a data analyst. In 1-2 plain sentences, answer the user's question using
only the query result below. Mention the key numbers. Do not invent anything not in the result.

Question: {question}
Result (first rows, CSV):
{table}"""


class QueryTimeout(RuntimeError):
    pass


@dataclass
class Answer:
    question: str
    sql: str | None = None
    data: pd.DataFrame | None = None
    summary: str | None = None
    error: str | None = None
    attempts: int = 0
    seconds: float = 0.0
    log: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.data is not None


class SQLAnalyst:
    def __init__(self, db_path: str, llm: LLM, max_rows: int = 1000, timeout_s: float = 10.0,
                 max_retries: int = 1):
        self.con = connect_readonly(db_path)
        self.llm = llm
        self.max_rows = max_rows
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.schema = describe_schema(self.con)

    # ------------------------------------------------------------------ public
    def ask(self, question: str, summarize: bool = False) -> Answer:
        t0 = time.time()
        ans = Answer(question=question)
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(schema=self.schema)},
                    {"role": "user", "content": question}]

        for attempt in range(1 + self.max_retries):
            ans.attempts = attempt + 1
            reply = self.llm.complete(messages)
            if reply.strip().startswith("CANNOT_ANSWER"):
                ans.error = reply.strip().split(":", 1)[-1].strip() or "question not answerable from this data"
                break
            sql = clean_sql(reply)
            ans.sql = sql
            try:
                ans.data = self.run_sql(sql)
                ans.error = None
                break
            except (UnsafeSQLError, sqlite3.Error, QueryTimeout) as e:
                ans.error = f"{type(e).__name__}: {e}"
                ans.log.append(f"attempt {attempt + 1} failed: {ans.error}")
                # self-correction: show the model its own SQL and the error
                messages += [{"role": "assistant", "content": reply},
                             {"role": "user", "content": f"That query failed with: {e}\n"
                                                         "Fix it and reply with the corrected SQL only."}]

        if summarize and ans.ok and len(ans.data):
            ans.summary = self.llm.complete([{"role": "user", "content": SUMMARY_PROMPT.format(
                question=question, table=ans.data.head(20).to_csv(index=False))}]).strip()
        ans.seconds = round(time.time() - t0, 2)
        return ans

    def run_sql(self, sql: str) -> pd.DataFrame:
        safe = validate(sql, self.max_rows)
        deadline = time.time() + self.timeout_s

        def _check():  # returning non-zero aborts the query
            return 1 if time.time() > deadline else 0

        self.con.set_progress_handler(_check, 10_000)
        try:
            cur = self.con.execute(safe)
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)
        except sqlite3.OperationalError as e:
            if "interrupted" in str(e):
                raise QueryTimeout(f"query took longer than {self.timeout_s}s") from e
            raise
        finally:
            self.con.set_progress_handler(None, 0)
