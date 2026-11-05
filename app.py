import os
import re
from datetime import date

from flask import Flask, jsonify, request

import config
import db
import rules
from db import init_db

app = Flask(__name__)

CURRENT_MEMBER = None


# ---------- helpers ----------


def check(value, kind):
    if kind == "email":
        return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", str(value)) is not None
    elif kind == "isbn":
        digits = str(value).replace("-", "")
        return digits.isdigit() and len(digits) in (10, 13)
    elif kind == "date":
        try:
            date.fromisoformat(str(value))
            return True
        except ValueError:
            return False
    elif kind == "member_type":
        return value in config.MEMBER_TYPES
    return False


def notify(kind, title="", send=True):
    if not send:
        return
    if kind == "checkout":
        subject = "Book checked out"
        body = "You checked out " + title
    elif kind == "renew":
        subject = "Loan renewed"
        body = "You renewed " + title
    else:
        subject = "Library notice"
        body = title
    with open(config.OUTBOX_PATH, "a") as f:
        f.write("TO: " + CURRENT_MEMBER["email"] + " | SUBJECT: " + subject + " | BODY: " + body + "\n")


# ---------- books ----------


@app.route("/books", methods=["GET"])
def list_books():
    conn = db.connect()
    if request.args.get("available") == "true":
        rows = conn.execute("SELECT * FROM books WHERE available = 1").fetchall()
    else:
        rows = conn.execute("SELECT * FROM books").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({"id": r["id"], "title": r["title"], "author": r["author"], "isbn": r["isbn"], "available": bool(r["available"])})
    return jsonify(result)


