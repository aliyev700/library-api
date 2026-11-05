from datetime import date, timedelta

import config


def money(amount):
    return round(float(amount), 2)


def days_late(due_date, today):
    return (today - date.fromisoformat(due_date)).days


def is_late(due_date, today):
    return days_late(due_date, today) > 0


def fine_for(due_date, today):
    return max(0, days_late(due_date, today)) * config.FINE_PER_DAY


def is_overdue(loan, today):
    return not loan["returned"] and is_late(loan["due_date"], today)


def current_fine(loan, today):
    if loan["returned"]:
        return loan["fine"]
    return fine_for(loan["due_date"], today)


def outstanding_fine(loan, today):
    if loan["returned"] and loan["fine_paid"]:
        return 0
    return current_fine(loan, today)


def amount_owed(loans, today):
    return sum(outstanding_fine(loan, today) for loan in loans)


def open_loan_count(loans):
    return sum(1 for loan in loans if not loan["returned"])


def loan_limit(member_type):
    if member_type == "staff":
        return config.LOAN_LIMITS["staff"]
    return config.LOAN_LIMITS["student"]


def loans_remaining(loans, member_type):
    return loan_limit(member_type) - open_loan_count(loans)


def checkout_block(loans, member_type, today):
    if amount_owed(loans, today) > 0:
        return "member has unpaid fines"
    if loans_remaining(loans, member_type) <= 0:
        return "loan limit reached"
    return None


def default_due_date(today):
    return (today + timedelta(days=config.LOAN_DAYS)).isoformat()


def renewed_due_date(due_date):
    return (date.fromisoformat(due_date) + timedelta(days=config.RENEWAL_DAYS)).isoformat()


def renewal_block(loan, today):
    if loan["returned"]:
        return "loan already returned"
    if is_late(loan["due_date"], today):
        return "overdue loans cannot be renewed"
    if loan["renewals"] >= config.MAX_RENEWALS:
        return "loan was already renewed"
    return None


def can_renew(loan, today):
    return renewal_block(loan, today) is None


def payment_block(loan):
    if not loan["returned"]:
        return "return the book before paying"
    if loan["fine"] <= 0 or loan["fine_paid"]:
        return "no fine to pay"
    return None
