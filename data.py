import pandas as pd

COLUMNS = [
    "id", "expense_date", "description",
    "amount", "category", "payment_method"
]


def empty_data():
    return pd.DataFrame(columns=COLUMNS)


def next_id(df):
    # max + 1 (not len + 1) so IDs stay unique after deleting a row
    if df.empty:
        return 1
    return int(pd.to_numeric(df["id"]).max()) + 1


def add_expense(df, expense_date, description, amount, category, payment):
    new = pd.DataFrame([{
        "id": next_id(df),
        "expense_date": expense_date,
        "description": description.strip(),
        "amount": amount,
        "category": category,
        "payment_method": payment
    }])
    return new if df.empty else pd.concat([df, new], ignore_index=True)


def delete_expense(df, expense_id):
    return df[df["id"] != expense_id].reset_index(drop=True)


def prepare(df):
    if df.empty:
        return df
    df = df.copy()
    df["id"] = pd.to_numeric(df["id"]).astype(int)
    df["expense_date"] = pd.to_datetime(df["expense_date"])
    df["amount"] = pd.to_numeric(df["amount"])
    return df
