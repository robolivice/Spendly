import os
from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import Flask, flash, redirect, render_template, request, session, url_for

import currency
import cycles
import db
import insights
import paths
import settings
import theme_catalog

app = Flask(
    __name__,
    template_folder=str(paths.resource_path("templates")),
    static_folder=str(paths.resource_path("static")),
)
app.secret_key = os.environ.get("SPENDLY_SECRET_KEY") or settings.ensure_secret()
app.config.update(
    DEBUG=False,
    TEMPLATES_AUTO_RELOAD=False,
    SESSION_COOKIE_SAMESITE="Lax",
)

DESKTOP_MODE = bool(os.environ.get("SPENDLY_DESKTOP"))

db.setup()

CATEGORY_COLORS = {
    "cat-food": "var(--cat-food)",
    "cat-transport": "var(--cat-transport)",
    "cat-shopping": "var(--cat-shopping)",
    "cat-bills": "var(--cat-bills)",
    "cat-other": "var(--cat-other)",
    "accent": "var(--accent)",
    "accent-2": "var(--accent-2)",
    "ok": "var(--ok)",
    "warn": "var(--warn)",
    "over": "var(--over)",
}

CATEGORY_COLOR_OPTIONS = (
    ("cat-food", "Amber"),
    ("cat-transport", "Sky"),
    ("cat-shopping", "Violet"),
    ("cat-bills", "Rose"),
    ("cat-other", "Slate"),
    ("accent", "Accent"),
    ("accent-2", "Accent 2"),
    ("ok", "Green"),
    ("warn", "Gold"),
    ("over", "Red"),
)


def category_color(token):
    return CATEGORY_COLORS.get(token, CATEGORY_COLORS["cat-other"])


def category_view(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "color": row["color"],
        "css_color": category_color(row["color"]),
        "budget": row["budget"],
        "position": row["position"],
    }


def parse_category_budget(raw):
    value = (raw or "").strip()
    if not value:
        return None
    amount = float(value)
    if amount < 0:
        raise ValueError
    return round(amount, 2)


def normalize_category_name(raw):
    value = " ".join((raw or "").split())
    if not value:
        return None
    return value[:40]


def choose_category(pid, raw):
    rows = db.getCategories(pid)
    names = [row["name"] for row in rows]
    if raw in names:
        return raw
    if "Other" in names:
        return "Other"
    return names[0] if names else "Other"


def category_spending(pid, start, end):
    if start is None or end is None:
        return {}, {}
    rows = db.getCategorySpending(pid, start, end)
    return (
        {row["category"]: row["spent"] for row in rows},
        {row["category"]: row["count"] for row in rows},
    )


def build_insights(pid, period, expenses, categories, today):
    start = date.fromisoformat(period["start_date"])
    end = date.fromisoformat(period["end_date"])
    spent = period["spent"]
    limit = period["limit"]
    pacing = insights.pacing(start, end, spent, limit, today)
    cumulative = insights.daily_series(expenses, start, end, today)
    ideal = insights.ideal_series(limit, pacing["total_days"], len(cumulative))
    chart = insights.pace_geometry(cumulative, ideal)
    spending, counts = category_spending(pid, period["start_date"], period["end_date"])
    breakdown = insights.category_breakdown(categories, spending, spent, counts)
    visible = [item for item in breakdown if item["spent"] > 0]
    donut = insights.donut_geometry(
        [
            {
                "name": item["name"],
                "value": item["spent"],
                "css_color": item["css_color"],
            }
            for item in visible
        ]
    )
    return {
        "pacing": pacing,
        "chart": chart,
        "series": cumulative,
        "ideal": ideal,
        "breakdown": breakdown,
        "visible": visible,
        "donut": donut,
    }



def active_currency():
    return currency.normalize(settings.get("currency"))


@app.context_processor
def inject_desktop():
    return {"is_desktop": DESKTOP_MODE, "app_version": paths.APP_VERSION}


