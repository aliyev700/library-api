from rules import money


def book_to_json(book):
    return {
        "id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "isbn": book["isbn"],
        "available": bool(book["available"]),
    }


def member_to_json(member):
    return {"id": member["id"], "name": member["name"], "email": member["email"], "type": member["type"]}


def loan_to_json(loan, current_fine=None):
    result = {
        "id": loan["id"],
        "book_id": loan["book_id"],
        "member_id": loan["member_id"],
        "due_date": loan["due_date"],
        "returned": bool(loan["returned"]),
        "fine": money(loan["fine"]),
        "fine_paid": bool(loan["fine_paid"]),
        "renewals": loan["renewals"],
        "checked_out": loan["checked_out"],
    }
    if current_fine is not None:
        result["current_fine"] = money(current_fine)
    return result


def member_loan_to_json(loan):
    return {
        "id": loan["id"],
        "book_id": loan["book_id"],
        "due_date": loan["due_date"],
        "returned": bool(loan["returned"]),
        "fine": money(loan["fine"]),
        "fine_paid": bool(loan["fine_paid"]),
    }


def overdue_item_to_json(row, days_late, fine):
    return {
        "loan_id": row["id"],
        "title": row["title"],
        "member": row["name"],
        "days_late": days_late,
        "fine": money(fine),
    }
