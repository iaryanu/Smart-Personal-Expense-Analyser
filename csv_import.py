"""Read an expenses CSV and turn it into rows the app can add.

Only `description` and `amount` are required. Everything else is optional:
  - date            -> blank / missing: the month picked in the sidebar is used
  - category        -> blank / unknown: detected from the description
  - payment_method  -> blank / unknown: "Other"
"""

import io
import re
import warnings

import pandas as pd

from data import CATEGORIES, PAYMENT_METHODS
from functions import predict_category


# Header names we accept for each field (case, spaces and symbols are ignored,
# so "Payment Method" and "Amount (₹)" work too).
COLUMN_NAMES = {
    "description": ["description", "desc", "item", "name", "details", "note", "notes", "title"],
    "amount": ["amount", "amt", "price", "cost", "total", "spent"],
    "expense_date": ["date", "expense_date", "transaction_date", "txn_date", "month"],
    "category": ["category", "cat", "type"],
    "payment_method": ["payment_method", "payment", "payment_mode", "method", "mode"],
}

PAYMENT_ALIASES = {
    "debit": "Debit Card",
    "credit": "Credit Card",
    "bank": "Bank Transfer",
    "netbanking": "Bank Transfer",
    "net banking": "Bank Transfer",
    "neft": "Bank Transfer",
    "imps": "Bank Transfer",
    "rtgs": "Bank Transfer",
    "gpay": "UPI",
    "phonepe": "UPI",
    "paytm": "UPI",
}

AUTO_WORDS = {"", "auto", "auto detect", "auto-detect"}

REQUIRED = ["description", "amount"]


def _clean_name(name):
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def _find_columns(columns):
    """Map our field names to the actual column names in the file."""
    found = {}
    for original in columns:
        key = _clean_name(original)
        for field, names in COLUMN_NAMES.items():
            if key in names and field not in found:
                found[field] = original
    return found


def _read(raw):
    """Read the CSV bytes. Handles Excel's BOM and non-UTF-8 files."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            return pd.read_csv(
                io.BytesIO(raw), dtype=str,
                encoding=encoding, skipinitialspace=True
            )
        except UnicodeDecodeError:
            continue
        except pd.errors.EmptyDataError:
            raise ValueError("That file is empty.")
        except pd.errors.ParserError:
            raise ValueError("Couldn't read that file as a CSV.")
    raise ValueError("Couldn't read that file as a CSV.")


def _parse_date(text):
    """Turn one date string into a Timestamp (NaT if unreadable)."""
    text = text.strip()
    if not text:
        return None  # blank -> caller fills in the default month
    is_iso = re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", text)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # 05/03/2026 is read as 5 March (day first); 2026-03-05 stays ISO
        return pd.to_datetime(text, dayfirst=not is_iso, errors="coerce")


def _parse_dates(values, default_date):
    lookup = {}
    for text in values.unique():
        parsed = _parse_date(text)
        lookup[text] = pd.Timestamp(default_date) if parsed is None else parsed
    return pd.to_datetime(values.map(lookup), errors="coerce")


def _plural(n, word="row"):
    return f"{n} {word}{'' if n == 1 else 's'}"


def read_expenses_csv(raw, default_date):
    """
    raw           bytes of the uploaded file
    default_date  date used for rows that have no date (first of the chosen month)

    Returns (rows, notes):
      rows   DataFrame with expense_date, description, amount, category, payment_method
      notes  plain-English messages about anything that was skipped or adjusted

    Raises ValueError if the file can't be used at all.
    """
    df = _read(raw)
    cols = _find_columns(df.columns)

    missing = [f for f in REQUIRED if f not in cols]
    if missing:
        found = ", ".join(str(c) for c in df.columns)
        hint = (
            " Check that the values are separated by commas."
            if len(df.columns) == 1 else ""
        )
        raise ValueError(
            f"Your file is missing the required "
            f"{'column' if len(missing) == 1 else 'columns'}: "
            f"**{', '.join(missing)}**. Columns found: {found}.{hint}"
        )

    df = df.fillna("").astype(str)
    notes = []

    # ----- clean the required fields -----
    description = df[cols["description"]].str.strip()

    amount_text = df[cols["amount"]].str.replace(
        r"(?i)rs\.?|inr|[₹$,\s]", "", regex=True
    )
    amount = pd.to_numeric(amount_text, errors="coerce").astype(float).round(2)

    if "expense_date" in cols:
        dates = _parse_dates(df[cols["expense_date"]], default_date)
    else:
        dates = pd.Series(pd.Timestamp(default_date), index=df.index)

    # ----- drop rows we can't use (and say why) -----
    keep = pd.Series(True, index=df.index)
    problems = [
        (description == "", "no description"),
        (amount.isna() | (amount <= 0), "a missing, zero or negative amount"),
        (dates.isna(), "a date that couldn't be read"),
    ]
    for bad, reason in problems:
        count = int((bad & keep).sum())
        if count:
            notes.append(f"Skipped {_plural(count)} with {reason}.")
        keep &= ~bad

    description = description[keep]
    amount = amount[keep]
    dates = dates[keep]

    # ----- category -----
    if "category" in cols:
        given = df[cols["category"]][keep].str.strip().str.lower()
        by_name = {c.lower(): c for c in CATEGORIES}
        matched = given.map(by_name)
        unknown = int((matched.isna() & ~given.isin(AUTO_WORDS)).sum())
        if unknown:
            notes.append(
                f"{_plural(unknown)} had a category that isn't one of "
                f"{', '.join(CATEGORIES)} — detected from the description instead."
            )
    else:
        matched = pd.Series(None, index=description.index, dtype=object)

    category = [
        m if isinstance(m, str) else predict_category(d)
        for m, d in zip(matched, description)
    ]

    # ----- payment method -----
    if "payment_method" in cols:
        given = df[cols["payment_method"]][keep].str.strip().str.lower()
        by_name = {p.lower(): p for p in PAYMENT_METHODS}
        by_name.update(PAYMENT_ALIASES)
        matched = given.map(by_name)
        unknown = int((matched.isna() & (given != "")).sum())
        if unknown:
            notes.append(
                f"{_plural(unknown)} had an unrecognised payment method — set to Other."
            )
        payment = [m if isinstance(m, str) else "Other" for m in matched]
    else:
        payment = ["Other"] * len(description)

    rows = pd.DataFrame({
        "expense_date": dates.dt.date.tolist(),
        "description": description.tolist(),
        "amount": amount.tolist(),
        "category": category,
        "payment_method": payment,
    })

    return rows, notes
