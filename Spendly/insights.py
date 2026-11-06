import math
from datetime import date


def round2(value):
    return round(float(value or 0), 2)


def days_inclusive(start, end):
    return (end - start).days + 1


def pacing(start, end, spent, limit, today):
    total_days = max(1, days_inclusive(start, end))
    if start > today:
        elapsed_days = 0
    else:
        cutoff = end if end < today else today
        elapsed_days = max(0, min(days_inclusive(start, cutoff), total_days))
    days_left = max(0, total_days - elapsed_days)
    remaining = None if limit is None else round2(limit - spent)
    if remaining is None:
        safe_per_day = None
    elif remaining > 0:
        safe_per_day = round2(remaining / days_left) if days_left > 0 else 0
    else:
        safe_per_day = 0
    burn_rate = spent / elapsed_days if elapsed_days > 0 else 0
    projected = round2(burn_rate * total_days)
    expected = None if limit is None else round2(limit * elapsed_days / total_days)
    if expected is None:
        pace_delta = None
        pace_percent = None
    else:
        pace_delta = round2(spent - expected) if elapsed_days > 0 else 0
        pace_percent = (spent / expected) * 100 if expected else None
    on_pace = pace_delta is None or pace_delta <= 0
    if limit is None:
        projection_status = "none"
    elif projected > limit:
        projection_status = "over"
    elif limit > 0 and projected >= limit * 0.8:
        projection_status = "warn"
    else:
        projection_status = "ok"
    return {
        "total_days": total_days,
        "elapsed_days": elapsed_days,
        "days_left": days_left,
        "safe_per_day": safe_per_day,
        "burn_rate": round2(burn_rate),
        "projected": projected,
        "expected": expected,
        "pace_delta": pace_delta,
        "pace_percent": pace_percent,
        "on_pace": on_pace,
        "remaining": remaining,
        "projection_status": projection_status,
    }


def daily_series(expenses, start, end, today):
    if today < start:
        return []
    cutoff = end if end < today else today
    count = days_inclusive(start, cutoff)
    if count <= 0:
        return []
    daily = [0.0] * count
    for expense in expenses:
        value = date.fromisoformat(str(expense["date"]))
        if value < start or value > cutoff:
            continue
        index = days_inclusive(start, value) - 1
        if 0 <= index < count:
            daily[index] += float(expense["amount"] or 0)
    running = 0.0
    series = []
    for value in daily:
        running += value
        series.append(round2(running))
    return series


def ideal_series(limit, total_days, elapsed_days):
    if limit is None or total_days <= 0 or elapsed_days <= 0:
        return []
    return [
        round2(limit * (index + 1) / total_days)
        for index in range(elapsed_days)
    ]


def pace_geometry(actual, ideal, width=620, height=190):
    count = max(len(actual), len(ideal), 2)
    maximum = max([1.0, *[float(value or 0) for value in actual], *[float(value or 0) for value in ideal]])
    padding = {"top": 14, "right": 10, "bottom": 22, "left": 10}
    plot_width = width - padding["left"] - padding["right"]
    plot_height = height - padding["top"] - padding["bottom"]
    step = plot_width / (count - 1)

    def point(value, index):
        x = padding["left"] + index * step
        y = padding["top"] + plot_height - (float(value or 0) / maximum) * plot_height
        return round(x, 2), round(y, 2)

    actual_points = [point(value, index) for index, value in enumerate(actual)]
    ideal_points = [point(value, index) for index, value in enumerate(ideal)]

    def path(points):
        return " ".join(f"{x},{y}" for x, y in points)

    grid = []
    for fraction in (0, 0.5, 1):
        y = round(padding["top"] + plot_height - plot_height * fraction, 2)
        grid.append({"y": y})

    area = ""
    if len(actual_points) >= 2:
        first = actual_points[0]
        last = actual_points[-1]
        bottom = padding["top"] + plot_height
        area = (
            f"{path(actual_points)} "
            f"{round(last[0], 2)},{round(bottom, 2)} "
            f"{round(first[0], 2)},{round(bottom, 2)}"
        )

    last_point = actual_points[-1] if actual_points else None
    return {
        "width": width,
        "height": height,
        "padding": padding,
        "plot_height": plot_height,
        "grid": grid,
        "actual": path(actual_points),
        "ideal": path(ideal_points),
        "area": area,
        "last": last_point,
        "maximum": maximum,
    }


def donut_geometry(items, size=196, thickness=21, gap=3):
    total = sum(float(item["value"] or 0) for item in items)
    radius = (size - thickness) / 2 - 2
    circumference = 2 * math.pi * radius
    offset = 0.0
    segments = []
    if total > 0:
        for item in items:
            value = float(item["value"] or 0)
            if value <= 0:
                continue
            fraction = value / total
            length = max(0.0, fraction * circumference - gap)
            segments.append(
                {
                    "label": item["name"],
                    "value": round2(value),
                    "color": item["css_color"],
                    "dasharray": f"{length:.2f} {circumference - length:.2f}",
                    "dashoffset": f"{-offset:.2f}",
                }
            )
            offset += fraction * circumference
    return {
        "size": size,
        "thickness": thickness,
        "radius": round(radius, 2),
        "center": round(size / 2, 2),
        "segments": segments,
    }


def category_breakdown(categories, spending, total_spent, counts=None, sort_items=True):
    rows = []
    spending = spending or {}
    counts = counts or {}
    for category in categories:
        name = category["name"]
        spent = round2(spending.get(name, 0))
        count = int(counts.get(name, 0))
        budget = category["budget"]
        if budget is not None:
            budget = round2(budget)
            if budget > 0:
                budget_percent = spent / budget * 100
            elif spent > 0:
                budget_percent = 100
            else:
                budget_percent = 0
            if budget_percent > 100 or (budget == 0 and spent > 0):
                status = "over"
            elif budget_percent >= 80:
                status = "warn"
            else:
                status = "ok"
            remaining = round2(budget - spent)
        else:
            budget_percent = None
            remaining = None
            status = "none"
        rows.append(
            {
                "id": category["id"],
                "name": name,
                "color": category["color"],
                "css_color": category["css_color"],
                "budget": budget,
                "spent": spent,
                "remaining": remaining,
                "percent": round2((spent / total_spent) * 100) if total_spent else 0,
                "budget_percent": round2(budget_percent) if budget_percent is not None else None,
                "bar": round2(min(budget_percent, 100)) if budget_percent is not None else 0,
                "status": status,
                "count": count,
            }
        )
    if sort_items:
        rows.sort(key=lambda item: (-item["spent"], item["name"].lower()))
    return rows
