"""Smart text chunking for documentation indexing.

Splits markdown content into chunks using a two-pass approach:
1. Split on headings to preserve document structure
2. Split oversized sections by paragraph/size boundaries
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


HEADING_PATTERN = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)

DEFAULT_MAX_CHUNK_SIZE = 1500
DEFAULT_OVERLAP_SIZE = 200
DEFAULT_MIN_CHUNK_SIZE = 100


@dataclass
class TextChunk:
    """A single chunk of text with metadata."""

    content: str
    title: str = ""
    chunk_index: int = 0
    headings: list[str] = field(default_factory=list)


class Chunker:
    """Splits markdown documents into indexed chunks."""

    def __init__(
        self,
        max_chunk_size: int = DEFAULT_MAX_CHUNK_SIZE,
        overlap_size: int = DEFAULT_OVERLAP_SIZE,
        min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
    ):
        self.max_chunk_size = max_chunk_size
        self.overlap_size = overlap_size
        self.min_chunk_size = min_chunk_size

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """
        Split text into sections based on markdown headings.
        Returns a list of (heading, content) tuples.
        """
        sections: list[tuple[str, str]] = []
        matches = list(HEADING_PATTERN.finditer(text))

        if not matches:
            return [("", text)]

        # Content before the first heading
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

        for i, match in enumerate(matches):
            heading = match.group(2).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()

            # Include the heading in the content for context
            full_content = f"{match.group(0)}\n\n{content}" if content else match.group(0)
            sections.append((heading, full_content))

        return sections

    def _split_large_section(self, text: str) -> list[str]:
        """
        Split an oversized section into smaller chunks by paragraphs,
        with overlap for context continuity.
        """
        paragraphs = re.split(r"\n\n+", text)
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_size = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            para_size = len(para)

            # Single paragraph exceeds max — hard split by character
            if para_size > self.max_chunk_size:
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                for i in range(0, para_size, self.max_chunk_size - self.overlap_size):
                    segment = para[i : i + self.max_chunk_size]
                    chunks.append(segment)
                continue

            if current_size + para_size + 2 > self.max_chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))

                # Keep last paragraph(s) as overlap
                overlap_text = ""
                overlap_parts: list[str] = []
                for p in reversed(current_chunk):
                    if len(overlap_text) + len(p) > self.overlap_size:
                        break
                    overlap_parts.insert(0, p)
                    overlap_text = "\n\n".join(overlap_parts)

                current_chunk = overlap_parts
                current_size = len(overlap_text)

            current_chunk.append(para)
            current_size += para_size + 2

        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def chunk(self, text: str, document_title: str = "") -> list[TextChunk]:
        """
        Split a markdown document into chunks.

        Strategy:
        1. Split by headings to respect document structure
        2. Merge small adjacent sections
        3. Split oversized sections with overlap
        """
        if not text or not text.strip():
            return []

        sections = self._split_by_headings(text)
        raw_chunks: list[TextChunk] = []
        heading_stack: list[str] = []

        if document_title:
            heading_stack.append(document_title)

        for heading, content in sections:
            if heading:
                heading_stack = heading_stack[:1]
                heading_stack.append(heading)

            if len(content) <= self.max_chunk_size:
                if (
                    raw_chunks
                    and len(content) < self.min_chunk_size
                    and len(raw_chunks[-1].content) + len(content) + 2
                    <= self.max_chunk_size
                ):
                    # Merge small sections into previous chunk
                    raw_chunks[-1].content += "\n\n" + content
                    if heading and heading not in raw_chunks[-1].headings:
                        raw_chunks[-1].headings.append(heading)
                else:
                    chunk_title = " > ".join(heading_stack) if heading_stack else ""
                    raw_chunks.append(
                        TextChunk(
                            content=content,
                            title=chunk_title,
                            headings=list(heading_stack),
                        )
                    )
            else:
                sub_chunks = self._split_large_section(content)
                chunk_title = " > ".join(heading_stack) if heading_stack else ""
                for sub in sub_chunks:
                    raw_chunks.append(
                        TextChunk(
                            content=sub,
                            title=chunk_title,
                            headings=list(heading_stack),
                        )
                    )

        # Assign sequential indices
        for i, chunk in enumerate(raw_chunks):
            chunk.chunk_index = i

        # Filter out empty/too-small chunks
        return [c for c in raw_chunks if len(c.content.strip()) >= self.min_chunk_size]
