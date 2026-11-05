import config
from rules import money


def send(to_email, subject, body):
    with open(config.OUTBOX_PATH, "a") as f:
        f.write("TO: " + to_email + " | SUBJECT: " + subject + " | BODY: " + body + "\n")


def book_checked_out(to_email, title):
    send(to_email, "Book checked out", "You checked out " + title)


def loan_renewed(to_email, title):
    send(to_email, "Loan renewed", "You renewed " + title)


def book_returned(to_email, title, fine):
    send(to_email, "Book returned", "You returned " + title + ". Fine: $" + str(money(fine)))


def fine_paid(to_email, amount):
    send(to_email, "Fine paid", "We received $" + str(money(amount)))
