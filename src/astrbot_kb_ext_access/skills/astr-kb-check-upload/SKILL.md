---
name: astr-kb-check-upload
description: Check the vectorization status of a file submitted with wait_completion=false.
---

# Tool: `astr_kb_check_upload` — Check Async Upload Status

## When to use
- Inside a recurring cron callback (triggered by `astr_kb_schedule_check`).
- When the user explicitly asks about a file that was uploaded asynchronously.

Do NOT call this tool in a polling loop. Use `astr_kb_schedule_check` to schedule recurring checks.

## Rules
- Do NOT call this repeatedly. The recurring cron handles the loop.
- Prefer `upload_task_id` (UUID) over `file_name` + `kb_id` for lookups.
