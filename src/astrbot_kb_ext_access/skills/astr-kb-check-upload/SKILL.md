---
name: astr-kb-check-upload
description: Check the vectorization status of a file submitted with wait_completion=false.
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

# Tool: `astr_kb_check_upload` — Check Async Upload Status

## When to use
- Inside a recurring cron callback (triggered by `astr_kb_schedule_check`).
- When the user explicitly asks about a file that was uploaded asynchronously.

Do NOT call this tool in a polling loop. Use `astr_kb_schedule_check` to schedule recurring checks.

## Rules
- Do NOT call this repeatedly. The recurring cron handles the loop.
- Prefer `upload_task_id` (UUID) over `file_name` + `kb_id` for lookups.
