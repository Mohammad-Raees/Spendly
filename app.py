import math
import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, get_user_by_email, create_user, CATEGORIES
from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
    insert_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))


def _parse_date(value):
    if not value:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return value
    except ValueError:
        return None


def _format_date_display(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if "@" not in email:
        return render_template("register.html", error="Enter a valid email address.")

    if len(password) < 8:
        return render_template("register.html", error="Password must be at least 8 characters.")

    if get_user_by_email(email) is not None:
        return render_template("register.html", error="An account with that email already exists.")

    password_hash = generate_password_hash(password)
    create_user(name, email, password_hash)

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    if not email or not password:
        return render_template("login.html", error="All fields are required.")

    user = get_user_by_email(email)

    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="Invalid email or password.")

    session["user_id"] = user["id"]

    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]

    date_from = _parse_date(request.args.get("date_from", ""))
    date_to   = _parse_date(request.args.get("date_to",   ""))

    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from

    date_from_display = _format_date_display(date_from)
    date_to_display   = _format_date_display(date_to)

    # ── AGENT 2 SECTION BEGIN (user + stats) ─────────────────────── #
    user = get_user_by_id(user_id)
    stats = get_summary_stats(user_id, date_from=date_from, date_to=date_to)
    # ── AGENT 2 SECTION END ──────────────────────────────────────── #

    # ── AGENT 1 SECTION BEGIN (transactions) ─────────────────────── #
    transactions = get_recent_transactions(user_id, date_from=date_from, date_to=date_to)
    # ── AGENT 1 SECTION END ──────────────────────────────────────── #

    # ── AGENT 3 SECTION BEGIN (categories) ───────────────────────── #
    categories = get_category_breakdown(user_id, date_from=date_from, date_to=date_to)
    # ── AGENT 3 SECTION END ──────────────────────────────────────── #

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_from=date_from,
        date_to=date_to,
        date_from_display=date_from_display,
        date_to_display=date_to_display,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template("add_expense.html",
                               categories=CATEGORIES,
                               today=datetime.today().date().isoformat())

    amount_raw  = request.form.get("amount", "").strip()
    category    = request.form.get("category", "").strip()
    date_raw    = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()[:200] or None

    def _fail(msg):
        return render_template("add_expense.html",
                               categories=CATEGORIES,
                               error=msg,
                               amount=amount_raw,
                               category=category,
                               date=date_raw,
                               description=description or "")

    try:
        amount = float(amount_raw)
        if amount <= 0 or not math.isfinite(amount):
            raise ValueError
    except ValueError:
        return _fail("Amount must be a positive number.")

    if category not in CATEGORIES:
        return _fail("Please select a valid category.")

    try:
        datetime.strptime(date_raw, "%Y-%m-%d")
    except ValueError:
        return _fail("Please enter a valid date (YYYY-MM-DD).")

    insert_expense(session["user_id"], amount, category, date_raw, description)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
