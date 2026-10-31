"""Transparent, data-backed recommendation helpers."""
import pandas as pd
from analytics import value_scores

def recommend(df,budget=None,cuisine=None,area=None,min_rating=None,veg=False,delivery=False,n=10):
    x=df.copy()
    if budget is not None: x=x[x["average_cost"]<=budget]
    if cuisine: x=x[x["cuisines"].str.contains(cuisine,case=False,na=False)]
    if area: x=x[x["area"].eq(area)]
    if min_rating is not None: x=x[x["delivery_rating"].ge(min_rating)]
    if veg: x=x[x["is_veg_only"].eq(1)]
    if delivery: x=x[x["home_delivery"].eq(1)]
    x=x[x["delivery_rating"].notna()].copy()
    if x.empty:return x
    x["recommendation_score"]=(x["delivery_rating"]*20 + (x["delivery_reviews"].clip(upper=10000)/10000)*10).round(2)
    x=x.sort_values(["recommendation_score","delivery_rating","delivery_reviews"],ascending=False).head(n)
    def why(r):
        bits=[f"rating {r.delivery_rating:.1f}"]
        if budget is not None: bits.append(f"within ₹{budget:,.0f}")
        if cuisine: bits.append(f"matches {cuisine}")
        if area: bits.append(f"in {area}")
        if veg: bits.append("pure vegetarian")
        if delivery: bits.append("home delivery")
        return "Recommended for " + ", ".join(bits) + "."
    x["why"]=x.apply(why,axis=1)
    return x
