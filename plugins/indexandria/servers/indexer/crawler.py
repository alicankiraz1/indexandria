"""Lightweight async web crawler that returns clean markdown content."""

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

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Indexandria/2.0 (+https://github.com/alicankiraz1/indexandria)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

NOISE_TAGS = ["nav", "footer", "header", "aside", "script", "style", "noscript", "iframe", "svg", "form"]
NOISE_CLASSES = re.compile(
    r"(nav|navbar|sidebar|footer|header|menu|breadcrumb|pagination|ads?|banner|cookie|modal|popup|social|share|comment)",
    re.IGNORECASE,
)

SKIP_EXTENSIONS = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
    ".pdf", ".zip", ".tar", ".gz", ".css", ".js",
    ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".mp3",
)

MAX_PAGE_SIZE = 5 * 1024 * 1024


def _extract(html: str, url: str) -> tuple[str, str, list[str]]:
    """Extract title, markdown content, and links from HTML."""
    soup = BeautifulSoup(html, "lxml")

    title = ""
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        title = title_tag.string.strip()

    content_root = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find(attrs={"id": re.compile(r"^(content|main|docs)", re.I)})
        or soup.find(attrs={"class": re.compile(r"(content|main|docs|article)", re.I)})
        or soup.find("body")
        or soup
    )

    for tag_name in NOISE_TAGS:
        for tag in content_root.find_all(tag_name):
            tag.decompose()
    for tag in content_root.find_all(attrs={"class": NOISE_CLASSES}):
        tag.decompose()
    for tag in content_root.find_all(attrs={"id": NOISE_CLASSES}):
        tag.decompose()
    for img_tag in content_root.find_all("img"):
        img_tag.decompose()

    links = [urljoin(url, a["href"]) for a in content_root.find_all("a", href=True)]

    markdown_content = md(str(content_root), heading_style="ATX", bullets="-")
    markdown_content = re.sub(r"\n{3,}", "\n\n", markdown_content).strip()

    return title, markdown_content, links


def _normalize(url: str) -> str:
    url, _ = urldefrag(url)
    if url.endswith("/") and len(urlparse(url).path) > 1:
        url = url.rstrip("/")
    return url


def _should_follow(url: str, base: str, visited: set, max_pages: int,
                   include: list[str], exclude: list[str]) -> bool:
    parsed, base_parsed = urlparse(url), urlparse(base)
    if parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc != base_parsed.netloc:
        return False
    if any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
        return False
    if _normalize(url) in visited:
        return False
    if len(visited) >= max_pages:
        return False
    if include and not any(fnmatch(url, p) for p in include):
        return False
    if exclude and any(fnmatch(url, p) for p in exclude):
        return False
    return True


async def crawl(
    start_url: str,
    max_depth: int = 2,
    max_pages: int = 50,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> list[dict]:
    """
    Crawl a URL and return pages as a list of {url, title, content} dicts.
    Everything stays in memory — nothing is written to disk.
    """
    include = include_patterns or []
    exclude = exclude_patterns or []
    max_depth = max(1, min(max_depth, 3))

    visited: set[str] = set()
    start_url = _normalize(start_url)
    visited.add(start_url)

    queue: list[tuple[str, int]] = [(start_url, 0)]
    results: list[dict] = []
    sem = asyncio.Semaphore(5)

    async with httpx.AsyncClient(headers=DEFAULT_HEADERS, follow_redirects=True, timeout=30) as client:
        while queue and len(results) < max_pages:
            batch = [queue.pop(0) for _ in range(min(len(queue), 8))]

            async def fetch(url: str, depth: int):
                async with sem:
                    try:
                        resp = await client.get(url)
                        resp.raise_for_status()
                        ct = resp.headers.get("content-type", "")
                        if "text/html" not in ct and "xhtml" not in ct:
                            return None
                        if len(resp.content) > MAX_PAGE_SIZE:
                            return None
                        title, content, links = _extract(resp.text, url)
                        if len(content) < 50:
                            return None
                        return {"url": url, "title": title, "content": content,
                                "links": links, "depth": depth}
                    except Exception as e:
                        logger.debug("Skip %s: %s", url, e)
                        return None
                    finally:
                        await asyncio.sleep(0.3)

            tasks = [fetch(u, d) for u, d in batch]
            for result in await asyncio.gather(*tasks):
                if result is None:
                    continue
                results.append(result)
                if result["depth"] < max_depth:
                    for link in result["links"]:
                        norm = _normalize(link)
                        if _should_follow(norm, start_url, visited, max_pages, include, exclude):
                            visited.add(norm)
                            queue.append((norm, result["depth"] + 1))

    return results
