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

"""Upload logic encapsulation — progress collection and result formatting."""

from __future__ import annotations

import asyncio
import base64
import io
import os
import tempfile
import time
from collections.abc import Callable, Coroutine
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.core.knowledge_base.kb_helper import KBHelper


class KnowledgeBaseUploader:
    """封装上传与进度收集逻辑，面向 Agent 优化输出。

    Upload logic with phase tracking for Agent-optimised output.
    Collects progress markers during processing and returns them
    in a single result, avoiding token waste on intermediate states.

    Supports two modes:
    - wait_completion=True (default): blocks until vectorization is done.
    - wait_completion=False: submits to background, returns pending status;
      caller should poll get_pending_result(file_name) for completion.
    """

    def __init__(
        self,
        kb_helper: KBHelper,
        pending_store: dict[str, dict[str, Any]] | None = None,
        on_async_complete: Callable[[str], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._kb_helper = kb_helper
        self._phases: list[dict[str, Any]] = []
        # 异步上传后台任务完成后的结果存储（可共享，跨工具调用存活）
        self._pending_store: dict[str, dict[str, Any]] = pending_store if pending_store is not None else {}
        # 异步上传完成回调（由插件传入，用于清理并发锁）
        self._on_async_complete = on_async_complete

    def _make_progress_callback(self, progress_key: str | None = None) -> Callable[[str, int, int], None]:
        """创建进度回调，收集处理阶段信息。
        progress_key 不为空时，同步更新 _pending_store[progress_key] 用于外部轮询进度。"""
        async def _callback(stage: str, current: int, total: int) -> None:
            entry = {"stage": stage, "current": current, "total": total}
            self._phases.append(entry)
            if progress_key is not None:
                self._pending_store[progress_key] = {
                    "status": "processing",
                    "stage": stage,
                    "current": current,
                    "total": total,
                }
        return _callback

    # ── Public upload methods ─────────────────────────────────────

    async def upload(
        self,
        file_name: str,
        file_content: str,
        binary: bool = False,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        timeout: float = 100.0,
        max_retries: int = 3,
        wait_completion: bool = True,
        upload_task_id: str | None = None,
    ) -> dict[str, Any]:
        """执行上传并返回结构化结果。

        Execute the upload and return a structured result.

        Args:
            file_name: 文件名（含扩展名）。
            file_content: 文本内容；若 binary=True 则为 base64 编码的原始数据。
            binary: 是否将 file_content 视为 base64 编码。
            chunk_size: 分块大小。
            chunk_overlap: 分块重叠。
            timeout: 单次同步尝试超时秒数。默认 100。
                超过 100s 的文件说明向量化耗时较长，不要试图增大 timeout，
                请改用 wait_completion=false 异步模式。
            max_retries: 失败重试次数。默认 3。
            wait_completion: 是否等待向量化完成。默认 True。
                设为 False 时上传进入后台处理，适用于同步超时的文件。
            upload_task_id: UUID 用于跟踪，替代 file_name 作为 pending_store 键。

        Returns:
            dict: 包含 result (str) 和 success (bool)。
                  若 wait_completion=False 且未完成，返回 pending 状态。
        """
        file_type = (
            file_name.rsplit(".", 1)[-1].lower()
            if "." in file_name else "txt"
        )
        raw_bytes = base64.b64decode(file_content) if binary else file_content.encode("utf-8")
        md = self._extract_markdown(raw_bytes, file_name)
        if md is not None:
            raw_bytes = md.encode("utf-8")
            file_type = "md"
        return await self._upload_with_retry(file_name, file_type, raw_bytes, chunk_size, chunk_overlap, timeout, max_retries, wait_completion, upload_task_id)

    async def upload_bytes(
        self,
        file_name: str,
        raw_bytes: bytes,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        timeout: float = 100.0,
        max_retries: int = 3,
        wait_completion: bool = True,
        upload_task_id: str | None = None,
    ) -> dict[str, Any]:
        """直接上传原始字节数据（由 sandbox_path 模式调用）。

        Upload raw bytes directly (called by sandbox_path mode).

        Args:
            upload_task_id: UUID 用于跟踪，替代 file_name 作为 pending_store 的键。
        """
        file_type = (
            file_name.rsplit(".", 1)[-1].lower()
            if "." in file_name else "txt"
        )
        md = self._extract_markdown(raw_bytes, file_name)
        if md is not None:
            raw_bytes = md.encode("utf-8")
            file_type = "md"
        return await self._upload_with_retry(
            file_name, file_type, raw_bytes,
            chunk_size, chunk_overlap,
            timeout, max_retries, wait_completion, upload_task_id,
        )

    async def get_pending_result(self, key: str) -> dict[str, Any] | None:
        """获取后台上传任务的完成结果（非阻塞）。key 是 upload_task_id 或 file_name。"""
        return self._pending_store.pop(key, None)

    # ── Core: retry + timeout wrapper ─────────────────────────────

    async def _upload_with_retry(
        self, file_name: str, file_type: str, raw_bytes: bytes,
        chunk_size: int, chunk_overlap: int,
        timeout: float, max_retries: int,
        wait_completion: bool,
        upload_task_id: str | None = None,
    ) -> dict[str, Any]:
        """带重试和超时的上传核心逻辑。"""
        if not wait_completion:
            return await self._upload_async(file_name, file_type, raw_bytes, chunk_size, chunk_overlap, timeout, upload_task_id)

        last_error = ""
        for attempt in range(1, max_retries + 1):
            self._phases.clear()
            start = time.monotonic()
            try:
                result = await self._run_upload(file_name, file_type, raw_bytes, chunk_size, chunk_overlap, timeout, start)
                if attempt > 1:
                    result["result"] = result["result"].replace("✅", f"✅ (第{attempt}次尝试成功)")
                return result
            except asyncio.TimeoutError:
                last_error = f"上传超时（{timeout if timeout > 0 else '无限'}秒限制）"
            except asyncio.CancelledError:
                last_error = "上传被取消（可能是 AstrBot 框架的 120s 工具调用超时限制）"
            except Exception as e:
                last_error = str(e)
            if attempt < max_retries:
                await asyncio.sleep(1)
        elapsed = time.monotonic() - start if 'start' in dir() else 0
        return {
            "success": False,
            "result": (
                f"❌ 上传失败（已重试 {max_retries} 次）\n"
                f"- 文件名: {file_name}\n"
                f"- 错误: {last_error}"
            ),
        }

    async def _upload_async(
        self, file_name: str, file_type: str, raw_bytes: bytes,
        chunk_size: int, chunk_overlap: int,
        timeout: float,
        upload_task_id: str | None = None,
    ) -> dict[str, Any]:
        """异步模式：后台执行上传，短等待后返回 pending 状态。

        使用 asyncio.shield() 保护后台任务不被框架 120s 超时取消。
        任务完成后结果存入 _pending_store，key 优先使用 upload_task_id。
        """
        key = upload_task_id or file_name
        self._pending_store.pop(key, None)

        async def _background_upload():
            """后台上传任务"""
            start = time.monotonic()
            for attempt in range(1, 4):  # 至多重试 3 次
                self._phases.clear()
                try:
                    return await self._run_upload(file_name, file_type, raw_bytes, chunk_size, chunk_overlap, 0, start, progress_key=key)
                except Exception as e:
                    if attempt < 3:
                        await asyncio.sleep(1)
                        continue
                    return {
                        "success": False,
                        "result": (
                            f"❌ 后台上传失败（重试 {attempt - 1} 次后放弃）\n"
                            f"- 文件名: {file_name}\n"
                            f"- 错误: {e!s}"
                        ),
                    }
            return {"success": False, "result": f"❌ {file_name}: 上传失败"}

        # 启动后台任务（shield 保护，避免被框架 timeout 取消）
        task = asyncio.create_task(_background_upload())

        # 短等待初始结果
        short_wait = min(timeout, 30) if timeout > 0 else 30
        try:
            result = await asyncio.wait_for(asyncio.shield(task), timeout=short_wait)
            return result
        except asyncio.TimeoutError:
            pass

        async def _store_result():
            try:
                result = await asyncio.shield(task)
                self._pending_store[key] = result
            except asyncio.CancelledError:
                self._pending_store[key] = {
                    "success": False,
                    "result": f"❌ {file_name}: 后台上传被取消",
                }
            except Exception as e:
                self._pending_store[key] = {
                    "success": False,
                    "result": f"❌ {file_name}: 后台上传失败 — {e!s}",
                }
            finally:
                if self._on_async_complete is not None:
                    await self._on_async_complete(key)

        asyncio.create_task(_store_result())

        return {
            "success": True,
            "pending": True,
            "result": (
                f"⏳ 文件已提交后台处理\n"
                f"- 文件名: {file_name}\n"
                f"- 知识库: {self._kb_helper.kb.kb_id}\n"
                f"- 状态: 向量化处理中，请使用 astr_kb_check_upload 查询完成状态"
            ),
        }

    async def _run_upload(
        self, file_name: str, file_type: str, raw_bytes: bytes,
        chunk_size: int, chunk_overlap: int,
        timeout: float, start_time: float,
        progress_key: str | None = None,
    ) -> dict[str, Any]:
        """单次上传执行（写入临时文件 → 调用 kb_helper）。"""
        tmp = tempfile.NamedTemporaryFile(suffix=f".{file_type}", delete=False)
        try:
            tmp.write(raw_bytes)
            tmp.close()

            progress_cb = self._make_progress_callback(progress_key)
            upload_coro = self._kb_helper.upload_document(
                file_name=file_name,
                file_content=raw_bytes,
                file_type=file_type,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                progress_callback=progress_cb,
            )
            doc = await upload_coro if timeout <= 0 else await asyncio.wait_for(upload_coro, timeout=timeout)

            elapsed = time.monotonic() - start_time
            phase_items = []
            for p in self._phases:
                stage = p["stage"]
                c, t = p["current"], p["total"]
                phase_items.append(f"{stage}({c}/{t})" if t > 0 else stage)
            phase_report = " → ".join(phase_items) if phase_items else "completed"

            return {
                "success": True,
                "result": (
                    f"✅ 上传成功\n"
                    f"- 文件名: {file_name}\n"
                    f"- 知识库: {self._kb_helper.kb.kb_id}\n"
                    f"- 文档ID: {doc.doc_id}\n"
                    f"- 切片数: {doc.chunk_count}\n"
                    f"- 处理流程: {phase_report}\n"
                    f"- 耗时: {elapsed:.1f}s"
                ),
            }
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    @staticmethod
    def _extract_markdown(raw_bytes: bytes, file_name: str) -> str | None:
        """将支持的格式提取为干净 Markdown 文本，绕过 AstrBot 内置文本化逻辑。

        返回 None 表示不需要自定义提取（AstrBot 原生支持良好）。
        """
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        if ext == "xlsx":
            return KnowledgeBaseUploader._xlsx_to_markdown(raw_bytes)
        # 未来可在此处添加更多格式：doc, ppt 等
        return None

    @staticmethod
    def _xlsx_to_markdown(raw_bytes: bytes) -> str:
        """将 .xlsx 转换为干净的 Markdown 表格，每工作表一个 section。

        使用 openpyxl 直接读取单元格值，自行构建 Markdown 表格，
        完全绕过 pandas.to_html() 的 NaN 问题。
        """
        import openpyxl

        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        parts: list[str] = []

        for ws in wb.worksheets:
            rows_data: list[list[str]] = []
            for row in ws.iter_rows(values_only=True):
                # 跳过全空行
                cleaned = [
                    str(c).strip() if c is not None else ""
                    for c in row
                ]
                if all(v == "" for v in cleaned):
                    continue
                rows_data.append(cleaned)

            if not rows_data:
                continue

            parts.append(f"## {ws.title}\n")

            # 表头
            parts.append("| " + " | ".join(rows_data[0]) + " |")
            parts.append("| " + " | ".join("---" for _ in rows_data[0]) + " |")

            # 数据行
            for row in rows_data[1:]:
                # 补齐短行
                while len(row) < len(rows_data[0]):
                    row.append("")
                parts.append("| " + " | ".join(row) + " |")

            parts.append("")

        return "\n".join(parts)