@app.context_processor
def inject_preferences():
    code = active_currency()
    return {
        "currency": code,
        "currency_info": currency.CURRENCIES[code],
        "currency_options": [
            currency.CURRENCIES[item] for item in currency.CURRENCY_CODES
        ],
    }


@app.context_processor
def inject_categories():
    pid = session.get("pid")
    if pid is None:
        return {"categories": [], "category_colors": {}}
    rows = db.getCategories(pid)
    views = [category_view(row) for row in rows]
    return {
        "categories": views,
        "category_colors": {
            item["name"]: item["css_color"] for item in views
        },
    }


@app.context_processor
def inject_undo():
    action_id = request.args.get("undo", type=int)
    if action_id is None:
        return {"undo_action": None}
    return {"undo_action": db.getPendingAction(session.get("pid"), action_id)}


@app.template_filter("money")
def money(value):
    return currency.format_amount(value, active_currency())


@app.context_processor
def inject_themes():
    return {
        "themes": theme_catalog.THEMES,
        "theme_ids": theme_catalog.THEME_IDS,
        "default_theme": theme_catalog.DEFAULT_THEME,
        "default_theme_meta": theme_catalog.THEMES_BY_ID[
            theme_catalog.DEFAULT_THEME
        ]["meta_color"],
        "system_light_theme": theme_catalog.SYSTEM_LIGHT_THEME,
        "system_dark_theme": theme_catalog.SYSTEM_DARK_THEME,
        "theme_config": [
            {"id": theme["id"], "name": theme["name"], "metaColor": theme["meta_color"]}
            for theme in theme_catalog.THEMES
        ],
    }


def make_period(row, today, spent=0):
    start = date.fromisoformat(row["start_date"])
    end = date.fromisoformat(row["end_date"])
    limit = row["limit_amount"]
    remaining = None
    percent = 0
    status = "none"
    if limit is not None:
        remaining = limit - spent
        if limit > 0:
            percent = spent / limit * 100
        elif spent > 0:
            percent = 100
        if percent > 100 or (limit == 0 and spent > 0):
            status = "over"
        elif percent >= 80:
            status = "warn"
        else:
            status = "ok"
    return {
        "id": row["id"],
        "start_date": row["start_date"],
        "end_date": row["end_date"],
        "label": cycles.label(end),
        "dates": cycles.dates(start, end),
        "year": end.year,
        "is_current": start <= today <= end,
        "spent": spent,
        "limit": limit,
        "remaining": remaining,
        "percent": percent,
        "bar": min(percent, 100),
        "status": status,
    }


def safe_next(default):
    target = request.form.get("next", "")
    if target.startswith("/") and not target.startswith("//"):
        return target
    return default


def with_query(target, **values):
    parts = urlsplit(target)
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key not in values
    ]
    query.extend((key, str(value)) for key, value in values.items())
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )


@app.route("/")
def index():
    profiles = db.getProfiles()
    return render_template(
        "profiles.html", profiles=profiles, active_pid=session.get("pid")
    )


@app.route("/profile/create", methods=["POST"])
def create():
    name = request.form["name"].strip()
    if name == "":
        return redirect(url_for("index"))
    pid = db.createProfile(name)
    if pid is None:
        return redirect(url_for("index"))
    session["pid"] = pid
    return redirect(url_for("dashboard"))


@app.route("/profile/rename", methods=["POST"])
def renameProfile():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    profile = db.getProfile(pid)
    if profile is None:
        return redirect(url_for("switch"))
    target = request.form.get("next", "")
    if not target.startswith("/") or target.startswith("//"):
        target = url_for("dashboard")
    name = request.form.get("name", "").strip()
    if name == "":
        flash("Profile name cannot be empty.", "error")
    elif name == profile["name"]:
        pass
    elif db.renameProfile(pid, name):
        flash("Profile renamed.", "ok")
    else:
        flash(f'A profile named "{name}" already exists.', "error")
    return redirect(target)


@app.route("/profile/delete/<int:pid>", methods=["DELETE"])
def deleteProfile(pid):
    db.deleteProfile(pid)
    if session.get("pid") == pid:
        session.pop("pid", None)
    return "", 204


