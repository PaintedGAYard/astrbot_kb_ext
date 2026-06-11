---
name: astr-kb-delete
description: Permanently delete an entire knowledge base. IRREVERSIBLE — requires user confirmation.
---

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
