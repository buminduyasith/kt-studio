"""Smile Dental HTTP server: the JSON API under /api and the frontend files.

Run:  CLINIC_TEST_PASSWORD=... python3 server.py   (then open http://localhost:8040)
"""
import json
import os
import re
import sys
from datetime import date, datetime
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from clinic import auth, booking, rules
from clinic.db import Database

HERE = Path(__file__).resolve().parent
FRONTEND = Path(os.environ.get("CLINIC_FRONTEND", HERE.parent / "frontend")).resolve()
PORT = int(os.environ.get("CLINIC_PORT", "8040"))
TYPES = {".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".svg": "image/svg+xml"}

ROUTES = []  # (method, compiled path pattern, handler, needs login)


def route(method, pattern, public=False):
    def register(fn):
        ROUTES.append((method, re.compile(f"^{pattern}$"), fn, not public))
        return fn
    return register


def now():
    """The clinic's clock. CLINIC_NOW pins it for demos and tests (for example 2026-10-19T08:00)."""
    pinned = os.environ.get("CLINIC_NOW")
    return datetime.fromisoformat(pinned) if pinned else datetime.now().replace(second=0, microsecond=0)


class Handler(BaseHTTPRequestHandler):
    db: Database = None

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # ---- plumbing -------------------------------------------------------------------------
    def _send(self, status, body, ctype="application/json", extra_headers=()):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        for k, v in extra_headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _token(self):
        jar = cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return jar[auth.COOKIE].value if auth.COOKIE in jar else None

    def _dispatch(self, method):
        url = urlparse(self.path)
        if not url.path.startswith("/api/"):
            return self._static(url.path)
        for m, pattern, fn, needs_login in ROUTES:
            match = pattern.match(url.path)
            if m != method or not match:
                continue
            staff_id = auth.staff_for(self._token())
            if needs_login and not staff_id:
                return self._send(401, {"error": "login_required", "message": "Please log in."})
            try:
                query = {k: v[0] for k, v in parse_qs(url.query).items()}
                return fn(self, staff_id=staff_id, query=query, **match.groupdict())
            except booking.BookingError as e:
                return self._send(e.status, {"error": e.code, "message": e.message})
        self._send(404, {"error": "not_found", "message": "No such endpoint."})

    def _static(self, path):
        target = (FRONTEND / (path.lstrip("/") or "index.html")).resolve()
        if not str(target).startswith(str(FRONTEND)) or not target.is_file():
            target = FRONTEND / "index.html"  # the single-page app handles its own routes
        self._send(200, target.read_bytes(), TYPES.get(target.suffix, "application/octet-stream"))

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")


# ---- API -------------------------------------------------------------------------------------
@route("POST", "/api/login", public=True)
def login(req, **_):
    body = req._json_body()
    token = auth.login(req.db, body.get("email", ""), body.get("password", ""))
    if not token:
        return req._send(401, {"error": "bad_login", "message": "Email or password is wrong."})
    cookie = f"{auth.COOKIE}={token}; HttpOnly; SameSite=Lax; Path=/; Max-Age={auth.SESSION_HOURS * 3600}"
    req._send(200, {"ok": True}, extra_headers=[("Set-Cookie", cookie)])


@route("POST", "/api/logout")
def logout(req, **_):
    auth.logout(req._token())
    req._send(200, {"ok": True}, extra_headers=[("Set-Cookie", f"{auth.COOKIE}=; Path=/; Max-Age=0")])


@route("GET", "/api/me")
def me(req, staff_id, **_):
    req._send(200, req.db.one("SELECT id, email, name FROM staff WHERE id = ?", (staff_id,)))


@route("GET", "/api/options")
def options(req, **_):
    """Everything the booking form needs in one call."""
    req._send(200, {
        "dentists": req.db.query("SELECT id, name, room FROM dentists ORDER BY id"),
        "patients": req.db.query("SELECT id, name FROM patients ORDER BY name"),
        "treatments": [{"id": k, **v} for k, v in rules.TREATMENTS.items()],
        "today": now().date().isoformat(),
    })


@route("GET", "/api/slots")
def slots(req, query, **_):
    day = date.fromisoformat(query["date"])
    free = booking.free_slots(req.db, int(query["dentist"]), day, query["treatment"], now())
    req._send(200, {"date": day.isoformat(), "slots": free})


@route("GET", "/api/appointments")
def appointments(req, query, **_):
    day = date.fromisoformat(query.get("date") or now().date().isoformat())
    req._send(200, {"date": day.isoformat(), "appointments": booking.day_schedule(req.db, day)})


@route("POST", "/api/appointments")
def create(req, staff_id, **_):
    b = req._json_body()
    appt = booking.book(req.db, staff_id, int(b["patientId"]), int(b["dentistId"]), b["treatment"],
                        f"{b['date']}T{b['time']}", b.get("note", ""), now())
    req._send(201, appt)


@route("POST", r"/api/appointments/(?P<appt_id>\d+)/cancel")
def cancel(req, appt_id, **_):
    req._send(200, booking.cancel(req.db, int(appt_id), now()))


@route("POST", r"/api/appointments/(?P<appt_id>\d+)/check-in")
def check_in(req, appt_id, **_):
    req._send(200, booking.check_in(req.db, int(appt_id), now()))


def main():
    password = os.environ.get("CLINIC_TEST_PASSWORD")
    if not password:
        sys.exit("Set CLINIC_TEST_PASSWORD: the password for the seeded receptionist account.")
    db = Database(Path(os.environ.get("CLINIC_DB", HERE / "clinic.db")))
    db.seed("reception@smile.test", "Front Desk", auth.hash_password(password))
    Handler.db = db
    print(f"Smile Dental on http://localhost:{PORT} (login: reception@smile.test)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
