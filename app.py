import streamlit as st
from datetime import date

from data import (
    empty_data, add_expense, delete_expense, prepare
)

from functions import (
    predict_category, month_data, previous_month, total_expenses,
    monthly_expenses, budget_percent, category_data, monthly_data,
    payment_data, top_category, biggest_expense, budget_status
)


MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December"
]

CATEGORIES = [
    "Food", "Travel", "Shopping", "Bills",
    "Education", "Entertainment", "Health", "Other"
]

# Newer Streamlit uses width="stretch"; older versions use use_container_width.
_version = tuple(int(x) for x in st.__version__.split(".")[:2])
STRETCH = (
    {"width": "stretch"} if _version >= (1, 50)
    else {"use_container_width": True}
)


def rupees(value):
    return f"-₹{abs(value):,.2f}" if value < 0 else f"₹{value:,.2f}"


# ---------- Setup ----------

st.set_page_config(
    page_title="Expense Analyser",
    page_icon="💰",
    layout="wide"
)

if "expenses" not in st.session_state:
    st.session_state.expenses = empty_data()

if "budgets" not in st.session_state:
    st.session_state.budgets = {}

# one-time message shown after a save / delete (st.rerun would hide st.success)
if "flash" in st.session_state:
    st.toast(st.session_state.pop("flash"), icon="✅")

df = prepare(st.session_state.expenses)


# ---------- Header ----------

st.title("💰 Smart Personal Expense Analyser")
st.write("Track expenses, analyse spending and monitor your budget.")


# ---------- Sidebar: month + budget ----------

st.sidebar.header("⚙️ Settings")

today = date.today()

sel_month_name = st.sidebar.selectbox(
    "Month", MONTHS, index=today.month - 1
)
sel_year = st.sidebar.selectbox(
    "Year", list(range(today.year - 10, today.year + 2)), index=10
)

sel_month = MONTHS.index(sel_month_name) + 1
month_key = f"{sel_year}-{sel_month:02d}"
month_label = f"{sel_month_name} {sel_year}"

# Each month keeps its own budget and income (new months start fresh).
saved = st.session_state.budgets.get(
    month_key, {"budget": 10000.0, "income": 20000.0}
)

budget = st.sidebar.number_input(
    f"Budget for {month_label} (₹)", 0.0, 1000000.0,
    saved["budget"], 500.0, key=f"budget_{month_key}"
)

income = st.sidebar.number_input(
    f"Income for {month_label} (₹)", 0.0, 1000000.0,
    saved["income"], 500.0, key=f"income_{month_key}"
)

st.session_state.budgets[month_key] = {"budget": budget, "income": income}


# ---------- Numbers used across the page ----------

month_df = month_data(df, sel_year, sel_month)

spent = total_expenses(month_df)
prev_year, prev_month = previous_month(sel_year, sel_month)
prev_spent = monthly_expenses(df, prev_year, prev_month)

budget_left = budget - spent
balance = income - spent
percent = budget_percent(budget, spent)


# ---------- Tabs ----------

dash_tab, add_tab, table_tab = st.tabs(
    ["📊 Dashboard", "➕ Add Expense", "📋 Transactions"]
)


# =============== DASHBOARD ===============

with dash_tab:

    st.subheader(f"{month_label} Overview")

    # --- key numbers ---
    c1, c2, c3, c4 = st.columns(4)

    with c1, st.container(border=True):
        change = spent - prev_spent
        st.metric(
            "Spent This Month",
            rupees(spent),
            delta=(
                f"{'-' if change < 0 else '+'}₹{abs(change):,.2f} vs last month"
                if prev_spent > 0 else None
            ),
            delta_color="inverse"
        )

    with c2, st.container(border=True):
        st.metric("Budget Left", rupees(budget_left))

    with c3, st.container(border=True):
        st.metric("Balance (Income − Spent)", rupees(balance))

    with c4, st.container(border=True):
        st.metric("All-time Total", rupees(total_expenses(df)))

    # --- budget progress ---
    st.subheader("Monthly Budget")

    st.progress(min(percent, 1.0))
    st.write(f"{percent * 100:.1f}% of ₹{budget:,.0f} budget used.")

    message, status = budget_status(budget, percent)
    getattr(st, status)(message)

    # --- charts / insights ---
    if df.empty:
        st.info("No expenses yet. Add your first expense in the ➕ Add Expense tab.")

    else:
        if month_df.empty:
            st.info(
                f"No expenses recorded for {month_label}. "
                "Pick another month in the sidebar or add one."
            )

        else:
            st.subheader(f"📈 Spending Analytics — {month_label}")

            left, right = st.columns(2)

            with left:
                st.markdown("**Category Distribution**")

                pie_df = category_data(month_df).reset_index()
                pie_df.columns = ["category", "amount"]
                pie_df["share"] = pie_df["amount"] / pie_df["amount"].sum()

                # Pie chart drawn with Streamlit's own vega_lite_chart
                pie_spec = {
                    "mark": {
                        "type": "arc", "innerRadius": 50,
                        "outerRadius": 120, "tooltip": True
                    },
                    "encoding": {
                        "theta": {
                            "field": "amount", "type": "quantitative",
                            "stack": True
                        },
                        "color": {
                            "field": "category", "type": "nominal",
                            "sort": pie_df["category"].tolist(),
                            "legend": {"title": "Category"}
                        },
                        "order": {
                            "field": "amount", "type": "quantitative",
                            "sort": "descending"
                        },
                        "tooltip": [
                            {"field": "category", "type": "nominal",
                             "title": "Category"},
                            {"field": "amount", "type": "quantitative",
                             "title": "Amount (₹)", "format": ",.2f"},
                            {"field": "share", "type": "quantitative",
                             "title": "Share", "format": ".1%"}
                        ]
                    },
                    "height": 300
                }
                st.vega_lite_chart(pie_df, pie_spec, **STRETCH)

            with right:
                st.markdown("**Payment Method Spending**")
                st.bar_chart(payment_data(month_df))

            # --- insights ---
            st.subheader("💡 Insights")

            with st.container(border=True):
                top_cat, top_amount = top_category(month_df)
                big_name, big_amount = biggest_expense(month_df)
                count = len(month_df)

                st.markdown(
                    f"- **Top category:** {top_cat} — {rupees(top_amount)} "
                    f"({top_amount / spent * 100:.0f}% of this month)\n"
                    f"- **Biggest expense:** {big_name} — {rupees(big_amount)}\n"
                    f"- **Transactions:** {count} "
                    f"(average {rupees(spent / count)})"
                )

        st.subheader("📅 Monthly Spending Trend")
        trend = monthly_data(df)

        if len(trend) > 1:
            st.line_chart(trend)
        else:
            st.bar_chart(trend)


