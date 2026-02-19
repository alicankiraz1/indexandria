# Indexandria

**Crawl any web documentation and pull it straight into Claude Code's context.**

Indexandria is a [Claude Code](https://code.claude.com) plugin that fetches documentation from any URL, converts it to clean markdown, and returns it directly into the conversation. Claude then uses this content as context while writing code — no database, no background server, no disk writes.

*Named after the Great Library of Alexandria.*

## Install

```
/plugin marketplace add alicankiraz1/indexandria
/plugin install indexandria@indexandria
```

Requires Python 3.10+ and [uv](https://docs.astral.sh/uv/).

## Quick Start

Tell Claude to fetch some docs:

```
> Crawl https://fastapi.tiangolo.com/tutorial/ and then build me an API with validation
```

For larger documentation sites, use deep indexing:

```
> Index the full React reference docs, then help me build a custom hook
```

## Two Workflows

### Quick Mode — Small, Focused Crawls

`crawl_docs` fetches 1-15 pages and returns content directly into context. Best for single API lookups and short tutorials.

```
"Crawl the useEffect docs"
       │
       ▼
 ┌───────────┐     ┌────────────┐     ┌───────────┐
 │  Claude    │────▶│ crawl_docs │────▶│  Crawler   │
 │  Code      │     │ (MCP tool) │     │ httpx+BS4  │
 └───────────┘     └────────────┘     └───────────┘
       │                                     │
       │          markdown content           │
       │◀────────────────────────────────────┘
       ▼
 Claude writes code using the docs
```

### Deep Mode — Large Documentation Sites

`index_docs` crawls up to 100 pages into memory and returns a compact table of contents. Claude then uses `search_indexed` and `get_indexed_page` to selectively read only what's needed.

```
"Index the FastAPI tutorial, then build OAuth2 auth"
       │
       ▼
 ┌───────────┐     ┌────────────┐     ┌───────────┐
 │  Claude    │────▶│ index_docs │────▶│  Crawler   │
 │  Code      │     │            │     │ (100 pages)│
 └───────────┘     └────────────┘     └───────────┘
       │                                     │
       │          compact index (TOC)        │
       │◀────────────────────────────────────┘
       │
       ├── search_indexed("OAuth2") ──▶ page 23, 24
       │
       ├── get_indexed_page([23, 24]) ──▶ full content
       │
       ▼
 Claude writes code with precise docs reference
```

**No database. No files. No background process.** Everything lives in memory for the session.

## Tools

### `crawl_docs` — Quick mode

| Parameter | Default | Description |
|-----------|---------|-------------|
| `url` | required | Starting URL to crawl |
| `depth` | 2 | Link levels to follow (1-3) |
| `max_pages` | 15 | Maximum pages to fetch (up to 50) |
| `include_patterns` | none | URL globs to include (e.g. `["*/docs/*"]`) |
| `exclude_patterns` | none | URL globs to exclude (e.g. `["*/blog/*"]`) |

### `index_docs` — Deep mode

| Parameter | Default | Description |
|-----------|---------|-------------|
| `url` | required | Starting URL to crawl |
| `depth` | 2 | Link levels to follow (1-3) |
| `max_pages` | 50 | Maximum pages to index (up to 100) |
| `include_patterns` | none | URL globs to include |
| `exclude_patterns` | none | URL globs to exclude |

### `get_indexed_page` — Read from index

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page_numbers` | required | List of 1-based page numbers (e.g. `[1, 5, 12]`) |

### `search_indexed` — Search across index

| Parameter | Default | Description |
|-----------|---------|-------------|
| `query` | required | Search term (case-insensitive) |
| `max_results` | 10 | Maximum matches to return |

Output from all tools is capped at ~110 KB to stay within Claude Code's MCP token limit.

## Tips

- **Be specific** — point to the relevant docs section, not the entire site
- **Quick mode** for 1-5 pages, **deep mode** for 20+ pages
- **Use include_patterns** to stay within a docs section: `["*/reference/*"]`
- **Search before reading** — with deep mode, search first to find the right pages
- Only `http` and `https` URLs are accepted

## Security & Privacy

- **No data stored** — nothing is written to disk, ever
- **No external services** — all processing is local
- **URL validation** — only http/https schemes are allowed
- **Session-scoped** — indexed content exists only in memory, cleared when the session ends
- **Open source** — the entire codebase is ~500 lines of Python

## Contributing

[github.com/alicankiraz1/indexandria](https://github.com/alicankiraz1/indexandria)

## License

MIT
