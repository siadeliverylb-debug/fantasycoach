"""SQLite persistence for accounts, credits, and weekly free-advice tracking."""

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path(os.environ["DB_PATH"]) if "DB_PATH" in os.environ else Path(__file__).resolve().parent.parent / "data.db"

PBKDF2_ITERATIONS = 210_000
SIGNUP_BONUS_CREDITS = 5
# Currently unused: the referral credit reward is disabled (see create_user)
# until there's a way to verify a referral is a real, distinct person.
REFERRAL_BONUS_CREDITS = 5
ADMIN_EMAILS = {"sia.delivery.lb@gmail.com"}


def init_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                team_id TEXT
            );

            CREATE TABLE IF NOT EXISTS billing (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                stripe_customer_id TEXT,
                credits INTEGER NOT NULL DEFAULT 0,
                referred_by INTEGER REFERENCES users(id),
                lifetime_credits_spent INTEGER NOT NULL DEFAULT 0,
                golden_until TEXT
            );

            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                endpoint TEXT NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id),
                credits INTEGER NOT NULL,
                amount_cents INTEGER NOT NULL,
                provider_reference TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS advice_usage (
                user_id INTEGER NOT NULL REFERENCES users(id),
                gameweek INTEGER NOT NULL,
                used_at TEXT NOT NULL,
                use_count INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (user_id, gameweek)
            );

            CREATE TABLE IF NOT EXISTS chat_usage (
                user_id INTEGER NOT NULL REFERENCES users(id),
                gameweek INTEGER NOT NULL,
                message_count INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, gameweek)
            );

            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                credits INTEGER NOT NULL,
                created_by INTEGER NOT NULL REFERENCES users(id),
                created_at TEXT NOT NULL,
                redeemed_by INTEGER REFERENCES users(id),
                redeemed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS drafts (
                user_id INTEGER PRIMARY KEY REFERENCES users(id),
                team_id TEXT NOT NULL,
                gameweek INTEGER NOT NULL,
                total_budget_m REAL NOT NULL,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS page_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visitor_id TEXT NOT NULL,
                path TEXT NOT NULL,
                country TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_page_visits_created_at ON page_visits(created_at);
        """)
        # Lightweight migration: CREATE TABLE IF NOT EXISTS doesn't alter an
        # already-existing table, so add columns introduced after the table
        # was first created here rather than in the schema above.
        existing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(billing)")}
        if "referred_by" not in existing_columns:
            conn.execute("ALTER TABLE billing ADD COLUMN referred_by INTEGER REFERENCES users(id)")

        page_visits_columns = {row["name"] for row in conn.execute("PRAGMA table_info(page_visits)")}
        if "country" not in page_visits_columns:
            conn.execute("ALTER TABLE page_visits ADD COLUMN country TEXT")

        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "is_admin" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0")

        billing_columns = {row["name"] for row in conn.execute("PRAGMA table_info(billing)")}
        if "lifetime_credits_spent" not in billing_columns:
            conn.execute("ALTER TABLE billing ADD COLUMN lifetime_credits_spent INTEGER NOT NULL DEFAULT 0")
        if "golden_until" not in billing_columns:
            conn.execute("ALTER TABLE billing ADD COLUMN golden_until TEXT")

        advice_usage_columns = {row["name"] for row in conn.execute("PRAGMA table_info(advice_usage)")}
        if "use_count" not in advice_usage_columns:
            # DEFAULT 1 is correct for existing rows too: a row's mere presence
            # used to mean "the one free advice use this gameweek is spent".
            conn.execute("ALTER TABLE advice_usage ADD COLUMN use_count INTEGER NOT NULL DEFAULT 1")

        if "team_id" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN team_id TEXT")

        # SQLite can't add a UNIQUE column via ALTER TABLE, so the one-account-
        # per-FPL-team-ID rule is enforced with a partial unique index instead -
        # partial so existing accounts with no team_id (NULL) don't collide.
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_team_id ON users(team_id) WHERE team_id IS NOT NULL"
        )

        purchases_columns = {row["name"] for row in conn.execute("PRAGMA table_info(purchases)")}
        if "stripe_session_id" in purchases_columns and "provider_reference" not in purchases_columns:
            # Renamed when billing moved from Stripe to Tap Payments (Stripe
            # doesn't support Lebanon-registered merchants) - same column,
            # provider-neutral name.
            conn.execute("ALTER TABLE purchases RENAME COLUMN stripe_session_id TO provider_reference")

        # Prevents a replayed/duplicate NOWPayments webhook delivery from
        # crediting the same payment twice - partial so purchases recorded
        # without a provider_reference (if any predate this) don't collide.
        # Wrapped: if duplicate provider_reference values already exist in an
        # existing database (a past double-credit already happened), creating
        # the index fails - don't let that crash startup on a live deploy;
        # surface it loudly so it can be reconciled manually instead.
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_purchases_provider_reference "
                "ON purchases(provider_reference) WHERE provider_reference IS NOT NULL"
            )
        except sqlite3.IntegrityError:
            print(
                "WARNING: duplicate purchases.provider_reference values already exist - "
                "the anti-replay UNIQUE index could not be created. This means a webhook "
                "was likely already replayed and credited twice. Audit the purchases table "
                "and remove/merge duplicates, then restart to enable full protection."
            )

        # Backfill: any account matching ADMIN_EMAILS becomes admin, including ones
        # created before this feature existed.
        if ADMIN_EMAILS:
            placeholders = ",".join("?" for _ in ADMIN_EMAILS)
            conn.execute(
                f"UPDATE users SET is_admin = 1 WHERE lower(email) IN ({placeholders})",
                tuple(e.lower() for e in ADMIN_EMAILS),
            )


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _hash_password(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS).hex()


def get_last_country(visitor_id: str) -> str | None:
    """Most recent country recorded for this visitor_id, if any - lets a
    returning visitor's country be remembered without a fresh geolocation
    API call on every page view (only done once, on their first visit)."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT country FROM page_visits WHERE visitor_id = ? AND country IS NOT NULL "
            "ORDER BY created_at DESC LIMIT 1",
            (visitor_id,),
        ).fetchone()
    return row["country"] if row else None


