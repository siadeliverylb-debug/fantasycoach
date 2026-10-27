"""Signup/login/logout endpoints and the current-user dependency."""

import sqlite3

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr

from . import db, tools

router = APIRouter(prefix="/api", tags=["auth"])


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    team_id: str | None = None
    ref: str | None = None  # referring user's id, from an invite link


class LinkTeamRequest(BaseModel):
    team_id: str


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
    # Optional: most visitors are on a phone and can't easily find their FPL
    # team ID (the FPL app never shows it), so they can link it after signup
    # via /api/me/team-id instead of being blocked at the door.
    team_id = (req.team_id or "").strip() or None
    if team_id is not None and not team_id.isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    referred_by = int(req.ref) if req.ref and req.ref.strip().isdigit() else None
    try:
        user_id = db.create_user(req.email, req.password, team_id, referred_by=referred_by)
    except sqlite3.IntegrityError as e:
        if "team_id" in str(e):
            raise HTTPException(409, "This FPL team ID is already registered to another account.")
        raise HTTPException(409, "An account with that email already exists.")
    request.session["user_id"] = user_id
    user = db.get_user(user_id)
    if not user["is_admin"]:
        _log_funnel(request, "signup_success", "with team ID" if team_id else "without team ID")
    return _me_response(user)


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


@router.post("/me/team-id")
def link_team(req: LinkTeamRequest, request: Request) -> MeResponse:
    """One-time self-serve link for accounts created without a team ID. Once
    set it's locked like a signup-time ID (still one account per FPL team) -
    changing it afterwards stays an admin-only correction."""
    user = get_current_user(request)
    if user.get("team_id"):
        raise HTTPException(409, "Your account is already linked to an FPL team.")
    team_id = req.team_id.strip()
    if not team_id.isdigit():
        raise HTTPException(400, "Your FPL Team ID is a number - digits only.")
    if "error" in tools.get_team_preview(int(team_id)):
        raise HTTPException(404, "Couldn't find an FPL team with that ID - check the number and try again.")
    try:
        db.set_team_id(user["id"], team_id)
    except ValueError:
        raise HTTPException(409, "This FPL team ID is already registered to another account.")
    if not user.get("is_admin"):
        _log_funnel(request, "team_linked")
    return _me_response(db.get_user(user["id"]))


def _log_funnel(request: Request, event: str, detail: str | None = None) -> None:
    """Server-side funnel step for the admin sign-up stats - keyed by the same
    anonymous visitor_id cookie as page views. Never allowed to break the
    request it's recording."""
    visitor_id = request.cookies.get("visitor_id")
    if not visitor_id:
        return
    try:
        db.log_funnel_event(visitor_id, event, detail)
    except Exception:
        pass


def get_current_user(request: Request) -> dict:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(401, "Not logged in.")
    user = db.get_user(user_id)
    if user is None:
        request.session.clear()
        raise HTTPException(401, "Not logged in.")
    return user
