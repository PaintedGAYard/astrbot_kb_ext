---
name: astrbot-kb-ext-access-skills
description: 知识库搜索、上传、创建与删除 / Knowledge base listing, upload, creation & deletion
---

# Knowledge Base Management Tools

Use these function tools to interact with AstrBot knowledge bases.
Do NOT use HTTP API or database directly.

**IMPORTANT**: Before ANY deletion, ask the user for confirmation unless they explicitly say "skip confirmation" / "just delete it".

---

## Tool Reference

### `astr_kb_list` — List KBs
When: Before any KB operation to find kb_id.
Output is already filtered by whitelist/blacklist.
Parameters: `query` (optional, name keyword).

### `astr_kb_upload` — Upload file
When: User asks to save/store content to a KB.
Steps: (1) `astr_kb_list` to get kb_id (2) ask user if unspecified (3) upload.

**Upload methods** (choose one):

**A. `sandbox_path` (recommended for binary files)** — pass the file path in the sandbox.
The tool downloads the file directly from the sandbox — no base64 needed.
```python
# Agent reads binary file in sandbox, passes its path:
astr_kb_upload(kb_id="xxx", sandbox_path="/workspace/doc.pdf", file_name="doc.pdf")
```

**B. `file_content`** — for text content or small files.
- Text: `file_content="plain text"`
- Binary with base64: `file_content="base64...", binary=true`

Parameters:
- `kb_id` (required): from astr_kb_list
- `file_name` (required): include extension — determines how AstrBot parses it
- `file_content` (optional): text or base64 data; used only when sandbox_path is empty
- `binary` (optional, default false): set true if file_content is base64-encoded
- `sandbox_path` (optional): path in sandbox — tool downloads directly, no encoding needed
- `chunk_size` (optional, default 512)
- `chunk_overlap` (optional, default 50)

Natively supported formats (exhaustive — files in other formats will be rejected):

| Category | Extensions |
|----------|-----------|
| Plain text | `.txt` |
| Markdown | `.md` `.markdown` `.mkd` `.mdx` |
| Structured text | `.rst` `.adoc` |
| PDF | `.pdf` |
| eBook | `.epub` |
| Word | `.docx` |
| Excel | `.xls` `.xlsx` |

> ⚠️ Only the formats listed above are accepted. For any other format (e.g. `.doc`, `.ppt`), extract text content first and upload as `.txt`.

### `astr_kb_create` — Create KB
When: User asks to create a new knowledge base.
Parameters:
- `kb_name` (required): short descriptive name
- `description` (optional): what this KB is for
- `embedding_provider` (optional): provider ID or keyword; leave blank for auto-select
- `rerank_provider` (optional): provider ID or keyword; leave blank to skip
- `chunk_size` (optional, default 512)
- `chunk_overlap` (optional, default 50)

Note: created KB is auto-added to whitelist. Use `astr_kb_search_ext` afterwards.

### `astr_kb_delete` — Delete KB (IRREVERSIBLE)
When: User asks to delete an entire KB.
Parameters:
- `kb_id` (required)
- `confirm` (optional, default false): set true to execute

### `astr_kb_delete_document` — Delete document (IRREVERSIBLE)
When: User asks to delete a specific file/document from a KB.
Parameters:
- `kb_id` (required)
- `doc_id` (optional, xor with file_name)
- `file_name` (optional, xor with doc_id): keyword match
- `confirm` (optional, default false): set true to execute

### `astr_kb_search_ext` — Search (access-controlled)
When: See search strategy below.
Parameters: `query` (required).

---

## Search Strategy — Which tool to use?

Two search tools exist. Both search the same vector DB but differ in which KBs they cover:

| Tool | Scope | Access control |
|------|-------|---------------|
| Built-in `astr_kb_search` | Dashboard-global KB config | None (fixed by admin) |
| Plugin `astr_kb_search_ext` | Plugin whitelist | Yes — only whitelisted KBs |

### Decision flow

```
User mentions a specific KB?
  ├── YES — is it in the plugin whitelist?
  │     ├── YES → astr_kb_search_ext
  │     └── NO  → built-in astr_kb_search
  ├── YES — just created by this plugin → astr_kb_search_ext
  └── NO  (vague request like "search the KB")
        → built-in astr_kb_search FIRST
        → if no results, suggest astr_kb_search_ext
```

## General rules
- Always `astr_kb_list` first to get kb_id before file operations
- Report results with key info: doc_id, chunk count, success/failure
- Delete ops MUST ask user confirmation first
