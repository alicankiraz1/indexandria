"""MCP server for the Indexandria plugin.

Exposes tools for crawling, indexing, and searching web documentation
via the Model Context Protocol using FastMCP.

Run modes:
  HTTP (default):  python server.py                → http://localhost:21517/mcp
  HTTP (custom):   python server.py --port 9000    → http://localhost:9000/mcp
  Stdio:           python server.py --stdio        → stdio transport
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Optional

from mcp.server.fastmcp import FastMCP

from crawler import Crawler
from indexer import DocumentIndexer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("indexandria")

DEFAULT_PORT = int(os.environ.get("INDEXANDRIA_PORT", "21517"))


@dataclass
class AppContext:
    """Application context holding the indexer instance."""

    indexer: DocumentIndexer


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Initialize and clean up the document indexer."""
    indexer = DocumentIndexer()
    logger.info("Indexer initialized with DB at: %s", indexer.db_path)
    try:
        yield AppContext(indexer=indexer)
    finally:
        indexer.close()
        logger.info("Indexer shut down")


mcp = FastMCP(
    "Indexandria",
    instructions=(
        "Indexandria provides tools for crawling and indexing web documentation. "
        "Use 'search_docs' to find relevant documentation when writing code. "
        "Use 'crawl_and_index' to add new documentation sources. "
        "The index persists across sessions."
    ),
    lifespan=app_lifespan,
    host="127.0.0.1",
    port=DEFAULT_PORT,
)


def _get_indexer(ctx) -> DocumentIndexer:
    """Extract the indexer from the request context."""
    return ctx.request_context.lifespan_context.indexer


# ── Tool: crawl_and_index ──────────────────────────────────────────


@mcp.tool()
async def crawl_and_index(
    url: str,
    depth: int = 2,
    include_patterns: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
    ctx=None,
) -> str:
    """Crawl a documentation URL and index its content for later search.

    Args:
        url: The starting URL to crawl (e.g. https://react.dev/reference).
        depth: How many levels of links to follow (1-3, default 2).
        include_patterns: Optional URL glob patterns to include (e.g. ["*/docs/*"]).
        exclude_patterns: Optional URL glob patterns to exclude (e.g. ["*/blog/*"]).

    Returns:
        A summary of the crawl operation including pages crawled and chunks created.
    """
    indexer = _get_indexer(ctx)
    depth = max(1, min(depth, 3))

    if ctx:
        await ctx.info(f"Starting crawl of {url} (depth={depth})...")

    source = indexer.add_source(
        url=url,
        crawl_depth=depth,
        include_patterns=include_patterns,
        exclude_patterns=exclude_patterns,
    )

    indexer.clear_source_documents(source.id)

    crawler = Crawler(
        max_depth=depth,
        include_patterns=include_patterns or [],
        exclude_patterns=exclude_patterns or [],
    )

    start_time = time.time()
    results = await crawler.crawl(url)
    total_chunks = 0
    pages_skipped = 0

    for i, result in enumerate(results):
        if ctx and i % 10 == 0:
            await ctx.report_progress(progress=i, total=len(results))

        chunks_created = indexer.index_document(
            source_id=source.id,
            url=result.url,
            title=result.title,
            markdown_content=result.markdown_content,
            content_hash=result.content_hash,
            source_url=url,
        )
        if chunks_created == 0:
            pages_skipped += 1
        total_chunks += chunks_created

    if not source.title and results:
        indexer.conn.execute(
            "UPDATE sources SET title = ? WHERE id = ?",
            (results[0].title, source.id),
        )
        indexer.conn.commit()

    indexer.update_source_stats(source.id)
    elapsed = round(time.time() - start_time, 1)

    return (
        f"Crawl complete for {url}\n"
        f"- Pages crawled: {len(results)}\n"
        f"- Pages skipped (unchanged): {pages_skipped}\n"
        f"- Chunks indexed: {total_chunks}\n"
        f"- Time elapsed: {elapsed}s"
    )


# ── Tool: search_docs ──────────────────────────────────────────────


@mcp.tool()
async def search_docs(
    query: str,
    limit: int = 10,
    source_filter: Optional[str] = None,
    ctx=None,
) -> str:
    """Search indexed documentation for relevant content.

    Use this tool when you need to find documentation about a library,
    framework, API, or any previously indexed content.

    Args:
        query: The search query (e.g. "useEffect cleanup", "API authentication").
        limit: Maximum number of results to return (default 10).
        source_filter: Optional source URL to limit search to a specific source.

    Returns:
        Matching documentation snippets with source URLs and relevance ranking.
    """
    indexer = _get_indexer(ctx)
    results = indexer.search(query, limit=limit, source_filter=source_filter)

    if not results:
        return f"No results found for: {query}"

    output_parts = [f"Found {len(results)} result(s) for: {query}\n"]
    for i, r in enumerate(results, 1):
        output_parts.append(
            f"---\n"
            f"**Result {i}** (relevance: {abs(r.rank):.2f})\n"
            f"Title: {r.title or 'N/A'}\n"
            f"URL: {r.url or 'N/A'}\n"
            f"Source: {r.source_url or 'N/A'}\n\n"
            f"{r.snippet}\n"
        )

    return "\n".join(output_parts)


