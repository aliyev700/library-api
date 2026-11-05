import os
from datetime import date

from flask import Flask, jsonify, request

import books
import members
import loans
import reports
import config
import notifications
import repository
import rules
import serializers
import validation
from db import init_db

app = Flask(__name__)
app.register_blueprint(reports.bp)
app.register_blueprint(loans.bp)
app.register_blueprint(members.bp)
app.register_blueprint(books.bp)

# ---------- helpers ----------


if not os.path.exists(config.DB_PATH):
    init_db()
