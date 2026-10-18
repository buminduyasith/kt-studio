"""Patient messages. Nothing is sent here: messages go to the outbox table, and the
SMS sender (a separate cron job, not in this repo) picks them up when send_at has passed."""
from datetime import datetime, timedelta

REMINDER_BEFORE = timedelta(hours=24)


def queue_booking_messages(tx, appointment_id: int, patient_name: str, dentist_name: str, starts: datetime):
    now = datetime.now().replace(second=0, microsecond=0)
    when = starts.strftime("%A %d %B at %H:%M")
    tx.execute(
        "INSERT INTO outbox(appointment_id, channel, send_at, body) VALUES (?, 'sms', ?, ?)",
        (appointment_id, now.isoformat(), f"Hi {patient_name}, your visit with {dentist_name} is booked for {when}."),
    )
    remind_at = starts - REMINDER_BEFORE
    # A booking made less than a day ahead gets no reminder: the confirmation is enough.
    if remind_at > now:
        tx.execute(
            "INSERT INTO outbox(appointment_id, channel, send_at, body) VALUES (?, 'sms', ?, ?)",
            (appointment_id, remind_at.isoformat(), f"Reminder: {dentist_name} tomorrow at {starts:%H:%M}."),
        )


def cancel_messages(tx, appointment_id: int):
    """Drops reminders that were not sent yet."""
    tx.execute("DELETE FROM outbox WHERE appointment_id = ? AND sent = 0", (appointment_id,))
