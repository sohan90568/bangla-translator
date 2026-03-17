# ============================================================
#  database.py  —  Production SQLite Database Layer
#  Complete rewrite — clean, fast, production-ready.
#
#  Tables (12):
#    users, sessions, login_attempts, otp_codes
#    translations, favorites, search_history
#    user_settings, daily_stats, payments, coupons, subscriptions
#
#  DEPLOYMENT NOTE:
#  SQLite works perfectly for local use and Railway.app (persistent disk).
#  For Streamlit Cloud free tier, data resets on container restart.
#  Recommended: Deploy on Railway.app for persistent storage.
# ============================================================

import sqlite3
import os
from datetime import datetime, timedelta
from contextlib import contextmanager
from config import DB_PATH, FREE_TRANSLATIONS_PER_DAY, FREE_TRANSLATIONS_TOTAL, PLANS


# ── Ensure data directory exists ─────────────────────────────
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


@contextmanager
def get_db():
    """Thread-safe database connection context manager."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory   = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ════════════════════════════════════════════════════════════
#  SCHEMA
# ════════════════════════════════════════════════════════════

def init_db():
    """Create all tables and indexes. Safe to call every startup."""
    with get_db() as c:
        # ── Auth tables ──────────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                email          TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                password_hash  TEXT    NOT NULL,
                display_name   TEXT    NOT NULL,
                avatar_color   TEXT    DEFAULT '#4F46E5',
                is_pro         INTEGER DEFAULT 0,
                is_admin       INTEGER DEFAULT 0,
                is_verified    INTEGER DEFAULT 0,
                daily_count    INTEGER DEFAULT 0,
                daily_reset    TEXT    DEFAULT (date('now','localtime')),
                total_count    INTEGER DEFAULT 0,
                preferred_lang   TEXT  DEFAULT 'Bangla → English',
                preferred_domain TEXT  DEFAULT 'General',
                preferred_tone   TEXT  DEFAULT 'Formal',
                locked_until   TEXT,
                created_at     TEXT    DEFAULT (datetime('now','localtime')),
                last_active    TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                token       TEXT    NOT NULL UNIQUE,
                expires_at  TEXT    NOT NULL,
                created_at  TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                attempt_id  INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL COLLATE NOCASE,
                success     INTEGER DEFAULT 0,
                attempted_at TEXT   DEFAULT (datetime('now','localtime'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS otp_codes (
                otp_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                email       TEXT    NOT NULL COLLATE NOCASE,
                otp         TEXT    NOT NULL,
                expires_at  TEXT    NOT NULL,
                used        INTEGER DEFAULT 0,
                created_at  TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        # ── Translation tables ───────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS translations (
                trans_id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id         INTEGER NOT NULL,
                source_lang     TEXT    NOT NULL,
                target_lang     TEXT    NOT NULL,
                source_text     TEXT    NOT NULL,
                translated_text TEXT    NOT NULL,
                domain          TEXT    DEFAULT 'General',
                tone            TEXT    DEFAULT 'Formal',
                word_count      INTEGER DEFAULT 0,
                char_count      INTEGER DEFAULT 0,
                is_favorite     INTEGER DEFAULT 0,
                user_rating     INTEGER,
                tokens_used     INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                fav_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                trans_id  INTEGER NOT NULL UNIQUE,
                user_id   INTEGER NOT NULL,
                note      TEXT,
                folder    TEXT    DEFAULT 'General',
                added_at  TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (trans_id) REFERENCES translations(trans_id),
                FOREIGN KEY (user_id)  REFERENCES users(user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                search_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                query        TEXT    NOT NULL,
                result_count INTEGER DEFAULT 0,
                searched_at  TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                key        TEXT    NOT NULL,
                value      TEXT,
                updated_at TEXT    DEFAULT (datetime('now','localtime')),
                UNIQUE(user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                stat_id    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                stat_date  TEXT    NOT NULL,
                direction  TEXT    NOT NULL,
                domain     TEXT,
                count      INTEGER DEFAULT 1,
                total_chars INTEGER DEFAULT 0,
                UNIQUE(user_id, stat_date, direction, domain)
            )
        """)
        # ── Payment tables ───────────────────────────────────
        c.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_id     INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id        INTEGER NOT NULL,
                tran_id        TEXT    NOT NULL UNIQUE,
                plan_key       TEXT    NOT NULL,
                original_amt   REAL    DEFAULT 0,
                paid_amt       REAL    DEFAULT 0,
                coupon_code    TEXT,
                discount_amt   REAL    DEFAULT 0,
                payment_method TEXT,
                status         TEXT    DEFAULT 'PENDING',
                is_sandbox     INTEGER DEFAULT 1,
                notes          TEXT,
                created_at     TEXT    DEFAULT (datetime('now','localtime')),
                verified_at    TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS coupons (
                coupon_id       INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                description     TEXT,
                discount_type   TEXT    DEFAULT 'percent',
                discount_value  REAL    DEFAULT 10,
                plan_restrict   TEXT,
                max_uses        INTEGER,
                used_count      INTEGER DEFAULT 0,
                is_active       INTEGER DEFAULT 1,
                created_by      INTEGER,
                expires_at      TEXT,
                created_at      TEXT    DEFAULT (datetime('now','localtime'))
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                sub_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                plan_key    TEXT    NOT NULL,
                payment_id  INTEGER,
                starts_at   TEXT    DEFAULT (datetime('now','localtime')),
                expires_at  TEXT,
                is_lifetime INTEGER DEFAULT 0,
                is_active   INTEGER DEFAULT 1,
                created_at  TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (user_id)   REFERENCES users(user_id),
                FOREIGN KEY (payment_id) REFERENCES payments(payment_id)
            )
        """)

        # ── Indexes ──────────────────────────────────────────
        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email    ON users(email)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_sessions_token ON sessions(token)",
            "CREATE INDEX IF NOT EXISTS ix_sessions_user   ON sessions(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_trans_user       ON translations(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_trans_date       ON translations(created_at)",
            "CREATE INDEX IF NOT EXISTS ix_trans_fav        ON translations(is_favorite)",
            "CREATE INDEX IF NOT EXISTS ix_fav_user         ON favorites(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_search_user      ON search_history(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_stats_user       ON daily_stats(user_id, stat_date)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_coupon    ON coupons(code)",
            "CREATE INDEX IF NOT EXISTS ix_payments_user    ON payments(user_id)",
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_pay_tran  ON payments(tran_id)",
            "CREATE INDEX IF NOT EXISTS ix_subs_user        ON subscriptions(user_id)",
            "CREATE INDEX IF NOT EXISTS ix_login_email      ON login_attempts(email)",
        ]
        for idx in indexes:
            try:
                c.execute(idx)
            except Exception:
                pass


# ════════════════════════════════════════════════════════════
#  AUTH DB FUNCTIONS
# ════════════════════════════════════════════════════════════

def db_register_user(email: str, pw_hash: str, display_name: str) -> dict:
    """Insert a new user. Returns {success, user_id, error}."""
    import random
    colors = ["#4F46E5","#10B981","#F59E0B","#EF4444","#8B5CF6","#06B6D4","#EC4899"]
    color  = random.choice(colors)
    try:
        with get_db() as c:
            cursor = c.execute("""
                INSERT INTO users (email, password_hash, display_name, avatar_color)
                VALUES (?, ?, ?, ?)
            """, (email, pw_hash, display_name, color))
            user_id = cursor.lastrowid
        return {"success": True, "user_id": user_id}
    except sqlite3.IntegrityError:
        return {"success": False, "error": "An account with this email already exists."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def db_get_user_by_email(email: str) -> dict | None:
    with get_db() as c:
        row = c.execute(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email,)
        ).fetchone()
        return dict(row) if row else None


def db_get_user_by_id(user_id: int) -> dict | None:
    with get_db() as c:
        row = c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def db_create_session(user_id: int, token: str, expires_at: str):
    """Save a new session token."""
    with get_db() as c:
        # Clean old sessions for this user first
        c.execute(
            "DELETE FROM sessions WHERE user_id = ? AND expires_at < datetime('now','localtime')",
            (user_id,)
        )
        c.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?,?,?)",
            (user_id, token, expires_at)
        )


def db_get_session_user(token: str) -> dict | None:
    """Get user from session token if not expired."""
    with get_db() as c:
        row = c.execute("""
            SELECT u.* FROM users u
            JOIN sessions s ON u.user_id = s.user_id
            WHERE s.token = ?
              AND s.expires_at > datetime('now','localtime')
        """, (token,)).fetchone()
        if row:
            # Update last_active
            c.execute(
                "UPDATE users SET last_active = datetime('now','localtime') WHERE user_id = ?",
                (row["user_id"],)
            )
            return dict(row)
        return None


def db_delete_session(token: str):
    with get_db() as c:
        c.execute("DELETE FROM sessions WHERE token = ?", (token,))


def db_record_login_attempt(email: str, success: bool):
    with get_db() as c:
        c.execute(
            "INSERT INTO login_attempts (email, success) VALUES (?,?)",
            (email, 1 if success else 0)
        )
        if success:
            # Reset failed attempts on success
            c.execute(
                "UPDATE users SET locked_until = NULL WHERE email = ? COLLATE NOCASE", (email,)
            )


def db_get_failed_attempts(email: str) -> int:
    """Count failed attempts in the last 30 minutes."""
    with get_db() as c:
        row = c.execute("""
            SELECT COUNT(*) AS cnt FROM login_attempts
            WHERE email = ? COLLATE NOCASE AND success = 0
              AND attempted_at > datetime('now','-30 minutes','localtime')
        """, (email,)).fetchone()
        return row["cnt"] if row else 0


def db_lock_account(email: str, minutes: int = 30):
    locked = (datetime.now() + timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as c:
        c.execute(
            "UPDATE users SET locked_until = ? WHERE email = ? COLLATE NOCASE",
            (locked, email)
        )


def db_save_otp(email: str, otp: str, expires_at: str):
    with get_db() as c:
        # Invalidate old OTPs for this email
        c.execute("UPDATE otp_codes SET used = 1 WHERE email = ? COLLATE NOCASE", (email,))
        c.execute(
            "INSERT INTO otp_codes (email, otp, expires_at) VALUES (?,?,?)",
            (email, otp, expires_at)
        )


def db_verify_otp(email: str, otp: str) -> bool:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as c:
        row = c.execute("""
            SELECT otp_id FROM otp_codes
            WHERE email = ? COLLATE NOCASE AND otp = ?
              AND used = 0 AND expires_at > ?
            ORDER BY created_at DESC LIMIT 1
        """, (email, otp, now)).fetchone()
        if row:
            c.execute("UPDATE otp_codes SET used = 1 WHERE otp_id = ?", (row["otp_id"],))
            return True
        return False


def db_update_password(email: str, pw_hash: str):
    with get_db() as c:
        c.execute(
            "UPDATE users SET password_hash = ? WHERE email = ? COLLATE NOCASE",
            (pw_hash, email)
        )


def db_update_user_field(user_id: int, field: str, value):
    """Update a single column on the users table safely."""
    allowed = {
        "display_name","avatar_color","preferred_lang","preferred_domain",
        "preferred_tone","is_pro","is_verified"
    }
    if field not in allowed:
        return
    with get_db() as c:
        c.execute(f"UPDATE users SET {field} = ? WHERE user_id = ?", (value, user_id))


def db_get_all_users() -> list[dict]:
    with get_db() as c:
        rows = c.execute("""
            SELECT user_id, email, display_name, is_pro, is_admin,
                   total_count, daily_count, created_at, last_active
            FROM users ORDER BY total_count DESC
        """).fetchall()
        return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════
#  TRANSLATION DB FUNCTIONS
# ════════════════════════════════════════════════════════════

def check_and_update_daily_limit(user_id: int, is_pro: bool) -> dict:
    """
    Check if user can translate today. Update counter if allowed.
    Returns {allowed, used_today, limit, is_pro}
    """
    if is_pro:
        return {"allowed": True, "used_today": 0, "limit": 999999, "is_pro": True}

    today = datetime.now().strftime("%Y-%m-%d")
    with get_db() as c:
        user = c.execute(
            "SELECT daily_count, daily_reset, total_count FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not user:
            return {"allowed": False, "used_today": 0, "limit": FREE_TRANSLATIONS_PER_DAY, "is_pro": False}

        # Reset daily counter if new day
        if user["daily_reset"] != today:
            c.execute(
                "UPDATE users SET daily_count = 0, daily_reset = ? WHERE user_id = ?",
                (today, user_id)
            )
            daily = 0
        else:
            daily = user["daily_count"]

        total = user["total_count"]

        # Check limits
        if daily >= FREE_TRANSLATIONS_PER_DAY:
            return {
                "allowed": False,
                "used_today": daily,
                "limit": FREE_TRANSLATIONS_PER_DAY,
                "reason": f"Daily limit of {FREE_TRANSLATIONS_PER_DAY} reached. Resets at midnight.",
                "is_pro": False
            }
        if total >= FREE_TRANSLATIONS_TOTAL:
            return {
                "allowed": False,
                "used_today": daily,
                "limit": FREE_TRANSLATIONS_TOTAL,
                "reason": f"You have used all {FREE_TRANSLATIONS_TOTAL} free translations. Please upgrade.",
                "is_pro": False
            }

        return {
            "allowed": True,
            "used_today": daily,
            "limit": FREE_TRANSLATIONS_PER_DAY,
            "is_pro": False
        }


def save_translation(
    user_id: int,
    source_lang: str, target_lang: str,
    source_text: str, translated_text: str,
    domain: str = "General", tone: str = "Formal",
    tokens_used: int = 0
) -> int:
    """Save translation and update all counters. Returns trans_id."""
    words    = len(source_text.split())
    chars    = len(source_text)
    today    = datetime.now().strftime("%Y-%m-%d")
    direction = "BN_TO_EN" if source_lang == "Bangla" else "EN_TO_BN"

    with get_db() as c:
        cursor = c.execute("""
            INSERT INTO translations
                (user_id, source_lang, target_lang, source_text, translated_text,
                 domain, tone, word_count, char_count, tokens_used)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (user_id, source_lang, target_lang, source_text, translated_text,
               domain, tone, words, chars, tokens_used))
        trans_id = cursor.lastrowid

        # Update user counters
        c.execute("""
            UPDATE users
            SET daily_count = daily_count + 1,
                total_count = total_count + 1,
                last_active = datetime('now','localtime')
            WHERE user_id = ?
        """, (user_id,))

        # Upsert daily stats
        c.execute("""
            INSERT INTO daily_stats (user_id, stat_date, direction, domain, count, total_chars)
            VALUES (?,?,?,?,1,?)
            ON CONFLICT(user_id, stat_date, direction, domain)
            DO UPDATE SET count = count+1, total_chars = total_chars+excluded.total_chars
        """, (user_id, today, direction, domain, chars))

        return trans_id