# =============== ADD EXPENSE ===============

with add_tab:

    st.subheader("Add Expense")

    with st.form("expense_form", clear_on_submit=True):
        st.caption(
            f"📅 Adding to **{month_label}** (change it in the sidebar)"
        )

        c1, c2 = st.columns(2)

        with c1:
            description = st.text_input(
                "Description", placeholder="Pizza, Uber, Books..."
            )
            amount = st.number_input(
                "Amount (₹)", min_value=0.01, value=100.0
            )

        with c2:
            payment = st.selectbox(
                "Payment Method",
                ["Cash", "UPI", "Debit Card",
                 "Credit Card", "Bank Transfer", "Other"]
            )

            category = st.selectbox(
                "Category", ["Auto Detect"] + CATEGORIES
            )

        save = st.form_submit_button("Save Expense")

        if save:
            if not description.strip():
                st.error("Enter an expense description.")
            else:
                final_category = (
                    predict_category(description)
                    if category == "Auto Detect"
                    else category
                )

                st.session_state.expenses = add_expense(
                    st.session_state.expenses,
                    date(sel_year, sel_month, 1),
                    description, amount, final_category, payment
                )

                st.session_state.flash = (
                    f"Saved {rupees(amount)} to {month_label} "
                    f"· Category: {final_category}"
                )
                st.rerun()


# =============== TRANSACTIONS ===============

with table_tab:

    st.subheader("All Expenses")

    if df.empty:
        st.write("No transactions recorded.")

    else:
        scope = st.radio(
            "Show", [month_label, "All months"], horizontal=True
        )
        view = month_df if scope == month_label else df

        if view.empty:
            st.info(f"No transactions in {month_label}.")

        else:
            view = view.sort_values(
                ["expense_date", "id"], ascending=False
            )

            display = view.copy()
            display["expense_date"] = display["expense_date"].dt.strftime("%b %Y")

            st.dataframe(
                display,
                hide_index=True,
                column_config={
                    "id": "ID",
                    "expense_date": "Month",
                    "description": "Description",
                    "amount": st.column_config.NumberColumn(
                        "Amount (₹)", format="₹%.2f"
                    ),
                    "category": "Category",
                    "payment_method": "Payment",
                },
                **STRETCH
            )

            # --- delete one ---
            st.subheader("🗑️ Delete Expense")

            labels = {
                row.id: (
                    f"#{row.id} · {row.expense_date:%b %Y} · "
                    f"{row.description} · ₹{row.amount:,.2f}"
                )
                for row in view.itertuples()
            }

            selected_id = st.selectbox(
                "Choose an expense", list(labels), format_func=labels.get
            )

            if st.button("Delete Selected Expense"):
                st.session_state.expenses = delete_expense(
                    st.session_state.expenses, selected_id
                )
                st.session_state.flash = "Expense deleted."
                st.rerun()

        # --- export ---
        st.subheader("📥 Export")

        export = df.assign(
            expense_date=df["expense_date"].dt.strftime("%b %Y")
        )
        st.download_button(
            "Download CSV",
            export.to_csv(index=False).encode("utf-8"),
            "expenses.csv",
            "text/csv"
        )

        # --- clear all ---
        st.subheader("⚠️ Danger Zone")

        confirm = st.checkbox("Yes, I want to delete ALL expenses")
        if st.button("Delete All Expenses", disabled=not confirm):
            st.session_state.expenses = empty_data()
            st.session_state.flash = "All expenses deleted."
            st.rerun()


st.divider()
st.caption("Built with Python, Pandas and Streamlit")
