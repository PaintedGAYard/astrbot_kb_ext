"""
AstrBot KB Tools Plugin (Agent-only, minimal output)

Tools:
  1. get_astrbot_kb_list    — 列出知识库
  2. add_astrbot_kb_document — 上传文档到知识库
"""

import asyncio, glob, json, os
from typing import Any
from .kb_client import KBClient


# ═══ Tool schemas (compact, JSON-native, token-efficient) ═══════════════

TOOL_KB_LIST = {
    "name": "get_astrbot_kb_list",
    "description": "列出 AstrBot 知识库。返回每个知识库的 id、名称、文档数、分块数、简介。",
    "parameters": {
        "type": "object",
        "properties": {
            "base_url":  {"type": "string", "description": "AstrBot 服务 URL"},
            "auth_token":{"type": "string", "description": "Bearer token (亦可设 env ASTRBOT_AUTH_TOKEN)"},
        },
        "required": ["base_url"],
    },
}

TOOL_KB_UPLOAD = {
    "name": "add_astrbot_kb_document",
    "description": "上传文档到 AstrBot 知识库。自动分块+向量化。支持 txt/md/docx/pdf。并发上传(N≥1)，含自动重试。",
    "parameters": {
        "type": "object",
        "properties": {
            "paths":       {"type": "array", "items": {"type": "string"}, "description": "文件路径列表，支持通配符"},
            "base_url":    {"type": "string", "description": "AstrBot 服务 URL"},
            "kb_id":       {"type": "string", "description": "目标知识库 ID"},
            "auth_token":  {"type": "string", "description": "Bearer token (亦可设 env ASTRBOT_AUTH_TOKEN)"},
            "chunk":       {"type": "integer", "default": 512, "description": "分块大小(字符数)"},
            "overlap":     {"type": "integer", "default": 50,  "description": "分块重叠(字符数)"},
            "batch":       {"type": "integer", "default": 32,  "description": "嵌入批大小"},
            "retries":     {"type": "integer", "default": 3,   "description": "单文件重试次数"},
            "parallel":    {"type": "integer", "default": 3,   "description": "并发上传数"},
            "timeout":     {"type": "number",  "default": 600, "description": "矢量化超时秒数(0=无限)"},
        },
        "required": ["paths", "base_url", "kb_id"],
    },
}


# ═══ Implementations ════════════════════════════════════════════════════

def _token(token: str) -> str:
    return token or os.environ.get("ASTRBOT_AUTH_TOKEN", "")


async def get_astrbot_kb_list(base_url: str, auth_token: str = "") -> str:
    """返回知识库列表 (JSON 字符串)"""
    tk = _token(auth_token)
    if not tk:
        return json.dumps({"ok": False, "err": "missing auth_token"}, ensure_ascii=False)

    c = KBClient(base_url, tk, timeout=30)
    try:
        kbs = await c.list()
        return json.dumps({
            "ok": True,
            "kbs": [{"id": k.id, "name": k.name, "docs": k.docs, "chunks": k.chunks, "desc": k.desc} for k in kbs],
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"ok": False, "err": str(e)}, ensure_ascii=False)


async def add_astrbot_kb_document(
    paths: list[str],
    base_url: str,
    kb_id: str,
    auth_token: str = "",
    chunk: int = 512,
    overlap: int = 50,
    batch: int = 32,
    retries: int = 3,
    parallel: int = 3,
    timeout: float = 600,
) -> str:
    """上传文档，返回结果 (JSON 字符串)"""
    tk = _token(auth_token)
    if not tk:
        return json.dumps({"ok": False, "err": "missing auth_token"}, ensure_ascii=False)

    # 展开通配符
    resolved: list[str] = []
    for pat in paths:
        g = glob.glob(pat, recursive=True)
        resolved.extend(g if g else [pat])
    valid = [p for p in resolved if os.path.isfile(p)]
    invalid = [p for p in resolved if not os.path.isfile(p)]

    if not valid:
        return json.dumps({"ok": False, "err": "no valid files", "invalid": invalid}, ensure_ascii=False)

    # 并发上传
    sem = asyncio.Semaphore(parallel)
    async def up_one(fp):
        async with sem:
            c = KBClient(base_url, tk, timeout=timeout + 60)
            try:
                r = await c.upload(fp, kb_id, chunk, overlap, batch, retries, timeout)
                return r
            finally:
                pass  # 每个 client 用完即弃，依赖 GC

    tasks = [up_one(p) for p in valid]
    results: list[object] = await asyncio.gather(*tasks)

    # 汇总 (token-efficient JSON)
    succeeded = []
    failed = []
    for r in results:
        if r.ok:
            succeeded.append({"f": r.file, "did": r.doc_id, "n": r.chunks})
        else:
            failed.append({"f": r.file, "err": r.err})

    # Compact output schema:
    # {ok, n_ok, n_fail, ok:[{f,did,n}], fail:[{f,err}], invalid:[...]}
    out = {
        "ok": len(failed) == 0,
        "n_ok": len(succeeded),
        "n_fail": len(failed),
        "ok_files": succeeded,
        "fail_files": failed,
    }
    if invalid:
        out["invalid"] = invalid

    return json.dumps(out, ensure_ascii=False)


# ═══ Plugin registration ════════════════════════════════════════════════

PLUGIN_NAME = "astrbot_kb_tools"
PLUGIN_VERSION = "2.0.0"
PLUGIN_DESCRIPTION = "AstrBot KB tools for agent: list & upload documents"
DEPENDENCIES = ["aiohttp"]

TOOLS = [
    (TOOL_KB_LIST, get_astrbot_kb_list),
    (TOOL_KB_UPLOAD, add_astrbot_kb_document),
]
