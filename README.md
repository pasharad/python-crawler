# python-crawler

A small news crawler that scrapes space-related news sites, stores raw articles in SQLite, filters articles using editable match rules, summarizes and translates matched articles, and exposes a small admin web UI to manage rules and view stats.

## Features
- Crawl configured websites and extract articles.
- Store raw articles in SQLite (`data/news.db`).
- Match articles against editable rules (stored in `match_rules` table).
- Summarize and translate matched articles.
- Admin web UI (FastAPI) to manage rules and view stats.
- Sender thread to post cleaned articles to external service.

## Quickstart (development)
1. Create virtualenv and install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
2. Initialize the database (optional — main.py calls this automatically):
```bash
python -c "from db.database import create_tables; create_tables()"
```
3. Run the crawler and web UI:
```bash
python main.py
# or run only the web admin:
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
Open the web UI at http://localhost:8000/ (login required — see auth.py).

## Managing match rules

- Rules are stored in the match_rules table and control which articles are processed.
- Manage rules via the admin UI or API.
- Programmatic DB API:
-- db.database.rules_all() — list rules
-- db.database.rules_create(...) — create rule
-- db.database.rules_update(...) — update rule
-- db.database.rules_delete(id) — delete rule

## API (admin)
- GET /api/stats — stats and tag breakdown
- GET /api/rules — list rules
- POST /api/rules — create rule
- POST /api/rules/{id} — update rule
- DELETE /api/rules/{id} — delete rule
- GET /api/articles_trend — recent articles trend

## Notes & tips
- Change admin credentials in auth.py before production.
- DB path is news.db (set in database.py).
- Add/modify matching rules at runtime via UI or API — parser uses DB rules for filtering and tagging.
- For development, run the FastAPI app with uvicorn to get hot reload.
