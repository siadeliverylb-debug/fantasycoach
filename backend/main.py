import asyncio
import hashlib
import html
import os
import secrets
import time
import uuid
from pathlib import Path

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware

load_dotenv()

from . import agent, auth, billing, db, tools  # noqa: E402  (must load env before importing agent)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="FPL Assistant")

_secret_key = os.environ.get("SECRET_KEY")
if not _secret_key:
    _secret_key = secrets.token_hex(32)
    print(
        "WARNING: SECRET_KEY not set in .env - using a random one-off key. "
        "Sessions will not survive a server restart. Set SECRET_KEY in .env for real use."
    )
app.add_middleware(SessionMiddleware, secret_key=_secret_key, https_only=True, same_site="lax")

# In-memory, not persisted on purpose - toggled on right before a deploy so an
# in-flight AI/credit-spending request gets a friendly message instead of a
# raw connection error, and it self-clears the moment the new process starts
# (a deploy always replaces this process), so there's nothing to remember to
# turn back off.
_maintenance_mode = False


def _require_not_in_maintenance() -> None:
    if _maintenance_mode:
        raise HTTPException(503, "Fantasy Coach is being updated - please try again in a moment.")

_TRACKED_PAGE_PATHS = {"/", "/pricing"}


def _get_client_ip(request) -> str | None:
    fly_ip = request.headers.get("fly-client-ip")
    if fly_ip:
        return fly_ip
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


def _lookup_country(ip: str | None) -> str | None:
    """Best-effort IP -> country via geojs.io's free, no-key endpoint - never
    raises; a timeout, rate limit, or private/local IP just means no country
    gets recorded for that visit rather than blocking the page load."""
    if not ip:
        return None
    try:
        resp = requests.get(f"https://get.geojs.io/v1/ip/country/{ip}.json", timeout=2)
        if resp.status_code != 200:
            return None
        name = resp.json().get("name")
        return name or None
    except (requests.RequestException, ValueError):
        return None


def _record_visit(visitor_id: str, path: str, ip: str | None, is_new_visitor: bool) -> None:
    country = _lookup_country(ip) if is_new_visitor else db.get_last_country(visitor_id)
    db.log_page_visit(visitor_id, path, country)


@app.middleware("http")
async def _track_page_visit(request, call_next):
    """Anonymous visit counter for the admin visitor-stats page - a random,
    long-lived cookie (separate from the login session) identifies repeat
    visitors. Country is looked up once per new visitor (not stored as a raw
    IP) and remembered for their later visits instead of a fresh API call
    each time. The lookup + DB write run in a background thread so a slow or
    rate-limited geolocation call never delays the page response itself."""
    response = await call_next(request)
    is_admin_session = False
    try:
        user_id = request.session.get("user_id")
        user = db.get_user(user_id) if user_id else None
        is_admin_session = bool(user and user["is_admin"])
    except Exception:
        pass
    if not is_admin_session and request.method == "GET" and request.url.path in _TRACKED_PAGE_PATHS:
        visitor_id = request.cookies.get("visitor_id")
        is_new_visitor = not visitor_id
        if is_new_visitor:
            visitor_id = uuid.uuid4().hex
            response.set_cookie(
                "visitor_id", visitor_id, max_age=365 * 24 * 3600,
                httponly=True, secure=True, samesite="lax",
            )
        ip = _get_client_ip(request)
        asyncio.create_task(asyncio.to_thread(_record_visit, visitor_id, request.url.path, ip, is_new_visitor))
    return response


db.init_db()

# One-off admin account bootstrap/password reset, no self-serve account
# management flow exists yet. Set ADMIN_PASSWORD_RESET="email:newpassword" as
# a secret to trigger it on the next restart (creates the account if it
# doesn't exist, otherwise resets its password), then unset it - remove this
# block once a real account-management flow exists.
_reset_spec = os.environ.get("ADMIN_PASSWORD_RESET")
if _reset_spec and ":" in _reset_spec:
    _reset_email, _reset_password = _reset_spec.split(":", 1)
    if _reset_email.lower().strip() in db.list_all_emails():
        db.reset_password(_reset_email, _reset_password)
    else:
        db.create_user(_reset_email, _reset_password, team_id=None)

app.include_router(auth.router)
app.include_router(billing.router)

FREE_CHAT_MESSAGES_PER_GAMEWEEK = 3
FREE_ADVICE_USES_PER_GAMEWEEK = 1
ADVICE_CREDIT_COST = 2

