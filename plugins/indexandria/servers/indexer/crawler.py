"""Async web crawler for documentation indexing."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from fnmatch import fnmatch
from typing import Optional
from urllib.parse import urljoin, urlparse, urldefrag

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

from models import CrawlResult

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Indexandria/1.0 "
        "(+https://github.com/alicankiraz/indexandria)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Tags that typically contain navigation, ads, footers — not main content
NOISE_TAGS = [
    "nav", "footer", "header", "aside",
    "script", "style", "noscript", "iframe",
    "svg", "form",
]

NOISE_CLASSES = re.compile(
    r"(nav|navbar|sidebar|footer|header|menu|breadcrumb|pagination|"
    r"ads?|banner|cookie|modal|popup|social|share|comment)",
    re.IGNORECASE,
)

MAX_PAGE_SIZE = 5 * 1024 * 1024  # 5 MB


class Crawler:
    """Async web crawler that extracts clean markdown from documentation pages."""

    def __init__(
        self,
        max_depth: int = 2,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
        rate_limit: float = 0.5,
        timeout: float = 30.0,
        max_pages: int = 500,
    ):
        self.max_depth = min(max_depth, 3)
        self.include_patterns = include_patterns or []
        self.exclude_patterns = exclude_patterns or []
        self.rate_limit = rate_limit
        self.timeout = timeout
        self.max_pages = max_pages
        self._visited: set[str] = set()
        self._semaphore = asyncio.Semaphore(5)

    def _normalize_url(self, url: str) -> str:
        """Remove fragment and trailing slash for dedup."""
        url, _ = urldefrag(url)
        if url.endswith("/") and len(urlparse(url).path) > 1:
            url = url.rstrip("/")
        return url

    def _should_crawl(self, url: str, base_url: str) -> bool:
        """Determine whether a URL should be crawled."""
        parsed = urlparse(url)
        base_parsed = urlparse(base_url)

        if parsed.scheme not in ("http", "https"):
            return False

        if parsed.netloc != base_parsed.netloc:
            return False

        # Skip non-document resources
        skip_extensions = (
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp",
            ".pdf", ".zip", ".tar", ".gz",
            ".css", ".js", ".woff", ".woff2", ".ttf", ".eot",
            ".mp4", ".mp3", ".avi", ".mov",
        )
        if any(parsed.path.lower().endswith(ext) for ext in skip_extensions):
            return False

        normalized = self._normalize_url(url)
        if normalized in self._visited:
            return False

        if len(self._visited) >= self.max_pages:
            return False

        if self.include_patterns:
            if not any(fnmatch(url, p) for p in self.include_patterns):
                return False

        if self.exclude_patterns:
            if any(fnmatch(url, p) for p in self.exclude_patterns):
                return False

        return True

    def _extract_content(self, html: str, url: str) -> tuple[str, str, list[str]]:
        """Extract title, markdown content, and links from HTML."""
        soup = BeautifulSoup(html, "lxml")

        title = ""
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()

        # Try to find the main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(attrs={"role": "main"})
            or soup.find(attrs={"id": re.compile(r"^(content|main|docs)", re.I)})
            or soup.find(attrs={"class": re.compile(r"(content|main|docs|article)", re.I)})
        )

        # Fall back to body if no main content area found
        content_root = main_content or soup.find("body") or soup

        # Remove noise elements
        for tag_name in NOISE_TAGS:
            for tag in content_root.find_all(tag_name):
                tag.decompose()

        for tag in content_root.find_all(attrs={"class": NOISE_CLASSES}):
            tag.decompose()
        for tag in content_root.find_all(attrs={"id": NOISE_CLASSES}):
            tag.decompose()

        # Extract links before converting to markdown
        links: list[str] = []
        for a_tag in content_root.find_all("a", href=True):
            href = a_tag["href"]
            absolute = urljoin(url, href)
            links.append(absolute)

        # Remove images before conversion (markdownify doesn't allow strip + convert)
        for img_tag in content_root.find_all("img"):
            img_tag.decompose()

        # Convert to markdown
        markdown_content = md(
            str(content_root),
            heading_style="ATX",
            bullets="-",
        )

        # Clean up excessive whitespace
        markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content)
        markdown_content = markdown_content.strip()

        return title, markdown_content, links

    async def _fetch_page(
        self, client: httpx.AsyncClient, url: str
    ) -> Optional[CrawlResult]:
        """Fetch and parse a single page."""
        async with self._semaphore:
            try:
                response = await client.get(
                    url,
                    follow_redirects=True,
                    timeout=self.timeout,
                )
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type and "xhtml" not in content_type:
                    logger.debug("Skipping non-HTML: %s (%s)", url, content_type)
                    return None

                if len(response.content) > MAX_PAGE_SIZE:
                    logger.warning("Page too large, skipping: %s", url)
                    return None

                html = response.text
                title, markdown_content, links = self._extract_content(html, url)

                if len(markdown_content) < 50:
                    logger.debug("Content too short, skipping: %s", url)
                    return None

                content_hash = hashlib.sha256(markdown_content.encode()).hexdigest()

                return CrawlResult(
                    url=url,
                    title=title or url,
                    markdown_content=markdown_content,
                    links=links,
                    content_hash=content_hash,
                )

            except httpx.HTTPStatusError as e:
                logger.warning("HTTP %d for %s", e.response.status_code, url)
                return None
            except (httpx.RequestError, Exception) as e:
                logger.warning("Failed to fetch %s: %s", url, e)
                return None
            finally:
                await asyncio.sleep(self.rate_limit)

    async def crawl(self, start_url: str) -> list[CrawlResult]:
        """
        Crawl starting from the given URL up to max_depth levels deep.

        Returns a list of CrawlResult objects for all successfully crawled pages.
        """
        self._visited.clear()
        results: list[CrawlResult] = []
        start_url = self._normalize_url(start_url)

        queue: list[tuple[str, int]] = [(start_url, 0)]
        self._visited.add(start_url)

        async with httpx.AsyncClient(headers=DEFAULT_HEADERS) as client:
            while queue:
                # Process pages in batches for efficiency
                batch_size = min(len(queue), 10)
                current_batch = [queue.pop(0) for _ in range(batch_size)]

                tasks = [
                    self._fetch_page(client, url)
                    for url, _ in current_batch
                ]
                batch_results = await asyncio.gather(*tasks)

                for (url, depth), result in zip(current_batch, batch_results):
                    if result is None:
                        continue

                    results.append(result)
                    logger.info(
                        "Crawled [%d/%d] depth=%d: %s",
                        len(results), self.max_pages, depth, url,
                    )

                    if depth < self.max_depth:
                        for link in result.links:
                            normalized = self._normalize_url(link)
                            if self._should_crawl(normalized, start_url):
                                self._visited.add(normalized)
                                queue.append((normalized, depth + 1))

        logger.info("Crawl complete: %d pages from %s", len(results), start_url)
        return results
