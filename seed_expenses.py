#!/usr/bin/env python3
"""Seed realistic dummy expenses for a user."""

import sys
import random
from datetime import datetime, timedelta
from database.db import get_db

# Parse arguments
if len(sys.argv) != 4:
    print("Usage: /seed-expenses <user_id> <count> <months>")
    print("Example: /seed-expenses 1 50 6")
    sys.exit(1)

try:
    USER_ID = int(sys.argv[1])
    COUNT = int(sys.argv[2])
    MONTHS = int(sys.argv[3])
except ValueError:
    print("Usage: /seed-expenses <user_id> <count> <months>")
    print("Example: /seed-expenses 1 50 6")
    sys.exit(1)

# Category definitions with Indian context
CATEGORIES = {
    "Food": {"min": 50, "max": 800, "weight": 25, "descriptions": [
        "Lunch at local restaurant", "Grocery shopping", "Street food",
        "Dinner with family", "Morning chai and snacks", "Biryani order",
        "Tiffin service", "Weekend buffet", "Coffee at Cafe Coffee Day",
        "South Indian thali", "Pizza delivery", "Ice cream"
    ]},
    "Transport": {"min": 20, "max": 500, "weight": 15, "descriptions": [
        "Auto rickshaw fare", "Metro card recharge", "Uber ride to office",
        "Bus pass monthly", "Fuel at petrol pump", "Ola cab",
        "Parking fee", "Train ticket", "Bike service"
    ]},
    "Bills": {"min": 200, "max": 3000, "weight": 12, "descriptions": [
        "Electricity bill BESCOM", "Mobile recharge Airtel", "Internet bill ACT",
        "Rent payment", "Water bill", "Gas cylinder booking",
        "Maintenance charges", "DTH recharge"
    ]},
    "Health": {"min": 100, "max": 2000, "weight": 8, "descriptions": [
        "Pharmacy medicines", "Doctor consultation", "Health checkup",
        "Gym membership", "Yoga class", "Vitamin supplements",
        "Dental clinic visit"
    ]},
    "Entertainment": {"min": 100, "max": 1500, "weight": 10, "descriptions": [
        "Movie tickets PVR", "Netflix subscription", "Concert entry",
        "Bowling with friends", "Amusement park", "Play tickets",
        "Gaming subscription"
    ]},
    "Shopping": {"min": 200, "max": 5000, "weight": 15, "descriptions": [
        "New clothes at Reliance Trends", "Electronics from Amazon",
        "Footwear Big Bazaar", "Home decor IKEA", "Birthday gift",
        "Festival shopping", "Watch purchase"
    ]},
    "Other": {"min": 50, "max": 1000, "weight": 10, "descriptions": [
        "Stationery items", "Donation to temple", "Magazine subscription",
        "Car wash", "Laundry service", "Pet supplies", "Miscellaneous"
    ]},
}

def generate_expense(user_id, start_date, end_date):
    """Generate a random expense within the date range."""
    # Pick category based on weights
    categories = list(CATEGORIES.keys())
    weights = [CATEGORIES[c]["weight"] for c in categories]
    category = random.choices(categories, weights=weights, k=1)[0]

    cat_data = CATEGORIES[category]
    amount = round(random.uniform(cat_data["min"], cat_data["max"]), 2)
    description = random.choice(cat_data["descriptions"])

    # Random date within range
    days_range = (end_date - start_date).days
    random_days = random.randint(0, days_range)
    expense_date = start_date + timedelta(days=random_days)

    return (user_id, amount, category, expense_date.strftime("%Y-%m-%d"), description)

def main():
    # Verify user exists
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, name FROM users WHERE id = ?", (USER_ID,))
    user = cur.fetchone()
    if not user:
        print(f"No user found with id {USER_ID}.")
        conn.close()
        sys.exit(1)

    print(f"Seeding {COUNT} expenses for {user['name']} (ID: {USER_ID}) over {MONTHS} months...")

    # Calculate date range
    today = datetime.now().date()
    start_date = today - timedelta(days=MONTHS * 30)

    # Generate all expenses
    expenses = [generate_expense(USER_ID, start_date, today) for _ in range(COUNT)]

    # Insert in single transaction
    try:
        cur.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
            expenses
        )
        conn.commit()
        print(f"\nSuccessfully inserted {cur.rowcount} expenses.")
    except Exception as e:
        conn.rollback()
        print(f"Error inserting expenses: {e}")
        conn.close()
        sys.exit(1)

    # Get date range of inserted expenses
    cur.execute("""
        SELECT MIN(date), MAX(date) FROM expenses
        WHERE user_id = ? AND date >= ?
    """, (USER_ID, start_date.strftime("%Y-%m-%d")))
    min_date, max_date = cur.fetchone()

    print(f"Date range: {min_date} to {max_date}")

    # Show sample of 5 records
    cur.execute("""
        SELECT id, amount, category, date, description FROM expenses
        WHERE user_id = ?
        ORDER BY RANDOM() LIMIT 5
    """, (USER_ID,))

    print("\nSample expenses:")
    print("-" * 80)
    for row in cur.fetchall():
        print(f"ID {row['id']}: ₹{row['amount']:.2f} | {row['category']:12} | {row['date']} | {row['description']}")

    conn.close()

if __name__ == "__main__":
    main()
