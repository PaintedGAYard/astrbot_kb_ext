---
name: astr-kb-upload-async
description: Upload large files asynchronously with FutureTask polling. Process multiple files by chaining FutureTask callbacks — one file at a time, automatically.
---

# Strategy C: Async Upload with FutureTask

For files whose estimated vectorization time exceeds the framework's 120s hard limit.
Instead of waiting, submit each file to a background task and use
`astr_kb_schedule_check` (server-side clock) to schedule checks.
When one file finishes, the callback automatically starts the next file —
creating a chain that processes all files sequentially.

## When to use
- `astr_kb_estimate_upload_time` returned a strategy containing "超时" or "必须异步".
- Estimated time > 100s.

## Prerequisite
- AstrBot's proactive capability must be enabled (for cron support).
- You MUST have already called `astr_kb_estimate_upload_time` and noted the `推荐轮询间隔`.

## HARD RULES
1. **ONE async upload at a time.** The tool rejects concurrent `wait_completion=false` calls.
2. **NO active polling.** NEVER use `astrbot_execute_shell sleep` to wait.
3. **MUST use `astr_kb_schedule_check`.** Use this plugin tool instead of the built-in `future_task` — it uses the server's system clock so timestamps are accurate.
4. **Use the dynamic polling interval.** Read it from the estimation output.

## Tool: `astr_kb_schedule_check` — Schedule a check (server-side time)

Use this instead of the built-in `future_task`. The server calculates `run_at` from
its own clock — no more wrong timestamps from the agent's inaccurate time context.

Parameters:
| Param | Required | Description |
|-------|----------|-------------|
| `file_name` | Yes | File name for the task label. |
| `delay_seconds` | Yes | Seconds from NOW to execute. Server calculates the absolute time. |
| `note_text` | Yes | Exact instructions for your future self when woken. Same content as the `future_task` note field. |

---

## How the chain works (read this first)

You have N files. You upload them ONE AT A TIME by chaining FutureTask callbacks:

```
Step 1: Upload file_1 (async)  →  schedule future_task to check file_1
Step 2: (future_task fires)    →  check file_1
        ├── done?              →  upload file_2 (async) → schedule future_task to check file_2
        └── not done?          →  schedule future_task to check file_1 again (retry)
Step 3: (future_task fires)    →  check file_2  →  same logic
... repeat until all files done
```

Each callback either retries the current file OR starts the next file.
You do NOT need to manage this actively — the `note` in each future_task
contains all the instructions your future self needs.

**The "one async at a time" rule is fine.** You never have more than one
async upload running because the next one only starts after the current one
finishes. This is NOT slow — it is the ONLY correct way.

---

## Part 1: Prepare the file list (before any upload)

### Instructions
1. Use `astr_kb_list` to get the target `kb_id`.
2. For each file in the sandbox, run `ls -l /path/to/file` to get `file_size_bytes`.
3. For each file, call `astr_kb_estimate_upload_time` and record the `推荐轮询间隔`.
4. Build a mental list of files to upload. Filter to only files with strategy "超时" or "必须异步".
5. Take the FIRST file from the list and proceed to Part 2.

---

## Part 2: Submit one file and schedule its first check

### Instructions
1. Call `astr_kb_upload` with `wait_completion=false` for the current file:
   ```json
   {
     "kb_id": "<from astr_kb_list>",
     "file_name": "file_1.xlsx",
     "sandbox_path": "/workspace/file_1.xlsx",
     "wait_completion": false
   }
   ```
   - If it returns `"❌ 已有异步上传进行中"`: stop. A previous upload is still running. Check it first.
   - If it returns `"⏳ 文件已提交后台处理"`: proceed to step 2.

2. Compute `delay_seconds` = estimated total duration (from estimation output).
   Do NOT try to compute an absolute time — use relative delay.

