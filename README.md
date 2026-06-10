# AstrBot KB External Access

AstrBot Star plugin providing Agent-facing tools for knowledge base listing, file upload, and knowledge base creation, with configurable whitelist/blacklist access control.

## Features

- **`astr_kb_list`** — List available knowledge bases (with access control filtering)
- **`astr_kb_upload`** — Upload file content to a knowledge base with configurable chunk parameters
- **`astr_kb_create`** — Create a new knowledge base with auto-selected embedding provider
- **Access Control** — Whitelist/blacklist mechanism via plugin configuration

## Installation

1. Build: `.\build.ps1` → produces `.\out\astrbot_kb_ext_access_<version>.zip`
2. In AstrBot WebUI → Plugin Management → Install Plugin → Upload the `.zip` file

## Configuration

Configure via AstrBot WebUI → Plugin Settings → `astrbot_kb_ext_access`:

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `mode` | string | `whitelist` | `whitelist` or `blacklist` |
| `whitelist` | list | `[]` | Allowed KB IDs |
| `blacklist` | list | `[]` | Blocked KB IDs |
| `auto_whitelist_created` | bool | `true` | Auto-add created KBs to whitelist |

## Build

```powershell
.\build.ps1
```

Output: `.\out\astrbot_kb_ext_access_<version>.zip`

## Project Structure

```
astrbot_kb_tools/
├── build.ps1                          # Build script
├── src/astrbot_kb_ext_access/         # Plugin source
│   ├── main.py                        # Star class + 3 @llm_tool
│   ├── access_control.py              # Whitelist/blacklist
│   ├── kb_uploader.py                 # Upload logic
│   ├── metadata.yaml                  # Plugin metadata
│   ├── _conf_schema.json             # Config schema
│   └── skills/                        # Agent SKILL.md
├── out/                               # Build output
│   └── astrbot_kb_ext_access_*.zip
├── design/                            # Design documents
├── ChangeLog.md
└── README.md
```
