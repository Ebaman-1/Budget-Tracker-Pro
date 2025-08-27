import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
import io

st.set_page_config(page_title="Budget Tracker Pro", page_icon="💰", layout="wide")

# ----------------------------
# Config
# ----------------------------
REQUIRED_COLS = ["Date", "Type", "Category", "Description", "Amount"]
CATEGORY_OPTIONS = ["Food", "Transport", "Bills", "Entertainment", "Other"]
CURRENCY_OPTIONS = {"$": "USD", "₦": "NGN", "€": "EUR", "£": "GBP"}

# ----------------------------
# Ensure schema
# ----------------------------
def ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(columns=REQUIRED_COLS)
    for col in REQUIRED_COLS:
        if col not in df.columns:
            if col == "Date":
                df[col] = pd.Series(dtype="datetime64[ns]")
            elif col == "Amount":
                df[col] = pd.Series(dtype="float")
            else:
                df[col] = pd.Series(dtype="object")
    df = df[REQUIRED_COLS]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    return df

# ----------------------------
# State Init
# ----------------------------
if "transactions" not in st.session_state:
    st.session_state["transactions"] = pd.DataFrame(columns=REQUIRED_COLS)

if "budgets" not in st.session_state:
    st.session_state["budgets"] = {cat: None for cat in CATEGORY_OPTIONS}

if "currency" not in st.session_state:
    st.session_state["currency"] = "$"

if "recurring" not in st.session_state:
    st.session_state["recurring"] = []  # list of dicts: {Type, Category, Amount, Description}

st.session_state["transactions"] = ensure_schema(st.session_state["transactions"])

currency = st.session_state["currency"]

# ----------------------------
# Sidebar: Settings + Filters
# ----------------------------
st.sidebar.title("⚙️ Settings")

# Currency Selector
currency = st.sidebar.selectbox("Currency", list(CURRENCY_OPTIONS.keys()), index=list(CURRENCY_OPTIONS.keys()).index(st.session_state["currency"]))
st.session_state["currency"] = currency

# Dark/Light Mode
theme = st.sidebar.radio("Theme", ["Light", "Dark"], horizontal=True)
if theme == "Dark":
    st.markdown(
        """
        <style>
        body { background-color: #1e1e1e; color: #e6e6e6; }
        .stApp { background-color: #1e1e1e; }
        </style>
        """,
        unsafe_allow_html=True
    )

# Reset
if st.sidebar.button("🔄 Reset Data"):
    for k in ["transactions", "budgets", "recurring"]:
        st.session_state.pop(k, None)
    st.rerun()

st.sidebar.header("🔍 Filters")
df_base = st.session_state["transactions"]

if not df_base.empty:
    search_text = st.sidebar.text_input("Search by Description", value="")
    category_choices = sorted(
        [c for c in df_base["Category"].dropna().unique().tolist() if str(c).strip() != ""]
    )
    filter_category = st.sidebar.multiselect("Filter by Category", options=category_choices)

    month_options = ["All"] + sorted(
        df_base["Date"].dropna().dt.strftime("%B %Y").unique().tolist()
    )
    filter_month = st.sidebar.selectbox("Filter by Month", options=month_options, index=0)
else:
    search_text = ""
    filter_category = []
    filter_month = "All"

# ----------------------------
# Header
# ----------------------------
st.title("💰 Budget Tracker Pro")
st.caption("Track income & expenses, budgets, recurring items, charts, and import/export.")

