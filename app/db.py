from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from . import config

_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id     INTEGER PRIMARY KEY,
    username    TEXT,
    first_name  TEXT,
    last_name   TEXT,
    phone       TEXT,
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS users_username ON users(lower(username));

CREATE TABLE IF NOT EXISTS bookings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    barber_id    INTEGER NOT NULL,
    date         TEXT NOT NULL,          -- YYYY-MM-DD
    time         TEXT NOT NULL,          -- HH:MM
    kind         TEXT NOT NULL DEFAULT 'client',   -- client | blocked
    user_id      INTEGER,
    name         TEXT,
    username     TEXT,
    phone        TEXT,
    status       TEXT NOT NULL DEFAULT 'active',   -- active | cancelled
    reminded     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    cancelled_at TEXT,
    cancelled_by INTEGER
);
CREATE UNIQUE INDEX IF NOT EXISTS bookings_slot
    ON bookings(barber_id, date, time) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS bookings_user ON bookings(user_id, status);
"""


def conn() -> sqlite3.Connection:
    assert _conn is not None, "db.init() chaqirilmagan"
    return _conn


def init() -> None:
    global _conn
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False, isolation_level=None)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.executescript(SCHEMA)


def _ts() -> str:
    return datetime.now(config.TZ).isoformat(timespec="seconds")


# ---------- users ----------

def upsert_user(user_id: int, username: Optional[str], first_name: Optional[str], last_name: Optional[str]) -> None:
    conn().execute(
        """INSERT INTO users(user_id, username, first_name, last_name, updated_at) VALUES (?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, first_name=excluded.first_name,
           last_name=excluded.last_name, updated_at=excluded.updated_at""",
        (user_id, username, first_name, last_name, _ts()),
    )


def set_phone(user_id: int, phone: str) -> None:
    conn().execute(
        """INSERT INTO users(user_id, phone, updated_at) VALUES (?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET phone=excluded.phone, updated_at=excluded.updated_at""",
        (user_id, phone, _ts()),
    )


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    return conn().execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()


def user_id_by_username(username: str) -> Optional[int]:
    row = conn().execute(
        "SELECT user_id FROM users WHERE lower(username)=? ORDER BY updated_at DESC LIMIT 1",
        (username.lower(),),
    ).fetchone()
    return row["user_id"] if row else None


# ---------- bookings ----------

def active_in_range(date_from: str, date_to: str) -> List[sqlite3.Row]:
    return conn().execute(
        "SELECT * FROM bookings WHERE status='active' AND date BETWEEN ? AND ? ORDER BY date, time, barber_id",
        (date_from, date_to),
    ).fetchall()


def create_booking(barber_id: int, d: str, t: str, kind: str, user_id: Optional[int], name: Optional[str],
                   username: Optional[str], phone: Optional[str], reminded: bool = False) -> Optional[int]:
    """Slot band bo'lsa None qaytaradi (unique index bilan himoyalangan)."""
    try:
        cur = conn().execute(
            """INSERT INTO bookings(barber_id, date, time, kind, user_id, name, username, phone, reminded, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (barber_id, d, t, kind, user_id, name, username, phone, int(reminded), _ts()),
        )
        return cur.lastrowid
    except sqlite3.IntegrityError:
        return None


def get_booking(booking_id: int) -> Optional[sqlite3.Row]:
    return conn().execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()


def user_active_booking(user_id: int, now_key: str) -> Optional[sqlite3.Row]:
    return conn().execute(
        """SELECT * FROM bookings WHERE user_id=? AND status='active' AND kind='client'
           AND (date || ' ' || time) >= ? ORDER BY date, time LIMIT 1""",
        (user_id, now_key),
    ).fetchone()


def cancel_booking(booking_id: int, by_user_id: int) -> bool:
    cur = conn().execute(
        "UPDATE bookings SET status='cancelled', cancelled_at=?, cancelled_by=? WHERE id=? AND status='active'",
        (_ts(), by_user_id, booking_id),
    )
    return cur.rowcount > 0


def unreminded(date_from: str, date_to: str) -> List[sqlite3.Row]:
    return conn().execute(
        """SELECT * FROM bookings WHERE status='active' AND kind='client' AND reminded=0
           AND user_id IS NOT NULL AND date BETWEEN ? AND ?""",
        (date_from, date_to),
    ).fetchall()


def mark_reminded(booking_id: int) -> None:
    conn().execute("UPDATE bookings SET reminded=1 WHERE id=?", (booking_id,))
