"""SQLite storage. One file, created and seeded on first start."""
import sqlite3
import threading
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS dentists (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    room TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS appointments (
    id INTEGER PRIMARY KEY,
    patient_id INTEGER NOT NULL REFERENCES patients(id),
    dentist_id INTEGER NOT NULL REFERENCES dentists(id),
    treatment TEXT NOT NULL,
    starts_at TEXT NOT NULL,          -- local time, ISO 8601, minute precision
    ends_at TEXT NOT NULL,
    status TEXT NOT NULL,             -- BOOKED, CHECKED_IN, CANCELLED
    fee_cents INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    created_by INTEGER NOT NULL REFERENCES staff(id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS appointments_dentist_day ON appointments(dentist_id, starts_at);
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY,
    appointment_id INTEGER NOT NULL REFERENCES appointments(id),
    channel TEXT NOT NULL,            -- sms
    send_at TEXT NOT NULL,
    body TEXT NOT NULL,
    sent INTEGER NOT NULL DEFAULT 0
);
"""

SEED_DENTISTS = [("Dr. Amara Perera", "Room 1"), ("Dr. Kamal Silva", "Room 2"), ("Dr. Nisha Fernando", "Room 3")]
SEED_PATIENTS = [
    ("Ruwan Jayasinghe", "+94 77 000 0101"),
    ("Dilini Wickrama", "+94 77 000 0102"),
    ("Tharindu Bandara", "+94 77 000 0103"),
    ("Sachini Gunawardena", "+94 77 000 0104"),
]


class Database:
    """A thread-safe wrapper: the HTTP server handles each request on its own thread."""

    def __init__(self, path: Path):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._conn.executescript(SCHEMA)

    def query(self, sql, params=()):
        with self._lock:
            return [dict(r) for r in self._conn.execute(sql, params).fetchall()]

    def one(self, sql, params=()):
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def transaction(self):
        """Use as `with db.transaction() as tx:`; commits on success, rolls back on error."""
        return _Tx(self)

    def seed(self, staff_email, staff_name, password_hash):
        with self.transaction() as tx:
            if not tx.execute("SELECT 1 FROM dentists").fetchone():
                tx.executemany("INSERT INTO dentists(name, room) VALUES (?, ?)", SEED_DENTISTS)
                tx.executemany("INSERT INTO patients(name, phone) VALUES (?, ?)", SEED_PATIENTS)
            tx.execute(
                "INSERT INTO staff(email, name, password_hash) VALUES (?, ?, ?) "
                "ON CONFLICT(email) DO UPDATE SET password_hash = excluded.password_hash",
                (staff_email, staff_name, password_hash),
            )


class _Tx:
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        self.db._lock.acquire()
        self.db._conn.execute("BEGIN IMMEDIATE")
        return self.db._conn

    def __exit__(self, exc_type, *_):
        try:
            if exc_type:
                self.db._conn.rollback()
            else:
                self.db._conn.commit()
        finally:
            self.db._lock.release()
