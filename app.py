"""Bengaluru Bites — Food Intelligence Platform."""
from pathlib import Path
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Bengaluru Bites | Food Intelligence", page_icon="BB", layout="wide", initial_sidebar_state="expanded")

from loader import all_cuisines, apply_filters, cuisine_ratings, dish_counts, load_restaurants, split_list
from database import QueryError, SQLRejected, build_connection, clean_sql, run_query
from engine import answer_question
from llm import LLMError, get_secret, make_sql_generator, make_summarizer
from analytics import kpis, cuisine_stats, locality_stats, locality_diversity, value_scores, correlation, best_value, high_rating_low_reviews, data_quality_report, segment_restaurants
from recommendations import recommend
from persistence import connect as user_connect, add_favorite, remove_favorite, favorites, add_search, searches, save_comparison, comparisons
from reporting import dataframe_csv, business_pdf

EXAMPLES=[
"Which locality has the most restaurants?",
"Which cuisines have the highest average ratings?",
"Find affordable restaurants with high ratings.",
"Compare restaurants in Indiranagar and Koramangala.",
"Which restaurants have the highest review counts?",
"What is the average cost by locality?",
"Which cuisines are most popular?"
]

st.markdown("""<style>
:root{--burgundy:#6b1f3a;--burgundy-2:#8a2d4f;--deep:#3b1222;--rose:#f0dfe5;--ivory:#fffaf5;--cream:#f6eee8;--surface:#fffdfb;--charcoal:#2b2225;--taupe:#786a69;--border:#e4d4d8}
.stApp{background:var(--ivory);color:var(--charcoal)}
section[data-testid="stSidebar"]{background:linear-gradient(180deg,#f8f0ea 0%,#f3e7e1 100%);border-right:1px solid var(--border)}
section[data-testid="stSidebar"] h3,section[data-testid="stSidebar"] strong{color:var(--deep)}
section[data-testid="stSidebar"] [data-baseweb="tag"]{background:var(--burgundy);color:white}
.stButton>button,.stDownloadButton>button{background:var(--burgundy);color:white;border:1px solid var(--burgundy);border-radius:10px;font-weight:650}
.stButton>button:hover,.stDownloadButton>button:hover{background:var(--burgundy-2);border-color:var(--burgundy-2);color:white}
.stTextInput input:focus,.stSelectbox [data-baseweb="select"]>div:focus-within{border-color:var(--burgundy)}
.bb-hero{padding:32px 36px;border:1px solid var(--border);border-radius:22px;background:linear-gradient(115deg,#fffdfb 0%,#f8e9ed 58%,#f2dfe5 100%);margin-bottom:20px;box-shadow:0 10px 30px rgba(107,31,58,.07)}
.bb-kicker{letter-spacing:.16em;font-size:.72rem;font-weight:800;color:var(--burgundy)}
.bb-title{font-size:2.45rem;font-weight:800;line-height:1.1;margin:7px 0;color:var(--deep)}
.bb-sub{font-size:1rem;color:#66595b;max-width:820px;line-height:1.6}
.bb-card{padding:18px;border:1px solid var(--border);border-radius:16px;background:var(--surface);box-shadow:0 6px 18px rgba(59,18,34,.045)}
.small{color:var(--taupe);font-size:.86rem}
div[data-testid="stMetric"]{background:var(--surface);border:1px solid var(--border);padding:14px;border-radius:14px;box-shadow:0 5px 16px rgba(59,18,34,.04)}
div[data-testid="stMetric"] label{color:var(--taupe)}
div[data-testid="stMetricValue"]{color:var(--deep)}
hr{border-color:var(--border)}
</style>""", unsafe_allow_html=True)

# Consistent burgundy palette for Plotly charts.
px.defaults.color_discrete_sequence = ["#6b1f3a", "#8a2d4f", "#b45f7c", "#d59bad", "#4a2634", "#9b7280"]

@st.cache_data(show_spinner="Loading source data")
def get_data(): return load_restaurants()

@st.cache_resource
def get_connection(): return build_connection(get_data())

df_all=get_data()
areas=sorted(df_all.area.dropna().unique())
cuisines=all_cuisines(df_all)

with st.sidebar:
    st.markdown("### Bengaluru Bites")
    st.caption("Food Intelligence Platform")
    nav=st.radio("Navigate",["Overview","Restaurant Explorer","Cuisine Intelligence","Location Intelligence","Price & Rating","Comparison Studio","Smart Recommendations","Ask AI","Data Quality","Advanced Data Lab","Reports & Exports","My Space","About"])
    st.divider()
    st.markdown("**Global filters**")
    sel_areas=st.multiselect("Locality",areas)
    sel_cuisines=st.multiselect("Cuisine",cuisines)
    veg=st.toggle("Pure vegetarian")
    min_reviews=st.slider("Minimum delivery reviews",0,5000,0,50)
    filtered=apply_filters(df_all,sel_areas,sel_cuisines,veg,min_reviews)
    st.caption(f"{len(filtered):,} restaurants in current view")

