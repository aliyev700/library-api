"""Unit tests for the library rules. No HTTP server and no database."""
import sys
import unittest
from datetime import date

import rules

TODAY = date(2026, 3, 15)


def loan(due_date="2026-03-15", returned=0, fine=0, fine_paid=0, renewals=0):
    return {"due_date": due_date, "returned": returned, "fine": fine, "fine_paid": fine_paid, "renewals": renewals}


class FineTests(unittest.TestCase):
    def test_no_fine_when_returned_early_or_on_due_date(self):
        self.assertEqual(rules.fine_for("2026-03-20", TODAY), 0)
        self.assertEqual(rules.fine_for("2026-03-15", TODAY), 0)

    def test_late_loan_costs_fifty_cents_per_day(self):
        self.assertEqual(rules.days_late("2026-03-11", TODAY), 4)
        self.assertEqual(rules.fine_for("2026-03-11", TODAY), 2.0)

    def test_days_late_is_negative_before_the_due_date(self):
        self.assertEqual(rules.days_late("2026-03-20", TODAY), -5)

    def test_open_loan_fine_grows_with_the_date(self):
        self.assertEqual(rules.current_fine(loan("2026-03-10"), TODAY), 2.5)

    def test_returned_loan_keeps_its_recorded_fine(self):
        self.assertEqual(rules.current_fine(loan("2026-03-01", returned=1, fine=1.5), TODAY), 1.5)


class AmountOwedTests(unittest.TestCase):
    def test_on_time_loan_owes_nothing(self):
        self.assertEqual(rules.amount_owed([loan("2026-03-20")], TODAY), 0)

    def test_late_open_loan_is_owed(self):
        self.assertEqual(rules.amount_owed([loan("2026-03-10")], TODAY), 2.5)

    def test_returned_loan_with_unpaid_fine_is_owed(self):
        self.assertEqual(rules.amount_owed([loan("2026-03-01", returned=1, fine=3.0)], TODAY), 3.0)

    def test_returned_loan_with_paid_fine_is_not_owed(self):
        self.assertEqual(rules.amount_owed([loan("2026-03-01", returned=1, fine=3.0, fine_paid=1)], TODAY), 0)

    def test_amounts_add_up_across_loans(self):
        loans = [loan("2026-03-10"), loan("2026-03-01", returned=1, fine=3.0), loan("2026-03-20")]
        self.assertEqual(rules.amount_owed(loans, TODAY), 5.5)

    def test_no_loans_owe_nothing(self):
        self.assertEqual(rules.amount_owed([], TODAY), 0)


class LoanLimitTests(unittest.TestCase):
    def test_student_limit(self):
        self.assertEqual(rules.loan_limit("student"), 3)

    def test_staff_limit(self):
        self.assertEqual(rules.loan_limit("staff"), 5)

    def test_only_open_loans_count(self):
        self.assertEqual(rules.open_loan_count([loan(), loan(returned=1), loan()]), 2)

    def test_loans_remaining(self):
        self.assertEqual(rules.loans_remaining([loan(), loan(returned=1)], "student"), 2)
        self.assertEqual(rules.loans_remaining([loan(), loan(returned=1)], "staff"), 4)

    def test_checkout_blocked_by_student_limit_but_not_for_staff(self):
        three_open = [loan("2026-03-20")] * 3
        self.assertEqual(rules.checkout_block(three_open, "student", TODAY), "loan limit reached")
        self.assertIsNone(rules.checkout_block(three_open, "staff", TODAY))

    def test_checkout_blocked_by_unpaid_fines(self):
        self.assertEqual(rules.checkout_block([loan("2026-03-10")], "staff", TODAY), "member has unpaid fines")


class RenewalTests(unittest.TestCase):
    def test_can_renew_before_and_on_due_date(self):
        self.assertTrue(rules.can_renew(loan("2026-03-20"), TODAY))
        self.assertTrue(rules.can_renew(loan("2026-03-15"), TODAY))

    def test_cannot_renew_overdue_loan(self):
        self.assertFalse(rules.can_renew(loan("2026-03-14"), TODAY))
        self.assertEqual(rules.renewal_block(loan("2026-03-14"), TODAY), "overdue loans cannot be renewed")

    def test_cannot_renew_twice(self):
        self.assertFalse(rules.can_renew(loan("2026-03-20", renewals=1), TODAY))
        self.assertEqual(rules.renewal_block(loan("2026-03-20", renewals=1), TODAY), "loan was already renewed")

    def test_cannot_renew_returned_loan(self):
        self.assertFalse(rules.can_renew(loan("2026-03-20", returned=1), TODAY))
        self.assertEqual(rules.renewal_block(loan("2026-03-20", returned=1), TODAY), "loan already returned")

    def test_renewal_adds_fourteen_days_to_due_date(self):
        self.assertEqual(rules.renewed_due_date("2026-03-20"), "2026-04-03")


class DueDateTests(unittest.TestCase):
    def test_default_due_date_is_fourteen_days_away(self):
        self.assertEqual(rules.default_due_date(TODAY), "2026-03-29")


class IsolationTests(unittest.TestCase):
    def test_rules_do_not_load_flask_or_sqlite(self):
        import subprocess

        code = "import sys, rules; print('flask' in sys.modules or 'sqlite3' in sys.modules)"
        output = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
        self.assertEqual(output.strip(), "False")


if __name__ == "__main__":
    unittest.main()