# Golden members get a bigger free weekly allowance instead of a discount on
# credit-priced actions - cost is capped and predictable (a few extra free
# calls per gameweek, not a bottomless perk), so it can't threaten margin the
# way discounting per-credit-cost actions would.
GOLDEN_FREE_CHAT_MESSAGES_PER_GAMEWEEK = 5
GOLDEN_FREE_ADVICE_USES_PER_GAMEWEEK = 2


def _current_gameweek() -> int:
    next_deadline = tools.get_next_deadline()
    if "error" in next_deadline:
        raise HTTPException(404, next_deadline["error"])
    return next_deadline["id"]


def require_admin(user: dict = Depends(auth.get_current_user)) -> dict:
    if not user.get("is_admin"):
        raise HTTPException(403, "Admin access required.")
    return user


def _require_own_team(user: dict, team_id: str) -> None:
    """Every account is tied to exactly one FPL team at signup (enforced by a
    unique index on users.team_id) - non-admin users may only look up their
    own team, not browse anyone else's by changing the team_id in a request."""
    if user.get("is_admin"):
        return
    if user.get("team_id") != team_id:
        raise HTTPException(403, "You can only look up your own FPL team.")


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    history: list[ChatMessage]
    team_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    is_advice: bool
    credits: int


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, user: dict = Depends(auth.get_current_user)) -> ChatResponse:
    _require_not_in_maintenance()
    if req.team_id is not None:
        _require_own_team(user, req.team_id)

    is_admin = user.get("is_admin")
    gameweek = None
    is_golden = False
    free_chat_limit = free_advice_limit = 0
    chat_used = advice_used = 0
    if not is_admin:
        gameweek = _current_gameweek()
        is_golden = db.user_is_golden(user["id"])
        free_chat_limit = GOLDEN_FREE_CHAT_MESSAGES_PER_GAMEWEEK if is_golden else FREE_CHAT_MESSAGES_PER_GAMEWEEK
        free_advice_limit = GOLDEN_FREE_ADVICE_USES_PER_GAMEWEEK if is_golden else FREE_ADVICE_USES_PER_GAMEWEEK
        chat_used = db.get_chat_count(user["id"], gameweek)
        advice_used = db.get_advice_usage_count(user["id"], gameweek)
        # Gate up front only on "nothing at all left" - which tier this turn
        # actually gets billed at (plain chat vs. advice) isn't known until
        # after the reply comes back, since that depends on whether it gives
        # an explicit buy/sell/captain verdict.
        if chat_used >= free_chat_limit and advice_used >= free_advice_limit and db.get_credits(user["id"]) < 1:
            raise HTTPException(
                402,
                f"You've used this week's free messages (GW{gameweek}). Buy credits above for more.",
            )

    history = [m.model_dump() for m in req.history]
    try:
        reply = agent.chat(history, team_id=req.team_id, user_id=user["id"])
    except Exception:
        # An unhandled error here (Claude API rate limit, timeout, network
        # blip) would otherwise bubble up as a bare 500 with a plain-text body -
        # the frontend's response.json() call then throws its own confusing
        # "Failed to execute 'json' on 'Response'" instead of a real message.
        raise HTTPException(503, "SIA is temporarily unavailable - please try again in a moment.")
    is_advice = agent.reply_has_advice_tag(reply)

    if not is_admin:
        if is_advice:
            if advice_used < free_advice_limit:
                db.increment_advice_usage(user["id"], gameweek)
            else:
                db.spend_credits(user["id"], min(ADVICE_CREDIT_COST, db.get_credits(user["id"])))
        else:
            if chat_used < free_chat_limit:
                db.increment_chat_count(user["id"], gameweek)
            else:
                db.spend_credits(user["id"], min(1, db.get_credits(user["id"])))

    return ChatResponse(reply=reply, is_advice=is_advice, credits=db.get_credits(user["id"]))


@app.get("/api/gameweek")
def gameweek_status() -> dict:
    result = tools.get_next_deadline()
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/team-preview")
def team_preview(team_id: str) -> dict:
    """Public (pre-signup) lookup so a user can confirm the FPL team ID they're
    about to register really is theirs - no auth, since no account exists yet
    at this point in the signup flow."""
    if not team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    result = tools.get_team_preview(int(team_id))
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@app.get("/api/my-squad")
def my_squad(
    team_id: str, gameweek: int | None = None, user: dict = Depends(auth.get_current_user)
) -> dict:
    if not team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    _require_own_team(user, team_id)

    result = tools.get_user_team(int(team_id), gameweek)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


