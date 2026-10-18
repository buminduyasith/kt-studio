"""Booking, cancelling and checking in. The HTTP layer (server.py) only parses and calls these."""
from datetime import date, datetime, timedelta

from . import notify, rules


class BookingError(Exception):
    """A rule said no. `code` is stable for the frontend; `message` is shown to the receptionist."""

    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _overlaps(start_a, end_a, start_b, end_b) -> bool:
    return start_a < end_b and start_b < end_a


def treatment_minutes(treatment: str) -> int:
    if treatment not in rules.TREATMENTS:
        raise BookingError("unknown_treatment", f"Unknown treatment: {treatment}", 400)
    return rules.TREATMENTS[treatment]["minutes"]


def fits_opening_hours(start: datetime, end: datetime) -> bool:
    """Inside 09:00-17:00, not on Sunday, and not across the 12:00-13:00 lunch break."""
    if start.weekday() in rules.CLOSED_WEEKDAYS:
        return False
    if start.time() < rules.OPENS or end.time() > rules.CLOSES or end.date() != start.date():
        return False
    lunch_start = datetime.combine(start.date(), rules.LUNCH_START)
    lunch_end = datetime.combine(start.date(), rules.LUNCH_END)
    return not _overlaps(start, end, lunch_start, lunch_end)


def busy_ranges(db, dentist_id: int, day: date):
    rows = db.query(
        "SELECT starts_at, ends_at FROM appointments "
        "WHERE dentist_id = ? AND status != ? AND substr(starts_at, 1, 10) = ?",
        (dentist_id, rules.CANCELLED, day.isoformat()),
    )
    return [(_parse(r["starts_at"]), _parse(r["ends_at"])) for r in rows]


def free_slots(db, dentist_id: int, day: date, treatment: str, now: datetime):
    """Every start time on the 15 minute grid where the whole treatment fits and the dentist is free."""
    length = timedelta(minutes=treatment_minutes(treatment))
    busy = busy_ranges(db, dentist_id, day)
    slots = []
    start = datetime.combine(day, rules.OPENS)
    last = datetime.combine(day, rules.CLOSES)
    while start + length <= last:
        end = start + length
        if (
            fits_opening_hours(start, end)
            and start >= now + rules.MIN_NOTICE
            and not any(_overlaps(start, end, b0, b1) for b0, b1 in busy)
        ):
            slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=rules.SLOT_MINUTES)
    return slots


def book(db, staff_id: int, patient_id: int, dentist_id: int, treatment: str, starts_at: str, note: str, now: datetime):
    """Creates a BOOKED appointment and queues its SMS messages, in one transaction."""
    start = _parse(starts_at).replace(second=0, microsecond=0)
    end = start + timedelta(minutes=treatment_minutes(treatment))

    if start.minute % rules.SLOT_MINUTES:
        raise BookingError("off_grid", "Appointments start every 15 minutes.", 400)
    if not fits_opening_hours(start, end):
        raise BookingError("closed", "The clinic is closed then, or the treatment runs into lunch or closing time.")
    if start < now + rules.MIN_NOTICE:
        raise BookingError("too_soon", "Book at least 2 hours ahead.")
    if start > now + rules.MAX_AHEAD:
        raise BookingError("too_far", "Bookings open 60 days ahead.")

    patient = db.one("SELECT id, name FROM patients WHERE id = ?", (patient_id,))
    dentist = db.one("SELECT id, name FROM dentists WHERE id = ?", (dentist_id,))
    if not patient or not dentist:
        raise BookingError("not_found", "Pick a patient and a dentist.", 404)

    with db.transaction() as tx:
        # Checked inside the transaction: two receptionists booking the same slot at once
        # cannot both pass. (BEGIN IMMEDIATE holds the write lock until commit.)
        taken = tx.execute(
            "SELECT 1 FROM appointments WHERE dentist_id = ? AND status != ? AND starts_at < ? AND ends_at > ?",
            (dentist_id, rules.CANCELLED, end.isoformat(), start.isoformat()),
        ).fetchone()
        if taken:
            raise BookingError("slot_taken", f"{dentist['name']} is busy at {start:%H:%M}. Pick another time.")

        upcoming = tx.execute(
            "SELECT COUNT(*) FROM appointments WHERE patient_id = ? AND status = ? AND starts_at > ?",
            (patient_id, rules.BOOKED, now.isoformat()),
        ).fetchone()[0]
        if upcoming >= rules.MAX_UPCOMING_PER_PATIENT:
            raise BookingError("too_many", f"{patient['name']} already has 3 upcoming visits.")

        cur = tx.execute(
            "INSERT INTO appointments(patient_id, dentist_id, treatment, starts_at, ends_at, status, note, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (patient_id, dentist_id, treatment, start.isoformat(), end.isoformat(), rules.BOOKED,
             note.strip()[:200], staff_id, now.isoformat()),
        )
        appointment_id = cur.lastrowid
        notify.queue_booking_messages(tx, appointment_id, patient["name"], dentist["name"], start)
    return get(db, appointment_id)


def cancel(db, appointment_id: int, now: datetime):
    """Cancels a BOOKED appointment. Inside 24 hours of the start it costs the late fee."""
    appt = get(db, appointment_id)
    if appt["status"] != rules.BOOKED:
        raise BookingError("wrong_state", f"Only a booked visit can be cancelled (this one is {appt['status']}).")
    start = _parse(appt["starts_at"])
    fee = rules.LATE_CANCEL_FEE_CENTS if start - now < rules.LATE_CANCEL_WINDOW else 0
    with db.transaction() as tx:
        tx.execute("UPDATE appointments SET status = ?, fee_cents = ? WHERE id = ?", (rules.CANCELLED, fee, appointment_id))
        notify.cancel_messages(tx, appointment_id)
    return get(db, appointment_id)


def check_in(db, appointment_id: int, now: datetime):
    """Marks the patient as arrived. Only from 30 minutes before to 15 minutes after the start."""
    appt = get(db, appointment_id)
    if appt["status"] != rules.BOOKED:
        raise BookingError("wrong_state", f"Only a booked visit can be checked in (this one is {appt['status']}).")
    start = _parse(appt["starts_at"])
    if not (start - rules.CHECK_IN_OPENS <= now <= start + rules.CHECK_IN_CLOSES):
        raise BookingError("check_in_closed", "Check-in opens 30 minutes before the visit and closes 15 minutes after.")
    with db.transaction() as tx:
        tx.execute("UPDATE appointments SET status = ? WHERE id = ?", (rules.CHECKED_IN, appointment_id))
    return get(db, appointment_id)


def get(db, appointment_id: int):
    appt = db.one(
        "SELECT a.*, p.name AS patient, d.name AS dentist, d.room FROM appointments a "
        "JOIN patients p ON p.id = a.patient_id JOIN dentists d ON d.id = a.dentist_id WHERE a.id = ?",
        (appointment_id,),
    )
    if not appt:
        raise BookingError("not_found", "No such appointment.", 404)
    appt["treatment_label"] = rules.TREATMENTS[appt["treatment"]]["label"]
    return appt


def day_schedule(db, day: date):
    rows = db.query(
        "SELECT a.id FROM appointments a WHERE substr(a.starts_at, 1, 10) = ? ORDER BY a.starts_at, a.dentist_id",
        (day.isoformat(),),
    )
    return [get(db, r["id"]) for r in rows]
