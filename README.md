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
