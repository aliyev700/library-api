import os
from datetime import date

from flask import Flask, jsonify, request

import books
import members
import config
import notifications
import repository
import rules
import serializers
import validation
from db import init_db

app = Flask(__name__)
app.register_blueprint(members.bp)
app.register_blueprint(books.bp)

# ---------- helpers ----------


# ---------- loans ----------


@app.route("/loans", methods=["GET"])
def list_loans():
    today = date.today()
    loans = repository.list_loans()
    if request.args.get("overdue") == "true":
        loans = [loan for loan in loans if rules.is_overdue(loan, today)]
    return jsonify([serializers.loan_to_json(loan, rules.current_fine(loan, today)) for loan in loans])


@app.route("/loans/<int:loan_id>", methods=["GET"])
def get_loan(loan_id):
    loan = repository.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    return jsonify(serializers.loan_to_json(loan, rules.current_fine(loan, date.today())))


@app.route("/loans", methods=["POST"])
def create_loan():
    data = request.get_json(silent=True) or {}
    if not data.get("book_id") or not data.get("member_id"):
        return jsonify({"error": "book_id and member_id are required"}), 400
    if data.get("due_date") and not validation.is_valid_date(data["due_date"]):
        return jsonify({"error": "invalid due_date"}), 400

    book = repository.get_book(data["book_id"])
    if book is None:
        return jsonify({"error": "book not found"}), 404
    member = repository.get_member(data["member_id"])
    if member is None:
        return jsonify({"error": "member not found"}), 404
    if not book["available"]:
        return jsonify({"error": "book is not available"}), 409

    today = date.today()
    blocked = rules.checkout_block(repository.list_loans_for_member(data["member_id"]), member["type"], today)
    if blocked:
        return jsonify({"error": blocked}), 409

    due_date = data.get("due_date") or rules.default_due_date(today)
    loan = repository.create_loan(data["book_id"], data["member_id"], due_date, today.isoformat())
    notifications.book_checked_out(member["email"], book["title"])
    return jsonify(serializers.loan_to_json(loan)), 201


@app.route("/loans/<int:loan_id>/return", methods=["POST"])
def return_book(loan_id):
    loan = repository.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    if loan["returned"]:
        return jsonify({"error": "loan already returned"}), 409

    fine = rules.fine_for(loan["due_date"], date.today())
    updated = repository.mark_returned(loan_id, loan["book_id"], fine)
    member = repository.get_member(loan["member_id"])
    book = repository.get_book(loan["book_id"])
    notifications.book_returned(member["email"], book["title"], fine)
    return jsonify(serializers.loan_to_json(updated))


@app.route("/loans/<int:loan_id>/renew", methods=["POST"])
def renew_loan(loan_id):
    loan = repository.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    blocked = rules.renewal_block(loan, date.today())
    if blocked:
        return jsonify({"error": blocked}), 409

    updated = repository.extend_loan(loan_id, rules.renewed_due_date(loan["due_date"]))
    member = repository.get_member(loan["member_id"])
    book = repository.get_book(loan["book_id"])
    notifications.loan_renewed(member["email"], book["title"])
    return jsonify(serializers.loan_to_json(updated))


@app.route("/loans/<int:loan_id>/pay-fine", methods=["POST"])
def pay_fine(loan_id):
    loan = repository.get_loan(loan_id)
    if loan is None:
        return jsonify({"error": "loan not found"}), 404
    blocked = rules.payment_block(loan)
    if blocked:
        return jsonify({"error": blocked}), 409

    updated = repository.mark_fine_paid(loan_id)
    member = repository.get_member(loan["member_id"])
    notifications.fine_paid(member["email"], loan["fine"])
    return jsonify(serializers.loan_to_json(updated))


# ---------- reports ----------


@app.route("/reports/overdue", methods=["GET"])
def report_overdue():
    today = date.today()
    overdue = [row for row in repository.list_open_loans_with_details() if rules.is_late(row["due_date"], today)]
    fines = [rules.fine_for(row["due_date"], today) for row in overdue]
    items = [
        serializers.overdue_item_to_json(row, rules.days_late(row["due_date"], today), fine)
        for row, fine in zip(overdue, fines)
    ]
    return jsonify({"items": items, "total_fines": rules.money(sum(fines))})


@app.route("/reports/summary", methods=["GET"])
def report_summary():
    loans = repository.list_loans()
    return jsonify(
        {
            "total_books": repository.count_books(),
            "on_loan": rules.open_loan_count(loans),
            "fines_outstanding": rules.money(rules.amount_owed(loans, date.today())),
        }
    )


if not os.path.exists(config.DB_PATH):
    init_db()
