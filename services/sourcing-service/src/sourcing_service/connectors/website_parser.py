"""Website parser connector: fetch pages and extract text/contacts.

Strategy: httpx + BeautifulSoup first; if the extracted text is too short and
Playwright is available, fall back to JS rendering. Playwright is optional and
import-guarded so the service runs without browser binaries installed.
"""

import re
import time
from dataclasses import dataclass, field

import httpx
import structlog
import tldextract
from bs4 import BeautifulSoup

from sourcing_service.connectors.base import (
    Connector,
    ConnectorResult,
    RawCandidate,
    SearchCriteria,
)

logger = structlog.get_logger()

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(?:\+7|8)[\s\-()]?\d{3}[\s\-()]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}")
_EMAIL_JUNK = ("example.", "test.", "sentry", "noreply", "no-reply")


@dataclass
class ParsedPage:
    url: str
    title: str
    text: str
    meta_description: str
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)


class WebsiteParserConnector(Connector):
    """Fetches pages and extracts text + contacts.

    Does NOT search for sites: works on the list of URLs in
    ``criteria.extra['urls']``. Used as an enricher after a web-search connector.
    """

    name = "website_parser"

    def __init__(self, *, timeout: float = 20.0, max_pages_per_site: int = 3) -> None:
        super().__init__(rate_limit_per_sec=2.0)
        self._timeout = timeout
        self._max_pages = max_pages_per_site
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=5.0),
            headers={"User-Agent": "Mozilla/5.0 (compatible; OutreachOS/0.1; +https://aitler.ru)"},
            follow_redirects=True,
        )

    @property
    def is_available(self) -> bool:
        return True

    async def search(self, criteria: SearchCriteria) -> ConnectorResult:
        urls = criteria.extra.get("urls", [])
        if not urls:
            return ConnectorResult(
                source=self.name, candidates=[], error="no urls in criteria.extra"
            )
        started = time.monotonic()
        candidates: list[RawCandidate] = []
        for url in urls[:20]:
            try:
                page = await self._parse(url)
                if page is None:
                    continue
                candidates.append(
                    RawCandidate(
                        source=self.name,
                        source_url=page.url,
                        title=page.title,
                        snippet=page.meta_description or page.text[:300],
                        domain=self._extract_domain(page.url),
                        raw_payload={
                            "text": page.text[:15000],
                            "emails": page.emails,
                            "phones": page.phones,
                            "meta_description": page.meta_description,
                        },
                    )
                )
            except Exception as e:
                logger.warning("parse_failed", url=url, error=str(e))
        duration_ms = int((time.monotonic() - started) * 1000)
        return ConnectorResult(
            source=self.name, candidates=candidates, cost_usd=0.0, duration_ms=duration_ms
        )

    async def _parse(self, url: str) -> ParsedPage | None:
        try:
            resp = await self._client.get(url)
            resp.raise_for_status()
            html = resp.text
            final_url = str(resp.url)
        except Exception as e:
            logger.debug("httpx_parse_failed", url=url, error=str(e))
            return None

        soup = BeautifulSoup(html, "lxml")
        text = self._extract_text(soup)

        if len(text) < 500:
            text_js, html_js = await self._render_with_playwright(final_url)
            if len(text_js) > len(text):
                text = text_js
                soup = BeautifulSoup(html_js, "lxml")

        if not text:
            return None

        title = soup.title.string.strip() if soup.title and soup.title.string else ""
        meta = soup.find("meta", attrs={"name": "description"})
        meta_description = str(meta["content"]).strip() if meta and meta.get("content") else ""
        return ParsedPage(
            url=final_url,
            title=title,
            text=text,
            meta_description=meta_description,
            emails=self._extract_emails(html),
            phones=self._extract_phones(html),
        )

    @staticmethod
    def _extract_text(soup: BeautifulSoup) -> str:
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line for line in text.split("\n") if line.strip()]
        return "\n".join(lines)

    @staticmethod
    def _extract_emails(html: str) -> list[str]:
        found = set(_EMAIL_RE.findall(html))
        return [e.lower() for e in found if not any(x in e for x in _EMAIL_JUNK)][:10]

    @staticmethod
    def _extract_phones(html: str) -> list[str]:
        return list(set(_PHONE_RE.findall(html)))[:10]

    async def _render_with_playwright(self, url: str) -> tuple[str, str]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return "", ""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (compatible; OutreachOS/0.1)",
                    viewport={"width": 1280, "height": 800},
                )
                page = await context.new_page()
                await page.goto(url, timeout=self._timeout * 1000, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                html = await page.content()
                text = await page.inner_text("body")
                await browser.close()
                return text, html
        except Exception as e:
            logger.warning("playwright_failed", url=url, error=str(e))
            return "", ""

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        if not url:
            return None
        ext = tldextract.extract(url)
        if not ext.domain or not ext.suffix:
            return None
        return f"{ext.domain}.{ext.suffix}".lower()

    async def close(self) -> None:
        await self._client.aclose()
