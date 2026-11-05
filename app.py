import os
from datetime import date

from flask import Flask, jsonify, request

import books
import members
import loans
import config
import notifications
import repository
import rules
import serializers
import validation
from db import init_db

app = Flask(__name__)
app.register_blueprint(loans.bp)
app.register_blueprint(members.bp)
app.register_blueprint(books.bp)

# ---------- helpers ----------


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
