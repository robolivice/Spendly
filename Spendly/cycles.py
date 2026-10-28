import calendar
from datetime import date, timedelta


def add_month(year, month, count=1):
    index = year * 12 + month - 1 + count
    return index // 12, index % 12 + 1


def clamp(year, month, day):
    return min(day, calendar.monthrange(year, month)[1])


def month_end(year, month, day):
    return date(year, month, clamp(year, month, day))


def end_day_for(end):
    return 31 if end.day == calendar.monthrange(end.year, end.month)[1] else end.day


def bounds(end, day):
    year, month = add_month(end.year, end.month, -1)
    return month_end(year, month, day) + timedelta(days=1), end


def current(day, today):
    end = month_end(today.year, today.month, day)
    if today > end:
        year, month = add_month(today.year, today.month)
        end = month_end(year, month, day)
    return bounds(end, day)


def next_period(end, day):
    candidate = month_end(end.year, end.month, day)
    if candidate <= end:
        year, month = add_month(end.year, end.month)
        candidate = month_end(year, month, day)
    return end + timedelta(days=1), candidate


def previous(start, day):
    end = start - timedelta(days=1)
    year, month = add_month(end.year, end.month, -1)
    return month_end(year, month, day) + timedelta(days=1), end


def dates(start, end):
    if start.year == end.year:
        return f"{start.strftime('%b')} {start.day} - {end.strftime('%b')} {end.day}, {end.year}"
    return f"{start.strftime('%b')} {start.day}, {start.year} - {end.strftime('%b')} {end.day}, {end.year}"


def label(end):
    return end.strftime("%B %Y")
