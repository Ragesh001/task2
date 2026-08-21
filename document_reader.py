"""
document_reader.py
-------------------
Utilities to extract raw text from uploaded documents (PDF, DOCX, TXT)
and split that text into overlapping chunks suitable for retrieval.

PDF extraction uses a multi-fallback strategy for maximum compatibility:
  1. pdfplumber  — best for native/digital PDFs with complex layouts
  2. PyMuPDF (fitz) — fast and robust, handles most PDFs
  3. PyPDF2       — legacy fallback
"""

import os
import warnings

from PyPDF2 import PdfReader
import docx


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def is_supported(filename: str) -> bool:
    return get_extension(filename) in SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# PDF extraction – multi-fallback for maximum compatibility
# ---------------------------------------------------------------------------

def _extract_pdf_pdfplumber(filepath: str) -> str:
    """Best for digital/native PDFs. Handles complex column layouts well."""
    try:
        import pdfplumber  # type: ignore
        text_parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except ImportError:
        return ""
    except Exception:  # noqa: BLE001
        return ""


def _extract_pdf_pymupdf(filepath: str) -> str:
    """Fast and robust. Works on most PDFs including those with unusual encodings."""
    try:
        import fitz  # PyMuPDF  # type: ignore
        doc = fitz.open(filepath)
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        doc.close()
        return "\n".join(text_parts)
    except ImportError:
        return ""
    except Exception:  # noqa: BLE001
        return ""


def _extract_pdf_pypdf2(filepath: str) -> str:
    """Legacy fallback. May struggle with some encodings."""
    try:
        text_parts = []
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            reader = PdfReader(filepath)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text_parts.append(page_text)
        return "\n".join(text_parts)
    except Exception:  # noqa: BLE001
        return ""


def extract_text_from_pdf(filepath: str) -> str:
    """
    Try each PDF extractor in order of quality.
    Use whichever returns the most text.
    """
    results = {}

    text = _extract_pdf_pdfplumber(filepath)
    if text.strip():
        results["pdfplumber"] = text

    text = _extract_pdf_pymupdf(filepath)
    if text.strip():
        results["pymupdf"] = text

    text = _extract_pdf_pypdf2(filepath)
    if text.strip():
        results["pypdf2"] = text

    if not results:
        return ""

    # Pick the result with the most extracted text (most complete)
    best_method = max(results, key=lambda k: len(results[k]))
    print(
        f"[document_reader] PDF extraction methods tried: {list(results.keys())}. "
        f"Using '{best_method}' ({len(results[best_method])} chars).",
        flush=True,
    )
    return results[best_method]


# ---------------------------------------------------------------------------
# DOCX / TXT
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200):
    """
    Split text into overlapping chunks (by character count) so that
    each chunk is small enough to feed into the model's context window,
    while overlap preserves context that spans chunk boundaries.

    chunk_size increased to 1200 (from 800) to give more context per chunk.
    overlap increased to 200 (from 150) to better preserve cross-boundary info.
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
