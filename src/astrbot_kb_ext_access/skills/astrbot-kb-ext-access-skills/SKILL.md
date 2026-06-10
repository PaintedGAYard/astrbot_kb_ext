---
name: astrbot-kb-ext-access-skills
description: 知识库搜索、文件上传与创建 / Knowledge base listing, upload & creation
---

# 知识库管理工具 / Knowledge Base Management Tools

你可以通过以下工具操作 AstrBot 知识库。请直接调用这些工具，不要尝试使用 HTTP API 或数据库。
You have access to AstrBot knowledge bases through the following tools.
Always call these tools directly — do NOT try to use HTTP API or database directly.

## 可用工具 / Available Tools

### `astr_kb_list`
列出所有可用的知识库。上传文件之前，先调用此工具获取目标 `kb_id`。
List all available knowledge bases. Use this first to find the target `kb_id`.

**使用时机 / When to use**: 当用户询问知识库时，或在上传文件之前。
When the user asks about knowledge bases, or before uploading files.

### `astr_kb_upload`
向知识库上传文件。
Upload a file to a knowledge base.

**使用时机 / When to use**: 当用户要求保存/存储/上传内容到知识库时。
When the user asks to save/store/upload content to a knowledge base.

**步骤 / Steps**:
1. 先调用 `astr_kb_list` 获取可用知识库列表和 ID。
   First call `astr_kb_list` to get available KBs and their IDs.
2. 如果用户未指定，询问用户要上传到哪个知识库。
   Ask the user which KB to upload to (if not specified).
3. 调用 `astr_kb_upload`，传入文件内容和目标 `kb_id`。
   Call `astr_kb_upload` with the file content and target `kb_id`.

**参数 / Parameters**:
- `kb_id`: 必填。从 `astr_kb_list` 获取。Required. Get this from `astr_kb_list`.
- `file_name`: 必填。包含扩展名（如 "report.md"）。Required. Include the extension.
- `file_content`: 必填。完整的文本内容。Required. The full text content to upload.
- `chunk_size`: 可选，默认 512。Optional. Default 512.
- `chunk_overlap`: 可选，默认 50。Optional. Default 50.

### `astr_kb_create`
创建新的知识库。
Create a new knowledge base.

**使用时机 / When to use**: 当用户要求创建一个新的知识库来组织文档时。
When the user asks to create a new knowledge base.

**参数 / Parameters**:
- `kb_name`: 必填。简短描述性的名称。Required. A short, descriptive name.
- `description`: 可选。描述知识库用途。Optional. Describe what this KB is for.
- `chunk_size`: 可选，默认 512。Optional. Default 512.

## 使用指南 / Guidelines
- 始终先调用 `astr_kb_list` 展示可用选项 / Always list KBs first
- 使用描述性的文件名 / Use descriptive file names
- 清晰报告结果：成功/失败、文档ID、切片数 / Report results clearly
