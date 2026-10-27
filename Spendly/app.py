from flask import Flask, render_template, request, redirect, url_for, session
from datetime import date
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

    month = request.args.get("month")
    if not month:
        month = date.today().strftime("%Y-%m")

    expenses = db.monthRange(pid, month)
    spent, limit = db.endStats(pid, month)

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

    return render_template(
        "dashboard.html",
        profile=profile, month=month, expenses=expenses,
        spent=spent, limit=limit, remaining=remaining,
        percent=percent, bar=bar, status=status,
        today=date.today().strftime("%Y-%m-%d")
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
    return redirect(url_for("dashboard", month=exp_date[:7]))

@app.route("/expense/delete/<int:eid>", methods=["POST"])
def delete(eid):
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    db.deleteExpense(pid, eid)
    return redirect(url_for("dashboard", month=request.form["month"]))

@app.route("/limit", methods=["POST"])
def limit():
    pid = session.get("pid")
    if pid is None:
        return redirect(url_for("index"))
    month = request.form["month"]
    amount = float(request.form["amount"])
    db.setLimit(pid, month, amount)
    return redirect(url_for("dashboard", month=month))

if __name__ == "__main__":
    app.run(debug=True)