# ============================================================
#  email_service.py  —  Email Notification Service
#  Uses Gmail SMTP — free, no external service needed.
#
#  SETUP (one time):
#  1. Enable 2-Step Verification on your Gmail
#  2. Go to: myaccount.google.com/apppasswords
#  3. Create an App Password for "Mail"
#  4. Add to .env:
#     EMAIL_ENABLED=true
#     EMAIL_ADDRESS=yourname@gmail.com
#     EMAIL_PASSWORD=xxxx xxxx xxxx xxxx   (16-char app password)
# ============================================================

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import EMAIL_ENABLED, EMAIL_ADDRESS, EMAIL_PASSWORD, EMAIL_FROM_NAME, APP_NAME, APP_URL


def _send(to_email: str, subject: str, html_body: str) -> bool:
    """
    Core send function. Returns True on success, False on failure.
    Silently fails if email is not configured — app never crashes.
    """
    if not EMAIL_ENABLED or not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        return False  # Email not configured — skip silently
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{EMAIL_FROM_NAME} <{EMAIL_ADDRESS}>"
        msg["To"]      = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, to_email, msg.as_string())
        return True
    except Exception:
        return False  # Never crash the app over email


def _base_template(content: str, name: str) -> str:
    """Wrap content in a clean email HTML template."""
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #f5f5f5; margin: 0; padding: 20px; }}
    .card {{ background: white; max-width: 560px; margin: 0 auto;
             border-radius: 12px; padding: 36px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
    .header {{ text-align: center; margin-bottom: 28px; }}
    .logo {{ font-size: 28px; font-weight: 700; color: #4F46E5; }}
    .tagline {{ font-size: 13px; color: #9CA3AF; margin-top: 4px; }}
    h2 {{ color: #1F2937; font-size: 20px; margin: 0 0 16px; }}
    p {{ color: #4B5563; line-height: 1.7; margin: 0 0 14px; }}
    .highlight {{ background: #F0F4FF; border-radius: 8px; padding: 16px;
                  border-left: 4px solid #4F46E5; margin: 20px 0; }}
    .btn {{ display: inline-block; background: #4F46E5; color: white;
            padding: 12px 28px; border-radius: 8px; text-decoration: none;
            font-weight: 600; font-size: 15px; margin: 16px 0; }}
    .footer {{ text-align: center; font-size: 12px; color: #9CA3AF; margin-top: 28px;
               border-top: 1px solid #F3F4F6; padding-top: 20px; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="header">
      <div class="logo">🔤 {APP_NAME}</div>
      <div class="tagline">Professional Bangla ↔ English Translation</div>
    </div>
    <p>Hi {name},</p>
    {content}
    <div class="footer">
      {APP_NAME} · <a href="{APP_URL}">{APP_URL}</a><br>
      You received this because you have an account with us.
    </div>
  </div>
</body>
</html>
"""


def send_welcome_email(email: str, name: str) -> bool:
    """Send welcome email after registration."""
    content = f"""
    <h2>Welcome to {APP_NAME}!</h2>
    <p>Your account has been created successfully. You can now start translating between
    Bangla and English with AI-powered accuracy.</p>
    <div class="highlight">
      <strong>Your free account includes:</strong><br>
      • {APP_NAME.split()[0]} free translations per day<br>
      • Translation history saved automatically<br>
      • Favorites and search<br>
      • Analytics dashboard
    </div>
    <a href="{APP_URL}" class="btn">Start Translating →</a>
    <p>Upgrade to Pro anytime for unlimited translations, all 7 domain modes,
    and priority support.</p>
    """
    return _send(email, f"Welcome to {APP_NAME}!", _base_template(content, name))


def send_payment_confirmation(
    email: str, name: str,
    plan_name: str, amount_bdt: float,
    tran_id: str, payment_method: str
) -> bool:
    """Send payment confirmation after successful upgrade."""
    content = f"""
    <h2>Payment Confirmed — You're now Pro! 🎉</h2>
    <p>Thank you for upgrading to <strong>{plan_name}</strong>.
    Your account now has unlimited access.</p>
    <div class="highlight">
      <strong>Payment details:</strong><br>
      Plan: {plan_name}<br>
      Amount paid: ৳{int(amount_bdt):,}<br>
      Payment method: {payment_method}<br>
      Transaction ID: {tran_id}<br>
      Date: {__import__('datetime').datetime.now().strftime('%d %B %Y, %H:%M')}
    </div>
    <a href="{APP_URL}" class="btn">Open the App →</a>
    <p>Keep this email as your payment receipt.
    If you have any issues, reply to this email.</p>
    """
    return _send(
        email,
        f"Payment Confirmed — {plan_name} ✓",
        _base_template(content, name)
    )


def send_password_reset_email(email: str, name: str, otp: str) -> bool:
    """Send OTP for password reset."""
    content = f"""
    <h2>Reset Your Password</h2>
    <p>We received a request to reset your password. Use the code below:</p>
    <div class="highlight" style="text-align:center;">
      <div style="font-size:36px;font-weight:800;color:#4F46E5;letter-spacing:8px;">
        {otp}
      </div>
      <div style="font-size:13px;color:#6B7280;margin-top:8px;">
        This code expires in 15 minutes
      </div>
    </div>
    <p>Enter this code on the password reset page to set a new password.</p>
    <p style="color:#9CA3AF;font-size:13px;">
      If you didn't request this, ignore this email. Your password won't change.
    </p>
    """
    return _send(
        email,
        f"Your {APP_NAME} password reset code: {otp}",
        _base_template(content, name)
    )


def send_pro_expiry_reminder(email: str, name: str, expires_on: str, plan_name: str) -> bool:
    """Remind user their Pro subscription is expiring soon."""
    content = f"""
    <h2>Your Pro subscription expires soon</h2>
    <p>Your <strong>{plan_name}</strong> subscription expires on
    <strong>{expires_on}</strong>.</p>
    <p>Renew now to keep your unlimited access, full history, and all Pro features.</p>
    <a href="{APP_URL}?page=pricing" class="btn">Renew Pro →</a>
    <p style="font-size:13px;color:#9CA3AF;">
      You'll automatically switch to the free tier (5 translations/day) if you don't renew.
      Your history and favorites are never deleted.
    </p>
    """
    return _send(
        email,
        f"Your {APP_NAME} Pro expires on {expires_on}",
        _base_template(content, name)
    )


def send_contact_reply(to_email: str, name: str, message: str, reply: str) -> bool:
    """Send admin reply to a contact form submission."""
    content = f"""
    <h2>Reply to your message</h2>
    <p><strong>Your message:</strong><br>
    <em>{message}</em></p>
    <div class="highlight">
      <strong>Our reply:</strong><br>
      {reply}
    </div>
    <a href="{APP_URL}" class="btn">Open the App →</a>
    """
    return _send(email, f"Re: Your message to {APP_NAME}", _base_template(content, name))
