"""Gemini wrapper: turns questions into SQL and explains results."""
from __future__ import annotations

import os
from typing import Callable

import pandas as pd

DEFAULT_MODELS = [
    "gemini-2.5-flash-lite",
]

SYSTEM_TEMPLATE = """You turn questions about Bengaluru restaurants into ONE SQLite query.

Table: restaurants (one row per restaurant)
Columns:
- name TEXT
- area TEXT: neighbourhood. Exact values: {areas}
- cuisines TEXT: comma-separated list, e.g. 'North Indian, Chinese, Biryani'
- is_veg_only INTEGER: 1 = pure vegetarian, 0 = not
- home_delivery, takeaway, indoor_seating INTEGER: 1 = yes, 0 = no
- dinner_rating REAL: dine-in rating, NULL if unrated
- dinner_reviews INTEGER
- delivery_rating REAL: delivery rating, NULL if unrated (best-covered rating)
- delivery_reviews INTEGER
- average_cost INTEGER: average cost in rupees as listed on Zomato
- popular_dishes TEXT: comma-separated list (may be empty)
- known_for TEXT, people_known_for TEXT: comma-separated tags (often empty)

Rules:
1. Reply with ONLY the SQL query. No markdown, no explanation.
2. Exactly one SELECT statement. Never modify data.
3. For cuisines or dishes use case-insensitive LIKE, e.g. LOWER(cuisines) LIKE '%biryani%'.
4. For areas use LOWER(area) = LOWER('HSR') with the exact names above.
5. "Rating" means delivery_rating unless the user says dinner/dine-in.
   When ranking or averaging ratings, add `rating IS NOT NULL`, and when ranking
   individual restaurants also require delivery_reviews >= 50.
6. Give columns readable aliases (e.g. AS avg_cost). Use LIMIT 20 for lists
   unless the user asks for a different number.
7. If the question cannot be answered from this table, return exactly:
   SELECT 'I can only answer questions about the Bengaluru restaurant dataset.' AS message
"""

SUMMARY_PROMPT = """Question: {question}

SQL used:
{sql}

Result (CSV, up to 30 rows):
{table}

In 2-3 plain sentences, answer the question using ONLY the result above.
Do not invent numbers. Mention ₹ for costs. No markdown headings."""


class LLMError(RuntimeError):
    """A user-presentable problem talking to the model."""


_working_model: str | None = None


def build_system_prompt(areas: list[str]) -> str:
    return SYSTEM_TEMPLATE.format(areas=", ".join(areas))


def _friendly(exc: Exception) -> LLMError:
    msg = str(exc)
    low = msg.lower()
    if any(t in low for t in ("api key", "api_key", "permission_denied", "401", "403")):
        return LLMError("The Gemini API key was rejected. Check GEMINI_API_KEY in the app's Secrets.")
    if any(t in low for t in ("429", "resource_exhausted", "quota")):
        return LLMError("The AI is rate-limited right now. Please wait a minute and try again.")
    return LLMError("The AI service had a problem. Please try again in a moment.")


def _is_model_missing(exc: Exception) -> bool:
    low = str(exc).lower()
    return any(t in low for t in ("404", "not_found", "not found", "is not supported"))


def _generate(api_key: str, prompt: str, system: str | None, model_override: str | None) -> str:
    global _working_model
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise LLMError("The google-genai package is not installed.") from exc

    client = genai.Client(api_key=api_key)
    candidates = [model_override] if model_override else []
    if _working_model:
        candidates.append(_working_model)
    candidates += [m for m in DEFAULT_MODELS if m not in candidates]

    last_exc: Exception | None = None
    for model in candidates:
        try:
            cfg = types.GenerateContentConfig(system_instruction=system) if system else None
            resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
            text = (resp.text or "").strip()
            if not text:
                raise LLMError("The AI returned an empty answer. Try rephrasing the question.")
            _working_model = model
            return text
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if _is_model_missing(exc):
                continue
            raise _friendly(exc) from exc
    raise _friendly(last_exc or RuntimeError("no model available"))


def make_sql_generator(api_key: str, areas: list[str], model_override: str | None = None) -> Callable[[str], str]:
    system = build_system_prompt(areas)
    return lambda prompt: _generate(api_key, prompt, system, model_override)


def make_summarizer(api_key: str, model_override: str | None = None) -> Callable[[str, str, pd.DataFrame], str]:
    def summarize(question: str, sql: str, df: pd.DataFrame) -> str:
        prompt = SUMMARY_PROMPT.format(
            question=question, sql=sql, table=df.head(30).to_csv(index=False)
        )
        return _generate(api_key, prompt, None, model_override)

    return summarize


def get_secret(name: str, st_secrets=None) -> str | None:
    """Read from Streamlit secrets if available, else environment."""
    value = None
    if st_secrets is not None:
        try:
            value = st_secrets.get(name)
        except Exception:  # no secrets file configured
            value = None
    return value or os.environ.get(name)
