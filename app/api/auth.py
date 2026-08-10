from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.auth.sessions import SESSION_USER_KEY, get_current_user, require_authenticated_user
from app.auth.security import normalize_email
from app.db.database import get_db
from app.db.models import UserRole
from app.db.repositories import authenticate_user, create_user, get_user_by_email


router = APIRouter(tags=["auth"])


@router.get("/register")
def register_form() -> dict[str, str]:
    return {"detail": "Submit email and password to register."}


@router.post("/register")
def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    normalized_email = normalize_email(email)
    if get_user_by_email(db, normalized_email) is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = create_user(db, normalized_email, password, role=UserRole.USER)
    request.session[SESSION_USER_KEY] = user.id
    return {"message": "registered", "user_id": user.id, "email": user.email, "role": user.role.value}


@router.get("/login")
def login_form() -> dict[str, str]:
    return {"detail": "Submit email and password to login."}


@router.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> dict[str, str | int]:
    user = authenticate_user(db, email, password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    request.session[SESSION_USER_KEY] = user.id
    return {"message": "logged_in", "user_id": user.id, "email": user.email, "role": user.role.value}


@router.post("/logout")
def logout(request: Request) -> dict[str, str]:
    request.session.pop(SESSION_USER_KEY, None)
    return {"message": "logged_out"}


@router.get("/profile")
def profile(current_user=Depends(require_authenticated_user)) -> dict[str, str | int]:
    return {"id": current_user.id, "email": current_user.email, "role": current_user.role.value}