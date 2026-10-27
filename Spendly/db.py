import sqlite3

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
        month TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(profile_id, month),
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )""")
    conn.commit()
    conn.close()

def getProfiles():
    conn = connect()
    rows = conn.execute("SELECT id, name FROM profiles").fetchall()
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

def save(pid, exp_date, category, amount, description):
    conn = connect()
    conn.execute(
        "INSERT INTO expenses(profile_id, date, category, amount, description) VALUES (?, ?, ?, ?, ?)",
        (pid, exp_date, category, amount, description)
    )
    conn.commit()
    conn.close()

def deleteExpense(pid, eid):
    conn = connect()
    conn.execute("DELETE FROM expenses WHERE id = ? AND profile_id = ?", (eid, pid))
    conn.commit()
    conn.close()

def monthRange(pid, month):
    start = month + "-01"
    end = month + "-31"
    conn = connect()
    rows = conn.execute(
        "SELECT id, date, category, amount, description FROM expenses "
        "WHERE profile_id = ? AND date BETWEEN ? AND ? ORDER BY date DESC",
        (pid, start, end)
    ).fetchall()
    conn.close()
    return rows

def setLimit(pid, month, amount):
    conn = connect()
    conn.execute("""
    INSERT INTO limits(profile_id, month, amount) VALUES (?, ?, ?)
    ON CONFLICT(profile_id, month) DO UPDATE SET amount = excluded.amount
    """, (pid, month, amount))
    conn.commit()
    conn.close()

def endStats(pid, month):
    conn = connect()
    row = conn.execute(
        "SELECT SUM(amount) FROM expenses WHERE profile_id = ? AND date LIKE ?",
        (pid, month + "%")
    ).fetchone()
    spent = row[0]
    if spent is None:
        spent = 0
    row = conn.execute(
        "SELECT amount FROM limits WHERE profile_id = ? AND month = ?",
        (pid, month)
    ).fetchone()
    limit = None
    if row:
        limit = row[0]
    conn.close()
    return spent, limit