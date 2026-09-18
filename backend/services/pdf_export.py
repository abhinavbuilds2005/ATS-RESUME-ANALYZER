import io
import re
import logging
from typing import Dict

logger = logging.getLogger('ats_resume_scorer')

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_INSTALLED = True
except Exception:
    WEASYPRINT_INSTALLED = False

try:
    from xhtml2pdf import pisa
    XHTML2PDF_INSTALLED = True
except Exception:
    XHTML2PDF_INSTALLED = False

try:
    from pypdf import PdfWriter
    PYPDF_INSTALLED = True
except ImportError:
    try:
        from PyPDF2 import PdfWriter
        PYPDF_INSTALLED = True
    except Exception:
        PYPDF_INSTALLED = False


def _generate_reportlab_fallback(html_docs: Dict[str, str]) -> bytes:
    """Ultimate fallback using ReportLab to ensure PDF generation never fails."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas

        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        y = height - 50
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, y, "ATS Resume Analysis Report")
        y -= 25
        p.setFont("Helvetica-Oblique", 10)
        p.drawString(50, y, "AI-Powered ATS Resume Scorer & Optimization System")
        y -= 20
        p.setLineWidth(1)
        p.line(50, y, width - 50, y)
        y -= 25

        for name, html_str in html_docs.items():
            clean_text = re.sub(r'<style.*?</style>', '', html_str, flags=re.DOTALL)
            clean_text = re.sub(r'<[^>]+>', '\n', clean_text)
            lines = [line.strip() for line in clean_text.splitlines() if line.strip()]

            if y < 100:
                p.showPage()
                y = height - 50

            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, f"Section: {name.replace('_', ' ').title()}")
            y -= 20

            p.setFont("Helvetica", 9)
            for line in lines[:50]:
                if y < 50:
                    p.showPage()
                    p.setFont("Helvetica", 9)
                    y = height - 50
                p.drawString(50, y, line[:100])
                y -= 14
            y -= 15

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer.getvalue()
    except Exception as exc:
        logger.error(f"ReportLab fallback failed: {exc}", exc_info=True)
        raise


def generate_combined_pdf(html_docs: Dict[str, str]) -> bytes:
    """
    Generate a combined PDF report from multiple HTML documents.
    Tries WeasyPrint first, falls back to xhtml2pdf + pypdf, and finally ReportLab.
    """
    if not html_docs:
        raise ValueError("No HTML documents provided for PDF generation.")

    # 1. Try WeasyPrint
    if WEASYPRINT_INSTALLED:
        try:
            documents = []
            for name, html_str in html_docs.items():
                doc = HTML(string=html_str).render()
                documents.append(doc)

            if documents:
                first_doc = documents[0]
                for other_doc in documents[1:]:
                    for page in other_doc.pages:
                        first_doc.pages.append(page)
                pdf_bytes = first_doc.write_pdf()
                if pdf_bytes and len(pdf_bytes) > 500:
                    return pdf_bytes
        except Exception as exc:
            logger.warning(f"WeasyPrint rendering failed ({exc}), falling back to xhtml2pdf engine...")

    # 2. Try xhtml2pdf + pypdf
    if XHTML2PDF_INSTALLED and PYPDF_INSTALLED:
        try:
            writer = PdfWriter()
            for name, html_str in html_docs.items():
                try:
                    pdf_buffer = io.BytesIO()
                    pisa_status = pisa.CreatePDF(html_str, dest=pdf_buffer, encoding='utf-8')
                    if pdf_buffer.tell() > 0:
                        pdf_buffer.seek(0)
                        writer.append(pdf_buffer)
                    elif not pisa_status.err and pdf_buffer.tell() > 0:
                        pdf_buffer.seek(0)
                        writer.append(pdf_buffer)
                except Exception as doc_err:
                    logger.warning(f"xhtml2pdf failed on section '{name}': {doc_err}")

            if len(writer.pages) > 0:
                output_io = io.BytesIO()
                writer.write(output_io)
                result = output_io.getvalue()
                if len(result) > 500:
                    return result
        except Exception as exc:
            logger.warning(f"xhtml2pdf assembly failed ({exc}), trying ReportLab fallback...")

    # 3. Ultimate Fallback: ReportLab
    logger.info("Using ReportLab fallback for PDF generation...")
    return _generate_reportlab_fallback(html_docs)

