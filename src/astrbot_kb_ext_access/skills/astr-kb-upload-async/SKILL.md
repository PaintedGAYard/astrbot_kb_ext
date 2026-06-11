---
name: astr-kb-upload-async
description: Upload large files asynchronously with a recurring FutureTask that polls until done — one file at a time.
---

# Strategy C: Async Upload with Recurring FutureTask

For files whose estimated vectorization time exceeds the framework's 120s hard limit.
Submit each file to a background task and set up a RECURRING `astr_kb_schedule_check`
that fires every N seconds. When the upload completes, the callback deletes the
recurring task and starts the next file.

## When to use
- `astr_kb_estimate_upload_time` returned a strategy containing "超时" or "必须异步".
- Estimated time > 100s.

## Prerequisite
- AstrBot's proactive capability must be enabled (for cron support).
- You MUST have already called `astr_kb_estimate_upload_time` and noted the `推荐轮询间隔`.

## HARD RULES
1. **ONE async upload at a time.** The tool rejects concurrent `wait_completion=false` calls.
2. **NO active polling.** NEVER use `astrbot_execute_shell sleep` to wait.
3. **MUST use `astr_kb_schedule_check` (recurring mode).** Set it once — it fires automatically.
4. **Use the recommended polling interval** from the estimation output (minimum 180s / 3 minutes).

## How it works

```
Step 1: Upload file_1 (async)
Step 2: astr_kb_schedule_check(interval_seconds=180)  →  creates recurring cron
Step 3: (cron fires every 180s) → check file_1
        ├── not done? → do nothing, cron fires again later
        └── done?     → future_task(action="delete", job_id=xxx) to stop cron
                        then upload file_2 and repeat
... until all files done
```

---

## Part 1: Prepare

### Instructions
1. `astr_kb_list()` to get `kb_id`.
2. For each file: `ls -l` → `astr_kb_estimate_upload_time` → record `推荐轮询间隔`.
3. Take the FIRST file from the list.

---

## Part 2: Upload and schedule recurring check

### Instructions
1. Upload the current file:
   ```json
   {
     "kb_id": "<kb_id>",
     "file_name": "file_1.xlsx",
     "sandbox_path": "/workspace/file_1.xlsx",
     "wait_completion": false
   }
   ```
   If it returns "❌ 已有异步上传进行中", stop — a previous upload is still running.

2. Call `astr_kb_schedule_check` (recurring mode):
   ```json
   {
     "file_name": "file_1.xlsx",
     "interval_seconds": 180,
     "note_text": "Call astr_kb_check_upload(kb_id='<kb_id>', file_name='file_1.xlsx'). "
                  "If result contains '已完成', first call future_task(action='delete', "
                  "job_id='<job_id>') to stop this recurring check. Then report doc_id "
                  "and chunk_count to the user. Then upload the next file and schedule "
                  "another recurring check for it. "
                  "If result contains '处理中' or '不在知识库中', do nothing — "
                  "this recurring cron will fire again automatically."
   }
   ```
   The return message includes the `job_id` you need for deletion.

3. End this response. The cron fires automatically every `interval_seconds`.

---

## Part 3: Cron callback (when woken)

1. Call `astr_kb_check_upload(kb_id="...", file_name="...")`.
2. Act on the result:
   - **"✅ 已完成"**: `future_task(action="delete", job_id="<job_id>")` to stop. Report to user. Start next file (go to Part 2).
   - **"⏳ 处理中"** or **"不在知识库中"**: Do nothing. The cron fires again automatically.

---

## Complete example: 3 files

```
Part 1: Prepare
  - astr_kb_list() → kb_id = "abc-123"
  - ls -l → file_1.xlsx=500KB, file_2.xlsx=800KB, file_3.pdf=2MB
  - estimate each → polling_interval=180s

Part 2: Start file 1
  - astr_kb_upload(kb_id="abc-123", file_name="file_1.xlsx",
                   sandbox_path="/workspace/file_1.xlsx", wait_completion=false)
  - astr_kb_schedule_check(file_name="file_1.xlsx", interval_seconds=180,
                           note_text="Check file_1. If done, delete this job and start file_2...")
  → End response.

--- Cron fires (every 180s) ---

Part 3: Check file 1 → still processing → do nothing → cron fires again

--- Cron fires again ---

Part 3: Check file 1 → ✅ done
  - future_task(action="delete", job_id="<id>")
  - Report to user.
  - Upload file 2 → schedule_check for file 2 → end response.

--- Cron fires for file 2 ---

... repeat until all 3 files done
```

## Forbidden patterns
```
❌ astrbot_execute_shell(command="sleep 40")              — NO active polling
❌ Calling astr_kb_check_upload in a loop                   — NO active polling
❌ Multiple wait_completion=false in one response            — tool rejects it
❌ Scheduling one-shot future_tasks in a callback chain      — use recurring mode instead
```
