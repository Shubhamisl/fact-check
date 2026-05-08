from io import BytesIO
import sys
from pathlib import Path

import fitz

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.pdf_service import extract_pdf_pages, find_pages_needing_ocr


def _make_pdf_with_text(page_texts: list[str]) -> BytesIO:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page()
        page.insert_text((72, 72), text)

    pdf_bytes = document.tobytes()
    document.close()

    return BytesIO(pdf_bytes)


def test_extract_pdf_pages_returns_page_text_with_pdf_source() -> None:
    pdf_file = _make_pdf_with_text(["First page text", "Second page text"])

    pages = extract_pdf_pages(pdf_file)

    assert [page.page_number for page in pages] == [1, 2]
    assert [page.text for page in pages] == ["First page text", "Second page text"]
    assert [page.source for page in pages] == ["pdf", "pdf"]


def test_find_pages_needing_ocr_returns_pages_below_min_chars() -> None:
    pdf_file = _make_pdf_with_text(["Short", "This page has enough searchable text."])
    pages = extract_pdf_pages(pdf_file)

    assert find_pages_needing_ocr(pages, min_chars=10) == [1]