3. Schedule a check using `astr_kb_schedule_check`:
   ```json
   {
     "file_name": "file_1.xlsx",
     "delay_seconds": 300,
     "note_text": "Call astr_kb_check_upload(kb_id='<kb_id>', file_name='file_1.xlsx'). "
                  "If result contains '已完成', report file_1.xlsx doc_id and chunk_count. "
                  "Then upload the next file: call astr_kb_upload with kb_id='<kb_id>', "
                  "file_name='file_2.xlsx', sandbox_path='/workspace/file_2.xlsx', "
                  "wait_completion=false. After that, call astr_kb_schedule_check "
                  "with file_name='file_2.xlsx', delay_seconds=<polling_interval>, "
                  "and a note_text following this same pattern. "
                  "If result contains '处理中', call astr_kb_schedule_check with "
                  "file_name='file_1.xlsx', delay_seconds=<polling_interval>, "
                  "and this identical note_text."
   }
   ```

4. The callback chain is now set up. You can end this response. AstrBot will
   wake you when it is time to check.

---

## Part 3: FutureTask callback (what to do when woken)

When AstrBot wakes you at the scheduled time:

### Instructions
1. Read the `note_text` that was set when `astr_kb_schedule_check` was called. It tells
   you exactly what to do. Follow it precisely.

2. Typically, the note will tell you to call `astr_kb_check_upload`:
   ```json
   {
     "kb_id": "<kb_id>",
     "file_name": "file_1.xlsx"
   }
   ```

3. Act on the result:
   - **"✅ 已完成"**: Report doc_id and chunk_count to the user. Then start the
     next file from your list using the pattern in Part 2 (step 3).
   - **"⏳ 处理中"**: Compute `new_run_at = current_time + 推荐轮询间隔`.
     Schedule another `future_task` with the same `note`. End the callback.
   - If this was the LAST file in your list and it completed: report summary to user.

---

## Complete example: 3 files

```
Part 1: Prepare
  - astr_kb_list() → kb_id = "abc-123"
  - ls -l → file_1.xlsx=500KB, file_2.xlsx=800KB, file_3.pdf=2MB
  - estimate each → all >100s, polling_interval=60s

Part 2: Start file 1
  - astr_kb_upload(kb_id="abc-123", file_name="file_1.xlsx",
                   sandbox_path="/workspace/file_1.xlsx",
                   wait_completion=false)
  - astr_kb_schedule_check(file_name="file_1.xlsx", delay_seconds=300,
                           note_text="...check file_1...if done start file_2...")
  → End response.

--- AstrBot wakes you ---

Part 3: Check file 1
  - astr_kb_check_upload(kb_id="abc-123", file_name="file_1.xlsx")
  → "✅ 已完成 (doc_id=xxx, 42 chunks)"
  - Report to user.
  - Start file 2:
    astr_kb_upload(kb_id="abc-123", file_name="file_2.xlsx",
                   sandbox_path="/workspace/file_2.xlsx",
                   wait_completion=false)
  - astr_kb_schedule_check(file_name="file_2.xlsx", delay_seconds=300,
                           note_text="...check file_2...if done start file_3...")
  → End response.

--- AstrBot wakes you ---

Part 3: Check file 2 → done → start file 3 → schedule check
  → End response.

--- AstrBot wakes you at 12:45 ---

Part 3: Check file 3 → done → all files uploaded → report summary
```

---

## `astr_kb_schedule_check` parameter reference

| Param | Required | Description |
|-------|----------|-------------|
| `file_name` | Yes | File name for the task label. |
| `delay_seconds` | Yes | Seconds from NOW. Server calculates the absolute time. |
| `note_text` | Yes | Exact instructions for your future self (see template in Part 2 step 3). |

## Forbidden patterns
```
❌ astrbot_execute_shell(command="sleep 40")              — NO active polling
❌ Calling astr_kb_check_upload in a loop                   — NO active polling
❌ Multiple wait_completion=false in one response            — tool rejects it
❌ Using built-in `future_task` with absolute run_at        — agent time is inaccurate.
   Use `astr_kb_schedule_check` with delay_seconds instead.
❌ Thinking "19 files × 1 at a time = 19 rounds = slow"
   → NO. Each round is a callback. You set it and forget it.
     The callbacks are automatic — you do NOT need to stay and wait.
```