def get_recent_translations(
    user_id: int, limit: int = 50,
    lang_filter: str = "All", domain_filter: str = "All"
) -> list[dict]:
    query  = "SELECT * FROM translations WHERE user_id = ?"
    params = [user_id]
    if lang_filter == "Bangla → English":
        query += " AND source_lang = 'Bangla'"
    elif lang_filter == "English → Bangla":
        query += " AND source_lang = 'English'"
    if domain_filter != "All":
        query += " AND domain = ?"
        params.append(domain_filter)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with get_db() as c:
        return [dict(r) for r in c.execute(query, params).fetchall()]


def search_translations(user_id: int, query: str) -> list[dict]:
    term = f"%{query}%"
    # Save to search history
    with get_db() as c:
        # Avoid duplicate searches within 1 minute
        recent = c.execute("""
            SELECT search_id FROM search_history
            WHERE user_id=? AND query=?
              AND searched_at > datetime('now','-1 minute','localtime')
        """, (user_id, query.strip())).fetchone()
        if not recent:
            c.execute(
                "INSERT INTO search_history (user_id, query) VALUES (?,?)",
                (user_id, query.strip())
            )
        rows = c.execute("""
            SELECT * FROM translations
            WHERE user_id = ?
              AND (source_text LIKE ? OR translated_text LIKE ?)
            ORDER BY created_at DESC LIMIT 50
        """, (user_id, term, term)).fetchall()
        return [dict(r) for r in rows]