def log_page_visit(visitor_id: str, path: str, country: str | None = None) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO page_visits (visitor_id, path, country, created_at) VALUES (?, ?, ?, ?)",
            (visitor_id, path, country, datetime.now(timezone.utc).isoformat()),
        )


def delete_visits_for_visitor(visitor_id: str) -> int:
    """Wipes all logged page visits for one visitor_id - used to let an admin
    clear their own dev/testing traffic out of the visitor stats. Returns how
    many rows were removed."""
    with _connect() as conn:
        cur = conn.execute("DELETE FROM page_visits WHERE visitor_id = ?", (visitor_id,))
        return cur.rowcount


def get_visitor_stats(days: int = 30, country: str | None = None) -> dict:
    """Rollup for the admin visitor-stats page: totals, unique visitors, a
    per-day breakdown, and a per-path breakdown, all for the last `days` days
    and optionally filtered to one `country` (as returned by `by_country`,
    which itself always covers every country regardless of this filter, so
    it can double as the filter dropdown's option list)."""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    if country == "Unknown":
        country_clause = " AND country IS NULL"
        country_params: tuple = ()
    elif country:
        country_clause = " AND country = ?"
        country_params = (country,)
    else:
        country_clause = ""
        country_params = ()
    with _connect() as conn:
        totals = conn.execute(
            f"SELECT COUNT(*) AS visits, COUNT(DISTINCT visitor_id) AS unique_visitors "
            f"FROM page_visits WHERE 1=1{country_clause}",
            country_params,
        ).fetchone()
        recent_totals = conn.execute(
            f"SELECT COUNT(*) AS visits, COUNT(DISTINCT visitor_id) AS unique_visitors "
            f"FROM page_visits WHERE created_at >= ?{country_clause}",
            (since, *country_params),
        ).fetchone()
        by_day = conn.execute(
            f"""
            SELECT substr(created_at, 1, 10) AS day,
                   COUNT(*) AS visits,
                   COUNT(DISTINCT visitor_id) AS unique_visitors
            FROM page_visits
            WHERE created_at >= ?{country_clause}
            GROUP BY day
            ORDER BY day
            """,
            (since, *country_params),
        ).fetchall()
        by_path = conn.execute(
            f"""
            SELECT path, COUNT(*) AS visits, COUNT(DISTINCT visitor_id) AS unique_visitors
            FROM page_visits
            WHERE created_at >= ?{country_clause}
            GROUP BY path
            ORDER BY visits DESC
            """,
            (since, *country_params),
        ).fetchall()
        by_country = conn.execute(
            """
            SELECT COALESCE(country, 'Unknown') AS country,
                   COUNT(*) AS visits,
                   COUNT(DISTINCT visitor_id) AS unique_visitors
            FROM page_visits
            WHERE created_at >= ?
            GROUP BY country
            ORDER BY visits DESC
            """,
            (since,),
        ).fetchall()
    return {
        "total_visits": totals["visits"],
        "total_unique_visitors": totals["unique_visitors"],
        "recent_visits": recent_totals["visits"],
        "recent_unique_visitors": recent_totals["unique_visitors"],
        "by_day": [dict(r) for r in by_day],
        "by_path": [dict(r) for r in by_path],
        "by_country": [dict(r) for r in by_country],
    }


