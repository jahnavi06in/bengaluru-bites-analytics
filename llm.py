"""Fast, safe Gemini wrapper for Bengaluru Bites dataset Q&A."""

from __future__ import annotations

import json
import os
import re
from typing import Callable

import pandas as pd


# Fast model dedicated to converting natural-language questions into SQL.
DEFAULT_MODEL = "gemini-2.5-flash-lite"


SYSTEM_TEMPLATE = """You are the SQL intelligence engine for Bengaluru Bites.

Your ONLY job is to convert a user's natural-language question into ONE
safe SQLite SELECT query against the restaurants table.

You are answering ONLY from the supplied Bengaluru restaurant dataset.

DATABASE TABLE
---------------
restaurants

COLUMNS
-------
name TEXT
area TEXT
cuisines TEXT
is_veg_only INTEGER
home_delivery INTEGER
takeaway INTEGER
indoor_seating INTEGER
dinner_rating REAL
dinner_reviews INTEGER
delivery_rating REAL
delivery_reviews INTEGER
average_cost INTEGER
popular_dishes TEXT
known_for TEXT
people_known_for TEXT

AREA VALUES
-----------
{areas}

MEANINGS
--------
is_veg_only:
1 = pure vegetarian
0 = not pure vegetarian

home_delivery:
1 = available
0 = unavailable

takeaway:
1 = available
0 = unavailable

indoor_seating:
1 = available
0 = unavailable

delivery_rating:
Best-covered restaurant rating.

dinner_rating:
Dine-in rating.

average_cost:
Average cost for two in Indian rupees.

RULES
-----
1. Return exactly ONE SELECT statement.

2. Never use INSERT, UPDATE, DELETE, DROP, ALTER, CREATE,
   ATTACH, DETACH, PRAGMA, VACUUM, REPLACE, or other write/admin SQL.

3. Never query a table other than restaurants.

4. Never invent a column.

5. Never invent restaurant data.

6. For cuisine searches use:
   LOWER(cuisines) LIKE '%keyword%'

7. For popular dishes use:
   LOWER(popular_dishes) LIKE '%keyword%'

8. For areas use:
   LOWER(area) = LOWER('exact area')

9. When the user says "rating", "best rated", or "highest rated",
   use delivery_rating unless they explicitly say dinner, dine-in,
   or dine in.

10. When calculating or ranking ratings, exclude NULL ratings.

11. When ranking individual restaurants by rating, prefer:
   delivery_reviews >= 50

12. For "how many", use COUNT(*).

13. For averages, use AVG().

14. For highest/lowest use MAX()/MIN() when appropriate.

15. For lists, use LIMIT 20 unless the user asks for another number.

16. If the user asks for a specific number such as top 5, use that LIMIT.

17. Use readable SQL aliases such as:
   avg_rating
   restaurant_count
   avg_cost
   total_reviews

18. If the question cannot be answered from this dataset, return:
   SELECT 'I can only answer questions about the Bengaluru restaurant dataset.' AS message

19. Do not answer using general knowledge.

20. Do not explain the SQL.

The output must contain only the SQL query.
"""


class LLMError(RuntimeError):
    """User-presentable Gemini problem."""


def build_system_prompt(areas: list[str]) -> str:
    return SYSTEM_TEMPLATE.format(
        areas=", ".join(str(a) for a in areas)
    )


def _friendly(exc: Exception) -> LLMError:
    """Convert Gemini exceptions into useful user-facing errors."""

    msg = str(exc)
    low = msg.lower()

    if any(
        x in low
        for x in (
            "api key",
            "api_key",
            "permission_denied",
            "unauthenticated",
            "401",
            "403",
        )
    ):
        return LLMError(
            "Gemini API key/access problem. "
            "Check GEMINI_API_KEY in Streamlit Secrets."
        )

    if any(
        x in low
        for x in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "too many requests",
        )
    ):
        return LLMError(
            "Gemini rate limit/quota reached. "
            "Please wait a little and try again."
        )

    if any(
        x in low
        for x in (
            "404",
            "not_found",
            "not found",
            "model",
            "unsupported",
        )
    ):
        return LLMError(
            "The selected Gemini model is unavailable for this API key/project."
        )

    return LLMError(
        f"Gemini request failed: {msg}"
    )


def _extract_sql(text: str) -> str:
    """Extract SQL safely from model output."""

    text = (text or "").strip()

    if not text:
        raise LLMError(
            "Gemini returned an empty response."
        )

    # Remove accidental markdown fences.
    text = re.sub(
        r"```(?:sql)?",
        "",
        text,
        flags=re.IGNORECASE,
    ).replace("```", "").strip()

    # If structured JSON accidentally arrives as plain text.
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            text = str(obj.get("sql", "")).strip()
        except Exception:
            pass

    if not text:
        raise LLMError(
            "Gemini did not return a SQL query."
        )

    return text


