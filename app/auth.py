from fastapi import APIRouter, Request, Form, Depends, HTTPException
from fastapi.responses import RedirectResponse
from passlib.hash import bcrypt

router = APIRouter()

# نمونه ساده: کاربر پیش‌فرض
ADMIN_USER = "admin"
# هش ثابت رمز عبور "admin123" با bcrypt (cost=12)
ADMIN_HASH = "admin123"

def set_session_logged_in(request: Request, username: str):
    request.session["user"] = {"username": username}

def clear_session(request: Request):
    request.session.pop("user", None)

def is_logged_in(request: Request):
    return "user" in request.session

@router.get("/login")
def login_page(request: Request):
    templates = request.app.state.templates
    return templates.TemplateResponse("login.html", {"request": request, "title": "Login"})

@router.post("/login")
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    # ساده: فقط یک کاربر
    if username == ADMIN_USER and password == ADMIN_HASH:
        set_session_logged_in(request, username)
        return RedirectResponse(url="/", status_code=303)
    raise HTTPException(status_code=401, detail="Invalid credentials")

@router.get("/logout")
def logout(request: Request):
    clear_session(request)
    return RedirectResponse(url="/login", status_code=303)