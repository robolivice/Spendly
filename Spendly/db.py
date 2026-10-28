import calendar
import sqlite3
from datetime import date

import cycles

DB = "expense.db"


def connect():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def setup():
    conn = connect()
    conn.execute("""
    CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS limits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(profile_id, start_date, end_date),
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS cycles(
        profile_id INTEGER PRIMARY KEY,
        end_day INTEGER NOT NULL CHECK(end_day BETWEEN 1 AND 31),
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )""")
    conn.execute("""
    CREATE TABLE IF NOT EXISTS periods(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        limit_amount REAL,
        UNIQUE(profile_id, start_date, end_date),
        FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_expenses_profile_date ON expenses(profile_id, date)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_periods_profile_end ON periods(profile_id, end_date)")
    conn.execute("""
    INSERT OR IGNORE INTO periods(profile_id, start_date, end_date, limit_amount)
    SELECT profile_id, start_date, end_date, amount FROM limits
    """)
    rows = conn.execute("""
    SELECT l.profile_id, l.end_date
    FROM limits l
    WHERE l.end_date = (SELECT MAX(end_date) FROM limits l2 WHERE l2.profile_id = l.profile_id)
    """).fetchall()
    for row in rows:
        end = date.fromisoformat(row["end_date"])
        day = 31 if end.day == calendar.monthrange(end.year, end.month)[1] else end.day
        conn.execute("INSERT OR IGNORE INTO cycles(profile_id, end_day) VALUES (?, ?)", (row["profile_id"], day))
    conn.commit()
    conn.close()


def getProfiles():
    conn = connect()
    rows = conn.execute("SELECT id, name FROM profiles ORDER BY name").fetchall()
    conn.close()
    return rows


def getProfile(pid):
    conn = connect()
    row = conn.execute("SELECT id, name FROM profiles WHERE id = ?", (pid,)).fetchone()
    conn.close()
    return row


def createProfile(name):
    conn = connect()
    pid = None
    try:
        cur = conn.execute("INSERT INTO profiles(name) VALUES (?)", (name,))
        conn.commit()
        pid = cur.lastrowid
    except sqlite3.IntegrityError:
        pid = None
    conn.close()
    return pid


def deleteProfile(pid):
    conn = connect()
    conn.execute("DELETE FROM expenses WHERE profile_id = ?", (pid,))
    conn.execute("DELETE FROM limits WHERE profile_id = ?", (pid,))
    conn.execute("DELETE FROM periods WHERE profile_id = ?", (pid,))
    conn.execute("DELETE FROM cycles WHERE profile_id = ?", (pid,))
    conn.execute("DELETE FROM profiles WHERE id = ?", (pid,))
    conn.commit()
    conn.close()


def getCycle(pid):
    conn = connect()
    row = conn.execute("SELECT end_day FROM cycles WHERE profile_id = ?", (pid,)).fetchone()
    conn.close()
    return row


def setCycleDay(pid, end_day):
    conn = connect()
    conn.execute("""
    INSERT INTO cycles(profile_id, end_day) VALUES (?, ?)
    ON CONFLICT(profile_id) DO UPDATE SET end_day = excluded.end_day
    """, (pid, end_day))
    conn.commit()
    conn.close()


def setupCycle(pid, end_day, amount=None, start=None, end=None, apply_history=False, today=None):
    today = today or date.today()
    conn = connect()
    conn.execute("""
    INSERT INTO cycles(profile_id, end_day) VALUES (?, ?)
    ON CONFLICT(profile_id) DO UPDATE SET end_day = excluded.end_day
    """, (pid, end_day))
    if start is not None and end is not None:
        conn.execute("""
        INSERT INTO periods(profile_id, start_date, end_date, limit_amount)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(profile_id, start_date, end_date) DO UPDATE SET limit_amount = excluded.limit_amount
        """, (pid, start.isoformat(), end.isoformat(), amount))
        conn.commit()
        conn.close()
        return
    row = conn.execute("SELECT MIN(date) FROM expenses WHERE profile_id = ?", (pid,)).fetchone()
    first = min(date.fromisoformat(row[0]), today) if row[0] else today
    start, end = cycles.current(end_day, first)
    current_end = cycles.current(end_day, today)[1]
    while True:
        value = amount if apply_history or start <= today <= end else None
        conn.execute("""
        INSERT OR IGNORE INTO periods(profile_id, start_date, end_date, limit_amount)
        VALUES (?, ?, ?, ?)
        """, (pid, start.isoformat(), end.isoformat(), value))
        if end >= current_end:
            break
        start, end = cycles.next_period(end, end_day)
    conn.commit()
    conn.close()


def ensurePeriods(pid, today=None):
    today = today or date.today()
    conn = connect()
    row = conn.execute("SELECT end_day FROM cycles WHERE profile_id = ?", (pid,)).fetchone()
    if row is None:
        conn.close()
        return None
    day = row["end_day"]
    row = conn.execute("SELECT start_date FROM periods WHERE profile_id = ? ORDER BY start_date LIMIT 1", (pid,)).fetchone()
    if row is None:
        start, end = cycles.current(day, today)
        conn.execute("""
        INSERT OR IGNORE INTO periods(profile_id, start_date, end_date, limit_amount)
        VALUES (?, ?, ?, ?)
        """, (pid, start.isoformat(), end.isoformat(), None))
        first_start = start
    else:
        first_start = date.fromisoformat(row["start_date"])
    row = conn.execute("SELECT MIN(date) FROM expenses WHERE profile_id = ?", (pid,)).fetchone()
    if row[0]:
        target = date.fromisoformat(row[0])
        start = first_start
        while target < start:
            previous_start, previous_end = cycles.previous(start, day)
            conn.execute("""
            INSERT OR IGNORE INTO periods(profile_id, start_date, end_date, limit_amount)
            VALUES (?, ?, ?, ?)
            """, (pid, previous_start.isoformat(), previous_end.isoformat(), None))
            start = previous_start
    row = conn.execute("SELECT end_date FROM periods WHERE profile_id = ? ORDER BY end_date DESC LIMIT 1", (pid,)).fetchone()
    latest = date.fromisoformat(row["end_date"])
    while latest < today:
        start, end = cycles.next_period(latest, day)
        row = conn.execute("""
        SELECT limit_amount FROM periods
        WHERE profile_id = ? AND end_date < ?
        ORDER BY end_date DESC LIMIT 1
        """, (pid, start.isoformat())).fetchone()
        amount = row["limit_amount"] if row else None
        conn.execute("""
        INSERT OR IGNORE INTO periods(profile_id, start_date, end_date, limit_amount)
        VALUES (?, ?, ?, ?)
        """, (pid, start.isoformat(), end.isoformat(), amount))
        latest = end
    row = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? AND start_date <= ? AND end_date >= ?
    ORDER BY end_date DESC LIMIT 1
    """, (pid, today.isoformat(), today.isoformat())).fetchone()
    if row is None:
        row = conn.execute("""
        SELECT id, start_date, end_date, limit_amount FROM periods
        WHERE profile_id = ? ORDER BY end_date DESC LIMIT 1
        """, (pid,)).fetchone()
    conn.commit()
    conn.close()
    return row


