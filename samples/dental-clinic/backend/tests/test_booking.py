import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clinic import auth, booking, rules  # noqa: E402
from clinic.db import Database  # noqa: E402

MONDAY_8AM = datetime(2026, 10, 19, 8, 0)


class BookingTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / "t.db")
        self.db.seed("t@smile.test", "Test", auth.hash_password("pw"))

    def tearDown(self):
        self.tmp.cleanup()

    def book(self, at, patient=1, dentist=1, treatment="checkup", now=MONDAY_8AM):
        return booking.book(self.db, 1, patient, dentist, treatment, at, "", now)

    def test_books_a_free_slot_and_queues_messages(self):
        appt = self.book("2026-10-21T10:00")
        self.assertEqual(appt["status"], rules.BOOKED)
        self.assertEqual(appt["ends_at"], "2026-10-21T10:30:00")
        self.assertEqual(len(self.db.query("SELECT * FROM outbox")), 2)

    def test_rejects_double_booking_of_the_same_dentist(self):
        self.book("2026-10-21T10:00", treatment="filling")
        with self.assertRaises(booking.BookingError) as e:
            self.book("2026-10-21T10:30", patient=2)
        self.assertEqual(e.exception.code, "slot_taken")

    def test_other_dentist_can_take_the_same_time(self):
        self.book("2026-10-21T10:00")
        self.assertEqual(self.book("2026-10-21T10:00", patient=2, dentist=2)["status"], rules.BOOKED)

    def test_treatment_cannot_run_into_lunch(self):
        with self.assertRaises(booking.BookingError) as e:
            self.book("2026-10-21T11:30", treatment="filling")
        self.assertEqual(e.exception.code, "closed")

    def test_needs_two_hours_notice(self):
        with self.assertRaises(booking.BookingError) as e:
            self.book("2026-10-19T09:30")
        self.assertEqual(e.exception.code, "too_soon")

    def test_at_most_three_upcoming_visits(self):
        for day in (20, 21, 22):
            self.book(f"2026-10-{day}T09:00")
        with self.assertRaises(booking.BookingError) as e:
            self.book("2026-10-23T09:00")
        self.assertEqual(e.exception.code, "too_many")

    def test_late_cancel_costs_the_fee(self):
        appt = self.book("2026-10-20T09:00")
        cancelled = booking.cancel(self.db, appt["id"], datetime(2026, 10, 19, 15, 0))
        self.assertEqual(cancelled["fee_cents"], rules.LATE_CANCEL_FEE_CENTS)
        self.assertEqual(self.db.query("SELECT * FROM outbox WHERE sent = 0"), [])

    def test_early_cancel_is_free(self):
        appt = self.book("2026-10-22T09:00")
        self.assertEqual(booking.cancel(self.db, appt["id"], MONDAY_8AM)["fee_cents"], 0)

    def test_check_in_window(self):
        appt = self.book("2026-10-21T10:00")
        with self.assertRaises(booking.BookingError):
            booking.check_in(self.db, appt["id"], datetime(2026, 10, 21, 9, 0))
        done = booking.check_in(self.db, appt["id"], datetime(2026, 10, 21, 9, 40))
        self.assertEqual(done["status"], rules.CHECKED_IN)

    def test_free_slots_skip_lunch_and_taken_times(self):
        self.book("2026-10-21T09:00")
        slots = booking.free_slots(self.db, 1, date(2026, 10, 21), "filling", MONDAY_8AM)
        self.assertNotIn("09:00", slots)
        self.assertNotIn("11:30", slots)   # would run into lunch
        self.assertIn("13:00", slots)
        self.assertEqual(slots[-1], "16:00")


if __name__ == "__main__":
    unittest.main()
