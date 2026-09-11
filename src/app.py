
import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st

try:
    import plotly.express as px  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover
    px = None

# ============================================================
# AI Invoice Control Tower
# Streamlit dashboard for the existing invoice-control pipeline
# ============================================================

st.set_page_config(
    page_title="AI Invoice Control Tower",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
DATA = ROOT / "data"

# ---------- Utilities ----------

def find_file(filename: str):
    candidates = [
        OUTPUTS / filename,
        DATA / filename,
        ROOT / filename,
        Path.cwd() / "outputs" / filename,
        Path.cwd() / "data" / filename,
        Path.cwd() / filename,
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


@st.cache_data(show_spinner=False)
def read_csv(path_str):
    return pd.read_csv(path_str)


@st.cache_data(show_spinner=False)
def load_data():
    files = {
        "ledger": find_file("invoice_risk_ledger.csv") or find_file("invoice_control_ledger.csv"),
        "match": find_file("invoice_match_ledger.csv"),
        "explanations": find_file("invoice_explanations.csv"),
        "risk_artifact": find_file("risk_model_artifact.json"),
        "vendors": find_file("vendors.csv"),
        "purchase_orders": find_file("purchase_orders.csv"),
        "goods_receipts": find_file("goods_receipts.csv"),
        "invoices": find_file("invoices.csv"),
        "payments": find_file("payments.csv"),
    }

    data = {}
    for key, path in files.items():
        if path and path.suffix.lower() == ".csv":
            data[key] = read_csv(str(path))
        elif path:
            data[key] = path
        else:
            data[key] = None

    # The control ledger is the preferred source for operational pages.
    # If it is absent, construct a lightweight fallback from the supplied
    # invoice + vendor + PO + receipt + payment data.
    if data["ledger"] is None and data["invoices"] is not None:
        data["ledger"] = build_fallback_ledger(data)

    return data


def build_fallback_ledger(data):
    """Fallback only: creates dashboard-friendly fields from raw CSVs.
    Replace this with outputs/invoice_control_ledger.csv for the full pipeline.
    """
    inv = data["invoices"].copy()
    po = data["purchase_orders"].copy() if data["purchase_orders"] is not None else None
    gr = data["goods_receipts"].copy() if data["goods_receipts"] is not None else None
    vendors = data["vendors"].copy() if data["vendors"] is not None else None
    pay = data["payments"].copy() if data["payments"] is not None else None

    if vendors is not None:
        inv = inv.merge(
            vendors[["vendor_id", "vendor_name", "category", "status"]],
            on="vendor_id", how="left", suffixes=("", "_master")
        )

    if po is not None:
        po_small = po[
            ["po_line_id", "po_id", "vendor_id", "item_id",
             "ordered_quantity", "unit_price", "tax_rate", "currency"]
        ].copy()
        po_small = po_small.rename(columns={
            "vendor_id": "po_vendor_id",
            "item_id": "po_item_id",
            "ordered_quantity": "ordered_qty",
            "unit_price": "po_unit_price",
            "tax_rate": "po_tax_rate",
            "currency": "po_currency",
        })
        inv = inv.merge(po_small, on="po_line_id", how="left", suffixes=("", "_po"))

    if gr is not None:
        receipt = (
            gr.groupby("po_line_id", dropna=False, as_index=False)["quantity_received"]
            .sum()
            .rename(columns={"quantity_received": "received_qty"})
        )
        inv = inv.merge(receipt, on="po_line_id", how="left")

    if pay is not None:
        payment = (
            pay.groupby("invoice_id", dropna=False)
            .agg(
                payment_status=("status", lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
                paid_amount=("payment_amount", "sum"),
                payment_date=("payment_date", "max"),
            )
            .reset_index()
        )
        inv = inv.merge(payment, on="invoice_id", how="left")

    inv["received_qty"] = inv.get("received_qty", 0).fillna(0)
    inv["ordered_qty"] = inv.get("ordered_qty", np.nan)
    inv["po_unit_price"] = inv.get("po_unit_price", np.nan)
    inv["po_tax_rate"] = inv.get("po_tax_rate", np.nan)

    inv["price_variance_pct"] = np.where(
        inv["po_unit_price"].notna() & (inv["po_unit_price"] != 0),
        (inv["unit_price"] - inv["po_unit_price"]) / inv["po_unit_price"] * 100,
        np.nan,
    )

    inv["quantity_over_receipt"] = inv["invoice_quantity"] - inv["received_qty"]
    inv["quantity_over_po"] = inv["invoice_quantity"] - inv["ordered_qty"]

    inv["po_exists"] = inv["po_line_id"].notna() & inv["po_unit_price"].notna()
    inv["vendor_match"] = (
        inv["po_vendor_id"].notna()
        & (inv["vendor_id"].astype(str) == inv["po_vendor_id"].astype(str))
    )
    inv["price_flag"] = inv["price_variance_pct"].abs() > 1
    inv["quantity_flag"] = (
        (inv["quantity_over_po"] > 0) | (inv["quantity_over_receipt"] > 0)
    )
    inv["hard_hold"] = (~inv["po_exists"]) | (~inv["vendor_match"])

    def decision(row):
        if row["hard_hold"]:
            return "HOLD"
        if row["price_flag"] or row["quantity_flag"]:
            return "HUMAN_REVIEW"
        return "AUTO_APPROVE"

    inv["decision"] = inv.apply(decision, axis=1)
    inv["risk_score"] = np.select(
        [inv["hard_hold"], inv["price_flag"] | inv["quantity_flag"]],
        [80, 35],
        default=10,
    )

    def flags(row):
        f = []
        if not row["po_exists"]:
            f.append("INVALID_PO")
        if not row["vendor_match"]:
            f.append("VENDOR_MISMATCH")
        if row["price_flag"]:
            f.append("PRICE_MISMATCH")
        if row["quantity_over_po"] > 0:
            f.append("ORDER_QUANTITY")
        if row["quantity_over_receipt"] > 0:
            f.append("RECEIPT_QUANTITY")
        return "|".join(f)

    inv["flags"] = inv.apply(flags, axis=1)
    return inv


def first_existing(df, names, default=None):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series(default, index=df.index)


def normalize_ledger(df):
    df = df.copy()

    # Common aliases from different pipeline implementations.
    aliases = {
        "invoice_id": ["invoice_id"],
        "vendor_id": ["vendor_id"],
        "vendor_name": ["vendor_name", "vendor_name_master", "vendor_name_raw"],
        "category": ["category"],
        "invoice_date": ["invoice_date"],
        "invoice_total": ["invoice_total", "line_total", "total"],
        "risk_score": ["risk_score", "score", "risk"],
        "decision": ["decision", "risk_decision", "route", "routing"],
        "flags": ["flags", "risk_flags", "exception_flags"],
        "hard_hold": ["hard_hold"],
        "po_id": ["po_id"],
        "po_line_id": ["po_line_id"],
        "invoice_quantity": ["invoice_quantity", "quantity"],
        "unit_price": ["unit_price", "invoice_unit_price"],
        "po_unit_price": ["po_unit_price", "po_price"],
        "received_qty": ["received_qty", "received_quantity", "quantity_received", "cumulative_received_qty"],
        "price_variance_pct": ["price_variance_pct", "price_variance"],
        "exception": ["exception", "synthetic_exception"],
        "exception_types": ["exception_types", "synthetic_exception_types"],
        "source_system": ["source_system"],
    }

    for target, candidates in aliases.items():
        if target not in df.columns:
            df[target] = first_existing(df, candidates, np.nan)

    for col in ["invoice_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    for col in [
        "invoice_total", "risk_score", "invoice_quantity", "unit_price",
        "po_unit_price", "received_qty", "price_variance_pct"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["decision"] = (
        df["decision"].astype(str).str.upper().str.replace(" ", "_", regex=False)
    )
    df["flags"] = df["flags"].fillna("").astype(str)
    df["vendor_name"] = df["vendor_name"].fillna(df["vendor_id"].astype(str))
    df["category"] = df["category"].fillna("Unknown")

    return df


def money(x):
    if pd.isna(x):
        return "—"
    x = float(x)
    if abs(x) >= 1e9:
        return f"₹{x/1e9:.2f}B"
    if abs(x) >= 1e6:
        return f"₹{x/1e6:.2f}M"
    if abs(x) >= 1e3:
        return f"₹{x/1e3:.1f}K"
    return f"₹{x:,.0f}"


def pct(x):
    return "—" if pd.isna(x) else f"{float(x):.1f}%"


def metric_card(label, value, help_text=None):
    st.metric(label, value, help=help_text)


def contains_flag(series, flag):
    return series.fillna("").astype(str).str.contains(flag, case=False, regex=False)


# ---------- Load ----------

data = load_data()
ledger = normalize_ledger(data["ledger"])

# Keep an original row-level copy for diagnostics.
raw_ledger = ledger.copy()

st.sidebar.title("🧾 AI Invoice Control Tower")
st.sidebar.caption("AP Operations & Risk Dashboard")

# ---------- Filters ----------

st.sidebar.subheader("Global Filters")

if ledger["invoice_date"].notna().any():
    min_date = ledger["invoice_date"].min().date()
    max_date = ledger["invoice_date"].max().date()
    selected_dates = st.sidebar.date_input(
        "Invoice date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )
    if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
        ledger = ledger[
            ledger["invoice_date"].dt.date.between(selected_dates[0], selected_dates[1])
        ]

vendors = sorted(ledger["vendor_name"].dropna().astype(str).unique())
selected_vendors = st.sidebar.multiselect("Vendor", vendors)

if selected_vendors:
    ledger = ledger[ledger["vendor_name"].isin(selected_vendors)]

categories = sorted(ledger["category"].dropna().astype(str).unique())
selected_categories = st.sidebar.multiselect("Category", categories)

if selected_categories:
    ledger = ledger[ledger["category"].isin(selected_categories)]

decisions = sorted(ledger["decision"].dropna().astype(str).unique())
selected_decisions = st.sidebar.multiselect("Decision", decisions)

if selected_decisions:
    ledger = ledger[ledger["decision"].isin(selected_decisions)]

if ledger.empty:
    st.warning("No invoices match the selected filters.")
    st.stop()

# ---------- Navigation ----------

pages = [
    "🏠 Executive Overview",
    "🚨 Exception Command Center",
    "🔎 Invoice Investigation",
    "🏢 Vendor Intelligence",
    "🤖 Automation Performance",
    "📊 Detection Analytics",
    "🧪 Model Evaluation",
]
page = st.sidebar.radio("Navigate", pages)

st.sidebar.divider()
st.sidebar.caption(f"{len(ledger):,} invoices in current view")

# ============================================================
# 1. Executive Overview
# ============================================================

if page == "🏠 Executive Overview":
    st.title("Executive Overview")
    st.caption("Operational view of invoice risk, routing, financial exposure and automation.")

    total = len(ledger)
    risk_count = int(ledger["decision"].isin(["HUMAN_REVIEW", "HOLD"]).sum())
    risk_value = ledger.loc[
        ledger["decision"].isin(["HUMAN_REVIEW", "HOLD"]), "invoice_total"
    ].sum()

    auto_count = int((ledger["decision"] == "AUTO_APPROVE").sum())
    hold_count = int((ledger["decision"] == "HOLD").sum())
    review_count = int((ledger["decision"] == "HUMAN_REVIEW").sum())

    cols = st.columns(4)
    with cols[0]:
        metric_card("Invoices", f"{total:,}")
    with cols[1]:
        metric_card("Auto-approve", f"{auto_count:,}", pct(auto_count / total * 100))
    with cols[2]:
        metric_card("Human review", f"{review_count:,}")
    with cols[3]:
        metric_card("Hold", f"{hold_count:,}")

    cols = st.columns(2)
    with cols[0]:
        metric_card("Exception / risk value", money(risk_value))
    with cols[1]:
        metric_card("Touchless rate", pct(auto_count / total * 100))

    st.subheader("Routing distribution")
    route_counts = ledger["decision"].value_counts().rename_axis("decision").reset_index(name="count")
    fig = px.bar(route_counts, x="decision", y="count", text="count", title="")
    fig.update_layout(xaxis_title="", yaxis_title="Invoices")
    st.plotly_chart(fig, use_container_width=True)

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Risk by invoice value")
        plot_df = ledger.copy()
        plot_df["invoice_total"] = plot_df["invoice_total"].fillna(0)
        fig = px.scatter(
            plot_df,
            x="invoice_total",
            y="risk_score",
            color="decision",
            hover_data=["invoice_id", "vendor_name", "flags"],
            log_x=True,
            title="Invoice value vs risk score",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.subheader("Top vendors by risk value")
        vendor_risk = (
            ledger[ledger["decision"].isin(["HUMAN_REVIEW", "HOLD"])]
            .groupby("vendor_name", as_index=False)["invoice_total"]
            .sum()
            .sort_values("invoice_total", ascending=False)
            .head(10)
        )
        fig = px.bar(
            vendor_risk.sort_values("invoice_total"),
            x="invoice_total",
            y="vendor_name",
            orientation="h",
            title="",
        )
        fig.update_xaxes(tickprefix="₹", separatethousands=True)
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 2. Exception Command Center
# ============================================================

elif page == "🚨 Exception Command Center":
    st.title("Exception Command Center")
    st.caption("Prioritize the invoices that require human attention.")

    exceptions = ledger[ledger["decision"].isin(["HUMAN_REVIEW", "HOLD"])].copy()

    if exceptions.empty:
        st.success("No exceptions in the current filter.")
        st.stop()

    a, b, c = st.columns(3)
    with a:
        metric_card("Exceptions", f"{len(exceptions):,}")
    with b:
        metric_card("Financial exposure", money(exceptions["invoice_total"].sum()))
    with c:
        metric_card("Average risk", f"{exceptions['risk_score'].mean():.1f}")

    sort_by = st.selectbox(
        "Prioritize by",
        ["Risk score", "Invoice value", "Risk × Value"],
    )

    exceptions["risk_value"] = exceptions["risk_score"].fillna(0) * exceptions["invoice_total"].fillna(0)

    if sort_by == "Risk score":
        exceptions = exceptions.sort_values("risk_score", ascending=False)
    elif sort_by == "Invoice value":
        exceptions = exceptions.sort_values("invoice_total", ascending=False)
    else:
        exceptions = exceptions.sort_values("risk_value", ascending=False)

    display_cols = [
        c for c in [
            "invoice_id", "vendor_name", "category", "invoice_total",
            "risk_score", "decision", "flags", "po_id", "invoice_date"
        ] if c in exceptions.columns
    ]

    st.dataframe(
        exceptions[display_cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "invoice_total": st.column_config.NumberColumn("Invoice Value", format="₹%,.2f"),
            "risk_score": st.column_config.ProgressColumn(
                "Risk", min_value=0, max_value=100, format="%d"
            ),
            "invoice_date": st.column_config.DateColumn("Invoice Date"),
        },
    )

    st.subheader("Exception flags")
    flag_counts = {}
    for flags in exceptions["flags"].dropna():
        for flag in [x.strip() for x in str(flags).split("|") if x.strip()]:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    if flag_counts:
        flag_df = (
            pd.DataFrame(list(flag_counts.items()), columns=["flag", "count"])
            .sort_values("count", ascending=False)
        )
        fig = px.bar(flag_df, x="count", y="flag", orientation="h", text="count")
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 3. Invoice Investigation
# ============================================================

elif page == "🔎 Invoice Investigation":
    st.title("Invoice Investigation")
    st.caption("Evidence-first view for AP analyst review.")

    invoice_ids = sorted(ledger["invoice_id"].dropna().astype(str).unique())
    selected_invoice = st.selectbox("Select invoice", invoice_ids)

    row = ledger[ledger["invoice_id"].astype(str) == selected_invoice].iloc[0]

    st.subheader(f"Invoice {selected_invoice}")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Vendor", str(row["vendor_name"]))
    with c2:
        metric_card("Invoice value", money(row["invoice_total"]))
    with c3:
        metric_card("Risk score", f"{row['risk_score']:.0f}" if pd.notna(row["risk_score"]) else "—")
    with c4:
        metric_card("Decision", str(row["decision"]))

    st.divider()

    left, right = st.columns(2)

    with left:
        st.subheader("Invoice evidence")
        evidence = {
            "Invoice ID": row.get("invoice_id"),
            "Vendor": row.get("vendor_name"),
            "Vendor ID": row.get("vendor_id"),
            "PO ID": row.get("po_id"),
            "PO Line": row.get("po_line_id"),
            "Invoice date": row.get("invoice_date"),
            "Invoice quantity": row.get("invoice_quantity"),
            "Invoice unit price": row.get("unit_price"),
            "Invoice total": row.get("invoice_total"),
            "Source system": row.get("source_system"),
        }
        ev = pd.DataFrame(
            [(k, v) for k, v in evidence.items()],
            columns=["Field", "Value"],
        )
        st.dataframe(ev, use_container_width=True, hide_index=True)

    with right:
        st.subheader("Control evidence")
        controls = []

        flag_text = str(row.get("flags", ""))
        controls.append(("Hard hold", "FAIL" if bool(row.get("hard_hold", False)) else "PASS"))
        controls.append(("PO reference", "FAIL" if "PO" in flag_text.upper() or "INVALID_PO" in flag_text.upper() else "PASS"))
        controls.append(("Vendor match", "FAIL" if "VENDOR" in flag_text.upper() else "PASS"))
        controls.append(("Price tolerance", "FAIL" if "PRICE" in flag_text.upper() else "PASS"))
        controls.append(("Quantity", "FAIL" if "QUANTITY" in flag_text.upper() else "PASS"))
        controls.append(("Duplicate candidate", "FAIL" if "DUPLICATE" in flag_text.upper() else "PASS"))

        control_df = pd.DataFrame(controls, columns=["Control", "Result"])
        st.dataframe(
            control_df,
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Why this invoice was routed")

    if data["explanations"] is not None:
        expl = data["explanations"]
        match_cols = [c for c in ["invoice_id", "decision_summary", "reasons", "recommended_action"] if c in expl.columns]
        if "invoice_id" in match_cols:
            selected_expl = expl[expl["invoice_id"].astype(str) == selected_invoice]
            if not selected_expl.empty:
                st.dataframe(selected_expl[match_cols], use_container_width=True, hide_index=True)

    if flag_text:
        st.warning(f"Flags: {flag_text}")
    else:
        st.success("No recorded exception flags.")

    if row.get("price_variance_pct", np.nan) is not None and pd.notna(row.get("price_variance_pct", np.nan)):
        st.write(f"**Price variance:** {row['price_variance_pct']:.2f}%")

    if pd.notna(row.get("invoice_quantity", np.nan)) and pd.notna(row.get("received_qty", np.nan)):
        st.write(
            f"**Quantity comparison:** invoiced {row['invoice_quantity']:,.2f} vs "
            f"received {row['received_qty']:,.2f}"
        )

# ============================================================
# 4. Vendor Intelligence
# ============================================================

elif page == "🏢 Vendor Intelligence":
    st.title("Vendor Intelligence")
    st.caption("Vendor-level invoice volume, risk and exception patterns.")

    vendor_summary = (
        ledger.groupby(["vendor_id", "vendor_name"], dropna=False)
        .agg(
            invoices=("invoice_id", "nunique"),
            invoice_value=("invoice_total", "sum"),
            avg_risk=("risk_score", "mean"),
            exceptions=("decision", lambda s: s.isin(["HUMAN_REVIEW", "HOLD"]).sum()),
            holds=("decision", lambda s: (s == "HOLD").sum()),
        )
        .reset_index()
    )
    vendor_summary["exception_rate"] = vendor_summary["exceptions"] / vendor_summary["invoices"] * 100

    c1, c2 = st.columns(2)

    with c1:
        top = vendor_summary.sort_values("invoice_value", ascending=False).head(15)
        fig = px.bar(
            top.sort_values("invoice_value"),
            x="invoice_value",
            y="vendor_name",
            orientation="h",
            title="Top vendors by invoice value",
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        top_risk = vendor_summary.sort_values("exception_rate", ascending=False).head(15)
        fig = px.bar(
            top_risk.sort_values("exception_rate"),
            x="exception_rate",
            y="vendor_name",
            orientation="h",
            title="Highest observed exception rates",
        )
        fig.update_xaxes(title="Exception rate (%)")
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("Vendor scorecard")
    st.dataframe(
        vendor_summary.sort_values("invoice_value", ascending=False),
        use_container_width=True,
        hide_index=True,
        column_config={
            "invoice_value": st.column_config.NumberColumn("Invoice Value", format="₹%,.2f"),
            "avg_risk": st.column_config.NumberColumn("Avg Risk", format="%.1f"),
            "exception_rate": st.column_config.NumberColumn("Exception Rate", format="%.1f%%"),
        },
    )

# ============================================================
# 5. Automation Performance
# ============================================================

elif page == "🤖 Automation Performance":
    st.title("Automation Performance")
    st.caption("Measures whether the control system is reducing manual AP workload safely.")

    total = len(ledger)
    auto = int((ledger["decision"] == "AUTO_APPROVE").sum())
    review = int((ledger["decision"] == "HUMAN_REVIEW").sum())
    hold = int((ledger["decision"] == "HOLD").sum())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Touchless rate", pct(auto / total * 100))
    with c2:
        metric_card("Human review rate", pct(review / total * 100))
    with c3:
        metric_card("Hold rate", pct(hold / total * 100))
    with c4:
        metric_card("Manual workload", f"{review + hold:,}")

    st.subheader("Routing volume")
    routing = ledger["decision"].value_counts().rename_axis("decision").reset_index(name="invoices")
    fig = px.pie(routing, names="decision", values="invoices", hole=0.45)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Potential workload reduction")
    st.info(
        f"If AUTO_APPROVE represents genuinely safe touchless processing, "
        f"the current prototype routes {auto:,} of {total:,} invoices without "
        f"an analyst review ({auto/total:.1%}). This is a synthetic-data prototype "
        f"metric, not a production performance claim."
    )

    if ledger["invoice_date"].notna().any():
        trend = (
            ledger.assign(month=ledger["invoice_date"].dt.to_period("M").astype(str))
            .groupby(["month", "decision"], as_index=False)
            .size()
            .rename(columns={"size": "invoices"})
        )
        fig = px.line(
            trend,
            x="month",
            y="invoices",
            color="decision",
            markers=True,
            title="Routing trend",
        )
        st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 6. Detection Analytics
# ============================================================

elif page == "📊 Detection Analytics":
    st.title("Detection Analytics")
    st.caption("Which controls and anomaly signals are driving intervention?")

    flag_counts = {}
    flag_values = {}

    for _, row in ledger.iterrows():
        flags = [x.strip() for x in str(row.get("flags", "")).split("|") if x.strip()]
        for flag in flags:
            flag_counts[flag] = flag_counts.get(flag, 0) + 1
            flag_values[flag] = flag_values.get(flag, 0) + (row["invoice_total"] if pd.notna(row["invoice_total"]) else 0)

    if flag_counts:
        flag_df = pd.DataFrame({
            "flag": list(flag_counts.keys()),
            "invoice_count": list(flag_counts.values()),
        })
        flag_df["invoice_value"] = flag_df["flag"].map(flag_values)

        c1, c2 = st.columns(2)
        with c1:
            fig = px.bar(
                flag_df.sort_values("invoice_count"),
                x="invoice_count",
                y="flag",
                orientation="h",
                text="invoice_count",
                title="Detection volume",
            )
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            fig = px.bar(
                flag_df.sort_values("invoice_value"),
                x="invoice_value",
                y="flag",
                orientation="h",
                text="invoice_value",
                title="Invoice value associated with flags",
            )
            st.plotly_chart(fig, use_container_width=True)

        st.dataframe(
            flag_df.sort_values("invoice_count", ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "invoice_value": st.column_config.NumberColumn("Invoice Value", format="₹%,.2f")
            },
        )
    else:
        st.success("No flags found in the current ledger.")

    st.subheader("Risk distribution")
    fig = px.histogram(
        ledger,
        x="risk_score",
        nbins=20,
        color="decision",
        title="Risk score distribution",
    )
    st.plotly_chart(fig, use_container_width=True)

# ============================================================
# 7. Model Evaluation
# ============================================================

elif page == "🧪 Model Evaluation":
    st.title("Model Evaluation")
    st.caption("Development-only evaluation against the synthetic ground truth.")

    if "exception" not in ledger.columns or ledger["exception"].isna().all():
        st.warning(
            "No synthetic exception label is available in the current operational ledger. "
            "This page requires the evaluation label to calculate model metrics."
        )
        st.stop()

    y_true = pd.to_numeric(ledger["exception"], errors="coerce")
    y_pred = ledger["decision"].isin(["HUMAN_REVIEW", "HOLD"]).astype(int)

    valid = y_true.notna()
    y_true = y_true[valid].astype(int)
    y_pred = y_pred[valid]

    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        metric_card("Precision", pct(precision * 100))
    with c2:
        metric_card("Recall", pct(recall * 100))
    with c3:
        metric_card("F1", f"{f1:.3f}")

    cm = pd.DataFrame(
        [[tn, fp], [fn, tp]],
        index=["Actual Clean", "Actual Exception"],
        columns=["Predicted Clean", "Predicted Exception"],
    )

    st.subheader("Confusion matrix")
    st.dataframe(cm, use_container_width=False)

    st.subheader("Interpretation")
    st.write(
        "The evaluation label is synthetic ground truth. These metrics are useful for "
        "testing the prototype's control coverage, but they should not be presented as "
        "production model performance."
    )

    st.warning(
        "Do not use `exception` or `exception_types` as predictive features. "
        "The risk model design explicitly excludes them."
    )

# ---------- Footer ----------

st.sidebar.divider()
st.sidebar.caption(
    "Prototype • Safety-first routing • Deterministic controls + ML risk + grounded explanations"
)