class DraftPick(BaseModel):
    element: int
    multiplier: int
    is_captain: bool
    is_vice_captain: bool


class DraftSaveRequest(BaseModel):
    team_id: str
    gameweek: int
    picks: list[DraftPick]
    bank_m: float


@app.get("/api/draft")
def get_draft(team_id: str, user: dict = Depends(auth.get_current_user)) -> dict:
    if not team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    _require_own_team(user, team_id)

    gameweek = _current_gameweek()
    # Derived fresh from the manager's actual transfer history each time (not
    # stored with the draft) - it reflects real play up to now, regardless of
    # what's been edited into this particular draft.
    free_transfers = tools.get_free_transfers(int(team_id))
    saved = db.get_draft(user["id"])
    # A draft saved for an earlier gameweek is stale once that gameweek has
    # moved on (real transfers may have happened on the official site since) -
    # only trust it as "the plan" if it's still for the current next gameweek.
    if saved and saved["team_id"] == team_id and saved["gameweek"] == gameweek:
        squad, _ = tools.resolve_picks(saved["picks"])
        return {
            "team_id": saved["team_id"],
            "gameweek": saved["gameweek"],
            "total_budget_m": saved["total_budget_m"],
            "bank_m": saved["bank_m"],
            "squad": squad,
            "saved": True,
            "chips": tools.get_chip_status(int(team_id)),
            "free_transfers": free_transfers,
        }

    # No saved draft yet (or it's for a different team, or stale for an earlier
    # gameweek) - start from the live squad, but the draft is "for" the next
    # upcoming gameweek, not the last locked one - this must match
    # _current_gameweek() so free-advice usage shares one pool.
    live = tools.get_user_team(int(team_id), fixture_gameweek=gameweek)
    if "error" in live:
        raise HTTPException(404, live["error"])
    # Strip last gameweek's live points - they're from a match already played,
    # not relevant to a squad that's carried forward unchanged as next week's plan.
    squad = [
        {k: v for k, v in p.items() if k not in ("gw_points", "gw_points_scored", "gw_points_breakdown")}
        for p in live["squad"]
    ]
    return {
        "team_id": team_id,
        "gameweek": gameweek,
        "total_budget_m": live["total_budget_m"],
        "bank_m": live["bank_m"],
        "squad": squad,
        "saved": False,
        "chips": live["chips"],
        "free_transfers": free_transfers,
    }


@app.post("/api/draft")
def save_draft(req: DraftSaveRequest, user: dict = Depends(auth.get_current_user)) -> dict:
    if not req.team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    _require_own_team(user, req.team_id)
    if len(req.picks) != 15:
        raise HTTPException(400, "A draft must have exactly 15 picks.")

    starters = [p for p in req.picks if p.multiplier >= 1]
    bench = [p for p in req.picks if p.multiplier == 0]
    if len(starters) != 11 or len(bench) != 4:
        raise HTTPException(400, "Must have exactly 11 starters and 4 bench players.")
    if sum(p.is_captain for p in starters) != 1 or sum(p.is_vice_captain for p in starters) != 1:
        raise HTTPException(400, "Exactly one captain and one vice-captain are required among starters.")

    existing = db.get_draft(user["id"])
    if existing and existing["team_id"] == req.team_id:
        total_budget_m = existing["total_budget_m"]
    else:
        live = tools.get_user_team(int(req.team_id))
        if "error" in live:
            raise HTTPException(404, live["error"])
        total_budget_m = live["total_budget_m"]

    picks_raw = [p.model_dump() for p in req.picks]
    squad, squad_value_now = tools.resolve_picks(picks_raw)
    if len(squad) != 15:
        raise HTTPException(400, "One or more player IDs were not recognized.")

    starting_outfield = [p for p in squad if p["multiplier"] >= 1 and p["position"] != "GKP"]
    def_count = sum(1 for p in starting_outfield if p["position"] == "DEF")
    mid_count = sum(1 for p in starting_outfield if p["position"] == "MID")
    fwd_count = sum(1 for p in starting_outfield if p["position"] == "FWD")
    if not (3 <= def_count <= 5 and 2 <= mid_count <= 5 and 1 <= fwd_count <= 3):
        raise HTTPException(
            400,
            f"Invalid formation ({def_count} DEF / {mid_count} MID / {fwd_count} FWD). "
            "Valid range is 3-5 DEF, 2-5 MID, 1-3 FWD.",
        )

    squad_value_m = squad_value_now / 10
    total = round(squad_value_m + req.bank_m, 1)
    if total > total_budget_m + 0.05:
        raise HTTPException(
            400, f"Over budget: squad (£{squad_value_m}m) + bank (£{req.bank_m}m) exceeds your £{total_budget_m}m limit."
        )

    db.save_draft(
        user["id"], req.team_id, req.gameweek, total_budget_m,
        {"picks": picks_raw, "bank_m": req.bank_m},
    )
    return {"saved": True, "squad_value_m": squad_value_m, "bank_m": req.bank_m, "total_budget_m": total_budget_m}