def list_all_emails() -> list[str]:
    with _connect() as conn:
        return [row["email"] for row in conn.execute("SELECT email FROM users")]


def reset_password(email: str, new_password: str) -> bool:
    """One-off admin password reset (no self-serve "forgot password" flow
    exists yet). Returns False if no account matches `email`."""
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(new_password, salt)
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE users SET password_hash = ?, password_salt = ? WHERE email = ?",
            (password_hash, salt.hex(), email.lower().strip()),
        )
        return cur.rowcount > 0


def create_user(email: str, password: str, team_id: str, referred_by: int | None = None) -> int:
    """Raises sqlite3.IntegrityError (message mentions "team_id") if team_id is
    already registered to another account - one FPL team can only back one
    account, to stop a single person farming signup bonuses with N accounts."""
    salt = secrets.token_bytes(16)
    password_hash = _hash_password(password, salt)
    email_norm = email.lower().strip()
    is_admin_flag = 1 if email_norm in {e.lower() for e in ADMIN_EMAILS} else 0
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, password_salt, created_at, is_admin, team_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (email_norm, password_hash, salt.hex(), datetime.now(timezone.utc).isoformat(), is_admin_flag, team_id),
        )
        user_id = cur.lastrowid

        valid_referrer = None
        if referred_by is not None:
            referrer_row = conn.execute("SELECT id FROM users WHERE id = ?", (referred_by,)).fetchone()
            if referrer_row is not None:
                valid_referrer = referred_by

        conn.execute(
            "INSERT INTO billing (user_id, credits, referred_by) VALUES (?, ?, ?)",
            (user_id, SIGNUP_BONUS_CREDITS, valid_referrer),
        )
        # Referral credit reward is disabled for now (no verification that a
        # referral is a real, distinct person yet - see REFERRAL_BONUS_CREDITS).
        # `referred_by` is still recorded so the link/tracking survives if the
        # reward is reintroduced later.
        return user_id


def verify_login(email: str, password: str) -> int | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, password_hash, password_salt FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if row is None:
        return None
    salt = bytes.fromhex(row["password_salt"])
    if not hmac.compare_digest(_hash_password(password, salt), row["password_hash"]):
        return None
    return row["id"]


def get_user(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, email, created_at, is_admin, team_id FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if row is None:
        return None
    user = dict(row)
    user["is_admin"] = bool(user["is_admin"])
    return user


def set_team_id(user_id: int, team_id: str | None) -> None:
    """Admin-only correction for a team ID entered wrong at signup (there's no
    self-serve way to change it, since it's the one-account-per-FPL-team
    unique key). Raises ValueError if another account already owns that ID."""
    with _connect() as conn:
        try:
            conn.execute("UPDATE users SET team_id = ? WHERE id = ?", (team_id, user_id))
        except sqlite3.IntegrityError:
            raise ValueError(f"Team ID {team_id} is already registered to another account.")


def is_admin(user_id: int) -> bool:
    with _connect() as conn:
        row = conn.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,)).fetchone()
    return bool(row["is_admin"]) if row else False


def list_users() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.email, u.created_at, u.is_admin, COALESCE(b.credits, 0) AS credits
            FROM users u
            LEFT JOIN billing b ON b.user_id = u.id
            ORDER BY u.id
            """
        ).fetchall()
    users = [dict(r) for r in rows]
    for u in users:
        u["is_admin"] = bool(u["is_admin"])
    return users


def get_user_row(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT u.id, u.email, u.created_at, u.is_admin, COALESCE(b.credits, 0) AS credits
            FROM users u
            LEFT JOIN billing b ON b.user_id = u.id
            WHERE u.id = ?
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    user = dict(row)
    user["is_admin"] = bool(user["is_admin"])
    return user


def set_credits(user_id: int, credits: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO billing (user_id, credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET credits = excluded.credits
            """,
            (user_id, credits),
        )


