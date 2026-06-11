---
name: astr-kb-create
description: Create a new knowledge base with optional embedding and rerank provider selection.
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

# Tool: `astr_kb_create` — Create Knowledge Base

## When to use
When the user asks to create a new knowledge base. The created KB is automatically added to the plugin's whitelist (if whitelist mode is active).

## Instructions
1. Call `astr_kb_list()` first to check if a similar KB already exists.
2. Call `astr_kb_create(kb_name="...", description="...")`.
3. The tool auto-adds the new KB to the whitelist.
4. After creation, use `astr_kb_search_ext` to verify the KB is searchable.

## Rules
- The new KB is auto-whitelisted. You do NOT need to manually configure access.
- If the user wants to use a specific embedding model, pass a keyword — the tool does fuzzy matching against available providers.
