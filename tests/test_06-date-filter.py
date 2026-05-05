"""
tests/test_06-date-filter.py

Pytest test suite for the Spendly date-filter feature (Step 6).

Spec: .claude/specs/06-date-filter.md

The seed user (demo@spendly.com / demo123, id=1) has 8 expenses, all in
April 2026:
    2026-04-01  Food          15.50   Lunch at cafe
    2026-04-03  Transport     45.00   Uber rides
    2026-04-05  Bills        120.00   Electric bill
    2026-04-07  Health        35.00   Pharmacy
    2026-04-10  Entertainment 60.00   Movie tickets and dinner
    2026-04-12  Shopping     200.00   New shoes
    2026-04-14  Other         25.00   Miscellaneous
    2026-04-15  Food          55.00   Grocery shopping
Total = 555.50, 8 transactions.

Important: the db.py helpers use a file-based DATABASE_PATH constant.  We
monkey-patch it to ':memory:' so every test gets an isolated database.
"""

import sqlite3
import pytest
from datetime import date, timedelta
from calendar import monthrange
from unittest.mock import patch

# ---------------------------------------------------------------------------
# We need to redirect the database layer to :memory: before importing app.
# database/db.py exposes DATABASE_PATH at module level, so we patch it.
# ---------------------------------------------------------------------------

import database.db as db_module

# ------------------------------------------------------------------ helpers --

_SEED_EXPENSES = [
    (15.50,  "Food",          "2026-04-01", "Lunch at cafe"),
    (45.00,  "Transport",     "2026-04-03", "Uber rides"),
    (120.00, "Bills",         "2026-04-05", "Electric bill"),
    (35.00,  "Health",        "2026-04-07", "Pharmacy"),
    (60.00,  "Entertainment", "2026-04-10", "Movie tickets and dinner"),
    (200.00, "Shopping",      "2026-04-12", "New shoes"),
    (25.00,  "Other",         "2026-04-14", "Miscellaneous"),
    (55.00,  "Food",          "2026-04-15", "Grocery shopping"),
]

SEED_TOTAL = 555.50
SEED_COUNT = 8


