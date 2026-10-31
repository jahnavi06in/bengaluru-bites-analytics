# Bengaluru Bites — Food Intelligence Platform

Bengaluru Bites is a Streamlit portfolio project that turns a real Bengaluru restaurant listing dataset into an interactive analytics and decision-support experience.

It demonstrates practical **Data Analyst skills**: Python/Pandas data preparation, SQL and SQLite, exploratory analysis, KPI design, Plotly visualization, data-quality checks, transparent recommendation logic, CSV/PDF reporting, and responsible Gemini natural-language-to-SQL integration.

> This is a student portfolio project. It uses the supplied dataset as its source of truth and does not claim live restaurant availability or real-time reviews.

## What problem it solves

Restaurant data can answer more than "where should I eat?". Bengaluru Bites lets a user explore restaurant supply, cuisine patterns, locality concentration, price/rating relationships, value signals and data quality — then ask the dataset questions in plain English.

## Features

- Overview business dashboard with dynamic KPIs
- Restaurant Explorer with search, filters, sorting and CSV export
- Cuisine Intelligence with multi-cuisine analysis
- Location Intelligence using locality data (no fabricated coordinates)
- Price & Rating Intelligence, correlation and transparent value scoring
- 2–4 restaurant Comparison Studio
- Rule-based Smart Recommendations with explanations
- Ask AI: Gemini → safe read-only SQLite SQL → real result → optional summary
- SQL preview, validation, retry/correction and result download
- Data Quality Centre with completeness, duplicates and rule-based anomaly checks
- Advanced Data Lab: segmentation, correlations, outliers, budget planner and SQL playground
- PDF executive report and CSV exports
- My Space: local favorites, searches and comparisons
- Methodology, limitations and recruiter demonstration guidance
- ## 🚀 Live Demo

