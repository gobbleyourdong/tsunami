"""Search tools — the scholar.

Search is humility encoded as a tool. Never rely solely
on what you already know. Use up to 3 query variants
to expand coverage. Follow up on snippets by visiting
the actual source — snippets lie.
"""

from __future__ import annotations

import json
import logging

from .base import BaseTool, ToolResult

log = logging.getLogger("tsunami.search")


class SearchWeb(BaseTool):
    name = "search_web"
    description = (
        "Search the web for information. Types: info (general), news (current events), "
        "research (academic), data (datasets/numbers), image (visual). "
        "Use up to 3 query variants per topic to expand coverage. "
        "Never trust snippets — visit the source with browser_navigate. "
        "The scholar: find what is known."
    )

    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "search_type": {
                    "type": "string",
                    "enum": ["info", "news", "research", "data", "image"],
                    "description": "Type of search",
                    "default": "info",
                },
                "num_results": {"type": "integer", "description": "Number of results", "default": 5},
            },
            "required": ["query"],
        }

    async def execute(self, query: str, search_type: str = "info",
                      num_results: int = 5, **kw) -> ToolResult:
        # Try backends in order of preference
        for backend in [self._search_ddg, self._search_brave, self._search_httpx_fallback]:
            result = await backend(query, search_type, num_results)
            if not result.is_error:
                return result

        return ToolResult(
            "All search backends failed. Use browser_navigate to search manually: "
            "navigate to https://duckduckgo.com/?q=your+query",
            is_error=True,
        )

    async def _search_ddg(self, query: str, search_type: str, num: int) -> ToolResult:
        """Search using DuckDuckGo via the duckduckgo-search package."""
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return ToolResult(
                "duckduckgo-search not installed. Run: pip install duckduckgo-search",
                is_error=True,
            )

        try:
            ddgs = DDGS()
            if search_type == "news":
                results = list(ddgs.news(query, max_results=num))
            elif search_type == "image":
                results = list(ddgs.images(query, max_results=num))
            else:
                results = list(ddgs.text(query, max_results=num))

            if not results:
                return ToolResult(f"No results for '{query}'")

            return self._format_results(query, search_type, results)

        except Exception as e:
            log.warning(f"DDG search failed: {e}")
            return ToolResult(f"DDG search error: {e}", is_error=True)

    async def _search_brave(self, query: str, search_type: str, num: int) -> ToolResult:
        """Search using Brave Search API (free tier, 2000 queries/month)."""
        import os
        api_key = os.environ.get("BRAVE_API_KEY", self.config.search_api_key or "")
        if not api_key:
            return ToolResult("No Brave API key", is_error=True)

        try:
            import httpx
            headers = {"Accept": "application/json", "X-Subscription-Token": api_key}
            params = {"q": query, "count": min(num, 20)}
            if search_type == "news":
                url = "https://api.search.brave.com/res/v1/news/search"
            else:
                url = "https://api.search.brave.com/res/v1/web/search"

            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code != 200:
                    return ToolResult(f"Brave API error: {resp.status_code}", is_error=True)

                data = resp.json()
                results = []
                for item in (data.get("web", {}).get("results", []) or data.get("results", []))[:num]:
                    results.append({
                        "title": item.get("title", ""),
                        "href": item.get("url", ""),
                        "body": item.get("description", ""),
                    })

                if not results:
                    return ToolResult(f"No Brave results for '{query}'", is_error=True)
                return self._format_results(query, search_type, results)

        except Exception as e:
            log.warning(f"Brave search failed: {e}")
            return ToolResult(f"Brave search error: {e}", is_error=True)

    async def _search_httpx_fallback(self, query: str, search_type: str, num: int) -> ToolResult:
        """Fallback: use DuckDuckGo HTML search via httpx."""
        try:
            import httpx

            params = {"q": query, "t": "h_", "ia": "web"}
            if search_type == "news":
                params["iar"] = "news"

            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params=params,
                    headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Manus/1.0"},
                )
                resp.raise_for_status()

            # Parse the HTML response for result snippets
            html = resp.text
            results = []
            import re

            # Extract result blocks
            for match in re.finditer(
                r'class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
                r'class="result__snippet"[^>]*>(.*?)</span>',
                html, re.DOTALL,
            ):
                url, title, snippet = match.groups()
                # Clean HTML tags
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                if url and title:
                    results.append({
                        "title": title,
                        "href": url,
                        "body": snippet,
                    })
                if len(results) >= num:
                    break

            if not results:
                return ToolResult(f"No results parsed from HTML search for '{query}'", is_error=True)

            return self._format_results(query, search_type, results)

        except Exception as e:
            log.warning(f"HTTP fallback search failed: {e}")
            return ToolResult(f"HTTP search error: {e}", is_error=True)

    def _format_results(self, query: str, search_type: str, results: list[dict]) -> ToolResult:
        """Format search results consistently."""
        lines = [f"Search results for '{query}' ({search_type}):"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "Untitled")
            url = r.get("href", r.get("url", r.get("link", "")))
            snippet = r.get("body", r.get("description", ""))
            lines.append(f"\n[{i}] {title}")
            if url:
                lines.append(f"    URL: {url}")
            if snippet:
                lines.append(f"    {snippet[:300]}")
        return ToolResult("\n".join(lines))
