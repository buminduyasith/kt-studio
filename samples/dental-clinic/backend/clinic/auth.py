"""Staff login. Passwords are stored as PBKDF2 hashes; sessions live in memory for 8 hours."""
import hashlib
import hmac
import os
import secrets
import time

SESSION_HOURS = 8
COOKIE = "clinic_session"
_ITERATIONS = 200_000
_sessions = {}  # token -> (staff_id, expires_at)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def check_password(password: str, stored: str) -> bool:
    salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


def login(db, email: str, password: str):
    """Returns a session token, or None. The same answer for a wrong email and a wrong password."""
    staff = db.one("SELECT id, password_hash FROM staff WHERE email = ?", (email.strip().lower(),))
    if not staff or not check_password(password, staff["password_hash"]):
        return None
    token = secrets.token_urlsafe(32)
    _sessions[token] = (staff["id"], time.time() + SESSION_HOURS * 3600)
    return token


def staff_for(token):
    entry = _sessions.get(token or "")
    if not entry or entry[1] < time.time():
        _sessions.pop(token or "", None)
        return None
    return entry[0]


def logout(token):
    _sessions.pop(token or "", None)
