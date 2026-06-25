import os

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db, get_user_by_email, create_user

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24))

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

    user = {
        "name": "Priya Sharma",
        "email": "priya@example.com",
        "member_since": "January 2024",
        "initials": "PS",
    }
    stats = {
        "total_spent": "32,847.50",
        "transaction_count": 24,
        "top_category": "Food",
    }
    transactions = [
        {"date": "25 Jun 2025", "description": "Swiggy order — dinner",     "category": "Food",          "amount": "648.00"},
        {"date": "23 Jun 2025", "description": "Ola cab to airport",         "category": "Transport",     "amount": "1,240.00"},
        {"date": "20 Jun 2025", "description": "Airtel broadband bill",      "category": "Bills",         "amount": "999.00"},
        {"date": "18 Jun 2025", "description": "Apollo pharmacy",            "category": "Health",        "amount": "380.50"},
        {"date": "15 Jun 2025", "description": "Inox movie tickets",         "category": "Entertainment", "amount": "750.00"},
        {"date": "12 Jun 2025", "description": "Myntra — kurta set",         "category": "Shopping",      "amount": "2,199.00"},
        {"date": "10 Jun 2025", "description": "Big Bazaar groceries",       "category": "Food",          "amount": "3,412.00"},
        {"date": "07 Jun 2025", "description": "Auto fare — daily commute",  "category": "Transport",     "amount": "320.00"},
        {"date": "05 Jun 2025", "description": "Electricity bill — MSEDCL", "category": "Bills",         "amount": "1,842.00"},
        {"date": "02 Jun 2025", "description": "PM Cares donation",          "category": "Other",         "amount": "500.00"},
    ]
    categories = [
        {"name": "Food",          "slug": "food",          "amount": "11,240.00", "bar_class": "bar-w-68"},
        {"name": "Bills",         "slug": "bills",         "amount": "8,320.00",  "bar_class": "bar-w-50"},
        {"name": "Shopping",      "slug": "shopping",      "amount": "5,980.00",  "bar_class": "bar-w-36"},
        {"name": "Transport",     "slug": "transport",     "amount": "4,210.00",  "bar_class": "bar-w-25"},
        {"name": "Entertainment", "slug": "entertainment", "amount": "1,620.00",  "bar_class": "bar-w-10"},
        {"name": "Health",        "slug": "health",        "amount": "920.00",    "bar_class": "bar-w-06"},
        {"name": "Other",         "slug": "other",         "amount": "557.50",    "bar_class": "bar-w-03"},
    ]
    return render_template("profile.html", user=user, stats=stats,
                           transactions=transactions, categories=categories)


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