# ----------------------------
# Add Transaction
# ----------------------------
st.header("➕ Add Transaction")
with st.form("transaction_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        t_type = st.radio("Type", ["Income", "Expense"], horizontal=True)
    with col2:
        t_cat = st.selectbox("Category", CATEGORY_OPTIONS)
    with col3:
        t_amt = st.number_input("Amount", min_value=0.0, format="%.2f")

    desc = st.text_input("Description")
    submit = st.form_submit_button("Add")

    if submit and t_amt > 0:
        new_row = pd.DataFrame([[datetime.now(), t_type, t_cat, desc, t_amt]], columns=REQUIRED_COLS)
        st.session_state["transactions"] = pd.concat([st.session_state["transactions"], new_row], ignore_index=True)
        st.success("✅ Transaction Added!")

# ----------------------------
# Recurring Transactions
# ----------------------------
st.header("🔁 Recurring Transactions")
with st.form("recurring_form"):
    col1, col2, col3 = st.columns(3)
    with col1:
        r_type = st.radio("Type", ["Income", "Expense"], key="rec_type", horizontal=True)
    with col2:
        r_cat = st.selectbox("Category", CATEGORY_OPTIONS, key="rec_cat")
    with col3:
        r_amt = st.number_input("Amount", min_value=0.0, format="%.2f", key="rec_amt")
    r_desc = st.text_input("Description", key="rec_desc")
    add_rec = st.form_submit_button("Add Recurring")

    if add_rec and r_amt > 0:
        st.session_state["recurring"].append({"Type": r_type, "Category": r_cat, "Amount": r_amt, "Description": r_desc})
        st.success("✅ Recurring Transaction Added!")

# 👉 Show stored recurring transactions
if st.session_state["recurring"]:
    st.subheader("📋 Stored Recurring Transactions")
    rec_df = pd.DataFrame(st.session_state["recurring"])
    st.dataframe(rec_df, use_container_width=True)
else:
    st.caption("No recurring transactions saved yet.")

# Apply recurring monthly (simple check: if not present this month, add once)
now_month = datetime.now().strftime("%B %Y")
for rec in st.session_state["recurring"]:
    if not st.session_state["transactions"].empty:
        exists = (
            (st.session_state["transactions"]["Description"] == rec["Description"])
            & (st.session_state["transactions"]["Category"] == rec["Category"])
            & (st.session_state["transactions"]["Date"].dt.strftime("%B %Y") == now_month)
        ).any()
    else:
        exists = False
    if not exists:
        new_row = pd.DataFrame([[datetime.now(), rec["Type"], rec["Category"], rec["Description"], rec["Amount"]]],
                               columns=REQUIRED_COLS)
        st.session_state["transactions"] = pd.concat([st.session_state["transactions"], new_row], ignore_index=True)

# ----------------------------
# Budget Goals
# ----------------------------
st.header("🎯 Budget Goals")
bud_cols = st.columns(len(CATEGORY_OPTIONS))
for idx, cat in enumerate(CATEGORY_OPTIONS):
    current_val = st.session_state["budgets"].get(cat)
    with bud_cols[idx]:
        new_val = st.number_input(f"{cat} Budget", min_value=0.0, value=current_val if current_val else 0.0, format="%.2f", key=f"bud_{cat}")
        st.session_state["budgets"][cat] = new_val if new_val > 0 else None

# ----------------------------
# Export / Import
# ----------------------------
st.header("📂 Export / Import")
col1, col2 = st.columns(2)
with col1:
    csv = st.session_state["transactions"].to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download CSV", data=csv, file_name="budget.csv", mime="text/csv")

    # Excel export
    excel_buffer = io.BytesIO()
    excel_ok = True
    try:
        st.session_state["transactions"].to_excel(excel_buffer, index=False)
    except Exception:
        excel_ok = False
    if excel_ok:
        st.download_button("⬇️ Download Excel", data=excel_buffer.getvalue(), file_name="budget.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    else:
        st.caption("Install `openpyxl` to enable Excel export: `pip install openpyxl`")

with col2:
    uploaded = st.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])
    if uploaded:
        try:
            if uploaded.name.endswith(".csv"):
                df_new = pd.read_csv(uploaded)
            else:
                df_new = pd.read_excel(uploaded)
            df_new = ensure_schema(df_new)
            st.session_state["transactions"] = pd.concat([st.session_state["transactions"], df_new], ignore_index=True)
            st.success("✅ Data Imported!")
        except Exception as e:
            st.error(f"Import failed: {e}")

# ----------------------------
# Apply Filters
# ----------------------------
df = st.session_state["transactions"].copy()

if search_text:
    df = df[df["Description"].str.contains(search_text, case=False, na=False)]
if filter_category:
    df = df[df["Category"].isin(filter_category)]
if filter_month != "All":
    df = df[df["Date"].dt.strftime("%B %Y") == filter_month]

# ----------------------------
# Display Data
# ----------------------------
st.header("📊 Transaction History")
if not df.empty:
    st.dataframe(df.sort_values("Date"), use_container_width=True)
else:
    st.info("No transactions match your filters. Add some above or adjust filters.")

