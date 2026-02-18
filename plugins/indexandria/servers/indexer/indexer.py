"""SQLite FTS5 based document indexer for full-text search."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from models import (
    Chunk,
    Document,
    IndexStats,
    SearchResult,
    Source,
    SourceSummary,
)
from chunker import Chunker, TextChunk

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(
    os.path.expanduser("~"), ".indexandria", "index.db"
)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT,
    crawl_depth INTEGER DEFAULT 1,
    include_patterns TEXT,
    exclude_patterns TEXT,
    last_crawled TIMESTAMP,
    page_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title TEXT,
    content TEXT,
    content_hash TEXT,
    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    title TEXT,
    content TEXT NOT NULL,
    url TEXT,
    source_url TEXT,
    chunk_index INTEGER DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    title,
    content,
    url,
    source_url,
    content='chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync with the chunks table
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, title, content, url, source_url)
    VALUES (new.id, new.title, new.content, new.url, new.source_url);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, title, content, url, source_url)
    VALUES ('delete', old.id, old.title, old.content, old.url, old.source_url);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, title, content, url, source_url)
    VALUES ('delete', old.id, old.title, old.content, old.url, old.source_url);
    INSERT INTO chunks_fts(rowid, title, content, url, source_url)
    VALUES (new.id, new.title, new.content, new.url, new.source_url);
END;

CREATE INDEX IF NOT EXISTS idx_documents_source_id ON documents(source_id);
CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_sources_url ON sources(url);
"""


