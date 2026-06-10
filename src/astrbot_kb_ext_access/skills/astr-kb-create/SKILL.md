---
name: astr-kb-create
description: Create a new knowledge base with optional embedding and rerank provider selection.
---

# Tool: `astr_kb_create` — Create Knowledge Base

## When to use
When the user asks to create a new knowledge base. The created KB is automatically added to the plugin's whitelist (if whitelist mode is active).

## Parameters
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `kb_name` | Yes | — | Short, descriptive name for the KB. |
| `description` | No | "" | What this KB is for. |
| `embedding_provider` | No | "" | Provider ID or name keyword. Leave empty for auto-select. Supports fuzzy matching (e.g. "openai", "bge"). |
| `rerank_provider` | No | "" | Provider ID or name keyword. Leave empty to skip reranking. Supports fuzzy matching. |
| `chunk_size` | No | 512 | Characters per chunk. |
| `chunk_overlap` | No | 50 | Character overlap between chunks. |

## Instructions
1. Call `astr_kb_list()` first to check if a similar KB already exists.
2. Call `astr_kb_create(kb_name="...", description="...")`.
3. The tool auto-adds the new KB to the whitelist.
4. After creation, use `astr_kb_search_ext` to verify the KB is searchable.

## Rules
- The new KB is auto-whitelisted. You do NOT need to manually configure access.
- If the user wants to use a specific embedding model, pass a keyword — the tool does fuzzy matching against available providers.
