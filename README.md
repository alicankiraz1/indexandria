# Indexandria

A Claude Code plugin that crawls and indexes web documentation, making it available as context while coding. Works like Cursor's built-in documentation indexer.

*Named after the Great Library of Alexandria — your own documentation library for Claude Code.*

## Features

- **URL Crawling**: Crawl documentation sites with configurable depth and URL patterns
- **Full-Text Search**: SQLite FTS5 powered search with BM25 relevance ranking
- **Smart Chunking**: Heading-aware text splitting for optimal search results
- **Auto-Context**: Claude automatically searches indexed docs when writing code
- **Source Management**: Add, remove, reindex, and list documentation sources

## Requirements

- Claude Code v1.0.33 or later
- Python 3.10+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

### Step 1: Add the Marketplace

In Claude Code, run:

```
/plugin marketplace add alicankiraz/indexandria
```

### Step 2: Install the Plugin

```
/plugin install indexandria@indexandria
```

That's it! The MCP server and skill are now active.

### Alternative: Local Development

```bash
git clone https://github.com/alicankiraz/indexandria.git
cd indexandria

# Install Python dependencies
cd plugins/indexandria/servers/indexer && uv sync && cd ../../../..

# Run Claude Code with the plugin loaded locally
claude --plugin-dir ./plugins/indexandria
```

## Usage

### Index Documentation

Ask Claude to index a documentation URL:

```
> Index the React documentation: https://react.dev/reference
```

Or use the search skill directly:

```
> /indexandria:doc-search useEffect cleanup function
```

### Automatic Usage

Once documentation is indexed, Claude automatically searches the index when you ask coding questions related to the indexed content:

```
> How do I use the useEffect hook with cleanup?
> Write a Next.js API route with error handling
```

### Manage Sources

```
> List all indexed documentation sources
> Remove the React docs from the index
> Reindex the Next.js documentation
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `crawl_and_index` | Crawl a URL and index its content |
| `search_docs` | Search indexed documentation |
| `get_document` | Retrieve a specific document |
| `list_sources` | List all indexed sources |
| `remove_source` | Remove a source and its documents |
| `reindex_source` | Re-crawl and update an existing source |
| `get_index_stats` | Get index statistics |

## Architecture

```
Indexandria Plugin
├── MCP Server (Python/FastMCP)
│   ├── Crawler (httpx + BeautifulSoup4 + markdownify)
│   ├── Chunker (heading-based + size-based splitting)
│   └── Indexer (SQLite FTS5)
└── Skill (doc-search)
    └── Guides Claude on when/how to search indexed docs
```

## Data Storage

Indexed data is stored in `~/.indexandria/index.db` (SQLite database). The database uses FTS5 virtual tables for fast full-text search with BM25 ranking.

## License

MIT