@app.route("/profile/select/<int:pid>")
def select(pid):
    if db.getProfile(pid) is None:
        return redirect(url_for("index"))
    session["pid"] = pid
    return redirect(url_for("dashboard"))


@app.route("/switch")
def switch():
    session.pop("pid", None)
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    profile = db.getProfile(pid)
    if profile is None:
        return redirect(url_for("switch"))
    today = date.today()
    cycle = db.getCycle(pid)
    if cycle is None:
        return render_template(
            "dashboard.html", profile=profile, cycle=None, periods=[], period=None,
            today=today.isoformat(),
            default_start=today.replace(day=1).isoformat(),
            default_end=cycles.month_end(today.year, today.month, 31).isoformat(),
        )
    current = db.ensurePeriods(pid, today)
    rows = db.getPeriods(pid)
    views = [make_period(row, today) for row in rows]
    selected = None
    range_start = request.args.get("start")
    range_end = request.args.get("end")
    parsed_range = False
    selected_id = request.args.get("period", type=int)
    if selected_id:
        selected = db.getPeriod(pid, selected_id) or current
    elif range_start and range_end:
        try:
            start_date = date.fromisoformat(range_start)
            end_date = date.fromisoformat(range_end)
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            range_start = start_date.isoformat()
            range_end = end_date.isoformat()
            parsed_range = True
            selected = db.getPeriodByRange(pid, range_start, range_end)
        except ValueError:
            range_start = None
            range_end = None
    if selected is None and not parsed_range:
        selected = current
    save_state = None
    save_limit = None
    save_target = None
    save_label = None
    overlap_names = []
    future_default = False
    if selected is not None:
        range_start = selected["start_date"]
        range_end = selected["end_date"]
        spent = db.getSpent(pid, range_start, range_end)
        period = make_period(selected, today, spent)
    else:
        start_date = date.fromisoformat(range_start)
        end_date = date.fromisoformat(range_end)
        spent = db.getSpent(pid, range_start, range_end)
        period = {
            "id": None,
            "start_date": range_start,
            "end_date": range_end,
            "label": "Custom range",
            "dates": cycles.dates(start_date, end_date),
            "year": end_date.year,
            "is_current": start_date <= today <= end_date,
            "spent": spent,
            "limit": None,
            "remaining": None,
            "percent": 0,
            "bar": 0,
            "status": "none",
        }
        overlaps = db.getOverlappingPeriods(pid, range_start, range_end)
        save_label = cycles.label(end_date)
        future_default = end_date >= today
        if len(overlaps) > 1:
            save_state = "blocked"
            overlap_names = [
                f"{cycles.label(date.fromisoformat(row['end_date']))} ({row['start_date']} to {row['end_date']})"
                for row in overlaps
            ]
        elif len(overlaps) == 1:
            save_state = "update"
            save_limit = overlaps[0]["limit_amount"]
            save_target = (
                f"{cycles.label(date.fromisoformat(overlaps[0]['end_date']))} "
                f"({overlaps[0]['start_date']} to {overlaps[0]['end_date']})"
            )
        else:
            save_state = "add"
            previous = db.getPeriodBefore(pid, range_start)
            if previous is not None:
                save_limit = previous["limit_amount"]
    ids = [view["id"] for view in views]
    anchor = selected or db.getPeriodContaining(pid, range_start)
    older = None
    newer = None
    if anchor:
        index = ids.index(anchor["id"])
        older = ids[index + 1] if index + 1 < len(ids) else None
        newer = ids[index - 1] if index > 0 else None
    sort = request.args.get("sort", "date")
    if sort not in ("date", "category", "amount", "description"):
        sort = "date"
    direction = request.args.get("dir", "desc")
    if direction not in ("asc", "desc"):
        direction = "desc"
    expenses = db.getPeriodExpenses(pid, range_start, range_end, sort, direction)
    category_views = [category_view(row) for row in db.getCategories(pid)]
    insight = build_insights(pid, period, expenses, category_views, today)
    return render_template(
        "dashboard.html", profile=profile, cycle=cycle, periods=views, period=period,
        older=older, newer=newer, expenses=expenses, sort=sort, direction=direction,
        range_start=range_start, range_end=range_end, today=today.isoformat(),
        save_state=save_state, save_limit=save_limit, save_target=save_target,
        save_label=save_label, overlap_names=overlap_names, future_default=future_default,
        insight=insight,
    )


