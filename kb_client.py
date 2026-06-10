"""
AstrBot KB API Client (minimal)
- 无人类可视化逻辑
- 无主动进度输出
- 仅提供 agent 可调用的查询接口
"""
import asyncio, json, os, time
from dataclasses import dataclass
from typing import Optional
import aiohttp


# ── Compact models ──────────────────────────────────────────────────────

@dataclass
class KBInfo:
    """知识库信息 (token-efficient)"""
    id: str          # kb_id
    name: str        # kb_name
    docs: int = 0    # doc_count
    chunks: int = 0  # chunk_count
    desc: str = ""   # description (truncated if needed)

    @classmethod
    def from_api(cls, d: dict) -> "KBInfo":
        return cls(
            id=d.get("kb_id",""),
            name=d.get("kb_name",""),
            docs=d.get("doc_count",0),
            chunks=d.get("chunk_count",0),
            desc=(d.get("description","") or "")[:200],
        )


@dataclass
class VecResult:
    """矢量化结果"""
    ok: bool = False
    doc_id: Optional[str] = None
    chunks: int = 0
    err: Optional[str] = None


@dataclass
class UpResult:
    """上传结果 (单文件)"""
    file: str = ""         # 文件名
    size: int = 0          # 字节数
    ok: bool = False       # 成功?
    doc_id: Optional[str] = None
    chunks: int = 0
    err: Optional[str] = None


# ── Client ───────────────────────────────────────────────────────────────

class KBClient:
    def __init__(self, base_url: str, auth_token: str, timeout: float = 180):
        self.url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {auth_token}"}
        self._timeout = timeout

    async def _sess(self):
        return aiohttp.ClientSession(headers=self._headers,
            timeout=aiohttp.ClientTimeout(total=self._timeout),
            connector=aiohttp.TCPConnector(limit=3))

    # ── list ────────────────────────────────────────────────────────

    async def list(self) -> list[KBInfo]:
        async with await self._sess() as s:
            async with s.get(f"{self.url}/api/kb/list") as r:
                r.raise_for_status()
                body = await r.json()
        if body.get("status") != "ok":
            raise ValueError(body.get("message","unknown"))
        return [KBInfo.from_api(it) for it in body.get("data",{}).get("items",[])]

    # ── upload single ───────────────────────────────────────────────

    async def upload(self, fp: str, kb_id: str,
                     chunk_size=512, chunk_overlap=50, batch_size=32,
                     retries=3, vec_timeout=600) -> UpResult:
        fn = os.path.basename(fp)
        fs = os.path.getsize(fp)

        task_id = None
        last_err = None

        for att in range(retries):
            tid, err = await self._post(fp, kb_id, chunk_size, chunk_overlap, batch_size)
            if tid:
                task_id = tid
                break
            last_err = err

        if not task_id:
            return UpResult(file=fn, size=fs, ok=False, err=last_err or "upload failed")

        vr = await self._poll(task_id, vec_timeout)
        if vr.ok:
            return UpResult(file=fn, size=fs, ok=True, doc_id=vr.doc_id, chunks=vr.chunks)
        else:
            return UpResult(file=fn, size=fs, ok=False, err=vr.err)

    async def _post(self, fp, kb_id, cs, co, bs):
        fn = os.path.basename(fp)
        form = aiohttp.FormData()
        form.add_field("file0", open(fp,"rb"), filename=fn)
        form.add_field("kb_id", kb_id)
        form.add_field("chunk_size", str(cs))
        form.add_field("chunk_overlap", str(co))
        form.add_field("batch_size", str(bs))
        form.add_field("tasks_limit", "1")
        form.add_field("max_retries", "3")

        async with await self._sess() as s:
            try:
                async with s.post(f"{self.url}/api/kb/document/upload", data=form) as r:
                    body = await r.json()
                if body.get("status")=="ok" and body.get("data",{}).get("task_id"):
                    return body["data"]["task_id"], None
                return None, body.get("message","upload failed")
            except Exception as e:
                return None, str(e)

    async def _poll(self, task_id, timeout):
        url = f"{self.url}/api/kb/document/upload/progress?task_id={task_id}"
        t0 = time.time()

        async with await self._sess() as s:
            while True:
                if timeout > 0 and (time.time() - t0) > timeout:
                    return VecResult(ok=False, err="timeout")
                try:
                    async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                        body = await r.json()
                    if body.get("status") != "ok":
                        await asyncio.sleep(2); continue
                    data = body.get("data", {})
                    st = data.get("status")
                    if st == "processing":
                        await asyncio.sleep(2); continue
                    if st == "completed":
                        uploaded = data.get("result",{}).get("uploaded",[])
                        if uploaded:
                            d = uploaded[0]
                            return VecResult(ok=True, doc_id=d.get("doc_id"), chunks=d.get("chunk_count",0))
                        return VecResult(ok=False, err="no documents in result")
                    await asyncio.sleep(2)
                except Exception:
                    await asyncio.sleep(2); continue
