"""Whish Pay checkout + callback handling for one-time credit-pack purchases.

Whish Pay (https://whish.money) is a Lebanese payment provider - used here
because mainstream card processors (Stripe, Tap, Areeba, MyFatoorah, Lemon
Squeezy) all refuse or heavily restrict merchants registered in Lebanon,
while Whish is itself Lebanese and accepts a Lebanon-registered merchant
directly. Replaced the earlier NOWPayments crypto integration (requiring a
payer to already hold USDT) now that a mainstream-payment option exists.
API reference: https://whish-partners.pages.dev/whish-pay-9z366gc6922w/
"""

import os
import uuid

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from . import db
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["billing"])

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")

WHISH_SANDBOX_BASE = "https://partner.api.sbx.whish.money/itel-service/api"
WHISH_PRODUCTION_BASE = "https://api.whish.money/itel-service/api"
# Defaults to sandbox so a missing/unset WHISH_ENV can never accidentally
# point real checkout traffic at the production API with sandbox-only
# credentials - set WHISH_ENV=production (and swap WHISH_CHANNEL/WHISH_SECRET
# to the production pair Whish issues separately) only once that pair exists.
WHISH_BASE = WHISH_PRODUCTION_BASE if os.environ.get("WHISH_ENV") == "production" else WHISH_SANDBOX_BASE

CREDIT_PACKS: dict[str, dict] = {
    # Dict keys are the API contract used by /api/checkout and the frontend's
    # goToCheckout(pack) - "label" is just the display name shown at checkout,
    # football-themed, and can change freely without touching the keys.
    "small": {"credits": 5, "amount_cents": 249, "label": "Kick-off - 5 credits"},
    "medium": {"credits": 15, "amount_cents": 629, "label": "Starting XI - 15 credits"},
    "large": {"credits": 40, "amount_cents": 1249, "label": "Captain - 40 credits"},
    # One-time "Golden Boot" pack: 60 credits + 30 days of Golden status,
    # $0.2498/credit - deliberately below Large's $0.3123/credit so it's the
    # best per-credit rate of any pack, not just the biggest. Still clears a
    # positive margin even worst-case (all 60 credits spent on the most
    # expensive action, detailed advice at ~$0.19/credit real API cost, plus
    # Golden's bigger free-tier allowance) against the $14.99 price - see
    # golden_days below.
    "golden": {"credits": 60, "amount_cents": 1499, "label": "Golden Boot - 60 credits + 30 days", "golden_days": 30},
}


class CheckoutRequest(BaseModel):
    pack: str  # "small", "medium", "large", or "golden"


class CheckoutResponse(BaseModel):
    url: str


def _whish_headers() -> dict[str, str]:
    channel = os.environ.get("WHISH_CHANNEL")
    secret = os.environ.get("WHISH_SECRET")
    website_url = os.environ.get("WHISH_WEBSITE_URL")
    if not channel or not secret or not website_url:
        raise HTTPException(500, "Whish Pay is not configured (WHISH_CHANNEL/WHISH_SECRET/WHISH_WEBSITE_URL missing).")
    return {
        "channel": channel,
        "secret": secret,
        "websiteUrl": website_url,
        "Content-Type": "application/json",
        # Required by Whish, identifying the calling app - not their own keys.
        "User-Agent": "FantasyCoach/1.0 (https://fantasycoach.org; sia.delivery.lb@gmail.com)",
    }


RETRYABLE_CODES = {"500", "itel.unknown_error"}


def _post_whish(path: str, payload: dict) -> dict:
    """POSTs to Whish and returns the parsed body, retrying exactly once with
    the identical payload (same externalId included) if the first response's
    code is one of the documented "outcome unknown, not failed" cases - per
    Whish's idempotency docs, resending with an unchanged externalId/body is
    always safe (never runs the payment twice) and recovers the stored
    result once it exists. A second occurrence of the same code means the
    request was genuinely rejected rather than merely slow, so that one is
    left for the caller to treat as a real failure."""
    for attempt in range(2):
        resp = requests.post(f"{WHISH_BASE}{path}", json=payload, headers=_whish_headers(), timeout=15)
        body = resp.json() if resp.content else {}
        if body.get("status") or body.get("code") not in RETRYABLE_CODES or attempt == 1:
            return body
    return body  # unreachable, satisfies type checkers


