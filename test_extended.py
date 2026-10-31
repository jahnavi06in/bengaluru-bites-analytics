"""Extended QA tests for analytics, recommendations and reporting."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from loader import load_restaurants, apply_filters
from analytics import kpis, cuisine_stats, locality_stats, locality_diversity, value_scores, data_quality_report, segment_restaurants, correlation
from recommendations import recommend
from reporting import business_pdf, dataframe_csv
DF=load_restaurants()

def test_kpis_are_data_derived():
    k=kpis(DF); assert k["restaurants"]==8923; assert k["localities"]==168; assert 0<k["veg_pct"]<100
def test_cuisine_associations_expand():
    c=cuisine_stats(DF); assert len(c)>20 and "Biryani" in set(c.cuisine)
def test_locality_stats():
    x=locality_stats(DF); assert x.restaurants.sum()==len(DF)
def test_diversity():
    x=locality_diversity(DF); assert x.cuisine_diversity.max()>0
def test_value_score_bounds():
    x=value_scores(DF); assert x.value_score.between(0,100).all()
def test_quality_schema():
    report,dupes,issues,score=data_quality_report(DF); assert "completeness_pct" in report; assert dupes==0; assert 0<=score<=100
def test_segments_cover_all():
    x=segment_restaurants(DF); assert len(x)==len(DF); assert x.segment.notna().all()
def test_correlation_shape():
    x=correlation(DF); assert "average_cost" in x.columns and "delivery_rating" in x.columns
def test_recommendations_respect_budget():
    x=recommend(DF,budget=300,min_rating=4.0,n=10); assert (x.average_cost<=300).all()
def test_recommendations_respect_veg():
    x=recommend(DF,budget=1000,min_rating=3.5,veg=True,n=10); assert x.is_veg_only.eq(1).all()
def test_csv_export():
    b=dataframe_csv(DF.head(2)); assert b.startswith(b"name,")
def test_pdf_export():
    b=business_pdf("Test",{"restaurants":2},["Finding"],["Limitation"]); assert b[:4]==b"%PDF"