@app.get("/api/players/search")
def search_players_endpoint(
    q: str, position: str | None = None, user: dict = Depends(auth.get_current_user)
) -> dict:
    result = tools.search_players(q, limit=15)
    players = result.get("players", [])
    if position:
        players = [p for p in players if p["position"] == position]
    return {"players": players[:8]}


class DraftAdviceRequest(BaseModel):
    team_id: str
    gameweek: int
    picks: list[DraftPick]
    bank_m: float


class DraftAdviceResponse(BaseModel):
    summary: str
    proposed_squad: list[dict]
    changes_count: int
    credits: int


def _draft_summary(squad: list[dict], bank_m: float) -> str:
    starters = [p for p in squad if p["multiplier"] >= 1]
    bench = [p for p in squad if p["multiplier"] == 0]
    lines = ["Starting XI:"]
    for p in starters:
        tag = " (C)" if p["is_captain"] else " (VC)" if p["is_vice_captain"] else ""
        lines.append(f"- {p['name']} ({p['position']}, {p['team_short']}) £{p['price_m']}m{tag}")
    lines.append("Bench:")
    for p in bench:
        lines.append(f"- {p['name']} ({p['position']}, {p['team_short']}) £{p['price_m']}m")
    lines.append(f"Bank: £{bank_m}m")
    return "\n".join(lines)


def _find_in_squad(squad: list[dict], name: str) -> dict | None:
    name_l = (name or "").lower().strip()
    if not name_l:
        return None
    for p in squad:
        if name_l in p["name"].lower() or p["name"].lower() in name_l:
            return p
    return None


@app.post("/api/draft/advice", response_model=DraftAdviceResponse)
def draft_advice(req: DraftAdviceRequest, user: dict = Depends(auth.get_current_user)) -> DraftAdviceResponse:
    _require_not_in_maintenance()
    if not req.team_id.strip().isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    _require_own_team(user, req.team_id)

    gameweek = req.gameweek
    is_admin = user.get("is_admin")
    if not is_admin:
        # Draft review always costs credits - it doesn't share the free weekly
        # allowance that chat-delivered advice verdicts get (see /api/chat).
        if db.get_credits(user["id"]) < ADVICE_CREDIT_COST:
            raise HTTPException(
                402,
                f"Draft review costs {ADVICE_CREDIT_COST} credits - buy more above.",
            )
        db.spend_credits(user["id"], ADVICE_CREDIT_COST)

    picks_raw = [p.model_dump() for p in req.picks]
    squad, _ = tools.resolve_picks(picks_raw)
    summary_text = _draft_summary(squad, req.bank_m)
    try:
        result = agent.get_draft_advice_structured(req.team_id, gameweek, summary_text, user_id=user["id"])
    except Exception:
        # Same rationale as /api/chat's try/except - and refund the credits
        # already spent above, since the user got nothing for them.
        if not is_admin:
            db.add_credits(user["id"], ADVICE_CREDIT_COST)
        raise HTTPException(503, "SIA is temporarily unavailable - please try again in a moment.")

    proposed = [dict(p) for p in squad]
    changes_count = 0
    for change in result.get("changes", []):
        target = _find_in_squad(proposed, change.get("out_web_name", ""))
        if not target:
            continue
        candidates = tools.search_players(change.get("in_web_name", ""), limit=1).get("players", [])
        if not candidates or candidates[0]["position"] != target["position"]:
            continue
        new_player = candidates[0]
        idx = next(i for i, p in enumerate(proposed) if p["element"] == target["element"])
        proposed[idx] = {
            **target,
            "element": new_player["id"],
            "name": new_player["web_name"],
            "team_short": new_player.get("team_short"),
            "team_code": new_player.get("team_code"),
            "price_m": new_player["price_m"],
            "price_change_m": 0,
            "status": new_player.get("status"),
            "chance_of_playing_next_round": new_player.get("chance_of_playing_next_round"),
            "news": new_player.get("news"),
            "next_fixture": None,
            "swapped": True,
        }
        changes_count += 1

    cap = _find_in_squad(proposed, result.get("captain_web_name", ""))
    cap_element = cap["element"] if cap else None
    vice = _find_in_squad(proposed, result.get("vice_web_name", ""))
    vice_element = vice["element"] if vice else None
    for p in proposed:
        if p["multiplier"] >= 1:
            p["is_captain"] = p["element"] == cap_element
            p["is_vice_captain"] = p["element"] == vice_element
        else:
            p["is_captain"] = False
            p["is_vice_captain"] = False

    return DraftAdviceResponse(
        summary=result.get("summary", ""),
        proposed_squad=proposed,
        changes_count=changes_count,
        credits=db.get_credits(user["id"]),
    )


