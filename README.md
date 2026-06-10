# AstrBot KB Tools Plugin v2.0

Agent-only, minimal output, token-efficient JSON.

## Tools

| Tool | API | 说明 |
|------|-----|------|
| `get_astrbot_kb_list` | `GET /api/kb/list` | 列出知识库 |
| `add_astrbot_kb_document` | `POST /api/kb/document/upload` | 上传文档 |

## JSON Output Schemas (token-efficient)

### `get_astrbot_kb_list`

```json
{"ok": true, "kbs": [{"id":"uuid", "name":"Lib", "docs":5, "chunks":30, "desc":"..."}]}
// or
{"ok": false, "err": "error message"}
```

| key | type | meaning |
|-----|------|---------|
| `ok` | bool | success |
| `kbs[].id` | str | knowledge base id |
| `kbs[].name` | str | name |
| `kbs[].docs` | int | document count |
| `kbs[].chunks` | int | chunk count |
| `kbs[].desc` | str | description (max 200 chars) |

### `add_astrbot_kb_document`

```json
{"ok": true, "n_ok": 3, "n_fail": 0,
 "ok_files": [{"f":"a.txt", "did":"doc-id", "n":12}],
 "fail_files": []}
// partial fail:
{"ok": false, "n_ok": 2, "n_fail": 1,
 "ok_files": [...],
 "fail_files": [{"f":"b.docx", "err":"timeout"}],
 "invalid": ["bad/*.xxx"]}
```

| key | type | meaning |
|-----|------|---------|
| `ok` | bool | all succeeded |
| `n_ok` | int | succeeded count |
| `n_fail` | int | failed count |
| `ok_files[].f` | str | filename |
| `ok_files[].did` | str | doc_id in KB |
| `ok_files[].n` | int | chunk count |
| `fail_files[].f` | str | filename |
| `fail_files[].err` | str | error reason |
| `invalid` | [str] | paths not found |

## Parameters

### get_astrbot_kb_list
- `base_url` *(required)*
- `auth_token` (or env `ASTRBOT_AUTH_TOKEN`)

### add_astrbot_kb_document
- `paths` *(required)* — file paths, supports glob
- `base_url` *(required)*
- `kb_id` *(required)*
- `auth_token` (or env)
- `chunk` (int, default 512)
- `overlap` (int, default 50)
- `batch` (int, default 32)
- `retries` (int, default 3)
- `parallel` (int, default 3)
- `timeout` (float seconds, default 600, 0=∞)

## 结构

```
astrbot_kb_tools/   (320 lines Python)
├── __init__.py      — 包入口
├── main.py          — tool 定义+实现 (150 lines)
└── kb_client.py     — HTTP client (152 lines)
```