def delete_translation(trans_id: int, user_id: int) -> bool:
    with get_db() as c:
        row = c.execute(
            "SELECT user_id FROM translations WHERE trans_id=?", (trans_id,)
        ).fetchone()
        if not row or row["user_id"] != user_id:
            return False
        c.execute("DELETE FROM favorites    WHERE trans_id=?", (trans_id,))
        c.execute("DELETE FROM translations WHERE trans_id=?", (trans_id,))
        return True


def rate_translation(trans_id: int, rating: int):
    if 1 <= rating <= 5:
        with get_db() as c:
            c.execute("UPDATE translations SET user_rating=? WHERE trans_id=?", (rating, trans_id))


def delete_all_history(user_id: int) -> int:
    with get_db() as c:
        c.execute("DELETE FROM favorites    WHERE user_id=?", (user_id,))
        r = c.execute("DELETE FROM translations WHERE user_id=?", (user_id,))
        # Reset counters
        c.execute("UPDATE users SET daily_count=0, total_count=0 WHERE user_id=?", (user_id,))
        return r.rowcount


# ════════════════════════════════════════════════════════════
#  FAVORITES
# ════════════════════════════════════════════════════════════

def toggle_favorite(trans_id: int, user_id: int) -> bool:
    """Toggle. Returns True if now favorited."""
    with get_db() as c:
        row = c.execute(
            "SELECT fav_id FROM favorites WHERE trans_id=? AND user_id=?",
            (trans_id, user_id)
        ).fetchone()
        if row:
            c.execute("DELETE FROM favorites WHERE trans_id=? AND user_id=?", (trans_id, user_id))
            c.execute("UPDATE translations SET is_favorite=0 WHERE trans_id=?", (trans_id,))
            return False
        else:
            c.execute(
                "INSERT INTO favorites (trans_id, user_id) VALUES (?,?)",
                (trans_id, user_id)
            )
            c.execute("UPDATE translations SET is_favorite=1 WHERE trans_id=?", (trans_id,))
            return True


