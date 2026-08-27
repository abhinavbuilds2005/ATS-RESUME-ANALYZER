import pytest
from backend.services.resume_parser import (
    validate_file,
    extract_text,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_doc,
    parse_resume_file,
    FileValidationError,
    FileParsingError,
)

def test_validate_file_valid_pdf(sample_pdf_bytes):
    is_valid, msg, file_type = validate_file(sample_pdf_bytes, "resume.pdf")
    assert is_valid is True
    assert file_type == "pdf"
    assert msg == ""

def test_validate_file_valid_docx(sample_docx_bytes):
    is_valid, msg, file_type = validate_file(sample_docx_bytes, "resume.docx")
    assert is_valid is True
    assert file_type == "docx"
    assert msg == ""

def test_validate_file_empty():
    is_valid, msg, file_type = validate_file(b"", "empty.pdf")
    assert is_valid is False
    assert "empty" in msg.lower()
    assert file_type is None

def test_validate_file_oversized():
    large_bytes = b"%PDF-" + b"0" * (6 * 1024 * 1024)
    is_valid, msg, file_type = validate_file(large_bytes, "large.pdf")
    assert is_valid is False
    assert "exceeds" in msg.lower()

def test_validate_file_invalid_signature():
    fake_pdf = b"NOT_A_PDF_FILE_HEADER"
    is_valid, msg, file_type = validate_file(fake_pdf, "fake.pdf")
    assert is_valid is False
    assert "unsupported" in msg.lower() or "invalid" in msg.lower()

def test_validate_file_legacy_doc_rejection():
    fake_doc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    is_valid, msg, file_type = validate_file(fake_doc, "resume.doc")
    assert is_valid is False
    assert ".doc" in msg.lower()

def test_extract_text_pdf(sample_pdf_bytes):
    text = extract_text_from_pdf(sample_pdf_bytes)
    assert len(text) > 0
    assert "John Doe" in text
    assert "FastAPI" in text

def test_extract_text_docx(sample_docx_bytes):
    text = extract_text_from_docx(sample_docx_bytes)
    assert len(text) > 0
    assert "Jane Smith" in text
    assert "CloudTech" in text

def test_extract_text_doc_raises_error():
    with pytest.raises(FileParsingError) as exc_info:
        extract_text_from_doc(b"dummy")
    assert "legacy .doc format is not supported" in str(exc_info.value).lower()

def test_parse_resume_file_success(sample_pdf_bytes):
    text, metadata = parse_resume_file(sample_pdf_bytes, "my_resume.pdf")
    assert metadata["success"] is True
    assert metadata["file_type"] == "pdf"
    assert metadata["filename"] == "my_resume.pdf"
    assert len(text) > 50

def test_parse_resume_file_invalid():
    with pytest.raises(FileValidationError):
        parse_resume_file(b"bad content", "corrupt.pdf")
