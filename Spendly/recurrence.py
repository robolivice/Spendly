import calendar
from datetime import date, timedelta

CADENCES = ("weekly", "monthly", "yearly")
CADENCE_LABELS = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "yearly": "Yearly",
}


def add_month(year, month, count=1):
    index = year * 12 + month - 1 + count
    return index // 12, index % 12 + 1


def clamp_day(year, month, day):
    return min(day, calendar.monthrange(year, month)[1])


def next_date(current, cadence, anchor):
    if cadence == "weekly":
        return current + timedelta(days=7)
    if cadence == "monthly":
        year, month = add_month(current.year, current.month)
        return date(year, month, clamp_day(year, month, anchor.day))
    if cadence == "yearly":
        year = current.year + 1
        month = anchor.month
        return date(year, month, clamp_day(year, month, anchor.day))
    raise ValueError(f"Unknown cadence: {cadence}")


def due_dates(next_due, cadence, anchor, end=None, today=None, limit=1000):
    try:
        due = next_due if isinstance(next_due, date) else date.fromisoformat(str(next_due))
    except ValueError:
        return []
    if today is None:
        today = date.today()
    results = []
    while due <= today and (end is None or due <= end) and len(results) < limit:
        results.append(due)
        try:
            due = next_date(due, cadence, anchor)
        except ValueError:
            break
    return results
