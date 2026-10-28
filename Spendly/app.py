from flask import Flask, render_template, request, redirect, url_for, session
from datetime import date, timedelta
import db

app = Flask(__name__)
app.secret_key = "change-this-secret"

db.setup()

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
    start = request.args.get("start")
    end = request.args.get("end")
    if not start:
        start = today.replace(day=1).strftime("%Y-%m-%d")
    if not end:
        end = today.strftime("%Y-%m-%d")
    if start > end:
        temp = start
        start = end
        end = temp

    expenses = db.monthRange(pid, start, end)
    spent, limit = db.endStats(pid, start, end)

    percent = 0
    remaining = None
    status = "none"
    if limit is not None:
        remaining = limit - spent
        if limit > 0:
            percent = spent / limit * 100
        if percent > 100:
            status = "over"
        elif percent >= 80:
            status = "warn"
        else:
            status = "ok"

    bar = percent
    if bar > 100:
        bar = 100
        
    last30_start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    this_month_start = today.replace(day=1).strftime("%Y-%m-%d")
    prev_end = today.replace(day=1) - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    presets = [
        ["This month", this_month_start, today.strftime("%Y-%m-%d")],
        ["Last 30 days", last30_start, today.strftime("%Y-%m-%d")],
        ["Last month", prev_start.strftime("%Y-%m-%d"), prev_end.strftime("%Y-%m-%d")]
    ]
    
    return render_template(
        "dashboard.html",
        profile=profile, start=start, end=end, expenses=expenses,
        spent=spent, limit=limit, remaining=remaining,
        percent=percent, bar=bar, status=status,
        today=today.strftime("%Y-%m-%d"),
        presets = presets
    )

@app.route("/expense/add", methods=["POST"])
def add():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    exp_date = request.form["date"]
    category = request.form["category"]
    amount = float(request.form["amount"])
    description = request.form["description"]
    db.save(pid, exp_date, category, amount, description)
    return redirect(url_for("dashboard", start=request.form["start"], end=request.form["end"]))

@app.route("/expense/delete/<int:eid>", methods=["POST"])
def delete(eid):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    db.deleteExpense(pid, eid)
    return redirect(url_for("dashboard", start=request.form["start"], end=request.form["end"]))

@app.route("/limit", methods=["POST"])
def limit():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    start = request.form["start"]
    end = request.form["end"]
    amount = float(request.form["amount"])
    db.setLimit(pid, start, end, amount)
    return redirect(url_for("dashboard", start=start, end=end))

if __name__ == "__main__":
    app.run(debug=True)