class AdminUserUsage(BaseModel):
    id: int
    email: str
    created_at: str
    is_admin: bool
    team_id: str | None
    team_name: str | None
    manager_name: str | None
    free_transfers: int | None
    is_golden: bool
    golden_until: str | None
    credits: int
    lifetime_credits_spent: int
    credits_purchased: int
    input_tokens: int
    output_tokens: int
    call_count: int
    api_cost_usd: float
    revenue_usd: float
    credit_value_usd: float


# Rough blended $/credit across the three packs - only used to put a dollar figure
# on credits redeemed that were never actually paid for (signup/referral bonuses),
# for comparison against real API cost. Actual income uses real NOWPayments amounts
# (db.record_purchase), not this estimate.
_CREDIT_USD_RATE = sum(p["amount_cents"] / 100 / p["credits"] for p in billing.CREDIT_PACKS.values()) / len(
    billing.CREDIT_PACKS
)


@app.get("/api/admin/usage")
def admin_usage(admin: dict = Depends(require_admin)) -> list[AdminUserUsage]:
    rows = db.get_usage_summary()
    out = []
    for r in rows:
        api_cost = (
            r["input_tokens"] / 1_000_000 * agent.INPUT_PRICE_PER_MTOK
            + r["output_tokens"] / 1_000_000 * agent.OUTPUT_PRICE_PER_MTOK
        )
        team_name = manager_name = None
        free_transfers = None
        if r["team_id"]:
            preview = tools.get_team_preview(int(r["team_id"]))
            team_name = preview.get("team_name")
            manager_name = preview.get("manager_name")
            free_transfers = tools.get_free_transfers(int(r["team_id"]))
        out.append(
            AdminUserUsage(
                **{k: r[k] for k in ("id", "email", "created_at", "is_admin", "team_id", "is_golden",
                                      "golden_until", "credits", "lifetime_credits_spent", "credits_purchased",
                                      "input_tokens", "output_tokens", "call_count")},
                team_name=team_name,
                manager_name=manager_name,
                free_transfers=free_transfers,
                api_cost_usd=round(api_cost, 4),
                revenue_usd=round(r["revenue_cents"] / 100, 4),
                credit_value_usd=round(r["lifetime_credits_spent"] * _CREDIT_USD_RATE, 4),
            )
        )
    return out


@app.get("/api/admin/visitors")
def admin_visitors(days: int = 30, country: str | None = None, admin: dict = Depends(require_admin)) -> dict:
    return db.get_visitor_stats(days=days, country=country)


@app.post("/api/admin/visitors/clear-mine")
def clear_my_visits(request: Request, admin: dict = Depends(require_admin)) -> dict:
    """Wipes the current browser's own visitor_id from the stats - for
    clearing out an admin's own dev/testing traffic. Going forward, an admin
    session's page views aren't logged at all (see _track_page_visit), so
    this is only needed once to clean up whatever was already recorded."""
    visitor_id = request.cookies.get("visitor_id")
    if not visitor_id:
        return {"deleted": 0}
    return {"deleted": db.delete_visits_for_visitor(visitor_id)}


class MaintenanceModeRequest(BaseModel):
    enabled: bool


@app.get("/api/admin/maintenance")
def get_maintenance_mode(admin: dict = Depends(require_admin)) -> dict:
    return {"enabled": _maintenance_mode}


@app.post("/api/admin/maintenance")
def set_maintenance_mode(req: MaintenanceModeRequest, admin: dict = Depends(require_admin)) -> dict:
    global _maintenance_mode
    _maintenance_mode = req.enabled
    return {"enabled": _maintenance_mode}


class AdminSetCreditsRequest(BaseModel):
    user_id: int
    credits: int


