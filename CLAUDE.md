# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python app.py
# Runs on http://localhost:5001

# Run tests
pytest
```

## Architecture

**Spendly** is a Flask-based expense tracking web application.

### Structure

- `app.py` — Flask application entry point. Defines all routes and view functions.
- `database/db.py` — Database layer with `get_db()`, `init_db()`, and `seed_db()` functions. Uses SQLite with row factory and foreign keys enabled.
- `templates/` — Jinja2 HTML templates. `base.html` provides the shared layout with navigation and footer.
- `static/` — Static assets (CSS, JavaScript).

### Key Patterns

- Templates extend `base.html` which provides navbar, footer, and block structure.
- Database connections are managed through `database/db.py` utilities.
- Session-based authentication (to be implemented in Step 3).
- Development database: `expense_tracker.db` (gitignored).

### Current State

The app has landing, login, register, terms, and privacy pages implemented. Routes for logout, profile, and expense CRUD operations are stubbed with placeholder responses.
