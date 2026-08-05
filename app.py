import io
import pandas as pd
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.lib.units import inch

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
        pagesize=A4,
        leftMargin=0.35 * inch,
        rightMargin=0.35 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.5 * inch
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
        alignment=TA_LEFT,
        spaceAfter=10
    )

    legend_text_style = ParagraphStyle(
        'LegendText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        spaceAfter=2,
        textColor=colors.black
    )

    today_str = datetime.now().strftime("%d-%b-%Y")

    legend_lines = [
        "MNQ1: Maintenance Q1",
        "MNQ2: Maintenance Q2",
        "MNQ3: Maintenance Q3",
        "MNQ4: Maintenance Q4",
        "IMP: Imprest",
        "SP0: Special Collection 40000",
        "SP1: Special Collection Installment 1",
        "SP2: Special Collection Installment 2",
        "SP3: Special Collection Installment 3",
        "SP4: Special Collection Installment 4",
        "CFW: Carry Forward",
        "LTF: Late Fee"
    ]

    story = [
        Paragraph(f"<b>CCAOA Maintenance Statement for Apartment : {apartment}</b>", styles["Title"]),
        Paragraph(f"Report Date: <b>{today_str}</b>", report_date_style),
        table,
        Spacer(1, 10)
    ]

    # Append each line as plain text paragraph
    for line in legend_lines:
        story.append(Paragraph(line, legend_text_style))

    def draw_footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#555555"))
        footer_text = "ccaoa1@gmail.com | WhatsApp: Chartered Coronet Apt Owners"
        canvas.drawString(0.35 * inch, 0.25 * inch, footer_text)
        canvas.restoreState()

    doc.build(
        story,
        onFirstPage=draw_footer,
        onLaterPages=draw_footer
    )

    pdf = buffer.getvalue()
    buffer.close()

    return pdf
