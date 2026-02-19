---
name: doc-search
description: Crawl web documentation into context for accurate, up-to-date coding assistance. Use when working with any library, framework, or API whose docs can be fetched from a URL.
---

# Documentation Fetcher

You have access to the `crawl_docs` tool via Indexandria. It crawls web pages and returns their content as markdown directly into the conversation — nothing is stored on disk.

## When to Use

- **User provides a docs URL** — Crawl it to get the full content into context.
- **Working with a library/framework** — If you need accurate API details, crawl the relevant docs page.
- **User says "check the docs"** — Use `crawl_docs` on the appropriate documentation URL.

## How to Use

Call `crawl_docs` with targeted URLs. Be specific — point to the relevant section, not the entire site.

Good:
```
crawl_docs("https://react.dev/reference/react/useEffect")
crawl_docs("https://fastapi.tiangolo.com/tutorial/first-steps/", depth=1)
```

Avoid crawling an entire site when you only need one page:
```
crawl_docs("https://react.dev", depth=3)  # too broad — will be slow and use lots of context
```

## Tips

- Use `depth=1` for a single page, `depth=2` to include linked subpages.
- Use `max_pages` to cap how many pages are fetched (default 15, max 50).
- Use `include_patterns` to stay within a docs section: `["*/reference/*"]`
- Output is capped at ~110 KB to fit within MCP token limits. If a crawl is too large, remaining pages are noted but omitted.
- The content goes straight into the conversation context. Keep crawls focused to preserve context space.
