from fastapi import Request, HTTPException, status

def require_login(request: Request):
    if "user" not in request.session:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, detail="Login required")