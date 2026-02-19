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

## Use

Tell Claude to fetch some docs:

```
> Crawl https://fastapi.tiangolo.com/tutorial/ and then build me an API with validation
```

Or use the skill directly:

```
> /indexandria:doc-search https://react.dev/reference/react/useEffect
```

Claude will crawl the pages, pull the content into context, and use it while writing code. That's it.

## How It Works

```
"Crawl the FastAPI docs"
        │
        ▼
  ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
  │   Claude     │────▶│  crawl_docs  │────▶│   Crawler    │
  │   Code       │     │  (MCP tool)  │     │ httpx + BS4  │
  └─────────────┘     └──────────────┘     └──────────────┘
        │                                          │
        │              markdown content            │
        │◀─────────────────────────────────────────┘
        │
        ▼
  Claude writes code using the docs as context
```

1. You mention a URL or ask about a framework
2. Claude calls `crawl_docs` with the URL
3. The crawler fetches pages, strips noise, converts to markdown
4. Content goes straight into the conversation context
5. Claude uses it to write accurate code

**No database. No files. No background process.** Everything lives in the conversation.

## Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `url` | required | Starting URL to crawl |
| `depth` | 2 | Link levels to follow (1-3) |
| `max_pages` | 15 | Maximum pages to fetch (up to 50) |
| `include_patterns` | none | URL globs to include (e.g. `["*/docs/*"]`) |
| `exclude_patterns` | none | URL globs to exclude (e.g. `["*/blog/*"]`) |

Output is automatically capped at ~110 KB to stay within Claude Code's MCP token limit. If a crawl exceeds this, the remaining pages are noted but omitted.

## Tips

- **Be specific** — point to the relevant docs section, not the entire site
- **Use depth=1** for a single page, **depth=2** to pull in linked subpages
- **Cap with max_pages** if you're worried about context space
- **Use include_patterns** to stay within a docs section: `["*/reference/*"]`
- Only `http` and `https` URLs are accepted

## Security & Privacy

- **No data stored** — nothing is written to disk, ever
- **No external services** — all processing is local
- **URL validation** — only http/https schemes are allowed
- **Ephemeral** — content exists only in the current conversation
- **Open source** — the entire codebase is ~180 lines of Python

## Contributing

[github.com/alicankiraz1/indexandria](https://github.com/alicankiraz1/indexandria)

## License

MIT
