---
name: astr-kb-list-documents
description: List all documents in a knowledge base with doc_id, file_name, type, and size.
---

# Tool: `astr_kb_list_documents` — List Documents in a KB

## When to use
Before reading a document's content or when the user asks what files are in a KB. The output provides `doc_id` required by `astr_kb_get_document`.

## Instructions
1. Call `astr_kb_list()` first if you don't have the `kb_id`.
2. Call `astr_kb_list_documents(kb_id="...")`.
3. Report the list to the user with doc_id and file_name.

## Rules
- Requires `kb_id` from `astr_kb_list`.
- Output respects the plugin's access control (whitelist/blacklist).
