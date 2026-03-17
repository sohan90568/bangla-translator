# ============================================================
#  payments.py  —  PortPos (formerly PortWallet) Integration
#
#  WHY PORTPOS:
#  - No trade license required (individual NID is enough)
#  - No subscription / annual fee
#  - Transaction fee only: ~1.5-2.5% per payment
#  - Free sandbox: sandbox.portpos.com (register with email)
#  - Supports: bKash, Nagad, Rocket, DBBL, Visa, Mastercard, Amex, Nexus
#  - Bangladesh Bank licensed
#  - Live registration: manage.portpos.com
#
#  API DOCS:  developer.portpos.com/documentation.php
#
#  EXACT FLOW (from official docs):
#  1. POST to /api/v1/ with call="gen_invoice"
#     token = md5(secret_key + timestamp)
#     Response: { "status": 200, "data": { "invoice_id": "..." } }
#  2. Redirect user to payment-sandbox.portpos.com/payment/?invoice=INVOICE_ID
#  3. User pays (bKash / Card / etc.)
#  4. PortPos redirects to your redirect_url
#  5. POST to /api/v1/ with call="ipn_validate" + invoice + amount
#     Response status 200 = ACCEPTED = paid
#
#  SANDBOX SETUP (free, 2 minutes):
#  1. Go to sandbox.portpos.com → Register
#  2. Log in → API Keys → copy App Key + Secret Key
#  3. Add to .env:
#       PORTPOS_APP_KEY=your_sandbox_app_key
#       PORTPOS_SECRET_KEY=your_sandbox_secret_key
#       PORTPOS_SANDBOX=true
#
#  LIVE SETUP (no trade license needed):
#  1. Go to manage.portpos.com → Register
#  2. Upload NID (front+back) + bank account details
#  3. Get live App Key + Secret Key (1-3 days)
#  4. Set PORTPOS_SANDBOX=false in .env
# ============================================================

import hashlib
import time
import requests
from config import (
    PORTPOS_SANDBOX, PORTPOS_APP_KEY, PORTPOS_SECRET_KEY,
    APP_URL, PLANS
)

# ── Endpoints (from official docs) ───────────────────────────
_SANDBOX_API = "https://api-sandbox.portpos.com/api/v1/"
_LIVE_API    = "https://api.portpos.com/api/v1/"
_SANDBOX_PAY = "https://payment-sandbox.portpos.com/payment/?invoice={}"
_LIVE_PAY    = "https://payment.portpos.com/payment/?invoice={}"

# ── Sandbox test credentials ─────────────────────────────────
SANDBOX_TEST_CREDENTIALS = {
    "Visa test card": {
        "Card number": "4111 1111 1111 1111",
        "Expiry":      "Any future date (e.g. 12/26)",
        "CVV":         "Any 3 digits",
        "Name":        "Any name",
    },
    "DBBL Nexus test": {
        "Card":   "5200 0000 0000 0007",
        "Expiry": "12/26",
        "CVV":    "123",
    },
    "bKash / Nagad": {
        "Note":  "Select on payment page, follow sandbox flow",
        "Phone": "Use any valid BD number format",
    },
}


def _api_url():
    return _SANDBOX_API if PORTPOS_SANDBOX else _LIVE_API

def _pay_url(invoice_id):
    tpl = _SANDBOX_PAY if PORTPOS_SANDBOX else _LIVE_PAY
    return tpl.format(invoice_id)

def _make_token(timestamp):
    """token = md5(secret_key + timestamp) — exact as PortPos docs specify."""
    raw = f"{PORTPOS_SECRET_KEY}{timestamp}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()

def _headers():
    return {"Content-Type": "application/x-www-form-urlencoded"}


