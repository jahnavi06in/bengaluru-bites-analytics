"""Read-only SQLite layer + SQL validation for AI-generated queries."""
from __future__ import annotations

import re
import sqlite3
import threading
import time

import pandas as pd

from loader import DB_COLUMNS

TABLE = "restaurants"
MAX_ROWS = 200
TIMEOUT_SECONDS = 3.0
_LOCK = threading.Lock()


class SQLRejected(ValueError):
    """The generated SQL is not a single, safe SELECT."""


class QueryError(RuntimeError):
    """The SQL was valid but failed when executed."""


_BLOCKED = re.compile(
    r"\b(insert|update|delete|drop|alter|create|attach|detach|pragma|"
    r"truncate|vacuum|reindex|load_extension)\b",
    re.I,
)
_FENCE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.I | re.S)


def clean_sql(raw: str) -> str:
    """Normalise model output and make sure it is one read-only SELECT."""
    if not raw or not raw.strip():
        raise SQLRejected("The model returned an empty query.")
    text = raw.strip()
    fence = _FENCE.search(text)
    if fence:
        text = fence.group(1).strip()
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)      # block comments
    text = re.sub(r"--[^\n]*", " ", text)                    # line comments
    text = text.strip().rstrip(";").strip()
    if not text:
        raise SQLRejected("The model returned an empty query.")
    if ";" in text:
        raise SQLRejected("Only one query is allowed.")
    if not re.match(r"^(select|with)\b", text, re.I):
        raise SQLRejected("Only SELECT queries are allowed.")
    if _BLOCKED.search(text):
        raise SQLRejected("That query contains a statement that isn't allowed.")
    return text


_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def _authorizer(action, arg1, arg2, db_name, source):
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY


def build_connection(df: pd.DataFrame) -> sqlite3.Connection:
    """In-memory DB, loaded once, then locked down to read-only."""
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    df[DB_COLUMNS].to_sql(TABLE, conn, index=False)
    conn.execute("PRAGMA query_only = ON")
    conn.set_authorizer(_authorizer)
    return conn


def run_query(conn: sqlite3.Connection, sql: str) -> pd.DataFrame:
    # The AI playground is intentionally scoped to the analytics table.
    # The SQLite authorizer is the final enforcement layer.
    normalized = sql.lower()
    if "sqlite_" in normalized or "information_schema" in normalized:
        raise QueryError("System catalog access is not allowed.")
    deadline = time.monotonic() + TIMEOUT_SECONDS

    def _abort():
        return 1 if time.monotonic() > deadline else 0

    with _LOCK:
        conn.set_progress_handler(_abort, 10000)
        try:
            cur = conn.execute(sql)
            cols = [d[0] for d in cur.description] if cur.description else []
            rows = cur.fetchmany(MAX_ROWS)
        except sqlite3.Error as exc:
            raise QueryError(str(exc)) from exc
        finally:
            conn.set_progress_handler(None, 0)
    return pd.DataFrame(rows, columns=cols)
