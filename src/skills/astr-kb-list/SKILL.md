---
name: astr-kb-list
description: List available knowledge bases with kb_id, used as prerequisite for all KB operations.
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

# Tool: `astr_kb_list` — List Knowledge Bases

## When to use
Call this tool BEFORE any knowledge base operation (upload, create, delete, search). It returns the `kb_id` required by all other KB tools. The output is pre-filtered by the plugin's whitelist/blacklist configuration.

## Instructions
1. Call `astr_kb_list()` with a `query` if you know part of the KB name, otherwise call without parameters.
2. Read the returned list to find the target KB's `kb_id`.
3. Use that `kb_id` in subsequent tool calls.

## Rules
- You MUST call this tool before ANY upload, delete, or search operation.
- Do NOT hardcode kb_id — always fetch it fresh.
