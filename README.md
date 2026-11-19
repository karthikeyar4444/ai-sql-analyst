# AI SQL Analyst

Ask business questions about **100K real e-commerce orders in plain English**. The assistant
writes the SQL with an LLM, checks it is safe, runs it **read-only**, fixes its own mistakes,
and returns a table, a chart and a one-line answer.

Accuracy is **measured, not assumed**: a 50-question benchmark with hand-written gold SQL
scores every answer by comparing query results.

**Stack:** Python · SQLite · SQL · OpenAI API · Streamlit · Plotly · pytest

---

## How it works

```
 "Which states have the slowest deliveries?"
                 │
                 ▼
  ┌───────────────────────────────┐
  │ Prompt = schema + example      │  db.describe_schema(): tables, columns,
  │ values + business notes        │  row counts, sample values, join hints
  └───────────────────────────────┘
                 │  OpenAI chat model
                 ▼
  ┌───────────────────────────────┐
  │ Safety guard                   │  only ONE SELECT/WITH · blocks DROP/DELETE/
  │                                │  UPDATE/PRAGMA/ATTACH… · 1,000-row limit
  └───────────────────────────────┘
                 ▼
  ┌───────────────────────────────┐
  │ Run on a READ-ONLY connection  │  SQLite opened with mode=ro + query_only
  │ with a 10-second timeout       │
  └───────────────────────────────┘
          │ error?  ──► send the error back to the model, retry once (self-correction)
          ▼
   table + auto chart + plain-English summary  (Streamlit chat app)
```

## Results

> Fill in from `eval/results/summary_openai.json` after running the benchmark on the real data.

| Metric | Value |
|---|---|
| Benchmark questions | 50 (16 easy · 18 medium · 16 hard) |
| Overall execution accuracy | … % |
| Easy / Medium / Hard | … % / … % / … % |
| Questions fixed by self-correction | … |
| Avg. time per question | … s |
| Model | … |

<!-- Add a screenshot: ![App](docs/screenshot.png) -->

## Safety

Two independent layers, so a bad query can never change the data:
1. **Validator** (`safety.py`): accepts a single `SELECT`/`WITH` statement only; rejects
   `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `PRAGMA`, `ATTACH` and multiple statements;
   wraps every query in a 1,000-row limit.
2. **Read-only database connection** (`db.connect_readonly`): even a query that slipped past
   the validator fails on write. Tested in `tests/test_engine.py`.

## Evaluation method

`eval/questions.py` holds 50 questions with gold SQL, from simple counts to window functions
(month-over-month growth, best category per state). `eval/run_eval.py` runs each question
through the assistant and marks it correct when the result matches the gold result: same row
count and every gold column matched by value (rounded, order-insensitive). Column names may
differ — the numbers must be right.

```bash
python eval/run_eval.py --llm gold     # sanity check: benchmark itself scores 100%
python eval/run_eval.py                # real run with OpenAI
```

## Setup

```bash
git clone https://github.com/<your-username>/ai-sql-analyst.git
cd ai-sql-analyst
pip install -r requirements.txt

# 1. data: download https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and unzip
python scripts/build_db.py --csv-dir ~/Downloads/olist

# 2. API key: create .env (never commit it)
cp .env.example .env        # then paste your key into .env

# 3. run
streamlit run app/streamlit_app.py
python eval/run_eval.py
pytest -q
```

## Project structure

```
ai-sql-analyst/
├── app/streamlit_app.py      # chat UI: answer, chart, table, SQL, CSV download
├── src/aisql/
│   ├── db.py                 # build SQLite from CSVs, read-only connection, schema text
│   ├── safety.py             # SQL validator + row limit
│   ├── llm.py                # OpenAI backend
│   └── engine.py             # question → SQL → safe run → self-correction → answer
├── eval/
│   ├── questions.py          # 50 benchmark questions + gold SQL
│   └── run_eval.py           # execution-accuracy scorer
├── scripts/
│   ├── build_db.py           # load the Kaggle CSVs
│   └── make_sample_csvs.py   # synthetic data for tests only
└── tests/test_engine.py      # safety, self-correction, scorer tests (no API needed)
```

## Dataset

[Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce):
~99K orders, 2016–2018, with customers, sellers, products, items, payments and reviews.
