"""Indexandria MCP server — crawl documentation straight into context.

No database, no disk writes, no background processes.
Fetches web pages, converts to markdown, returns directly to Claude.
"""

from __future__ import annotations

import logging
import sys
import time
from typing import Optional
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from crawler import crawl

MAX_OUTPUT_CHARS = 110_000

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("indexandria")

mcp = FastMCP(
    "Indexandria",
    instructions=(
        "Indexandria fetches and converts web documentation into markdown. "
        "Use 'crawl_docs' to pull documentation into the conversation context. "
        "The content is returned directly — nothing is stored on disk."
    ),
)


@mcp.tool()
async def crawl_docs(
    url: str,
    depth: int = 2,
    max_pages: int = 15,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> str:
    """Crawl a documentation URL and return its content as markdown.

    The content is returned directly into the conversation — nothing is
    written to disk. Use this to pull framework docs, API references, or
    any web documentation into context before writing code.

    Args:
        url: The starting URL (e.g. https://react.dev/reference/react/useEffect).
        depth: How many levels of links to follow (1-3, default 2).
        max_pages: Maximum number of pages to crawl (default 15).
        include_patterns: URL glob patterns to include (e.g. ["*/docs/*"]).
        exclude_patterns: URL glob patterns to exclude (e.g. ["*/blog/*"]).

    Returns:
        Crawled documentation as markdown, ready to use as context.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"Invalid URL: {url} — only http/https URLs are supported."

    depth = max(1, min(depth, 3))
    max_pages = max(1, min(max_pages, 50))

    start = time.time()
    pages = await crawl(
        start_url=url,
        max_depth=depth,
        max_pages=max_pages,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )
    elapsed = round(time.time() - start, 1)

    if not pages:
        return f"No content found at {url}"

    parts = [f"# Crawled {len(pages)} page(s) from {url} ({elapsed}s)\n"]
    total_chars = len(parts[0])
    included = 0
    for page in pages:
        chunk = f"\n---\n## {page['title'] or page['url']}\nSource: {page['url']}\n\n{page['content']}\n"
        if total_chars + len(chunk) > MAX_OUTPUT_CHARS:
            remaining = len(pages) - included
            parts.append(f"\n---\n*{remaining} more page(s) omitted (output size limit)*\n")
            break
        parts.append(chunk)
        total_chars += len(chunk)
        included += 1

    return "\n".join(parts)


if __name__ == "__main__":
    mcp.run(transport="stdio")