st.markdown("""<div class="bb-hero"><div class="bb-kicker">BENGALURU · FOOD DATA · DECISION INTELLIGENCE</div>
<div class="bb-title">Bengaluru Bites</div><div class="bb-sub">Explore restaurant data, benchmark localities and cuisines, evaluate value, and ask the dataset questions in plain English.</div></div>""",unsafe_allow_html=True)

def metric_row(d):
    ks=kpis(d); cols=st.columns(5)
    vals=[(f"{ks['restaurants']:,}","Restaurants"),(f"{ks['avg_rating']:.2f}" if pd.notna(ks['avg_rating']) else "—","Avg rating"),
          (f"₹{ks['median_cost']:,.0f}" if pd.notna(ks['median_cost']) else "—","Median cost"),
          (f"{ks['localities']:,}","Localities"),(f"{ks['veg_pct']:.1f}%","Pure veg")]
    for c,(v,l) in zip(cols,vals): c.metric(l,v)

def show_table(d):
    st.dataframe(d,hide_index=True,use_container_width=True)

if nav=="Overview":
    metric_row(filtered)
    if filtered.empty: st.warning("No records match the current filters.")
    else:
        a,b=st.columns(2)
        with a:
            st.subheader("Top-rated restaurants")
            x=filtered[filtered.delivery_rating.notna() & (filtered.delivery_reviews>=max(100,min_reviews))].sort_values(["delivery_rating","delivery_reviews"],ascending=False).head(10)
            show_table(x[["name","area","cuisines","average_cost","delivery_rating","delivery_reviews","url"]].rename(columns={"name":"Restaurant","area":"Locality","cuisines":"Cuisine","average_cost":"Cost","delivery_rating":"Rating","delivery_reviews":"Reviews","url":"Source"}))
        with b:
            st.subheader("Rating distribution")
            st.plotly_chart(px.histogram(filtered,x="delivery_rating",nbins=12,title="Delivery ratings"),use_container_width=True)
        a,b=st.columns(2)
        with a:
            st.subheader("Popular dishes")
            dishes=dish_counts(filtered,top=10)
            show_table(dishes.rename(columns={"dish":"Dish","restaurants":"Restaurants"}))
        with b:
            st.subheader("Most represented cuisines")
            cs=cuisine_stats(filtered).sort_values("restaurants",ascending=False).head(12)
            st.plotly_chart(px.bar(cs.sort_values("restaurants"),x="restaurants",y="cuisine",orientation="h"),use_container_width=True)
        st.subheader("Locality leaderboard")
        ls=locality_stats(filtered).sort_values("restaurants",ascending=False).head(12)
        st.plotly_chart(px.bar(ls.sort_values("restaurants"),x="restaurants",y="area",orientation="h"),use_container_width=True)
        st.subheader("Business insights")
        ls=locality_stats(filtered)
        cs=cuisine_stats(filtered)
        if not ls.empty:
            top=ls.loc[ls.restaurants.idxmax()]; expensive=ls.loc[ls.avg_cost.idxmax()]
            st.write(f"**Largest restaurant concentration:** {top.area} with {int(top.restaurants):,} listings.")
            st.write(f"**Highest average listed cost among localities in this view:** {expensive.area} at ₹{expensive.avg_cost:,.0f}. This is descriptive, not causal.")

elif nav=="Restaurant Explorer":
    st.subheader("Restaurant Explorer")
    q=st.text_input("Search restaurant name")
    x=filtered[filtered.name.str.contains(q,case=False,na=False)] if q else filtered.copy()
    sort=st.selectbox("Sort by",["Rating","Cost","Reviews","Name"])
    asc=st.toggle("Ascending",False)
    col={"Rating":"delivery_rating","Cost":"average_cost","Reviews":"delivery_reviews","Name":"name"}[sort]
    x=x.sort_values(col,ascending=asc,na_position="last")
    show_table(x[["name","area","cuisines","average_cost","delivery_rating","delivery_reviews","is_veg_only","home_delivery","takeaway","indoor_seating","url"]].head(500))
    st.download_button("Download filtered CSV",dataframe_csv(x),file_name="bengaluru_bites_filtered.csv",mime="text/csv")
    if not x.empty:
        fav_name=st.selectbox("Save a restaurant to My Space",x.name.tolist())
        fav_row=x[x.name.eq(fav_name)].iloc[0]
        if st.button("Save favorite"):
            add_favorite(user_connect(),fav_name,fav_row.url)
            st.success(f"Saved {fav_name} to My Space.")