def get_favorites(user_id: int, folder: str = None) -> list[dict]:
    query  = """
        SELECT t.*, f.note, f.folder, f.added_at
        FROM favorites f JOIN translations t ON f.trans_id = t.trans_id
        WHERE f.user_id = ?
    """
    params = [user_id]
    if folder and folder != "All folders":
        query += " AND f.folder = ?"
        params.append(folder)
    query += " ORDER BY f.added_at DESC"
    with get_db() as c:
        return [dict(r) for r in c.execute(query, params).fetchall()]


def update_favorite_note(trans_id: int, user_id: int, note: str):
    with get_db() as c:
        c.execute(
            "UPDATE favorites SET note=? WHERE trans_id=? AND user_id=?",
            (note, trans_id, user_id)
        )


def update_favorite_folder(trans_id: int, user_id: int, folder: str):
    with get_db() as c:
        c.execute(
            "UPDATE favorites SET folder=? WHERE trans_id=? AND user_id=?",
            (folder, trans_id, user_id)
        )


def get_favorite_folders(user_id: int) -> list[str]:
    with get_db() as c:
        rows = c.execute(
            "SELECT DISTINCT folder FROM favorites WHERE user_id=? AND folder IS NOT NULL ORDER BY folder",
            (user_id,)
        ).fetchall()
        return [r["folder"] for r in rows]


