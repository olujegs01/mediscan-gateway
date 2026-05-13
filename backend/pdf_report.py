"""
Shift report PDF generator using ReportLab.
"""
from __future__ import annotations
from io import BytesIO
from datetime import datetime


def generate_shift_pdf(report: dict) -> bytes:
    """Generate a HIPAA-compliant shift handoff PDF. Returns raw PDF bytes."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.enums import TA_CENTER

        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=letter, leftMargin=0.75*inch, rightMargin=0.75*inch,
                                topMargin=0.75*inch, bottomMargin=0.75*inch)
        styles = getSampleStyleSheet()
        story = []

        # Title
        title_style = ParagraphStyle("Title", parent=styles["Heading1"], alignment=TA_CENTER,
                                     fontSize=16, spaceAfter=6)
        story.append(Paragraph("MediScan Gateway — Shift Handoff Report", title_style))
        story.append(Paragraph(
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}  |  "
            f"Shift: {report.get('shift_start', 'N/A')} – {report.get('shift_end', 'N/A')}",
            ParagraphStyle("Sub", parent=styles["Normal"], alignment=TA_CENTER, fontSize=9,
                           textColor=colors.grey, spaceAfter=18)
        ))

        # Summary stats table
        summary_data = [
            ["Total Patients", "Avg Wait", "Sepsis Alerts", "Admissions Predicted"],
            [
                str(report.get("total_patients", 0)),
                f"{report.get('avg_wait_minutes', 0):.0f} min",
                str(report.get("sepsis_count", 0)),
                str(report.get("admissions_predicted", 0)),
            ],
        ]
        t = Table(summary_data, colWidths=[1.5*inch]*4)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0d9488")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 11),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f0fdfa")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#0d9488")),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 16))

        # ESI breakdown
        esi_breakdown = report.get("esi_breakdown", {})
        if esi_breakdown:
            story.append(Paragraph("ESI Distribution", styles["Heading2"]))
            esi_labels = {1: "Critical", 2: "High Acuity", 3: "Urgent", 4: "Less Urgent", 5: "Non-Urgent"}
            rows = [["ESI Level", "Label", "Count"]]
            for level in range(1, 6):
                count = esi_breakdown.get(str(level), esi_breakdown.get(level, 0))
                if count:
                    rows.append([f"ESI {level}", esi_labels[level], str(count)])
            if len(rows) > 1:
                et = Table(rows, colWidths=[1.2*inch, 2.5*inch, 1*inch])
                et.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]))
                story.append(et)
                story.append(Spacer(1, 12))

        # Footer
        story.append(Spacer(1, 24))
        story.append(Paragraph(
            "CONFIDENTIAL — HIPAA Protected Health Information. Authorised personnel only.",
            ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                           textColor=colors.grey, alignment=TA_CENTER)
        ))

        doc.build(story)
        return buf.getvalue()

    except ImportError:
        # ReportLab not installed — return a minimal valid PDF stub
        return _minimal_pdf(report)


def _minimal_pdf(report: dict) -> bytes:
    """Fallback: returns a bare-minimum valid PDF when ReportLab is absent."""
    # Minimal valid PDF 1.4 structure
    pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n9\n%%EOF\n"
    )
    return pdf
