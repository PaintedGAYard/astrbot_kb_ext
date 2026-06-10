"""Upload logic encapsulation — progress collection and result formatting."""

from __future__ import annotations

import os
import tempfile
import time
from collections.abc import Callable
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from astrbot.core.knowledge_base.kb_helper import KBHelper


class KnowledgeBaseUploader:
    """封装上传与进度收集逻辑，面向 Agent 优化输出。

    Upload logic with phase tracking for Agent-optimised output.
    Collects progress markers during processing and returns them
    in a single result, avoiding token waste on intermediate states.
    """

    def __init__(self, kb_helper: KBHelper) -> None:
        self._kb_helper = kb_helper
        self._phases: list[dict[str, Any]] = []

    def _make_progress_callback(self) -> Callable[[str, int, int], None]:
        """创建进度回调，收集处理阶段信息。

        Create a callback that records processing phase markers.
        """

        def _callback(stage: str, current: int, total: int) -> None:
            self._phases.append({
                "stage": stage,
                "current": current,
                "total": total,
            })

        return _callback

    async def upload(
        self,
        file_name: str,
        file_content: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> dict[str, Any]:
        """执行上传并返回结构化结果。

        Execute the upload and return a structured result.

        Args:
            file_name: 文件名（含扩展名）。
            file_content: 文件文本内容。
            chunk_size: 分块大小（字符数）。
            chunk_overlap: 分块重叠（字符数）。

        Returns:
            dict: 包含 result (str) 和 success (bool)。
        """
        self._phases.clear()
        start_time = time.monotonic()

        # 推断文件类型
        file_type = (
            file_name.rsplit(".", 1)[-1].lower()
            if "." in file_name
            else "txt"
        )

        # 写入临时文件
        tmp = tempfile.NamedTemporaryFile(
            suffix=f".{file_type}",
            delete=False,
        )
        try:
            tmp.write(file_content.encode("utf-8"))
            tmp.close()

            # 异步读取文件内容
            import aiofiles

            async with aiofiles.open(tmp.name, "rb") as f:
                raw_content = await f.read()

            # 调用上传 API，传入进度回调
            progress_cb = self._make_progress_callback()
            doc = await self._kb_helper.upload_document(
                file_name=file_name,
                file_content=raw_content,
                file_type=file_type,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                progress_callback=progress_cb,
            )

            elapsed = time.monotonic() - start_time

            # 格式化阶段报告
            phase_items = []
            for p in self._phases:
                stage = p["stage"]
                c, t = p["current"], p["total"]
                if t > 0:
                    phase_items.append(f"{stage}({c}/{t})")
                else:
                    phase_items.append(stage)
            phase_report = " → ".join(phase_items) if phase_items else "completed"

            result_text = (
                f"✅ 上传成功\n"
                f"- 文件名: {file_name}\n"
                f"- 知识库: {self._kb_helper.kb.kb_id}\n"
                f"- 文档ID: {doc.doc_id}\n"
                f"- 切片数: {doc.chunk_count}\n"
                f"- 处理流程: {phase_report}\n"
                f"- 耗时: {elapsed:.1f}s"
            )

            return {"success": True, "result": result_text}

        except Exception as e:
            elapsed = time.monotonic() - start_time
            return {
                "success": False,
                "result": (
                    f"❌ 上传失败\n"
                    f"- 文件名: {file_name}\n"
                    f"- 错误: {e!s}\n"
                    f"- 耗时: {elapsed:.1f}s\n"
                    f"建议检查文件格式或重试。"
                ),
            }
        finally:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
