"""Booking rules for Smile Dental. Every number the front desk asks about lives here.

Changing a rule? Update docs/booking-rules.md and the tests in tests/test_booking.py too.
"""
from datetime import time, timedelta

# Opening hours, Monday to Saturday. Sunday is closed.
OPENS = time(9, 0)
CLOSES = time(17, 0)
LUNCH_START = time(12, 0)
LUNCH_END = time(13, 0)
CLOSED_WEEKDAYS = {6}  # Monday is 0, Sunday is 6

# Appointments start on a 15 minute grid: 09:00, 09:15, 09:30, ...
SLOT_MINUTES = 15

# Treatment length in minutes. A treatment must fit before lunch or before closing.
TREATMENTS = {
    "checkup": {"label": "Check-up", "minutes": 30},
    "cleaning": {"label": "Cleaning", "minutes": 45},
    "filling": {"label": "Filling", "minutes": 60},
    "root-canal": {"label": "Root canal", "minutes": 90},
}

# How far ahead a patient can book.
MIN_NOTICE = timedelta(hours=2)
MAX_AHEAD = timedelta(days=60)

# A patient may hold at most this many upcoming appointments.
MAX_UPCOMING_PER_PATIENT = 3

# Cancelling less than 24 hours before the start costs a late fee (in cents).
LATE_CANCEL_WINDOW = timedelta(hours=24)
LATE_CANCEL_FEE_CENTS = 2500

# Check-in opens 30 minutes before the start and closes 15 minutes after it.
CHECK_IN_OPENS = timedelta(minutes=30)
CHECK_IN_CLOSES = timedelta(minutes=15)

# Appointment states. BOOKED -> CHECKED_IN, BOOKED -> CANCELLED. Nothing else.
BOOKED = "BOOKED"
CHECKED_IN = "CHECKED_IN"
CANCELLED = "CANCELLED"
