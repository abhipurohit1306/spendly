import calendar
import math
from datetime import date, datetime, timedelta

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import create_user, get_user_by_email, init_db, seed_db
from database.queries import (
    get_category_breakdown,
    get_expense_by_id,
    get_recent_transactions,
    get_summary_stats,
    get_user_by_id,
    insert_expense,
    update_expense,
)

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-production"


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
# Date filter helpers                                                 #
# ------------------------------------------------------------------ #

def parse_date_range(args):
    """Return (start_date, end_date, error) from query args.

    Dates come back as 'YYYY-MM-DD' strings or None. An invalid or
    reversed range returns (None, None, message) so the page renders
    unfiltered."""
    raw_start = (args.get("start_date") or "").strip()
    raw_end = (args.get("end_date") or "").strip()
    try:
        start = datetime.strptime(raw_start, "%Y-%m-%d").date() if raw_start else None
        end = datetime.strptime(raw_end, "%Y-%m-%d").date() if raw_end else None
    except ValueError:
        return None, None, "Please enter valid dates."

    if start and end and start > end:
        return None, None, "Start date must be on or before end date."

    return (
        start.isoformat() if start else None,
        end.isoformat() if end else None,
        None,
    )


def months_ago(today, months):
    """Return the same day `months` calendar months before `today`,
    clamped to the last day of a shorter month (31 May - 3 -> 28 Feb)."""
    month_index = today.year * 12 + today.month - 1 - months
    year, month = divmod(month_index, 12)
    month += 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def date_presets(today):
    """Return the quick-filter ranges shown above the profile stats."""
    return [
        {
            "label": "This month",
            "start_date": today.replace(day=1).isoformat(),
            "end_date": today.isoformat(),
        },
        {
            "label": "Last 30 days",
            "start_date": (today - timedelta(days=29)).isoformat(),
            "end_date": today.isoformat(),
        },
        {
            "label": "Last 3 months",
            "start_date": months_ago(today, 3).isoformat(),
            "end_date": today.isoformat(),
        },
        {
            "label": "Last 6 months",
            "start_date": months_ago(today, 6).isoformat(),
            "end_date": today.isoformat(),
        },
        {"label": "All time", "start_date": None, "end_date": None},
    ]


# ------------------------------------------------------------------ #
# Expense form helpers                                                #
# ------------------------------------------------------------------ #

# Title case matters: profile.html builds badge classes from category|lower.
EXPENSE_CATEGORIES = (
    "Food",
    "Transport",
    "Bills",
    "Health",
    "Entertainment",
    "Shopping",
    "Other",
)
AMOUNT_MAX = 10_000_000
DESCRIPTION_MAX_LEN = 200


def parse_expense_form(form):
    """Return (expense, error) from submitted add/edit expense form data.

    On success `expense` is a dict ready for insert_expense() or
    update_expense() and error
    is None. On failure it is (None, message) for the first bad field,
    checked in order: amount, category, date, description."""
    raw_amount = (form.get("amount") or "").strip()
    if not raw_amount:
        return None, "Please enter an amount."
    try:
        amount = float(raw_amount)
    except ValueError:
        amount = None
    if amount is None or not math.isfinite(amount) or amount <= 0:
        return None, "Amount must be a number greater than 0."
    if amount > AMOUNT_MAX:
        return None, f"Amount must be ₹{AMOUNT_MAX:,} or less."

    category = (form.get("category") or "").strip()
    if category not in EXPENSE_CATEGORIES:
        return None, "Please choose a valid category."

    raw_date = (form.get("date") or "").strip()
    try:
        expense_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "Please enter a valid date."

    description = (form.get("description") or "").strip() or None
    if description and len(description) > DESCRIPTION_MAX_LEN:
        return None, (
            f"Description must be {DESCRIPTION_MAX_LEN} characters or fewer."
        )

    return {
        "amount": round(amount, 2),
        "category": category,
        "date": expense_date.isoformat(),
        "description": description,
    }, None


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
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    user = get_user_by_id(user_id)
    if user is None:
        session.clear()
        return redirect(url_for("login"))

    start_date, end_date, filter_error = parse_date_range(request.args)
    date_range = {"start_date": start_date, "end_date": end_date}

    # --- Transaction history ---
    expenses = get_recent_transactions(user_id, **date_range)
    # --- end transaction history ---

    # --- Summary stats ---
    summary = get_summary_stats(user_id, **date_range)
    # --- end summary stats ---

    # --- Category breakdown ---
    categories = get_category_breakdown(user_id, **date_range)
    # --- end category breakdown ---

    return render_template(
        "profile.html",
        user=user,
        expenses=expenses,
        summary=summary,
        categories=categories,
        start_date=start_date,
        end_date=end_date,
        filter_error=filter_error,
        presets=date_presets(date.today()),
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    # A stale session for a deleted user would fail the expenses FK.
    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            form={"date": date.today().isoformat()},
        )

    expense, error = parse_expense_form(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=EXPENSE_CATEGORIES,
            form=request.form,
            error=error,
        )

    insert_expense(user_id, **expense)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("login"))

    if get_user_by_id(user_id) is None:
        session.clear()
        return redirect(url_for("login"))

    # Missing and foreign expenses both 404 so ids aren't disclosed.
    expense = get_expense_by_id(id, user_id)
    if expense is None:
        abort(404)

    if request.method == "GET":
        return render_template(
            "edit_expense.html",
            categories=EXPENSE_CATEGORIES,
            form={
                "amount": f"{expense['amount']:.2f}",
                "category": expense["category"],
                "date": expense["date"],
                "description": expense["description"] or "",
            },
            expense_id=id,
        )

    updated, error = parse_expense_form(request.form)
    if error:
        return render_template(
            "edit_expense.html",
            categories=EXPENSE_CATEGORIES,
            form=request.form,
            expense_id=id,
            error=error,
        )

    # The row may have vanished between the lookup and the update.
    if not update_expense(id, user_id, **updated):
        abort(404)
    return redirect(url_for("profile"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
