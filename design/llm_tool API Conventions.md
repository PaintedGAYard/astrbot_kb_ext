# `@llm_tool` API Conventions

This document explains how AstrBot's `@llm_tool` decorator works and how to
write correct tool definitions.  It supplements the general coding style rules
in `Working Guidelines.md`.

## How `@llm_tool` reads the tool definition

The decorator (defined in `astrbot/core/star/register/star_handler.py`)
does **not** use Python's `inspect.signature()`.  Instead it reads two things
from the source:

1. **The docstring's first paragraph** — used as the tool's *description* in
   the LLM function-calling schema.
2. **The docstring's `Args:` section** — parsed by `docstring_parser` to
   extract parameter names, types, and descriptions for the JSON Schema.

## What goes in `Args:` — and what does NOT

```
@llm_tool(name="example")
async def example_tool(
    event: AstrMessageEvent,    ← framework-injected, do NOT document
    query: str,                 ← LLM-facing, MUST be in Args:
    page: int = 1,              ← LLM-facing, MUST be in Args:
) -> str:
    """Tool description for the LLM.

    Args:
        query(string): Search keyword.
        page(number): Page number. Default 1.
    """
```

| Parameter | In function signature? | In docstring `Args:`? | Reason |
|-----------|----------------------|----------------------|--------|
| `self` | ✅ (class methods) | ❌ **never** | Framework-injected |
| `event: AstrMessageEvent` | ✅ (if needed) | ❌ **never** | Framework-injected; its type `AstrMessageEvent` is **not** in the supported types list |
| `kb_id: str`, `query: str`, etc. | ✅ | ✅ **always** | LLM agent provides these values |

> **Rule:** Only document parameters that the LLM agent supplies.
> `self` and `event` are injected by the framework — leave them out of `Args:`.

## Supported types

Only JSON Schema primitive types are accepted:

| In `Args:` | Maps to JSON Schema | Python equivalent |
|------------|-------------------|-------------------|
| `string` | `"type": "string"` | `str` |
| `number` | `"type": "number"` | `int`, `float` |
| `boolean` | `"type": "boolean"` | `bool` |
| `object` | `"type": "object"` | `dict` |
| `array` | `"type": "array"` | `list`, `tuple`, `set` |
| `list[string]` | `"type": "array", "items": {"type": "string"}` | `list[str]` |
| `list[number]` | `"type": "array", "items": {"type": "number"}` | `list[int]` |

Both the JSON Schema name (`string`) and the Python name (`str`) work — the
decorator maps Python names via `PY_TO_JSON_TYPE`.  The official examples use
JSON Schema names; **prefer `string`/`number`/`boolean`/`array`/`object`**
for consistency with AstrBot's own tools.

Any other type name (e.g. `AstrMessageEvent`, `UploadResult`, `MyClass`)
raises `ValueError` at plugin load time.

## Return value

| Return type | Behaviour |
|-------------|-----------|
| `str` | The string is injected into the next LLM prompt so the agent can summarise the result. |
| `None` | Nothing is injected. |

Tools can also use `yield` to send real-time messages or terminate the event.

## Docstring format (Google-style)

```
"""Short description used as the LLM tool description.

Args:
    param1(string): Description of param1.
    param2(number): Description of param2. Default 42.
    param3(boolean): Description. Default false.
    param4(list[string]): Description of a string list.

Return schema (JSON):
    (optional — document the JSON shape for the LLM)
"""
```

### First line = tool description

The first paragraph (before any `Args:` / `Returns:` section) is used as the
tool's `description` in the function-calling schema.  Keep it short but
informative — the LLM reads this to decide when to call the tool.

### `Args:` section

Each entry: `name(type): description.`  The type is mandatory — omission
raises `ValueError` at load time.  The description should explain the
parameter's purpose and any default value if applicable.

### `Return schema (JSON)` block (optional but recommended)

When the tool returns a JSON string, document the discriminated-union shape
so the LLM knows what to expect.  Use TypeScript type notation.

## Required conventions for this plugin

1. **Do NOT put `event` or `self` in `Args:`** — framework-injected.
2. **Use JSON Schema type names** (`string`, `number`, `boolean`, `array`, `object`) in Args types for consistency with AstrBot examples.
3. **First line = tool description** for the LLM.  Make it a concise, self-contained sentence.
4. **Document the return schema** in a `Return schema (JSON):` block using TypeScript notation.
5. **All documentation is in English** per the Language Usage Guideline in `Working Guidelines.md`.
