import sqlite3
#import gui

conn = sqlite3.connect("expense.db")
conn.execute("PRAGMA foreign_keys = ON")
cur = conn.cursor()

def setup():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS profiles(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS expenses(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        category TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS limits(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        month TEXT NOT NULL,
        amount REAL NOT NULL,
        UNIQUE(profile_id, month),
        FOREIGN KEY (profile_id) REFERENCES profiles(id)
    )""")
    conn.commit()


def monthRange(pid, start, end):
    cur.execute(
        "SELECT date, category, amount, description FROM expenses WHERE profile_id = ? AND date BETWEEN ? AND ?",
        (pid, start, end)
    )
    return cur.fetchall()

def dateSelect():
    month = input("Month (YYYY-MM): ")
    start = month + "-01"
    end = month + "-31"
    return month, start, end

def createProfile():
    name = input("New profile name: ")
    cur.execute("SELECT id FROM profiles WHERE name = ?", (name,))
    if cur.fetchone():
        print("Name already exists")
        return None
    cur.execute("INSERT INTO profiles(name) VALUES (?)", (name,))
    conn.commit()
    return cur.lastrowid

def selectProfile():
    cur.execute("SELECT id, name FROM profiles")
    rows = cur.fetchall()
    if len(rows) == 0:
        print("No profiles yet")
        return None
    for r in rows:
        print(r[0], "-", r[1])
    try:
        pid = int(input("Enter profile id: "))
    except ValueError:
        print("Invalid id")
        return None
    for r in rows:
        if r[0] == pid:
            return pid

def profile():
    pid = None
    while pid is None:
        print("1. Select existing profile")
        print("2. Create new profile")
        choice = input("Choose: ")
        if choice == "1":
            pid = selectProfile()
        elif choice == "2":
            pid = createProfile()
        else:
            print("Invalid choice")
    return pid

def limit(pid):
    month = input("Month (YYYY-MM): ")
    cur.execute("SELECT amount FROM limits WHERE profile_id = ? AND month = ?", (pid, month))
    row = cur.fetchone()
    if row:
        print("Current limit:", row[0])
    else:
        print("No limit set yet")
    amount = float(input("New limit: "))
    cur.execute("""
    INSERT INTO limits(profile_id, month, amount) VALUES (?, ?, ?)
    ON CONFLICT(profile_id, month) DO UPDATE SET amount = excluded.amount
    """, (pid, month, amount))
    conn.commit()
    print("Limit saved")

def save(pid, date, category, amount, description):
    cur.execute(
        "INSERT INTO expenses(profile_id, date, category, amount, description) VALUES (?, ?, ?, ?, ?)",
        (pid, date, category, amount, description)
    )
    conn.commit()

#def gui():

def endStats(pid, month):
    cur.execute(
        "SELECT SUM(amount) FROM expenses WHERE profile_id = ? AND date LIKE ?",
        (pid, month + "%")
    )
    total = cur.fetchone()[0]
    if total is None:
        total = 0

    cur.execute("SELECT amount FROM limits WHERE profile_id = ? AND month = ?", (pid, month))
    row = cur.fetchone()

    print("Spent:", total)
    if row:
        print("Limit:", row[0])
        if total > row[0]:
            print("Over limit!")
        else:
            print("Within limit")
    else:
        print("No limit set")

def main():
    setup()
    pid = profile()
    while True:
        print("\n1. Add expense")
        print("2. Set / edit limit")
        print("3. View month")
        print("4. Stats")
        print("5. Switch profile")
        print("6. Exit")
        choice = input("Choose: ")

        if choice == "1":
            date = input("Date (YYYY-MM-DD): ")
            category = input("Category: ")
            amount = float(input("Amount: "))
            description = input("Description: ")
            save(pid, date, category, amount, description)
        elif choice == "2":
            limit(pid)
        elif choice == "3":
            month, start, end = dateSelect()
            for row in monthRange(pid, start, end):
                print(row)
        elif choice == "4":
            month, start, end = dateSelect()
            endStats(pid, month)
        elif choice == "5":
            pid = profile()
        elif choice == "6":
            break
        else:
            print("Invalid choice")

main()