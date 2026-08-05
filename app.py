import io
import os
import glob
import pandas as pd
import streamlit as st
from datetime import datetime
from reportlab.lib.pagesizes import A4
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
    cleaned = str(code_str).split('.')[0].strip()
    return cleaned.zfill(4) if len(cleaned) <= 4 and cleaned.isdigit() else cleaned

# ----------------------------------------------------
# PDF Generator Logic (A4 Portrait)
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

    # Configured explicitly for A4 Portrait
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
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

    # Adjusted column widths to sum up within standard A4 printable area (~7.57 inches)
    table = Table(
        rows,
        colWidths=[
            2.27 * inch,
            1.05 * inch,
            1.05 * inch,
            1.05 * inch,
            1.05 * inch,
            1.10 * inch
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
   report_date_style = ParagraphStyle(
    'ReportDateStyle',
    parent=styles['Normal'],
    fontName='Helvetica',
    fontSize=9,
    alignment=TA_LEFT,  # Or alignment=0
    spaceAfter=10
)

# 2. Format Date String
today_str = datetime.now().strftime("%d-%b-%Y")

# 3. Construct Flowables List
story = [
    Paragraph(f"<b>CCAOA Maintenance Statement for Apartment : {apartment}</b>", styles["Title"]),
    Paragraph(f"Report Date: <b>{today_str}</b>", report_date_style),
    table
]
    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()

    return pdf

# ----------------------------------------------------
# Main Streamlit Application
# ----------------------------------------------------

st.set_page_config(
    page_title="CCAOA Maintenance",
    page_icon="🏢",
    layout="wide"
)

# Custom Styling
st.markdown("""
    <style>
        .block-container { 
            padding-top: 2rem; 
            padding-bottom: 1rem; 
        }
        h1 {
            font-size: 1.6rem !important;
            line-height: 1.4 !important;
            padding-top: 0.5rem !important;
            padding-bottom: 0.5rem !important;
            margin: 0 !important;
            overflow: visible !important;
        }
        .stButton button, .stDownloadButton button { 
            width: 100%; 
        }
    </style>
""", unsafe_allow_html=True)

st.title("🏢 CCAOA Maintenance")

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
# Direct PDF Generation & Download
# ----------------------------------------------------

if df is not None and apartment and is_verified:
    pdf_bytes = generate_pdf(df, apartment)

    st.markdown("<br/>", unsafe_allow_html=True)
    st.download_button(
        label=f"⬇️ Download PDF Statement ({apartment})",
        data=pdf_bytes,
        file_name=f"{apartment}_Statement.pdf",
        mime="application/pdf",
        type="primary",
        key="btn_dl"
    )
