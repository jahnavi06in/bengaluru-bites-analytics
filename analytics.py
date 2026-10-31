"""Business analytics for Bengaluru Bites. All outputs derive from the supplied dataset."""
from __future__ import annotations
import numpy as np
import pandas as pd
from loader import split_list

def kpis(df):
    rated=df["delivery_rating"].dropna()
    return {
        "restaurants": len(df),
        "avg_rating": float(rated.mean()) if len(rated) else np.nan,
        "avg_cost": float(df["average_cost"].mean()) if len(df) else np.nan,
        "median_cost": float(df["average_cost"].median()) if len(df) else np.nan,
        "localities": int(df["area"].nunique()),
        "veg_pct": float(df["is_veg_only"].mean()*100) if len(df) else 0,
        "delivery_pct": float(df["home_delivery"].mean()*100) if len(df) else 0,
        "takeaway_pct": float(df["takeaway"].mean()*100) if len(df) else 0,
        "indoor_pct": float(df["indoor_seating"].mean()*100) if len(df) else 0,
        "cuisine_count": int(len({c for s in df["cuisines"] for c in split_list(s)})),
    }

def cuisine_stats(df):
    rows=[]
    for idx,row in df[["cuisines","delivery_rating","average_cost","delivery_reviews","area"]].iterrows():
        for c in split_list(row["cuisines"]):
            rows.append((c,row["delivery_rating"],row["average_cost"],row["delivery_reviews"],row["area"]))
    x=pd.DataFrame(rows,columns=["cuisine","rating","cost","reviews","area"])
    if x.empty: return x
    return x.groupby("cuisine").agg(restaurants=("cuisine","size"),avg_rating=("rating","mean"),
        avg_cost=("cost","mean"),median_cost=("cost","median"),avg_reviews=("reviews","mean")).reset_index()

def locality_stats(df):
    return df.groupby("area").agg(restaurants=("name","size"),avg_rating=("delivery_rating","mean"),
        avg_cost=("average_cost","mean"),median_cost=("average_cost","median"),
        veg_pct=("is_veg_only","mean"),cuisine_entries=("cuisines","size")).reset_index()

def locality_diversity(df):
    rows=[]
    for area,g in df.groupby("area"):
        cuisines={c for s in g["cuisines"] for c in split_list(s)}
        rows.append({"area":area,"restaurants":len(g),"cuisine_diversity":len(cuisines)})
    return pd.DataFrame(rows).sort_values(["cuisine_diversity","restaurants"],ascending=False)

def value_scores(df, min_reviews=50):
    x=df.copy()
    x=x[x["delivery_rating"].notna() & (x["delivery_reviews"]>=min_reviews) & (x["average_cost"]>0)]
    if x.empty: return x.assign(value_score=pd.Series(dtype=float))
    # Transparent, bounded heuristic: rating normalized against cost percentile.
    cost_q=x["average_cost"].rank(pct=True, method="average")
    rating_norm=(x["delivery_rating"]-2.4)/(4.7-2.4)
    x["value_score"]=(100*(0.7*rating_norm+0.3*(1-cost_q))).round(1)
    return x.sort_values(["value_score","delivery_reviews"],ascending=False)

def correlation(df):
    x=df[["average_cost","delivery_rating","delivery_reviews"]].corr(numeric_only=True)
    return x

def best_value(df, n=10, min_reviews=50):
    return value_scores(df,min_reviews).head(n)

def high_rating_low_reviews(df, n=10, max_reviews=500):
    x=df[df["delivery_rating"].notna() & (df["delivery_reviews"]<=max_reviews)].copy()
    return x.sort_values(["delivery_rating","delivery_reviews"],ascending=[False,True]).head(n)

def anomalies(df):
    issues=[]
    if (df["average_cost"]<=0).any(): issues.append(("Non-positive cost",int((df["average_cost"]<=0).sum())))
    if ((df["delivery_rating"]<0)|(df["delivery_rating"]>5)).any(): issues.append(("Invalid delivery rating",int(((df["delivery_rating"]<0)|(df["delivery_rating"]>5)).sum())))
    if (df["name"].str.strip()=="").any(): issues.append(("Blank restaurant name",int((df["name"].str.strip()=="").sum())))
    if df["cuisines"].str.strip().eq("").any(): issues.append(("Missing cuisine",int(df["cuisines"].str.strip().eq("").sum())))
    return pd.DataFrame(issues,columns=["issue","records"])

def data_quality_report(df):
    rows=[]
    for c in df.columns:
        missing=int(df[c].isna().sum())
        blanks=int(df[c].astype(str).str.strip().eq("").sum()) if df[c].dtype=="object" else 0
        rows.append({"column":c,"records":len(df),"missing":missing,"blanks":blanks,
                     "completeness_pct":round(100*(len(df)-missing-blanks)/len(df),2) if len(df) else 0,
                     "unique":int(df[c].nunique(dropna=True))})
    report=pd.DataFrame(rows)
    duplicate=int(df.duplicated().sum())
    issue_count=int(report["missing"].sum()+report["blanks"].sum()+duplicate+len(anomalies(df)))
    score=max(0,round(100*(1-min(issue_count/(max(len(df),1)*0.02),1)),1))
    return report, duplicate, anomalies(df), score

def segment_restaurants(df):
    x=df.copy()
    x["segment"]=np.select([
        x["delivery_rating"].ge(4.2)&x["average_cost"].le(x["average_cost"].median()),
        x["delivery_rating"].ge(4.2),
        x["average_cost"].le(x["average_cost"].median()),
    ],["High-rated value","Premium high-rated","Budget-friendly"],default="Mainstream")
    return x
