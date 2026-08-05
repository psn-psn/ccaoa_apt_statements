import base64
import io
import zipfile
import pandas as pd
import streamlit as st

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph
)
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import inch

# ----------------------------------------------------
# PDF Generator Logic
# ----------------------------------------------------

def generate_pdf(df, apartment):
    styles = getSampleStyleSheet()
    df = df.copy()

    df["Txn Date"] = pd.to_datetime(
        df["Txn Date"],
        dayfirst=True,
        errors="coerce"
    )

    df = df[
        df["Apartment Number"]
        .astype(str)
        .str.upper()
        == str(apartment).upper()
    ]

    df = df.sort_values("Txn Date")

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=(11.69 * inch, 8.27 * inch),
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch
    )

    rows = [[
        "Description",
        "Invoice Date",
        "Debits (₹)",
        "Payment Date",
        "Credits (₹)",
        "Balance (₹)"
    ]]

    balance = 0
    total_debit = 0
    total_credit = 0

    for _, r in df.iterrows():
        amount = abs(float(r["Amount"]))
        payment = (
            "payment" in str(r["Type"]).lower()
            or float(r["Amount"]) < 0
        )

        description = Paragraph(
            f"<b>{r['Description']}</b><br/>"
            f"<font size='7'>{r['Details']}</font>",
            styles["BodyText"]
        )

        txn_date = ""
        if pd.notna(r["Txn Date"]):
            txn_date = r["Txn Date"].strftime("%d-%b-%Y")

        if payment:
            invoice_date = ""
            payment_date = txn_date
            debit = ""
            credit = f"{amount:,.2f}"
            balance -= amount
            total_credit += amount
        else:
            invoice_date = txn_date
            payment_date = ""
            debit = f"{amount:,.2f}"
            credit = ""
            balance += amount
            total_debit += amount

        rows.append([
            description,
            invoice_date,
            debit,
            payment_date,
            credit,
            f"{balance:,.2f}"
        ])

    rows.append([
        Paragraph("<b>TOTAL</b>", styles["BodyText"]),
        "",
        f"{total_debit:,.2f}",
        "",
        f"{total_credit:,.2f}",
        f"{balance:,.2f}"
    ])

    table = Table(
        rows,
        colWidths=[
            4.2 * inch,
            1.0 * inch,
            0.9 * inch,
            1.0 * inch,
            0.9 * inch,
            1.0 * inch
        ],
        repeatRows=1
    )

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.beige),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("FONTSIZE", (0, 0), (-1, -1), 8)
    ]))

    story = [
        Paragraph("<b>Apartment Maintenance Statement</b>", styles["Title"]),
        Paragraph(f"Apartment : <b>{apartment}</b>", styles["Normal"]),
        table
    ]

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    return pdf


def create_batch_zip(df, apartments):
    """Generates PDFs for all apartments and packs them into a ZIP archive."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for apt in apartments:
            pdf_bytes = generate_pdf(df, apt)
            file_name = f"{apt}_Statement.pdf"
            zf.writestr(file_name, pdf_bytes)
    zip_buffer.seek(0)
    return zip_buffer.getvalue()


# ----------------------------------------------------
# Main Streamlit Application
# ----------------------------------------------------

st.set_page_config(
    page_title="Statement Generator",
    page_icon="🏢",
    layout="wide"
)

# Custom Styling for Compact View
st.markdown("""
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
        div[data-testid="stMetricValue"] { font-size: 1.15rem; }
        .stButton button, .stDownloadButton button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 Apartment Statement Generator")

# Control Bar: File Upload & Dropdown
c1, c2 = st.columns([2, 2])
with c1:
    uploaded_file = st.file_uploader("Upload CSV", type="csv")

df = None
apartment = None
apartments = []

if uploaded_file:
    df = pd.read_csv(uploaded_file)
    apartments = sorted(df["Apartment Number"].astype(str).unique())
    with c2:
        apartment = st.selectbox("Select Apartment", apartments)

st.markdown("---")

if uploaded_file and apartment:
    preview = df[
        df["Apartment Number"]
        .astype(str)
        .str.upper()
        == str(apartment).upper()
    ].copy()

    total_debits = preview[preview["Amount"] > 0]["Amount"].sum() if "Amount" in preview.columns else 0
    total_credits = abs(preview[preview["Amount"] < 0]["Amount"].sum()) if "Amount" in preview.columns else 0
    net_bal = total_debits - total_credits

    # Top Metric Bar
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected Flat", apartment)
    m2.metric("Total Debits", f"₹{total_debits:,.2f}")
    m3.metric("Total Credits", f"₹{total_credits:,.2f}")
    m4.metric("Net Balance", f"₹{net_bal:,.2f}")

    st.markdown("<br/>", unsafe_allow_html=True)

    # --- Dedicated Action Toolbar ---
    st.subheader("⚡ Actions & Exports")
    
    # 2-Row Action Grid ensuring visibility
    row1_col1, row1_col2 = st.columns([1, 1])
    
    with row1_col1:
        view_pdf = st.button("👁️ Open / Preview Current PDF", key="btn_view")
        if view_pdf:
            st.session_state["pdf_bytes"] = generate_pdf(df, apartment)
            st.session_state["pdf_apt"] = apartment

        if "pdf_bytes" in st.session_state and st.session_state.get("pdf_apt") == apartment:
            st.download_button(
                label=f"⬇️ Download PDF ({apartment})",
                data=st.session_state["pdf_bytes"],
                file_name=f"{apartment}_Statement.pdf",
                mime="application/pdf",
                type="primary",
                key="btn_dl"
            )

    with row1_col2:
        batch_pdf = st.button("📦 Batch Generate ALL PDFs (.ZIP)", key="btn_batch")
        
        if batch_pdf:
            with st.spinner(f"Generating PDF statements for all {len(apartments)} apartments..."):
                st.session_state["zip_bytes"] = create_batch_zip(df, apartments)
                st.toast("Batch generation complete!", icon="✅")

        if "zip_bytes" in st.session_state:
            st.download_button(
                label="⬇️ Download All Statements (.ZIP Archive)",
                data=st.session_state["zip_bytes"],
                file_name="All_Apartment_Statements.zip",
                mime="application/zip",
                type="primary",
                key="btn_zip_dl"
            )

    st.markdown("<br/>", unsafe_allow_html=True)

    # --- Embedded Viewer (Opens when 'View PDF' is clicked) ---
    if "pdf_bytes" in st.session_state and st.session_state.get("pdf_apt") == apartment:
        st.markdown("### 📄 Statement Preview")
        base64_pdf = base64.b64encode(st.session_state["pdf_bytes"]).decode('utf-8')
        pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="550" type="application/pdf"></iframe>'
        st.markdown(pdf_display, unsafe_allow_html=True)
        st.markdown("<br/>", unsafe_allow_html=True)

    # Data Table Preview
    st.subheader("📊 Transaction Log Preview")
    st.dataframe(
        preview,
        use_container_width=True,
        height=300,
        hide_index=True
    )

else:
    st.info("👆 Please upload an apartment CSV file above to proceed.")