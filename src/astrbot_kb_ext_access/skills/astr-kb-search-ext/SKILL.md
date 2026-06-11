---
name: astr-kb-search-ext
description: Search knowledge bases with plugin access control. Use instead of built-in astr_kb_search when the target KB is under whitelist/blacklist management.
---

<!--
MIT License

Copyright (c) 2026 Mingxi "Lucien" Du

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
-->

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
