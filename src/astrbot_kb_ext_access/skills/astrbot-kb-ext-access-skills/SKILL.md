---
name: astrbot-kb-ext-access-skills
description: Plugin overview — delegates to per-tool skill files in sibling folders.
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

# AstrBot KB External Access — Tool Index

This plugin provides tools for knowledge base management with access control.

## Available tools and their skill files

| Tool / Strategy | Skill folder | Purpose |
|----------------|-------------|---------|
| `astr_kb_list` | `astr-kb-list/` | List KBs to get kb_id |
| `astr_kb_estimate_upload_time` | `astr-kb-estimate-upload-time/` | Estimate vectorization time |
| **Strategy A & B** (sync/batch) | `astr-kb-upload-fast/` | Upload files < 100s |
| **Strategy C** (async) | `astr-kb-upload-async/` | Upload files > 100s with FutureTask |
| `astr_kb_check_upload` | `astr-kb-check-upload/` | Check async upload status |
| `astr_kb_create` | `astr-kb-create/` | Create a new KB |
| `astr_kb_delete` | `astr-kb-delete/` | Delete an entire KB |
| `astr_kb_delete_document` | `astr-kb-delete-document/` | Delete a document from a KB |
| `astr_kb_list_documents` | `astr-kb-list-documents/` | List all documents in a KB |
| `astr_kb_get_document_content_chunk` | `astr-kb-get-document/` | Get one text chunk by index |
| `astr_kb_search_ext` | `astr-kb-search-ext/` | Access-controlled search |

## HARD RULES (apply to all tools)
1. Before ANY deletion, ask the user for confirmation unless they explicitly say "skip confirmation".
2. Before ANY upload, call `astr_kb_list` first to get the kb_id.
3. NEVER use `astrbot_execute_shell sleep` to wait for uploads. Use `future_task` instead.
4. NEVER launch multiple `wait_completion=false` uploads concurrently — the tool rejects them.
5. After `astr_kb_upload(wait_completion=false)`, you MUST schedule a `future_task`. Do NOT actively poll.
6. Always report results with key info: doc_id, chunk count, success/failure.

## Supported file formats (exhaustive)
| Category | Extensions |
|----------|-----------|
| Plain text | `.txt` |
| Markdown | `.md` `.markdown` `.mkd` `.mdx` |
| Structured text | `.rst` `.adoc` |
| PDF | `.pdf` |
| eBook | `.epub` |
| Word | `.docx` ONLY — `.doc` is NOT supported |
| Excel | `.xls` `.xlsx` BOTH supported |

For any other format (e.g. `.doc`, `.ppt`), extract text first and upload as `.md`.
