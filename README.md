# Indexandria

**Crawl and index any web documentation, then let Claude Code use it as context while you write code.**

Indexandria is a [Claude Code](https://code.claude.com) plugin inspired by Cursor's built-in documentation indexer. Point it at any documentation URL, and it will crawl the pages, chunk the content intelligently, and build a local full-text search index. Claude then automatically searches this index whenever you're working with the indexed technologies — no manual lookups needed.

*Named after the Great Library of Alexandria.*

## Why Indexandria?

- You're working with a framework whose docs Claude doesn't know well enough
- You want Claude to reference your company's internal documentation
- You need precise, up-to-date API information instead of stale training data
- You want Cursor-style doc indexing inside Claude Code

## Features

- **Deep Crawling** — Follow links up to 3 levels deep with URL pattern filtering
- **Full-Text Search** — SQLite FTS5 with BM25 relevance ranking, no external services needed
- **Smart Chunking** — Heading-aware splitting preserves document structure and context
- **Automatic Lookup** — Claude searches the index on its own when writing related code
- **Persistent Index** — Indexed docs survive across sessions, no need to re-crawl every time
- **Source Management** — Add, remove, reindex, and list documentation sources on the fly

## Quick Start

### Install

```
/plugin marketplace add alicankiraz1/indexandria
/plugin install indexandria@indexandria
```

Requires Claude Code v1.0.33+, Python 3.10+, and [uv](https://docs.astral.sh/uv/).

### Use

Index some docs:

```
> Index the React docs: https://react.dev/reference
```

Then just code — Claude will search the index automatically:

```
> Build a custom hook that debounces API calls
```

Or search explicitly:

```
> /indexandria:doc-search useEffect cleanup function
```

## All MCP Tools

| Tool | What it does |
|------|-------------|
| `crawl_and_index` | Crawl a URL (configurable depth & URL filters) and index its content |
| `search_docs` | Full-text search across all indexed documentation |
| `get_document` | Retrieve the full content of a specific indexed page |
| `list_sources` | Show all indexed documentation sources with stats |
| `remove_source` | Delete a source and all its indexed data |
| `reindex_source` | Re-crawl a source to pick up documentation updates |
| `get_index_stats` | Show index size, chunk counts, and per-source breakdown |

## How It Works

```
You ask Claude a question
        │
        ▼
  ┌─────────────┐     ┌──────────────┐     ┌─────────────┐
  │  doc-search  │────▶│  MCP Server  │────▶│ SQLite FTS5 │
  │   (Skill)    │     │  (FastMCP)   │     │   (Index)   │
  └─────────────┘     └──────────────┘     └─────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Crawler  │  │ Chunker  │  │ Indexer   │
        │httpx+BS4 │  │ heading  │  │  BM25     │
        │+markdown │  │  aware   │  │ ranking   │
        └──────────┘  └──────────┘  └──────────┘
```

1. **Crawl** — `httpx` fetches pages, `BeautifulSoup4` extracts content, `markdownify` converts to clean Markdown
2. **Chunk** — Documents are split by headings first, then by size (~1500 chars) with overlap for context continuity
3. **Index** — Chunks are stored in SQLite with FTS5 virtual tables using Porter stemming and Unicode tokenization
4. **Search** — BM25 ranking returns the most relevant chunks with highlighted snippets

All data is stored locally at `~/.indexandria/index.db`.

## Local Development

```bash
git clone https://github.com/alicankiraz1/indexandria.git
cd indexandria/plugins/indexandria/servers/indexer
uv sync

# Test the plugin without installing
claude --plugin-dir ../../
```

## Contributing

Issues and pull requests are welcome at [github.com/alicankiraz1/indexandria](https://github.com/alicankiraz1/indexandria).

## License

MIT
