"""Tiny SQLite layer. One file on disk, no database server to maintain."""
import logging
import os
import secrets
import sqlite3
from contextlib import contextmanager

log = logging.getLogger("mahlzeit.db")

DB_PATH = os.environ.get("MAHLZEIT_DB", os.path.join(os.path.dirname(__file__), "..", "mahlzeit.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    NOT NULL UNIQUE,
    lunch_id    TEXT    UNIQUE,           -- random public ID shown instead of a name
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    last_login  TEXT
);

-- Magic-link tokens. Only a SHA-256 hash is stored, never the token itself,
-- so a leaked database file cannot be used to log in.
CREATE TABLE IF NOT EXISTS login_tokens (
    token_hash  TEXT    PRIMARY KEY,
    email       TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT    NOT NULL,
    used        INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_tokens_email ON login_tokens(email);

-- One lunch profile per user, filled in over three pages. Columns stay empty
-- until their page is saved; completed = 1 once the last page is done.
-- Deliberately no name, nationality, birthday, photo, phone or dietary info.
CREATE TABLE IF NOT EXISTS profiles (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    -- page 1: about you
    role          TEXT CHECK (role IN ('newcomer', 'local')),
    faculty       TEXT,
    languages     TEXT,   -- JSON list of language codes
    answers       TEXT,   -- JSON {"food": "Döner", ...}
    -- page 2: where & when
    city          TEXT,
    mensa         TEXT,   -- id from options.MENSAS
    slots         TEXT,   -- JSON list like ["Mon-12:30", ...]
    -- page 3: who you'd like to meet
    age           INTEGER,             -- from the slider; AGE_MAX means "40 or older"
    age_min       INTEGER,             -- age range they'd like at their table
    age_max       INTEGER,
    friend_email  TEXT,
    consent_at    TEXT,
    completed     INTEGER NOT NULL DEFAULT 0,
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Matching results. Each "Run matching" creates a round; the latest one is shown.
CREATE TABLE IF NOT EXISTS match_rounds (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS match_tables (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    round_id     INTEGER NOT NULL REFERENCES match_rounds(id) ON DELETE CASCADE,
    table_no     INTEGER NOT NULL,
    mensa        TEXT    NOT NULL,
    slot         TEXT    NOT NULL,
    score        REAL    NOT NULL,
    languages    TEXT    NOT NULL,   -- JSON list
    icebreakers  TEXT    NOT NULL,   -- JSON list
    checkin_code TEXT                -- 4 digits, printed on the table card at the Mensa
);
CREATE TABLE IF NOT EXISTS match_seats (
    table_id  INTEGER NOT NULL REFERENCES match_tables(id) ON DELETE CASCADE,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    animal    TEXT,                       -- e.g. "fox": unique within the table
    checked_in_at   TEXT,                 -- set when the right table code was entered
    failed_checkins INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (table_id, user_id)
);

-- Optional feedback after the lunch. Every answer is optional.
CREATE TABLE IF NOT EXISTS feedback (
    table_id    INTEGER NOT NULL REFERENCES match_tables(id) ON DELETE CASCADE,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    attended    TEXT CHECK (attended IN ('yes', 'no')),
    rating      INTEGER CHECK (rating BETWEEN 1 AND 5),
    meet_again  TEXT CHECK (meet_again IN ('yes', 'no')),
    join_again  TEXT CHECK (join_again IN ('yes', 'maybe', 'no')),
    comment     TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (table_id, user_id)
);

-- Reports about a tablemate. The reported person never sees who reported them.
-- A reported pair is never seated together again (see rounds.load_profiles).
CREATE TABLE IF NOT EXISTS reports (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    table_id     INTEGER REFERENCES match_tables(id) ON DELETE SET NULL,
    reporter_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reported_id  INTEGER REFERENCES users(id) ON DELETE CASCADE,   -- NULL = "not sure which person"
    category     TEXT    NOT NULL,
    details      TEXT,
    contact_ok   INTEGER NOT NULL DEFAULT 0,   -- reporter agrees the team may contact them
    status       TEXT    NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'resolved')),
    created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
    resolved_at  TEXT
);

-- Every time the team reveals an email behind a report, it's logged here.
CREATE TABLE IF NOT EXISTS reveal_log (
    report_id    INTEGER NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    admin_email  TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""

LUNCH_ID_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I lookalikes


def new_lunch_id(conn) -> str:
    """Random 6-character ID. Not derived from the email, so it can't be traced back."""
    while True:
        lid = "".join(secrets.choice(LUNCH_ID_ALPHABET) for _ in range(6))
        if not conn.execute("SELECT 1 FROM users WHERE lunch_id = ?", (lid,)).fetchone():
            return lid


def new_checkin_code() -> str:
    return f"{secrets.randbelow(10000):04d}"


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")  # so deleting a user also deletes their data
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _columns(conn, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}


def _migrate(conn) -> None:
    """Upgrade databases created by earlier prototype versions."""
    if "first_name" in _columns(conn, "profiles") or "campus" in _columns(conn, "match_tables"):
        # The profile changed shape (no names, Mensa instead of campus, 3 pages).
        # Old test profiles can't be converted, so they're cleared; accounts are kept.
        log.warning("Old database format: clearing profiles and matching rounds (accounts are kept).")
        conn.executescript("""
            DROP TABLE IF EXISTS feedback;
            DROP TABLE IF EXISTS match_seats;
            DROP TABLE IF EXISTS match_tables;
            DROP TABLE IF EXISTS match_rounds;
            DROP TABLE IF EXISTS profiles;
        """)
    cols = _columns(conn, "profiles")
    if cols and "age" not in cols:
        # Age groups were replaced by sliders: add the new columns and ask people
        # to redo the last page (their other answers are kept).
        for c in ("age", "age_min", "age_max"):
            conn.execute(f"ALTER TABLE profiles ADD COLUMN {c} INTEGER")
        conn.execute("UPDATE profiles SET completed = 0")
    seat_cols = _columns(conn, "match_seats")
    if seat_cols and "animal" not in seat_cols:
        conn.execute("ALTER TABLE match_seats ADD COLUMN animal TEXT")
    if seat_cols and "checked_in_at" not in seat_cols:
        conn.execute("ALTER TABLE match_seats ADD COLUMN checked_in_at TEXT")
        conn.execute("ALTER TABLE match_seats ADD COLUMN failed_checkins INTEGER NOT NULL DEFAULT 0")
    table_cols = _columns(conn, "match_tables")
    if table_cols and "checkin_code" not in table_cols:
        conn.execute("ALTER TABLE match_tables ADD COLUMN checkin_code TEXT")
    if _columns(conn, "users") and "lunch_id" not in _columns(conn, "users"):
        conn.execute("ALTER TABLE users ADD COLUMN lunch_id TEXT")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_lunch_id ON users(lunch_id)")


def init_db() -> None:
    with connect() as conn:
        _migrate(conn)
        conn.executescript(SCHEMA)
        # Tables from older versions get a check-in code too.
        for row in conn.execute("SELECT id FROM match_tables WHERE checkin_code IS NULL").fetchall():
            conn.execute("UPDATE match_tables SET checkin_code = ? WHERE id = ?", (new_checkin_code(), row["id"]))
        # Give every account a Lunch ID (covers accounts from older versions).
        for row in conn.execute("SELECT id FROM users WHERE lunch_id IS NULL").fetchall():
            conn.execute("UPDATE users SET lunch_id = ? WHERE id = ?", (new_lunch_id(conn), row["id"]))
