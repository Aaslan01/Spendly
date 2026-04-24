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
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validation: check for empty fields
        if not name or not email or not password or not confirm_password:
            flash("All fields are required")
            return render_template("register.html", name=name, email=email)

        # Validation: passwords must match
        if password != confirm_password:
            flash("Passwords do not match")
            return render_template("register.html", name=name, email=email)

        # Try to create user
        try:
            create_user(name, email, password)
            flash("Account created successfully! Please log in.")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already registered")
            return render_template("register.html", name=name, email=email)

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        # Validation: check for empty fields
        if not email or not password:
            flash("All fields are required")
            return render_template("login.html")

        # Fetch user and verify password
        user = get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Welcome back!")
            return redirect(url_for("landing"))
        else:
            flash("Invalid email or password.")
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
    flash("You have been logged out")
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    return "Profile page — coming in Step 4"


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