# ════════════════════════════════════════════════════════════
#  ANALYTICS
# ════════════════════════════════════════════════════════════

def get_analytics_summary(user_id: int) -> dict:
    today    = datetime.now().strftime("%Y-%m-%d")
    week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    with get_db() as c:
        row = c.execute("""
            SELECT
                COUNT(*)                                              AS total,
                SUM(char_count)                                       AS total_chars,
                SUM(word_count)                                       AS total_words,
                COUNT(CASE WHEN is_favorite=1 THEN 1 END)            AS favorites,
                COUNT(CASE WHEN source_lang='Bangla' THEN 1 END)      AS bn_to_en,
                COUNT(CASE WHEN source_lang='English' THEN 1 END)     AS en_to_bn,
                ROUND(AVG(CASE WHEN user_rating IS NOT NULL THEN user_rating END),1) AS avg_rating,
                COUNT(CASE WHEN DATE(created_at)=? THEN 1 END)        AS today_count,
                COUNT(CASE WHEN DATE(created_at)>=? THEN 1 END)       AS week_count
            FROM translations WHERE user_id=?
        """, (today, week_ago, user_id)).fetchone()
        result = dict(row) if row else {}

        # Streak
        days = c.execute("""
            SELECT DISTINCT DATE(created_at) AS d
            FROM translations WHERE user_id=?
            ORDER BY d DESC LIMIT 30
        """, (user_id,)).fetchall()
        streak = 0
        for i, d in enumerate(days):
            expected = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            if d["d"] == expected:
                streak += 1
            else:
                break
        result["streak"] = streak
        return result


