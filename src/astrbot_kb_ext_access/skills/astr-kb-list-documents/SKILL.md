---
name: astr-kb-list-documents
description: List all documents in a knowledge base with doc_id, file_name, type, and size.
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
