"""
Web Search Plugin — fetches real-time information from the web.

Uses DuckDuckGo (free, no API key required) by default,
with fallback to a configurable search API provider.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import httpx

from aiden.plugins.base import Plugin, PluginSpec


class WebSearchPlugin(Plugin):
    """Search the web for real-time information."""

    spec = PluginSpec(
        name="web_search",
        description="Search the web for current information. Use this when you need "
        "real-time data, recent news, or facts you're not confident about.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query (e.g. 'latest Python version 2025')",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of search results to return (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    )

    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=15.0,
            follow_redirects=True,
            headers={"User-Agent": "Aiden/0.1 (AI Assistant)"},
        )

    async def execute(self, query: str, max_results: int = 5) -> str:
        """Execute a web search and return formatted results."""
        max_results = max(1, min(10, max_results))
        try:
            results = await self._search_duckduckgo(query, max_results)
            if not results:
                return f"⚠️ No results found for '{query}'."
            return self._format_results(results, query)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 202:
                # DDG sometimes returns 202 for rate-limiting
                await asyncio.sleep(1)
                try:
                    results = await self._search_duckduckgo(query, max_results)
                    if results:
                        return self._format_results(results, query)
                except Exception:
                    pass
            return f"⚠️ Search failed (HTTP {e.response.status_code}). Try again later."
        except httpx.TimeoutException:
            return "⚠️ Search timed out. Please try again."
        except Exception as e:
            return f"⚠️ Search error: {type(e).__name__}: {e}"

    async def _search_duckduckgo(
        self, query: str, max_results: int
    ) -> list[dict]:
        """Use DuckDuckGo's instant answer API (no key required)."""
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        resp = await self._client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        results: list[dict] = []

        # Abstract (from the instant answer)
        abstract = data.get("AbstractText", "")
        abstract_source = data.get("AbstractSource", "")
        abstract_url = data.get("AbstractURL", "")
        if abstract:
            results.append({
                "title": abstract_source or "Summary",
                "snippet": abstract,
                "url": abstract_url,
            })

        # Related topics
        for topic in data.get("RelatedTopics", []):
            if "Text" in topic and "FirstURL" in topic:
                results.append({
                    "title": topic.get("Text", "").split(" - ")[0],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                })
            if len(results) >= max_results:
                break

        # Infobox (if available)
        infobox = data.get("Infobox", {})
        if infobox and isinstance(infobox, dict):
            content = infobox.get("content", [])
            for item in content[:3]:
                label = item.get("label", "")
                value = item.get("value", "")
                if label and value:
                    results.append({
                        "title": label,
                        "snippet": str(value)[:200],
                        "url": "",
                    })

        return results[:max_results]

    def _format_results(self, results: list[dict], query: str) -> str:
        """Format search results as a readable string."""
        lines = [f"🔍 Search results for: **{query}**\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"{i}. **{r['title']}**")
            if r.get("url"):
                lines.append(f"   URL: {r['url']}")
            lines.append(f"   {r.get('snippet', '')[:300]}")
            lines.append("")
        return "\n".join(lines)

    async def close(self) -> None:
        await self._client.aclose()