@app.route("/period/settings")
def period_settings():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    profile = db.getProfile(pid)
    if profile is None:
        return redirect(url_for("switch"))
    cycle = db.getCycle(pid)
    if cycle is None:
        flash("Set up your monthly cycle first.", "error")
        return redirect(url_for("dashboard"))
    today = date.today()
    db.ensurePeriods(pid, today)
    rows = db.getPeriods(pid)
    views = [make_period(row, today) for row in rows]
    selected_id = request.args.get("period", type=int)
    period = next((view for view in views if view["id"] == selected_id), None)
    if period is None:
        current = db.getPeriodContaining(pid, today.isoformat())
        period = next(
            (view for view in views if current is not None and view["id"] == current["id"]),
            None,
        )
    if period is None and views:
        period = views[0]
    category_rows = [category_view(row) for row in db.getCategories(pid)]
    if period is not None:
        spending, counts = category_spending(
            pid, period["start_date"], period["end_date"]
        )
        category_rows = insights.category_breakdown(
            category_rows, spending, period["spent"], counts, sort_items=False
        )
    else:
        category_rows = insights.category_breakdown(
            category_rows, {}, 0, {}, sort_items=False
        )
    new_start = None
    new_end = None
    if rows:
        previous_start, previous_end = cycles.previous(
            date.fromisoformat(rows[-1]["start_date"]), cycle["end_day"]
        )
        new_start = previous_start.isoformat()
        new_end = previous_end.isoformat()
    return render_template(
        "period_settings.html", profile=profile, cycle=cycle, periods=views,
        period=period, new_start=new_start, new_end=new_end,
        categories=category_rows,
        category_color_options=[
            {"token": token, "label": label, "css_color": category_color(token)}
            for token, label in CATEGORY_COLOR_OPTIONS
        ],
    )


@app.route("/settings/preferences", methods=["POST"])
def save_preferences():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    code = currency.normalize(request.form.get("currency"))
    settings.set("currency", code)
    flash("Preferences saved.", "ok")
    return redirect(safe_next(url_for("period_settings")))


@app.route("/categories/add", methods=["POST"])
def category_add():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    target = safe_next(url_for("period_settings"))
    name = normalize_category_name(request.form.get("name"))
    if not name:
        flash("Enter a category name.", "error")
        return redirect(target)
    color = request.form.get("color", "")
    if color not in CATEGORY_COLORS:
        color = "cat-other"
    try:
        budget = parse_category_budget(request.form.get("budget"))
    except ValueError:
        flash("Enter a valid category budget.", "error")
        return redirect(target)
    if db.addCategory(pid, name, color, budget) is None:
        flash(f'A category named "{name}" already exists.', "error")
    else:
        flash("Category added.", "ok")
    return redirect(target)


@app.route("/categories/<int:category_id>/update", methods=["POST"])
def category_update(category_id):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    target = safe_next(url_for("period_settings"))
    if db.getCategory(pid, category_id) is None:
        flash("Category not found.", "error")
        return redirect(target)
    name = normalize_category_name(request.form.get("name"))
    if not name:
        flash("Enter a category name.", "error")
        return redirect(target)
    color = request.form.get("color", "")
    if color not in CATEGORY_COLORS:
        color = "cat-other"
    try:
        budget = parse_category_budget(request.form.get("budget"))
    except ValueError:
        flash("Enter a valid category budget.", "error")
        return redirect(target)
    updated = db.updateCategory(pid, category_id, name, color, budget)
    if updated is None:
        flash("Category not found.", "error")
    elif not updated:
        flash(f'A category named "{name}" already exists.', "error")
    else:
        flash("Category saved.", "ok")
    return redirect(target)