@app.post("/api/admin/credits")
def admin_set_credits(req: AdminSetCreditsRequest, admin: dict = Depends(require_admin)) -> dict:
    if req.credits < 0:
        raise HTTPException(400, "Credits can't be negative.")
    if db.get_user(req.user_id) is None:
        raise HTTPException(404, "No such user.")
    db.set_credits(req.user_id, req.credits)
    return db.get_user_row(req.user_id)


class AdminSetTeamIdRequest(BaseModel):
    user_id: int
    team_id: str | None = None


@app.post("/api/admin/team-id")
def admin_set_team_id(req: AdminSetTeamIdRequest, admin: dict = Depends(require_admin)) -> dict:
    team_id = req.team_id.strip() if req.team_id else None
    if team_id is not None and not team_id.isdigit():
        raise HTTPException(400, "team_id must be numeric.")
    if db.get_user(req.user_id) is None:
        raise HTTPException(404, "No such user.")
    try:
        db.set_team_id(req.user_id, team_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return db.get_user(req.user_id)


class CreatePromoCodeRequest(BaseModel):
    credits: int


@app.post("/api/admin/promo-codes")
def admin_create_promo_code(req: CreatePromoCodeRequest, admin: dict = Depends(require_admin)) -> dict:
    if req.credits <= 0:
        raise HTTPException(400, "Credits must be positive.")
    code = db.create_promo_code(req.credits, admin["id"])
    return {"code": code, "credits": req.credits}


@app.get("/api/admin/promo-codes")
def admin_list_promo_codes(admin: dict = Depends(require_admin)) -> list[dict]:
    return db.list_promo_codes()


@app.delete("/api/admin/promo-codes/{code}")
def admin_delete_promo_code(code: str, admin: dict = Depends(require_admin)) -> dict:
    if not db.delete_promo_code(code):
        raise HTTPException(404, "No such promo code.")
    return {"deleted": True}


class RedeemPromoCodeRequest(BaseModel):
    code: str


@app.post("/api/redeem-promo")
def redeem_promo_code(req: RedeemPromoCodeRequest, user: dict = Depends(auth.get_current_user)) -> dict:
    try:
        credits = db.redeem_promo_code(req.code, user["id"])
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"credits_added": credits, "credits": db.get_credits(user["id"])}


app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

_asset_version_cache: dict[str, str] = {}


def _asset_version(filename: str) -> str:
    """Short content hash used to cache-bust /static/<filename> references in
    the served HTML, so a deploy's CSS/JS changes take effect for visitors
    immediately instead of waiting on each browser's own cache to expire."""
    cached = _asset_version_cache.get(filename)
    if cached is not None:
        return cached
    digest = hashlib.md5((FRONTEND_DIR / filename).read_bytes()).hexdigest()[:8]
    _asset_version_cache[filename] = digest
    return digest


def _render_page(html_filename: str, *asset_filenames: str) -> HTMLResponse:
    html = (FRONTEND_DIR / html_filename).read_text(encoding="utf-8")
    for asset in asset_filenames:
        html = html.replace(f'/static/{asset}"', f'/static/{asset}?v={_asset_version(asset)}"')
    return HTMLResponse(html)


@app.get("/robots.txt")
def robots_txt() -> PlainTextResponse:
    return PlainTextResponse((FRONTEND_DIR / "robots.txt").read_text(encoding="utf-8"))


@app.get("/sitemap.xml")
def sitemap_xml() -> Response:
    return Response((FRONTEND_DIR / "sitemap.xml").read_text(encoding="utf-8"), media_type="application/xml")


@app.get("/google7b01a54d3d9874e5.html")
def google_site_verification() -> PlainTextResponse:
    # Google Search Console domain-ownership check - must be served at this
    # exact root path with this exact content for verification to pass.
    return PlainTextResponse((FRONTEND_DIR / "google7b01a54d3d9874e5.html").read_text(encoding="utf-8"))


_captain_picks_cache: dict = {"gameweek": None, "generated_at": 0.0, "content": None}
_CAPTAIN_PICKS_CACHE_TTL_SECONDS = 12 * 60 * 60  # regenerate at most twice a day, or on gameweek rollover


def _captain_picks_still_fresh(content: dict) -> bool:
    """False if any picked player has since become doubtful/injured/suspended/
    unavailable - an injury update should knock a pick off the page right
    away rather than wait out the full cache TTL."""
    element_ids = [p["element"] for p in content.get("picks", []) if "element" in p]
    if not element_ids:
        return True
    statuses = tools.get_players_status(element_ids)
    return all(statuses.get(eid) == "a" for eid in element_ids)


