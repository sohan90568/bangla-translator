# ============================================================
#  email_service.py  —  Email Notification Service
#  Uses Gmail SMTP — reads secrets LIVE on every call
#  (fixes Streamlit Cloud caching issue)
#
#  SETUP:
#  1. Enable 2-Step Verification on your Gmail
#  2. Go to: myaccount.google.com/apppasswords
#  3. Create App Password → copy 16-char code
#  4. Add to Streamlit secrets:
#       EMAIL_ENABLED  = "true"
#       EMAIL_ADDRESS  = "yourname@gmail.com"
#       EMAIL_PASSWORD = "xxxx xxxx xxxx xxxx"
# ============================================================

import smtplib
import ssl
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def _get_email_config() -> dict:
    """
    Read email settings FRESH on every call.
    Checks st.secrets first (Streamlit Cloud), then os.environ (.env).
    This avoids the import-time caching bug.
    """
    def _read(key, default=""):
        # Try Streamlit secrets
        try:
            import streamlit as st
            val = st.secrets.get(key, "")
            if val:
                return str(val).strip()
        except Exception:
            pass
        # Fall back to environment variable
        return os.getenv(key, default).strip()

    return {
        "enabled":   _read("EMAIL_ENABLED",   "false").lower() == "true",
        "address":   _read("EMAIL_ADDRESS",   ""),
        "password":  _read("EMAIL_PASSWORD",  ""),
        "from_name": _read("EMAIL_FROM_NAME", "Bangla AI Translator"),
    }


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """Send email via Gmail SMTP. Returns True on success."""
    cfg = _get_email_config()

    if not cfg["enabled"]:
        return False
    if not cfg["address"] or not cfg["password"]:
        return False
    if not to_email or "@" not in to_email:
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{cfg['from_name']} <{cfg['address']}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(cfg["address"], cfg["password"])
            server.sendmail(cfg["address"], to_email, msg.as_string())
        return True
    except smtplib.SMTPAuthenticationError:
        # Wrong Gmail credentials — log but don't crash
        try:
            import streamlit as st
            st.warning("Email: Gmail authentication failed. Check EMAIL_ADDRESS and EMAIL_PASSWORD in secrets.")
        except Exception:
            pass
        return False
    except Exception:
        return False


def _app_name() -> str:
    try:
        from config import APP_NAME
        return APP_NAME
    except Exception:
        return "Bangla AI Translator"


def _app_url() -> str:
    try:
        import streamlit as st
        v = st.secrets.get("APP_URL", "")
        if v:
            return str(v)
    except Exception:
        pass
    return os.getenv("APP_URL", "https://bangla-translator.streamlit.app")


