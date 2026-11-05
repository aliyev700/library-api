# Refactoring Results

## Measurements

| Measure | Before | After |
|---|---|---|
| Tests passing | 53 / 53 | 77 / 77 (the original 53 plus 24 new in `test_rules.py`) |
| Lines in the largest file | 555 (`app.py`) | 140 (`repository.py`), not counting the test files; `app.py` is now 19 |
| Places where the fine rate appears | 7 | 1 (`config.py`) |
| Route handlers containing SQL | 16 of 16 | 0 of 16 |
| Places edited for the change request | n/a | n/a (given in class) |
| Can the fine rule be tested without HTTP or a database? | No | Yes (`test_rules.py`) |

`test_api.py` is unchanged. As an extra check, the same 228 requests were sent to the original `app.py` and to the code at each refactoring commit, including invalid input and error cases. Status codes, response bodies, `outbox.txt` and the final database contents were identical every time.

## Structure

| File | Job |
|---|---|
| `app.py` | Creates the app, registers blueprints, exposes `app` and `init_db` |
| `config.py` | Fine rate, loan policy and file paths |
| `rules.py` | Library rules as pure functions |
| `validation.py` | Input format checks |
| `db.py` | Opens connections; creates the schema and seed data |
| `repository.py` | All queries used by the API; returns dicts |
| `notifications.py` | Email wording and the outbox line format |
| `serializers.py` | JSON response shapes |
| `books.py`, `members.py`, `loans.py`, `reports.py` | Thin HTTP handlers |

Where this differs from the suggested plan:

- **`db.py` came before `rules.py`.** The rules read `loan["due_date"]`, so rows needed column names first. `sqlite3.Row` allowed that switch without breaking the remaining positional code.
- **`rules.py` has a few extra functions:** `checkout_block`, `renewal_block` and `payment_block` return the reason an action is refused. The API has a different error message for each reason, so `can_renew`'s yes/no answer alone wasn't enough.
- **There is no service layer.** The target structure has handlers call rules and the repository directly (see question 3).

## Questions

### 1. Which module is the most cohesive?

`rules.py`. Its one job: given loan data and a date, decide what the library's rules say about what is owed and which actions are allowed. It does no input or output. The one function that doesn't quite belong is `money()`, a rounding helper.

### 2. Which dependency did you remove, and what can now change independently?

The hidden dependency between `notify()` and the global `CURRENT_MEMBER`. The recipient is now an ordinary argument, and every email goes through `notifications.send()`. So the email delivery method can change in that one function, without touching any handler, and a request can no longer email the member set by a different request.

Moving SQL out of the handlers also means the schema and queries can change in `db.py` and `repository.py` without editing a handler, as long as the column names the other modules read stay the same.

### 3. What coupling remains, and why did you accept it?

- **Handlers coordinate the workflow.** `loans.py` knows the order: check the rules, write to the database, send the email. A second interface, such as a command-line tool, would have to repeat that order. I accepted this because the handlers are short and there is only one interface; a service layer is the next step if that changes.
- **`rules.py` and `serializers.py` depend on column names** such as `loan["due_date"]`. Renaming a column means updating them. This is far safer than positions, and plain dicts keep the rules testable.
- **`rules.py` returns the API's error messages,** which ties policy to wording. This keeps each message in one place and the responses identical.
- **Modules read `config` constants directly.** Using a different fine rate for one call would need patching or a new parameter. A single policy doesn't need more than this.
- **File paths stay relative and the database is created on import,** because the exercise requires that behavior.