elif nav=="Cuisine Intelligence":
    st.subheader("Cuisine Intelligence")
    cs=cuisine_stats(filtered)
    st.caption("A multi-cuisine restaurant contributes once to each cuisine category. Counts therefore represent cuisine associations, not unique restaurants.")
    if not cs.empty:
        a,b=st.columns(2)
        with a: st.plotly_chart(px.bar(cs.nlargest(15,"restaurants").sort_values("restaurants"),x="restaurants",y="cuisine",orientation="h",title="Cuisine prevalence"),use_container_width=True)
        with b:
            rated=cs.dropna(subset=["avg_rating"]).query("restaurants>=15").nlargest(15,"avg_rating")
            st.plotly_chart(px.bar(rated.sort_values("avg_rating"),x="avg_rating",y="cuisine",orientation="h",title="Highest average rating"),use_container_width=True)
        show_table(cs.sort_values("restaurants",ascending=False).round(2))

elif nav=="Location Intelligence":
    st.subheader("Location Intelligence")
    ls=locality_stats(filtered); div=locality_diversity(filtered)
    if not ls.empty:
        a,b=st.columns(2)
        with a: st.plotly_chart(px.bar(ls.nlargest(15,"restaurants").sort_values("restaurants"),x="restaurants",y="area",orientation="h",title="Restaurant concentration"),use_container_width=True)
        with b: st.plotly_chart(px.bar(ls.nlargest(15,"cuisine_entries").sort_values("cuisine_entries"),x="cuisine_entries",y="area",orientation="h",title="Cuisine associations"),use_container_width=True)
        show_table(div.head(30).rename(columns={"area":"Locality","restaurants":"Restaurants","cuisine_diversity":"Distinct cuisines"}))

elif nav=="Price & Rating":
    st.subheader("Price & Rating Intelligence")
    metric_row(filtered)
    x=filtered[["average_cost","delivery_rating","delivery_reviews"]].dropna()
    a,b=st.columns(2)
    with a:
        st.plotly_chart(px.scatter(x.sample(min(2500,len(x)),random_state=7),x="average_cost",y="delivery_rating",hover_data=["delivery_reviews"],title="Cost vs rating"),use_container_width=True)
    with b:
        st.dataframe(correlation(filtered).round(3),use_container_width=True)
        st.caption("Correlation measures association, not causation.")
    st.subheader("High-rated, relatively low-review restaurants")
    show_table(high_rating_low_reviews(filtered).head(15)[["name","area","delivery_rating","delivery_reviews","average_cost","url"]])
    st.subheader("Best value")
    show_table(best_value(filtered).head(15)[["name","area","delivery_rating","delivery_reviews","average_cost","value_score","url"]])
    st.caption("Value score is a transparent heuristic: 70% rating normalization and 30% inverse cost percentile, with a minimum review threshold. It is not a market or financial score.")

elif nav=="Comparison Studio":
    st.subheader("Restaurant Comparison Studio")
    choices=sorted(filtered.name.unique())
    selected=st.multiselect("Choose 2–4 restaurants",choices,max_selections=4)
    if 2<=len(selected)<=4:
        x=filtered[filtered.name.isin(selected)].copy()
        cols=["name","area","cuisines","delivery_rating","delivery_reviews","average_cost","is_veg_only","home_delivery","takeaway","indoor_seating","url"]
        show_table(x[cols])
        save_comparison(user_connect(),selected)
    else: st.info("Select 2–4 restaurants to compare.")
    if len(selected)>=2:
        st.download_button("Download comparison CSV",dataframe_csv(filtered[filtered.name.isin(selected)]),file_name="restaurant_comparison.csv",mime="text/csv")

elif nav=="Smart Recommendations":
    st.subheader("Smart Recommendations")
    a,b=st.columns(2)
    with a: budget=st.number_input("Maximum cost for two (₹)",50,10000,800,50)
    with b: cuisine_q=st.selectbox("Cuisine",["Any"]+cuisines)
    a,b,c=st.columns(3)
    with a: area_q=st.selectbox("Locality",["Any"]+areas)
    with b: rating_q=st.slider("Minimum rating",0.0,5.0,4.0,0.1)
    with c: delivery_q=st.toggle("Home delivery")
    rec=recommend(df_all,budget,cuisine_q if cuisine_q!="Any" else None,area_q if area_q!="Any" else None,rating_q,veg,delivery_q,10)
    if rec.empty: st.warning("No restaurants meet these criteria. Relax one filter.")
    else: show_table(rec[["name","area","cuisines","average_cost","delivery_rating","delivery_reviews","why","url"]])