# ----------------------------
# Edit Transactions
# ----------------------------
st.subheader("✏️ Edit Transactions")
if not st.session_state["transactions"].empty:
    edit_index = st.number_input("Enter transaction index to edit", min_value=0, max_value=len(st.session_state["transactions"])-1, step=1)
    row = st.session_state["transactions"].iloc[int(edit_index)]
    with st.form("edit_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            e_type = st.radio("Type", ["Income", "Expense"], index=["Income", "Expense"].index(row["Type"]))
        with col2:
            e_cat = st.selectbox("Category", CATEGORY_OPTIONS, index=CATEGORY_OPTIONS.index(row["Category"]))
        with col3:
            e_amt = st.number_input("Amount", min_value=0.0, format="%.2f", value=float(row["Amount"]))
        e_desc = st.text_input("Description", value=row["Description"])
        save_edit = st.form_submit_button("Save Changes")
        if save_edit:
            st.session_state["transactions"].at[edit_index, "Type"] = e_type
            st.session_state["transactions"].at[edit_index, "Category"] = e_cat
            st.session_state["transactions"].at[edit_index, "Amount"] = e_amt
            st.session_state["transactions"].at[edit_index, "Description"] = e_desc
            st.session_state["transactions"].at[edit_index, "Date"] = datetime.now()
            st.success("✅ Transaction Updated!")
else:
    st.caption("No transactions available to edit.")

# ----------------------------
# Monthly Summary (Current Month)
# ----------------------------
st.subheader("📈 Monthly Summary")
current_month = datetime.now().strftime("%B %Y")
month_df = st.session_state["transactions"][st.session_state["transactions"]["Date"].dt.strftime("%B %Y") == current_month]

if not month_df.empty:
    income = month_df[month_df["Type"] == "Income"]["Amount"].sum()
    expenses = month_df[month_df["Type"] == "Expense"]["Amount"].sum()
    balance = income - expenses
    st.info(f"{current_month} – Income: {currency}{income:,.2f} | Expenses: {currency}{expenses:,.2f} | Balance: {currency}{balance:,.2f}")
else:
    st.info(f"{current_month} – Income: {currency}0.00 | Expenses: {currency}0.00 | Balance: {currency}0.00")

# ----------------------------
# Budget warnings (current month)
# ----------------------------
st.subheader("⚠️ Budget Check")
if not month_df.empty:
    exp_by_cat = month_df[month_df["Type"] == "Expense"].groupby("Category", as_index=False)["Amount"].sum()
    for cat, limit in st.session_state["budgets"].items():
        spent = float(exp_by_cat.loc[exp_by_cat["Category"] == cat, "Amount"].sum()) if not exp_by_cat.empty else 0.0
        if limit and spent > limit:
            st.error(f"❌ Over budget for {cat}: Spent {currency}{spent:,.2f} / Limit {currency}{limit:,.2f}")
        elif limit:
            st.success(f"✅ Within budget for {cat}: Spent {currency}{spent:,.2f} / Limit {currency}{limit:,.2f}")
else:
    st.caption("No expenses this month yet.")

# ----------------------------
# Charts
# ----------------------------
st.subheader("📉 Visuals")

colA, colB = st.columns(2)

# Pie chart: total expenses by category (all time)
with colA:
    exp_df = st.session_state["transactions"]
    exp_df = exp_df[exp_df["Type"] == "Expense"].copy()
    if not exp_df.empty:
        pie_df = exp_df.groupby("Category", as_index=False)["Amount"].sum()
        pie = (
            alt.Chart(pie_df)
            .mark_arc()
            .encode(
                theta=alt.Theta(field="Amount", type="quantitative"),
                color=alt.Color(field="Category", type="nominal", legend=alt.Legend(title="Category")),
                tooltip=[alt.Tooltip("Category:N"), alt.Tooltip("Amount:Q", format=",.2f")]
            )
            .properties(title="Spending by Category (All Time)")
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        st.caption("No expense data yet for the pie chart.")

# Line chart: balance over time (cumulative)
with colB:
    df_sorted = st.session_state["transactions"].sort_values("Date").copy()
    if not df_sorted.empty:
        df_sorted["Delta"] = df_sorted.apply(lambda r: r["Amount"] if r["Type"] == "Income" else -r["Amount"], axis=1)
        df_sorted["Balance"] = df_sorted["Delta"].cumsum()
        line = (
            alt.Chart(df_sorted)
            .mark_line(point=True)
            .encode(
                x=alt.X("Date:T", title="Date"),
                y=alt.Y("Balance:Q", title=f"Balance ({currency})"),
                tooltip=[alt.Tooltip("Date:T", title="Date"), alt.Tooltip("Balance:Q", title="Balance", format=",.2f")]
            )
            .properties(title=f"Balance Over Time ({currency})")
        )
        st.altair_chart(line, use_container_width=True)
    else:
        st.caption("No transactions yet for the balance chart.")
