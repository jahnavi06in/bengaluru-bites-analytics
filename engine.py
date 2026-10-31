"""Question -> SQL -> result pipeline (model calls are injected, so it is testable)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

from database import QueryError, SQLRejected, clean_sql


@dataclass
class Answer:
    sql: str
    df: pd.DataFrame
    summary: str | None = None
    retried: bool = False


def answer_question(
    question: str,
    generate_sql: Callable[[str], str],
    run_sql: Callable[[str], pd.DataFrame],
    summarize: Callable[[str, str, pd.DataFrame], str] | None = None,
) -> Answer:
    """Generate SQL, run it, retry once with the error message, then summarise."""
    prompt = question
    retried = False
    last_error: Exception | None = None

    for attempt in range(2):
        try:
            sql = clean_sql(generate_sql(prompt))
            df = run_sql(sql)
            break
        except (SQLRejected, QueryError) as exc:
            last_error = exc
            if attempt == 1:
                raise
            retried = True
            prompt = (
                f"{question}\n\nYour previous attempt failed: {exc}\n"
                "Return a corrected single SQLite SELECT query only."
            )
    else:  # pragma: no cover
        raise last_error  # type: ignore[misc]

    summary = None
    is_refusal = list(df.columns) == ["message"]
    if summarize and not df.empty and not is_refusal:
        try:
            summary = summarize(question, sql, df)
        except Exception:  # noqa: BLE001 - the table alone is still a good answer
            summary = None
    return Answer(sql=sql, df=df, summary=summary, retried=retried)