[**Open Bengaluru Bites →**](https://bengaluru-bites-analytics-qhygjwhvwy56vswtup3jhn.streamlit.app/)

## Technology stack

- Python
- Streamlit
- Pandas / NumPy
- SQLite
- Plotly
- Google Gemini API via `google-genai`
- ReportLab
- Pytest-compatible test modules

## Dataset

File: `data/BangaloreZomatoData.csv`

The supplied source contains **8,923 records and 19 columns**. The analytical loader preserves the source file and standardizes selected fields:

- restaurant name
- Zomato URL
- cuisines
- locality
- timing/address/phone in the source
- delivery/takeaway/indoor-seating flags
- dinner and delivery ratings/review counts
- known-for and popular-dish text
- average cost

The SQL layer intentionally exposes a reduced schema and does **not** expose phone numbers or addresses.

### Data handling

- `-` rating values become missing (`NULL`/`NaN`) for analysis.
- Locality is derived from the first part of the source `Area` value.
- Cuisine analysis expands comma-separated cuisine associations. A restaurant with three cuisines contributes once to each of those cuisine categories.
- Popular-dish normalization removes category labels and combines biryani variants.
- The original CSV is never overwritten.

## Project architecture

```text
Source CSV
   |
   v
loader.py  ---> analytical DataFrame
   |                |
   |                +--> analytics.py
   |                +--> recommendations.py
   |                +--> reporting.py
   |
   +--> database.py ---> read-only SQLite
                           ^
                           |
Gemini --> engine.py --> safe SQL
                           |
                           v
                      Streamlit app
                           |
                           +--> persistence.py (separate user-preference store)
```

## Folder structure

```text
bengaluru-bites/
├── app.py
├── loader.py
├── database.py
├── engine.py
├── llm.py
├── analytics.py
├── recommendations.py
├── reporting.py
├── persistence.py
├── requirements.txt
├── README.md
├── data/
│   └── BangaloreZomatoData.csv
├── tests/
│   ├── test_core.py
│   └── test_extended.py
└── .streamlit/
    ├── config.toml
    └── secrets.toml.example
```

## Installation

Use Python 3.11+.

```bash
pip install -r requirements.txt
```

## Run locally

```bash
streamlit run app.py
```

The dashboard and all non-AI analytics work without a Gemini key.

## Gemini setup

Create a local secrets file from the example:

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Then put your own key in the local secrets file:

```toml
GEMINI_API_KEY = "your-key"
```

Optional:

```toml
GEMINI_MODEL = "gemini-flash-latest"
```

Never commit `.streamlit/secrets.toml`.

The application handles missing credentials, rejected keys, rate limits, unavailable models and other Gemini errors without fabricating an answer.

## SQL safety

The natural-language SQL workflow is deliberately constrained:

1. Gemini is instructed to return one read-only query.
2. The SQL is normalized.
3. Comments and markdown fences are removed.
4. Multiple statements are rejected.
5. Non-`SELECT`/`WITH` statements are rejected.
6. Write/DDL operations such as `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER` and `CREATE` are blocked.
7. SQLite's authorizer is locked to read-oriented actions.
8. System-catalog access is rejected.
9. Queries have a progress-handler timeout.
10. Results are capped at 200 rows.
11. One automatic correction attempt is made if a generated query fails.

Example:

```sql
SELECT area, COUNT(*) AS restaurants
FROM restaurants
GROUP BY area
ORDER BY restaurants DESC
LIMIT 10;
```

## Analytical methodology

### Value score

The value score is intentionally transparent rather than pretending to be a machine-learning model:

- 70%: normalized delivery rating
- 30%: inverse cost percentile
- minimum review threshold: 50 by default

It is a portfolio heuristic for comparison, not a universal restaurant-quality score.

### Cuisine analysis

A multi-cuisine restaurant is counted once for every cuisine association. This is useful for cuisine benchmarking but means cuisine totals are not unique-restaurant totals.

### Segmentation

The Data Lab uses simple rule-based segments based on rating and median listed cost. It is explicitly not presented as machine learning.

### Correlation

Cost, rating and review-count correlations are descriptive associations. The application does not claim that cost causes rating changes.

### Data-quality score

The score is a monitoring heuristic based on missingness, blanks, duplicates and selected rule-based invalid-value checks. It is not an industry certification.

## Key data-backed questions

The application can answer questions such as:

- Which locality has the highest restaurant count?
- Which cuisines have the highest average ratings?
- Which restaurants have the strongest value score?
- Which localities have the highest average listed cost?
- Is cost associated with rating?
- Which locality has the greatest cuisine diversity?
- What percentage of restaurants are pure vegetarian?
- Which restaurants have high ratings but relatively few reviews?
- Which restaurants have the highest review counts?
- Which localities offer lower-cost options?
- How do cuisine associations vary by locality?
- Which restaurants fit a specified budget?

## Reports and exports

Available exports include:

- filtered restaurant CSV
- AI/SQL result CSV
- data-quality CSV
- comparison CSV
- executive PDF business report

## Testing

Run the original/core suite:

```bash
python tests/test_core.py
```

Run the extended suite:

```bash
python -m pytest tests
```

The core suite contains 11 original tests. The extended suite adds checks for analytics, recommendations and PDF/CSV reporting.

## Streamlit Community Cloud

1. Push the project to GitHub.
2. Do not commit `.streamlit/secrets.toml`.
3. Create a Streamlit Community Cloud app with `app.py` as the main file.
4. In app settings, add:

```toml
GEMINI_API_KEY = "your-key"
```

5. Deploy.

If Gemini is not configured, the non-AI application remains usable.

## Persistence limitation

`persistence.py` keeps user favorites/searches/comparisons separate from the analytical database. Local execution can retain these records in a small SQLite file. Streamlit Community Cloud storage is not guaranteed to be permanent across redeployments/restarts, so a production multi-user version would require an external persistent database and authentication.

## Honest limitations

- The source is a restaurant listing dataset, not a live restaurant inventory.
- Ratings and review counts are dataset fields, not real-time values.
- No geographic coordinates are present in the source, so the application does not fabricate map points.
- Recommendation logic is transparent and rule-based, not personalized machine learning.
- Gemini is optional and requires a valid user-provided API key.
- User persistence is local/ephemeral unless an external database is added.

## Recruiter demonstration — 3 to 5 minutes

**1. Start with Overview (30–45 sec)**  
Show dynamic KPIs, restaurant concentration, cuisine distribution and rating distribution.

**2. Demonstrate analysis (45–60 sec)**  
Open Location Intelligence and Price & Rating. Explain the locality benchmark, correlation and transparent value score.

**3. Show practical discovery (30–45 sec)**  
Use Restaurant Explorer or Smart Recommendations with a budget and rating constraint.

**4. Demonstrate SQL + AI (60–90 sec)**  
Ask: "Which locality has the most restaurants?"  
Open the SQL preview. Explain that Gemini generates the query but SQLite validation and the read-only authorizer control execution.

**5. Finish with data quality (30–45 sec)**  
Show completeness, duplicates and rule-based issue detection. This is a strong Data Analyst signal because it demonstrates that the project does not blindly trust the source data.

## Credits

Dataset: supplied `BangaloreZomatoData.csv`.

Project: **Bengaluru Bites — Food Intelligence Platform**.

Built as a student Data Analyst portfolio project focused on practical analytics, SQL, Python, visualization, data quality and responsible AI.
