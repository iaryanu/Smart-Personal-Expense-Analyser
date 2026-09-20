import string
import pandas as pd


KEYWORDS = {
    "Food": "pizza burger food restaurant swiggy zomato cafe coffee lunch dinner breakfast",
    "Travel": "uber ola train bus metro rickshaw auto travel petrol fuel",
    "Shopping": "amazon flipkart clothes shirt shoes shopping",
    "Education": "book books course college education stationery",
    "Entertainment": "movie netflix game gaming concert",
    "Health": "medicine doctor hospital pharmacy health",
    "Bills": "electricity recharge internet wifi bill"
}


# ---------- Category detection ----------

def predict_category(text):
    # strip punctuation so "Pizza," or "Uber." still match
    clean = text.lower().translate(str.maketrans("", "", string.punctuation))
    words = clean.split()

    for category, keywords in KEYWORDS.items():
        if any(word in words for word in keywords.split()):
            return category

    return "Other"


# ---------- Month helpers ----------

def month_data(df, year, month):
    """Rows that belong to one specific month."""
    if df.empty:
        return df
    dates = df["expense_date"].dt
    return df[(dates.year == year) & (dates.month == month)]


def previous_month(year, month):
    return (year - 1, 12) if month == 1 else (year, month - 1)


# ---------- Totals ----------

def total_expenses(df):
    return float(df["amount"].sum()) if not df.empty else 0.0


def monthly_expenses(df, year, month):
    return total_expenses(month_data(df, year, month))


def budget_percent(budget, spent):
    return spent / budget if budget > 0 else 0


# ---------- Chart data ----------

def category_data(df):
    return df.groupby("category")["amount"].sum().sort_values(ascending=False)


def payment_data(df):
    return df.groupby("payment_method")["amount"].sum().sort_values(ascending=False)


def monthly_data(df):
    """Total per month, with empty months in between shown as 0."""
    months = df["expense_date"].dt.to_period("M")
    totals = df.groupby(months)["amount"].sum()
    full_range = pd.period_range(totals.index.min(), totals.index.max(), freq="M")
    totals = totals.reindex(full_range, fill_value=0.0)
    totals.index = totals.index.strftime("%Y-%m")
    return totals


# ---------- Insights ----------

def top_category(df):
    data = category_data(df)
    return (data.idxmax(), float(data.max())) if not data.empty else ("None", 0.0)


def biggest_expense(df):
    row = df.loc[df["amount"].idxmax()]
    return row["description"], float(row["amount"])


def budget_status(budget, percent):
    if budget <= 0:
        return "ℹ️ Set a budget for this month in the sidebar to track it.", "info"
    if percent >= 1:
        return "🚨 Budget exceeded.", "error"
    if percent >= 0.8:
        return "⚠️ You are close to your budget.", "warning"
    return "✅ You are within your budget.", "success"