def _encode_external_id(user_id: int, pack_key: str) -> str:
    """Packs user_id + pack into the externalId itself (mirrors the old
    NOWPayments order_id trick) so the GET callback - which Whish fires with
    no body, only whatever query params we attached at creation time - can be
    decoded without a separate pending-payments table. The random suffix is
    what actually satisfies Whish's "must be unique per payment" requirement;
    pack keys are hyphen-free by construction so the split below is safe."""
    return f"user-{user_id}-{pack_key}-{uuid.uuid4().hex[:10]}"


def _decode_external_id(external_id: str) -> tuple[int, str] | None:
    parts = external_id.split("-", 2)
    if len(parts) != 3 or parts[0] != "user":
        return None
    pack_key = parts[2].rsplit("-", 1)[0]  # drop the trailing random suffix
    try:
        return int(parts[1]), pack_key
    except ValueError:
        return None


@router.post("/checkout")
def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)) -> CheckoutResponse:
    pack = CREDIT_PACKS.get(req.pack)
    if not pack:
        raise HTTPException(400, "pack must be 'small', 'medium', 'large', or 'golden'.")

    external_id = _encode_external_id(user["id"], req.pack)
    payload = {
        "amount": f"{pack['amount_cents'] / 100:.2f}",
        "currency": "USD",
        "invoice": pack["label"],
        "externalId": external_id,
        "successCallbackUrl": f"{BASE_URL}/api/webhook/whish?external_id={external_id}&result=success",
        "failureCallbackUrl": f"{BASE_URL}/api/webhook/whish?external_id={external_id}&result=failure",
        "successRedirectUrl": f"{BASE_URL}/?checkout=success",
        "failureRedirectUrl": f"{BASE_URL}/?checkout=cancel",
    }

    try:
        body = _post_whish("/payment/whish", payload)
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach Whish Pay: {e}")

    # Whish's own success/failure signal is the body's "status" field, not the
    # HTTP status code - a 200 can still carry status: false.
    if not body.get("status"):
        raise HTTPException(502, f"Whish Pay error: {body.get('code')} {body.get('dialog') or ''}".strip())

    collect_url = (body.get("data") or {}).get("collectUrl")
    if not collect_url:
        raise HTTPException(502, "Whish Pay did not return a payment link.")
    return CheckoutResponse(url=collect_url)


def _confirm_and_credit(user_id: int, pack_key: str, external_id: str) -> None:
    pack = CREDIT_PACKS.get(pack_key)
    if not pack:
        return
    try:
        body = _post_whish("/payment/collect/status", {"currency": "USD", "externalId": external_id})
        status = (body.get("data") or {}).get("collectStatus")
    except (requests.RequestException, ValueError):
        return  # best-effort - an unconfirmed payment is simply not credited yet

    if status != "success":
        return  # pending/failed/refunded/unknown - never credit on anything but a confirmed success

    # record_purchase is the dedup gate (UNIQUE on provider_reference): only
    # credit if this externalId hasn't been recorded before, so a duplicate
    # callback delivery (or a callback arriving after we'd already polled and
    # credited it) can't double-credit.
    is_new_payment = db.record_purchase(user_id, pack["credits"], pack["amount_cents"], provider_reference=external_id)
    if is_new_payment:
        db.add_credits(user_id, pack["credits"])
        golden_days = pack.get("golden_days", 0)
        if golden_days:
            db.extend_golden(user_id, golden_days)


@router.get("/webhook/whish")
def whish_callback(external_id: str, result: str, request: Request) -> Response:
    # Whish's callback is just a GET ping with no body and no signature - the
    # docs are explicit that it's a signal, not proof of payment, so a
    # "success" callback still gets confirmed against Get Payment Status
    # before anything is credited. A "failure" callback needs no action at
    # all (nothing was ever credited), but still gets a 200 either way.
    if result == "success":
        decoded = _decode_external_id(external_id)
        if decoded:
            user_id, pack_key = decoded
            _confirm_and_credit(user_id, pack_key, external_id)
    return Response(status_code=200)
