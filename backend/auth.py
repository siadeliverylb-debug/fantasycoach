"""Signup/login/logout endpoints and the current-user dependency."""

import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from . import db

router = APIRouter(prefix="/api", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    team_id: str
    ref: str | None = None  # referring user's id, from an invite link


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class MeResponse(BaseModel):
    id: int
    email: str
    credits: int
    is_admin: bool = False
    is_golden: bool = False
    golden_until: str | None = None
    team_id: str | None = None


def _me_response(user: dict) -> MeResponse:
    golden_until = db.get_golden_until(user["id"])
    return MeResponse(
        id=user["id"],
        email=user["email"],
        credits=db.get_credits(user["id"]),
        is_admin=user["is_admin"],
        is_golden=db.is_golden_active(golden_until),
        golden_until=golden_until,
        team_id=user.get("team_id"),
    )


@router.post("/signup", status_code=201)
def signup(req: SignupRequest, request: Request) -> MeResponse:
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")
    if not req.team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    referred_by = int(req.ref) if req.ref and req.ref.strip().isdigit() else None
    try:
        user_id = db.create_user(req.email, req.password, req.team_id.strip(), referred_by=referred_by)
    except sqlite3.IntegrityError as e:
        if "team_id" in str(e):
            raise HTTPException(409, "This FPL team ID is already registered to another account.")
        raise HTTPException(409, "An account with that email already exists.")
    request.session["user_id"] = user_id
    return _me_response(db.get_user(user_id))


@router.post("/login")
def login(req: LoginRequest, request: Request) -> MeResponse:
    user_id = db.verify_login(req.email, req.password)
    if user_id is None:
        raise HTTPException(401, "Invalid email or password.")
    request.session["user_id"] = user_id
    return _me_response(db.get_user(user_id))


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    request.session.clear()


@router.get("/me")
def me(request: Request) -> MeResponse:
    return _me_response(get_current_user(request))


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(401, "Not logged in.")
    user = db.get_user(user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(401, "Not logged in.")
    return user
