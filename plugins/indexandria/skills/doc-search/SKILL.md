---
name: doc-search
description: Crawl web documentation into context for accurate, up-to-date coding assistance. Supports quick single-page lookups and deep multi-page indexing with search.
---

# Indexandria — Documentation Fetcher

You have access to Indexandria's MCP tools for pulling web documentation into the conversation. Nothing is stored on disk — all content lives in memory for the session.

## Two Workflows

### Quick Mode — `crawl_docs`

Best for **1-15 pages**. Content goes directly into context.

```
crawl_docs("https://react.dev/reference/react/useEffect", depth=1)
```

Use when:
- User provides a specific docs URL
- You need a single API reference page
- User says "check the docs" for a specific topic

### Deep Mode — `index_docs` + `get_indexed_page` + `search_indexed`

Best for **20-100 pages**. Crawls everything into memory, returns a compact index. You then selectively retrieve only the pages you need.

```
# Step 1: Index the docs (returns a table of contents, not full content)
index_docs("https://fastapi.tiangolo.com/tutorial/", depth=2, max_pages=50)

# Step 2: Search for what you need
search_indexed("OAuth2")

# Step 3: Read the relevant pages
get_indexed_page([12, 15])
```

Use when:
- Working with a full framework or library
- User asks to "learn" or "study" documentation
- Multiple related topics need to be referenced
- A large reference site needs targeted navigation

## Choosing the Right Mode

| Scenario | Mode | Example |
|----------|------|---------|
| Single API/hook/function | Quick, `depth=1` | `crawl_docs("https://react.dev/reference/react/useEffect")` |
| One tutorial page | Quick, `depth=1` | `crawl_docs("https://fastapi.tiangolo.com/tutorial/first-steps/", depth=1)` |
| Tutorial section with subpages | Quick, `depth=2` | `crawl_docs("https://docs.python.org/3/tutorial/classes.html")` |
| Full framework docs | Deep | `index_docs("https://fastapi.tiangolo.com/tutorial/", max_pages=60)` |
| Large API reference | Deep + patterns | `index_docs("https://react.dev/reference/", include_patterns=["*/reference/*"])` |
| Unknown docs structure | Deep, low pages | `index_docs(url, max_pages=30)` then browse the index |

## Using Docs While Writing Code

When you have indexed documentation, follow this pattern before writing implementation code:

1. **Search before implementing.** Before writing code that uses a library API, call `search_indexed` for the specific function, class, or pattern you need. Do not rely on memory — the docs are right there.

2. **Read the relevant pages.** Use `get_indexed_page` to pull in the full content of pages that match your search. Read them carefully.

3. **Verify parameters and return types.** If the docs specify exact parameter names, types, or return values, use them as written. Do not guess.

4. **Re-search when unsure.** If mid-implementation you are unsure about a behavior, call `search_indexed` again rather than making assumptions.

## Tool Reference

### `crawl_docs(url, depth=2, max_pages=15, include_patterns=None, exclude_patterns=None)`

Crawl and return content directly. Output capped at ~110 KB.

### `index_docs(url, depth=2, max_pages=50, include_patterns=None, exclude_patterns=None)`

Crawl up to 100 pages into memory. Returns a compact index table (page number, title, headings). Pages stay in memory until the next `index_docs` call or session end.

### `get_indexed_page(page_numbers)`

Retrieve full content of specific pages by number (1-based). Example: `get_indexed_page([1, 5, 12])`. Output capped at ~110 KB — request fewer pages if hitting the limit.

### `search_indexed(query, max_results=10)`

Case-insensitive keyword search across all indexed pages. Returns matching snippets with page numbers and context. Use results to decide which pages to read fully.

## Tips

- **Be specific with URLs** — point to the relevant section, not the site root.
- **Use `include_patterns`** to stay within a docs section: `["*/reference/*"]`
- **Use `depth=1`** when you only need a single page.
- **Deep index first, read selectively** — for large sites, index everything but only read what you need.
- **Re-index when switching topics** — `index_docs` replaces the previous index.

## Example: Full Workflow

```
User: "Build a FastAPI app with OAuth2 and JWT authentication"

1. index_docs("https://fastapi.tiangolo.com/tutorial/", depth=2, max_pages=60)
   → Returns index: 45 pages covering tutorial sections

2. search_indexed("OAuth2")
   → Matches: Page 23 (Security - OAuth2), Page 24 (OAuth2 with JWT)

3. get_indexed_page([23, 24])
   → Full content of OAuth2 tutorial pages

4. search_indexed("dependency injection")
   → Matches: Page 8 (Dependencies), Page 9 (Dependencies in path operations)

5. get_indexed_page([8, 9])
   → Full content of dependency injection pages

6. Write the implementation using the docs as reference
```