def _validate_model_sql(sql: str) -> str:
    """
    Lightweight pre-validation before the project's existing
    database safety layer performs the final validation.
    """

    cleaned = sql.strip()

    if not re.match(
        r"^\s*(SELECT|WITH)\b",
        cleaned,
        flags=re.IGNORECASE,
    ):
        raise LLMError(
            "Gemini returned something other than a SELECT query."
        )

    blocked = (
        "insert",
        "update",
        "delete",
        "drop",
        "alter",
        "create",
        "attach",
        "detach",
        "pragma",
        "vacuum",
        "replace",
        "truncate",
    )

    lower = cleaned.lower()

    for keyword in blocked:
        if re.search(
            rf"\b{re.escape(keyword)}\b",
            lower,
        ):
            raise LLMError(
                "Gemini generated an unsafe SQL operation."
            )

    return cleaned


def _generate(
    api_key: str,
    prompt: str,
    system: str | None,
    model_override: str | None = None,
) -> str:

    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise LLMError(
            "google-genai is not installed. "
            "Add google-genai to requirements.txt."
        ) from exc

    model = (
        model_override
        or DEFAULT_MODEL
    )

    try:
        client = genai.Client(
            api_key=api_key
        )

        config_kwargs = {
            "system_instruction": system,
            "temperature": 0.0,
            "max_output_tokens": 512,
            "response_mime_type": "application/json",
            "response_schema": {
                "type": "OBJECT",
                "properties": {
                    "sql": {
                        "type": "STRING",
                        "description": (
                            "Exactly one safe SQLite SELECT query "
                            "for the restaurants table."
                        ),
                    }
                },
                "required": ["sql"],
            },
        }

        # Gemini 2.5 Flash-Lite supports thinking_budget.
        # Zero thinking is appropriate here because this request
        # only translates a question into SQL.
        try:
            config_kwargs["thinking_config"] = (
                types.ThinkingConfig(
                    thinking_budget=0
                )
            )
        except Exception:
            # Keep compatibility if the installed SDK exposes
            # a slightly different configuration surface.
            pass

        config = types.GenerateContentConfig(
            **config_kwargs
        )

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        raw = (
            getattr(response, "text", None)
            or ""
        ).strip()

        if not raw:
            raise LLMError(
                "Gemini returned an empty response."
            )

        # Structured output should be JSON.
        try:
            parsed = json.loads(raw)

            sql = str(
                parsed.get("sql", "")
            ).strip()

        except json.JSONDecodeError:
            # Graceful fallback in case the SDK/model returns
            # plain SQL despite the structured-output request.
            sql = _extract_sql(raw)

        sql = _validate_model_sql(sql)

        return sql

    except LLMError:
        raise

    except Exception as exc:
        raise _friendly(exc) from exc


def make_sql_generator(
    api_key: str,
    areas: list[str],
    model_override: str | None = None,
) -> Callable[[str], str]:

    system = build_system_prompt(
        areas
    )

    return lambda question: _generate(
        api_key=api_key,
        prompt=question,
        system=system,
        model_override=model_override,
    )


# ---------------------------------------------------------
# Optional summarizer
# ---------------------------------------------------------
# Your current fast Ask AI flow can pass None here.
# This remains available for other parts of the application.

SUMMARY_PROMPT = """Question: {question}

SQL used:
{sql}

Result:
{table}

Answer the question in 2-3 plain sentences.
Use ONLY the supplied result.
Do not invent numbers.
Mention ₹ for costs.
"""


def make_summarizer(
    api_key: str,
    model_override: str | None = None,
) -> Callable[[str, str, pd.DataFrame], str]:

    def summarize(
        question: str,
        sql: str,
        df: pd.DataFrame,
    ) -> str:

        prompt = SUMMARY_PROMPT.format(
            question=question,
            sql=sql,
            table=df.head(30).to_csv(
                index=False
            ),
        )

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(
                api_key=api_key
            )

            model = (
                model_override
                or DEFAULT_MODEL
            )

            config = types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=200,
            )

            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config,
            )

            return (
                response.text or ""
            ).strip()

        except Exception:
            # Summary is optional.
            # Never fail the actual SQL result because
            # the explanation model call failed.
            return ""

    return summarize


def get_secret(
    name: str,
    st_secrets=None,
) -> str | None:
    """Read Streamlit secret first, then environment variable."""

    value = None

    if st_secrets is not None:
        try:
            value = st_secrets.get(name)
        except Exception:
            value = None

    return value or os.environ.get(name)