@app.route("/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    conn = db.connect()
    r = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    if r is None:
        return jsonify({"error": "book not found"}), 404
    return jsonify({"id": r["id"], "title": r["title"], "author": r["author"], "isbn": r["isbn"], "available": bool(r["available"])})


@app.route("/books", methods=["POST"])
def create_book():
    data = request.get_json(silent=True) or {}
    if not data.get("title") or not data.get("author"):
        return jsonify({"error": "title and author are required"}), 400
    if not check(data.get("isbn"), "isbn"):
        return jsonify({"error": "invalid isbn"}), 400
    conn = db.connect()
    cur = conn.execute(
        "INSERT INTO books (title, author, isbn, available) VALUES (?, ?, ?, 1)",
        (data["title"], data["author"], data["isbn"]),
    )
    conn.commit()
    r = conn.execute("SELECT * FROM books WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify({"id": r["id"], "title": r["title"], "author": r["author"], "isbn": r["isbn"], "available": bool(r["available"])}), 201


@app.route("/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    conn = db.connect()
    r = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if r is None:
        conn.close()
        return jsonify({"error": "book not found"}), 404
    if r["available"] == 0:
        conn.close()
        return jsonify({"error": "book is on loan"}), 409
    conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return "", 204


# ---------- members ----------


@app.route("/members", methods=["GET"])
def list_members():
    conn = db.connect()
    rows = conn.execute("SELECT * FROM members").fetchall()
    conn.close()
    result = []
    for r in rows:
        result.append({"id": r["id"], "name": r["name"], "email": r["email"], "type": r["type"]})
    return jsonify(result)


@app.route("/members/<int:member_id>", methods=["GET"])
def get_member(member_id):
    conn = db.connect()
    r = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    conn.close()
    if r is None:
        return jsonify({"error": "member not found"}), 404
    return jsonify({"id": r["id"], "name": r["name"], "email": r["email"], "type": r["type"]})


@app.route("/members", methods=["POST"])
def create_member():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if not check(data.get("email"), "email"):
        return jsonify({"error": "invalid email"}), 400
    member_type = data.get("type", "student")
    if not check(member_type, "member_type"):
        return jsonify({"error": "type must be student or staff"}), 400
    conn = db.connect()
    existing = conn.execute("SELECT * FROM members WHERE email = ?", (data["email"],)).fetchone()
    if existing is not None:
        conn.close()
        return jsonify({"error": "email already registered"}), 409
    cur = conn.execute(
        "INSERT INTO members (name, email, type) VALUES (?, ?, ?)",
        (data["name"], data["email"], member_type),
    )
    conn.commit()
    r = conn.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()
    return jsonify({"id": r["id"], "name": r["name"], "email": r["email"], "type": r["type"]}), 201


@app.route("/members/<int:member_id>/loans", methods=["GET"])
def member_loans(member_id):
    conn = db.connect()
    m = conn.execute("SELECT * FROM members WHERE id = ?", (member_id,)).fetchone()
    if m is None:
        conn.close()
        return jsonify({"error": "member not found"}), 404
    rows = conn.execute("SELECT * FROM loans WHERE member_id = ?", (member_id,)).fetchall()
    conn.close()
    loans = []
    for loan in rows:
        loans.append(
            {
                "id": loan["id"],
                "book_id": loan["book_id"],
                "due_date": loan["due_date"],
                "returned": bool(loan["returned"]),
                "fine": rules.money(loan["fine"]),
                "fine_paid": bool(loan["fine_paid"]),
            }
        )
    owed = rules.amount_owed(rows, date.today())
    remaining = rules.loans_remaining(rows, m["type"])
    return jsonify({"loans": loans, "total_owed": rules.money(owed), "loans_remaining": remaining})


# ---------- loans ----------


@app.route("/loans", methods=["GET"])
def list_loans():
    conn = db.connect()
    rows = conn.execute("SELECT * FROM loans").fetchall()
    conn.close()
    today = date.today()
    result = []
    for loan in rows:
        current_fine = rules.current_fine(loan, today)
        if request.args.get("overdue") == "true" and not rules.is_overdue(loan, today):
            continue
        result.append(
            {
                "id": loan["id"],
                "book_id": loan["book_id"],
                "member_id": loan["member_id"],
                "due_date": loan["due_date"],
                "returned": bool(loan["returned"]),
                "fine": rules.money(loan["fine"]),
                "fine_paid": bool(loan["fine_paid"]),
                "renewals": loan["renewals"],
                "checked_out": loan["checked_out"],
                "current_fine": rules.money(current_fine),
            }
        )
    return jsonify(result)


@app.route("/loans/<int:loan_id>", methods=["GET"])
def get_loan(loan_id):
    conn = db.connect()
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    conn.close()
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    current_fine = rules.current_fine(loan, date.today())
    return jsonify(
        {
            "id": loan["id"],
            "book_id": loan["book_id"],
            "member_id": loan["member_id"],
            "due_date": loan["due_date"],
            "returned": bool(loan["returned"]),
            "fine": rules.money(loan["fine"]),
            "fine_paid": bool(loan["fine_paid"]),
            "renewals": loan["renewals"],
            "checked_out": loan["checked_out"],
            "current_fine": rules.money(current_fine),
        }
    )


@app.route("/loans", methods=["POST"])
def create_loan():
    global CURRENT_MEMBER
    data = request.get_json(silent=True) or {}
    if not data.get("book_id") or not data.get("member_id"):
        return jsonify({"error": "book_id and member_id are required"}), 400
    if data.get("due_date") and not check(data["due_date"], "date"):
        return jsonify({"error": "invalid due_date"}), 400

    conn = db.connect()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (data["book_id"],)).fetchone()
    if book is None:
        conn.close()
        return jsonify({"error": "book not found"}), 404
    member = conn.execute("SELECT * FROM members WHERE id = ?", (data["member_id"],)).fetchone()
    if member is None:
        conn.close()
        return jsonify({"error": "member not found"}), 404
    if book["available"] == 0:
        conn.close()
        return jsonify({"error": "book is not available"}), 409

    rows = conn.execute("SELECT * FROM loans WHERE member_id = ?", (data["member_id"],)).fetchall()
    today = date.today()
    blocked = rules.checkout_block(rows, member["type"], today)
    if blocked:
        conn.close()
        return jsonify({"error": blocked}), 409

    due_date = data.get("due_date") or rules.default_due_date(today)
    cur = conn.execute(
        "INSERT INTO loans (book_id, member_id, due_date, checked_out) VALUES (?, ?, ?, ?)",
        (data["book_id"], data["member_id"], due_date, today.isoformat()),
    )
    conn.execute("UPDATE books SET available = 0 WHERE id = ?", (data["book_id"],))
    conn.commit()
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (cur.lastrowid,)).fetchone()
    conn.close()

    CURRENT_MEMBER = member
    notify("checkout", book["title"])

    return (
        jsonify(
            {
                "id": loan["id"],
                "book_id": loan["book_id"],
                "member_id": loan["member_id"],
                "due_date": loan["due_date"],
                "returned": bool(loan["returned"]),
                "fine": rules.money(loan["fine"]),
                "fine_paid": bool(loan["fine_paid"]),
                "renewals": loan["renewals"],
                "checked_out": loan["checked_out"],
            }
        ),
        201,
    )


@app.route("/loans/<int:loan_id>/return", methods=["POST"])
def return_book(loan_id):
    conn = db.connect()
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if loan is None:
        conn.close()
        return jsonify({"error": "loan not found"}), 404
    if loan["returned"] == 1:
        conn.close()
        return jsonify({"error": "loan already returned"}), 409

    fine = rules.fine_for(loan["due_date"], date.today())
    conn.execute("UPDATE loans SET returned = 1, fine = ? WHERE id = ?", (fine, loan_id))
    conn.execute("UPDATE books SET available = 1 WHERE id = ?", (loan["book_id"],))
    conn.commit()
    member = conn.execute("SELECT * FROM members WHERE id = ?", (loan["member_id"],)).fetchone()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (loan["book_id"],)).fetchone()
    updated = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    conn.close()

    with open(config.OUTBOX_PATH, "a") as f:
        f.write(
            "TO: " + member["email"] + " | SUBJECT: Book returned | BODY: You returned " + book["title"]
            + ". Fine: $" + str(rules.money(fine)) + "\n"
        )

    return jsonify(
        {
            "id": updated["id"],
            "book_id": updated["book_id"],
            "member_id": updated["member_id"],
            "due_date": updated["due_date"],
            "returned": bool(updated["returned"]),
            "fine": rules.money(updated["fine"]),
            "fine_paid": bool(updated["fine_paid"]),
            "renewals": updated["renewals"],
            "checked_out": updated["checked_out"],
        }
    )