def getPeriods(pid):
    conn = connect()
    rows = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? ORDER BY end_date DESC
    """, (pid,)).fetchall()
    conn.close()
    return rows


def getPeriod(pid, period_id):
    conn = connect()
    row = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE id = ? AND profile_id = ?
    """, (period_id, pid)).fetchone()
    conn.close()
    return row


def getPeriodByRange(pid, start, end):
    conn = connect()
    row = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? AND start_date = ? AND end_date = ?
    """, (pid, start, end)).fetchone()
    conn.close()
    return row


def getPeriodContaining(pid, on_date):
    conn = connect()
    row = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? AND start_date <= ? AND end_date >= ?
    ORDER BY end_date DESC LIMIT 1
    """, (pid, on_date, on_date)).fetchone()
    conn.close()
    return row


def getPeriodBefore(pid, on_date):
    conn = connect()
    row = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? AND end_date < ?
    ORDER BY end_date DESC LIMIT 1
    """, (pid, on_date)).fetchone()
    conn.close()
    return row


def getOverlappingPeriods(pid, start, end):
    conn = connect()
    rows = conn.execute("""
    SELECT id, start_date, end_date, limit_amount FROM periods
    WHERE profile_id = ? AND start_date <= ? AND end_date >= ?
    ORDER BY start_date
    """, (pid, end, start)).fetchall()
    conn.close()
    return rows


def savePeriod(pid, start, end, amount):
    conn = connect()
    overlaps = conn.execute("""
    SELECT id FROM periods
    WHERE profile_id = ? AND start_date <= ? AND end_date >= ?
    ORDER BY start_date
    """, (pid, end, start)).fetchall()
    if len(overlaps) > 1:
        conn.close()
        return None, "overlap"
    if len(overlaps) == 1:
        period_id = overlaps[0]["id"]
        conn.execute("""
        UPDATE periods SET start_date = ?, end_date = ?, limit_amount = ?
        WHERE id = ? AND profile_id = ?
        """, (start, end, amount, period_id, pid))
        action = "updated"
    else:
        cur = conn.execute("""
        INSERT INTO periods(profile_id, start_date, end_date, limit_amount)
        VALUES (?, ?, ?, ?)
        """, (pid, start, end, amount))
        period_id = cur.lastrowid
        action = "created"
    conn.commit()
    conn.close()
    return period_id, action


def setPeriodLimit(pid, period_id, amount):
    conn = connect()
    conn.execute("UPDATE periods SET limit_amount = ? WHERE id = ? AND profile_id = ?", (amount, period_id, pid))
    conn.commit()
    conn.close()


def getSpent(pid, start, end):
    conn = connect()
    row = conn.execute("""
    SELECT COALESCE(SUM(amount), 0) FROM expenses
    WHERE profile_id = ? AND date BETWEEN ? AND ?
    """, (pid, start, end)).fetchone()
    conn.close()
    return row[0]


def getPeriodExpenses(pid, start, end, sort="date", direction="desc"):
    columns = {
        "date": "e.date",
        "category": "e.category",
        "amount": "e.amount",
        "description": "COALESCE(e.description, '')",
    }
    column = columns.get(sort, "e.date")
    order = "ASC" if direction == "asc" else "DESC"
    conn = connect()
    rows = conn.execute(f"""
    SELECT e.id, e.date, e.category, e.amount, e.description FROM expenses e
    WHERE e.profile_id = ? AND e.date BETWEEN ? AND ?
    ORDER BY {column} {order}, e.id {order}
    """, (pid, start, end)).fetchall()
    conn.close()
    return rows


def getPeriodHistory(pid, year=None, sort="period", direction="desc"):
    columns = {
        "period": ("p.end_date", False),
        "spent": ("spent", False),
        "limit": ("p.limit_amount", True),
        "remaining": ("(p.limit_amount - COALESCE(SUM(e.amount), 0))", True),
    }
    expression, nullable = columns.get(sort, columns["period"])
    order = "ASC" if direction == "asc" else "DESC"
    order_by = f"{expression} IS NULL, {expression} {order}" if nullable else f"{expression} {order}"
    query = """
    SELECT p.id, p.start_date, p.end_date, p.limit_amount, COALESCE(SUM(e.amount), 0) AS spent
    FROM periods p
    LEFT JOIN expenses e ON e.profile_id = p.profile_id AND e.date BETWEEN p.start_date AND p.end_date
    WHERE p.profile_id = ?
    """
    params = [pid]
    if year:
        query += " AND substr(p.end_date, 1, 4) = ?"
        params.append(str(year))
    query += f" GROUP BY p.id ORDER BY {order_by}, p.end_date DESC"
    conn = connect()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return rows


def getPeriodYears(pid):
    conn = connect()
    rows = conn.execute("""
    SELECT DISTINCT substr(end_date, 1, 4) AS year FROM periods
    WHERE profile_id = ? ORDER BY year DESC
    """, (pid,)).fetchall()
    conn.close()
    return rows


def save(pid, exp_date, category, amount, description):
    conn = connect()
    conn.execute("""
    INSERT INTO expenses(profile_id, date, category, amount, description)
    VALUES (?, ?, ?, ?, ?)
    """, (pid, exp_date, category, amount, description))
    conn.commit()
    conn.close()


def deleteExpense(pid, eid):
    conn = connect()
    conn.execute("DELETE FROM expenses WHERE id = ? AND profile_id = ?", (eid, pid))
    conn.commit()
    conn.close()
