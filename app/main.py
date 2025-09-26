from datetime import datetime, timedelta
import json
import os
import sqlite3
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from db.database import get_counts_and_tags_breakdown, rules_all, rules_create, rules_delete, rules_update, types_all, types_create, types_delete, types_update, get_cleaned_articles_by_date, set_type, set_personal_opinion
from app.auth import router as auth_router, is_logged_in

SECRET_KEY = os.getenv("APP_SECRET", "change-me-please")

app = FastAPI(title="Crawler Panel")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, same_site="strict", https_only=False)

# static & templates
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.state.templates = templates



# auth routes
app.include_router(auth_router, tags=["auth"])

# pages
@app.get("/")
def dashboard(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "Dashboard"})

@app.get("/types")
def types_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    return templates.TemplateResponse("types.html", {"request": request, "title": "Types"})

@app.get("/search")
def search_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    return templates.TemplateResponse("search_articles.html", {"request": request, "title": "Search Articles"})
# APIs

@app.get("/api/types")
def types_page(request: Request):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    all_types = types_all()
    types = [{"id": r[0], "type_name": r[1]} for r in all_types]
    return types

@app.post("/api/types")
def types_create_page(request: Request, type_name: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    tid = types_create(type_name)
    return {"id": tid}

@app.post("/api/types/{type_id}")
def types_update_page(request: Request, type_id: int, type_name: str = Form(...)):
    if not is_logged_in(request):
        return RedirectResponse(url="/login", status_code=401)
    types_update(type_id, type_name)
    return {"ok": True}

@app.delete("/api/types/{type_id}")
def types_delete_page(request: Request, type_id: int):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    types_delete(type_id)
    return {"ok": True}

@app.get("/api/stats")
def api_stats(request: Request):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    total_raw, total_cleaned, breakdown = get_counts_and_tags_breakdown()

    # percent per tag w.r.t total_cleaned (avoid division by zero)
    stats = []
    for item in breakdown:
        percent = (item["count"] / total_cleaned * 100) if total_cleaned else 0
        stats.append({
            "tag": item["tag"],
            "count": item["count"],
            "percent": round(percent, 2)
        })
    return {
        "total_raw": total_raw,
        "total_cleaned": total_cleaned,
        "pie": {
            "cleaned": total_cleaned,
            "uncleaned": max(total_raw - total_cleaned, 0)
        },
        "tags": stats
    }
@app.get("/api/rules")
def api_rules(request: Request):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    rows = rules_all()
    return [{"id": r[0], "pattern": r[1], "tag": r[2], "enabled": bool(r[3])} for r in rows]

@app.post("/api/rules")
def api_rules_create(request: Request, pattern: str = Form(...), tag: str = Form(...), enabled: bool = Form(True)):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    rid = rules_create(pattern, tag, enabled)
    return {"id": rid}

@app.post("/api/rules/{rule_id}")
def api_rules_update(request: Request, rule_id: int, pattern: str = Form(...), tag: str = Form(...), enabled: bool = Form(True)):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    rules_update(rule_id, pattern, tag, enabled)
    return {"ok": True}

@app.delete("/api/rules/{rule_id}")
def api_rules_delete(request: Request, rule_id: int):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    rules_delete(rule_id)
    return {"ok": True}

@app.get("/api/articles_trend")
def api_articles_trend(request: Request):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    conn = sqlite3.connect("data/news.db")
    c = conn.cursor()

    today = datetime.now().date()
    start_date = today - timedelta(days=9)

    c.execute("""
        SELECT strftime('%Y-%m-%d', created_at) as day, COUNT(*)
        FROM articles_cleaned
        WHERE DATE(created_at) >= DATE(?)
        GROUP BY day
        ORDER BY day ASC
    """, (start_date.isoformat(),))

    rows = c.fetchall()
    conn.close()
    # تبدیل به dict
    trend = {row[0]: row[1] for row in rows}
    
    # پر کردن تاریخ‌هایی که خالی هستند با صفر
    data = []
    for i in range(10):
        day = (start_date + timedelta(days=i)).isoformat()
        data.append({
            "date": day,
            "count": trend.get(day, 0)
        })

    return {"trend": data}

@app.get("/api/search_articles/{date}")
def api_search_articles(request: Request, date):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

    results = [{"id": r[0], "title": r[1], "url": r[2], "date": r[3], "description": r[4], "summery": r[5], "second_summery" : r[6], "personal_opinion" : r[7], "translated_text": r[8], "second_translated_text" : r[9], "source": r[10], "tags": r[11], "type_id": r[12]} for r in get_cleaned_articles_by_date(date) if r[11]]
    return results

@app.post("/api/articles/set_type/{article_id}")
async def api_articles_set_types(request: Request, article_id: int):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    type_id = await request.json()
    type_id = int(type_id["type_id"]) if type_id["type_id"] else None
    set_type(article_id, type_id)

@app.post("/api/articles/set_personal_summary/{article_id}")
async def api_personal_summary(request: Request, article_id: int):
    if not is_logged_in(request):
        return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    data = await request.json()
    personal_summary = data.get("personal_summary")
    if personal_summary == '':
        personal_summary = None
    set_personal_opinion(article_id, personal_summary)
    return {"ok": True}