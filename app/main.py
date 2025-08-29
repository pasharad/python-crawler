from datetime import datetime, timedelta
import os
import sqlite3
from fastapi import FastAPI, Form, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from db.database import get_counts_and_tags_breakdown, rules_all, rules_create, rules_delete, rules_update
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
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse("dashboard.html", {"request": request, "title": "Dashboard"})

# APIs
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