# ── Tool: get_document ─────────────────────────────────────────────


@mcp.tool()
async def get_document(doc_id: int, ctx=None) -> str:
    """Retrieve the full content of a specific indexed document.

    Args:
        doc_id: The document ID (from search results or source listing).

    Returns:
        The full markdown content of the document.
    """
    indexer = _get_indexer(ctx)
    doc = indexer.get_document(doc_id)

    if not doc:
        return f"Document with ID {doc_id} not found."

    return (
        f"# {doc.title or 'Untitled'}\n"
        f"URL: {doc.url}\n"
        f"Crawled: {doc.crawled_at}\n\n"
        f"---\n\n"
        f"{doc.content}"
    )


# ── Tool: list_sources ─────────────────────────────────────────────


@mcp.tool()
async def list_sources(ctx=None) -> str:
    """List all indexed documentation sources.

    Returns:
        A formatted list of all sources with their details and statistics.
    """
    indexer = _get_indexer(ctx)
    sources = indexer.list_sources()

    if not sources:
        return "No documentation sources indexed yet. Use crawl_and_index to add one."

    parts = [f"Indexed sources ({len(sources)}):\n"]
    for s in sources:
        parts.append(
            f"- **{s.title or s.url}**\n"
            f"  URL: {s.url}\n"
            f"  Pages: {s.page_count} | Depth: {s.crawl_depth}\n"
            f"  Last crawled: {s.last_crawled or 'Never'}\n"
        )
    return "\n".join(parts)


# ── Tool: remove_source ────────────────────────────────────────────


@mcp.tool()
async def remove_source(source_url: str, ctx=None) -> str:
    """Remove an indexed documentation source and all its data.

    Args:
        source_url: The URL of the source to remove.

    Returns:
        Confirmation of removal or an error message.
    """
    indexer = _get_indexer(ctx)
    removed = indexer.remove_source(source_url)

    if removed:
        return f"Successfully removed source and all indexed data for: {source_url}"
    return f"Source not found: {source_url}"


# ── Tool: reindex_source ───────────────────────────────────────────


@mcp.tool()
async def reindex_source(source_url: str, ctx=None) -> str:
    """Re-crawl and update an existing documentation source.

    This will re-crawl the source URL with its original settings and
    update the index. Unchanged pages are skipped for efficiency.

    Args:
        source_url: The URL of the source to reindex.

    Returns:
        A summary of the reindex operation.
    """
    indexer = _get_indexer(ctx)
    source = indexer.get_source(source_url)

    if not source:
        return f"Source not found: {source_url}. Use crawl_and_index to add it first."

    return await crawl_and_index(
        url=source.url,
        depth=source.crawl_depth,
        include_patterns=source.include_patterns,
        exclude_patterns=source.exclude_patterns,
        ctx=ctx,
    )


# ── Tool: get_index_stats ──────────────────────────────────────────


@mcp.tool()
async def get_index_stats(ctx=None) -> str:
    """Get statistics about the documentation index.

    Returns:
        Overview of total sources, documents, chunks, and database size.
    """
    indexer = _get_indexer(ctx)
    stats = indexer.get_stats()

    parts = [
        "Index Statistics:",
        f"- Total sources: {stats.total_sources}",
        f"- Total documents: {stats.total_documents}",
        f"- Total chunks: {stats.total_chunks}",
        f"- Database size: {stats.db_size_mb} MB",
    ]

    if stats.sources:
        parts.append("\nPer-source breakdown:")
        for s in stats.sources:
            parts.append(
                f"  - {s.title or s.url}: "
                f"{s.page_count} pages, {s.chunk_count} chunks"
            )

    return "\n".join(parts)


# ── Entry Point ────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Indexandria MCP Server")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"HTTP port (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "--stdio", action="store_true",
        help="Use stdio transport instead of HTTP",
    )
    args = parser.parse_args()

    if args.stdio:
        logger.info("Starting Indexandria in stdio mode")
        mcp.run(transport="stdio")
    else:
        if args.port != DEFAULT_PORT:
            mcp.settings.port = args.port
        logger.info("Starting Indexandria on http://localhost:%d/mcp", args.port)
        mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
