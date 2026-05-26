import hashlib
import sqlite3
import uuid
from datetime import datetime

DB_PATH = "users.db"


def init_db():
    """Create database tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            name            TEXT NOT NULL,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            token           TEXT,
            share_token     TEXT UNIQUE,
            created_at      TEXT,
            last_seen       TEXT,
            latitude        REAL,
            longitude       REAL,
            battery_level   REAL,
            battery_charging INTEGER DEFAULT 0
        )"""
    )
    # Add share_token column to existing DBs created before this migration.
    # Note: SQLite's ALTER TABLE does NOT support inline constraints like UNIQUE,
    # so we add the column plain and create the index separately.
    try:
        c.execute("ALTER TABLE users ADD COLUMN share_token TEXT")
    except Exception:
        pass  # column already exists
    c.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_share_token ON users(share_token)"
    )
    conn.commit()
    conn.close()


def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(name: str, email: str, password: str) -> dict | None:
    """
    Create a new user and return their record, or None if email already exists.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    user_id = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    try:
        c.execute(
            "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, email.lower().strip(), _hash(password), now),
        )
        conn.commit()
        return {"id": user_id, "name": name, "email": email, "created_at": now}
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()


def login_user(email: str, password: str) -> tuple:
    """
    Validate credentials, generate a fresh session token.
    Returns (user_id, token, name) on success, (None, None, None) on failure.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, name FROM users WHERE email=? AND password_hash=?",
        (email.lower().strip(), _hash(password)),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return None, None, None

    user_id, name = row
    token = str(uuid.uuid4())
    c.execute("UPDATE users SET token=? WHERE id=?", (token, user_id))
    conn.commit()
    conn.close()
    return user_id, token, name


def get_user_by_token(token: str) -> dict | None:
    """Return user info dict for a valid session token, or None."""
    if not token:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """SELECT id, name, email, latitude, longitude,
                  battery_level, battery_charging, last_seen
           FROM users WHERE token=?""",
        (token,),
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "name": row[1],
        "email": row[2],
        "latitude": row[3],
        "longitude": row[4],
        "battery_level": row[5],
        "battery_charging": bool(row[6]),
        "last_seen": row[7],
    }


def update_device_info(
    token: str,
    latitude: float,
    longitude: float,
    battery_level: float,
    battery_charging: bool,
) -> bool:
    """Persist the device's latest location + battery for the given session token."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.utcnow().isoformat()
    c.execute(
        """UPDATE users
           SET latitude=?, longitude=?, battery_level=?, battery_charging=?, last_seen=?
           WHERE token=?""",
        (latitude, longitude, battery_level, int(battery_charging), now, token),
    )
    updated = c.rowcount > 0
    conn.commit()
    conn.close()
    return updated


def logout_user(token: str) -> None:
    """Invalidate the session token."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET token=NULL WHERE token=?", (token,))
    conn.commit()
    conn.close()


def get_or_create_share_token(session_token: str) -> str | None:
    """
    Return the persistent share token for the user identified by their session
    token. Creates one if it doesn't exist yet.
    Returns None if the session token is invalid.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, share_token FROM users WHERE token=?", (session_token,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    user_id, share_token = row
    if not share_token:
        share_token = str(uuid.uuid4())
        c.execute("UPDATE users SET share_token=? WHERE id=?", (share_token, user_id))
        conn.commit()
    conn.close()
    return share_token


def get_location_by_share_token(share_token: str) -> dict | None:
    """
    Return publicly shareable location data for a share token.
    Returns None if the token is unknown or the user has no location yet.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """SELECT name, latitude, longitude, battery_level, battery_charging, last_seen
           FROM users WHERE share_token=?""",
        (share_token,),
    )
    row = c.fetchone()
    conn.close()
    if not row or row[1] is None:
        return None
    return {
        "name": row[0],
        "latitude": row[1],
        "longitude": row[2],
        "battery_level": row[3],
        "battery_charging": bool(row[4]),
        "last_seen": row[5],
    }
