"""Data models for the Claude Code Indexer plugin."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Represents an indexed documentation source."""

    id: int
    url: str
    title: Optional[str] = None
    crawl_depth: int = 1
    include_patterns: Optional[list[str]] = None
    exclude_patterns: Optional[list[str]] = None
    last_crawled: Optional[datetime] = None
    page_count: int = 0
    created_at: Optional[datetime] = None


class Document(BaseModel):
    """Represents a single crawled page/document."""

    id: int
    source_id: int
    url: str
    title: Optional[str] = None
    content: Optional[str] = None
    content_hash: Optional[str] = None
    crawled_at: Optional[datetime] = None


class Chunk(BaseModel):
    """Represents a text chunk from a document, used for FTS indexing."""

    id: int
    document_id: int
    title: Optional[str] = None
    content: str
    url: Optional[str] = None
    source_url: Optional[str] = None
    chunk_index: int = 0


class SearchResult(BaseModel):
    """A single search result returned from the index."""

    chunk_id: int
    title: Optional[str] = None
    snippet: str
    url: Optional[str] = None
    source_url: Optional[str] = None
    rank: float = 0.0


class CrawlResult(BaseModel):
    """Result of crawling a single page."""

    url: str
    title: Optional[str] = None
    markdown_content: str
    links: list[str] = Field(default_factory=list)
    content_hash: str


class CrawlStats(BaseModel):
    """Statistics returned after a crawl operation."""

    source_url: str
    pages_crawled: int
    pages_skipped: int
    chunks_created: int
    elapsed_seconds: float


class IndexStats(BaseModel):
    """Overall index statistics."""

    total_sources: int
    total_documents: int
    total_chunks: int
    db_size_mb: float
    sources: list[SourceSummary] = Field(default_factory=list)


class SourceSummary(BaseModel):
    """Summary info for a single source in stats."""

    url: str
    title: Optional[str] = None
    page_count: int
    chunk_count: int
    last_crawled: Optional[datetime] = None