@app.route("/categories/<int:category_id>/delete", methods=["POST"])
def category_delete(category_id):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    target = safe_next(url_for("period_settings"))
    result = db.deleteCategory(pid, category_id)
    if result == "ok":
        flash("Category deleted.", "ok")
    elif result == "used":
        flash("That category still has expenses. Move or delete them first.", "error")
    elif result == "last":
        flash("Keep at least one category.", "error")
    else:
        flash("Category not found.", "error")
    return redirect(target)


@app.route("/search")
def search():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    profile = db.getProfile(pid)
    if profile is None:
        return redirect(url_for("switch"))
    if db.getCycle(pid) is None:
        return redirect(url_for("dashboard"))
    today = date.today()
    db.ensurePeriods(pid, today)
    query = request.args.get("q", "").strip()[:120]
    scope = request.args.get("scope", "current")
    if scope not in ("current", "all"):
        scope = "current"
    current = db.getPeriodContaining(pid, today.isoformat())
    range_start = None
    range_end = None
    if scope == "current" and current is not None:
        range_start = current["start_date"]
        range_end = current["end_date"]
    elif scope == "current":
        scope = "all"
    results = db.searchExpenses(pid, query, range_start, range_end) if query else []
    return render_template(
        "search.html",
        profile=profile,
        query=query,
        scope=scope,
        results=results,
        total=sum(row["amount"] for row in results),
        current_period=current,
    )


@app.route("/themes")
def themes():
    profile = None
    pid = session.get("pid")
    if pid is not None:
        profile = db.getProfile(pid)
    return render_template("themes.html", profile=profile)


@app.route("/history")
def history():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    profile = db.getProfile(pid)
    if profile is None:
        return redirect(url_for("switch"))
    if db.getCycle(pid) is None:
        return redirect(url_for("dashboard"))
    today = date.today()
    db.ensurePeriods(pid, today)
    year = request.args.get("year") or None
    sort = request.args.get("sort", "period")
    if sort not in ("period", "spent", "limit", "remaining"):
        sort = "period"
    direction = request.args.get("dir", "desc")
    if direction not in ("asc", "desc"):
        direction = "desc"
    rows = db.getPeriodHistory(pid, year, sort, direction)
    periods = [make_period(row, today, row["spent"]) for row in rows]
    years = [row["year"] for row in db.getPeriodYears(pid)]
    summary = {
        "count": len(periods),
        "spent": sum(period["spent"] for period in periods),
        "over": sum(1 for period in periods if period["status"] == "over"),
        "near": sum(1 for period in periods if period["status"] == "warn"),
    }
    return render_template(
        "history.html", profile=profile, periods=periods, years=years, year=year,
        sort=sort, direction=direction, summary=summary
    )


