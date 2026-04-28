import sqlite3

from flask import Flask, render_template, request, flash, redirect, url_for, session
from werkzeug.exceptions import abort

from database.db import get_db, init_db, seed_db, create_user, get_user_by_email
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = "spendly-dev-secret-key-change-in-production"


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
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation: check for empty fields
        if not name or not email or not password or not confirm_password:
            flash("All fields are required", "error")
            return render_template("register.html", name=name, email=email)

        # Validation: passwords must match
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html", name=name, email=email)

        # Try to create user
        try:
            create_user(name, email, password)
            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered", "error")
            return render_template("register.html", name=name, email=email)

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("landing"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Validation: check for empty fields
        if not email or not password:
            flash("All fields are required", "error")
            return render_template("login.html")

        # Fetch user and verify password
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Welcome back!", "success")
            return redirect(url_for("landing"))
        else:
            flash("Invalid email or password.", "error")
            return render_template("login.html")

    return render_template("login.html")


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
    flash("You have been logged out", "info")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    # Authentication check
    if not session.get("user_id"):
        return redirect(url_for("login"))

    # Hardcoded user data (will be replaced with DB query in Step 05)
    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "April 2026"
    }

    # Hardcoded summary stats
    summary = {
        "total_spent": 555.50,
        "transaction_count": 8,
        "top_category": "Shopping"
    }

    # Hardcoded recent transactions
    transactions = [
        {"date": "2026-04-15", "description": "Grocery shopping", "category": "Food", "amount": 55.00},
        {"date": "2026-04-14", "description": "Miscellaneous", "category": "Other", "amount": 25.00},
        {"date": "2026-04-12", "description": "New shoes", "category": "Shopping", "amount": 200.00},
        {"date": "2026-04-10", "description": "Movie tickets and dinner", "category": "Entertainment", "amount": 60.00},
        {"date": "2026-04-07", "description": "Pharmacy", "category": "Health", "amount": 35.00},
    ]

    # Hardcoded category breakdown
    categories = [
        {"name": "Food", "total": 70.50, "count": 2},
        {"name": "Shopping", "total": 200.00, "count": 1},
        {"name": "Transport", "total": 45.00, "count": 1},
        {"name": "Bills", "total": 120.00, "count": 1},
        {"name": "Entertainment", "total": 60.00, "count": 1},
    ]

    return render_template("profile.html", user=user, summary=summary, transactions=transactions, categories=categories)


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
    init_db()
    seed_db()
    app.run(debug=True, port=5001)
