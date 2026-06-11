---
name: astr-kb-list
description: List available knowledge bases with kb_id, used as prerequisite for all KB operations.
---

# Tool: `astr_kb_list` — List Knowledge Bases

## When to use
Call this tool BEFORE any knowledge base operation (upload, create, delete, search). It returns the `kb_id` required by all other KB tools. The output is pre-filtered by the plugin's whitelist/blacklist configuration.

## Instructions
1. Call `astr_kb_list()` with a `query` if you know part of the KB name, otherwise call without parameters.
2. Read the returned list to find the target KB's `kb_id`.
3. Use that `kb_id` in subsequent tool calls.

## Rules
- You MUST call this tool before ANY upload, delete, or search operation.
- Do NOT hardcode kb_id — always fetch it fresh.