def _get_captain_picks_cached(gameweek: int) -> dict:
    now = time.time()
    if (
        _captain_picks_cache["content"] is not None
        and _captain_picks_cache["gameweek"] == gameweek
        and now - _captain_picks_cache["generated_at"] < _CAPTAIN_PICKS_CACHE_TTL_SECONDS
        and _captain_picks_still_fresh(_captain_picks_cache["content"])
    ):
        return _captain_picks_cache["content"]
    content = agent.get_captain_picks_content(gameweek)
    _captain_picks_cache.update(gameweek=gameweek, generated_at=now, content=content)
    return content


@app.get("/captain-picks")
def captain_picks_page() -> HTMLResponse:
    gameweek = _current_gameweek()
    try:
        content = _get_captain_picks_cached(gameweek)
    except Exception:
        # Best-effort public content page - if generation fails, still show a
        # usable page pointing people at the real (logged-in) chat instead of
        # a bare error.
        content = {"intro": "", "picks": []}

    intro = html.escape(content.get("intro") or "")
    picks = content.get("picks") or []

    if picks:
        cards = "\n".join(
            f"""      <div class="captain-pick-card">
        <div class="captain-pick-rank">#{i + 1}</div>
        <div class="captain-pick-body">
          <div class="captain-pick-name">{'<span class="captain-pick-c-badge" title="Top captain pick">C</span> ' if i == 0 else ""}{html.escape(p.get("web_name", ""))}
            <span class="captain-pick-meta">{html.escape(p.get("position", ""))} · {html.escape(p.get("team_short", ""))} · £{p.get("price_m", 0)}m · {html.escape(p.get("opponent", ""))}</span>
          </div>
          <p class="captain-pick-reason">{html.escape(p.get("reason", ""))}</p>
        </div>
      </div>"""
            for i, p in enumerate(picks)
        )
    else:
        cards = '      <p class="captain-picks-empty">Picks for this gameweek are being put together - check back shortly.</p>'

    page_title = f"Gameweek {gameweek} Captain Picks - Fantasy Coach"
    page_description = (
        f"SIA's top 5 FPL captain picks for Gameweek {gameweek}, backed by real stats - "
        "form, fixtures, and price. Free AI-powered Fantasy Premier League advice."
    )
    html_out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(page_description)}" />
  <link rel="canonical" href="https://fantasycoach.org/captain-picks" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="Fantasy Coach" />
  <meta property="og:title" content="{html.escape(page_title)}" />
  <meta property="og:description" content="{html.escape(page_description)}" />
  <meta property="og:url" content="https://fantasycoach.org/captain-picks" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{html.escape(page_title)}" />
  <meta name="twitter:description" content="{html.escape(page_description)}" />
  <link rel="stylesheet" href="/static/style.css?v={_asset_version("style.css")}" />
</head>
<body>
  <div class="pricing-page">
    <a href="/" class="pricing-back-link">← Back to app</a>
    <header class="pricing-header">
      <h1>Gameweek {gameweek} FPL Captain Picks</h1>
      <p class="subtitle">{intro or "SIA's top captain picks for the upcoming gameweek, backed by real stats."}</p>
    </header>

    <div class="captain-picks-list">
{cards}
    </div>

    <p class="content-crosslink"><a href="/differentials">→ This gameweek's differential picks (under 10% owned)</a></p>
    <a href="/" class="pricing-cta">Get personalized advice for your own squad - free →</a>

    <p class="disclaimer pricing-disclaimer">
      Fantasy Coach is an independent tool, not affiliated with or endorsed by the Premier League
      or Fantasy Premier League. All advice is AI-generated from public data and may be wrong or
      out of date. It's informational only, not a guarantee of results - you make your own FPL
      decisions, and this site and its operator accept no responsibility for points, rank, or any
      other outcome from following it.
    </p>
  </div>
