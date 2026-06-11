---
name: astr-kb-create
description: Create a new knowledge base with optional embedding and rerank provider selection.
---

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
