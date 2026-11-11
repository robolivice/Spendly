import sqlite3
from datetime import date, datetime

import db
import recurrence


def _anchor(rule):
    return date.fromisoformat(rule["start_date"])


def _end(rule):
    value = rule["end_date"]
    return date.fromisoformat(value) if value else None


def _advance(rule, current):
    return recurrence.next_date(current, rule["cadence"], _anchor(rule))


def _pending(rule, today):
    return recurrence.due_dates(
        rule["next_due"],
        rule["cadence"],
        _anchor(rule),
        _end(rule),
        today,
    )


def _view(rule, today):
    view = dict(rule)
    view["cadence_label"] = recurrence.CADENCE_LABELS.get(rule["cadence"], "Monthly")
    view["auto_post"] = bool(rule["auto_post"])
    view["next_due_display"] = date.fromisoformat(rule["next_due"]).strftime("%b %d, %Y")
    view["start_display"] = date.fromisoformat(rule["start_date"]).strftime("%b %d, %Y")
    view["end_display"] = (
        date.fromisoformat(rule["end_date"]).strftime("%b %d, %Y")
        if rule["end_date"]
        else None
    )
    return view


def upcoming(pid, today=None):
    today = today or date.today()
    due_rows = []
    scheduled = []
    completed = []
    for rule in db.getRecurringRules(pid):
        view = _view(rule, today)
        due = date.fromisoformat(rule["next_due"])
        end = _end(rule)
        if end is not None and due > end:
            completed.append(view)
            continue
        pending = _pending(rule, today)
        if pending:
            view["due_date"] = pending[0].isoformat()
            view["due_display"] = pending[0].strftime("%b %d, %Y")
            view["due_count"] = len(pending)
            view["overdue"] = pending[0] < today
            view["due_label"] = "Overdue" if pending[0] < today else "Due today"
            due_rows.append(view)
        elif due > today:
            scheduled.append(view)
        else:
            completed.append(view)
    due_rows.sort(key=lambda item: (item["due_date"], (item["description"] or "").lower()))
    scheduled.sort(key=lambda item: (item["next_due"], (item["description"] or "").lower()))
    completed.sort(key=lambda item: item["next_due"])
    return due_rows, scheduled, completed


def _prepare(conn, pid, rule_id, due_date, today):
    row = conn.execute(
        "SELECT * FROM recurring WHERE id = ? AND profile_id = ?",
        (rule_id, pid),
    ).fetchone()
    if row is None:
        return None, None, "Recurring rule not found."
    try:
        due = date.fromisoformat(str(due_date))
    except ValueError:
        return None, None, "Choose a valid due date."
    try:
        next_due = date.fromisoformat(row["next_due"])
    except ValueError:
        return None, None, "This recurring rule has an invalid next due date."
    if due != next_due:
        return None, None, "That occurrence was already handled or the rule changed."
    if due > today:
        return None, None, "This occurrence is not due yet."
    end = _end(row)
    if end is not None and due > end:
        return None, None, "This recurring rule has ended."
    return row, due, None


def post(pid, rule_id, due_date, today=None, values=None):
    today = today or date.today()
    conn = db.connect()
    try:
        row, due, error = _prepare(conn, pid, rule_id, due_date, today)
        if error:
            return False, error
        if values is None:
            exp_date = due
            category = row["category"]
            amount = row["amount"]
            description = row["description"] or ""
        else:
            exp_date = values.get("date") or due
            try:
                amount = float(values.get("amount"))
            except (TypeError, ValueError):
                return False, "Enter a valid amount."
            if amount < 0:
                return False, "The amount cannot be negative."
            category = str(values.get("category") or row["category"]).strip()
            if not category:
                return False, "Choose a category."
            description = str(values.get("description") or "").strip()
        if exp_date > today:
            return False, "Expense dates cannot be in the future."
        conn.execute(
            """
            INSERT INTO recurring_occurrences(rule_id, due_date, status, handled_at)
            VALUES (?, ?, 'posted', ?)
            """,
            (rule_id, due.isoformat(), datetime.now().isoformat(timespec="seconds")),
        )
        cur = conn.execute(
            """
            INSERT INTO expenses(profile_id, date, category, amount, description)
            VALUES (?, ?, ?, ?, ?)
            """,
            (pid, exp_date.isoformat(), category, amount, description),
        )
        conn.execute(
            """
            UPDATE recurring_occurrences SET expense_id = ?
            WHERE rule_id = ? AND due_date = ?
            """,
            (cur.lastrowid, rule_id, due.isoformat()),
        )
        next_due = _advance(row, due)
        conn.execute(
            "UPDATE recurring SET next_due = ? WHERE id = ? AND profile_id = ?",
            (next_due.isoformat(), rule_id, pid),
        )
        conn.commit()
        return True, f"Posted {category} for {due.strftime('%b %d, %Y')}."
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "That occurrence was already handled."
    except (OSError, sqlite3.Error):
        conn.rollback()
        return False, "Could not post this occurrence."
    finally:
        conn.close()


def skip(pid, rule_id, due_date, today=None):
    today = today or date.today()
    conn = db.connect()
    try:
        row, due, error = _prepare(conn, pid, rule_id, due_date, today)
        if error:
            return False, error
        conn.execute(
            """
            INSERT INTO recurring_occurrences(rule_id, due_date, status, handled_at)
            VALUES (?, ?, 'skipped', ?)
            """,
            (rule_id, due.isoformat(), datetime.now().isoformat(timespec="seconds")),
        )
        next_due = _advance(row, due)
        conn.execute(
            "UPDATE recurring SET next_due = ? WHERE id = ? AND profile_id = ?",
            (next_due.isoformat(), rule_id, pid),
        )
        conn.commit()
        return True, f"Skipped {due.strftime('%b %d, %Y')}. It will not be posted."
    except sqlite3.IntegrityError:
        conn.rollback()
        return False, "That occurrence was already handled."
    except (OSError, sqlite3.Error):
        conn.rollback()
        return False, "Could not skip this occurrence."
    finally:
        conn.close()


def auto_post(pid, today=None):
    today = today or date.today()
    rules = [rule for rule in db.getRecurringRules(pid) if rule["auto_post"]]
    posted = 0
    for rule in rules:
        rule_id = rule["id"]
        while posted < 1000:
            current = db.getRecurringRule(pid, rule_id)
            if current is None or not current["auto_post"]:
                break
            due = date.fromisoformat(current["next_due"])
            end = _end(current)
            if due > today or (end is not None and due > end):
                break
            ok, _message = post(pid, rule_id, due.isoformat(), today)
            if not ok:
                break
            posted += 1
    return posted
