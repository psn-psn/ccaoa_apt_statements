import base64
import glob
import io
import os
import re
import zipfile
import pandas as pd
import pypdfium2 as pdfium
from PIL import Image
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
# Helper Functions
# ----------------------------------------------------

def clean_code(code_str):
    """Strips whitespace and converts code to a clean string."""
    if pd.isna(code_str):
        return ""
    # Remove any decimal points if pandas read numerical codes as floats
    cleaned = str(code_str).split('.')[0].strip()
    return cleaned.zfill(4) if len(cleaned) <= 4 and cleaned.isdigit() else cleaned

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

def render_pdf_to_images(pdf_bytes):
    """Converts in-memory PDF bytes into PIL Images for previewing."""
    pdf_file = pdfium.PdfDocument(pdf_bytes)
    images = []
    for page in pdf_file:
        bitmap = page.render(scale=150 / 72)
        pil_image = bitmap.to_pil()
        images.append(pil_image)
    return images

# ----------------------------------------------------
# Main Streamlit Application
# ----------------------------------------------------

st.set_page_config(
    page_title="Chartered Coronet Apartment Maintenance Statements",
    page_icon="🏢",
    layout="wide"
)

# Custom Styling
st.markdown("""
    <style>
        .block-container { padding-top: 1.2rem; padding-bottom: 1rem; }
        div[data-testid="stMetricValue"] { font-size: 1.15rem; }
        .stButton button, .stDownloadButton button { width: 100%; }
    </style>
""", unsafe_allow_html=True)

st.title("Chartered Coronet Apartment Maintenance Statements")

# Auto-Detect Files
script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()

# Locate main transaction CSV (excluding mobile_code.csv)
all_csvs = glob.glob(os.path.join(script_dir, "*.csv"))
data_csvs = [f for f in all_csvs if os.path.basename(f) != "mobile_code.csv"]
code_csv_path = os.path.join(script_dir, "mobile_code.csv")

df = None
code_df = None
apartment = None
apartments = []

# Load data files behind the scenes
if data_csvs:
    loaded_file_path = data_csvs[0]
    df = pd.read_csv(loaded_file_path)
    apartments = sorted(df["Apartment Number"].astype(str).unique())
else:
    st.error("❌ Transaction CSV file not found in script directory.")

if os.path.exists(code_csv_path):
    code_df = pd.read_csv(code_csv_path, dtype=str)
else:
    st.error("❌ `mobile_code.csv` not found in script directory.")

# Controls Layout
c1, c2 = st.columns([1, 1])

with c1:
    if df is not None and apartments:
        apartment = st.selectbox("Select Apartment", apartments)

user_code = ""
with c2:
    if df is not None and apartment:
        user_code = st.text_input(
            "Enter 4-Digit Passcode",
            max_chars=4,
            type="password",
            placeholder="****"
        ).strip()

st.markdown("---")

# ----------------------------------------------------
# Verification & Access Gate
# ----------------------------------------------------

is_verified = False

if df is not None and apartment:
    if code_df is None:
        st.error("❌ Unable to verify code because `mobile_code.csv` is missing.")
    else:
        # Standardize column search in mobile_code.csv
        apt_col = None
        code_col = None

        for col in code_df.columns:
            col_lower = col.lower()
            if "apartment" in col_lower or "flat" in col_lower:
                apt_col = col
            elif "code" in col_lower or "passcode" in col_lower or "pin" in col_lower or "mobile" in col_lower:
                code_col = col

        # Fallback to 1st and 2nd columns if headers aren't explicitly named
        if not apt_col:
            apt_col = code_df.columns[0]
        if not code_col:
            code_col = code_df.columns[1] if len(code_df.columns) > 1 else code_df.columns[0]

        # Match selected apartment
        matched_row = code_df[
            code_df[apt_col].astype(str).str.upper() == str(apartment).upper()
        ]

        if not matched_row.empty:
            expected_code = clean_code(matched_row.iloc[0][code_col])
            clean_user_code = clean_code(user_code)

            if not user_code:
                st.info("🔒 Please enter your 4-digit code to verify access.")
            elif len(clean_user_code) != 4 or not clean_user_code.isdigit():
                st.warning("⚠️ Please enter a valid 4-digit numeric code.")
            elif clean_user_code == expected_code:
                st.success("✅ Code verified successfully!")
                is_verified = True
            else:
                st.error("❌ Incorrect 4-digit code for this apartment.")
        else:
            st.error(f"❌ No passcode mapping found for Apartment {apartment} in `mobile_code.csv`.")

# ----------------------------------------------------
# Content Display (Protected by Passcode)
# ----------------------------------------------------

if df is not None and apartment and is_verified:
    preview = df[
        df["Apartment Number"]
        .astype(str)
        .str.upper()
        == str(apartment).upper()
    ].copy()

    total_debits = preview[preview["Amount"] > 0]["Amount"].sum() if "Amount" in preview.columns else 0
    total_credits = abs(preview[preview["Amount"] < 0]["Amount"].sum()) if "Amount" in preview.columns else 0
    net_bal = total_debits - total_credits

    # Metrics Bar
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Selected Flat", apartment)
    m2.metric("Total Debits", f"₹{total_debits:,.2f}")
    m3.metric("Total Credits", f"₹{total_credits:,.2f}")
    m4.metric("Net Balance", f"₹{net_bal:,.2f}")

    st.markdown("<br/>", unsafe_allow_html=True)

    # Actions Toolbar
    st.subheader("⚡ Actions & Exports")
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
        st.button("📦 Batch Generate ALL PDFs (.ZIP) [Disabled]", key="btn_batch", disabled=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # PDF Image Render
    if "pdf_bytes" in st.session_state and st.session_state.get("pdf_apt") == apartment:
        st.markdown("### 📄 Statement Preview")
        try:
            images = render_pdf_to_images(st.session_state["pdf_bytes"])
            for idx, img in enumerate(images):
                st.image(img, caption=f"Page {idx + 1}", use_container_width=True)
        except Exception as e:
            st.error(f"Error rendering preview: {e}")
            
        st.markdown("<br/>", unsafe_allow_html=True)

    # Data Table Preview
    st.subheader("📊 Transaction Log Preview")
    st.dataframe(
        preview,
        use_container_width=True,
        height=300,
        hide_index=True
    )
