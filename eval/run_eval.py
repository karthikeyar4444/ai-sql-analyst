"""Measure execution accuracy of the text-to-SQL assistant on the 50-question benchmark.

A prediction counts as correct when its result matches the gold query's result:
same number of rows, and every gold column has a matching column in the prediction
(same values after rounding, compared order-insensitively). Extra columns and different
column names are allowed - what matters is that the numbers are right.

    python eval/run_eval.py                     # real run (Gemini or OpenAI key from .env)
    python eval/run_eval.py --llm gold          # sanity check: every gold query runs and scores 100%
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval"))

from aisql.engine import SQLAnalyst  # noqa: E402
from questions import QUESTIONS  # noqa: E402


def _norm(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 1)
    return str(v).strip().lower()


def _col_signature(s: pd.Series) -> tuple:
    vals = [_norm(v) for v in s.tolist()]
    return tuple(sorted(vals, key=lambda x: (x is None, str(type(x)), x if x is not None else 0)))


def results_match(gold: pd.DataFrame, pred: pd.DataFrame) -> bool:
    if pred is None or len(gold) != len(pred):
        return False
    pred_sigs = [_col_signature(pred[c]) for c in pred.columns]
    return all(_col_signature(gold[c]) in pred_sigs for c in gold.columns)


class GoldLLM:
    """Returns the gold SQL - used only to check that the benchmark itself is valid."""
    def __init__(self):
        self.lookup = {q: sql for _, q, sql in QUESTIONS}
        self.total_tokens = 0

    def complete(self, messages):
        return self.lookup[messages[-1]["content"]]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--db", default="data/olist.db")
    p.add_argument("--llm", choices=["api", "gold"], default="api",
                   help="api = Gemini or OpenAI (whichever key is in .env); gold = benchmark self-check")
    p.add_argument("--model", default=None, help="model id (default: LLM_MODEL or the provider default)")
    p.add_argument("--out", default="eval/results")
    p.add_argument("--sleep", type=float, default=0.0,
                   help="seconds to wait between questions (use ~6 on free-tier APIs to avoid rate limits)")
    a = p.parse_args()

    if a.llm == "gold":
        llm = GoldLLM()
    else:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        from aisql.llm import ChatLLM
        llm = ChatLLM(model=a.model)

    analyst = SQLAnalyst(a.db, llm)
    rows = []
    t0 = time.time()
    for i, (level, question, gold_sql) in enumerate(QUESTIONS, 1):
        gold = analyst.run_sql(gold_sql)
        ans = analyst.ask(question)
        ok = ans.ok and results_match(gold, ans.data)
        rows.append({"id": i, "difficulty": level, "question": question, "correct": ok,
                     "attempts": ans.attempts, "seconds": ans.seconds,
                     "error": ans.error, "generated_sql": ans.sql, "gold_sql": gold_sql})
        print(f"[{i:02d}] {'PASS' if ok else 'FAIL'}  ({level:<6}) {question}")
        if a.sleep:
            time.sleep(a.sleep)

    df = pd.DataFrame(rows)
    by_level = df.groupby("difficulty")["correct"].agg(["sum", "count"])
    summary = {
        "model": f"{getattr(llm, 'provider', a.llm)} / {getattr(llm, 'model', a.llm)}",
        "questions": len(df),
        "accuracy_pct": round(100 * df["correct"].mean(), 1),
        "by_difficulty_pct": {k: round(100 * r["sum"] / r["count"], 1) for k, r in by_level.iterrows()},
        "fixed_by_self_correction": int(((df["attempts"] > 1) & df["correct"]).sum()),
        "avg_seconds_per_question": round(df["seconds"].mean(), 2),
        "total_tokens": getattr(llm, "total_tokens", None),
        "runtime_sec": round(time.time() - t0, 1),
    }
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / f"eval_{a.llm}.csv", index=False)
    (out / f"summary_{a.llm}.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
