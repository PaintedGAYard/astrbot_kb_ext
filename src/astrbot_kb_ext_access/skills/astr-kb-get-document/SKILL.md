---
name: astr-kb-get-document-content-chunk
description: Get one text chunk from a document by index. Use chunk_index to navigate chunks sequentially.
---

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