def get_credits(user_id: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT credits FROM billing WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["credits"] if row else 0


def get_golden_until(user_id: int) -> str | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT golden_until FROM billing WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["golden_until"] if row else None


def extend_golden(user_id: int, days: int) -> str:
    """Extends Golden status by `days` from whichever is later: now, or the
    current expiry (so renewing before it lapses stacks on top instead of
    wasting the remaining time). Returns the new expiry as an ISO string."""
    now = datetime.now(timezone.utc)
    current = get_golden_until(user_id)
    base = now
    if current:
        try:
            current_dt = datetime.fromisoformat(current)
            if current_dt > now:
                base = current_dt
        except ValueError:
            pass
    new_until = (base + timedelta(days=days)).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO billing (user_id, golden_until) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET golden_until = excluded.golden_until
            """,
            (user_id, new_until),
        )
    return new_until


def add_credits(user_id: int, n: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO billing (user_id, credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET credits = credits + excluded.credits
            """,
            (user_id, n),
        )


def spend_credits(user_id: int, n: int = 1) -> None:
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE billing SET credits = credits - ? WHERE user_id = ? AND credits >= ?",
            (n, user_id, n),
        )
        if cur.rowcount:
            conn.execute(
                "UPDATE billing SET lifetime_credits_spent = lifetime_credits_spent + ? WHERE user_id = ?",
                (n, user_id),
            )


def log_token_usage(user_id: int, endpoint: str, input_tokens: int, output_tokens: int) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO token_usage (user_id, endpoint, input_tokens, output_tokens, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, endpoint, input_tokens, output_tokens, datetime.now(timezone.utc).isoformat()),
        )


def record_purchase(user_id: int, credits: int, amount_cents: int, provider_reference: str | None = None) -> bool:
    """Logs an actual completed payment (via NOWPayments) - the real dollars
    taken in, as opposed to `lifetime_credits_spent` which tracks credits
    redeemed (including free signup/referral credits that were never paid for).

    Returns False without inserting if provider_reference was already recorded
    (a duplicate/replayed webhook delivery for a payment already credited) -
    enforced by a UNIQUE index, not just this check, so it's race-safe."""
    with _connect() as conn:
        try:
            conn.execute(
                "INSERT INTO purchases (user_id, credits, amount_cents, provider_reference, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, credits, amount_cents, provider_reference, datetime.now(timezone.utc).isoformat()),
            )
        except sqlite3.IntegrityError:
            return False
        return True


def create_promo_code(credits: int, created_by: int) -> str:
    """Generates a single-use promo code worth `credits` free credits, e.g. for
    handing to a friend outside the (currently disabled) referral flow."""
    code = secrets.token_hex(4).upper()  # 8 hex chars, e.g. "A1B2C3D4"
    with _connect() as conn:
        conn.execute(
            "INSERT INTO promo_codes (code, credits, created_by, created_at) VALUES (?, ?, ?, ?)",
            (code, credits, created_by, datetime.now(timezone.utc).isoformat()),
        )
    return code


def redeem_promo_code(code: str, user_id: int) -> int:
    """Redeems a promo code for `user_id`, crediting their account. Raises
    ValueError if the code doesn't exist or was already redeemed (by anyone,
    including this same user)."""
    code_norm = code.strip().upper()
    with _connect() as conn:
        row = conn.execute("SELECT credits FROM promo_codes WHERE code = ?", (code_norm,)).fetchone()
        if row is None:
            raise ValueError("Invalid promo code.")
        # Single atomic UPDATE guarded by "redeemed_by IS NULL" instead of a
        # separate check-then-act - prevents two concurrent redemptions of the
        # same code both succeeding (SQLite serializes writers, so only one
        # of two racing UPDATEs can match this WHERE clause).
        cur = conn.execute(
            "UPDATE promo_codes SET redeemed_by = ?, redeemed_at = ? WHERE code = ? AND redeemed_by IS NULL",
            (user_id, datetime.now(timezone.utc).isoformat(), code_norm),
        )
        if cur.rowcount == 0:
            raise ValueError("This promo code has already been used.")
        conn.execute(
            """
            INSERT INTO billing (user_id, credits) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET credits = credits + excluded.credits
            """,
            (user_id, row["credits"]),
        )
        return row["credits"]


