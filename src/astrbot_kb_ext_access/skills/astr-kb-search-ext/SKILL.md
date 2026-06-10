---
name: astr-kb-search-ext
description: Search knowledge bases with plugin access control. Use instead of built-in astr_kb_search when the target KB is under whitelist/blacklist management.
---

# Tool: `astr_kb_search_ext` — Search (Access-Controlled)

## When to use this tool
Two search tools exist. Use this decision flow to pick the right one:

```
User mentions a specific KB by name?
  ├── YES → Is the KB in the plugin's whitelist?
  │     ├── YES → Use astr_kb_search_ext
  │     └── NO  → Use built-in astr_kb_search
  ├── YES → KB was just created by this plugin → Use astr_kb_search_ext
  └── NO  (vague request like "search the KBs")
        → Use built-in astr_kb_search FIRST
        → If no results, suggest astr_kb_search_ext
```

## Parameters
| Param | Required | Description |
|-------|----------|-------------|
| `query` | Yes | Search query string. |

## Comparison
| Tool | Search scope | Access control |
|------|-------------|----------------|
| Built-in `astr_kb_search` | Dashboard-global KB config | None (fixed by admin) |
| Plugin `astr_kb_search_ext` | Plugin whitelist only | Yes — respects whitelist/blacklist |

## Instructions
1. Determine which tool to use using the decision flow above.
2. Call `astr_kb_search_ext(query="user's question")`.
3. Report the results to the user with relevant snippets and source KB info.

## Rules
- When in doubt, try the built-in search first — it covers more KBs.
- If the KB was created by this plugin, always use `astr_kb_search_ext` even if the KB might not be in the dashboard config yet.
