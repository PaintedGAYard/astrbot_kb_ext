---
name: astrbot-kb-ext-access-skills
description: Plugin overview — delegates to per-tool skill files in sibling folders.
---

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
```

## General rules
- Always `astr_kb_list` first to get kb_id before file operations
- Report results with key info: doc_id, chunk count, success/failure
- Delete ops MUST ask user confirmation first
