---
name: astr-kb-delete-document
description: Permanently delete a specific document from a knowledge base. IRREVERSIBLE — requires user confirmation.
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
