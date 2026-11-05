# Diagnosis of `app.py`

Line numbers refer to the original 555-line `app.py` (commit `1b6f3b3`).

## Baseline metrics

| Measure | Before |
|---|---|
| Tests passing | 53 / 53 |
| Lines in the largest file | 555 (`app.py`) |
| Places where the fine rate appears | 7 |
| Route handlers containing SQL | 16 of 16 |
| Can the fine rule be tested without HTTP or a database? | No |

## Problems

| # | Problem | Location | Type | Future change it makes harder |
|---|---|---|---|---|
| 1 | The fine rule is duplicated. | `member_loans` 227, `list_loans` 260, `get_loan` 290, `create_loan` 337, `return_book` 394, `report_overdue` 528, `report_summary` 548 | Cohesion: duplication, one rule scattered across 7 places. Written both as `0.5` and `0.50`, so a search for one misses the other. | Changing the rate, or adding a fine cap or grace period, needs 7 identical edits. Missing one makes the API report different amounts for the same loan. |
| 2 | The "amount owed + open loans" loop is duplicated. | `member_loans` 222-229, `create_loan` 332-339, `report_summary` 544-550 | Cohesion: duplication of a business rule inside handlers. | Changing what counts as debt (for example, waived fines) can make checkout refuse a member whose account page shows $0. |
| 3 | Every route handler contains SQL. | All 16 handlers, 103-551 | Coupling: external coupling to SQLite. Cohesion: handlers mix HTTP, persistence and rules (communicational at best). | Changing the schema or database means editing every handler. A handler can't be tested without a real database. |
| 4 | Rows are read by position. | `loan[4]`, `loan[6]`, `r[4]`, `member[3]`, for example 223-229, 257-273, 325, 344, 389, 438, 477 | Coupling: content coupling. Handlers depend on the column order hidden behind `SELECT *`. | Adding or reordering a column silently breaks handlers. `loan[4]` also says nothing about its meaning, so mistakes are easy to miss in review. |
| 5 | `notify()` gets its recipient from a global. | `CURRENT_MEMBER` at 10, read at 97, written at 361 and 445 (`global` at 309, 426) | Coupling: common coupling. Callers must set the global before calling, and nothing enforces that order. Reading only `[2]` of a whole row is also stamp coupling. | Sending any new notification depends on remembering the hidden step. Concurrent requests share the global, so an email can reach the wrong member. |
| 6 | `notify(kind, title, send)` branches on flags. | 84-97 | Coupling: control coupling. The caller picks the function's behavior with `kind` and `send`. The `send=False` path and the generic `else` branch are never used. | Each new email type grows the `if/elif` chain, and misspelling a `kind` silently sends a "Library notice". |
| 7 | Return and pay-fine bypass `notify` and write the outbox themselves. | `return_book` 403-407, `pay_fine` 487-490 (and `notify` at 96-97) | Cohesion: duplication. Coupling: external coupling to the outbox file and its line format in 3 places. | Replacing `outbox.txt` with a real mail server, or changing the line format, needs 3 edits and is easy to do only partly. |
| 8 | `check(value, kind)` mixes four unrelated validators. | 63-77, called at 132, 190, 193, 313 | Cohesion: logical cohesion. Coupling: control coupling through `kind`. An unknown `kind` returns `False`, which looks like invalid input. | Changing the rule for one field means editing a function shared with the others. A typo such as `check(x, "e-mail")` rejects all input without an error. |
| 9 | Library policy is written as magic numbers. | Loan length 351, renewal length 442, limits 241-243 and 343-345, one renewal 438 | Cohesion: policy values scattered across handlers. | "Staff can borrow 10 books" needs edits in two handlers. The two `14`s look the same but mean different things. |
| 10 | Loan JSON is copy-pasted. | 263-276, 292-303, 366-376, 410-420, 454-463, 493-503, and a shorter form at 231-238. Book JSON: 113, 124, 142. Member JSON: 171, 182, 207. | Cohesion: duplication. Coupling: data coupling to the response shape in many handlers. | Adding one field to a loan response needs 6 or 7 edits, and missing one makes endpoints inconsistent. |
| 11 | One file does every job. | Whole file, 1-555 (setup and seed data 13-57, validation 63-77, email 84-97, HTTP throughout) | Cohesion: coincidental cohesion, the weakest kind. | Any change means reading unrelated code, and two people working on different features touch the same file. |
| 12 | `date.today()` and `"library.db"` are hard-coded inside the logic. | `date.today()` at 225, 258, 289, 335, 350, 393, 435, 526, 547. `sqlite3.connect("library.db")` 17 times. | Coupling: external coupling to the system clock and the file system. | The fine rule can't be tested for a chosen date, and moving the database means 17 edits. |
