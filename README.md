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

## Installation

### Prerequisites

- Claude Code v1.0.33+
- Python 3.10+
- [uv](https://docs.astral.sh/uv/)

### Step 1: Install the Plugin

```
/plugin marketplace add alicankiraz1/indexandria
/plugin install indexandria@indexandria
```

### Step 2: Start the Server

Indexandria runs as a local HTTP server that you control. Open a terminal and run:

```bash
# Clone the repo (first time only)
git clone https://github.com/alicankiraz1/indexandria.git ~/.indexandria/repo

# Start the server
~/.indexandria/repo/plugins/indexandria/servers/indexer/start.sh
```

The server starts on `http://localhost:21517/mcp` and runs in the background. To stop it:

```bash
~/.indexandria/repo/plugins/indexandria/servers/indexer/start.sh stop
```

### Step 3: Use It

Open Claude Code and start indexing:

```
> Index the React docs: https://react.dev/reference
```

## Usage Examples

**Index documentation:**
```
> Index https://fastapi.tiangolo.com with depth 2
```

**Automatic context** — just code, Claude searches the index on its own:
```
> Build a FastAPI endpoint with request validation
```

**Explicit search:**
```
> /indexandria:doc-search useEffect cleanup function
```

**Manage sources:**
```
> List all indexed documentation sources
> Reindex the FastAPI docs
> Remove the React docs from the index
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

## Security & Privacy

Indexandria is designed with transparency in mind:

- **HTTP transport** — The plugin connects to the server via `http://localhost:21517/mcp`. It does not execute commands on your machine. You start and stop the server yourself.
- **Local only** — All data stays on your machine at `~/.indexandria/index.db`. Nothing is sent to external services.
- **No file system access** — The server only reads from the web (URLs you provide) and writes to its own SQLite database. It does not access your project files.
- **Open source** — Every line of code is auditable in this repository.
- **User controlled** — You decide when the server runs, which URLs to index, and when to stop it.

## Advanced

### Custom Port

```bash
# Start on a different port
~/.indexandria/repo/plugins/indexandria/servers/indexer/start.sh 9000
```

Then update the MCP connection in Claude Code:
```
claude mcp add --transport http indexandria http://localhost:9000/mcp
```

### Stdio Mode (for advanced users)

If you prefer the traditional stdio transport:

```bash
claude mcp add --transport stdio indexandria -- \
  uv run --directory ~/.indexandria/repo/plugins/indexandria/servers/indexer server.py --stdio
```

## Contributing

Issues and pull requests are welcome at [github.com/alicankiraz1/indexandria](https://github.com/alicankiraz1/indexandria).

## License

MIT
