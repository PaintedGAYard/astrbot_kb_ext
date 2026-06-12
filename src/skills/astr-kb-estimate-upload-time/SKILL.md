---
name: astr-kb-estimate-upload-time
description: Estimate vectorization time for a file to determine upload strategy (sync vs async vs batch).
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

# Tool: `astr_kb_estimate_upload_time` — Estimate Upload Duration

## When to use
Call this BEFORE uploading ANY file. Use the output to decide which upload strategy to follow. Also use the output's `recommended polling interval` to schedule FutureTask delays.

## Instructions
1. In the sandbox, run `ls -l /path/to/file` to get `file_size_bytes`.
2. Call `astr_kb_estimate_upload_time(file_size_bytes=N, file_name="doc.pdf")`.
3. Parse the JSON result:
   - `d.strategy` tells you which upload strategy to use.
   - `d.polling_interval_seconds` gives the polling interval for FutureTask.
   - `d.strategy_label` is a human-readable description.

## Output interpretation
| `d.strategy` | Meaning | Action |
|---|---|---|
| `"sync_fast"` | < 30s | Use Strategy A (sync) or Strategy B (batch). |
| `"sync"` | 30-100s | Use Strategy A (sync). Do NOT batch. |
| `"async"` | > 100s | MUST use Strategy C (async + FutureTask). |

## Accuracy warning
Estimates for compressed formats (XLSX, DOCX, EPUB) can be inaccurate because
compression ratios vary widely. A file estimated at 52s may actually take 100s+.

⚠️ **XLSX 特别注意**：插件已内置 xlsx→markdown 预处理，使用 openpyxl
自行构建 Markdown 表格，完全绕过 pandas.to_html() 的 NaN 问题。
但 pandas 的 used_range 仍可能包含大量空白行列，且 text_ratio 按 0.1
计算（压缩比），实际文本量取决于数据密度。
**如果 xlsx 同步上传超时，不要增加超时重试，请直接切换到 Strategy C（异步模式）。**

## Rules
- You MUST call this before every upload to choose the correct strategy.
- Read `d.polling_interval_seconds` — it is used for `astr_kb_schedule_check`.
- If a sync upload times out, re-classify the file as async and use Strategy C.