def get_daily_counts(user_id: int, days: int = 14) -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_db() as c:
        rows = c.execute("""
            SELECT
                DATE(created_at)                                    AS day,
                strftime('%d %b', created_at)                       AS label,
                COUNT(*)                                            AS total,
                COUNT(CASE WHEN source_lang='Bangla' THEN 1 END)    AS bn,
                COUNT(CASE WHEN source_lang='English' THEN 1 END)   AS en
            FROM translations
            WHERE user_id=? AND DATE(created_at)>=?
            GROUP BY DATE(created_at) ORDER BY day
        """, (user_id, since)).fetchall()
        return [dict(r) for r in rows]


def get_domain_stats(user_id: int) -> list[dict]:
    with get_db() as c:
        rows = c.execute("""
            SELECT COALESCE(domain,'General') AS domain, COUNT(*) AS total
            FROM translations WHERE user_id=?
            GROUP BY domain ORDER BY total DESC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_hourly_heatmap(user_id: int) -> list[dict]:
    with get_db() as c:
        rows = c.execute("""
            SELECT CAST(strftime('%H',created_at) AS INTEGER) AS hour, COUNT(*) AS total
            FROM translations WHERE user_id=?
            GROUP BY hour ORDER BY hour
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]


def get_search_history(user_id: int, limit: int = 10) -> list[str]:
    with get_db() as c:
        rows = c.execute("""
            SELECT DISTINCT query FROM search_history
            WHERE user_id=? ORDER BY searched_at DESC LIMIT ?
        """, (user_id, limit)).fetchall()
        return [r["query"] for r in rows]


def clear_search_history(user_id: int):
    with get_db() as c:
        c.execute("DELETE FROM search_history WHERE user_id=?", (user_id,))


# ════════════════════════════════════════════════════════════
#  USER SETTINGS
# ════════════════════════════════════════════════════════════

def save_setting(user_id: int, key: str, value: str):
    with get_db() as c:
        c.execute("""
            INSERT INTO user_settings (user_id, key, value, updated_at)
            VALUES (?,?,?,datetime('now','localtime'))
            ON CONFLICT(user_id, key)
            DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """, (user_id, key, value))


def get_setting(user_id: int, key: str, default: str = None) -> str:
    with get_db() as c:
        row = c.execute(
            "SELECT value FROM user_settings WHERE user_id=? AND key=?",
            (user_id, key)
        ).fetchone()
        return row["value"] if row else default


# ════════════════════════════════════════════════════════════
#  PAYMENTS
# ════════════════════════════════════════════════════════════

def create_payment_record(
    user_id: int, tran_id: str, plan_key: str,
    original_amt: float, paid_amt: float,
    coupon_code: str = None, discount_amt: float = 0,
    is_sandbox: bool = True
) -> int:
    with get_db() as c:
        r = c.execute("""
            INSERT INTO payments
                (user_id, tran_id, plan_key, original_amt, paid_amt,
                 coupon_code, discount_amt, status, is_sandbox)
            VALUES (?,?,?,?,?,?,?,'PENDING',?)
        """, (user_id, tran_id, plan_key, original_amt, paid_amt,
               coupon_code, discount_amt, 1 if is_sandbox else 0))
        return r.lastrowid


def mark_payment_success(tran_id: str, payment_method: str = "") -> bool:
    with get_db() as c:
        pay = c.execute("SELECT * FROM payments WHERE tran_id=?", (tran_id,)).fetchone()
        if not pay:
            return False
        pay = dict(pay)

        c.execute("""
            UPDATE payments
            SET status='PAID', payment_method=?,
                verified_at=datetime('now','localtime')
            WHERE tran_id=?
        """, (payment_method, tran_id))

        # Upgrade user
        c.execute("UPDATE users SET is_pro=1 WHERE user_id=?", (pay["user_id"],))

        # Create subscription
        plan     = PLANS.get(pay["plan_key"], {})
        days     = plan.get("duration_days", 30)
        is_life  = 1 if days > 9999 else 0
        expires  = None if is_life else (
            datetime.now() + timedelta(days=days)
        ).strftime("%Y-%m-%d %H:%M:%S")

        c.execute("""
            INSERT INTO subscriptions (user_id, plan_key, payment_id, expires_at, is_lifetime)
            VALUES (?,?,?,?,?)
        """, (pay["user_id"], pay["plan_key"], pay["payment_id"], expires, is_life))

        # Update coupon usage
        if pay.get("coupon_code"):
            c.execute(
                "UPDATE coupons SET used_count=used_count+1 WHERE code=? COLLATE NOCASE",
                (pay["coupon_code"],)
            )
        return True


