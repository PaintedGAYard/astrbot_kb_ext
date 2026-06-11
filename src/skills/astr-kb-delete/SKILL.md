---
name: astr-kb-delete
description: Permanently delete an entire knowledge base. IRREVERSIBLE — requires user confirmation.
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

# Tool: `astr_kb_delete` — Delete Knowledge Base (IRREVERSIBLE)

## When to use
When the user asks to delete an entire knowledge base and all its documents.

## Instructions
1. Call `astr_kb_list()` to confirm the KB exists and get its `kb_id`.
2. Ask the user for confirmation: "Are you sure you want to permanently delete KB '{name}' ({kb_id})? All documents will be lost."
3. ONLY if the user explicitly confirms (or says "skip confirmation"), call:
   ```json
   {
     "kb_id": "<kb_id>",
     "confirm": true
   }
   ```

## Rules
- You MUST ask for user confirmation before setting `confirm=true`.
- "确认" / "yes" / "delete it" / "skip confirmation" all count as explicit confirmation.
- A vague "ok" or "go ahead" does NOT count — ask explicitly.
- After deletion, the KB is also removed from the whitelist automatically.
