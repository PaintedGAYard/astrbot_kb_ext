---
name: astr-kb-check-upload
description: Check the vectorization status of a file submitted with wait_completion=false.
---

# Tool: `astr_kb_check_upload` — Check Async Upload Status

## When to use
- Inside a `future_task` callback (triggered by the cron scheduler).
- When the user explicitly asks about a file that was uploaded asynchronously.

Do NOT call this tool in a polling loop. Use `future_task` to schedule checks.

## Parameters
| Param | Required | Description |
|-------|----------|-------------|
| `kb_id` | Yes | Knowledge base ID from `astr_kb_list`. |
| `file_name` | Yes | File name to check. |

## Returns
- `"✅ ... 已完成"` — Vectorization is complete. Report `doc_id` and `chunk_count` to the user.
- `"⏳ ... 处理中"` — Still processing. Schedule another `future_task` with the recommended polling interval.
- `"❌ ... 不存在"` — File was not found. May need to re-upload.

## Instructions (for FutureTask callbacks)
1. Call `astr_kb_check_upload(kb_id="...", file_name="...")`.
2. Read the result:
   - **Completed**: Report to user, proceed to next file.
   - **Processing**: Schedule another `future_task` with `run_at = now + polling_interval`.
   - **Error/not found**: Report to user.
3. End the callback — do NOT continue executing beyond the note's instructions.

## Rules
- Do NOT call this repeatedly. Schedule a `future_task` and let AstrBot wake you.
- This tool is ONLY useful for files uploaded with `wait_completion=false`.
