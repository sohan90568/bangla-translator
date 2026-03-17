# ============================================================
#  app.py  —  Bangla AI Translator  (Production v2.0)
#  Run:  streamlit run app.py
# ============================================================

import streamlit as st
import pandas as pd
import json
import uuid
from datetime import datetime

from config       import (APP_NAME, APP_VERSION, PLANS, DOMAINS, TONES,
                           FREE_TRANSLATIONS_PER_DAY, FREE_TRANSLATIONS_TOTAL,
                           PORTPOS_SANDBOX, ADMIN_EMAIL)
from auth         import (register_user, login_user, validate_session,
                           logout_user, request_password_reset, reset_password_with_otp)
from translator   import translate_text, detect_language, improve_translation, explain_translation
from payments     import create_payment, verify_payment, format_bdt, SANDBOX_TEST_CREDENTIALS
from database     import (
    init_db,
    check_and_update_daily_limit, save_translation,
    get_recent_translations, search_translations,
    delete_translation, rate_translation, delete_all_history,
    toggle_favorite, get_favorites, get_favorite_folders,
    update_favorite_note, update_favorite_folder,
    get_search_history, clear_search_history,
    get_analytics_summary, get_daily_counts,
    get_domain_stats, get_hourly_heatmap,
    save_setting, get_setting, export_user_data, get_db_size,
    create_payment_record, mark_payment_success, mark_payment_failed,
    get_payment_by_tran, get_user_payments,
    get_all_payments, get_payment_stats,
    get_subscription, check_subscription_expiry,
    upgrade_to_pro, downgrade_to_free,
    create_coupon, apply_coupon, get_coupon,
    get_all_coupons, deactivate_coupon,
    db_update_user_field, db_get_all_users,
    get_all_emails_for_admin,
)

# ── Init database ────────────────────────────────────────────
init_db()

# ── Page config ──────────────────────────────────────────────
st.set_page_config(
    page_title=APP_NAME,
    page_icon="🔤",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help":    "mailto:support@yourdomain.com",
        "Report a Bug":"mailto:support@yourdomain.com",
        "About":       f"{APP_NAME} v{APP_VERSION} — Professional Bangla ↔ English AI Translator"
    }
)

# ── CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Bengali:wght@400;500;600&display=swap');
*  { box-sizing: border-box; }
.main { background: #FAFAFA; }
.block-container { padding-top: 1.5rem !important; }

/* Translation area */
.tx-box {
  background: #F0F4FF; border: 1.5px solid #C5D5FF;
  border-radius: 12px; padding: 16px 18px;
  font-size: 15px; line-height: 2.0; min-height: 180px;
  color: #1a1a2e; white-space: pre-wrap;
  font-family: 'Noto Sans Bengali', sans-serif;
}
.tx-empty {
  background: #F9FAFB; border: 1.5px dashed #D1D5DB;
  border-radius: 12px; padding: 16px 18px;
  font-size: 14px; min-height: 180px; color: #9CA3AF;
  display: flex; align-items: center; justify-content: center;
}
textarea {
  font-family: 'Noto Sans Bengali', sans-serif !important;
  font-size: 15px !important; line-height: 1.8 !important;
}

/* Cards */
.card {
  background: white; border: 1px solid #E5E7EB;
  border-radius: 12px; padding: 16px; margin-bottom: 8px;
}
.card-warn { border-left: 4px solid #F59E0B !important; }
.card-success { border-left: 4px solid #10B981 !important; }
.card-info { border-left: 4px solid #4F46E5 !important; }

/* Badges */
.badge { font-size: 11px; padding: 2px 8px; border-radius: 10px;
         font-weight: 600; display: inline-block; }
.badge-pro   { background: #FEF3C7; color: #92400E; border: 1px solid #FCD34D; }
.badge-free  { background: #F3F4F6; color: #6B7280; }
.badge-paid  { background: #D1FAE5; color: #065F46; }
.badge-pend  { background: #FEF3C7; color: #92400E; }
.badge-fail  { background: #FEE2E2; color: #991B1B; }

/* Plan cards */
.plan-card {
  border: 1.5px solid #E5E7EB; border-radius: 14px;
  padding: 20px 16px; text-align: center; background: white;
  transition: border-color .2s, transform .1s;
}
.plan-card:hover { border-color: #4F46E5; transform: translateY(-2px); }
.plan-popular { border-color: #4F46E5 !important; background: #F5F3FF !important; }

/* Sidebar */
[data-testid="stSidebar"] { background: #1E1E2E; }
[data-testid="stSidebar"] .stRadio label { color: #CDD6F4 !important; }
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #CDD6F4 !important; }

/* Progress bar */
.limit-bar { height: 6px; background: #E5E7EB; border-radius: 3px; overflow: hidden; }
.limit-fill { height: 100%; border-radius: 3px; transition: width .3s;
              background: linear-gradient(90deg, #4F46E5, #7C3AED); }

/* Mobile responsive */
@media (max-width: 640px) {
  .tx-box, .tx-empty { min-height: 120px; font-size: 14px; }
  .block-container { padding: 0.5rem !important; }
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════
#  SESSION STATE
# ════════════════════════════════════════════════════════════

def _ss(key, default=None):
    if key not in st.session_state:
        st.session_state[key] = default
    return st.session_state[key]

_ss("auth_token",    None)
_ss("user",          None)
_ss("page",          "translate")
_ss("result",        "")
_ss("source_text",   "")
_ss("last_trans_id", None)
_ss("direction",     "Bangla → English")
_ss("coupon_data",   None)
_ss("sel_plan",      "yearly")
_ss("show_pay",      False)
_ss("admin_ok",      False)


# ── Payment callback from PortPos ───────────────────────────
qp = st.query_params
if qp.get("payment") and qp.get("tran_id"):
    status  = qp["payment"]
    tran_id = qp["tran_id"]
    uid     = int(qp.get("uid", 0))
    plan    = qp.get("plan", "monthly")

    if status == "success":
        vfy = verify_payment(tran_id)
        method = vfy.get("card_type", "PortPos")
        if vfy.get("success"):
            mark_payment_success(tran_id, method)
        else:
            # Sandbox fallback
            pay_rec = get_payment_by_tran(tran_id)
            if pay_rec and pay_rec.get("status") == "PENDING":
                mark_payment_success(tran_id, "Sandbox")
        st.session_state["_pay_ok"] = True
        # Refresh user session
        if st.session_state.auth_token:
            from database import db_get_session_user
            st.session_state.user = db_get_session_user(st.session_state.auth_token)
    elif status in ("failed", "cancelled"):
        mark_payment_failed(tran_id, f"User {status}")
        st.session_state["_pay_fail"] = status
    st.query_params.clear()


# ════════════════════════════════════════════════════════════
#  AUTH PAGES  (shown when not logged in)
# ════════════════════════════════════════════════════════════

def _auth_page():
    """Registration / Login / Password reset."""
    # Check persistent token
    if st.session_state.auth_token:
        user = validate_session(st.session_state.auth_token)
        if user:
            st.session_state.user = user
            return True
        else:
            st.session_state.auth_token = None

    # Center the auth card
    _, center, _ = st.columns([1, 2, 1])
    with center:
        st.markdown(f"""
        <div style='text-align:center;padding:30px 0 20px'>
          <div style='font-size:48px'>🔤</div>
          <h1 style='font-size:28px;font-weight:700;margin:8px 0 4px'>{APP_NAME}</h1>
          <p style='color:#6B7280;margin:0'>Professional Bangla ↔ English AI Translation</p>
        </div>
        """, unsafe_allow_html=True)

        auth_tab = st.radio(
            "auth_mode", ["Login", "Register", "Forgot Password"],
            horizontal=True, label_visibility="collapsed"
        )

        if auth_tab == "Login":
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="yourname@gmail.com")
                password = st.text_input("Password", type="password", placeholder="Your password")
                submitted = st.form_submit_button("Login", type="primary", use_container_width=True)
            if submitted:
                if not email or not password:
                    st.error("Please enter your email and password.")
                else:
                    with st.spinner("Logging in..."):
                        res = login_user(email, password)
                    if res["success"]:
                        st.session_state.auth_token = res["token"]
                        st.session_state.user       = res["user"]
                        st.success(f"Welcome back, {res['user']['display_name']}!")
                        st.rerun()
                    else:
                        st.error(res["error"])

        elif auth_tab == "Register":
            with st.form("reg_form"):
                name  = st.text_input("Your name",  placeholder="Muhammad Rahman")
                email = st.text_input("Email",       placeholder="yourname@gmail.com")
                pwd1  = st.text_input("Password",    type="password", placeholder="Min 8 chars, must include a number")
                pwd2  = st.text_input("Confirm password", type="password", placeholder="Repeat password")
                submitted = st.form_submit_button("Create account", type="primary", use_container_width=True)
            if submitted:
                if pwd1 != pwd2:
                    st.error("Passwords do not match.")
                else:
                    with st.spinner("Creating account..."):
                        res = register_user(email, pwd1, name)
                    if res["success"]:
                        # Auto-login after register
                        login_res = login_user(email, pwd1)
                        if login_res["success"]:
                            st.session_state.auth_token = login_res["token"]
                            st.session_state.user       = login_res["user"]
                            # Send welcome email (silently)
                            try:
                                from email_service import send_welcome_email
                                send_welcome_email(email.strip().lower(), name.strip())
                            except Exception:
                                pass
                            st.success(f"Account created! Welcome, {name}!")
                            st.rerun()
                    else:
                        st.error(res["error"])

        else:  # Forgot Password
            st.markdown("#### Reset your password")
            if "reset_step" not in st.session_state:
                st.session_state.reset_step  = 1
                st.session_state.reset_email = ""

            if st.session_state.reset_step == 1:
                with st.form("reset_req"):
                    email = st.text_input("Your email", placeholder="yourname@gmail.com")
                    sub   = st.form_submit_button("Send reset code", type="primary", use_container_width=True)
                if sub:
                    res = request_password_reset(email)
                    if res["success"]:
                        st.session_state.reset_email = email.lower()
                        st.session_state.reset_step  = 2
                        st.success("Reset code sent! Check your email.")
                        st.rerun()
                    else:
                        st.error(res.get("error","Failed"))

            else:
                st.info(f"Code sent to {st.session_state.reset_email}")
                with st.form("reset_verify"):
                    otp  = st.text_input("6-digit code", placeholder="123456")
                    pwd1 = st.text_input("New password", type="password")
                    pwd2 = st.text_input("Confirm",      type="password")
                    sub  = st.form_submit_button("Reset password", type="primary", use_container_width=True)
                if sub:
                    if pwd1 != pwd2:
                        st.error("Passwords do not match.")
                    else:
                        res = reset_password_with_otp(st.session_state.reset_email, otp, pwd1)
                        if res["success"]:
                            st.success(res["message"])
                            st.session_state.reset_step = 1
                        else:
                            st.error(res["error"])

        st.markdown("""
        <div style='text-align:center;font-size:12px;color:#9CA3AF;margin-top:20px'>
          By creating an account you agree to our
          <a href='?page=terms' style='color:#4F46E5'>Terms of Service</a> and
          <a href='?page=privacy' style='color:#4F46E5'>Privacy Policy</a>
        </div>
        """, unsafe_allow_html=True)
    return False


# ── Check auth ───────────────────────────────────────────────
if not st.session_state.user:
    if not _auth_page():
        st.stop()

user    = st.session_state.user
uid     = user["user_id"]
is_pro  = bool(user.get("is_pro", 0))
display = user.get("display_name", "User")
email   = user.get("email", "")
color   = user.get("avatar_color", "#4F46E5")
initials= "".join(w[0].upper() for w in display.split()[:2]) or "U"

# ── Auto-admin: if logged-in email matches ADMIN_EMAIL in secrets/env,
#    grant admin instantly — solves Streamlit Cloud fresh-DB problem.
_admin_email = ADMIN_EMAIL.strip().lower()
is_admin = (
    bool(user.get("is_admin", 0))
    or (bool(_admin_email) and email.strip().lower() == _admin_email)
)
# Write is_admin=1 to DB so it persists across sessions
if is_admin and not bool(user.get("is_admin", 0)):
    try:
        from database import get_db as _gdb_admin
        with _gdb_admin() as _c:
            _c.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (uid,))
        st.session_state.user["is_admin"] = 1
    except Exception:
        pass

# Check subscription expiry on each load
if is_pro and not check_subscription_expiry(uid):
    is_pro = False
    from database import db_get_user_by_id
    st.session_state.user = db_get_user_by_id(uid) or user


# ════════════════════════════════════════════════════════════
#  SIDEBAR
# ════════════════════════════════════════════════════════════

with st.sidebar:
    # User avatar card
    st.markdown(f"""
    <div style='display:flex;align-items:center;gap:10px;padding:8px 0 4px'>
      <div style='width:38px;height:38px;border-radius:50%;background:{color};
                  display:flex;align-items:center;justify-content:center;
                  color:white;font-weight:700;font-size:14px;flex-shrink:0'>{initials}</div>
      <div>
        <div style='font-weight:600;font-size:14px;color:#CDD6F4'>{display}</div>
        <div style='font-size:11px;color:#6C7086'>{email or "No email set"}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    if is_pro:
        st.markdown('<span class="badge badge-pro">★ Pro</span>', unsafe_allow_html=True)

    st.markdown("---")

    nav_items = ["🔤 Translate","📋 History","★ Favorites","📊 Analytics",
                 "💳 Pricing","👤 Profile","📜 Terms","🔒 Privacy"]
    if is_admin:
        nav_items.append("⚙️ Admin")

    page = st.radio("nav", nav_items, label_visibility="collapsed")

    st.markdown("---")

    # Usage meter
    limit_data = check_and_update_daily_limit(uid, is_pro)
    if not is_pro:
        used_today = limit_data.get("used_today", 0)
        pct = min(100, int(used_today / FREE_TRANSLATIONS_PER_DAY * 100))
        st.markdown(
            f"**Today:** {used_today}/{FREE_TRANSLATIONS_PER_DAY} "
            f"<span style='font-size:11px;color:#6C7086'>free uses</span>",
            unsafe_allow_html=True
        )
        st.markdown(
            f'<div class="limit-bar"><div class="limit-fill" style="width:{pct}%"></div></div>',
            unsafe_allow_html=True
        )
        total_used = user.get("total_count", 0)
        remaining_total = max(0, FREE_TRANSLATIONS_TOTAL - total_used)
        st.caption(f"{remaining_total} total free uses remaining")
        if not limit_data.get("allowed"):
            st.error("Limit reached — upgrade for unlimited")
    else:
        st.success("Pro — Unlimited ∞")

    # Promo code entry (free users only)
    if not is_pro:
        st.markdown("---")
        promo = st.text_input("Promo code", placeholder="Enter code...",
                              label_visibility="collapsed", key="sidebar_promo")
        if st.button("Redeem", use_container_width=True, key="redeem_btn"):
            if promo.strip():
                from database import db_register_user   # just import check
                # Use promo code system from promo_codes table
                from database import get_coupon as _gc
                c = _gc(promo.strip())
                if c and c.get("discount_type") == "free":
                    r = apply_coupon(promo.strip(), 0, None)
                    # Activate free pro
                    upgrade_to_pro(uid, "monthly")
                    from database import db_get_user_by_id
                    st.session_state.user = db_get_user_by_id(uid)
                    st.success("Free Pro access activated!")
                    st.rerun()
                else:
                    st.info("Use coupons on the 💳 Pricing page.")

    st.markdown("---")
    # Quick stats
    summary = get_analytics_summary(uid)
    c1, c2 = st.columns(2)
    c1.metric("Total", f"{summary.get('total',0):,}")
    c2.metric("Today", f"{summary.get('today_count',0)}")
    streak = summary.get("streak", 0)
    if streak > 1:
        st.markdown(
            f'<div style="font-size:12px;color:#F59E0B;font-weight:600">'
            f'🔥 {streak}-day streak</div>',
            unsafe_allow_html=True
        )

    st.markdown("---")
    st.caption(f"DB: {get_db_size()} | v{APP_VERSION}")
    if st.button("Logout", use_container_width=True):
        logout_user(st.session_state.auth_token)
        st.session_state.auth_token = None
        st.session_state.user       = None
        st.rerun()


# ════════════════════════════════════════════════════════════
#  PAGE — TRANSLATE
# ════════════════════════════════════════════════════════════

if page == "🔤 Translate":

    # Payment result messages
    if st.session_state.pop("_pay_ok", False):
        st.success("🎉 Payment confirmed! You are now Pro — unlimited translations.")
        st.balloons()
        from database import db_get_user_by_id
        st.session_state.user = db_get_user_by_id(uid) or user
        is_pro = True

    if st.session_state.pop("_pay_fail", None):
        st.error("Payment was not completed. Please try again on the Pricing page.")

    st.markdown("# 🔤 Bangla ↔ English Translator")

    # Controls
    cc1, cc2, cc3, cc4 = st.columns([2,2,2,1])
    with cc1:
        direction = st.selectbox(
            "Direction", ["Bangla → English","English → Bangla"],
            index=0 if user.get("preferred_lang","Bangla → English")=="Bangla → English" else 1
        )
        db_update_user_field(uid, "preferred_lang", direction)
    with cc2:
        domain = st.selectbox(
            "Domain", DOMAINS,
            index=DOMAINS.index(user.get("preferred_domain","General"))
                  if user.get("preferred_domain","General") in DOMAINS else 0
        )
        db_update_user_field(uid, "preferred_domain", domain)
    with cc3:
        tone = st.selectbox(
            "Tone", TONES,
            index=TONES.index(user.get("preferred_tone","Formal"))
                  if user.get("preferred_tone","Formal") in TONES else 0
        )
        db_update_user_field(uid, "preferred_tone", tone)
    with cc4:
        keep_fmt = st.checkbox("Keep formatting", value=True)

    st.markdown("---")

    # Limit check banner
    limit_check = check_and_update_daily_limit(uid, is_pro)
    can_translate = limit_check.get("allowed", False)
    if not can_translate and not is_pro:
        st.warning(
            f"⚠️ {limit_check.get('reason','Limit reached.')} "
            "Go to **💳 Pricing** to upgrade."
        )

    # Two-column layout
    src_label = "🇧🇩 Bangla"  if direction=="Bangla → English" else "🇬🇧 English"
    tgt_label = "🇬🇧 English" if direction=="Bangla → English" else "🇧🇩 Bangla"
    placeholder = "এখানে বাংলা লিখুন..." if direction=="Bangla → English" else "Type English here..."

    col_src, col_sw, col_tgt = st.columns([10,1,10])

    with col_src:
        st.markdown(f"**{src_label}**")
        source = st.text_area(
            "src", label_visibility="collapsed",
            placeholder=placeholder, height=200,
            value=st.session_state.source_text, key="src_area"
        )
        if source:
            st.caption(f"{len(source):,} chars · {len(source.split()):,} words")
            if len(source) > 5:
                det = detect_language(source)
                exp = "Bangla" if direction=="Bangla → English" else "English"
                if det not in ("unknown","Mixed") and det != exp:
                    st.info(f"Detected: {det} — did you mean to swap direction?")

    with col_sw:
        st.markdown("<br><br><br><br>", unsafe_allow_html=True)
        if st.button("⇄", help="Swap direction"):
            nd = "English → Bangla" if direction=="Bangla → English" else "Bangla → English"
            st.session_state.direction  = nd
            if st.session_state.result:
                st.session_state.source_text = st.session_state.result
                st.session_state.result      = ""
            st.rerun()

    with col_tgt:
        st.markdown(f"**{tgt_label}**")
        if st.session_state.result:
            st.markdown(
                f'<div class="tx-box">{st.session_state.result}</div>',
                unsafe_allow_html=True
            )
        else:
            st.markdown(
                '<div class="tx-empty">Translation will appear here...</div>',
                unsafe_allow_html=True
            )

    st.markdown("")

    # Action buttons
    b1,b2,b3,b4,b5 = st.columns([3,2,2,2,3])
    with b1:
        translate_btn = st.button(
            "Translate", type="primary",
            use_container_width=True, disabled=not can_translate
        )
    with b2:
        clear_btn = st.button("Clear", use_container_width=True)
    with b3:
        fav_btn = st.button(
            "★ Favorite", use_container_width=True,
            disabled=not st.session_state.last_trans_id
        )
    with b4:
        if st.session_state.result:
            st.download_button(
                "Download .txt",
                data=(
                    f"ORIGINAL ({src_label}):\n{source}\n\n"
                    f"TRANSLATION ({tgt_label}):\n{st.session_state.result}\n\n"
                    f"Domain: {domain} | Tone: {tone}\n"
                    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                ),
                file_name=f"translation_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                mime="text/plain", use_container_width=True
            )
    with b5:
        if not can_translate and not is_pro:
            if st.button("Upgrade to Pro →", type="secondary", use_container_width=True):
                st.session_state.page = "💳 Pricing"
                st.rerun()

    # Translate action
    if translate_btn:
        if not source.strip():
            st.warning("Please enter some text first.")
        else:
            with st.spinner("Translating..."):
                res = translate_text(source, direction, domain, tone, keep_fmt)
            if res["success"]:
                st.session_state.result      = res["translation"]
                st.session_state.source_text = source
                # Save to DB (counter already incremented by check_and_update_daily_limit)
                tid = save_translation(
                    user_id=uid,
                    source_lang="Bangla" if direction=="Bangla → English" else "English",
                    target_lang="English" if direction=="Bangla → English" else "Bangla",
                    source_text=source,
                    translated_text=res["translation"],
                    domain=domain, tone=tone,
                    tokens_used=res.get("tokens_used",0)
                )
                st.session_state.last_trans_id = tid
                # Refresh user counters
                from database import db_get_user_by_id
                st.session_state.user = db_get_user_by_id(uid) or user
                st.rerun()
            else:
                st.error(f"Translation error: {res['error']}")

    if clear_btn:
        st.session_state.result      = ""
        st.session_state.source_text = ""
        st.session_state.last_trans_id = None
        st.rerun()

    if fav_btn and st.session_state.last_trans_id:
        now_fav = toggle_favorite(st.session_state.last_trans_id, uid)
        st.toast("★ Added to favorites!" if now_fav else "Removed from favorites")

    # Improve / Explain / Rate tabs
    if st.session_state.result:
        st.markdown("---")
        t1,t2,t3 = st.tabs(["Improve","Explain","Rate"])
        with t1:
            fb = st.text_input("What to improve?",
                               placeholder='"Make it more formal" or "Use simpler words"')
            if st.button("Apply", type="secondary") and fb:
                with st.spinner("Improving..."):
                    imp = improve_translation(source, st.session_state.result, direction, fb)
                if imp["success"]:
                    st.session_state.result = imp["translation"]
                    st.rerun()
                else:
                    st.error(imp.get("error","Failed"))
        with t2:
            if st.button("Explain this translation"):
                with st.spinner("Analyzing..."):
                    exp = explain_translation(source, st.session_state.result, direction)
                st.info(exp)
        with t3:
            rating = st.select_slider(
                "Rating", [1,2,3,4,5], 5,
                format_func=lambda x: "★"*x+"☆"*(5-x),
                label_visibility="collapsed"
            )
            if st.button("Submit rating") and st.session_state.last_trans_id:
                rate_translation(st.session_state.last_trans_id, rating)
                st.success(f"Rated {'★'*rating}")

    # Quick examples
    st.markdown("---")
    st.caption("Quick examples:")
    e1,e2,e3,e4 = st.columns(4)
    with e1:
        if st.button("Bangla greeting"):
            st.session_state.source_text="আপনার সাথে পরিচিত হতে পেরে অত্যন্ত আনন্দিত।"
            st.session_state.direction="Bangla → English"
            st.rerun()
    with e2:
        if st.button("Business email"):
            st.session_state.source_text="I am writing to follow up on our proposal. Please find the revised quotation attached."
            st.session_state.direction="English → Bangla"
            st.rerun()
    with e3:
        if st.button("Medical"):
            st.session_state.source_text="রোগীর উচ্চ রক্তচাপ এবং ডায়াবেটিস রয়েছে।"
            st.session_state.direction="Bangla → English"
            st.rerun()
    with e4:
        if st.button("Legal"):
            st.session_state.source_text="This agreement is binding upon both parties and enforceable under Bangladeshi law."
            st.session_state.direction="English → Bangla"
            st.rerun()


# ════════════════════════════════════════════════════════════
#  PAGE — HISTORY
# ════════════════════════════════════════════════════════════

elif page == "📋 History":
    st.markdown("# 📋 Translation History")

    f1,f2,f3 = st.columns([3,2,2])
    with f1:
        recent_s = get_search_history(uid, 5)
        search_q = st.text_input("Search","",placeholder="Search in any language...",
                                  label_visibility="collapsed")
        if recent_s and not search_q:
            st.caption("Recent: " + "  ·  ".join(f'"{s}"' for s in recent_s[:4]))
    with f2:
        lang_f   = st.selectbox("Lang",["All","Bangla → English","English → Bangla"],
                                 label_visibility="collapsed")
    with f3:
        domain_f = st.selectbox("Domain",["All"]+DOMAINS, label_visibility="collapsed")

    records = (search_translations(uid, search_q)
               if search_q
               else get_recent_translations(uid, 100, lang_f, domain_f))

    tc1,tc2,tc3 = st.columns([2,2,2])
    with tc1: st.markdown(f"**{len(records)} records**")
    with tc2:
        if records:
            df_e = pd.DataFrame(records)
            safe = [c for c in ["trans_id","source_lang","target_lang","source_text",
                                 "translated_text","domain","tone","word_count","created_at"]
                    if c in df_e.columns]
            st.download_button("Export CSV", df_e[safe].to_csv(index=False),
                               f"history_{datetime.now().strftime('%Y%m%d')}.csv",
                               "text/csv", use_container_width=True)
    with tc3:
        if st.button("Clear all history", type="secondary"):
            n = delete_all_history(uid)
            st.success(f"Deleted {n} records.")
            st.rerun()

    st.markdown("---")
    if not records:
        st.info("No translations yet. Go to Translate to get started!")
    else:
        for rec in records:
            tid      = rec["trans_id"]
            src_lang = rec.get("source_lang","")
            tgt_lang = rec.get("target_lang","")
            domain_  = rec.get("domain","General")
            is_fav   = rec.get("is_favorite",0)==1
            rating   = rec.get("user_rating")
            created  = (rec.get("created_at") or "")[:16]
            src_prev = (rec.get("source_text") or "")[:70]
            fav_icon = "★" if is_fav else "☆"
            star_str = ("★"*(rating or 0)+"☆"*(5-(rating or 0))) if rating else ""
            with st.expander(f"{fav_icon} [{src_lang}→{tgt_lang}] [{domain_}] {src_prev}..."):
                hc1,hc2 = st.columns(2)
                with hc1:
                    st.markdown(f"**{src_lang}**")
                    st.write(rec.get("source_text",""))
                with hc2:
                    st.markdown(f"**{tgt_lang}**")
                    st.write(rec.get("translated_text",""))
                st.caption(
                    f"Domain: {domain_} | Words: {rec.get('word_count',0)} | {created}"
                    + (f" | {star_str}" if star_str else "")
                )
                ac1,ac2,ac3 = st.columns(3)
                with ac1:
                    if st.button(f"{'Unfav' if is_fav else 'Fav'}",key=f"hfav{tid}"):
                        toggle_favorite(tid, uid); st.rerun()
                with ac2:
                    if st.button("Re-translate",key=f"hret{tid}"):
                        st.session_state.source_text = rec.get("source_text","")
                        st.session_state.direction   = f"{src_lang} → {tgt_lang}"
                        st.session_state.result      = ""
                        st.rerun()
                with ac3:
                    if st.button("Delete",key=f"hdel{tid}"):
                        delete_translation(tid, uid); st.rerun()


# ════════════════════════════════════════════════════════════
#  PAGE — FAVORITES
# ════════════════════════════════════════════════════════════

elif page == "★ Favorites":
    st.markdown("# ★ Favorites")
    folders = get_favorite_folders(uid)
    fold_opts = ["All folders"] + folders
    sel_folder = st.selectbox("Folder", fold_opts, label_visibility="collapsed")
    fp = None if sel_folder == "All folders" else sel_folder
    favs = get_favorites(uid, folder=fp)
    st.markdown(f"**{len(favs)} saved**")
    st.markdown("---")
    if not favs:
        st.info("No favorites yet. Use the ★ Favorite button on the Translate page.")
    else:
        for fav in favs:
            tid      = fav["trans_id"]
            src_lang = fav.get("source_lang","")
            tgt_lang = fav.get("target_lang","")
            domain_  = fav.get("domain","General")
            note     = fav.get("note","") or ""
            folder_  = fav.get("folder","General")
            added    = (fav.get("added_at") or "")[:10]
            src_prev = (fav.get("source_text") or "")[:60]
            with st.expander(f"★ [{src_lang}→{tgt_lang}] [{domain_}] {src_prev}..."):
                fc1,fc2 = st.columns(2)
                with fc1:
                    st.markdown(f"**{src_lang}**")
                    st.write(fav.get("source_text",""))
                with fc2:
                    st.markdown(f"**{tgt_lang}**")
                    st.write(fav.get("translated_text",""))
                if note: st.info(f"Note: {note}")
                st.caption(f"Folder: {folder_} | Saved: {added}")
                nc1,nc2,nc3 = st.columns(3)
                with nc1:
                    new_note = st.text_input("Note",value=note,
                                             key=f"fn{tid}",label_visibility="collapsed",
                                             placeholder="Add a note...")
                    if st.button("Save note",key=f"sn{tid}"):
                        update_favorite_note(tid,uid,new_note); st.toast("Note saved!")
                with nc2:
                    new_fold = st.text_input("Folder",value=folder_,
                                             key=f"ff{tid}",label_visibility="collapsed")
                    if st.button("Move",key=f"mf{tid}"):
                        update_favorite_folder(tid,uid,new_fold); st.toast(f"Moved to {new_fold}")
                with nc3:
                    if st.button("Remove ★",key=f"uf{tid}"):
                        toggle_favorite(tid,uid); st.rerun()


# ════════════════════════════════════════════════════════════
#  PAGE — ANALYTICS
# ════════════════════════════════════════════════════════════

elif page == "📊 Analytics":
    st.markdown("# 📊 Your Analytics")
    summary = get_analytics_summary(uid)
    if summary.get("total",0) == 0:
        st.info("No data yet. Start translating to see your analytics!")
        st.stop()

    m1,m2,m3,m4,m5 = st.columns(5)
    m1.metric("Total",      f"{summary.get('total',0):,}")
    m2.metric("Today",      f"{summary.get('today_count',0)}")
    m3.metric("This week",  f"{summary.get('week_count',0)}")
    m4.metric("Favorites",  f"{summary.get('favorites',0)}")
    m5.metric("Streak",     f"{summary.get('streak',0)} 🔥")
    st.markdown("---")

    import plotly.express as px
    ch1,ch2 = st.columns(2)
    with ch1:
        st.markdown("**Direction**")
        bn = summary.get("bn_to_en",0) or 0
        en = summary.get("en_to_bn",0) or 0
        if bn+en > 0:
            fig = px.pie(values=[bn,en],
                         names=["Bangla→EN","EN→Bangla"],
                         color_discrete_sequence=["#4F46E5","#10B981"],
                         hole=0.45)
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),height=240,showlegend=True)
            st.plotly_chart(fig, use_container_width=True)
    with ch2:
        st.markdown("**By domain**")
        dom_data = get_domain_stats(uid)
        if dom_data:
            df_d = pd.DataFrame(dom_data)
            fig  = px.bar(df_d,x="total",y="domain",orientation="h",
                          color_discrete_sequence=["#4F46E5"])
            fig.update_layout(xaxis_title="Count",yaxis_title="",
                              margin=dict(t=10,b=10,l=10,r=10),height=240)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Activity — last 14 days**")
    daily = get_daily_counts(uid, 14)
    if daily:
        df_day = pd.DataFrame(daily)
        if "label" in df_day.columns and "bn" in df_day.columns:
            fig = px.bar(df_day, x="label", y=["bn","en"],
                         color_discrete_map={"bn":"#4F46E5","en":"#10B981"},
                         barmode="stack",
                         labels={"bn":"Bangla→EN","en":"EN→Bangla","label":""})
            fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),height=230)
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Activity by hour**")
    hourly = get_hourly_heatmap(uid)
    if hourly:
        df_h = pd.DataFrame(hourly)
        all_h = pd.DataFrame({"hour":range(24)})
        df_h  = all_h.merge(df_h,on="hour",how="left").fillna(0)
        df_h["label"] = df_h["hour"].apply(lambda h: f"{h:02d}:00")
        fig = px.bar(df_h,x="label",y="total",color_discrete_sequence=["#8B5CF6"],
                     labels={"label":"Hour","total":"Translations"})
        fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),height=210)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    if st.button("Export all my data (JSON)"):
        data = export_user_data(uid)
        st.download_button(
            "Download my_data.json",
            data=json.dumps(data,indent=2,default=str),
            file_name="my_data.json", mime="application/json"
        )


# ════════════════════════════════════════════════════════════
#  PAGE — PRICING
# ════════════════════════════════════════════════════════════

elif page == "💳 Pricing":
    st.markdown("# 💳 Upgrade to Pro")

    if is_pro:
        st.success("You are already on Pro!")
        sub = get_subscription(uid)
        if sub:
            if sub.get("is_lifetime"):
                st.info("Plan: **Lifetime Pro** — never expires")
            elif sub.get("expires_at"):
                st.info(f"Expires: {sub['expires_at'][:10]}")
        pays = get_user_payments(uid)
        if pays:
            st.markdown("### Payment history")
            df_p = pd.DataFrame(pays)
            safe = [c for c in ["tran_id","plan_key","paid_amt","status","payment_method","created_at"]
                    if c in df_p.columns]
            st.dataframe(df_p[safe],use_container_width=True,hide_index=True)
        st.stop()

    if PORTPOS_SANDBOX:
        st.info("🧪 **Sandbox mode — PortPos** — no real money. Use test credentials below. Register free at sandbox.portpos.com to get your keys.")

    # Coupon input
    st.markdown("#### Have a coupon code?")
    ci1,ci2 = st.columns([3,1])
    with ci1:
        coup_in = st.text_input("Coupon","",placeholder="Enter coupon code...",
                                 label_visibility="collapsed")
    with ci2:
        apply_btn = st.button("Apply",use_container_width=True)
    if apply_btn and coup_in:
        cr = apply_coupon(coup_in, PLANS["yearly"]["amount_bdt"], "yearly")
        if cr["valid"]:
            st.session_state.coupon_data = {"code": coup_in, "result": cr}
            st.success(cr["message"])
        else:
            st.error(cr["message"])
            st.session_state.coupon_data = None

    active_coup = st.session_state.coupon_data

    st.markdown("---")
    st.markdown("#### Choose your plan")

    pc1,pc2,pc3 = st.columns(3)
    for plan_key, col in [("monthly",pc1),("yearly",pc2),("lifetime",pc3)]:
        plan   = PLANS[plan_key]
        orig   = plan["amount_bdt"]
        if active_coup:
            cr    = apply_coupon(active_coup["code"], orig, plan_key)
            final = cr.get("discounted_amount", orig)
            lbl   = cr.get("label","") if cr.get("valid") else ""
        else:
            final, lbl = orig, ""
        is_free    = (final == 0)
        is_popular = plan.get("popular", False)

        with col:
            border = "2px solid #4F46E5" if is_popular else "1.5px solid #E5E7EB"
            bg     = "#F5F3FF"           if is_popular else "white"
            st.markdown(f"""
            <div class="plan-card {'plan-popular' if is_popular else ''}"
                 style="border:{border};background:{bg}">
              {"<div style='font-size:11px;font-weight:700;color:#4F46E5;margin-bottom:8px'>MOST POPULAR</div>" if is_popular else ""}
              <div style="font-size:17px;font-weight:700;color:#1F2937">{plan['name']}</div>
              <div style="font-size:12px;color:#6B7280;margin:4px 0 12px">{plan['desc']}</div>
              {"<div style='font-size:12px;color:#9CA3AF;text-decoration:line-through'>৳"+f"{orig:,}"+"</div>" if lbl else ""}
              <div style="font-size:30px;font-weight:800;color:{'#059669' if is_free else '#4F46E5'}">
                {'FREE' if is_free else format_bdt(final)}
              </div>
              {"<div style='font-size:11px;background:#D1FAE5;color:#065F46;padding:2px 8px;border-radius:8px;display:inline-block;margin-top:4px'>"+lbl+"</div>" if lbl else ""}
            </div>
            """, unsafe_allow_html=True)
            if st.button(
                "Get FREE Access" if is_free else f"Pay {format_bdt(final)}",
                key=f"sel_{plan_key}", type="primary" if is_popular else "secondary",
                use_container_width=True
            ):
                st.session_state.sel_plan = plan_key
                st.session_state.sel_amount = final
                st.session_state.show_pay = True

    st.markdown("---")

    # Payment section
    if st.session_state.show_pay:
        sel_key    = st.session_state.sel_plan
        sel_amount = st.session_state.sel_amount
        sel_plan   = PLANS[sel_key]

        st.markdown(f"### Confirm — {sel_plan['name']}")
        pay1,pay2 = st.columns([2,1])
        with pay1:
            cust_email = st.text_input("Email for receipt", value=email,
                                        placeholder="yourname@gmail.com")
            cust_name  = st.text_input("Your name", value=display)
        with pay2:
            st.markdown(f"""
            <div style='background:#F3F4F6;border-radius:10px;padding:16px;text-align:center'>
              <div style='font-size:12px;color:#6B7280'>You pay</div>
              <div style='font-size:28px;font-weight:800;color:{"#059669" if sel_amount==0 else "#4F46E5"}'>
                {"FREE" if sel_amount==0 else format_bdt(sel_amount)}
              </div>
              <div style='font-size:11px;color:#9CA3AF;margin-top:4px'>{sel_plan["desc"]}</div>
            </div>
            """, unsafe_allow_html=True)

        if sel_amount == 0:
            if st.button("Activate Free Pro", type="primary", use_container_width=True):
                tran_id = f"FREE-{uid}-{uuid.uuid4().hex[:8].upper()}"
                create_payment_record(
                    uid, tran_id, sel_key,
                    PLANS[sel_key]["amount_bdt"], 0,
                    coupon_code=active_coup["code"] if active_coup else None,
                    discount_amt=PLANS[sel_key]["amount_bdt"], is_sandbox=True
                )
                mark_payment_success(tran_id, "Coupon (Free)")
                from database import db_get_user_by_id
                st.session_state.user = db_get_user_by_id(uid)
                is_pro = True
                st.success("🎉 Free Pro activated! Enjoy unlimited translations.")
                st.session_state.show_pay = False
                st.balloons()
                st.rerun()
        else:
            if st.button(
                f"Pay {format_bdt(sel_amount)} via PortPos (bKash · Nagad · DBBL · Visa · Mastercard)",
                type="primary", use_container_width=True
            ):
                with st.spinner("Connecting to payment gateway..."):
                    pay_res = create_payment(
                        user_id=uid, username=display,
                        plan_key=sel_key, amount_bdt=sel_amount,
                        coupon_code=active_coup["code"] if active_coup else None,
                        customer_email=cust_email, customer_name=cust_name
                    )
                if pay_res["success"]:
                    create_payment_record(
                        uid, pay_res["tran_id"], sel_key,
                        PLANS[sel_key]["amount_bdt"], sel_amount,
                        coupon_code=active_coup["code"] if active_coup else None,
                        discount_amt=PLANS[sel_key]["amount_bdt"]-sel_amount,
                        is_sandbox=PORTPOS_SANDBOX
                    )
                    st.success(f"Payment page ready! Txn: **{pay_res['tran_id']}**")
                    st.markdown(f"""
                    <a href="{pay_res['payment_url']}" target="_blank">
                      <button style="width:100%;background:#4F46E5;color:white;border:none;
                        padding:14px;border-radius:10px;font-size:16px;font-weight:600;
                        cursor:pointer;margin-top:8px">
                        Open Payment Page (bKash · Nagad · Card) →
                      </button>
                    </a>
                    """, unsafe_allow_html=True)
                else:
                    st.error(f"Gateway error: {pay_res['error']}")

        if PORTPOS_SANDBOX:
            st.markdown("---")
            st.markdown("#### 🧪 PortPos sandbox test credentials")
            cred_cols = st.columns(len(SANDBOX_TEST_CREDENTIALS))
            for col, (method, creds) in zip(cred_cols, SANDBOX_TEST_CREDENTIALS.items()):
                with col:
                    st.markdown(f"**{method}**")
                    st.code("\n".join(f"{k}: {v}" for k,v in creds.items()))

    # What's included
    st.markdown("---")
    st.markdown("### What Pro includes")
    f1,f2,f3 = st.columns(3)
    with f1:
        st.markdown("**Unlimited translations**\nNo daily or total limits.")
    with f2:
        st.markdown("**All 7 domains**\nMedical, Legal, Business, Academic and more.")
    with f3:
        st.markdown("**Full history + analytics**\nComplete data, charts, export.")

    # Manual bKash
    with st.expander("Pay manually via bKash / Nagad"):
        st.markdown("""
**Send to bKash/Nagad:** 01833052490 (bKash / Nagad)

1. Send the amount to your number
2. Use your username as reference
3. Message us on WhatsApp with your email and transaction ID
4. We activate Pro within a few hours

**Prices: ৳299/month · ৳1,999/year · ৳4,999 lifetime**
        """)
        mp1, mp2 = st.columns(2)
        with mp1:
            manual_txn = st.text_input("Your bKash/Nagad transaction number:",
                                        placeholder="e.g. 8ABC123DEF456")
        with mp2:
            manual_plan = st.selectbox(
                "Plan you paid for",
                ["monthly","yearly","lifetime"],
                format_func=lambda x: {
                    "monthly":  "Monthly — ৳299",
                    "yearly":   "Yearly  — ৳1,999",
                    "lifetime": "Lifetime — ৳4,999"
                }[x]
            )
        if st.button("Submit manual payment", type="primary") and manual_txn.strip():
            plan_amount = PLANS[manual_plan]["amount_bdt"]
            tran_id     = f"MANUAL-{uid}-{manual_txn.strip()[:14].upper()}"
            try:
                create_payment_record(
                    uid, tran_id, manual_plan,
                    plan_amount, plan_amount,
                    is_sandbox=False
                )
                st.success(
                    f"✅ Submitted! Your {PLANS[manual_plan]['name']} payment is under review. "
                    "We activate within a few hours after verification."
                )
                st.info(f"Your reference: **{tran_id}** — save this.")
            except Exception:
                st.info("Already submitted. Please wait for verification.")


# ════════════════════════════════════════════════════════════
#  PAGE — PROFILE
# ════════════════════════════════════════════════════════════

elif page == "👤 Profile":
    st.markdown("# 👤 Profile")
    p1,p2 = st.columns([1,2])
    with p1:
        initials2 = "".join(w[0].upper() for w in display.split()[:2])
        st.markdown(f"""
        <div style='width:80px;height:80px;border-radius:50%;background:{color};
             display:flex;align-items:center;justify-content:center;
             color:white;font-weight:700;font-size:28px;margin-bottom:12px'>
          {initials2}
        </div>
        """, unsafe_allow_html=True)
        st.markdown(f"**{display}**")
        st.caption(f"{email or 'No email'}")
        st.caption(f"Joined: {(user.get('created_at') or '')[:10]}")
        if is_pro:
            st.markdown('<span class="badge badge-pro">★ Pro</span>', unsafe_allow_html=True)
        else:
            st.markdown('<span class="badge badge-free">Free</span>', unsafe_allow_html=True)
    with p2:
        st.markdown("### Edit profile")
        with st.form("profile_form"):
            new_name = st.text_input("Display name", value=display)
            new_email= st.text_input("Email address", value=email or "",
                                      placeholder="yourname@gmail.com")
            color_opts = {"Indigo":"#4F46E5","Emerald":"#10B981","Amber":"#F59E0B",
                          "Rose":"#F43F5E","Purple":"#8B5CF6","Sky":"#0EA5E9"}
            cur_name = next((k for k,v in color_opts.items() if v==color), "Indigo")
            new_color= st.selectbox("Avatar color", list(color_opts.keys()),
                                     index=list(color_opts.keys()).index(cur_name))
            save_p   = st.form_submit_button("Save changes", type="primary")
        if save_p:
            if new_name.strip():
                db_update_user_field(uid, "display_name", new_name.strip())
            if new_email.strip():
                from auth import validate_email as _ve
                ok, err = _ve(new_email)
                if ok:
                    db_update_user_field(uid, "email", new_email.strip().lower())
                else:
                    st.error(err)
                    st.stop()
            db_update_user_field(uid, "avatar_color", color_opts[new_color])
            from database import db_get_user_by_id
            st.session_state.user = db_get_user_by_id(uid)
            st.success("Profile saved!")
            st.rerun()

    st.markdown("---")
    st.markdown("### Change password")
    with st.form("pwd_form"):
        old_pwd  = st.text_input("Current password", type="password")
        new_pwd1 = st.text_input("New password",     type="password")
        new_pwd2 = st.text_input("Confirm new",      type="password")
        save_pwd = st.form_submit_button("Update password")
    if save_pwd:
        from auth import verify_password as _vp, hash_password as _hp, validate_password as _vpw
        if not _vp(old_pwd, user["password_hash"]):
            st.error("Current password is wrong.")
        elif new_pwd1 != new_pwd2:
            st.error("New passwords don't match.")
        else:
            ok, err = _vpw(new_pwd1)
            if not ok:
                st.error(err)
            else:
                from database import db_update_password
                db_update_password(email, _hp(new_pwd1))
                st.success("Password updated!")

    st.markdown("---")
    st.markdown("### Data management")
    dm1,dm2,dm3 = st.columns(3)
    with dm1:
        data = export_user_data(uid)
        st.download_button("Export my data (JSON)",
                            json.dumps(data,indent=2,default=str),
                            "my_data.json","application/json",
                            use_container_width=True)
    with dm2:
        if st.button("Clear search history", use_container_width=True):
            clear_search_history(uid); st.success("Done!")
    with dm3:
        if st.button("Delete all history", type="secondary", use_container_width=True):
            n = delete_all_history(uid)
            st.warning(f"Deleted {n} translations.")


# ════════════════════════════════════════════════════════════
#  PAGE — TERMS OF SERVICE
# ════════════════════════════════════════════════════════════

elif page == "📜 Terms":
    st.markdown("# 📜 Terms of Service")
    st.markdown(f"*Last updated: {datetime.now().strftime('%B %Y')}*")
    st.markdown(f"""
### 1. Acceptance
By using {APP_NAME}, you agree to these terms. If you don't agree, please don't use the service.

### 2. Service description
{APP_NAME} provides AI-powered translation between Bangla and English. We use Groq AI models to generate translations.

### 3. Free and Pro accounts
Free accounts receive {FREE_TRANSLATIONS_PER_DAY} translations per day up to {FREE_TRANSLATIONS_TOTAL} total.
Pro accounts receive unlimited translations during their active subscription period.

### 4. Payments and refunds
Payments are processed securely via PortPos (Bangladesh Bank licensed payment gateway). We offer a 48-hour refund policy for technical issues.
Contact us at support@yourdomain.com for refund requests.

### 5. User responsibilities
You must not use this service to translate illegal, harmful, or offensive content.
You are responsible for the accuracy of translations used in critical contexts (medical, legal decisions).

### 6. Data and privacy
We collect email, translation history, and usage data to provide the service. See our Privacy Policy for details.
You can export or delete your data at any time from the Profile page.

### 7. Limitation of liability
Translations are AI-generated and may contain errors. Do not rely solely on our translations for critical decisions.
We are not liable for damages arising from incorrect translations.

### 8. Changes to terms
We may update these terms at any time. Continued use of the service means you accept the new terms.

### 9. Contact
For questions about these terms, contact: support@yourdomain.com
    """)


# ════════════════════════════════════════════════════════════
#  PAGE — PRIVACY POLICY
# ════════════════════════════════════════════════════════════

elif page == "🔒 Privacy":
    st.markdown("# 🔒 Privacy Policy")
    st.markdown(f"*Last updated: {datetime.now().strftime('%B %Y')}*")
    st.markdown("""
### 1. What data we collect
- **Account data:** Email address, display name, avatar color
- **Usage data:** Translations you make, favorites, search history
- **Payment data:** Transaction IDs, plan purchased (we never store card details — PortPos handles that)
- **Technical data:** Login timestamps, session tokens

### 2. How we use your data
- To provide the translation service
- To save your history and favorites
- To process your payments
- To send important account emails (payment confirmation, password reset)
- To improve the service through usage analytics

### 3. Data storage
Your data is stored in a secure SQLite database on our server. Translation text is stored to enable your history feature.

### 4. Data sharing
We do not sell your data. We do not share your data with third parties except:
- PortPos (payment processing, Bangladesh Bank licensed) — they receive your name, email for payment
- Groq AI (translation) — your text is sent to Groq for translation (see groq.com/privacy)

### 5. Your rights
- **Export:** Download all your data from Profile → Export my data
- **Delete:** Delete your translation history from Profile → Delete all history
- **Account deletion:** Email us at support@yourdomain.com to delete your account completely

### 6. Cookies and sessions
We use secure session tokens stored in your browser to keep you logged in. No tracking cookies.

### 7. Children's privacy
This service is not intended for children under 13. We do not knowingly collect data from children.

### 8. Bangladesh law
This service operates under the laws of Bangladesh. Any disputes are subject to Bangladeshi jurisdiction.

### 9. Contact
For privacy questions: support@yourdomain.com
    """)


# ════════════════════════════════════════════════════════════
#  PAGE — ADMIN PANEL  (admin only)
# ════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════
#  PAGE — ADMIN PANEL
#  Access: only users with is_admin=1 in the database
#  How to become admin: see ADMIN SETUP section below
#
#  ADMIN SETUP (first time only):
#  1. Register a normal account in the app
#  2. Open your .env and find ADMIN_PASSWORD
#  3. On the Admin page, enter that password to unlock
#  4. Go to Manual Upgrade tab → enter your own email
#  5. Click "Make Admin" — now you have permanent admin access
# ════════════════════════════════════════════════════════════

elif page == "⚙️ Admin":

    if not is_admin:
        st.error("Access denied. Admin accounts only.")
        st.stop()

    # ── Password gate (extra security layer) ─────────────────
    if not st.session_state.admin_ok:
        _, center, _ = st.columns([1,2,1])
        with center:
            st.markdown("## 🔐 Admin Login")
            st.caption("Enter your admin password to unlock the panel.")
            pwd = st.text_input(
                "Admin password", type="password",
                placeholder="Enter admin password...",
                label_visibility="collapsed"
            )
            if st.button("Unlock Admin Panel", type="primary", use_container_width=True):
                from config import ADMIN_PASSWORD as _AP
                if pwd == _AP:
                    st.session_state.admin_ok = True
                    st.rerun()
                else:
                    st.error("Wrong password.")
        st.stop()

    # ── Admin header ──────────────────────────────────────────
    col_h1, col_h2 = st.columns([3,1])
    with col_h1:
        st.markdown(f"# ⚙️ Admin Panel")
        st.caption(f"Logged in as: {display} | {email}")
    with col_h2:
        if st.button("🔒 Lock Panel", use_container_width=True):
            st.session_state.admin_ok = False
            st.rerun()

    # ── Quick summary metrics ─────────────────────────────────
    all_users_q = db_get_all_users()
    pay_stats   = get_payment_stats()
    pending_pays = [p for p in get_all_payments(500) if p.get("status") == "PENDING"]

    qs1,qs2,qs3,qs4,qs5 = st.columns(5)
    qs1.metric("Total users",      len(all_users_q))
    qs2.metric("Pro users",        sum(1 for u in all_users_q if u.get("is_pro")))
    qs3.metric("Total revenue",    f"৳{int(pay_stats.get('live_revenue',0)):,}")
    qs4.metric("Today's sales",    pay_stats.get("today_sales",0))
    qs5.metric("Pending payments", len(pending_pays),
               delta=f"{len(pending_pays)} need review" if pending_pays else None,
               delta_color="off")

    if pending_pays:
        st.warning(
            f"⚠️ **{len(pending_pays)} pending payment(s) need your review.** "
            "Go to **Pending Payments** tab to approve or reject them."
        )

    st.markdown("---")

    # ── 6 tabs ────────────────────────────────────────────────
    tab_pending, tab_rev, tab_coup, tab_users, tab_emails, tab_manual = st.tabs([
        f"⏳ Pending ({len(pending_pays)})",
        "💰 Revenue",
        "🎫 Coupons",
        "👥 Users",
        "📧 Emails",
        "🔧 Manual Upgrade",
    ])


    # ════════════════════════════════════════════════════════
    #  TAB 1 — PENDING PAYMENTS
    #  This is where you acknowledge manual bKash/Nagad payments
    # ════════════════════════════════════════════════════════
    with tab_pending:
        st.markdown("### ⏳ Pending payments — needs your action")
        st.markdown(
            "When a user pays manually via bKash/Nagad and submits their "
            "transaction number, it appears here as **PENDING**. "
            "You verify it and click **Mark as PAID** to give them Pro access."
        )

        if not pending_pays:
            st.success("✅ No pending payments — all clear!")
        else:
            for pay in pending_pays:
                pay_uid   = pay.get("user_id")
                tran      = pay.get("tran_id","")
                plan_k    = pay.get("plan_key","monthly")
                paid_amt  = pay.get("paid_amt", 0)
                orig_amt  = pay.get("original_amt", 0)
                created   = (pay.get("created_at") or "")[:16]
                is_manual = tran.startswith("MANUAL")

                # Load user details for this payment
                from database import db_get_user_by_id as _uid2user
                pay_user = _uid2user(pay_uid) or {}
                pay_email = pay.get("email") or pay_user.get("email","unknown")
                pay_name  = pay.get("display_name") or pay_user.get("display_name","unknown")

                card_color = "#FEF3C7" if is_manual else "#EFF6FF"
                card_border = "#F59E0B" if is_manual else "#3B82F6"
                method_label = "Manual bKash/Nagad" if is_manual else "PortPos"

                st.markdown(f"""
                <div style="background:{card_color};border:1.5px solid {card_border};
                     border-radius:12px;padding:16px;margin-bottom:12px">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start">
                    <div>
                      <span style="font-weight:700;font-size:15px">{pay_name}</span>
                      <span style="color:#6B7280;font-size:13px;margin-left:8px">{pay_email}</span>
                    </div>
                    <span style="background:#FDE68A;color:#92400E;font-size:11px;
                          padding:3px 10px;border-radius:10px;font-weight:600">
                      {method_label}
                    </span>
                  </div>
                  <div style="margin-top:8px;font-size:13px;color:#374151;line-height:2">
                    Plan: <b>{PLANS.get(plan_k,{}).get('name',plan_k)}</b> &nbsp;|&nbsp;
                    Amount: <b>৳{int(paid_amt):,}</b> &nbsp;|&nbsp;
                    Txn ID: <code>{tran}</code> &nbsp;|&nbsp;
                    Date: <b>{created}</b>
                  </div>
                </div>
                """, unsafe_allow_html=True)

                pa1, pa2, pa3 = st.columns([2,2,2])
                with pa1:
                    if st.button(
                        f"✅ Mark PAID — give {PLANS.get(plan_k,{}).get('name',plan_k)}",
                        key=f"pay_ok_{tran}",
                        type="primary",
                        use_container_width=True
                    ):
                        mark_payment_success(tran, "Manual bKash/Nagad")
                        # Send confirmation email
                        if pay_email and "@" in pay_email:
                            try:
                                from email_service import send_payment_confirmation
                                send_payment_confirmation(
                                    pay_email, pay_name,
                                    PLANS.get(plan_k,{}).get("name","Pro"),
                                    paid_amt, tran,
                                    "Manual bKash/Nagad"
                                )
                                st.success(
                                    f"✅ {pay_name} upgraded to Pro! "
                                    f"Confirmation email sent to {pay_email}."
                                )
                            except Exception:
                                st.success(f"✅ {pay_name} upgraded to Pro!")
                        else:
                            st.success(f"✅ {pay_name} upgraded to Pro!")
                        st.rerun()

                with pa2:
                    if st.button(
                        f"❌ Reject payment",
                        key=f"pay_no_{tran}",
                        type="secondary",
                        use_container_width=True
                    ):
                        mark_payment_failed(tran, "Rejected by admin")
                        st.warning(f"Payment {tran} rejected.")
                        st.rerun()

                with pa3:
                    # Change plan before approving
                    new_plan = st.selectbox(
                        "Change plan",
                        ["monthly","yearly","lifetime"],
                        index=["monthly","yearly","lifetime"].index(plan_k)
                              if plan_k in ["monthly","yearly","lifetime"] else 0,
                        key=f"plan_sel_{tran}",
                        label_visibility="collapsed"
                    )
                    if new_plan != plan_k:
                        from database import get_db as _gdb2
                        with _gdb2() as c:
                            c.execute(
                                "UPDATE payments SET plan_key=?, paid_amt=? WHERE tran_id=?",
                                (new_plan, PLANS[new_plan]["amount_bdt"], tran)
                            )
                        st.info(f"Plan changed to {PLANS[new_plan]['name']}")
                        st.rerun()

                st.markdown("---")

        # ── How to verify a bKash payment ────────────────────
        with st.expander("How to verify a bKash / Nagad payment manually"):
            st.markdown("""
**Step 1 — Check your bKash/Nagad app**
Open your bKash or Nagad mobile app → go to Transaction History →
confirm you received the correct amount from the user.

**Step 2 — Match the transaction ID**
The user submits their transaction ID. Compare it with the ID in
your bKash/Nagad app. If it matches → click **Mark as PAID**.

**Step 3 — Verify the amount matches the plan**
- Monthly: ৳299
- Yearly: ৳1,999
- Lifetime: ৳4,999

If the amount is less, use **Change Plan** to assign the correct plan
before approving.

**Step 4 — Mark as PAID**
Click the green button. The user instantly becomes Pro and
receives an email confirmation automatically.
            """)


    # ════════════════════════════════════════════════════════
    #  TAB 2 — REVENUE DASHBOARD
    # ════════════════════════════════════════════════════════
    with tab_rev:
        st.markdown("### 💰 Revenue dashboard")

        r1,r2,r3,r4 = st.columns(4)
        r1.metric("Total successful",  pay_stats.get("successful",0))
        r2.metric("Today's sales",     pay_stats.get("today_sales",0))
        r3.metric("Live revenue",      f"৳{int(pay_stats.get('live_revenue',0)):,}")
        r4.metric("Today's revenue",   f"৳{int(pay_stats.get('today_revenue',0)):,}")

        st.markdown("")
        r5,r6,r7,r8 = st.columns(4)
        r5.metric("All-time (BDT)",    f"৳{int(pay_stats.get('total_revenue',0)):,}")
        r6.metric("Pending",           pay_stats.get("pending",0))
        r7.metric("Failed/Rejected",   pay_stats.get("failed",0))
        r8.metric("Total attempts",    pay_stats.get("total_attempts",0))

        if PORTPOS_SANDBOX:
            st.warning(
                "PortPos **Sandbox mode** ON — payments are test only, not real money. "
                "Set PORTPOS_SANDBOX=false in .env to go live."
            )

        st.markdown("---")

        all_pays_rev = get_all_payments(500)
        if not all_pays_rev:
            st.info("No payments yet.")
        else:
            import plotly.express as px

            # Status filter
            status_f = st.selectbox(
                "Filter by status",
                ["All","PAID","PENDING","FAILED"],
                label_visibility="collapsed"
            )
            filtered_pays = (
                all_pays_rev if status_f == "All"
                else [p for p in all_pays_rev if p.get("status") == status_f]
            )

            df_rev = pd.DataFrame(filtered_pays)
            if not df_rev.empty:
                show_r = [c for c in [
                    "tran_id","display_name","email","plan_key",
                    "paid_amt","coupon_code","status","payment_method",
                    "is_sandbox","created_at"
                ] if c in df_rev.columns]

                def _style_status(val):
                    return {
                        "PAID":    "background:#D1FAE5;color:#065F46",
                        "FAILED":  "background:#FEE2E2;color:#991B1B",
                        "PENDING": "background:#FEF3C7;color:#92400E",
                    }.get(val,"")

                df_show = df_rev[show_r].copy()
                if "status" in df_show.columns:
                    styled = df_show.style.applymap(_style_status, subset=["status"])
                    st.dataframe(styled, use_container_width=True, hide_index=True)
                else:
                    st.dataframe(df_show, use_container_width=True, hide_index=True)

                sc1, sc2 = st.columns(2)
                with sc1:
                    st.download_button(
                        "Export all payments CSV",
                        data=df_show.to_csv(index=False),
                        file_name=f"payments_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime="text/csv", use_container_width=True
                    )

                # Revenue by plan chart
                st.markdown("**Revenue by plan**")
                paid_df = df_rev[df_rev.get("status","") == "PAID"] if "status" in df_rev.columns else pd.DataFrame()
                if not paid_df.empty and "plan_key" in paid_df.columns and "paid_amt" in paid_df.columns:
                    plan_rev = paid_df.groupby("plan_key")["paid_amt"].sum().reset_index()
                    fig = px.bar(plan_rev, x="plan_key", y="paid_amt",
                                 color_discrete_sequence=["#4F46E5"],
                                 labels={"plan_key":"Plan","paid_amt":"Revenue (৳)"})
                    fig.update_layout(margin=dict(t=10,b=10,l=10,r=10),height=220)
                    st.plotly_chart(fig, use_container_width=True)


    # ════════════════════════════════════════════════════════
    #  TAB 3 — COUPONS
    # ════════════════════════════════════════════════════════
    with tab_coup:
        st.markdown("### 🎫 Coupon codes")
        st.caption(
            "Coupons give buyers a discount. Share the code in social media, "
            "Eid offers, or directly to specific buyers."
        )

        with st.form("coup_form", clear_on_submit=True):
            cf1,cf2 = st.columns(2)
            with cf1:
                c_code = st.text_input("Coupon code", placeholder="e.g. EID50 or FREEPRO")
                c_type = st.selectbox(
                    "Discount type",
                    ["percent","fixed","free"],
                    format_func=lambda x:{
                        "percent":"% Percentage off",
                        "fixed":  "৳ Fixed amount off",
                        "free":   "100% Free access"
                    }[x]
                )
            with cf2:
                c_val  = st.number_input("Value (ignored for Free)", min_value=0.0, max_value=10000.0, value=20.0)
                c_max  = st.number_input("Max uses (0 = unlimited)", min_value=0, value=0)
            cf3,cf4 = st.columns(2)
            with cf3:
                c_days = st.number_input("Expires in days (0 = never)", min_value=0, value=30)
            with cf4:
                c_plan = st.selectbox(
                    "Restrict to plan",
                    ["(any plan)","monthly","yearly","lifetime"]
                )
            c_desc = st.text_input("Your note", placeholder="Eid 2025 offer — 50% off")
            c_sub  = st.form_submit_button("Create coupon", type="primary")

        if c_sub:
            if not c_code.strip():
                st.error("Please enter a code.")
            else:
                res = create_coupon(
                    code=c_code.strip().upper(),
                    discount_type=c_type,
                    discount_value=c_val if c_type != "free" else 100,
                    description=c_desc,
                    max_uses=int(c_max) if c_max > 0 else None,
                    plan_restrict=c_plan if c_plan != "(any plan)" else None,
                    expires_days=int(c_days) if c_days > 0 else None,
                    created_by=uid
                )
                if res["success"]:
                    st.success(f"✅ Created: **{res['code']}** — share this with buyers!")
                else:
                    st.error(res.get("error","Failed"))

        st.markdown("**Quick create:**")
        q1,q2,q3,q4 = st.columns(4)
        with q1:
            if st.button("20% off any",use_container_width=True):
                create_coupon("SAVE20","percent",20,"20% off",created_by=uid)
                st.toast("Created: SAVE20")
        with q2:
            if st.button("50% Yearly",use_container_width=True):
                create_coupon("HALF50","percent",50,"50% yearly",plan_restrict="yearly",created_by=uid)
                st.toast("Created: HALF50")
        with q3:
            if st.button("৳500 off",use_container_width=True):
                create_coupon("BD500","fixed",500,"৳500 off lifetime",plan_restrict="lifetime",created_by=uid)
                st.toast("Created: BD500")
        with q4:
            if st.button("Free (influencer)",use_container_width=True):
                import random,string
                code = "FREE"+"".join(random.choices(string.ascii_uppercase+string.digits,k=5))
                create_coupon(code,"free",100,"Free 1-use",max_uses=1,created_by=uid)
                st.toast(f"Created: {code}")

        st.markdown("---")
        all_c = get_all_coupons()
        if all_c:
            df_c = pd.DataFrame(all_c)
            def _fmt_disc(row):
                t,v = row.get("discount_type",""),row.get("discount_value",0)
                if t=="percent": return f"{int(v)}% off"
                if t=="fixed":   return f"৳{int(v)} off"
                return "100% FREE"
            df_c["Discount"] = df_c.apply(_fmt_disc,axis=1)
            df_c["Status"]   = df_c["is_active"].apply(lambda x:"✅ Active" if x else "❌ Off")
            show_c = [c for c in ["code","Discount","description","max_uses","used_count","Status","expires_at"]
                      if c in df_c.columns]
            st.dataframe(df_c[show_c], use_container_width=True, hide_index=True)

            kc1,kc2 = st.columns([3,1])
            with kc1:
                kill_c = st.text_input("Deactivate code",placeholder="CODE123",
                                        label_visibility="collapsed")
            with kc2:
                if st.button("Deactivate",type="secondary",use_container_width=True) and kill_c.strip():
                    deactivate_coupon(kill_c.strip())
                    st.success(f"{kill_c.upper()} deactivated")
                    st.rerun()


    # ════════════════════════════════════════════════════════
    #  TAB 4 — ALL USERS
    # ════════════════════════════════════════════════════════
    with tab_users:
        st.markdown("### 👥 All users")

        all_u = db_get_all_users()
        um1,um2,um3,um4 = st.columns(4)
        um1.metric("Total",     len(all_u))
        um2.metric("Pro",       sum(1 for u in all_u if u.get("is_pro")))
        um3.metric("Free",      sum(1 for u in all_u if not u.get("is_pro")))
        um4.metric("Admins",    sum(1 for u in all_u if u.get("is_admin")))

        if all_u:
            df_u = pd.DataFrame(all_u)
            df_u["Plan"]  = df_u["is_pro"].apply(lambda x:"★ Pro" if x else "Free")
            df_u["Admin"] = df_u.get("is_admin",pd.Series([0]*len(df_u))).apply(lambda x:"✅" if x else "")
            show_u = [c for c in ["email","display_name","Plan","Admin",
                                   "total_count","created_at","last_active"]
                      if c in df_u.columns]
            st.dataframe(df_u[show_u], use_container_width=True, hide_index=True)
            st.download_button(
                "Export users CSV",
                data=df_u[show_u].to_csv(index=False),
                file_name=f"users_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


    # ════════════════════════════════════════════════════════
    #  TAB 5 — EMAIL LIST
    # ════════════════════════════════════════════════════════
    with tab_emails:
        st.markdown("### 📧 User emails")
        st.caption("All users who added their email on the Profile page. Use for newsletters and upgrade offers.")

        email_list = get_all_emails_for_admin()
        if not email_list:
            st.info("No emails yet. Encourage users to add their email on the Profile page.")
        else:
            pro_em  = [e for e in email_list if e.get("is_pro")]
            free_em = [e for e in email_list if not e.get("is_pro")]

            em1,em2,em3 = st.columns(3)
            em1.metric("Total emails",  len(email_list))
            em2.metric("Pro users",     len(pro_em))
            em3.metric("Free users",    len(free_em), help="These are upgrade prospects!")

            df_em = pd.DataFrame(email_list)
            df_em["Plan"] = df_em["is_pro"].apply(lambda x:"★ Pro" if x else "Free")
            show_em = [c for c in ["email","display_name","Plan","total_count","created_at"]
                       if c in df_em.columns]
            st.dataframe(df_em[show_em], use_container_width=True, hide_index=True)

            plain = "\n".join(
                f"{r.get('display_name','')},{r.get('email','')}"
                for r in email_list if r.get("email")
            )
            ee1,ee2 = st.columns(2)
            with ee1:
                st.download_button(
                    "Export full CSV",
                    data=df_em[show_em].to_csv(index=False),
                    file_name=f"emails_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv", use_container_width=True
                )
            with ee2:
                st.download_button(
                    "Export Name, Email (for Mailchimp)",
                    data=plain,
                    file_name="email_list.txt",
                    mime="text/plain", use_container_width=True
                )


    # ════════════════════════════════════════════════════════
    #  TAB 6 — MANUAL UPGRADE
    # ════════════════════════════════════════════════════════
    with tab_manual:
        st.markdown("### 🔧 Manual user management")

        st.markdown("#### Find a user")
        tgt_email = st.text_input(
            "User email",
            placeholder="Enter the user's email address exactly",
            help="The user must be registered in the app first."
        )

        if tgt_email.strip():
            from database import db_get_user_by_email as _gube2
            tgt_user = _gube2(tgt_email.strip().lower())

            if not tgt_user:
                st.error(f"No user found with email: **{tgt_email}**")
                st.info("Ask the user to register first at your app URL.")
            else:
                # User info card
                tu_plan = "★ Pro" if tgt_user.get("is_pro") else "Free"
                tu_sub  = get_subscription(tgt_user["user_id"])
                tu_exp  = ""
                if tu_sub and tu_sub.get("expires_at"):
                    tu_exp = f" (expires {tu_sub['expires_at'][:10]})"
                elif tu_sub and tu_sub.get("is_lifetime"):
                    tu_exp = " (lifetime)"

                st.success(f"""
**User found:**
- Name: {tgt_user.get('display_name','')}
- Email: {tgt_user.get('email','')}
- Current plan: {tu_plan}{tu_exp}
- Total translations: {tgt_user.get('total_count',0):,}
- Joined: {(tgt_user.get('created_at') or '')[:10]}
                """)

                st.markdown("#### Actions")
                ac1,ac2 = st.columns(2)
                with ac1:
                    plan_to_give = st.selectbox(
                        "Plan to assign",
                        ["monthly","yearly","lifetime"],
                        format_func=lambda x: {
                            "monthly":  "Pro Monthly (30 days) — ৳299",
                            "yearly":   "Pro Yearly (365 days) — ৳1,999",
                            "lifetime": "Lifetime Pro (forever) — ৳4,999"
                        }[x]
                    )
                with ac2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button(
                        f"✅ Upgrade to {PLANS[plan_to_give]['name']}",
                        type="primary", use_container_width=True
                    ):
                        upgrade_to_pro(tgt_user["user_id"], plan_to_give)
                        # Send email notification
                        u_email = tgt_user.get("email","")
                        if u_email:
                            try:
                                from email_service import send_payment_confirmation
                                p = PLANS[plan_to_give]
                                send_payment_confirmation(
                                    u_email, tgt_user["display_name"],
                                    p["name"], p["amount_bdt"],
                                    f"MANUAL-{tgt_user['user_id']}-{datetime.now().strftime('%Y%m%d')}",
                                    "Manual bKash/Nagad"
                                )
                                st.success(
                                    f"✅ **{tgt_user['display_name']}** upgraded to "
                                    f"**{PLANS[plan_to_give]['name']}**! "
                                    f"Confirmation email sent to {u_email}."
                                )
                            except Exception:
                                st.success(
                                    f"✅ **{tgt_user['display_name']}** upgraded to "
                                    f"**{PLANS[plan_to_give]['name']}**!"
                                )
                        else:
                            st.success(
                                f"✅ **{tgt_user['display_name']}** upgraded! "
                                "No email on file — user will see Pro on next login."
                            )
                        st.rerun()

                st.markdown("")
                da1,da2,da3 = st.columns(3)
                with da1:
                    if st.button("⬇️ Downgrade to Free", type="secondary", use_container_width=True):
                        downgrade_to_free(tgt_user["user_id"])
                        st.warning(f"{tgt_user['display_name']} downgraded to Free.")
                        st.rerun()
                with da2:
                    if st.button("🔑 Make Admin", use_container_width=True):
                        from database import get_db as _gdb3
                        with _gdb3() as c:
                            c.execute(
                                "UPDATE users SET is_admin=1 WHERE user_id=?",
                                (tgt_user["user_id"],)
                            )
                        st.success(
                            f"✅ {tgt_user['display_name']} is now admin. "
                            "They can access ⚙️ Admin panel after re-login."
                        )
                with da3:
                    if st.button("🗑️ Reset free counter", use_container_width=True):
                        from database import get_db as _gdb4
                        with _gdb4() as c:
                            c.execute(
                                "UPDATE users SET daily_count=0 WHERE user_id=?",
                                (tgt_user["user_id"],)
                            )
                        st.success("Free counter reset — user gets 5 more translations today.")

                # Payment history for this user
                st.markdown("---")
                st.markdown("**Payment history for this user:**")
                u_pays = get_user_payments(tgt_user["user_id"])
                if u_pays:
                    df_up = pd.DataFrame(u_pays)
                    show_up = [c for c in ["tran_id","plan_key","paid_amt","status","payment_method","created_at"]
                               if c in df_up.columns]
                    st.dataframe(df_up[show_up], use_container_width=True, hide_index=True)
                else:
                    st.caption("No payments on record for this user.")

        st.markdown("---")
        st.markdown("#### 📱 Manual bKash/Nagad flow (step by step)")
        st.info("""
**How it works end-to-end:**

**Buyer side:**
1. Buyer opens your app → goes to 💳 Pricing
2. Scrolls down → clicks "Pay manually via bKash / Nagad"
3. Sends ৳299/৳1,999/৳4,999 to your bKash number **01833052490**
4. Enters their bKash transaction ID in the form → clicks Submit
5. Sees: "Submitted! We will verify within a few hours"

**Your side (admin):**
1. You get the notification in your bKash app
2. Open your app → ⚙️ Admin → ⏳ Pending tab
3. See the user's name, email, transaction ID, and plan
4. Open bKash app → verify you received that amount
5. Click **Mark as PAID** → user instantly gets Pro access
6. Confirmation email is sent to user automatically

**Total time: 2 minutes on your end.**
        """)
