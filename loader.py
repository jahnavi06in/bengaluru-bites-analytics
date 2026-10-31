"""Load and clean the Zomato Bengaluru dataset."""
from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).parent / "data" / "BangaloreZomatoData.csv"

# Columns exposed to the SQL engine (no phone numbers / addresses).
DB_COLUMNS = [
    "name", "area", "cuisines", "is_veg_only", "home_delivery", "takeaway",
    "indoor_seating", "dinner_rating", "dinner_reviews", "delivery_rating",
    "delivery_reviews", "average_cost", "popular_dishes", "known_for",
    "people_known_for",
]

# "Popular dishes" entries that are really categories, not dishes.
GENERIC_DISHES = {
    "starters", "starter", "dessert", "desserts", "snacks", "snack", "sweets",
    "sweet", "spicy food", "beverages", "beverage", "drinks", "main course",
    "food", "combo", "combos", "sides", "non veg", "veg", "fast food",
    "street food", "chinese", "north indian", "south indian",
}
DISH_ALIASES = {
    "ice creams": "Ice Cream", "icecream": "Ice Cream", "pizzas": "Pizza",
    "burgers": "Burger", "sandwiches": "Sandwich", "momo": "Momos",
    "noodle": "Noodles", "salads": "Salad", "rolls": "Roll",
}


def split_list(value) -> list[str]:
    """'A, B, C' -> ['A', 'B', 'C'] (safe for NaN/None)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    return [p.strip() for p in str(value).split(",") if p.strip()]


def normalize_dish(raw: str) -> str | None:
    """Clean one popular-dish label. Returns None for non-dishes."""
    s = (raw or "").strip()
    if not s:
        return None
    low = s.lower()
    if low in GENERIC_DISHES:
        return None
    if "biryani" in low:
        return "Biryani"
    if low in DISH_ALIASES:
        return DISH_ALIASES[low]
    return s[0].upper() + s[1:]


def load_restaurants(path: Path | str = DATA_PATH) -> pd.DataFrame:
    raw = pd.read_csv(path)
    df = pd.DataFrame(
        {
            "name": raw["Name"].astype(str).str.strip(),
            "area": raw["Area"].astype(str).str.split(",").str[0].str.strip(),
            "cuisines": raw["Cuisines"].fillna("").astype(str).str.strip(),
            "is_veg_only": raw["isVegOnly"].astype(int),
            "home_delivery": raw["IsHomeDelivery"].astype(int),
            "takeaway": raw["isTakeaway"].astype(int),
            "indoor_seating": raw["isIndoorSeating"].astype(int),
            # '-' means "not rated" in the source file -> NaN / NULL
            "dinner_rating": pd.to_numeric(raw["Dinner Ratings"], errors="coerce"),
            "dinner_reviews": raw["Dinner Reviews"].astype(int),
            "delivery_rating": pd.to_numeric(raw["Delivery Ratings"], errors="coerce"),
            "delivery_reviews": raw["Delivery Reviews"].astype(int),
            "average_cost": raw["AverageCost"].astype(int),
            "popular_dishes": raw["PopularDishes"].fillna("").astype(str),
            "known_for": raw["KnownFor"].fillna("").astype(str),
            "people_known_for": raw["PeopleKnownFor"].fillna("").astype(str),
            "url": raw["URL"].astype(str),
        }
    )
    df = df[df["name"].str.len() > 0].drop_duplicates(subset="url").reset_index(drop=True)
    return df


def apply_filters(df, areas=None, cuisines=None, veg_only=False, min_reviews=0):
    out = df
    if areas:
        out = out[out["area"].isin(areas)]
    if cuisines:
        wanted = set(cuisines)
        out = out[out["cuisines"].map(lambda s: bool(wanted & set(split_list(s))))]
    if veg_only:
        out = out[out["is_veg_only"] == 1]
    if min_reviews:
        out = out[out["delivery_reviews"] >= min_reviews]
    return out


def all_cuisines(df) -> list[str]:
    seen = set()
    for s in df["cuisines"]:
        seen.update(split_list(s))
    return sorted(seen)


def dish_counts(df, top: int = 8) -> pd.DataFrame:
    counter: Counter = Counter()
    for s in df["popular_dishes"]:
        dishes = {d for d in map(normalize_dish, split_list(s)) if d}
        counter.update(dishes)
    rows = counter.most_common(top)
    return pd.DataFrame(rows, columns=["dish", "restaurants"])


def neighbourhood_stats(df) -> pd.DataFrame:
    g = df.groupby("area").agg(
        restaurants=("name", "size"),
        avg_rating=("delivery_rating", "mean"),
        median_cost=("average_cost", "median"),
    )
    return g.reset_index()


def cuisine_ratings(df, min_n: int = 15) -> pd.DataFrame:
    tmp = df.loc[df["delivery_rating"].notna(), ["cuisines", "delivery_rating"]].copy()
    tmp["cuisine"] = tmp["cuisines"].map(split_list)
    tmp = tmp.explode("cuisine").dropna(subset=["cuisine"])
    g = tmp.groupby("cuisine")["delivery_rating"].agg(["mean", "size"]).reset_index()
    g.columns = ["cuisine", "avg_rating", "restaurants"]
    g = g[g["restaurants"] >= min_n].sort_values("avg_rating", ascending=False)
    return g.reset_index(drop=True)
