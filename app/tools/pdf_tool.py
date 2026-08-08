"""
Extracts text from PDF documents the user uploads (annual reports,
earnings statements, etc.) so the AI can answer questions about them.
Uses pdfplumber, which handles real-world PDF layouts better than
simpler extractors.
"""

import io
import pdfplumber

MAX_CHARS = 8000


def extract_pdf_text(file_bytes: bytes) -> str:
    """
    Extracts text from a PDF's pages, up to MAX_CHARS. Returns an
    empty-ish string (caller should check length) if nothing could
    be extracted - e.g. a scanned PDF with no text layer.
    """
    text_parts = []
    total_len = 0

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
            total_len += len(page_text)
            if total_len >= MAX_CHARS:
                break

    full_text = "\n".join(text_parts).strip()

    if len(full_text) > MAX_CHARS:
        full_text = full_text[:MAX_CHARS] + "\n\n[Document truncated - only the first part was read.]"

    return full_text