</body>
</html>
"""
    return HTMLResponse(html_out)


_differentials_cache: dict = {"gameweek": None, "generated_at": 0.0, "content": None}
_DIFFERENTIALS_CACHE_TTL_SECONDS = 12 * 60 * 60  # regenerate at most twice a day, or on gameweek rollover


def _get_differentials_cached(gameweek: int) -> dict:
    now = time.time()
    if (
        _differentials_cache["content"] is not None
        and _differentials_cache["gameweek"] == gameweek
        and now - _differentials_cache["generated_at"] < _DIFFERENTIALS_CACHE_TTL_SECONDS
        # A low-ownership pick going injured/suspended is exactly the kind of
        # update that should knock it off the page immediately, same
        # reasoning as _captain_picks_still_fresh.
        and _captain_picks_still_fresh(_differentials_cache["content"])
    ):
        return _differentials_cache["content"]
    content = agent.get_differentials_content(gameweek)
    _differentials_cache.update(gameweek=gameweek, generated_at=now, content=content)
    return content


@app.get("/differentials")
def differentials_page() -> HTMLResponse:
    gameweek = _current_gameweek()
    try:
        content = _get_differentials_cached(gameweek)
    except Exception:
        content = {"intro": "", "picks": []}

    intro = html.escape(content.get("intro") or "")
    picks = content.get("picks") or []

    if picks:
        cards = "\n".join(
            f"""      <div class="captain-pick-card">
        <div class="captain-pick-rank">#{i + 1}</div>
        <div class="captain-pick-body">
          <div class="captain-pick-name">{html.escape(p.get("web_name", ""))}
            <span class="captain-pick-meta">{html.escape(p.get("position", ""))} · {html.escape(p.get("team_short", ""))} · £{p.get("price_m", 0)}m · {p.get("ownership_percent", 0)}% owned · {html.escape(p.get("opponent", ""))}</span>
          </div>
          <p class="captain-pick-reason">{html.escape(p.get("reason", ""))}</p>
        </div>
      </div>"""
            for i, p in enumerate(picks)
        )
    else:
        cards = '      <p class="captain-picks-empty">Picks for this gameweek are being put together - check back shortly.</p>'

    page_title = f"Gameweek {gameweek} FPL Differentials - Fantasy Coach"
    page_description = (
        f"SIA's top 5 FPL differential picks for Gameweek {gameweek} - low-ownership players "
        "with strong underlying stats. Free AI-powered Fantasy Premier League advice."
    )
    html_out = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(page_title)}</title>
  <meta name="description" content="{html.escape(page_description)}" />
  <link rel="canonical" href="https://fantasycoach.org/differentials" />
  <meta property="og:type" content="article" />
  <meta property="og:site_name" content="Fantasy Coach" />
  <meta property="og:title" content="{html.escape(page_title)}" />
  <meta property="og:description" content="{html.escape(page_description)}" />
  <meta property="og:url" content="https://fantasycoach.org/differentials" />
  <meta name="twitter:card" content="summary" />
  <meta name="twitter:title" content="{html.escape(page_title)}" />
  <meta name="twitter:description" content="{html.escape(page_description)}" />
  <link rel="stylesheet" href="/static/style.css?v={_asset_version("style.css")}" />
</head>
<body>
  <div class="pricing-page">
    <a href="/" class="pricing-back-link">← Back to app</a>
    <header class="pricing-header">
      <h1>Gameweek {gameweek} FPL Differentials</h1>
      <p class="subtitle">{intro or "SIA's top low-ownership picks for the upcoming gameweek, backed by real stats."}</p>
    </header>

    <div class="captain-picks-list">
{cards}
    </div>

    <p class="content-crosslink"><a href="/captain-picks">→ This gameweek's top captain picks</a></p>
    <a href="/" class="pricing-cta">Get personalized advice for your own squad - free →</a>

    <p class="disclaimer pricing-disclaimer">
      Fantasy Coach is an independent tool, not affiliated with or endorsed by the Premier League
      or Fantasy Premier League. All advice is AI-generated from public data and may be wrong or
      out of date. It's informational only, not a guarantee of results - you make your own FPL
      decisions, and this site and its operator accept no responsibility for points, rank, or any
      other outcome from following it.
    </p>
  </div>
</body>
</html>
"""
    return HTMLResponse(html_out)


@app.get("/")
def index() -> HTMLResponse:
    return _render_page("index.html", "style.css", "app.js")


@app.get("/pricing")
def pricing() -> HTMLResponse:
    return _render_page("pricing.html", "style.css")


@app.get("/admin")
def admin_page() -> HTMLResponse:
    # Not gated here - the page's own fetches to /api/admin/* are the real
    # gate (require_admin, 403 for non-admins); this just serves the shell.
    return _render_page("admin.html", "style.css", "admin.js")


@app.get("/admin/visitors")
def admin_visitors_page() -> HTMLResponse:
    # Same pattern as /admin - gated by the page's own fetch to
    # /api/admin/visitors (require_admin), not here.
    return _render_page("visitors.html", "style.css", "visitors.js")