def mark_payment_failed(tran_id: str, reason: str = ""):
    with get_db() as c:
        c.execute("UPDATE payments SET status='FAILED', notes=? WHERE tran_id=?", (reason, tran_id))


def get_payment_by_tran(tran_id: str) -> dict | None:
    with get_db() as c:
        row = c.execute("SELECT * FROM payments WHERE tran_id=?", (tran_id,)).fetchone()
        return dict(row) if row else None


def get_user_payments(user_id: int) -> list[dict]:
    with get_db() as c:
        rows = c.execute(
            "SELECT * FROM payments WHERE user_id=? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return [dict(r) for r in rows]


def get_all_payments(limit: int = 200) -> list[dict]:
    with get_db() as c:
        rows = c.execute("""
            SELECT p.*, u.email, u.display_name
            FROM payments p
            JOIN users u ON p.user_id = u.user_id
            ORDER BY p.created_at DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_payment_stats() -> dict:
    with get_db() as c:
        row = c.execute("""
            SELECT
                COUNT(*)                                             AS total_attempts,
                COUNT(CASE WHEN status='PAID'    THEN 1 END)        AS successful,
                COUNT(CASE WHEN status='FAILED'  THEN 1 END)        AS failed,
                COUNT(CASE WHEN status='PENDING' THEN 1 END)        AS pending,
                COALESCE(SUM(CASE WHEN status='PAID' THEN paid_amt END),0)           AS total_revenue,
                COALESCE(SUM(CASE WHEN status='PAID' AND is_sandbox=0 THEN paid_amt END),0) AS live_revenue,
                COUNT(CASE WHEN status='PAID' AND DATE(created_at)=DATE('now') THEN 1 END)  AS today_sales,
                COALESCE(SUM(CASE WHEN status='PAID' AND DATE(created_at)=DATE('now') THEN paid_amt END),0) AS today_revenue
            FROM payments
        """).fetchone()
        return dict(row) if row else {}


def check_subscription_expiry(user_id: int) -> bool:
    """Returns True if still active Pro, downgrades if expired."""
    with get_db() as c:
        sub = c.execute("""
            SELECT * FROM subscriptions
            WHERE user_id=? AND is_active=1
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,)).fetchone()
        if not sub:
            return False
        if sub["is_lifetime"]:
            return True
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if sub["expires_at"] and now > sub["expires_at"]:
            c.execute("UPDATE subscriptions SET is_active=0 WHERE sub_id=?", (sub["sub_id"],))
            c.execute("UPDATE users SET is_pro=0 WHERE user_id=?", (user_id,))
            return False
        return True


def get_subscription(user_id: int) -> dict | None:
    with get_db() as c:
        row = c.execute("""
            SELECT * FROM subscriptions WHERE user_id=? AND is_active=1
            ORDER BY created_at DESC LIMIT 1
        """, (user_id,)).fetchone()
        return dict(row) if row else None


