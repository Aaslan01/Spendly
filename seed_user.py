#!/usr/bin/env python3
"""Seed a realistic random Indian user into the database."""

import sqlite3
import random
from datetime import datetime
from werkzeug.security import generate_password_hash

DATABASE_PATH = "expense_tracker.db"


def get_db():
    """Opens a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Common Indian first names across regions
FIRST_NAMES = [
    # North Indian
    "Rahul", "Amit", "Rajesh", "Vikram", "Arjun", "Rohan", "Karan", "Aditya",
    "Priya", "Neha", "Anjali", "Pooja", "Sneha", "Divya", "Meera", "Kavya",
    # South Indian
    "Aravind", "Karthik", "Venkat", "Mohan", "Krishnan", "Ravi", "Suresh",
    "Lakshmi", "Padmavati", "Saraswati", "Gayatri", "Kamala", "Bharathi",
    # Pan-Indian
    "Sanjay", "Manoj", "Deepak", "Anil", "Sunita", "Rekha", "Usha", "Ashok",
]

# Common Indian surnames across regions
LAST_NAMES = [
    # North Indian
    "Sharma", "Verma", "Gupta", "Agarwal", "Singh", "Kumar", "Yadav", "Malhotra",
    "Kapoor", "Chopra", "Bhatt", "Joshi", "Pandey", "Tiwari", "Mishra",
    # South Indian
    "Iyer", "Iyengar", "Nair", "Menon", "Reddy", "Rao", "Naidu", "Chetty",
    "Pillai", "Gounder", "Mudaliar", "Hegde", "Kulkarni", "Deshpande",
    # Pan-Indian
    "Patel", "Shah", "Desai", "Jain", "Mehta", "Banerjee", "Chatterjee",
    "Ghosh", "Bose", "Sen", "Das", "Sarkar",
]


def generate_indian_name():
    """Generate a realistic Indian name."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    return f"{first_name} {last_name}"


def generate_email(name):
    """Generate email from name with random 2-3 digit suffix."""
    # Convert name to email-friendly format
    parts = name.lower().split()
    if len(parts) >= 2:
        first, last = parts[0], parts[-1]
        base = f"{first}.{last}"
    else:
        base = parts[0]

    # Add random 2-3 digit number
    suffix = random.randint(10, 999)
    return f"{base}{suffix}@gmail.com"


def email_exists(email):
    """Check if email already exists in database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE email = ?", (email,))
    count = cursor.fetchone()[0]
    conn.close()
    return count > 0


def seed_user():
    """Generate and insert a unique Indian user."""
    max_attempts = 10

    for attempt in range(max_attempts):
        name = generate_indian_name()
        email = generate_email(name)

        if email_exists(email):
            print(f"Email {email} exists, regenerating...")
            continue

        # Generate password hash
        password_hash = generate_password_hash("password123")

        # Insert user
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO users (name, email, password_hash, created_at)
               VALUES (?, ?, ?, ?)""",
            (name, email, password_hash, datetime.now().isoformat())
        )
        conn.commit()

        user_id = cursor.lastrowid
        conn.close()

        print(f"\n✓ User created successfully!")
        print(f"  id: {user_id}")
        print(f"  name: {name}")
        print(f"  email: {email}")
        return

    print("Failed to generate unique email after multiple attempts.")


if __name__ == "__main__":
    seed_user()
