import sqlite3
from datetime import date, datetime

from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from database.db import (
    authenticate_user,
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_largest_expenses,
    get_monthly_totals,
    get_recent_expenses,
    get_user_by_id,
    init_db,
    seed_db,
    seed_demo_expenses,
)

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

@app.template_filter("inr")
def inr(amount):
    """₹ with thousands separators and 2 decimals, e.g. ₹18,450.00."""
    return "₹{:,.2f}".format(amount or 0)


@app.template_filter("inr_short")
def inr_short(amount):
    """Compact ₹ for chart axes, e.g. ₹25k."""
    if amount >= 1000:
        return "₹{:g}k".format(round(amount / 1000, 1))
    return "₹{:g}".format(amount)


with app.app_context():
    init_db()
    seed_db()
    seed_demo_expenses("John Doe", "johndoe@gmail.com", "john123")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    if request.method != "POST":
        abort(405)

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not (name and email and password and confirm_password):
        flash("All fields are required.", "error")
        return render_template("register.html")

    if password != confirm_password:
        flash("Passwords do not match.", "error")
        return render_template("register.html")

    try:
        create_user(name, email, password)
    except sqlite3.IntegrityError:
        flash("Email already registered.", "error")
        return render_template("register.html")

    flash("Account created! Please sign in.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        if session.get("user_id"):
            return redirect(url_for("profile"))
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user_id = authenticate_user(email, password) if email and password else None
    if user_id is None:
        return render_template("login.html", error="Invalid email or password.")

    session.clear()
    session["user_id"] = user_id
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been signed out.", "success")
    return redirect(url_for("login"))


@app.route("/profile")
def profile():
    user_id = session.get("user_id")
    user = get_user_by_id(user_id) if user_id else None
    if user is None:
        session.clear()
        flash("Please sign in to view your profile.", "error")
        return redirect(url_for("login"))

    summary = get_expense_summary(user_id)
    total = summary["total_amount"]
    categories = [
        {
            "name": row["category"],
            "total": row["total"],
            "count": row["count"],
            "pct": round(row["total"] / total * 100, 1) if total else 0,
        }
        for row in get_category_breakdown(user_id)
    ]
    top_total = categories[0]["total"] if categories else 0
    for c in categories:
        # Bar length relative to the largest category so the top one fills the row
        c["bar"] = round(c["total"] / top_total * 100, 1) if top_total else 0

    months = _monthly_series(user_id, count=6)
    this_month = months[-1]["total"]
    last_month = months[-2]["total"]
    avg_month = total / summary["active_months"] if summary["active_months"] else 0

    initials = "".join(part[0] for part in user["name"].split()[:2]).upper()
    try:
        member_since = datetime.strptime(
            user["created_at"], "%Y-%m-%d %H:%M:%S"
        ).strftime("%B %Y")
    except (TypeError, ValueError):
        member_since = None

    return render_template(
        "profile.html",
        user=user,
        initials=initials,
        member_since=member_since,
        summary=summary,
        categories=categories,
        months=months,
        chart_ticks=_chart_ticks(max(m["total"] for m in months)),
        this_month=this_month,
        last_month=last_month,
        avg_month=avg_month,
        largest=get_largest_expenses(user_id, limit=4),
        recent=get_recent_expenses(user_id, limit=8),
    )


def _monthly_series(user_id, count):
    """Last `count` calendar months (oldest first), zero-filled."""
    today = date.today()
    keys = []
    for back in range(count - 1, -1, -1):
        y, m = today.year, today.month - back
        while m < 1:
            y, m = y - 1, m + 12
        keys.append(date(y, m, 1))
    totals = get_monthly_totals(user_id, keys[0].isoformat())
    return [
        {
            "label": d.strftime("%b"),
            "full_label": d.strftime("%B %Y"),
            "total": totals.get(d.strftime("%Y-%m"), 0.0),
            "current": i == count - 1,
        }
        for i, d in enumerate(keys)
    ]


def _chart_ticks(peak, max_steps=5):
    """Evenly spaced 'nice' axis ticks from 0 to just above `peak`."""
    if peak <= 0:
        return [0]
    raw = peak / max_steps
    magnitude = 10 ** (len(str(int(raw))) - 1)
    step = next(n * magnitude for n in (1, 2, 2.5, 5, 10) if n * magnitude >= raw)
    count = -(-peak // step)  # ceil
    return [step * i for i in range(int(count) + 1)]


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
