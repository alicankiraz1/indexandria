"""Indexandria MCP server — crawl documentation straight into context.

No database, no disk writes, no background processes.
Fetches web pages, converts to markdown, returns directly to Claude.
Supports session-based in-memory indexing for large doc sets.
"""

from __future__ import annotations

import logging
import re
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

# Session-scoped in-memory store — persists while the MCP server is alive,
# cleared automatically when Claude Code closes the session.
_store: dict = {
    "source_url": None,
    "pages": [],
    "crawled_at": None,
}

mcp = FastMCP(
    "Indexandria",
    instructions=(
        "Indexandria fetches and converts web documentation into markdown. "
        "It has two workflows:\n"
        "1. Quick: 'crawl_docs' for small crawls (1-15 pages) — content goes directly into context.\n"
        "2. Deep: 'index_docs' to crawl up to 100 pages into memory, then use "
        "'get_indexed_page' or 'search_indexed' to retrieve specific content.\n"
        "Nothing is stored on disk. All data lives in memory for the session duration."
    ),
)


def _validate_url(url: str) -> str | None:
    """Return an error message if the URL is invalid, None if OK."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return f"Invalid URL: {url} — only http/https URLs are supported."
    return None


# ---------------------------------------------------------------------------
# Tool 1: crawl_docs (quick mode — unchanged from v2)
# ---------------------------------------------------------------------------

@mcp.tool()
async def crawl_docs(
    url: str,
    depth: int = 2,
    max_pages: int = 15,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> str:
    """Crawl a documentation URL and return its content as markdown.

    Best for small, focused crawls (1-15 pages). Content goes directly
    into the conversation context. For larger doc sets (50-100 pages),
    use index_docs instead.

    Args:
        url: The starting URL (e.g. https://react.dev/reference/react/useEffect).
        depth: How many levels of links to follow (1-3, default 2).
        max_pages: Maximum number of pages to crawl (default 15).
        include_patterns: URL glob patterns to include (e.g. ["*/docs/*"]).
        exclude_patterns: URL glob patterns to exclude (e.g. ["*/blog/*"]).

    Returns:
        Crawled documentation as markdown, ready to use as context.
    """
    err = _validate_url(url)
    if err:
        return err

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


# ---------------------------------------------------------------------------
# Tool 2: index_docs (deep mode — crawl & store, return compact index)
# ---------------------------------------------------------------------------

@mcp.tool()
async def index_docs(
    url: str,
    depth: int = 2,
    max_pages: int = 50,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
) -> str:
    """Crawl a large documentation site and build an in-memory index.

    Pages are stored in memory (not on disk) for the duration of the session.
    Returns a compact table of contents with page numbers, titles, and headings.
    Use get_indexed_page(page_numbers) to read specific pages, or
    search_indexed(query) to find content across all pages.

    Best for large doc sets (20-100 pages). For quick single-page lookups,
    use crawl_docs instead.

    Args:
        url: The starting URL to crawl.
        depth: How many levels of links to follow (1-3, default 2).
        max_pages: Maximum pages to index (default 50, max 100).
        include_patterns: URL glob patterns to include (e.g. ["*/docs/*"]).
        exclude_patterns: URL glob patterns to exclude (e.g. ["*/blog/*"]).

    Returns:
        A compact index listing all crawled pages with their headings.
    """
    err = _validate_url(url)
    if err:
        return err

    depth = max(1, min(depth, 3))
    max_pages = max(1, min(max_pages, 100))

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

    _store["source_url"] = url
    _store["pages"] = pages
    _store["crawled_at"] = time.strftime("%Y-%m-%d %H:%M:%S")

    total_bytes = sum(len(p["content"]) for p in pages)
    lines = [
        f"# Indexed {len(pages)} page(s) from {url} ({elapsed}s)",
        f"Total content: {total_bytes // 1024} KB in memory\n",
        "| #  | Title | Key Headings |",
        "|----|-------|-------------|",
    ]

    for i, page in enumerate(pages, 1):
        title = page["title"] or page["url"]
        if len(title) > 60:
            title = title[:57] + "..."
        h_list = page.get("headings", [])
        # Show up to 5 h2/h3 headings as a preview
        preview_headings = [h for h in h_list if h.startswith("## ") or h.startswith("### ")][:5]
        headings_str = ", ".join(preview_headings) if preview_headings else "—"
        if len(headings_str) > 80:
            headings_str = headings_str[:77] + "..."
        lines.append(f"| {i} | {title} | {headings_str} |")

    lines.append("")
    lines.append("**Next steps:** `get_indexed_page([1, 2])` to read full pages, "
                  "or `search_indexed(\"query\")` to find specific content.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 3: get_indexed_page (retrieve full content from store)
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_indexed_page(
    page_numbers: list[int],
) -> str:
    """Retrieve full content of specific pages from the in-memory index.

    Call index_docs first to build the index. Then use this tool to read
    the full markdown content of specific pages by their number from the
    index table.

    Args:
        page_numbers: List of 1-based page numbers to retrieve (e.g. [1, 5, 12]).

    Returns:
        Full markdown content of the requested pages.
    """
    if not _store["pages"]:
        return "No indexed docs available. Call index_docs(url) first to build an index."

    pages = _store["pages"]
    valid_range = range(1, len(pages) + 1)
    invalid = [n for n in page_numbers if n not in valid_range]
    if invalid:
        return f"Invalid page number(s): {invalid}. Valid range: 1-{len(pages)}."

    parts = []
    total_chars = 0
    included = 0
    for num in page_numbers:
        page = pages[num - 1]
        chunk = f"## [{num}] {page['title'] or page['url']}\nSource: {page['url']}\n\n{page['content']}\n\n---\n"
        if total_chars + len(chunk) > MAX_OUTPUT_CHARS:
            remaining = len(page_numbers) - included
            parts.append(f"\n*{remaining} more page(s) omitted (output size limit). "
                         "Request fewer pages at a time.*\n")
            break
        parts.append(chunk)
        total_chars += len(chunk)
        included += 1

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tool 4: search_indexed (keyword search across stored pages)
# ---------------------------------------------------------------------------

@mcp.tool()
async def search_indexed(
    query: str,
    max_results: int = 10,
) -> str:
    """Search across all indexed pages for a keyword or phrase.

    Call index_docs first to build the index. Returns matching snippets
    with page numbers so you can then use get_indexed_page to read the
    full content.

    Args:
        query: Search term (case-insensitive).
        max_results: Maximum number of matches to return (default 10).

    Returns:
        Matching snippets with page numbers and context lines.
    """
    if not _store["pages"]:
        return "No indexed docs available. Call index_docs(url) first to build an index."

    if not query or not query.strip():
        return "Please provide a search query."

    query_lower = query.lower().strip()
    max_results = max(1, min(max_results, 30))
    pattern = re.compile(re.escape(query_lower), re.IGNORECASE)

    matches: list[str] = []
    for i, page in enumerate(_store["pages"], 1):
        content_lines = page["content"].split("\n")
        page_matches = []
        for line_num, line in enumerate(content_lines):
            if pattern.search(line):
                # Grab surrounding context (1 line before, 1 after)
                start = max(0, line_num - 1)
                end = min(len(content_lines), line_num + 2)
                snippet = "\n".join(content_lines[start:end]).strip()
                page_matches.append(snippet)
                if len(page_matches) >= 3:
                    break

        if page_matches:
            title = page["title"] or page["url"]
            entry = f"### Page {i}: {title}\n"
            for snippet in page_matches:
                entry += f"```\n{snippet}\n```\n"
            matches.append(entry)

        if len(matches) >= max_results:
            break

    if not matches:
        return f"No results found for \"{query}\" across {len(_store['pages'])} indexed pages."

    header = f"# Search results for \"{query}\" ({len(matches)} page(s) matched)\n"
    footer = "\n**Tip:** Use `get_indexed_page([N])` to read the full content of a matching page."
    return header + "\n".join(matches) + footer


if __name__ == "__main__":
    mcp.run(transport="stdio")
