"""NOWPayments checkout + IPN webhook for one-time credit-pack purchases.

NOWPayments (https://nowpayments.io) is a non-custodial crypto payment
processor, used here because mainstream card processors (Stripe, Tap, Areeba,
MyFatoorah, Lemon Squeezy) all refuse or heavily restrict merchants
registered in Lebanon - crypto payments route around that banking
restriction entirely, since settlement is a wallet-to-wallet transfer rather
than a bank rail. See NOWPayments API docs: https://documenter.getpostman.com/view/7907941/S1a32n38
"""

import hashlib
import hmac
import json
import os

import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from . import db
from .auth import get_current_user

router = APIRouter(prefix="/api", tags=["billing"])

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
NOWPAYMENTS_API_BASE = "https://api.nowpayments.io/v1"

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


def _get_api_key() -> str:
    key = os.environ.get("NOWPAYMENTS_API_KEY")
    if not key:
        raise HTTPException(500, "NOWPayments is not configured (NOWPAYMENTS_API_KEY missing).")
    return key


def _get_ipn_secret() -> str:
    secret = os.environ.get("NOWPAYMENTS_IPN_SECRET")
    if not secret:
        raise HTTPException(500, "NOWPayments is not configured (NOWPAYMENTS_IPN_SECRET missing).")
    return secret


@router.post("/checkout")
def create_checkout(req: CheckoutRequest, user: dict = Depends(get_current_user)) -> CheckoutResponse:
    pack = CREDIT_PACKS.get(req.pack)
    if not pack:
        raise HTTPException(400, "pack must be 'small', 'medium', 'large', or 'golden'.")

    api_key = _get_api_key()

    # user_id/pack are re-derived from order_id in the webhook instead of a
    # dedicated metadata field - NOWPayments' invoice endpoint has no
    # arbitrary metadata dict (unlike Tap's), so order_id doubles as it.
    payload = {
        "price_amount": round(pack["amount_cents"] / 100, 2),
        "price_currency": "usd",
        "order_id": f"user-{user['id']}-{req.pack}",
        "order_description": f"Fantasy Coach - {pack['label']}",
        "ipn_callback_url": f"{BASE_URL}/api/webhook/nowpayments",
        "success_url": f"{BASE_URL}/?checkout=success",
        "cancel_url": f"{BASE_URL}/?checkout=cancel",
    }

    try:
        resp = requests.post(
            f"{NOWPAYMENTS_API_BASE}/invoice",
            json=payload,
            headers={"x-api-key": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach NOWPayments: {e}")

    if resp.status_code >= 400:
        raise HTTPException(502, f"NOWPayments error: {resp.text}")

    invoice_url = resp.json().get("invoice_url")
    if not invoice_url:
        raise HTTPException(502, "NOWPayments did not return an invoice URL.")
    return CheckoutResponse(url=invoice_url)


def _nowpayments_signature(body: dict, ipn_secret: str) -> str:
    """Reproduces NOWPayments' IPN signature: top-level keys sorted
    alphabetically, compact (no-whitespace) JSON, HMAC-SHA512 with the IPN
    secret - matching the reference PHP/Node examples in their docs."""
    sorted_body = dict(sorted(body.items()))
    payload_str = json.dumps(sorted_body, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(ipn_secret.encode(), payload_str.encode(), hashlib.sha512).hexdigest()


@router.post("/webhook/nowpayments", status_code=200)
async def nowpayments_webhook(request: Request) -> dict:
    body = await request.json()
    signature = request.headers.get("x-nowpayments-sig", "")
    ipn_secret = _get_ipn_secret()

    expected = _nowpayments_signature(body, ipn_secret)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(400, "Invalid webhook signature.")

    if body.get("payment_status") == "finished":
        order_id = body.get("order_id") or ""
        parts = order_id.split("-", 2)
        if len(parts) == 3 and parts[0] == "user":
            try:
                user_id = int(parts[1])
            except ValueError:
                user_id = 0
            pack = CREDIT_PACKS.get(parts[2])
            payment_id = body.get("payment_id")
            if user_id and pack and payment_id:
                # record_purchase is the dedup gate (UNIQUE on provider_reference):
                # only credit if this exact payment hasn't been recorded before,
                # so a replayed/retried webhook delivery can't double-credit.
                is_new_payment = db.record_purchase(
                    user_id, pack["credits"], pack["amount_cents"], provider_reference=str(payment_id)
                )
                if is_new_payment:
                    db.add_credits(user_id, pack["credits"])
                    golden_days = pack.get("golden_days", 0)
                    if golden_days:
                        db.extend_golden(user_id, golden_days)

    return {"received": True}
