"""Simple website content fetcher (no JS rendering)."""

from typing import Any

import httpx
import structlog
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = structlog.get_logger()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=5),
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    reraise=False,
)
async def _fetch_one(client: httpx.AsyncClient, url: str) -> dict[str, Any] | None:
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
    except Exception as e:
        logger.warning("fetch_failed", url=url, error=str(e))
        return None

    soup = BeautifulSoup(resp.text, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator="\n", strip=True)

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    description = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        description = str(meta["content"]).strip()

    return {
        "url": str(resp.url),
        "title": title,
        "description": description,
        "text": text[:20_000],
    }


async def fetch_websites(urls: list[str], *, timeout: float = 15.0) -> list[dict[str, Any]]:
    """Fetch website contents, skipping unreachable ones."""
    if not urls:
        return []
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=5.0),
        headers={"User-Agent": "OutreachOS/0.1 (+https://aitler.ru)"},
    ) as client:
        for url in urls:
            item = await _fetch_one(client, url)
            if item is not None:
                results.append(item)
    return results