@app.route("/loans/<int:loan_id>/renew", methods=["POST"])
def renew_loan(loan_id):
    global CURRENT_MEMBER
    conn = db.connect()
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if loan is None:
        conn.close()
        return jsonify({"error": "loan not found"}), 404
    blocked = rules.renewal_block(loan, date.today())
    if blocked:
        conn.close()
        return jsonify({"error": blocked}), 409

    new_due = rules.renewed_due_date(loan["due_date"])
    conn.execute("UPDATE loans SET due_date = ?, renewals = renewals + 1 WHERE id = ?", (new_due, loan_id))
    conn.commit()
    CURRENT_MEMBER = conn.execute("SELECT * FROM members WHERE id = ?", (loan["member_id"],)).fetchone()
    book = conn.execute("SELECT * FROM books WHERE id = ?", (loan["book_id"],)).fetchone()
    updated = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    conn.close()

    notify("renew", book["title"])

    return jsonify(
        {
            "id": updated["id"],
            "book_id": updated["book_id"],
            "member_id": updated["member_id"],
            "due_date": updated["due_date"],
            "returned": bool(updated["returned"]),
            "fine": rules.money(updated["fine"]),
            "fine_paid": bool(updated["fine_paid"]),
            "renewals": updated["renewals"],
            "checked_out": updated["checked_out"],
        }
    )


@app.route("/loans/<int:loan_id>/pay-fine", methods=["POST"])
def pay_fine(loan_id):
    conn = db.connect()
    loan = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    if loan is None:
        conn.close()
        return jsonify({"error": "loan not found"}), 404
    blocked = rules.payment_block(loan)
    if blocked:
        conn.close()
        return jsonify({"error": blocked}), 409

    conn.execute("UPDATE loans SET fine_paid = 1 WHERE id = ?", (loan_id,))
    conn.commit()
    member = conn.execute("SELECT * FROM members WHERE id = ?", (loan["member_id"],)).fetchone()
    updated = conn.execute("SELECT * FROM loans WHERE id = ?", (loan_id,)).fetchone()
    conn.close()

    with open(config.OUTBOX_PATH, "a") as f:
        f.write(
            "TO: " + member["email"] + " | SUBJECT: Fine paid | BODY: We received $" + str(rules.money(loan["fine"])) + "\n"
        )

    return jsonify(
        {
            "id": updated["id"],
            "book_id": updated["book_id"],
            "member_id": updated["member_id"],
            "due_date": updated["due_date"],
            "returned": bool(updated["returned"]),
            "fine": rules.money(updated["fine"]),
            "fine_paid": bool(updated["fine_paid"]),
            "renewals": updated["renewals"],
            "checked_out": updated["checked_out"],
        }
    )


# ---------- reports ----------


@app.route("/reports/overdue", methods=["GET"])
def report_overdue():
    conn = db.connect()
    rows = conn.execute(
        """
        SELECT loans.id, books.title, members.name, loans.due_date
        FROM loans
        JOIN books ON books.id = loans.book_id
        JOIN members ON members.id = loans.member_id
        WHERE loans.returned = 0
        """
    ).fetchall()
    conn.close()
    today = date.today()
    items = []
    total = 0
    for r in rows:
        if rules.is_late(r["due_date"], today):
            fine = rules.fine_for(r["due_date"], today)
            total += fine
            items.append(
                {
                    "loan_id": r["id"],
                    "title": r["title"],
                    "member": r["name"],
                    "days_late": rules.days_late(r["due_date"], today),
                    "fine": rules.money(fine),
                }
            )
    return jsonify({"items": items, "total_fines": rules.money(total)})


@app.route("/reports/summary", methods=["GET"])
def report_summary():
    conn = db.connect()
    total_books = conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    rows = conn.execute("SELECT * FROM loans").fetchall()
    conn.close()
    on_loan = rules.open_loan_count(rows)
    outstanding = rules.amount_owed(rows, date.today())
    return jsonify({"total_books": total_books, "on_loan": on_loan, "fines_outstanding": rules.money(outstanding)})


if not os.path.exists(config.DB_PATH):
    init_db()
