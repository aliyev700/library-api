from contextlib import closing

import db


def _fetch_one(query, params=()):
    with closing(db.connect()) as conn:
        row = conn.execute(query, params).fetchone()
    return dict(row) if row is not None else None


def _fetch_all(query, params=()):
    with closing(db.connect()) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def _insert(query, params):
    with closing(db.connect()) as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid


# ---------- books ----------


def list_books(only_available=False):
    if only_available:
        return _fetch_all("SELECT * FROM books WHERE available = 1")
    return _fetch_all("SELECT * FROM books")


def get_book(book_id):
    return _fetch_one("SELECT * FROM books WHERE id = ?", (book_id,))


def create_book(title, author, isbn):
    book_id = _insert(
        "INSERT INTO books (title, author, isbn, available) VALUES (?, ?, ?, 1)",
        (title, author, isbn),
    )
    return get_book(book_id)


def delete_book(book_id):
    with closing(db.connect()) as conn:
        conn.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()


def count_books():
    return _fetch_one("SELECT COUNT(*) AS total FROM books")["total"]


# ---------- members ----------


def list_members():
    return _fetch_all("SELECT * FROM members")


def get_member(member_id):
    return _fetch_one("SELECT * FROM members WHERE id = ?", (member_id,))


def get_member_by_email(email):
    return _fetch_one("SELECT * FROM members WHERE email = ?", (email,))


def create_member(name, email, member_type):
    member_id = _insert(
        "INSERT INTO members (name, email, type) VALUES (?, ?, ?)",
        (name, email, member_type),
    )
    return get_member(member_id)


# ---------- loans ----------


def list_loans():
    return _fetch_all("SELECT * FROM loans")


def list_loans_for_member(member_id):
    return _fetch_all("SELECT * FROM loans WHERE member_id = ?", (member_id,))


def get_loan(loan_id):
    return _fetch_one("SELECT * FROM loans WHERE id = ?", (loan_id,))


def create_loan(book_id, member_id, due_date, checked_out):
    with closing(db.connect()) as conn:
        cur = conn.execute(
            "INSERT INTO loans (book_id, member_id, due_date, checked_out) VALUES (?, ?, ?, ?)",
            (book_id, member_id, due_date, checked_out),
        )
        conn.execute("UPDATE books SET available = 0 WHERE id = ?", (book_id,))
        conn.commit()
        loan_id = cur.lastrowid
    return get_loan(loan_id)


def mark_returned(loan_id, book_id, fine):
    with closing(db.connect()) as conn:
        conn.execute("UPDATE loans SET returned = 1, fine = ? WHERE id = ?", (fine, loan_id))
        conn.execute("UPDATE books SET available = 1 WHERE id = ?", (book_id,))
        conn.commit()
    return get_loan(loan_id)


def extend_loan(loan_id, new_due_date):
    with closing(db.connect()) as conn:
        conn.execute("UPDATE loans SET due_date = ?, renewals = renewals + 1 WHERE id = ?", (new_due_date, loan_id))
        conn.commit()
    return get_loan(loan_id)


def mark_fine_paid(loan_id):
    with closing(db.connect()) as conn:
        conn.execute("UPDATE loans SET fine_paid = 1 WHERE id = ?", (loan_id,))
        conn.commit()
    return get_loan(loan_id)


# ---------- reports ----------


def list_open_loans_with_details():
    return _fetch_all(
        """
        SELECT loans.id, books.title, members.name, loans.due_date
        FROM loans
        JOIN books ON books.id = loans.book_id
        JOIN members ON members.id = loans.member_id
        WHERE loans.returned = 0
        """
    )
