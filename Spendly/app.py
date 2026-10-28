from flask import Flask, flash, redirect, render_template, request, session, url_for
from datetime import date

import cycles
import db

app = Flask(__name__)
app.secret_key = "change-this-secret"

db.setup()


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


@app.route("/")
def index():
    profiles = db.getProfiles()
    return render_template("profiles.html", profiles=profiles)


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
    new_start = None
    new_end = None
    if rows:
        previous_start, previous_end = cycles.previous(
            date.fromisoformat(rows[-1]["start_date"]), cycle["end_day"]
        )
        new_start = previous_start.isoformat()
        new_end = previous_end.isoformat()
    return render_template(
        "dashboard.html", profile=profile, cycle=cycle, periods=views, period=period,
        older=older, newer=newer, expenses=expenses, sort=sort, direction=direction,
        range_start=range_start, range_end=range_end, today=today.isoformat(),
        save_state=save_state, save_limit=save_limit, save_target=save_target,
        save_label=save_label, overlap_names=overlap_names, future_default=future_default,
        new_start=new_start, new_end=new_end, add_open=request.args.get("add") == "1",
    )


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
    return render_template(
        "history.html", profile=profile, periods=periods, years=years, year=year,
        sort=sort, direction=direction
    )


@app.route("/cycle", methods=["POST"])
def cycle():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    if db.getCycle(pid):
        try:
            end_day = int(request.form["end_day"])
        except (KeyError, ValueError):
            flash("Choose an end day between 1 and 31.", "error")
            return redirect(url_for("dashboard"))
        if end_day < 1 or end_day > 31:
            flash("Choose an end day between 1 and 31.", "error")
            return redirect(url_for("dashboard"))
        db.setCycleDay(pid, end_day)
        flash("Cycle end day saved. It applies from the next period.", "ok")
        return redirect(url_for("dashboard"))
    raw_start = request.form.get("start")
    raw_end = request.form.get("end")
    if raw_start and raw_end:
        try:
            start_date = date.fromisoformat(raw_start)
            end_date = date.fromisoformat(raw_end)
        except ValueError:
            flash("Choose valid start and end dates.", "error")
            return redirect(url_for("dashboard"))
        if start_date > end_date:
            flash("The start date must be on or before the end date.", "error")
            return redirect(url_for("dashboard"))
        if start_date > date.today():
            flash("The first period cannot start in the future.", "error")
            return redirect(url_for("dashboard"))
        raw = request.form.get("amount", "").strip()
        amount = None
        if raw:
            try:
                amount = float(raw)
            except ValueError:
                flash("Enter a valid limit.", "error")
                return redirect(url_for("dashboard"))
            if amount < 0:
                flash("The limit cannot be negative.", "error")
                return redirect(url_for("dashboard"))
        db.setupCycle(pid, cycles.end_day_for(end_date), amount, start=start_date, end=end_date)
        db.ensurePeriods(pid)
        flash("Cycle set up.", "ok")
        return redirect(url_for("dashboard"))
    try:
        end_day = int(request.form["end_day"])
    except (KeyError, ValueError):
        flash("Choose an end day between 1 and 31.", "error")
        return redirect(url_for("dashboard"))
    if end_day < 1 or end_day > 31:
        flash("Choose an end day between 1 and 31.", "error")
        return redirect(url_for("dashboard"))
    raw = request.form.get("amount", "").strip()
    amount = None
    if raw:
        try:
            amount = float(raw)
        except ValueError:
            flash("Enter a valid limit.", "error")
            return redirect(url_for("dashboard"))
        if amount < 0:
            flash("The limit cannot be negative.", "error")
            return redirect(url_for("dashboard"))
    db.setupCycle(pid, end_day, amount, apply_history=request.form.get("apply_history") == "on")
    return redirect(url_for("dashboard"))


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
        return redirect(url_for("dashboard"))
    if start_date > end_date:
        flash("The start date must be on or before the end date.", "error")
        return redirect(url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat()))
    raw = request.form.get("amount", "").strip()
    amount = None
    if raw:
        try:
            amount = float(raw)
        except ValueError:
            flash("Enter a valid limit.", "error")
            return redirect(url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat()))
        if amount < 0:
            flash("The limit cannot be negative.", "error")
            return redirect(url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat()))
    period_id, action = db.savePeriod(
        pid, start_date.isoformat(), end_date.isoformat(), amount
    )
    if period_id is None:
        flash("That range overlaps more than one saved period. Choose a range within one month.", "error")
        return redirect(url_for("dashboard", start=start_date.isoformat(), end=end_date.isoformat()))
    if request.form.get("future") == "on":
        db.setCycleDay(pid, cycles.end_day_for(end_date))
    label = cycles.label(end_date)
    flash(f"{label} {'updated' if action == 'updated' else 'added'}.", "ok")
    if request.form.get("mode") == "past":
        return redirect(url_for("dashboard", period=period_id, add=1))
    return redirect(url_for("dashboard", period=period_id))


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
    category = request.form.get("category", "Other")
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


@app.route("/expense/delete/<int:eid>", methods=["POST"])
def delete(eid):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    db.deleteExpense(pid, eid)
    range_start = request.form.get("start")
    range_end = request.form.get("end")
    if range_start and range_end:
        return redirect(url_for("dashboard", start=range_start, end=range_end))
    period_id = request.form.get("period", type=int)
    if period_id and db.getPeriod(pid, period_id):
        return redirect(url_for("dashboard", period=period_id))
    return redirect(url_for("dashboard"))


if __name__ == "__main__":
    app.run(debug=True)
