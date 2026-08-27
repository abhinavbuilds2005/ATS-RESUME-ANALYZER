import io
import logging
from typing import Dict

logger = logging.getLogger('ats_resume_scorer')

try:
    from weasyprint import HTML, CSS
    WEASYPRINT_INSTALLED = True
except (ImportError, OSError):
    WEASYPRINT_INSTALLED = False

try:
    from xhtml2pdf import pisa
    XHTML2PDF_INSTALLED = True
except ImportError:
    XHTML2PDF_INSTALLED = False

try:
    from pypdf import PdfWriter
    PYPDF_INSTALLED = True
except ImportError:
    try:
        from PyPDF2 import PdfWriter
        PYPDF_INSTALLED = True
    except ImportError:
        PYPDF_INSTALLED = False



def generate_combined_pdf(html_docs: Dict[str, str]) -> bytes:
    """
    Generate a combined PDF report from multiple HTML documents.
    Tries WeasyPrint first, then falls back to xhtml2pdf + pypdf for Windows/cross-platform compatibility.
    """
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
                return first_doc.write_pdf()
        except Exception as exc:
            logger.warning(f"WeasyPrint rendering failed ({exc}), falling back to xhtml2pdf engine...")

    if XHTML2PDF_INSTALLED and PYPDF_INSTALLED:
        writer = PdfWriter()
        for name, html_str in html_docs.items():
            pdf_buffer = io.BytesIO()
            pisa_status = pisa.CreatePDF(html_str, dest=pdf_buffer)
            if not pisa_status.err and pdf_buffer.tell() > 0:
                pdf_buffer.seek(0)
                writer.append(pdf_buffer)

        output_io = io.BytesIO()
        writer.write(output_io)
        return output_io.getvalue()

    raise RuntimeError("No working PDF generator engine found (WeasyPrint or xhtml2pdf).")