@app.route("/cycle", methods=["POST"])
def cycle():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    target = safe_next(url_for("dashboard"))
    if db.getCycle(pid):
        try:
            end_day = int(request.form["end_day"])
        except (KeyError, ValueError):
            flash("Choose an end day between 1 and 31.", "error")
            return redirect(target)
        if end_day < 1 or end_day > 31:
            flash("Choose an end day between 1 and 31.", "error")
            return redirect(target)
        db.setCycleDay(pid, end_day)
        flash("Cycle end day saved. It applies from the next period.", "ok")
        return redirect(target)
    raw_start = request.form.get("start")
    raw_end = request.form.get("end")
    if raw_start and raw_end:
        try:
            start_date = date.fromisoformat(raw_start)
            end_date = date.fromisoformat(raw_end)
        except ValueError:
            flash("Choose valid start and end dates.", "error")
            return redirect(target)
        if start_date > end_date:
            flash("The start date must be on or before the end date.", "error")
            return redirect(target)
        if start_date > date.today():
            flash("The first period cannot start in the future.", "error")
            return redirect(target)
        raw = request.form.get("amount", "").strip()
        amount = None
        if raw:
            try:
                amount = float(raw)
            except ValueError:
                flash("Enter a valid limit.", "error")
                return redirect(target)
            if amount < 0:
                flash("The limit cannot be negative.", "error")
                return redirect(target)
        db.setupCycle(pid, cycles.end_day_for(end_date), amount, start=start_date, end=end_date)
        db.ensurePeriods(pid)
        flash("Cycle set up.", "ok")
        return redirect(target)
    try:
        end_day = int(request.form["end_day"])
    except (KeyError, ValueError):
        flash("Choose an end day between 1 and 31.", "error")
        return redirect(target)
    if end_day < 1 or end_day > 31:
        flash("Choose an end day between 1 and 31.", "error")
        return redirect(target)
    raw = request.form.get("amount", "").strip()
    amount = None
    if raw:
        try:
            amount = float(raw)
        except ValueError:
            flash("Enter a valid limit.", "error")
            return redirect(target)
        if amount < 0:
            flash("The limit cannot be negative.", "error")
            return redirect(target)
    db.setupCycle(pid, end_day, amount, apply_history=request.form.get("apply_history") == "on")
    return redirect(target)


@app.route("/period/save", methods=["POST"])
def period_save():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    raw_start = request.form.get("start", "").strip()
    raw_end = request.form.get("end", "").strip()
    try:
        start_date = date.fromisoformat(raw_start)
        end_date = date.fromisoformat(raw_end)
    except ValueError:
        flash("Choose valid start and end dates.", "error")
        return redirect(safe_next(url_for("dashboard")))
    if start_date > end_date:
        flash("The start date must be on or before the end date.", "error")
        return redirect(safe_next(
            url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat())
        ))
    raw = request.form.get("amount", "").strip()
    amount = None
    if raw:
        try:
            amount = float(raw)
        except ValueError:
            flash("Enter a valid limit.", "error")
            return redirect(safe_next(
                url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat())
            ))
        if amount < 0:
            flash("The limit cannot be negative.", "error")
            return redirect(safe_next(
                url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat())
            ))
    period_id, action = db.savePeriod(
        pid, start_date.isoformat(), end_date.isoformat(), amount
    )
    if period_id is None:
        flash("That range overlaps more than one saved period. Choose a range within one month.", "error")
        return redirect(safe_next(
            url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat())
        ))
    if request.form.get("future") == "on":
        db.setCycleDay(pid, cycles.end_day_for(end_date))
    label = cycles.label(end_date)
    flash(f"{label} {'updated' if action == 'updated' else 'added'}.", "ok")
    return redirect(safe_next(url_for("dashboard", period=period_id)))


@app.route("/period/<int:period_id>/limit", methods=["POST"])
def period_limit(period_id):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    if db.getPeriod(pid, period_id) is None:
        return redirect(url_for("dashboard"))
    raw = request.form.get("amount", "").strip()
    amount = None
    if raw:
        try:
            amount = float(raw)
        except ValueError:
            flash("Enter a valid limit.", "error")
            return redirect(url_for("dashboard", period=period_id))
        if amount < 0:
            flash("The limit cannot be negative.", "error")
            return redirect(url_for("dashboard", period=period_id))
    db.setPeriodLimit(pid, period_id, amount)
    return redirect(url_for("dashboard", period=period_id))


@app.route("/period/<int:period_id>/range", methods=["POST"])
def period_range(period_id):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    target = safe_next(url_for("dashboard", period=period_id))
    if db.getPeriod(pid, period_id) is None:
        flash("Period not found.", "error")
        return redirect(target)
    raw_start = request.form.get("start", "").strip()
    raw_end = request.form.get("end", "").strip()
    try:
        start_date = date.fromisoformat(raw_start)
        end_date = date.fromisoformat(raw_end)
    except ValueError:
        flash("Choose valid start and end dates.", "error")
        return redirect(target)
    if start_date > end_date:
        flash("The start date must be on or before the end date.", "error")
        return redirect(target)
    if db.updatePeriodRange(pid, period_id, start_date.isoformat(), end_date.isoformat()):
        flash("Period dates updated.", "ok")
    else:
        flash("Those dates overlap another saved period.", "error")
    return redirect(target)


