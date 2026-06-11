---
name: astr-kb-get-document-content-chunk
description: Get one text chunk from a document by index. Use chunk_index to navigate chunks sequentially.
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

# Tool: `astr_kb_get_document_content_chunk` — Get One Chunk

## When to use
When you need the full text of a specific section of a document. Call `astr_kb_list_documents` first to get `doc_id`. Use `chunk_index` to navigate chunks sequentially (0, 1, 2, ...) until the chunk is null.

## Usage pattern — reading a full document

```
1. astr_kb_list_documents(kb_id="...")
   → get doc_id and total chunk count (chunk_count field)

2. astr_kb_get_document_content_chunk(kb_id="...", doc_id="...", chunk_index=0)
   → {"s": true, "c": "chunk 0 content...", "e": null}

3. astr_kb_get_document_content_chunk(kb_id="...", doc_id="...", chunk_index=1)
   → {"s": true, "c": "chunk 1 content...", "e": null}

4. ... continue incrementing chunk_index until s=false
```

## Limitations
- AstrBot stores only parsed text chunks, NOT the original file.
- Formatting, fonts, images, table layouts from source docs (.pdf/.docx/.xlsx) are lost.
- For .txt/.md files the chunk content closely matches the original.
