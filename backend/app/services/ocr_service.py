import fitz

from app.config import get_settings
from app.models import PageText
from app.services.openrouter_client import OpenRouterClient


class OcrService:
    def __init__(
        self,
        client: OpenRouterClient | None = None,
        max_pages: int | None = None,
    ) -> None:
        settings = get_settings()
        self.client = client or OpenRouterClient()
        self.max_pages = max_pages or settings.max_ocr_pages

    async def extract_pages(
        self,
        pdf_bytes: bytes,
        page_numbers: list[int],
    ) -> list[PageText]:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        try:
            pages: list[PageText] = []
            for page_number in page_numbers[: self.max_pages]:
                if page_number < 1 or page_number > doc.page_count:
                    continue

                page = doc.load_page(page_number - 1)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                text = await self.client.vision_ocr(pixmap.tobytes("png"))
                pages.append(
                    PageText(
                        page_number=page_number,
                        text=text,
                        source="ocr",
                    )
                )

            return pages
        finally:
            doc.close()