elif nav=="Ask AI":
    st.subheader("Ask AI — Gemini Food Intelligence")
    st.caption("Gemini generates a read-only SQL query; SQLite validates and executes it against the real dataset. Results are never invented.")
    api_key=get_secret("GEMINI_API_KEY",st.secrets); model=get_secret("GEMINI_MODEL",st.secrets)
    if not api_key: st.info("Gemini is unavailable because GEMINI_API_KEY is not configured. All non-AI analytics remain available.")
    else:
        q=st.text_input("Ask a question",placeholder="Which locality has the most restaurants?")
        st.caption("Suggested questions: "+ " · ".join(EXAMPLES[:4]))
        if st.button("Run analysis",type="primary") and q.strip():
            add_search(user_connect(),q.strip())
            with st.spinner("Generating and validating SQL"):
                try:
                    ans=answer_question(q.strip(),make_sql_generator(api_key,areas,model),lambda s:run_query(get_connection(),s),make_summarizer(api_key,model))
                    if ans.summary: st.success(ans.summary)
                    if ans.df.empty: st.warning("The query returned no rows.")
                    else:
                        show_table(ans.df)
                        st.download_button("Download result CSV",dataframe_csv(ans.df),file_name="ai_query_result.csv",mime="text/csv")
                    with st.expander("SQL preview and method"):
                        st.code(ans.sql,"sql"); st.caption("One automatic correction attempt is allowed when the first query fails.")
                except SQLRejected as e: st.error(f"Safe-query check rejected the generated SQL: {e}")
                except QueryError as e: st.error(f"Query could not be executed safely: {e}")
                except LLMError as e: st.error(str(e))
                except Exception: st.error("The AI operation failed. No fabricated result was shown.")

elif nav=="Data Quality":
    st.subheader("Data Quality Centre")
    report,dupes,issues,score=data_quality_report(filtered)
    c1,c2,c3=st.columns(3); c1.metric("Quality score",f"{score}/100"); c2.metric("Duplicate rows",f"{dupes:,}"); c3.metric("Records",f"{len(filtered):,}")
    st.caption("Score methodology: a transparent completeness/issue heuristic. It is a monitoring indicator, not an official data-quality standard.")
    st.subheader("Column completeness"); show_table(report.sort_values("completeness_pct"))
    st.subheader("Detected value issues"); show_table(issues if not issues.empty else pd.DataFrame({"status":["No rule-based value issues detected"]}))
    st.download_button("Download data-quality CSV",dataframe_csv(report),file_name="data_quality_report.csv",mime="text/csv")
    st.info("Original CSV is preserved unchanged. Cleaning occurs in the analytical loader; no source records are overwritten.")

elif nav=="Advanced Data Lab":
    st.subheader("Advanced Data Lab")
    mode=st.selectbox("Analysis",["Segmentation","Correlation Matrix","Outlier Detection","Budget Planner","SQL Playground","Analytical Challenge"])
    if mode=="Segmentation":
        x=segment_restaurants(filtered); seg=x.groupby("segment").size().reset_index(name="restaurants")
        st.plotly_chart(px.bar(seg,x="segment",y="restaurants"),use_container_width=True); show_table(seg)
        st.caption("Rule-based segmentation uses rating and median cost. It is not machine learning.")
    elif mode=="Correlation Matrix":
        st.plotly_chart(px.imshow(correlation(filtered),text_auto=True,aspect="auto",color_continuous_scale="RdBu"),use_container_width=True)
    elif mode=="Outlier Detection":
        x=filtered.copy(); q1=x.average_cost.quantile(.25); q3=x.average_cost.quantile(.75); iqr=q3-q1
        out=x[(x.average_cost<q1-1.5*iqr)|(x.average_cost>q3+1.5*iqr)]
        show_table(out[["name","area","average_cost","delivery_rating","delivery_reviews","url"]].sort_values("average_cost",ascending=False).head(50))
        st.caption("Cost outliers use the 1.5×IQR rule.")
    elif mode=="Budget Planner":
        b=st.number_input("Group budget (₹)",100,50000,2000,100); people=st.number_input("People",1,20,4)
        per=b/people; st.metric("Approximate cost per person",f"₹{per:,.0f}")
        st.caption("This compares the listed average cost for two with a simple budget allocation; it is not a bill estimate.")
        show_table(filtered[filtered.average_cost<=b].sort_values(["delivery_rating","average_cost"],ascending=[False,True]).head(15)[["name","area","average_cost","delivery_rating","url"]])
    elif mode=="SQL Playground":
        sql=st.text_area("Read-only SQL",value="SELECT area, COUNT(*) AS restaurants FROM restaurants GROUP BY area ORDER BY restaurants DESC LIMIT 10")
        if st.button("Run safe SQL"):
            try: show_table(run_query(get_connection(),clean_sql(sql)))
            except (SQLRejected,QueryError) as e: st.error(str(e))
    else:
        st.write("Challenge: Which locality has the most restaurants?")
        if st.button("Reveal data-backed answer"):
            x=locality_stats(df_all).sort_values("restaurants",ascending=False).iloc[0]
            st.success(f"{x.area} has the highest restaurant count in the supplied dataset: {int(x.restaurants):,} listings.")

