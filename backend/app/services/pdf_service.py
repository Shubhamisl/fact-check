from typing import BinaryIO

from pypdf import PdfReader

from app.models import PageText


def extract_pdf_pages(file_obj: BinaryIO) -> list[PageText]:
    reader = PdfReader(file_obj)

    return [
        PageText(
            page_number=page_index,
            text=(page.extract_text() or "").strip(),
            source="pdf",
        )
        for page_index, page in enumerate(reader.pages, start=1)
    ]


def find_pages_needing_ocr(pages: list[PageText], min_chars: int = 40) -> list[int]:
    return [
        page.page_number
        for page in pages
        if len(page.text.strip()) < min_chars
    ]
