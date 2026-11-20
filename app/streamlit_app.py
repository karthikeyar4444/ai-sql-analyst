"""AI SQL Analyst - ask questions about the Olist e-commerce data in plain English.

    streamlit run app/streamlit_app.py
"""
import os
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aisql.engine import SQLAnalyst  # noqa: E402
from aisql.llm import ChatLLM  # noqa: E402

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass
# Streamlit Cloud: secrets -> environment
for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_MODEL"):
    try:
        if key not in os.environ and key in st.secrets:
            os.environ[key] = st.secrets[key]
    except Exception:  # no secrets file when running locally - that's fine
        pass

DB_PATH = os.getenv("AISQL_DB", str(ROOT / "data" / "olist.db"))
EXAMPLES = [
    "Which 5 product categories bring in the most revenue?",
    "How has the number of orders changed month by month?",
    "Do late deliveries get worse review scores?",
    "Which states have the slowest average delivery time?",
    "What share of customers ordered more than once?",
]

st.set_page_config(page_title="AI SQL Analyst", page_icon="🔎", layout="wide")


@st.cache_resource
def get_analyst() -> SQLAnalyst:
    return SQLAnalyst(DB_PATH, ChatLLM())


def auto_chart(df: pd.DataFrame):
    """Draw a sensible chart when the result is 'one label column + numbers'."""
    if df is None or len(df) < 2 or df.shape[1] < 2:
        return None
    num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    label_cols = [c for c in df.columns if c not in num_cols]
    if not num_cols:
        return None
    x = label_cols[0] if label_cols else df.columns[0]
    # first numeric column is usually the answer (counts like review_count tend to come after)
    y = num_cols[0] if num_cols[0] != x else num_cols[-1]
    is_time = any(k in str(x).lower() for k in ("month", "year", "date", "hour", "week", "day"))
    if is_time:
        return px.line(df, x=x, y=y, markers=True)
    return px.bar(df.head(25), x=y, y=x, orientation="h").update_yaxes(autorange="reversed")


def render(ans) -> None:
    if ans.summary:
        st.markdown(ans.summary.replace("$", r"\$"))  # stop "$" from being read as math
    if not ans.ok:
        st.error(f"Couldn't answer that: {ans.error}")
    else:
        fig = auto_chart(ans.data)
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ans.data, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", ans.data.to_csv(index=False), "result.csv",
                           key=f"dl_{id(ans)}")
    if ans.sql:
        with st.expander("Show SQL"):
            st.code(ans.sql, language="sql")
            st.caption(f"{ans.attempts} attempt(s) · {ans.seconds}s · read-only, max 1,000 rows")


# ---------------------------------------------------------------- layout
st.title("🔎 AI SQL Analyst")
st.caption("Ask questions about 100K Brazilian e-commerce orders (Olist, 2016–2018) in plain English. "
           "The assistant writes SQL, runs it read-only, and shows the result.")

if not Path(DB_PATH).exists():
    st.error(f"Database not found at {DB_PATH}. Run `python scripts/build_db.py --csv-dir <olist folder>` first.")
    st.stop()
if not any(os.getenv(k) for k in ("GROQ_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY")):
    st.error("No API key found. Add GROQ_API_KEY (free) to a `.env` file (see README).")
    st.stop()

analyst = get_analyst()

with st.sidebar:
    st.header("Try a question")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state.pending = q
    st.divider()
    summarize = st.toggle("Write a plain-English answer", value=True)
    with st.expander("Database schema"):
        st.text(analyst.schema)
    st.caption(f"Model: {analyst.llm.provider} · {analyst.llm.model}")
    if st.button("Clear chat"):
        st.session_state.history = []

st.session_state.setdefault("history", [])
for q, ans in st.session_state.history:
    with st.chat_message("user"):
        st.write(q)
    with st.chat_message("assistant"):
        render(ans)

question = st.chat_input("e.g. What were the top 10 sellers by revenue in 2018?")
question = question or st.session_state.pop("pending", None)
if question:
    with st.chat_message("user"):
        st.write(question)
    with st.chat_message("assistant"):
        with st.spinner("Writing and running SQL..."):
            ans = analyst.ask(question, summarize=summarize)
        render(ans)
    st.session_state.history.append((question, ans))