elif nav=="Reports & Exports":
    st.subheader("Reports & Exports")
    metric_row(filtered)
    ks=kpis(filtered); ls=locality_stats(filtered); cs=cuisine_stats(filtered)
    findings=[]
    if not ls.empty:
        t=ls.sort_values("restaurants",ascending=False).iloc[0]; findings.append(f"{t.area} has the largest restaurant concentration with {int(t.restaurants):,} listings.")
    if not cs.empty:
        t=cs.sort_values("restaurants",ascending=False).iloc[0]; findings.append(f"{t.cuisine} is the most represented cuisine association with {int(t.restaurants):,} restaurant-cuisine entries.")
    findings.append(f"Average listed cost is ₹{ks['avg_cost']:,.0f}; median is ₹{ks['median_cost']:,.0f}.")
    limitations=["The source is a restaurant listing dataset and may not represent every Bengaluru restaurant.","Listed cost and ratings are descriptive fields; they do not establish causation.","No geographic coordinates are fabricated; locality analysis is used instead of a map."]
    pdf=business_pdf("Bengaluru Bites — Business Report",ks,findings,limitations)
    st.download_button("Download executive PDF",pdf,"bengaluru_bites_business_report.pdf","application/pdf")
    st.download_button("Download filtered CSV",dataframe_csv(filtered),"bengaluru_bites_filtered.csv","text/csv")
    st.markdown("### Report contents")
    st.write("Executive KPIs, key findings, methodology context and honest dataset limitations.")

elif nav=="My Space":
    st.subheader("My Space")
    con=user_connect()
    st.markdown("#### Favorites")
    fav=favorites(con)
    if fav: show_table(pd.DataFrame(fav,columns=["Restaurant","Source","Saved at"]))
    else: st.info("No favorites saved yet. Use the explorer's source records and save through this workspace in a future session.")
    st.markdown("#### Recent AI/search history")
    hist=searches(con)
    show_table(pd.DataFrame(hist,columns=["Query","Time"]) if hist else pd.DataFrame({"Query":[],"Time":[]}))
    st.markdown("#### Saved comparisons")
    comp=comparisons(con)
    show_table(pd.DataFrame(comp,columns=["Restaurants","Time"]) if comp else pd.DataFrame({"Restaurants":[],"Time":[]}))
    st.caption("Local persistence is supported when the app can write its SQLite preference file. Streamlit Community Cloud storage is ephemeral, so persistent user accounts would require an external database.")

elif nav=="About":
    st.subheader("About Bengaluru Bites")
    st.write("A student portfolio project demonstrating practical data analytics, SQL, Python, visualization, data-quality analysis, recommendation logic and responsible AI integration using a real Bengaluru restaurant listing dataset.")
    st.markdown("### Methodology")
    st.write("The source CSV is preserved. The loader standardizes fields such as ratings and locality names for analysis. Cuisine analysis expands comma-separated cuisine associations. AI questions are converted to a single read-only SQLite query and executed against the same loaded data.")
    st.markdown("### Architecture")
    st.code("Streamlit UI → analytics/recommendation layer → Pandas + SQLite → optional Gemini NL-to-SQL\nSource CSV → loader → validated analytical DataFrame\nUser preferences → separate local SQLite store")
    st.markdown("### Limitations")
    st.write("The dataset contains listing attributes, not live availability or real-time reviews. Geographic coordinates are not present, so no map coordinates are invented. Gemini requires a valid API key. Local user persistence on Streamlit Cloud is not guaranteed.")
    st.markdown("### Recruiter demo")
    st.write("Start with Overview KPIs, filter a locality, show Cuisine/Location benchmarking, demonstrate the transparent value score, run one safe AI question and open the SQL preview, then finish with Data Quality and the PDF report.")
