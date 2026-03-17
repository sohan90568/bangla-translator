# ============================================================
#  auth.py  —  Authentication System
#  Features:
#  - Email + password registration and login
#  - bcrypt password hashing (industry standard)
#  - Secure session tokens stored in DB
#  - Password reset via email OTP
#  - Rate limiting on login attempts
#  - Account lockout after 5 wrong attempts
# ============================================================

import bcrypt
import secrets
import re
from datetime import datetime, timedelta
from config import SESSION_EXPIRE_DAYS


# ── Password hashing ─────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a password with bcrypt. Returns hashed string."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Check a plain password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


# ── Token generation ─────────────────────────────────────────

def generate_session_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(48)


def generate_otp() -> str:
    """Generate a 6-digit OTP for password reset."""
    import random
    return str(random.randint(100000, 999999))


# ── Validation ───────────────────────────────────────────────

def validate_email(email: str) -> tuple[bool, str]:
    """Validate email format. Returns (is_valid, error_message)."""
    email = email.strip().lower()
    if not email:
        return False, "Email is required."
    pattern = r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return False, "Invalid email format. Example: yourname@gmail.com"
    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password strength.
    Rules: min 8 chars, at least 1 letter and 1 number.
    """
    if not password:
        return False, "Password is required."
    if len(password) < 8:
        return False, "Password must be at least 8 characters."
    if not any(c.isalpha() for c in password):
        return False, "Password must contain at least one letter."
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one number."
    return True, ""


def validate_display_name(name: str) -> tuple[bool, str]:
    """Validate display name."""
    name = name.strip()
    if not name:
        return False, "Name is required."
    if len(name) < 2:
        return False, "Name must be at least 2 characters."
    if len(name) > 50:
        return False, "Name must be under 50 characters."
    return True, ""


# ── Auth operations (use database via import) ─────────────────

def register_user(email: str, password: str, display_name: str) -> dict:
    """
    Register a new user.
    Returns: {success, user_id, error}
    """
    from database import db_register_user

    # Validate inputs
    ok, err = validate_email(email)
    if not ok:
        return {"success": False, "error": err}

    ok, err = validate_password(password)
    if not ok:
        return {"success": False, "error": err}

    ok, err = validate_display_name(display_name)
    if not ok:
        return {"success": False, "error": err}

    # Hash password and save
    pw_hash = hash_password(password)
    result  = db_register_user(
        email=email.strip().lower(),
        pw_hash=pw_hash,
        display_name=display_name.strip()
    )
    return result


def login_user(email: str, password: str) -> dict:
    """
    Authenticate a user and create a session.
    Returns: {success, token, user, error}
    """
    from database import db_get_user_by_email, db_create_session, db_record_login_attempt

    if not email or not password:
        return {"success": False, "error": "Email and password are required."}

    email = email.strip().lower()
    user  = db_get_user_by_email(email)

    if not user:
        db_record_login_attempt(email, success=False)
        return {"success": False, "error": "No account found with this email."}

    # Check account lockout
    if user.get("locked_until"):
        locked_until = user["locked_until"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if now < locked_until:
            return {
                "success": False,
                "error": f"Account locked due to too many failed attempts. Try again after {locked_until[:16]}."
            }

    if not verify_password(password, user["password_hash"]):
        db_record_login_attempt(email, success=False)
        # Check if should lock account
        from database import db_get_failed_attempts
        attempts = db_get_failed_attempts(email)
        if attempts >= 5:
            from database import db_lock_account
            db_lock_account(email, minutes=30)
            return {
                "success": False,
                "error": "Too many failed attempts. Account locked for 30 minutes."
            }
        remaining = 5 - attempts
        return {
            "success": False,
            "error": f"Wrong password. {remaining} attempt(s) remaining before lockout."
        }

    # Success — create session token
    token   = generate_session_token()
    expires = (datetime.now() + timedelta(days=SESSION_EXPIRE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    db_create_session(user_id=user["user_id"], token=token, expires_at=expires)
    db_record_login_attempt(email, success=True)

    return {"success": True, "token": token, "user": user}


def validate_session(token: str) -> dict | None:
    """
    Check if a session token is valid and not expired.
    Returns user dict if valid, None otherwise.
    """
    if not token:
        return None
    from database import db_get_session_user
    return db_get_session_user(token)


def logout_user(token: str):
    """Invalidate a session token."""
    if token:
        from database import db_delete_session
        db_delete_session(token)


def request_password_reset(email: str) -> dict:
    """
    Generate OTP for password reset and send email.
    Returns: {success, otp (for testing), error}
    """
    from database import db_get_user_by_email, db_save_otp

    user = db_get_user_by_email(email.strip().lower())
    if not user:
        # Don't reveal if email exists or not
        return {"success": True, "message": "If that email exists, a reset code was sent."}

    otp     = generate_otp()
    expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    db_save_otp(email=email.lower(), otp=otp, expires_at=expires)

    # Send email
    from email_service import send_password_reset_email
    send_password_reset_email(email=email, name=user.get("display_name", ""), otp=otp)

    return {"success": True, "message": "Reset code sent to your email."}


def reset_password_with_otp(email: str, otp: str, new_password: str) -> dict:
    """Reset password using OTP."""
    from database import db_verify_otp, db_update_password

    ok, err = validate_password(new_password)
    if not ok:
        return {"success": False, "error": err}

    valid = db_verify_otp(email.lower(), otp)
    if not valid:
        return {"success": False, "error": "Invalid or expired reset code."}

    pw_hash = hash_password(new_password)
    db_update_password(email.lower(), pw_hash)
    return {"success": True, "message": "Password updated successfully. Please log in."}
