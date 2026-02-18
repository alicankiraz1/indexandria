---
name: doc-search
description: Search indexed documentation when working with libraries, frameworks, or APIs. Use this skill whenever you need to look up documentation that has been previously indexed, or when the user asks about a technology whose docs have been crawled.
---

# Documentation Search

You have access to an indexed documentation database through the Indexandria MCP tools. Use these tools to provide accurate, up-to-date information from the user's indexed documentation sources.

## When to Search

Automatically search the index in these situations:

1. **Writing code with a framework/library**: When implementing features using React, Next.js, Django, FastAPI, or any indexed technology, search for relevant API docs, patterns, and examples.
2. **Answering API questions**: When the user asks "how do I use X?" or "what are the options for Y?", search the index first before relying on general knowledge.
3. **Debugging**: When troubleshooting errors related to indexed libraries, search for known issues, configuration guides, and troubleshooting docs.
4. **Configuration and setup**: When setting up tools, build systems, or deployment configurations, search for the official setup guides.
5. **User explicitly asks**: When the user says "check the docs", "look it up", "search documentation", or similar.

## How to Search

1. First use `list_sources` to see what documentation is available.
2. Use `search_docs` with specific, targeted queries:
   - Good: `search_docs("useEffect cleanup function")` 
   - Good: `search_docs("API route error handling", source_filter="https://nextjs.org")`
   - Bad: `search_docs("react")` (too broad)
3. If a result looks promising but you need more context, use `get_document` with the document ID to retrieve the full page content.
4. Cite the source URL when referencing documentation in your responses.

## Managing the Index

- Use `crawl_and_index` when the user wants to add new documentation sources.
- Use `reindex_source` when documentation might be outdated.
- Use `remove_source` to clean up sources no longer needed.
- Use `get_index_stats` to show what's currently indexed.

## Best Practices

- **Be specific**: Use targeted search queries with key terms rather than broad phrases.
- **Cross-reference**: When results seem incomplete, try rephrasing the query or searching with different terms.
- **Cite sources**: Always mention the documentation URL when referencing indexed content.
- **Stay current**: If the user mentions a version mismatch, suggest reindexing the source.