class DocumentIndexer:
    """Manages the SQLite FTS5 index for crawled documentation."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.environ.get("INDEXER_DB_PATH", DEFAULT_DB_PATH)
        self._ensure_db_dir()
        self._conn: Optional[sqlite3.Connection] = None
        self._chunker = Chunker()

    def _ensure_db_dir(self) -> None:
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
            self._init_schema()
        return self._conn

    def _init_schema(self) -> None:
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Source Management ──────────────────────────────────────────

    def add_source(
        self,
        url: str,
        title: Optional[str] = None,
        crawl_depth: int = 1,
        include_patterns: Optional[list[str]] = None,
        exclude_patterns: Optional[list[str]] = None,
    ) -> Source:
        """Add or update a source in the index."""
        now = datetime.now(timezone.utc).isoformat()
        inc_json = json.dumps(include_patterns) if include_patterns else None
        exc_json = json.dumps(exclude_patterns) if exclude_patterns else None

        cursor = self.conn.execute(
            """
            INSERT INTO sources (url, title, crawl_depth, include_patterns, exclude_patterns, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                title = COALESCE(excluded.title, sources.title),
                crawl_depth = excluded.crawl_depth,
                include_patterns = excluded.include_patterns,
                exclude_patterns = excluded.exclude_patterns
            RETURNING *
            """,
            (url, title, crawl_depth, inc_json, exc_json, now),
        )
        row = cursor.fetchone()
        self.conn.commit()
        return self._row_to_source(row)

    def get_source(self, url: str) -> Optional[Source]:
        cursor = self.conn.execute("SELECT * FROM sources WHERE url = ?", (url,))
        row = cursor.fetchone()
        return self._row_to_source(row) if row else None

    def list_sources(self) -> list[Source]:
        cursor = self.conn.execute("SELECT * FROM sources ORDER BY created_at DESC")
        return [self._row_to_source(row) for row in cursor.fetchall()]

    def remove_source(self, url: str) -> bool:
        """Remove a source and all its documents/chunks (cascade)."""
        source = self.get_source(url)
        if not source:
            return False

        # Manually delete chunks first to trigger FTS sync
        doc_ids = [
            row["id"]
            for row in self.conn.execute(
                "SELECT id FROM documents WHERE source_id = ?", (source.id,)
            ).fetchall()
        ]
        for doc_id in doc_ids:
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))

        self.conn.execute("DELETE FROM documents WHERE source_id = ?", (source.id,))
        self.conn.execute("DELETE FROM sources WHERE id = ?", (source.id,))
        self.conn.commit()
        return True

    # ── Document Indexing ──────────────────────────────────────────

    def index_document(
        self,
        source_id: int,
        url: str,
        title: str,
        markdown_content: str,
        content_hash: str,
        source_url: str,
    ) -> int:
        """Index a single document: store it and create FTS chunks."""
        # Check if document already exists with same content
        existing = self.conn.execute(
            "SELECT id, content_hash FROM documents WHERE source_id = ? AND url = ?",
            (source_id, url),
        ).fetchone()

        if existing and existing["content_hash"] == content_hash:
            logger.debug("Skipping unchanged document: %s", url)
            return 0

        # Remove old chunks if re-indexing
        if existing:
            self.conn.execute(
                "DELETE FROM chunks WHERE document_id = ?", (existing["id"],)
            )
            self.conn.execute("DELETE FROM documents WHERE id = ?", (existing["id"],))

        # Insert document
        cursor = self.conn.execute(
            """
            INSERT INTO documents (source_id, url, title, content, content_hash, crawled_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                source_id, url, title, markdown_content,
                content_hash, datetime.now(timezone.utc).isoformat(),
            ),
        )
        doc_id = cursor.lastrowid

        # Chunk and index
        text_chunks: list[TextChunk] = self._chunker.chunk(markdown_content, title)
        for chunk in text_chunks:
            self.conn.execute(
                """
                INSERT INTO chunks (document_id, title, content, url, source_url, chunk_index)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (doc_id, chunk.title, chunk.content, url, source_url, chunk.chunk_index),
            )

        self.conn.commit()
        return len(text_chunks)

    def update_source_stats(self, source_id: int) -> None:
        """Refresh page_count and last_crawled on a source."""
        self.conn.execute(
            """
            UPDATE sources SET
                page_count = (SELECT COUNT(*) FROM documents WHERE source_id = ?),
                last_crawled = ?
            WHERE id = ?
            """,
            (source_id, datetime.now(timezone.utc).isoformat(), source_id),
        )
        self.conn.commit()

    def clear_source_documents(self, source_id: int) -> None:
        """Remove all documents and chunks for a source (for reindexing)."""
        doc_ids = [
            row["id"]
            for row in self.conn.execute(
                "SELECT id FROM documents WHERE source_id = ?", (source_id,)
            ).fetchall()
        ]
        for doc_id in doc_ids:
            self.conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
        self.conn.execute("DELETE FROM documents WHERE source_id = ?", (source_id,))
        self.conn.commit()

    # ── Search ─────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        limit: int = 10,
        source_filter: Optional[str] = None,
    ) -> list[SearchResult]:
        """
        Full-text search across all indexed chunks.
        Uses BM25 ranking and returns highlighted snippets.
        """
        if not query or not query.strip():
            return []

        # Escape FTS5 special characters and build query
        fts_query = self._build_fts_query(query)

        params: list = [fts_query]
        source_clause = ""
        if source_filter:
            source_clause = "AND c.source_url = ?"
            params.append(source_filter)
        params.append(limit)

        sql = f"""
            SELECT
                c.id AS chunk_id,
                c.title,
                snippet(chunks_fts, 1, '**', '**', '...', 64) AS snippet,
                c.url,
                c.source_url,
                rank
            FROM chunks_fts
            JOIN chunks c ON c.id = chunks_fts.rowid
            WHERE chunks_fts MATCH ?
            {source_clause}
            ORDER BY rank
            LIMIT ?
        """

        try:
            cursor = self.conn.execute(sql, params)
            results = []
            for row in cursor.fetchall():
                results.append(
                    SearchResult(
                        chunk_id=row["chunk_id"],
                        title=row["title"],
                        snippet=row["snippet"],
                        url=row["url"],
                        source_url=row["source_url"],
                        rank=row["rank"],
                    )
                )
            return results
        except sqlite3.OperationalError as e:
            logger.warning("FTS query failed: %s (query: %s)", e, fts_query)
            return []

    def _build_fts_query(self, query: str) -> str:
        """
        Build a safe FTS5 query from user input.
        Splits into terms and joins with implicit AND.
        """
        # Remove FTS5 special chars
        cleaned = ""
        for ch in query:
            if ch.isalnum() or ch in (" ", "_", "-"):
                cleaned += ch
            else:
                cleaned += " "

        terms = cleaned.split()
        if not terms:
            return '""'

        # Use prefix matching for better recall
        fts_terms = [f'"{t}"*' for t in terms if t]
        return " AND ".join(fts_terms)

    def get_document(self, doc_id: int) -> Optional[Document]:
        row = self.conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
        if not row:
            return None
        return Document(
            id=row["id"],
            source_id=row["source_id"],
            url=row["url"],
            title=row["title"],
            content=row["content"],
            content_hash=row["content_hash"],
            crawled_at=row["crawled_at"],
        )

    def get_chunk(self, chunk_id: int) -> Optional[Chunk]:
        row = self.conn.execute(
            "SELECT * FROM chunks WHERE id = ?", (chunk_id,)
        ).fetchone()
        if not row:
            return None
        return Chunk(
            id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            content=row["content"],
            url=row["url"],
            source_url=row["source_url"],
            chunk_index=row["chunk_index"],
        )

    # ── Statistics ─────────────────────────────────────────────────

    def get_stats(self) -> IndexStats:
        total_sources = self.conn.execute(
            "SELECT COUNT(*) FROM sources"
        ).fetchone()[0]
        total_documents = self.conn.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]
        total_chunks = self.conn.execute(
            "SELECT COUNT(*) FROM chunks"
        ).fetchone()[0]

        db_size = 0.0
        if os.path.exists(self.db_path):
            db_size = os.path.getsize(self.db_path) / (1024 * 1024)

        sources_summary: list[SourceSummary] = []
        for source in self.list_sources():
            chunk_count = self.conn.execute(
                """
                SELECT COUNT(*) FROM chunks
                WHERE document_id IN (SELECT id FROM documents WHERE source_id = ?)
                """,
                (source.id,),
            ).fetchone()[0]

            sources_summary.append(
                SourceSummary(
                    url=source.url,
                    title=source.title,
                    page_count=source.page_count,
                    chunk_count=chunk_count,
                    last_crawled=source.last_crawled,
                )
            )

        return IndexStats(
            total_sources=total_sources,
            total_documents=total_documents,
            total_chunks=total_chunks,
            db_size_mb=round(db_size, 2),
            sources=sources_summary,
        )

    # ── Helpers ────────────────────────────────────────────────────

    def _row_to_source(self, row: sqlite3.Row) -> Source:
        inc = json.loads(row["include_patterns"]) if row["include_patterns"] else None
        exc = json.loads(row["exclude_patterns"]) if row["exclude_patterns"] else None
        return Source(
            id=row["id"],
            url=row["url"],
            title=row["title"],
            crawl_depth=row["crawl_depth"],
            include_patterns=inc,
            exclude_patterns=exc,
            last_crawled=row["last_crawled"],
            page_count=row["page_count"],
            created_at=row["created_at"],
        )
