---
name: astr-kb-estimate-upload-time
description: Estimate vectorization time for a file to determine upload strategy (sync vs async vs batch).
---

# Tool: `astr_kb_estimate_upload_time` — Estimate Upload Duration

## When to use
Call this BEFORE uploading ANY file. Use the output to decide which upload strategy to follow. Also use the output's `recommended polling interval` to schedule FutureTask delays.

## Parameters
| Param | Required | Default | Description |
|-------|----------|---------|-------------|
| `file_size_bytes` | Yes | — | File size in bytes. Get from `ls -l` or `stat` in the sandbox. |
| `file_name` | Yes | — | File name WITH extension. Extension determines the text density ratio used in estimation. |
| `chunk_size` | No | 512 | Chunk size in characters. |
| `chunk_overlap` | No | 50 | Chunk overlap in characters. |

## Instructions
1. In the sandbox, run `ls -l /path/to/file` to get `file_size_bytes`.
2. Call `astr_kb_estimate_upload_time(file_size_bytes=N, file_name="doc.pdf")`.
3. Read the output:
   - `建议策略` tells you which upload strategy to use.
   - `推荐轮询间隔` gives the polling interval in seconds for FutureTask scheduling.

## Output interpretation
| Strategy label | Meaning | Action |
|---|---|---|
| Contains "极快" | < 30s | Use Strategy A (sync) or Strategy B (batch for multiple files). |
| Contains "较快" | 30-100s | Use Strategy A (sync). Do NOT batch. |
| Contains "超时" or "必须异步" | > 100s | MUST use Strategy C (async + FutureTask). |

## Accuracy warning
Estimates for compressed formats (XLSX, DOCX, EPUB) can be inaccurate because
compression ratios vary widely. A file estimated at 52s may actually take 100s+.

**If a sync upload times out, do NOT retry with a higher timeout. Switch to Strategy C (async).**

## Rules
- You MUST call this before every upload to choose the correct strategy.
- Read the `推荐轮询间隔` value — it is used in `future_task` scheduling.
- If a sync upload times out, re-classify the file as async and use Strategy C.
