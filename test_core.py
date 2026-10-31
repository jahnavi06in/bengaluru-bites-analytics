"""Run with:  python tests/test_core.py   (or: pytest)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from database import QueryError, SQLRejected, build_connection, clean_sql, run_query
from engine import answer_question
from loader import (apply_filters, cuisine_ratings, dish_counts, load_restaurants,
                    neighbourhood_stats, normalize_dish)

DF = load_restaurants()
CONN = build_connection(DF)


def test_loading():
    assert len(DF) == 8923
    assert DF["delivery_rating"].notna().sum() == 7792       # '-' became NULL
    assert not DF["area"].str.contains(",").any()


def test_filters_default_to_all():
    assert len(apply_filters(DF)) == len(DF)
    assert len(apply_filters(DF, areas=["HSR"])) == 457
    assert apply_filters(DF, veg_only=True)["is_veg_only"].eq(1).all()
    assert apply_filters(DF, cuisines=["Biryani"])["cuisines"].str.contains("Biryani").all()


def test_dishes_clean():
    names = set(dish_counts(DF, top=30)["dish"])
    assert not names & {"Starters", "Dessert", "Desserts", "Spicy Food"}
    assert "Chicken Biryani" not in names and "Biryani" in names
    assert normalize_dish("Starters") is None and normalize_dish("Pizzas") == "Pizza"


def test_stats():
    s = neighbourhood_stats(DF).sort_values("restaurants", ascending=False)
    assert s.iloc[0]["area"] == "Electronic City"
    assert len(cuisine_ratings(DF)) > 5


def test_sql_validation():
    for bad in ["DROP TABLE restaurants", "SELECT 1; SELECT 2", "UPDATE restaurants SET name='x'",
                "PRAGMA query_only=OFF", "", "DELETE FROM restaurants"]:
        try:
            clean_sql(bad)
            raise AssertionError(f"accepted: {bad}")
        except SQLRejected:
            pass
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"
    assert clean_sql("WITH a AS (SELECT 1) SELECT * FROM a") .startswith("WITH")


def test_db_is_read_only():
    for bad in ["DELETE FROM restaurants", "DROP TABLE restaurants", "CREATE TABLE t(a)",
                "WITH x AS (SELECT 1) INSERT INTO restaurants(name) VALUES('a')"]:
        try:
            run_query(CONN, bad)
            raise AssertionError(f"ran: {bad}")
        except QueryError:
            pass
    assert run_query(CONN, "SELECT COUNT(*) AS n FROM restaurants").iloc[0, 0] == 8923


def test_runaway_query_times_out():
    try:
        run_query(CONN, "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c")
        raise AssertionError("no timeout")
    except QueryError:
        pass


# Reference SQL a good model would produce for each example in app.py
EXAMPLE_SQL = {
    "most restaurants": "SELECT area, COUNT(*) AS restaurants FROM restaurants GROUP BY area ORDER BY restaurants DESC LIMIT 20",
    "top rated HSR": "SELECT name, delivery_rating, delivery_reviews FROM restaurants WHERE LOWER(area)=LOWER('HSR') AND delivery_rating IS NOT NULL AND delivery_reviews >= 50 ORDER BY delivery_rating DESC, delivery_reviews DESC LIMIT 10",
    "highest avg cost": "SELECT area, ROUND(AVG(average_cost)) AS avg_cost, COUNT(*) AS n FROM restaurants GROUP BY area HAVING n >= 10 ORDER BY avg_cost DESC LIMIT 10",
    "veg indiranagar": "SELECT COUNT(*) AS veg_restaurants FROM restaurants WHERE LOWER(area)=LOWER('Indiranagar') AND is_veg_only = 1",
    "cheap biryani BTM": "SELECT name, average_cost, delivery_rating FROM restaurants WHERE LOWER(area)=LOWER('BTM') AND LOWER(cuisines) LIKE '%biryani%' AND delivery_rating >= 4.0 AND delivery_reviews >= 50 ORDER BY average_cost ASC LIMIT 20",
}


def test_every_example_has_data():
    for label, sql in EXAMPLE_SQL.items():
        out = run_query(CONN, clean_sql(sql))
        assert len(out) > 0, label
    assert run_query(CONN, EXAMPLE_SQL["veg indiranagar"]).iloc[0, 0] > 0


def test_pipeline_and_retry():
    calls = []

    def gen(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return "SELECT nonexistent_col FROM restaurants"
        return "```sql\nSELECT COUNT(*) AS n FROM restaurants;\n```"

    ans = answer_question("how many?", gen, lambda s: run_query(CONN, s),
                          lambda q, s, d: f"There are {d.iloc[0,0]} restaurants.")
    assert ans.retried and len(calls) == 2 and "failed" in calls[1]
    assert ans.summary == "There are 8923 restaurants."


def test_pipeline_gives_up_after_one_retry():
    try:
        answer_question("x", lambda p: "DROP TABLE restaurants", lambda s: run_query(CONN, s))
        raise AssertionError("should raise")
    except SQLRejected:
        pass


def test_summary_failure_is_not_fatal():
    def boom(q, s, d):
        raise RuntimeError("quota")
    ans = answer_question("x", lambda p: "SELECT 1 AS a", lambda s: run_query(CONN, s), boom)
    assert ans.summary is None and ans.df.iloc[0, 0] == 1


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("PASS", t.__name__)
    print(f"\n{len(tests)} tests passed")
