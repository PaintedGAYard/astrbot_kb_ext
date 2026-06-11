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

# AstrBot Knowledge Base Extended Access

An AstrBot Star plugin providing Agent-facing LLM tools for knowledge base management with configurable whitelist/blacklist access control. All tools call AstrBot's internal Python APIs directly — no HTTP round-trips.

## Tools (12 `@llm_tool`)

### Knowledge Base CRUD

| Tool | Description |
|------|-------------|
| `astr_kb_list` | List available KBs, filtered by access control |
| `astr_kb_create` | Create KB with optional embedding/rerank provider selection (fuzzy matching) |
| `astr_kb_delete` | Delete an entire KB (requires user confirmation) |
| `astr_kb_search_ext` | Search across access-controlled KBs |

### Document Management

| Tool | Description |
|------|-------------|
| `astr_kb_list_documents` | List all documents in a KB |
| `astr_kb_delete_document` | Delete a document from a KB (requires user confirmation) |
| `astr_kb_get_document_content_chunk` | Get one text chunk by index — sequential reading for full content |

### File Upload (3 strategies)

| Strategy | Tool | When | Behavior |
|----------|------|------|----------|
| **A — Sync** | `astr_kb_upload` (wait_completion=true) | Estimated &lt; 100s | Blocks until vectorization complete |
| **B — Batch** | `astr_kb_upload_batch` | All files estimated &lt; 30s | Uploads multiple files sequentially |
| **C — Async** | `astr_kb_upload` (wait_completion=false) + `astr_kb_schedule_check` | Estimated &gt; 100s | Background processing with recurring cron check |

Supporting upload tools:
- `astr_kb_estimate_upload_time` — Estimate vectorization time from file size + type, returns recommended strategy and polling interval
- `astr_kb_check_upload` — Query async upload progress (stage: parsing / chunking / embedding)
- `astr_kb_schedule_check` — Schedule a recurring cron-based check (server-side time, min 180s interval)

Upload features: configurable `timeout` (per-attempt), `max_retries`, `chunk_size`, `chunk_overlap`, `sandbox_path` (avoids base64 overhead), `file_content` (text/base64).

## Access Control

| Mode | Behavior |
|------|----------|
| `whitelist` | Agent can only access listed KBs |
| `blacklist` | Agent can access all KBs except those listed |

- KBs created by the plugin are auto-whitelisted
- Access control applies to: search, upload, delete, document listing, chunk reading
- Plugin settings page available in AstrBot WebUI for management

## Supported File Formats

| Category | Extensions |
|----------|-----------|
| Plain text | `.txt` |
| Markdown | `.md` `.markdown` `.mkd` `.mdx` |
| Structured text | `.rst` `.adoc` |
| PDF | `.pdf` |
| eBook | `.epub` |
| Word | `.docx` only |
| Excel | `.xls` `.xlsx` |

> ⚠️ `.doc`, `.ppt`, `.pptx` are **not** supported — extract text first and upload as `.md`.

## Agent Guidance (SKILL.md)

The plugin includes 11 skill files in `skills/` that instruct the LLM Agent on:
- Which upload strategy to use based on file size estimation
- Hard rules (no concurrent async uploads, no active polling, always confirm deletion)
- Complete multi-file async workflow (upload → schedule recurring check → cron callback → next file)
- Decision flow for choosing between built-in `astr_kb_search` and `astr_kb_search_ext`

## Configuration

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mode` | string | `whitelist` | Access control mode |
| `whitelist` | list of string | `[]` | Allowed KB IDs |
| `blacklist` | list of string | `[]` | Blocked KB IDs |
| `auto_whitelist_created` | bool | `true` | Auto-add created KBs to whitelist |
| `avg_embedding_time` | number | `1.5` | Avg seconds per chunk for upload time estimation |

## Build

```powershell
.\build.ps1
```

Output: `.\out\astrbot_kb_ext_access_<version>.zip`

## Installation

1. Build the plugin zip
2. AstrBot WebUI → Plugin Management → Install Plugin → Upload the `.zip`

## Project Structure

```
astrbot_kb_tools/
├── build.ps1                          # Build script (reads version from metadata.yaml)
├── LICENSE                            # MIT License
├── ChangeLog.md
├── README.md
├── src/astrbot_kb_ext_access/         # Plugin source
│   ├── __init__.py                    # Package init, __version__ from metadata.yaml
│   ├── main.py                        # Star class + 12 @llm_tool
│   ├── access_control.py              # Whitelist/blacklist logic
│   ├── kb_uploader.py                 # Upload logic with progress tracking & retry
│   ├── metadata.yaml                  # Plugin metadata (single version source)
│   ├── _conf_schema.json              # Config schema
│   ├── .astrbot-plugin/i18n/         # Internationalization
│   ├── pages/access-control/          # Plugin settings web page
│   └── skills/                        # 11 Agent SKILL.md files
└── out/                               # Build output (.zip archives)
```
