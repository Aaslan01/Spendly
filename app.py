import sqlite3
import requests

from flask import Flask, render_template, request, flash, redirect, url_for, session
from werkzeug.exceptions import abort

from database.db import get_db, init_db, seed_db, create_user, get_user_by_email, get_user_by_id, update_user_currency
from database.queries import get_summary_stats, get_recent_transactions, get_category_breakdown
from datetime import datetime, date as date_type
from werkzeug.security import check_password_hash


# Currency symbol mapping
CURRENCY_SYMBOLS = {
    'USD': '$',
    'CAD': '$',
    'EUR': '€',
    'GBP': '£',
    'AUD': '$',
    'INR': '₹',
    'JPY': '¥'
}


def get_currency_symbol(currency_code):
    """Returns the symbol for a given currency code."""
    return CURRENCY_SYMBOLS.get(currency_code, currency_code)


def detect_currency_from_ip():
    """
    Detects the user's currency based on their IP address using ipapi.co.
    Returns a tuple of (currency_code, currency_name) or (None, None) on failure.
    """
    try:
        # Get client IP
        ip = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ip == '127.0.0.1' or ip == '::1':
            # Localhost - default to CAD
            return 'CAD', 'Canadian Dollar'

        # Query ipapi.co for location data
        response = requests.get(f'https://ipapi.co/{ip}/json/', timeout=5)
        if response.status_code == 200:
            data = response.json()
            country = data.get('country_code')

            # Map country codes to currencies
            country_to_currency = {
                'US': ('USD', 'US Dollar'),
                'CA': ('CAD', 'Canadian Dollar'),
                'GB': ('GBP', 'British Pound'),
                'DE': ('EUR', 'Euro'),
                'FR': ('EUR', 'Euro'),
                'IT': ('EUR', 'Euro'),
                'ES': ('EUR', 'Euro'),
                'AU': ('AUD', 'Australian Dollar'),
                'IN': ('INR', 'Indian Rupee'),
                'JP': ('JPY', 'Japanese Yen'),
                'CN': ('CNY', 'Chinese Yuan'),
                'MX': ('MXN', 'Mexican Peso'),
                'BR': ('BRL', 'Brazilian Real'),
            }

            if country in country_to_currency:
                return country_to_currency[country]

            # Default to USD if country not found
            return 'USD', 'US Dollar'
    except Exception:
        pass

    return None, None

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

        # Try to create user (detect currency from IP for initial preference)
        try:
            detected_currency, _ = detect_currency_from_ip()
            create_user(name, email, password, currency=detected_currency or 'CAD')
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

    # Fetch real user data from database
    user = get_user_by_id(session["user_id"])
    if not user:
        session.clear()
        flash("User not found. Please log in again.", "error")
        return redirect(url_for("login"))

    # Format member since date
    member_since = datetime.strptime(user["created_at"][:10], "%Y-%m-%d").strftime("%B %Y") if user["created_at"] else "Unknown"
    user_data = {
        "name": user["name"],
        "email": user["email"],
        "member_since": member_since,
        "currency": user["currency"] or "CAD"
    }

    # Get currency symbol
    currency_symbol = get_currency_symbol(user_data["currency"])

    # Parse and validate date filter params
    def _parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date() if s else None
        except ValueError:
            return None

    d_from = _parse_date(request.args.get("date_from", "").strip())
    d_to   = _parse_date(request.args.get("date_to",   "").strip())

    if d_from and d_to and d_from > d_to:
        flash("Start date must be before end date.", "error")
        d_from = d_to = None

    date_from = d_from.strftime("%Y-%m-%d") if d_from else None
    date_to   = d_to.strftime("%Y-%m-%d")   if d_to   else None

    # Compute preset date ranges
    today = date_type.today()

    def _first_of_month_n_months_ago(n):
        month = today.month - n
        year  = today.year
        while month <= 0:
            month += 12
            year  -= 1
        return date_type(year, month, 1)

    presets = {
        "this_month":    (today.replace(day=1).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
        "last_3_months": (_first_of_month_n_months_ago(3).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
        "last_6_months": (_first_of_month_n_months_ago(6).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")),
    }

    # Determine which preset is active
    if date_from is None and date_to is None:
        active_preset = "all_time"
    elif (date_from, date_to) == presets["this_month"]:
        active_preset = "this_month"
    elif (date_from, date_to) == presets["last_3_months"]:
        active_preset = "last_3_months"
    elif (date_from, date_to) == presets["last_6_months"]:
        active_preset = "last_6_months"
    else:
        active_preset = None

    summary      = get_summary_stats(session["user_id"], date_from=date_from, date_to=date_to)
    transactions = get_recent_transactions(session["user_id"], date_from=date_from, date_to=date_to)
    categories   = get_category_breakdown(session["user_id"], date_from=date_from, date_to=date_to)

    return render_template(
        "profile.html",
        user=user_data,
        summary=summary,
        transactions=transactions,
        categories=categories,
        currency_symbol=currency_symbol,
        date_from=date_from,
        date_to=date_to,
        active_preset=active_preset,
        presets=presets,
    )


@app.route("/profile/settings", methods=["POST"])
def update_currency():
    """Updates the user's currency preference."""
    if not session.get("user_id"):
        flash("Please log in to update settings", "error")
        return redirect(url_for("login"))

    currency = request.form.get("currency", "CAD").upper()

    # Validate currency
    valid_currencies = ['USD', 'CAD', 'EUR', 'GBP', 'AUD', 'INR', 'JPY']
    if currency not in valid_currencies:
        flash("Invalid currency selected", "error")
        return redirect(url_for("profile"))

    # Update user currency
    update_user_currency(session["user_id"], currency)
    flash(f"Currency updated to {currency}", "success")
    return redirect(url_for("profile"))


@app.route("/profile/detect-currency")
def detect_currency():
    """Detects and returns the user's currency based on their IP location."""
    if not session.get("user_id"):
        return {"success": False, "error": "Not authenticated"}, 401

    currency_code, currency_name = detect_currency_from_ip()

    if currency_code:
        return {"success": True, "currency": currency_code, "currencyName": currency_name}
    else:
        return {"success": False, "error": "Could not detect location"}, 500


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
