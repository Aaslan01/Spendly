from database.db import get_db


def _build_date_filter(user_id: int, date_from: str | None, date_to: str | None):
    # `where` is built from hardcoded fragments only — all values go through params
    conditions = ["user_id = ?"]
    params: list = [user_id]
    if date_from and date_to:
        conditions.append("date BETWEEN ? AND ?")
        params.extend([date_from, date_to])
    return " AND ".join(conditions), params


def get_category_breakdown(user_id: int, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """
    Fetches category breakdown for a given user.

    Args:
        user_id: The ID of the user whose expenses to analyze

    Returns:
        A list of dicts with keys: name, amount, pct
        - name: category name (string)
        - amount: total amount spent in that category (float, rounded to 2 decimals)
        - pct: percentage of total spending (integer, 0-100)
        Ordered by amount DESC. Returns empty list if user has no expenses.
    """
    conn = get_db()
    cursor = conn.cursor()

    where, params = _build_date_filter(user_id, date_from, date_to)

    # Get category totals grouped and ordered by amount DESC
    cursor.execute(
        "SELECT category, SUM(amount) as total "
        "FROM expenses "
        "WHERE " + where + " "
        "GROUP BY category "
        "ORDER BY total DESC",
        params
    )

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return []

    # Calculate grand total
    grand_total = sum(row["total"] for row in rows)

    # Build result with rounded percentages
    result = []
    for row in rows:
        amount = round(row["total"], 2)
        pct = round((row["total"] / grand_total) * 100)
        result.append({
            "name": row["category"],
            "amount": amount,
            "pct": pct
        })

    # Ensure percentages sum to exactly 100
    # Adjust the largest category (first one, since ordered by amount DESC)
    total_pct = sum(item["pct"] for item in result)
    if total_pct != 100:
        result[0]["pct"] += (100 - total_pct)

    return result


def get_recent_transactions(user_id: int, limit: int = 10, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """
    Fetches recent transactions for a given user.

    Args:
        user_id: The ID of the user whose transactions to fetch
        limit: Maximum number of transactions to return (default: 10)

    Returns:
        A list of dicts with keys: date, description, category, amount
        Returns empty list if user has no expenses
    """
    conn = get_db()
    cursor = conn.cursor()

    where, params = _build_date_filter(user_id, date_from, date_to)
    params.append(limit)

    cursor.execute(
        "SELECT date, description, category, amount "
        "FROM expenses "
        "WHERE " + where + " "
        "ORDER BY date DESC "
        "LIMIT ?",
        params
    )

    rows = cursor.fetchall()
    conn.close()

    transactions = []
    for row in rows:
        transactions.append({
            "date": row["date"],
            "description": row["description"],
            "category": row["category"],
            "amount": row["amount"]
        })

    return transactions


def get_summary_stats(user_id: int, date_from: str | None = None, date_to: str | None = None) -> dict:
    """
    Fetches summary statistics for a given user's expenses.

    Args:
        user_id: The ID of the user whose stats to fetch

    Returns:
        A dict with keys:
            - total_spent: SUM of all amounts (float, rounded to 2 decimals)
            - transaction_count: COUNT of all expenses (int)
            - top_category: The category with highest total spending (string)
        Returns {"total_spent": 0, "transaction_count": 0, "top_category": "—"}
        if user has no expenses.
    """
    conn = get_db()
    cursor = conn.cursor()

    where, params = _build_date_filter(user_id, date_from, date_to)

    # Get total spent and transaction count
    cursor.execute(
        "SELECT COALESCE(SUM(amount), 0) AS total_spent, "
        "COUNT(*) AS transaction_count "
        "FROM expenses "
        "WHERE " + where,
        params
    )

    row = cursor.fetchone()
    total_spent = round(row["total_spent"], 2)
    transaction_count = row["transaction_count"]

    # Handle users with no expenses
    if transaction_count == 0:
        conn.close()
        return {
            "total_spent": 0,
            "transaction_count": 0,
            "top_category": "—"
        }

    # Get top category by total spending
    cursor.execute(
        "SELECT category, SUM(amount) AS category_total "
        "FROM expenses "
        "WHERE " + where + " "
        "GROUP BY category "
        "ORDER BY category_total DESC "
        "LIMIT 1",
        params
    )

    top_row = cursor.fetchone()
    top_category = top_row["category"] if top_row else "—"

    conn.close()

    return {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category
    }