def upgrade_to_pro(user_id: int, plan_key: str = "lifetime"):
    """Admin upgrade without payment."""
    days = PLANS.get(plan_key, {}).get("duration_days", 99999)
    is_life = 1 if days > 9999 else 0
    expires = None if is_life else (
        datetime.now() + timedelta(days=days)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db() as c:
        c.execute("UPDATE users SET is_pro=1 WHERE user_id=?", (user_id,))
        c.execute("""
            INSERT INTO subscriptions (user_id, plan_key, expires_at, is_lifetime)
            VALUES (?,?,?,?)
        """, (user_id, plan_key, expires, is_life))


def downgrade_to_free(user_id: int):
    with get_db() as c:
        c.execute("UPDATE users SET is_pro=0, daily_count=0 WHERE user_id=?", (user_id,))
        c.execute("UPDATE subscriptions SET is_active=0 WHERE user_id=?", (user_id,))


# ════════════════════════════════════════════════════════════
#  COUPONS
# ════════════════════════════════════════════════════════════

def create_coupon(
    code: str, discount_type: str, discount_value: float,
    description: str = "", max_uses: int = None,
    plan_restrict: str = None, expires_days: int = None,
    created_by: int = None
) -> dict:
    code = code.strip().upper()
    expires = None
    if expires_days:
        expires = (datetime.now() + timedelta(days=expires_days)).strftime("%Y-%m-%d")
    try:
        with get_db() as c:
            c.execute("""
                INSERT INTO coupons
                    (code, description, discount_type, discount_value,
                     plan_restrict, max_uses, expires_at, created_by)
                VALUES (?,?,?,?,?,?,?,?)
            """, (code, description, discount_type, discount_value,
                   plan_restrict, max_uses, expires, created_by))
        return {"success": True, "code": code}
    except sqlite3.IntegrityError:
        return {"success": False, "error": f"Code '{code}' already exists."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_coupon(code: str) -> dict | None:
    with get_db() as c:
        row = c.execute(
            "SELECT * FROM coupons WHERE code=? COLLATE NOCASE AND is_active=1",
            (code.strip(),)
        ).fetchone()
        return dict(row) if row else None


def apply_coupon(code: str, amount: float, plan_key: str = None) -> dict:
    """Apply coupon to amount. Returns discount details."""
    coupon = get_coupon(code)
    if not coupon:
        return {"valid": False, "message": "Invalid or expired coupon code."}
    if coupon.get("max_uses") and coupon["used_count"] >= coupon["max_uses"]:
        return {"valid": False, "message": "This coupon has reached its usage limit."}
    if coupon.get("expires_at"):
        if datetime.now().strftime("%Y-%m-%d") > coupon["expires_at"]:
            return {"valid": False, "message": "This coupon has expired."}
    if coupon.get("plan_restrict") and plan_key and coupon["plan_restrict"] != plan_key:
        pname = PLANS.get(coupon["plan_restrict"],{}).get("name", coupon["plan_restrict"])
        return {"valid": False, "message": f"This coupon only applies to {pname}."}

    dt, dv = coupon["discount_type"], float(coupon["discount_value"])
    if dt == "percent":
        saved  = round(amount * dv / 100, 2)
        final  = max(0, amount - saved)
        label  = f"{int(dv)}% OFF"
    elif dt == "fixed":
        saved  = min(dv, amount)
        final  = max(0, amount - saved)
        label  = f"৳{int(dv)} OFF"
    else:  # free
        saved  = amount
        final  = 0
        label  = "100% FREE"

    return {
        "valid": True,
        "discounted_amount": final,
        "saved": saved,
        "label": label,
        "is_free": (final == 0),
        "message": f"Coupon applied! {label} — Save ৳{int(saved)}"
    }


def get_all_coupons() -> list[dict]:
    with get_db() as c:
        rows = c.execute("""
            SELECT code, description, discount_type, discount_value,
                   plan_restrict, max_uses, used_count, is_active,
                   expires_at, created_at
            FROM coupons ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]


def deactivate_coupon(code: str):
    with get_db() as c:
        c.execute("UPDATE coupons SET is_active=0 WHERE code=? COLLATE NOCASE", (code,))


# ════════════════════════════════════════════════════════════
#  UTILITIES
# ════════════════════════════════════════════════════════════

def export_user_data(user_id: int) -> dict:
    """Export all user data as a dict for GDPR-style download."""
    import json
    with get_db() as c:
        user   = dict(c.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone() or {})
        trans  = [dict(r) for r in c.execute("SELECT * FROM translations WHERE user_id=?", (user_id,)).fetchall()]
        favs   = [dict(r) for r in c.execute("SELECT * FROM favorites WHERE user_id=?", (user_id,)).fetchall()]
        pays   = [dict(r) for r in c.execute("SELECT * FROM payments WHERE user_id=?", (user_id,)).fetchall()]
    user.pop("password_hash", None)
    return {
        "exported_at":   datetime.now().isoformat(),
        "user":          user,
        "translations":  trans,
        "favorites":     favs,
        "payments":      pays,
    }


def get_db_size() -> str:
    if os.path.exists(DB_PATH):
        b = os.path.getsize(DB_PATH)
        if b < 1024:        return f"{b} B"
        elif b < 1048576:   return f"{b/1024:.1f} KB"
        else:               return f"{b/1048576:.2f} MB"
    return "0 B"


def get_all_emails_for_admin() -> list[dict]:
    """Get all user emails — admin only."""
    with get_db() as c:
        rows = c.execute("""
            SELECT email, display_name, is_pro, total_count, created_at, last_active
            FROM users WHERE email IS NOT NULL
            ORDER BY created_at DESC
        """).fetchall()
        return [dict(r) for r in rows]
