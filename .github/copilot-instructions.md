# AstrBot Plugin Coding Guide

This project has undergone a major refactoring. Follow these principles when writing or reviewing code.

## 1. Documentation discipline

Documentation in source code (docstrings, comments) serves a single purpose: **reduce the reader's surprise**. Every other kind of comment is noise.

**Required** for every non-trivial function/class:
- Full type annotations
- Parameters (name + type + intent)
- Return value
- Common exceptions
- Notable side-effects

**Do NOT write**:
- "Summary of purpose" when the function name already says it (e.g., `_xlsx_to_markdown()` needs no "Converts xlsx to markdown" — the name is the summary)
- Implementation details in docstrings — describe *what*, not *how*
- Bilingual docstrings (Chinese + English saying the same thing — pick one)
- Section header comments like `# ── Tool 1 ──` or `# ── Config ──` — they add zero information over the code structure itself

**Inline comments** are for subtle business logic only. Not for stating the obvious, not for random notes, not for "TODO" without context.

## 2. Function size & parameter count

| Threshold | Action |
|-----------|--------|
| > 5 parameters | Consider refactoring into a `@dataclass` parameter pack |
| > 8 parameters | **Must** refactor — use a `@dataclass` or similar |
| > 2 nested control constructs | Extract inner blocks into helper functions or classes |
| Function contains inner functions | Likely too fat — extract them into a named class |

**Example from this codebase**: `upload()` originally had 11 parameters → refactored into `UploadParams` dataclass (6 required, 3 with defaults).

## 3. Abstraction over branching

When a branching condition (e.g., `if ext == "xlsx": ... elif ext == "xls": ...`) represents a **conceptual category that may grow independently**, extract it into an abstraction layer instead of adding more branches.

**Good**: `MarkdownExtractor.extract(raw_bytes, file_name)` dispatches internally. Adding `.docx` support doesn't touch upload logic.
**Bad**: `if ext in (...)` scattered across the upload pipeline.

Exception: 2–3 simple branches with no expansion likelihood → keep simple.

## 4. Internal vs external (LLM-facing) interfaces

**Internal (non-LLM-facing)** methods:
- Return structured objects (dataclasses, primitives, typed dicts)
- **Never** return LLM-prompt-like messages with emojis, bullet-point formatting, etc.
- Use exceptions for error propagation (don't return `{"success": False, "error": "..."}` — that's for the LLM layer)

**LLM-facing** methods (`@llm_tool`):
- Serialize results to `{"s": ..., "d": ..., "e": ...}` JSON
- Catch exceptions and translate to structured error responses
- Hand-crafted messages (emojis, templates) are acceptable here

**Separate the two cleanly**: build result objects in internal code, format them at the tool boundary.

## 5. Error handling

- Internal logic errors → propagate as exceptions
- LLM-facing interfaces → catch exceptions and translate
- **One shared decorator** (`tool_error_handler`) for all `@llm_tool` methods instead of repetitive try/except blocks per tool
- Tools that need custom error handling (e.g., per-item errors in batch) are exceptions — keep their try/except, but most tools don't need it

## 6. Repeated patterns → extract

If you see the same 5+ lines of code appearing twice, extract it:

| Pattern in this codebase | Extracted to |
|--------------------------|-------------|
| Sandbox file reading (6 lines) | `_read_sandbox_file()` |
| `asyncio.shield()` + short_wait + store_result (20+ lines) | `_AsyncUploadTask` class |
| `PermissionError` + `Exception` handling in every tool | `tool_error_handler` decorator |

## 7. Shared mutable state

If a method modifies instance state (e.g., appending to `self._phases`):
- That's a **side-effect** — document it in the method's docstring
- Explain why it's safe (e.g., "awaited, single coroutine at a time")
- If it's NOT safe (multiple coroutines access the same state), guard with a lock or restructure

## 8. Async conventions

- I/O-bound operations → `async def`
- CPU-bound pure computations → synchronous, call via `await asyncio.to_thread()` when in async context
- `asyncio.shield()` for background tasks that must survive the framework's tool-call timeout

## 9. File organization

Single-responsibility principle applies at the file level too:

| File | Responsibility |
|------|---------------|
| `main.py` | `@llm_tool` plugin class, web APIs, tool orchestration |
| `kb_uploader.py` | Upload pipeline, retry, async background, `UploadParams`/`UploadResult` |
| `markdown_extractor.py` | Binary-format → Markdown conversion (no upload logic) |
| `access_control.py` | Whitelist/blacklist rules |

Don't mix concerns: upload logic doesn't know about Markdown extraction internals; tools don't build LLM messages inline.
