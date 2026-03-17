# ============================================================
#  config.py  —  Central configuration
#  Reads from .env locally, from st.secrets on Streamlit Cloud.
#  Works automatically in both environments.
# ============================================================

import os
from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str = "") -> str:
    """
    Read a config value.
    Priority: st.secrets (Streamlit Cloud) → os.environ (.env) → default
    """
    # Try Streamlit secrets first (only available when deployed)
    try:
        import streamlit as st
        val = st.secrets.get(key)
        if val is not None:
            return str(val)
    except Exception:
        pass
    # Fall back to environment variable / .env
    return os.getenv(key, default)


# ── App identity ─────────────────────────────────────────────
APP_NAME        = "Bangla AI Translator"
APP_VERSION     = "2.0.0"
APP_TAGLINE     = "Professional Bangla ↔ English translation powered by AI"
ADMIN_USERNAME  = _get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD  = _get("ADMIN_PASSWORD", "Admin@1234")
# Your email — anyone who logs in with this email gets admin automatically.
# Set ADMIN_EMAIL in Streamlit secrets or .env
ADMIN_EMAIL     = _get("ADMIN_EMAIL", "").strip().lower()

# ── Free tier limits ─────────────────────────────────────────
FREE_TRANSLATIONS_PER_DAY = 5    # resets at midnight
FREE_TRANSLATIONS_TOTAL   = 20   # lifetime cap before upgrade
SESSION_EXPIRE_DAYS       = 30   # login session lifetime

# ── AI engine — Groq (FREE, no card needed) ──────────────────
# Get free key: console.groq.com
GROQ_API_KEY = _get("GROQ_API_KEY", "")
GROQ_MODEL   = "llama-3.3-70b-versatile"

# ── Database ─────────────────────────────────────────────────
# data/ folder is created automatically on first run
DB_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "data", "translator.db"
)

# ── PortPos Payment Gateway ───────────────────────────────────
#
# SANDBOX (free, no approval needed):
#   1. Go to: sandbox.portpos.com
#   2. Register → Log in → API Keys
#   3. Copy App Key + Secret Key → paste in .env or st.secrets
#
# LIVE (no trade license needed):
#   1. Go to: manage.portpos.com
#   2. Upload NID + bank account → approved in 1-3 days
#
PORTPOS_SANDBOX    = _get("PORTPOS_SANDBOX",    "true").lower() == "true"
PORTPOS_APP_KEY    = _get("PORTPOS_APP_KEY",    "")
PORTPOS_SECRET_KEY = _get("PORTPOS_SECRET_KEY", "")
APP_URL            = _get("APP_URL", "http://localhost:8501")

# ── Email notifications (Gmail SMTP — optional) ───────────────
EMAIL_ENABLED   = _get("EMAIL_ENABLED", "false").lower() == "true"
EMAIL_ADDRESS   = _get("EMAIL_ADDRESS",  "")
EMAIL_PASSWORD  = _get("EMAIL_PASSWORD", "")
EMAIL_FROM_NAME = _get("EMAIL_FROM_NAME", APP_NAME)

# ── Pricing plans ─────────────────────────────────────────────
PLANS = {
    "monthly": {
        "name":          "Pro Monthly",
        "amount_bdt":    299,
        "duration_days": 30,
        "desc":          "Unlimited translations for 30 days",
        "popular":       False,
    },
    "yearly": {
        "name":          "Pro Yearly",
        "amount_bdt":    1999,
        "duration_days": 365,
        "desc":          "Unlimited for 1 year — save 44%",
        "popular":       True,
    },
    "lifetime": {
        "name":          "Lifetime Pro",
        "amount_bdt":    4999,
        "duration_days": 99999,
        "desc":          "Pay once, use forever",
        "popular":       False,
    },
}

# ── Translation options ───────────────────────────────────────
DOMAINS = ["General", "Medical", "Legal", "Business", "Academic", "News", "Casual / SMS"]
TONES   = ["Formal", "Informal", "Simple", "Professional"]