def _base_template(content: str, name: str) -> str:
    app_name = _app_name()
    app_url  = _app_url()
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background:#f5f5f5; margin:0; padding:20px; }}
    .card {{ background:white; max-width:560px; margin:0 auto;
             border-radius:12px; padding:36px;
             box-shadow:0 2px 8px rgba(0,0,0,0.08); }}
    .logo {{ font-size:26px; font-weight:700; color:#4F46E5;
             text-align:center; margin-bottom:4px; }}
    .tagline {{ font-size:13px; color:#9CA3AF; text-align:center;
                margin-bottom:28px; }}
    h2 {{ color:#1F2937; font-size:20px; margin:0 0 16px; }}
    p  {{ color:#4B5563; line-height:1.7; margin:0 0 14px; }}
    .highlight {{ background:#F0F4FF; border-radius:8px; padding:16px;
                  border-left:4px solid #4F46E5; margin:20px 0; }}
    .otp-box {{ background:#F0F4FF; border-radius:10px; padding:20px;
                text-align:center; margin:20px 0; }}
    .otp-code {{ font-size:38px; font-weight:800; color:#4F46E5;
                 letter-spacing:10px; }}
    .otp-exp {{ font-size:13px; color:#6B7280; margin-top:8px; }}
    .btn {{ display:inline-block; background:#4F46E5; color:white;
            padding:12px 28px; border-radius:8px; text-decoration:none;
            font-weight:600; font-size:15px; margin:16px 0; }}
    .footer {{ text-align:center; font-size:12px; color:#9CA3AF;
               margin-top:28px; border-top:1px solid #F3F4F6;
               padding-top:20px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">🔤 {app_name}</div>
    <div class="tagline">Professional Bangla ↔ English Translation</div>
    <p>Hi {name},</p>
    {content}
    <div class="footer">
      {app_name} &middot;
      <a href="{app_url}">{app_url}</a><br>
      You received this because you have an account with us.
    </div>
  </div>
</body>
</html>
"""


# ── Public email functions ────────────────────────────────────

def send_welcome_email(email: str, name: str) -> bool:
    """Sent immediately after a user registers."""
    app_name = _app_name()
    app_url  = _app_url()
    content = f"""
    <h2>Welcome to {app_name}! 🎉</h2>
    <p>Your account has been created. You can now translate between Bangla and English
    with AI-powered accuracy across 7 professional domains.</p>
    <div class="highlight">
      <strong>Your free account includes:</strong><br>
      &bull; 5 free translations per day<br>
      &bull; Translation history saved automatically<br>
      &bull; Favorites, search, and analytics<br>
      &bull; Bangla &amp; English auto-detection
    </div>
    <a href="{app_url}" class="btn">Start Translating →</a>
    <p>Upgrade to Pro anytime for unlimited translations and all domain modes.</p>
    """
    return _send(email, f"Welcome to {app_name}! 🎉", _base_template(content, name))


def send_payment_confirmation(
    email: str, name: str,
    plan_name: str, amount_bdt: float,
    tran_id: str, payment_method: str
) -> bool:
    """Sent after a successful payment — works as receipt."""
    from datetime import datetime
    app_name = _app_name()
    app_url  = _app_url()
    content = f"""
    <h2>Payment Confirmed — You're Pro now! 🎉</h2>
    <p>Thank you for upgrading to <strong>{plan_name}</strong>.
    You now have <strong>unlimited access</strong> to all features.</p>
    <div class="highlight">
      <strong>Payment receipt:</strong><br><br>
      Plan: <strong>{plan_name}</strong><br>
      Amount paid: <strong>৳{int(amount_bdt):,}</strong><br>
      Payment method: {payment_method}<br>
      Transaction ID: <code>{tran_id}</code><br>
      Date: {datetime.now().strftime('%d %B %Y, %H:%M')}
    </div>
    <a href="{app_url}" class="btn">Open the App →</a>
    <p style="font-size:13px;color:#9CA3AF;">
      Keep this email as your payment receipt.
      For any issues reply to this email or contact us on WhatsApp: 01833052490
    </p>
    """
    return _send(
        email,
        f"Payment Confirmed — {plan_name} ✓",
        _base_template(content, name)
    )


def send_password_reset_email(email: str, name: str, otp: str) -> bool:
    """Sent when user clicks Forgot Password — contains 6-digit OTP."""
    app_name = _app_name()
    content = f"""
    <h2>Reset Your Password</h2>
    <p>We received a request to reset your {app_name} password.
    Use the code below to set a new password:</p>
    <div class="otp-box">
      <div class="otp-code">{otp}</div>
      <div class="otp-exp">This code expires in <strong>15 minutes</strong></div>
    </div>
    <p>Enter this code on the password reset page in the app.</p>
    <p style="font-size:13px;color:#9CA3AF;">
      If you did not request this, ignore this email safely.
      Your password will not change.
    </p>
    """
    return _send(
        email,
        f"Your {app_name} password reset code: {otp}",
        _base_template(content, name)
    )


def send_pro_expiry_reminder(
    email: str, name: str,
    expires_on: str, plan_name: str
) -> bool:
    """Sent a few days before Pro subscription expires."""
    app_name = _app_name()
    app_url  = _app_url()
    content = f"""
    <h2>Your Pro subscription expires soon ⏰</h2>
    <p>Your <strong>{plan_name}</strong> expires on <strong>{expires_on}</strong>.</p>
    <p>Renew now to keep your unlimited access, full history, and all Pro features.</p>
    <a href="{app_url}?page=pricing" class="btn">Renew Pro →</a>
    <p style="font-size:13px;color:#9CA3AF;">
      After expiry you automatically move to the free tier (5 translations/day).
      Your history and favorites are never deleted.
    </p>
    """
    return _send(
        email,
        f"Your {app_name} Pro expires on {expires_on}",
        _base_template(content, name)
    )
