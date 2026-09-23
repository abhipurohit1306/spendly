from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_db, get_user_by_email, init_db, seed_db

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


# ------------------------------------------------------------------ #
# Hardcoded profile data — Step 4, replaced by DB queries in Step 5   #
# ------------------------------------------------------------------ #

PROFILE_USER = {
    "name": "Demo User",
    "email": "demo@spendly.com",
    "member_since": "2026-09-01",
}

PROFILE_EXPENSES = [
    {
        "id": 8, "amount": 20.00, "category": "Other",
        "date": "2026-09-20", "description": "Birthday gift",
    },
    {
        "id": 7, "amount": 60.20, "category": "Shopping",
        "date": "2026-09-17", "description": "New running shoes",
    },
    {
        "id": 6, "amount": 15.00, "category": "Entertainment",
        "date": "2026-09-14", "description": "Movie ticket",
    },
    {
        "id": 5, "amount": 32.75, "category": "Food",
        "date": "2026-09-11", "description": "Groceries",
    },
    {
        "id": 4, "amount": 25.00, "category": "Health",
        "date": "2026-09-09", "description": "Pharmacy - vitamins",
    },
    {
        "id": 3, "amount": 89.99, "category": "Bills",
        "date": "2026-09-05", "description": "Electricity bill",
    },
    {
        "id": 2, "amount": 45.00, "category": "Transport",
        "date": "2026-09-04", "description": "Monthly metro pass",
    },
    {
        "id": 1, "amount": 12.50, "category": "Food",
        "date": "2026-09-02", "description": "Coffee and bagel",
    },
]


def build_profile_summary(expenses):
    """Derive total, count, top category and per-category breakdown
    (sorted by total, largest first) from a list of expense dicts."""
    totals = {}
    for expense in expenses:
        category = expense["category"]
        totals[category] = totals.get(category, 0) + expense["amount"]

    total_spent = sum(totals.values())
    categories = [
        {
            "category": category,
            "total": total,
            "percent": round(total / total_spent * 100) if total_spent else 0,
        }
        for category, total in sorted(
            totals.items(), key=lambda item: item[1], reverse=True
        )
    ]
    return {
        "total_spent": total_spent,
        "transaction_count": len(expenses),
        "top_category": categories[0]["category"] if categories else None,
        "categories": categories,
    }


# ------------------------------------------------------------------ #
# Template filters                                                    #
# ------------------------------------------------------------------ #

@app.template_filter("date_fmt")
def date_fmt(value, fmt="%d %b %Y"):
    """Format a 'YYYY-MM-DD[ ...]' string; return it unchanged if unparseable."""
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").strftime(fmt)
    except ValueError:
        return value


@app.template_filter("initials")
def initials(name):
    """Return up to two uppercase initials from a name, or '?' if empty."""
    parts = (name or "").split()
    if not parts:
        return "?"
    first, last = parts[0][0], parts[-1][0] if len(parts) > 1 else ""
    return (first + last).upper()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not name or not email or not password:
        return render_template("register.html", error="All fields are required.")

    if "@" not in email or "." not in email.split("@")[-1]:
        return render_template(
            "register.html", error="Please enter a valid email address."
        )

    if len(password) < 8:
        return render_template(
            "register.html", error="Password must be at least 8 characters."
        )

    if get_user_by_email(email):
        return render_template(
            "register.html", error="An account with that email already exists."
        )

    user_id = create_user(name, email, password)
    session["user_id"] = user_id
    session["user_name"] = name
    return redirect(url_for("profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not email or not password:
        return render_template(
            "login.html", error="Email and password are required.", email=email
        )

    user = get_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template(
        "profile.html",
        user=PROFILE_USER,
        expenses=PROFILE_EXPENSES,
        summary=build_profile_summary(PROFILE_EXPENSES),
    )


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

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
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
