---
name: astr-kb-upload-async
description: Upload large files asynchronously with a recurring FutureTask that polls until done — one file at a time.
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
Step 1: Upload file_1 (async)             → returns upload_task_id="uuid-1"
Step 2: astr_kb_schedule_check(upload_task_id="uuid-1", interval_seconds=180)  → creates recurring cron
Step 3: (cron fires every 180s) → check by upload_task_id
        ├── not done? → do nothing, cron fires again later
        └── done?     → report result, then upload file_2 and repeat
... until all files done
```

Each upload gets a unique `upload_task_id` (UUID). Use this ID for all
subsequent check and schedule calls — do NOT use file_name.

---

## Part 1: Prepare

### Instructions
1. `astr_kb_list()` to get `kb_id`.
2. For each file: `ls -l` → `astr_kb_estimate_upload_time` → record polling interval.
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
   Returns JSON: `{"s":true, "d":{"upload_task_id":"uuid-xxx", "pending":true}}`
   Save the `upload_task_id` — you need it for all subsequent calls.
   If `s=false` and `e` mentions "已有异步上传进行中", stop.

2. Call `astr_kb_schedule_check` with the upload_task_id:
   ```json
   {
     "upload_task_id": "uuid-xxx",
     "interval_seconds": 180
   }
   ```
   Returns JSON with `d.job_id` for the cron job.

3. End this response. The cron fires automatically every `interval_seconds`.

---

## Part 3: Cron callback (when woken)

1. Call `astr_kb_check_upload(upload_task_id="uuid-xxx")`.
2. Act on the JSON result:
   - `d.status === "completed"`: Report doc_id and chunk_count. Upload next file (go to Part 2).
   - `d.status === "processing"`: Do nothing. Cron fires again.
   - `d.status === "not_found"`: Do nothing. Cron fires again.

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
  → get upload_task_id = "uuid-1"
  - astr_kb_schedule_check(upload_task_id="uuid-1", interval_seconds=180)
  → End response.

--- Cron fires (every 180s) ---

Part 3: Check uuid-1 → processing → do nothing → cron fires again

--- Cron fires again ---

Part 3: Check uuid-1 → completed
  - Report doc_id and chunk_count to user.
  - Upload file 2 → get upload_task_id → schedule_check for file 2 → end response.

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
