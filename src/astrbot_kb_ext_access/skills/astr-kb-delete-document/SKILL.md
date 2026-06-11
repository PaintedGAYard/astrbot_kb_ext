---
name: astr-kb-delete-document
description: Permanently delete a specific document from a knowledge base. IRREVERSIBLE — requires user confirmation.
---

# Tool: `astr_kb_delete_document` — Delete Document (IRREVERSIBLE)

## When to use
When the user asks to delete a specific file or document from a knowledge base.

## Instructions
1. Call `astr_kb_list()` to get the `kb_id`.
2. Identify the document to delete. Use `astr_kb_search_ext` if needed to find the `doc_id`.
3. Ask the user for confirmation with the document name/ID.
4. ONLY if the user explicitly confirms, call:
   ```json
   {
     "kb_id": "<kb_id>",
     "doc_id": "<doc_id>",
     "confirm": true
   }
   ```
   Or use `file_name` instead of `doc_id` for keyword matching.

## Rules
- You MUST ask for user confirmation before setting `confirm=true`.
- Provide both the KB name and document name when asking for confirmation.
