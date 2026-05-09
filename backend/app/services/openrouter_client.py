import base64
import json
from typing import Any

import httpx

from app.config import get_settings


def parse_json_content(content: str) -> Any:
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        for index, character in enumerate(stripped):
            if character not in "{[":
                continue
            try:
                value, _ = decoder.raw_decode(stripped[index:])
            except json.JSONDecodeError:
                continue
            return value
        raise


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        vision_model: str | None = None,
        http_referer: str | None = None,
        title: str = "CogWeb Fact-Check Agent",
    ) -> None:
        settings = get_settings()
        self.api_key = api_key if api_key is not None else settings.openrouter_api_key
        self.model = model or settings.openrouter_model
        self.vision_model = vision_model or settings.openrouter_vision_model
        self.http_referer = http_referer or settings.frontend_origin
        self.title = title

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.http_referer,
            "X-Title": self.title,
        }

    async def chat_json(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> dict[str, Any]:
        content = await self.chat_text(system=system, user=user, model=model)
        return parse_json_content(content)

    async def chat_text(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> str:
        payload = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"]

    async def vision_ocr(self, image_bytes: bytes) -> str:
        image_data = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Extract all readable text from this page image. "
                                "Preserve order and numbers. Return only the text."
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data}",
                            },
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()