def _make_in_memory_db():
    """Return a fresh :memory: connection with the Spendly schema + seed data."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            currency TEXT DEFAULT 'CAD'
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    return conn


# ---------------------------------------------------------------- fixtures ---

@pytest.fixture
def _conn():
    """Shared in-memory connection; kept open for the lifetime of a test."""
    conn = _make_in_memory_db()
    yield conn
    conn.close()


@pytest.fixture
def _app(_conn):
    """
    Flask app configured for testing with an isolated in-memory SQLite DB.

    We patch db_module.get_db so every call inside app.py and queries.py
    returns a *new* connection to the same :memory: database via the URI
    trick, but that is not available on all platforms.  Instead we use a
    simpler approach: patch get_db to clone connections sharing the same
    file opened as ':memory:' — actually the cleanest way is to make all
    callers share the single _conn fixture connection.
    """
    from werkzeug.security import generate_password_hash
    from app import app as flask_app

    flask_app.config.update({
        'TESTING': True,
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
    })

    # Seed the in-memory DB through _conn
    pw_hash = generate_password_hash("demo123")
    _conn.execute(
        "INSERT INTO users (name, email, password_hash, currency) VALUES (?, ?, ?, ?)",
        ("Demo User", "demo@spendly.com", pw_hash, "INR"),
    )
    _conn.commit()

    user_id = _conn.execute(
        "SELECT id FROM users WHERE email = ?", ("demo@spendly.com",)
    ).fetchone()[0]

    _conn.executemany(
        "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
        [(user_id, amt, cat, dt, desc) for amt, cat, dt, desc in _SEED_EXPENSES],
    )
    _conn.commit()

    # Patch get_db to return our in-memory connection each time.
    # SQLite :memory: connections cannot be shared across threads, but Flask's
    # test client runs synchronously, so this is safe.
    def _fake_get_db():
        # Return the single shared connection (do NOT close it between calls).
        return _conn

    with patch.object(db_module, "get_db", side_effect=_fake_get_db):
        with flask_app.app_context():
            yield flask_app, user_id


@pytest.fixture
def client(_app):
    flask_app, user_id = _app
    return flask_app.test_client(), user_id


@pytest.fixture
def auth_client(client):
    """Test client pre-authenticated as the seed user via session injection."""
    test_client, user_id = client
    with test_client.session_transaction() as sess:
        sess["user_id"] = user_id
    return test_client, user_id


# ===========================================================================
# 1. Authentication guard
# ===========================================================================

class TestAuthGuard:
    def test_unauthenticated_get_profile_redirects_to_login(self, client):
        test_client, _ = client
        response = test_client.get("/profile")
        assert response.status_code == 302, "Expected redirect for unauthenticated request"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated /profile should redirect to /login"
        )

    def test_unauthenticated_get_profile_with_params_redirects_to_login(self, client):
        test_client, _ = client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-15")
        assert response.status_code == 302, "Expected redirect for unauthenticated request with params"
        assert "/login" in response.headers["Location"], (
            "Unauthenticated /profile with date params should redirect to /login"
        )


# ===========================================================================
# 2. Baseline — no query params (All Time / unfiltered)
# ===========================================================================

class TestBaselineNoParams:
    def test_profile_no_params_returns_200(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        assert response.status_code == 200, "GET /profile with no params should return 200"

    def test_profile_no_params_renders_profile_template(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        data = response.data
        assert b"Demo User" in data, "Profile page should display the user's name"

    def test_profile_no_params_shows_all_seed_expenses_total(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        # Total = 555.50; currency symbol is ₹ (seed user has INR)
        assert b"555.50" in response.data, (
            "Unfiltered profile should show total of all seed expenses: 555.50"
        )

    def test_profile_no_params_shows_correct_transaction_count(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        # 8 transactions in seed data
        assert b"8" in response.data, (
            "Unfiltered profile should show 8 transactions"
        )

    def test_profile_no_params_shows_all_time_active_preset(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        html = response.data.decode("utf-8")
        # The "All Time" button must carry the 'active' CSS class
        assert "All Time" in html, "All Time preset button must appear on the page"
        # Find the portion of HTML for 'All Time' and verify 'active' is nearby
        all_time_idx = html.find("All Time")
        surrounding = html[max(0, all_time_idx - 100): all_time_idx + 20]
        assert "active" in surrounding, (
            "The 'All Time' preset button should have the 'active' class when no date params are set"
        )

    def test_profile_no_params_shows_filter_bar(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        html = response.data.decode("utf-8")
        assert "This Month" in html, "Filter bar must contain 'This Month' preset"
        assert "Last 3 Months" in html, "Filter bar must contain 'Last 3 Months' preset"
        assert "Last 6 Months" in html, "Filter bar must contain 'Last 6 Months' preset"
        assert "All Time" in html, "Filter bar must contain 'All Time' preset"

    def test_profile_no_params_contains_apply_button(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        assert b"Apply" in response.data, "Filter bar must contain an Apply button for the custom date range"

    def test_profile_no_params_contains_date_inputs(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        html = response.data.decode("utf-8")
        assert 'name="date_from"' in html, "Filter bar must have a date_from input"
        assert 'name="date_to"' in html, "Filter bar must have a date_to input"

    def test_profile_no_params_shows_currency_symbol(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        # Seed user has INR — symbol is ₹
        assert "₹" in response.data.decode("utf-8"), (
            "Profile page should display the ₹ currency symbol for INR users"
        )

    def test_profile_no_params_shows_top_category_shopping(self, auth_client):
        """Shopping has the highest total (200.00) in the seed data."""
        test_client, _ = auth_client
        response = test_client.get("/profile")
        assert b"Shopping" in response.data, (
            "Unfiltered top category should be Shopping (highest at 200.00)"
        )


# ===========================================================================
# 3. Custom valid date range
# ===========================================================================

class TestCustomDateRange:
    def test_full_april_range_returns_all_expenses(self, auth_client):
        """date_from=2026-04-01 to date_to=2026-04-15 spans all 8 seed expenses."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-15")
        assert response.status_code == 200
        assert b"555.50" in response.data, (
            "Full April range should return the same total as unfiltered: 555.50"
        )

    def test_partial_range_filters_total_correctly(self, auth_client):
        """
        date_from=2026-04-01, date_to=2026-04-05 captures 3 expenses:
            15.50 + 45.00 + 120.00 = 180.50
        """
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        assert response.status_code == 200
        assert b"180.50" in response.data, (
            "Partial April 1–5 range should show total 180.50"
        )

    def test_partial_range_hides_out_of_range_transactions(self, auth_client):
        """Expenses after 2026-04-05 (Shopping, Entertainment, etc.) must not appear."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        # Shopping (2026-04-12, 200.00) must not appear in the filtered view
        assert "200.00" not in html, (
            "Shopping expense (200.00, after 2026-04-05) must not appear in filtered range"
        )

    def test_partial_range_shows_only_in_range_categories(self, auth_client):
        """
        April 1–5 has Food, Transport, Bills.
        Shopping (April 12) must not appear in category breakdown.
        """
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Food" in html, "Food category should appear in the Apr 1–5 range"
        assert "Transport" in html, "Transport category should appear in the Apr 1–5 range"
        assert "Bills" in html, "Bills category should appear in the Apr 1–5 range"

    def test_single_day_range_returns_one_expense(self, auth_client):
        """date_from=date_to=2026-04-01 → only the 15.50 Food expense."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-01")
        assert response.status_code == 200
        assert b"15.50" in response.data, "Single-day range 2026-04-01 should show 15.50"
        # Should not contain amounts from other days
        assert b"45.00" not in response.data, (
            "Single-day range should not show the Apr 3 Transport expense"
        )

    def test_range_returns_200_status(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-07&date_to=2026-04-12")
        assert response.status_code == 200

    def test_filtered_view_still_shows_currency_symbol(self, auth_client):
        """Currency symbol must appear regardless of the active filter."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        assert "₹" in response.data.decode("utf-8"), (
            "₹ symbol must appear even when a date filter is active"
        )

    def test_custom_range_active_preset_is_none(self, auth_client):
        """
        A custom range that does not match any preset must not mark any preset
        button as active.  The word 'active' may appear in other contexts, so
        we check that no preset anchor carries 'active' in its class.
        The HTML pattern in the template is:
            class="filter-btn{% if active_preset == '...' %} active{% endif %}"
        When active_preset is None none of those branches fire.
        """
        test_client, _ = auth_client
        # This range does not match any of the four presets
        response = test_client.get("/profile?date_from=2026-04-02&date_to=2026-04-09")
        html = response.data.decode("utf-8")
        # None of the preset buttons should have the active class
        for preset_label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            idx = html.find(preset_label)
            assert idx != -1, f"Preset button '{preset_label}' must always be rendered"
            surrounding = html[max(0, idx - 120): idx + len(preset_label)]
            assert "filter-btn active" not in surrounding, (
                f"Preset '{preset_label}' must NOT be active for a custom non-matching range"
            )


# ===========================================================================
# 4. Inverted date range (date_from > date_to)
# ===========================================================================

class TestInvertedDateRange:
    def test_inverted_range_returns_200(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-15&date_to=2026-04-01")
        assert response.status_code == 200, "Inverted date range must not cause a server error"

    def test_inverted_range_flashes_error_message(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get(
            "/profile?date_from=2026-04-15&date_to=2026-04-01",
            follow_redirects=True,
        )
        assert b"Start date must be before end date." in response.data, (
            "Inverted date range must flash 'Start date must be before end date.'"
        )

    def test_inverted_range_falls_back_to_unfiltered_total(self, auth_client):
        """After flashing the error the view must return all expenses (555.50)."""
        test_client, _ = auth_client
        response = test_client.get(
            "/profile?date_from=2026-04-15&date_to=2026-04-01",
            follow_redirects=True,
        )
        assert b"555.50" in response.data, (
            "Inverted-range fallback should show unfiltered total 555.50"
        )

    def test_inverted_range_shows_all_time_active(self, auth_client):
        """After the invalid range is rejected, All Time should be active."""
        test_client, _ = auth_client
        response = test_client.get(
            "/profile?date_from=2026-04-15&date_to=2026-04-01",
            follow_redirects=True,
        )
        html = response.data.decode("utf-8")
        all_time_idx = html.find("All Time")
        assert all_time_idx != -1
        surrounding = html[max(0, all_time_idx - 100): all_time_idx + 20]
        assert "active" in surrounding, (
            "After an inverted-range rejection, 'All Time' preset should be active"
        )


# ===========================================================================
# 5. Malformed date strings
# ===========================================================================

@pytest.mark.parametrize("bad_date_from,bad_date_to", [
    ("not-a-date", "2026-04-15"),
    ("2026-04-01", "not-a-date"),
    ("not-a-date", "not-a-date"),
    ("",           "2026-04-15"),
    ("2026-04-01", ""),
    ("13/01/2026", "2026-04-15"),   # wrong separator format
    ("2026-99-99", "2026-04-15"),   # out-of-range values
    ("abcdefgh",   "zzzzzzzz"),
    ("' OR 1=1--", "2026-04-15"),   # SQL-injection attempt
    ("2026-04-01", "' OR 1=1--"),
])
def test_malformed_dates_do_not_crash(auth_client, bad_date_from, bad_date_to):
    """Malformed dates must be silently ignored; app returns 200 with unfiltered data."""
    test_client, _ = auth_client
    response = test_client.get(
        f"/profile?date_from={bad_date_from}&date_to={bad_date_to}"
    )
    assert response.status_code == 200, (
        f"Malformed dates ({bad_date_from!r}, {bad_date_to!r}) must not crash the app"
    )


@pytest.mark.parametrize("bad_date_from,bad_date_to", [
    ("not-a-date", "not-a-date"),
    ("13/01/2026", "31/12/2026"),
    ("abcdefgh",   "zzzzzzzz"),
])
def test_malformed_dates_fall_back_to_unfiltered(auth_client, bad_date_from, bad_date_to):
    """Fully malformed params should produce the unfiltered 555.50 total."""
    test_client, _ = auth_client
    response = test_client.get(
        f"/profile?date_from={bad_date_from}&date_to={bad_date_to}"
    )
    assert b"555.50" in response.data, (
        f"Fully malformed dates ({bad_date_from!r}, {bad_date_to!r}) should fall back to unfiltered view"
    )


# ===========================================================================
# 6. No expenses in selected range
# ===========================================================================

class TestEmptyRange:
    def test_future_range_returns_200(self, auth_client):
        """A date range in the future (no seed data) must not crash."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
        assert response.status_code == 200

    def test_future_range_shows_zero_total(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
        assert b"0.00" in response.data, (
            "A range with no expenses must show 0.00 total"
        )

    def test_future_range_shows_zero_transactions(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
        html = response.data.decode("utf-8")
        # The transactions table body should contain no rows with amounts
        assert "200.00" not in html, "No seed-data transactions should appear in a future range"

    def test_past_range_before_seed_data_returns_200(self, auth_client):
        """A valid range that is before all seed expenses must not error."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert response.status_code == 200

    def test_past_range_before_seed_data_shows_zero_total(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2020-01-01&date_to=2020-12-31")
        assert b"0.00" in response.data, (
            "A range before seed data should show 0.00 total"
        )


# ===========================================================================
# 7. Preset active states
# ===========================================================================

class TestPresetActiveStates:
    def _preset_dates(self, preset_name: str):
        """
        Compute the date_from / date_to strings for a named preset exactly as
        app.py does, so we can hit /profile with the matching params and expect
        the preset to be flagged as active.
        """
        today = date.today()

        def first_of_month_n_months_ago(n):
            month = today.month - n
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            return date(year, month, 1)

        if preset_name == "this_month":
            return today.replace(day=1).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        elif preset_name == "last_3_months":
            return first_of_month_n_months_ago(3).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        elif preset_name == "last_6_months":
            return first_of_month_n_months_ago(6).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
        raise ValueError(f"Unknown preset: {preset_name}")

    def test_this_month_preset_active(self, auth_client):
        test_client, _ = auth_client
        d_from, d_to = self._preset_dates("this_month")
        response = test_client.get(f"/profile?date_from={d_from}&date_to={d_to}")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        # "This Month" button must carry the 'active' class
        idx = html.find("This Month")
        assert idx != -1, "'This Month' button must be present"
        surrounding = html[max(0, idx - 120): idx + len("This Month")]
        assert "active" in surrounding, (
            "The 'This Month' preset button must have the 'active' class when its dates are active"
        )

    def test_last_3_months_preset_active(self, auth_client):
        test_client, _ = auth_client
        d_from, d_to = self._preset_dates("last_3_months")
        response = test_client.get(f"/profile?date_from={d_from}&date_to={d_to}")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        idx = html.find("Last 3 Months")
        assert idx != -1, "'Last 3 Months' button must be present"
        surrounding = html[max(0, idx - 120): idx + len("Last 3 Months")]
        assert "active" in surrounding, (
            "The 'Last 3 Months' preset button must have the 'active' class when its dates are active"
        )

    def test_last_6_months_preset_active(self, auth_client):
        test_client, _ = auth_client
        d_from, d_to = self._preset_dates("last_6_months")
        response = test_client.get(f"/profile?date_from={d_from}&date_to={d_to}")
        assert response.status_code == 200
        html = response.data.decode("utf-8")
        idx = html.find("Last 6 Months")
        assert idx != -1, "'Last 6 Months' button must be present"
        surrounding = html[max(0, idx - 120): idx + len("Last 6 Months")]
        assert "active" in surrounding, (
            "The 'Last 6 Months' preset button must have the 'active' class when its dates are active"
        )

    def test_all_time_active_when_no_params(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        html = response.data.decode("utf-8")
        idx = html.find("All Time")
        assert idx != -1, "'All Time' button must be present"
        surrounding = html[max(0, idx - 120): idx + len("All Time")]
        assert "active" in surrounding, (
            "The 'All Time' preset button must have the 'active' class when no date params are set"
        )

    def test_this_month_preset_not_active_when_other_range(self, auth_client):
        """When a different preset is active, 'This Month' must not be active."""
        test_client, _ = auth_client
        d_from, d_to = self._preset_dates("last_3_months")
        response = test_client.get(f"/profile?date_from={d_from}&date_to={d_to}")
        html = response.data.decode("utf-8")
        # Locate the "This Month" anchor and verify it lacks 'active'
        idx = html.find("This Month")
        assert idx != -1
        surrounding = html[max(0, idx - 120): idx + len("This Month")]
        assert "filter-btn active" not in surrounding, (
            "'This Month' must NOT be active when a different preset is selected"
        )


# ===========================================================================
# 8. Transaction list content (filtered)
# ===========================================================================

class TestTransactionListFiltered:
    def test_april_1_to_5_shows_expected_descriptions(self, auth_client):
        """
        Expenses in range Apr 1–5:
            Lunch at cafe, Uber rides, Electric bill
        """
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Lunch at cafe" in html, "Apr 1 expense should appear"
        assert "Uber rides" in html, "Apr 3 expense should appear"
        assert "Electric bill" in html, "Apr 5 expense should appear"

    def test_april_1_to_5_hides_later_descriptions(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Pharmacy" not in html, "Apr 7 expense must be excluded"
        assert "New shoes" not in html, "Apr 12 expense must be excluded"
        assert "Grocery shopping" not in html, "Apr 15 expense must be excluded"

    def test_april_10_to_15_shows_correct_expenses(self, auth_client):
        """
        Expenses in range Apr 10–15:
            Movie tickets and dinner (60.00)
            New shoes (200.00)
            Miscellaneous (25.00)
            Grocery shopping (55.00)
        Total = 340.00
        """
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-10&date_to=2026-04-15")
        assert b"340.00" in response.data, (
            "Apr 10–15 range should show total 340.00"
        )

    def test_transactions_ordered_by_date_desc(self, auth_client):
        """Most recent date should appear first in the transaction list."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-15")
        html = response.data.decode("utf-8")
        # Scope the search to the transactions table to avoid false matches in
        # the filter bar form inputs (which also contain these date strings).
        table_start = html.find("transactions-table")
        assert table_start != -1, "transactions-table must be present"
        table_html = html[table_start:]
        idx_apr15 = table_html.find("2026-04-15")
        idx_apr01 = table_html.find("2026-04-01")
        assert idx_apr15 != -1 and idx_apr01 != -1
        assert idx_apr15 < idx_apr01, (
            "More recent date (2026-04-15) should appear before earlier date (2026-04-01)"
        )


# ===========================================================================
# 9. Category breakdown filtered
# ===========================================================================

class TestCategoryBreakdownFiltered:
    def test_apr_1_to_5_breakdown_excludes_later_categories(self, auth_client):
        """Shopping (Apr 12) and Entertainment (Apr 10) must not be in breakdown."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        # We look for the category names in the breakdown section.
        # Both "Shopping" and "Entertainment" appear only after Apr 5.
        assert "Shopping" not in html, "Shopping must not appear in Apr 1–5 breakdown"
        assert "Entertainment" not in html, "Entertainment must not appear in Apr 1–5 breakdown"

    def test_apr_1_to_5_breakdown_includes_correct_categories(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        assert "Food" in html, "Food must appear in Apr 1–5 breakdown"
        assert "Transport" in html, "Transport must appear in Apr 1–5 breakdown"
        assert "Bills" in html, "Bills must appear in Apr 1–5 breakdown"

    def test_empty_range_produces_empty_breakdown(self, auth_client):
        """No expenses in range → category breakdown must be empty (no rows)."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
        html = response.data.decode("utf-8")
        # None of the seed categories should appear in the breakdown
        for cat in ("Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"):
            assert cat not in html, (
                f"Category '{cat}' must not appear in breakdown for a future empty range"
            )


# ===========================================================================
# 10. Summary stats zero-state
# ===========================================================================

class TestSummaryStatsZeroState:
    def test_empty_range_top_category_dash(self, auth_client):
        """When no expenses match, top_category should be '—'."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2030-01-01&date_to=2030-12-31")
        html = response.data.decode("utf-8")
        assert "—" in html, "Top category must show '—' when no expenses are in range"

    def test_partial_range_transaction_count(self, auth_client):
        """April 1–5 has 3 transactions."""
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-05")
        html = response.data.decode("utf-8")
        # The stat-card for Transactions should show 3
        assert ">3<" in html or "3" in html, (
            "Apr 1–5 should show 3 transactions"
        )


# ===========================================================================
# 11. HTTP semantics
# ===========================================================================

class TestHttpSemantics:
    def test_profile_get_with_valid_params_is_200(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=2026-04-01&date_to=2026-04-15")
        assert response.status_code == 200

    def test_profile_no_params_is_200(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile")
        assert response.status_code == 200

    def test_profile_malformed_dates_is_200(self, auth_client):
        test_client, _ = auth_client
        response = test_client.get("/profile?date_from=garbage&date_to=garbage")
        assert response.status_code == 200

    def test_unauthenticated_is_302(self, client):
        test_client, _ = client
        response = test_client.get("/profile")
        assert response.status_code == 302
