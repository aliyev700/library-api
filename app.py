import os

from flask import Flask

import books
import config
import loans
import members
import reports
from db import init_db

app = Flask(__name__)
app.register_blueprint(books.bp)
app.register_blueprint(members.bp)
app.register_blueprint(loans.bp)
app.register_blueprint(reports.bp)

if not os.path.exists(config.DB_PATH):
    init_db()
