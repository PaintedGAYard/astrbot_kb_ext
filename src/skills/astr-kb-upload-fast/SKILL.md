---
name: astr-kb-upload-fast
description: Upload files synchronously or in batch — for files estimated to complete within 100 seconds.
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

# Strategy A & B: Fast Upload — Sync and Batch

## When to use

| Strategy | Condition |
|----------|-----------|
| **A — Sync Upload** | Single file, estimated time < 100s (strategy contains "极快" or "较快") |
| **B — Batch Upload** | Multiple files, ALL estimated time < 30s (strategy contains "极快") |

Call `astr_kb_estimate_upload_time` first to confirm the strategy.

---

## Strategy A: Sync Upload (one file)

### Instructions
1. Call `astr_kb_list()` to get the target `kb_id`.
2. Call `astr_kb_upload()` with these parameters:
   ```json
   {
     "kb_id": "<from astr_kb_list>",
     "file_name": "document.pdf",
     "sandbox_path": "/workspace/document.pdf",
     "wait_completion": true
   }
   ```
3. Wait for the tool to return. The tool blocks until vectorization completes.
4. Report the result to the user: doc_id, chunk_count, success/failure.

---

## Strategy B: Batch Upload (multiple small files)

### Instructions
1. Call `astr_kb_list()` to get the target `kb_id`.
2. Estimate each file. Confirm ALL have estimated time < 30s.
3. Assemble the `files` array:
   ```json
   {
     "files": [
       {
         "kb_id": "<from astr_kb_list>",
         "file_name": "small1.pdf",
         "sandbox_path": "/workspace/small1.pdf"
       },
       {
         "kb_id": "<from astr_kb_list>",
         "file_name": "small2.docx",
         "sandbox_path": "/workspace/small2.docx"
       }
     ]
   }
   ```
   Do NOT include `wait_completion` — batch mode forces blocking uploads.
4. Call `astr_kb_upload_batch(files=[...])`.
5. Report the summary: success count, failure count, per-file details.

---

## Rules
- Do NOT put files with estimated time > 30s into a batch — they will hit the framework timeout.
- Do NOT use `wait_completion=false` in this strategy — that is for Strategy C only.
- Always use `sandbox_path` when possible. It avoids base64 encoding overhead.