def delete_promo_code(code: str) -> bool:
    """Removes a promo code outright - even if already redeemed, this only
    deletes the tracking row, it doesn't claw back credits already granted."""
    code_norm = code.strip().upper()
    with _connect() as conn:
        cur = conn.execute("DELETE FROM promo_codes WHERE code = ?", (code_norm,))
    return cur.rowcount > 0


def list_promo_codes() -> list[dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.code, p.credits, p.created_at, p.redeemed_at, u.email AS redeemed_by_email
            FROM promo_codes p
            LEFT JOIN users u ON u.id = p.redeemed_by
            ORDER BY p.created_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_usage_summary() -> list[dict]:
    """Per-user usage rollup for the admin dashboard: token totals (from every
    Claude API call attributable to that user, including the scope classifier),
    lifetime credits spent, real NOWPayments revenue collected, and current
    chat/advice activity."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id, u.email, u.created_at, u.is_admin, u.team_id,
                COALESCE(b.credits, 0) AS credits,
                COALESCE(b.lifetime_credits_spent, 0) AS lifetime_credits_spent,
                COALESCE(t.input_tokens, 0) AS input_tokens,
                COALESCE(t.output_tokens, 0) AS output_tokens,
                COALESCE(t.call_count, 0) AS call_count,
                COALESCE(p.amount_cents, 0) AS revenue_cents,
                COALESCE(p.credits_purchased, 0) AS credits_purchased,
                b.golden_until
            FROM users u
            LEFT JOIN billing b ON b.user_id = u.id
            LEFT JOIN (
                SELECT user_id, SUM(input_tokens) AS input_tokens,
                       SUM(output_tokens) AS output_tokens, COUNT(*) AS call_count
                FROM token_usage
                GROUP BY user_id
            ) t ON t.user_id = u.id
            LEFT JOIN (
                SELECT user_id, SUM(amount_cents) AS amount_cents, SUM(credits) AS credits_purchased
                FROM purchases
                GROUP BY user_id
            ) p ON p.user_id = u.id
            ORDER BY u.id
            """
        ).fetchall()
    users = [dict(r) for r in rows]
    for u in users:
        u["is_admin"] = bool(u["is_admin"])
        u["is_golden"] = is_golden_active(u["golden_until"])
    return users


def is_golden_active(golden_until: str | None) -> bool:
    if not golden_until:
        return False
    try:
        return datetime.fromisoformat(golden_until) > datetime.now(timezone.utc)
    except ValueError:
        return False


def get_advice_usage_count(user_id: int, gameweek: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT use_count FROM advice_usage WHERE user_id = ? AND gameweek = ?",
            (user_id, gameweek),
        ).fetchone()
    return row["use_count"] if row else 0


def increment_advice_usage(user_id: int, gameweek: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO advice_usage (user_id, gameweek, used_at, use_count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(user_id, gameweek) DO UPDATE SET use_count = use_count + 1
            """,
            (user_id, gameweek, datetime.now(timezone.utc).isoformat()),
        )


def user_is_golden(user_id: int) -> bool:
    return is_golden_active(get_golden_until(user_id))


def get_chat_count(user_id: int, gameweek: int) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT message_count FROM chat_usage WHERE user_id = ? AND gameweek = ?",
            (user_id, gameweek),
        ).fetchone()
    return row["message_count"] if row else 0


def increment_chat_count(user_id: int, gameweek: int) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO chat_usage (user_id, gameweek, message_count) VALUES (?, ?, 1)
            ON CONFLICT(user_id, gameweek) DO UPDATE SET message_count = message_count + 1
            """,
            (user_id, gameweek),
        )


def get_draft(user_id: int) -> dict | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT team_id, gameweek, total_budget_m, data FROM drafts WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "team_id": row["team_id"],
        "gameweek": row["gameweek"],
        "total_budget_m": row["total_budget_m"],
        **json.loads(row["data"]),
    }


def save_draft(user_id: int, team_id: str, gameweek: int, total_budget_m: float, data: dict) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO drafts (user_id, team_id, gameweek, total_budget_m, data, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                team_id = excluded.team_id,
                gameweek = excluded.gameweek,
                total_budget_m = excluded.total_budget_m,
                data = excluded.data,
                updated_at = excluded.updated_at
            """,
            (user_id, team_id, gameweek, total_budget_m, json.dumps(data), datetime.now(timezone.utc).isoformat()),
        )
