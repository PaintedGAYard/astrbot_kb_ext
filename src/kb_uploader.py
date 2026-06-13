# MIT License
#
# Copyright (c) 2026 Mingxi "Lucien" Du
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Upload logic with retry, async background, and markdown extraction.

Internal methods return UploadResult dataclasses; LLM-friendly
formatting is done at the tool boundary in main.py.
"""

from __future__ import annotations

import asyncio
import base64
import os
import tempfile
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.core.knowledge_base.kb_helper import KBHelper

from astrbot.api import logger

from .markdown_extractor import MarkdownExtractor


# ── Parameter / result types ─────────────────────────────────────


@dataclass
class UploadParams:
    """Packed parameters for a single file upload.

    Args:
        file_name: File name with extension.
        raw_bytes: Raw file content.
        chunk_size: Characters per chunk.
        chunk_overlap: Character overlap between chunks.
        timeout: Max seconds per attempt (0 = infinite).
        max_retries: Retry count on failure.
        wait_completion: If True, block until vectorization completes.
        upload_task_id: UUID for async tracking (None for sync).
        extracted_as_markdown: When True, _run_upload uses "md" as file_type
            regardless of the file extension.  Set by _run when markdown
            extraction succeeded (all current extractors output Markdown).
    """
    file_name: str
    raw_bytes: bytes
    chunk_size: int = 512
    chunk_overlap: int = 50
    timeout: float = 100.0
    max_retries: int = 3
    wait_completion: bool = True
    upload_task_id: str | None = None
    extracted_as_markdown: bool = False


@dataclass
class UploadResult:
    """Structured upload result. Callers (LLM tools) may serialise to JSON.

    Args:
        success: True if the upload completed (synchronously or asynchronously).
        pending: True when the upload was submitted to background.
        doc_id: AstrBot document ID (only on sync success).
        chunk_count: Number of vector chunks created.
        error: Error message (only on failure).
        upload_task_id: UUID for tracking async uploads.
        kb_helper: KBHelper used (for building info in tool layer).
    """
    success: bool = False
    pending: bool = False
    doc_id: str | None = None
    chunk_count: int | None = None
    error: str | None = None
    upload_task_id: str | None = None
    kb_helper: Any | None = None
    detail: dict | None = None


# ── The uploader ─────────────────────────────────────────────────


class _AsyncUploadTask:
    """Encapsulates a background upload with shield protection and result storage.

    Wraps the asyncio.shield / short-wait / background-store pattern used by
    _upload_async.  One instance per async upload submission.
    """

    def __init__(self, uploader: KnowledgeBaseUploader, p: UploadParams) -> None:
        self._uploader = uploader
        self._p = p
        self._key = p.upload_task_id or p.file_name
        uploader._pending_store.pop(self._key, None)

    async def start(self) -> UploadResult:
        task = asyncio.create_task(self._background_upload())
        short_wait = min(self._p.timeout, 30) if self._p.timeout > 0 else 30

        try:
            r = await asyncio.wait_for(asyncio.shield(task), timeout=short_wait)
            return r if isinstance(r, UploadResult) else UploadResult(success=False, error="后台任务意外完成")
        except asyncio.TimeoutError:
            pass

        asyncio.create_task(self._store_result(task))
        return UploadResult(success=True, pending=True, upload_task_id=self._p.upload_task_id,
                            kb_helper=self._uploader._kb_helper)

    async def _background_upload(self) -> UploadResult:
        u = self._uploader
        for attempt in range(1, 4):
            u._phases.clear()
            try:
                return await u._run_upload(self._p, time.monotonic(), progress_key=self._key)
            except Exception as e:
                if attempt < 3:
                    await asyncio.sleep(1)
                    continue
                return UploadResult(success=False, error=str(e))
        return UploadResult(success=False, error="上传失败")

    async def _store_result(self, task: asyncio.Task) -> None:
        u = self._uploader
        try:
            r = await asyncio.shield(task)
            u._pending_store[self._key] = (
                {"success": r.success, "result": r}
                if isinstance(r, UploadResult) else r
            )
        except Exception as e:
            u._pending_store[self._key] = UploadResult(success=False, error=str(e))
        finally:
            if u._on_async_complete is not None:
                await u._on_async_complete(self._key)


class KnowledgeBaseUploader:
    """Upload files to an AstrBot knowledge base with retry & progress tracking.

    Two modes:
    - wait_completion=True (default): blocks until vectorization is done.
    - wait_completion=False: submits to background, caller checks
      get_pending_result(key) later.

    Side-effects:
    - _phases is mutated during _run_upload as progress callbacks fire.
      This is safe because _run_upload is awaited (single coroutine at a time).
    - _pending_store is mutated by background tasks and _store_result;
      callers must coordinate access (see _upload_async).
    """

    def __init__(
        self,
        kb_helper: KBHelper,
        pending_store: dict[str, dict[str, Any]] | None = None,
        on_async_complete: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._kb_helper = kb_helper
        self._pending_store: dict[str, dict[str, Any]] = (
            pending_store if pending_store is not None else {}
        )
        self._on_async_complete = on_async_complete
        self._phases: list[dict[str, Any]] = []

    async def upload(self, file_name: str, file_content: str, binary: bool = False,
                     chunk_size: int = 512, chunk_overlap: int = 50,
                     timeout: float = 100.0, max_retries: int = 3,
                     wait_completion: bool = True,
                     upload_task_id: str | None = None) -> UploadResult:
        """Upload file content (text or base64-encoded) to a knowledge base.

        Args:
            file_name(str): File name with extension.
            file_content(str): File content. Text passes through; binary must use binary=True.
            binary(bool): Whether file_content is base64-encoded. Default false.
            chunk_size(int): Chunk size in characters. Default 512.
            chunk_overlap(int): Chunk overlap in characters. Default 50.
            timeout(float): Per-attempt timeout in seconds. Default 100.
            max_retries(int): Number of retries on failure. Default 3.
            wait_completion(bool): Whether to wait for vectorization. Default true.
            upload_task_id(str | None): UUID for async tracking. Default None.

        Returns:
            UploadResult: Upload result dataclass.

        Raises:
            binascii.Error: binary=True but file_content is not valid base64.
            UnicodeEncodeError: file_content contains characters that cannot be encoded as UTF-8.
        """
        raw_bytes = base64.b64decode(file_content) if binary else file_content.encode("utf-8")
        params = UploadParams(file_name, raw_bytes, chunk_size, chunk_overlap,
                              timeout, max_retries, wait_completion, upload_task_id)
        return await self._run(params)

    async def upload_bytes(self, file_name: str, raw_bytes: bytes,
                           chunk_size: int = 512, chunk_overlap: int = 50,
                           timeout: float = 100.0, max_retries: int = 3,
                           wait_completion: bool = True,
                           upload_task_id: str | None = None) -> UploadResult:
        """Upload raw bytes directly (used by sandbox_path mode).

        Args:
            file_name(str): File name with extension.
            raw_bytes(bytes): Raw file content as bytes.
            chunk_size(int): Chunk size in characters. Default 512.
            chunk_overlap(int): Chunk overlap in characters. Default 50.
            timeout(float): Per-attempt timeout in seconds. Default 100.
            max_retries(int): Number of retries on failure. Default 3.
            wait_completion(bool): Whether to wait for vectorization. Default true.
            upload_task_id(str | None): UUID for async tracking. Default None.

        Returns:
            UploadResult: Upload result dataclass.
        """
        params = UploadParams(file_name, raw_bytes, chunk_size, chunk_overlap,
                              timeout, max_retries, wait_completion, upload_task_id)
        return await self._run(params)

    def get_pending_result(self, key: str) -> dict[str, Any] | None:
        """Non-blocking poll for an async upload's completion.

        The entry is removed from internal storage after retrieval (one-shot consume).

        Args:
            key(str): upload_task_id or file_name.

        Returns:
            dict | None: The result dict stored by the background task, or None.
        """
        return self._pending_store.pop(key, None)

    # ── Internal: dispatch & markdown extraction ──────────────────

    async def _run(self, p: UploadParams) -> UploadResult:
        """Apply markdown extraction, then dispatch to sync or async path.

        Side-effects: when markdown extraction succeeds, p.raw_bytes is replaced
        with the extracted text (encoded as UTF-8) and p.extracted_as_markdown
        is set to True so that _run_upload passes ``file_type="md"`` to AstrBot.
        The original file name has ``.md`` appended (e.g. ``report.xls`` →
        ``report.xls.md``) so that AstrBot's parser and chunker see the
        ``.md`` extension and treat the content as Markdown text, while
        preserving the original format identifier in the file name.
        """
        logger.info("Uploader._run: extracting %s (%d bytes)", p.file_name, len(p.raw_bytes))
        md = MarkdownExtractor.extract(p.raw_bytes, p.file_name)
        if md is not None:
            logger.info("Uploader._run: extraction succeeded, %d chars, replacing raw_bytes", len(md))
            p.raw_bytes = md.encode("utf-8")
            p.extracted_as_markdown = True
            p.file_name = f"{p.file_name}.md"
        else:
            logger.warning("Uploader._run: extraction returned None, keeping original raw_bytes")

        if not p.wait_completion:
            return await self._upload_async(p)

        return await self._upload_with_retry(p)

    async def _upload_with_retry(self, p: UploadParams) -> UploadResult:
        """Sync upload with retry loop."""
        last_error = ""
        for attempt in range(1, p.max_retries + 1):
            self._phases.clear()
            start = time.monotonic()
            try:
                return await self._run_upload(p, start)
            except asyncio.TimeoutError:
                last_error = f"上传超时（{p.timeout if p.timeout > 0 else '无限'}秒限制）"
            except asyncio.CancelledError:
                last_error = "上传被取消（可能是 AstrBot 框架的 120s 工具调用超时限制）"
            except Exception as e:
                last_error = str(e)
            if attempt < p.max_retries:
                await asyncio.sleep(1)
        return UploadResult(success=False, error=last_error)

    async def _upload_async(self, p: UploadParams) -> UploadResult:
        """Submit to background and return pending status.

        Uses asyncio.shield() to protect the background task from the
        framework's 120s tool-call timeout.  The result is stored in
        _pending_store under p.upload_task_id (or p.file_name as fallback).
        """
        task = _AsyncUploadTask(self, p)
        return await task.start()

    async def _run_upload(
        self, p: UploadParams, start_time: float,
        progress_key: str | None = None,
    ) -> UploadResult:
        """Single upload execution: write temp file → call kb_helper."""
        if p.extracted_as_markdown:
            file_type = "md"
        else:
            file_type = (
                p.file_name.rsplit(".", 1)[-1].lower()
                if "." in p.file_name else "txt"
            )
        tmp = tempfile.NamedTemporaryFile(suffix=f".{file_type}", delete=False)
        try:
            tmp.write(p.raw_bytes)
            tmp.close()

            progress_cb = self._make_progress_callback(progress_key)
            upload_coro = self._kb_helper.upload_document(
                file_name=p.file_name,
                file_content=p.raw_bytes,
                file_type=file_type,
                chunk_size=p.chunk_size,
                chunk_overlap=p.chunk_overlap,
                progress_callback=progress_cb,
            )
            doc = await (upload_coro if p.timeout <= 0
                         else asyncio.wait_for(upload_coro, timeout=p.timeout))

            return UploadResult(
                success=True,
                doc_id=doc.doc_id,
                chunk_count=doc.chunk_count,
                detail={"elapsed": time.monotonic() - start_time},
            )
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    def _make_progress_callback(
        self, progress_key: str | None = None,
    ) -> Callable[[str, int, int], None]:
        """Return a progress callback.

        Side-effect: appends to self._phases (safe because _run_upload is awaited).
        When progress_key is set, also writes to self._pending_store for external polling.
        """
        async def _cb(stage: str, current: int, total: int) -> None:
            entry = {"stage": stage, "current": current, "total": total}
            self._phases.append(entry)
            if progress_key is not None:
                self._pending_store[progress_key] = {
                    "status": "processing",
                    "stage": stage,
                    "current": current,
                    "total": total,
                }
        return _cb