@app.route("/expense/add", methods=["POST"])
def add():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    exp_date = request.form["date"]
    try:
        parsed = date.fromisoformat(exp_date)
    except ValueError:
        flash("Enter a valid date.", "error")
        return redirect(url_for("dashboard"))
    if parsed > date.today():
        flash("Expense dates cannot be in the future.", "error")
        return redirect(url_for("dashboard"))
    try:
        amount = float(request.form["amount"])
    except (KeyError, ValueError):
        flash("Enter a valid amount.", "error")
        return redirect(url_for("dashboard"))
    if amount < 0:
        flash("The amount cannot be negative.", "error")
        return redirect(url_for("dashboard"))
    category = choose_category(pid, request.form.get("category", "Other"))
    description = request.form.get("description", "").strip()
    db.save(pid, exp_date, category, amount, description)
    db.ensurePeriods(pid)
    range_start = request.form.get("start")
    range_end = request.form.get("end")
    if range_start and range_end and range_start <= exp_date <= range_end:
        return redirect(url_for("dashboard", start=range_start, end=range_end))
    period = db.getPeriodContaining(pid, exp_date)
    if period is None:
        return redirect(url_for("dashboard"))
    return redirect(url_for("dashboard", period=period["id"]))


@app.route("/expense/<int:eid>/edit", methods=["POST"])
def edit_expense(eid):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    expense = db.getExpense(pid, eid)
    if expense is None:
        flash("Expense not found.", "error")
        return redirect(safe_next(url_for("dashboard")))
    exp_date = request.form.get("date", "").strip()
    try:
        parsed = date.fromisoformat(exp_date)
    except ValueError:
        flash("Enter a valid date.", "error")
        return redirect(safe_next(url_for("dashboard")))
    if parsed > date.today():
        flash("Expense dates cannot be in the future.", "error")
        return redirect(safe_next(url_for("dashboard")))
    try:
        amount = float(request.form["amount"])
    except (KeyError, ValueError):
        flash("Enter a valid amount.", "error")
        return redirect(safe_next(url_for("dashboard")))
    if amount < 0:
        flash("The amount cannot be negative.", "error")
        return redirect(safe_next(url_for("dashboard")))
    category = choose_category(pid, request.form.get("category", "Other"))
    description = request.form.get("description", "").strip()
    db.updateExpense(pid, eid, exp_date, category, amount, description)
    db.ensurePeriods(pid)
    flash("Expense updated.", "ok")
    target = safe_next("")
    if target:
        return redirect(target)
    period = db.getPeriodContaining(pid, exp_date)
    if period is not None:
        return redirect(url_for("dashboard", period=period["id"]))
    return redirect(url_for("dashboard"))


@app.route("/expense/delete/<int:eid>", methods=["POST"])
def delete(eid):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    expense = db.deleteExpense(pid, eid)
    target = safe_next("")
    if not target:
        range_start = request.form.get("start")
        range_end = request.form.get("end")
        period_id = request.form.get("period", type=int)
        if range_start and range_end:
            target = url_for("dashboard", start=range_start, end=range_end)
        elif period_id and db.getPeriod(pid, period_id):
            target = url_for("dashboard", period=period_id)
        else:
            target = url_for("dashboard")
    if expense is not None:
        action_id = db.logDeleteAction(pid, expense)
        target = with_query(target, undo=action_id)
    return redirect(target)


@app.route("/expense/undo/<int:action_id>", methods=["POST"])
def undo_expense(action_id):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    restored = db.undoDelete(pid, action_id)
    if restored is None:
        flash("That action can no longer be undone.", "error")
    else:
        flash("Expense restored.", "ok")
    return redirect(safe_next(url_for("dashboard")))


if __name__ == "__main__":
    app.run(debug=True)