def create_payment(
    user_id, username, plan_key, amount_bdt,
    coupon_code=None, customer_email="",
    customer_name="", customer_phone="01700000000",
):
    """
    Create a PortPos invoice. Returns {success, payment_url, tran_id, error}.
    tran_id == invoice_id from PortPos (stored in DB as tran_id).
    """
    if not PORTPOS_APP_KEY or not PORTPOS_SECRET_KEY:
        return {
            "success": False,
            "error": (
                "PortPos keys not set in .env!\n\n"
                "Get free sandbox keys:\n"
                "  1. Go to sandbox.portpos.com\n"
                "  2. Register with your email\n"
                "  3. Log in → API Keys\n"
                "  4. Add to .env:\n"
                "       PORTPOS_APP_KEY=your_key\n"
                "       PORTPOS_SECRET_KEY=your_secret\n"
                "       PORTPOS_SANDBOX=true"
            ),
        }

    plan      = PLANS.get(plan_key, PLANS["monthly"])
    timestamp = int(time.time())
    token     = _make_token(timestamp)

    # redirect_url carries our data so callback handler knows who paid
    redirect_url = (
        f"{APP_URL}"
        f"?payment=success"
        f"&uid={user_id}"
        f"&plan={plan_key}"
        f"&amount={amount_bdt:.2f}"
    )

    payload = {
        "app_key":             PORTPOS_APP_KEY,
        "timestamp":           str(timestamp),
        "token":               token,
        "call":                "gen_invoice",
        "amount":              f"{amount_bdt:.2f}",
        "currency":            "BDT",
        "product_name":        plan["name"][:150],
        "product_description": f"{plan['desc']} — {APP_URL}"[:300],
        "name":                (customer_name or username)[:50],
        "email":               (customer_email or f"user{user_id}@app.local")[:50],
        "phone":               customer_phone[:15],
        "address":             "Dhaka, Bangladesh"[:200],
        "city":                "Dhaka"[:50],
        "state":               "Dhaka"[:50],
        "zipcode":             "1000",
        "country":             "BD",
        "redirect_url":        redirect_url[:250],
        "ipn_url":             f"{APP_URL}?payment=ipn"[:250],
    }

    try:
        resp = requests.post(_api_url(), data=payload, headers=_headers(), timeout=20)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") == 200:
            invoice_id = data["data"]["invoice_id"]
            return {
                "success":     True,
                "payment_url": _pay_url(invoice_id),
                "tran_id":     invoice_id,
                "invoice_id":  invoice_id,
                "error":       None,
            }
        else:
            msg = data.get("message") or data.get("data") or str(data)
            if isinstance(msg, dict):
                msg = "; ".join(f"{k}: {v}" for k, v in msg.items())
            return {"success": False, "error": f"PortPos error: {msg}"}

    except requests.Timeout:
        return {"success": False, "error": "Payment gateway timed out. Try again."}
    except requests.ConnectionError:
        return {"success": False, "error": "Cannot connect to PortPos. Check internet."}
    except Exception as e:
        return {"success": False, "error": f"Error: {e}"}


def verify_payment(invoice_id, amount):
    """
    Verify a PortPos payment after redirect.
    Returns {success, status, amount, card_type, error}.
    Status 200=ACCEPTED(paid), 300=REJECTED, 100=PENDING.
    """
    if not PORTPOS_APP_KEY or not PORTPOS_SECRET_KEY:
        return {"success": False, "status": "CONFIG_ERROR", "error": "PortPos keys missing"}

    timestamp = int(time.time())
    token     = _make_token(timestamp)

    payload = {
        "app_key":   PORTPOS_APP_KEY,
        "timestamp": str(timestamp),
        "token":     token,
        "call":      "ipn_validate",
        "invoice":   invoice_id,
        "amount":    f"{float(amount):.2f}",
    }

    try:
        resp = requests.post(_api_url(), data=payload, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data    = resp.json()
        code    = data.get("status")
        tx      = data.get("data", {})
        tx_stat = tx.get("status", "")

        if code == 200 or tx_stat == "ACCEPTED":
            return {
                "success":   True,
                "status":    "PAID",
                "amount":    _safe_float(tx.get("amount", amount)),
                "card_type": tx.get("card_brand") or tx.get("gateway_name", ""),
                "payer":     tx.get("payer_name", ""),
                "error":     None,
            }
        elif code == 300 or tx_stat == "REJECTED":
            return {
                "success": False,
                "status":  "REJECTED",
                "error":   tx.get("reason", "Payment rejected."),
            }
        else:  # 100 = PENDING or anything else
            return {
                "success": False,
                "status":  "PENDING",
                "error":   "Payment still processing.",
            }

    except requests.Timeout:
        return {"success": False, "status": "ERROR", "error": "Verification timed out."}
    except Exception as e:
        return {"success": False, "status": "ERROR", "error": str(e)}


def _safe_float(val):
    try:
        return float(str(val).replace(",", ""))
    except Exception:
        return 0.0


def format_bdt(amount):
    """Format as Bangladeshi Taka string. e.g. ৳1,999"""
    return f"৳{int(amount):,}"
