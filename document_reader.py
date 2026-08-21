"""
document_reader.py
-------------------
Utilities to extract raw text from uploaded documents (PDF, DOCX, TXT)
and split that text into overlapping chunks suitable for retrieval.
"""

import os
from PyPDF2 import PdfReader
import docx


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_supported(filename: str) -> bool:
    return get_extension(filename) in SUPPORTED_EXTENSIONS


def extract_text_from_pdf(filepath: str) -> str:
    text_parts = []
    reader = PdfReader(filepath)
    for page in reader.pages:
        page_text = page.extract_text() or ""
        text_parts.append(page_text)
    return "\n".join(text_parts)


def extract_text_from_docx(filepath: str) -> str:
    document = docx.Document(filepath)
    paragraphs = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_txt(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def extract_text(filepath: str) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = get_extension(filepath)
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    if ext == ".docx":
        return extract_text_from_docx(filepath)
    if ext == ".txt":
        return extract_text_from_txt(filepath)
    raise ValueError(f"Unsupported file type: {ext}")


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150):
    """
    Split text into overlapping chunks (by character count) so that
    each chunk is small enough to feed into the model's context window,
    while overlap preserves context that spans chunk boundaries.
    """
    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == text_len:
            break
        start = end - overlap  # step forward, keeping overlap

    return chunks
