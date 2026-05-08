import httpx


class TavilyClient:
    def __init__(self, api_key: str, search_depth: str = "basic") -> None:
        self.api_key = api_key
        self.search_depth = search_depth

    async def search(self, query: str, max_results: int = 5) -> dict:
        payload = {
            "query": query,
            "search_depth": self.search_depth,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()
