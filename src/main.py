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

"""AstrBot Knowledge Base Extended Access Plugin — main entry point.

Provides Agent-facing LLM tools:
  - astr_kb_list              : List available knowledge bases
  - astr_kb_upload            : Upload a file to a knowledge base
  - astr_kb_create            : Create a new knowledge base
  - astr_kb_delete            : Delete a knowledge base
  - astr_kb_delete_document   : Delete a document from a knowledge base
  - astr_kb_list_documents    : List documents in a knowledge base
  - astr_kb_get_document      : Get full text content of a document

All tools bypass HTTP and directly call kb_manager Python APIs within
the AstrBot process. Access is controlled by KbAccessControl
(whitelist/blacklist).
"""

from astrbot.api import logger
from astrbot.api import star, llm_tool
from astrbot.api.event import AstrMessageEvent

from .access_control import KbAccessControl
from .kb_uploader import KnowledgeBaseUploader, UploadResult

import datetime
import functools
import json as _json
import uuid


# ── Shared tool error handler ────────────────────────────────────


def tool_error_handler(func):
    """Decorator for @llm_tool methods that translates exceptions to structured JSON."""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except PermissionError as e:
            return _json.dumps({"s": False, "d": None, "e": f"权限不足: {e}"})
        except Exception as e:
            logger.error(f"Tool {func.__name__} failed: {e}")
            return _json.dumps({"s": False, "d": None, "e": str(e)})
    return wrapper


class AstrBotKnowledgeBaseExtAccess(star.Star):
    """AstrBot Knowledge Base Extended Access Plugin — main entry point.

    Provides Agent-facing LLM tools:
      - astr_kb_list              : List available knowledge bases
      - astr_kb_upload            : Upload a file to a knowledge base
      - astr_kb_create            : Create a new knowledge base
      - astr_kb_delete            : Delete a knowledge base
      - astr_kb_delete_document   : Delete a document from a knowledge base
      - astr_kb_list_documents    : List documents in a knowledge base
      - astr_kb_get_document      : Get full text content of a document

    All tools bypass HTTP and directly call kb_manager Python APIs within
    the AstrBot process. Access is controlled by KbAccessControl
    (whitelist/blacklist).
    """

    def __init__(
        self,
        context: star.Context,
        config: dict | None = None,
    ) -> None:
        self.context = context
        raw_config = dict(config) if config else {}
        self.access_control = KbAccessControl(raw_config)
        self._avg_embedding_time: float = float(
            raw_config.get("avg_embedding_time", 1.5)
        )
        self._async_pending: dict[str, dict] = {}  # upload_task_id → result/progress

    async def initialize(self) -> None:
        """Initialise the plugin: validate config, register plugin page APIs.

        Also loads persisted kb_id lists from the config JSON file.
        """
        try:
            self.access_control.validate_config()
        except ValueError as e:
            logger.error("astrbot_kb_ext_access: invalid config — %s", e)

        self._load_config_from_file()

        logger.info(
            "astrbot_kb_ext_access: mode=%s, whitelist=%s, blacklist=%s",
            self.access_control.mode,
            sorted(self.access_control.whitelist),
            sorted(self.access_control.blacklist),
        )

        # Plugin page API routes must start with the plugin name so that
        # _match_registered_web_api matches <plugin_name>/<endpoint> correctly.
        pfx = f"/{self.name}" if hasattr(self, "name") and self.name else ""
        self.context.register_web_api(
            route=f"{pfx}/access-control/kb-list",
            view_handler=self._api_kb_list,
            methods=["GET"],
            desc="获取知识库列表（ID + 名称）",
        )
        self.context.register_web_api(
            route=f"{pfx}/access-control/config",
            view_handler=self._api_get_config,
            methods=["GET"],
            desc="获取当前访问控制配置",
        )
        self.context.register_web_api(
            route=f"{pfx}/access-control/save",
            view_handler=self._api_save_config,
            methods=["POST"],
            desc="保存访问控制配置",
        )

    async def _api_kb_list(self):
        """Return all knowledge bases for the plugin settings page."""
        from quart import jsonify
        try:
            kbs = await self.context.kb_manager.list_kbs()
            items = [
                {
                    "kb_id": kb.kb_id,
                    "kb_name": kb.kb_name,
                    "emoji": kb.emoji or "📚",
                    "description": kb.description or "",
                    "doc_count": kb.doc_count,
                    "chunk_count": kb.chunk_count,
                }
                for kb in (kbs or [])
            ]
            return jsonify({"status": "ok", "data": {"items": items}})
        except Exception as e:
            logger.error("astrbot_kb_ext_access: _api_kb_list failed — %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    async def _api_get_config(self):
        """Return the current access control configuration."""
        from quart import jsonify
        return jsonify({
            "status": "ok",
            "data": {
                "kb_access_control": {
                    "mode": self.access_control.mode,
                    "whitelist": sorted(self.access_control.whitelist),
                    "blacklist": sorted(self.access_control.blacklist),
                }
            },
        })

    async def _api_save_config(self):
        """Save access control configuration (pure kb_id, no name resolution)."""
        from quart import jsonify, request

        try:
            body = await request.json
            if not body:
                return jsonify({"status": "error", "message": "empty body"}), 400

            kb_ac = body.get("kb_access_control", {})
            mode = kb_ac.get("mode", "whitelist")
            whitelist = kb_ac.get("whitelist", [])
            blacklist = kb_ac.get("blacklist", [])

            if not isinstance(whitelist, list) or not isinstance(blacklist, list):
                return jsonify({"status": "error", "message": "invalid format"}), 400
            if mode not in ("whitelist", "blacklist"):
                return jsonify({"status": "error", "message": "invalid mode"}), 400

            self.access_control.mode = mode
            self.access_control.whitelist = set(whitelist)
            self.access_control.blacklist = set(blacklist)

            self._persist_config()

            return jsonify({"status": "ok", "data": {"message": "saved"}})

        except Exception as e:
            logger.error("astrbot_kb_ext_access: save config failed — %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    def _load_config_from_file(self) -> None:
        """Load persisted kb_id lists from the plugin config JSON file."""
        import json as pyjson
        import os

        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_config_path
            config_path = os.path.join(
                get_astrbot_config_path(),
                "astrbot_kb_ext_access_config.json",
            )
            if not os.path.exists(config_path):
                return
            with open(config_path, "r", encoding="utf-8-sig") as f:
                disk_config = pyjson.load(f)
            kb_ac = disk_config.get("kb_access_control", {})
            if "whitelist" in kb_ac:
                self.access_control.whitelist = set(kb_ac["whitelist"])
            if "blacklist" in kb_ac:
                self.access_control.blacklist = set(kb_ac["blacklist"])
        except Exception as e:
            logger.warning("astrbot_kb_ext_access: failed to load config file — %s", e)

    @llm_tool(name="astr_kb_list")
    async def list_knowledge_bases(
        self,
        event: AstrMessageEvent,
        query: str = "",
    ) -> str:
        """List all available knowledge bases in AstrBot.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // list of knowledge bases
                    "kb_id": string,
                    "kb_name": string,
                    "doc_count": number,
                    "chunk_count": number,
                    "description": string | null
                }[],
                "e": null // no error
            } | {
                "s": false, // error
                "d": null,
                "e": string // error message
            }
            ```

        Args:
            query(string): Optional keyword to filter knowledge bases by name.
        """
        kbs = await self.context.kb_manager.list_kbs()
        kbs = self.access_control.filter_kb_list(kbs)
        if query:
            q = query.lower()
            kbs = [kb for kb in kbs if q in kb.kb_name.lower()]

        data = [
            {
                "kb_id": kb.kb_id,
                "kb_name": kb.kb_name,
                "doc_count": kb.doc_count,
                "chunk_count": kb.chunk_count,
                "description": (kb.description or "").strip() or None,
            }
            for kb in kbs
        ]
        return _json.dumps({"s": True, "d": data, "e": None})

    @llm_tool(name="astr_kb_upload")
    async def upload_to_knowledge_base(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        file_name: str,
        file_content: str = "",
        binary: bool = False,
        sandbox_path: str = "",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        timeout: float = 100.0,
        max_retries: int = 3,
        wait_completion: bool = True,
    ) -> str:
        """Upload file content to a specified knowledge base.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // sync upload succeeded
                    "pending": false,
                    "doc_id": string,
                    "file_name": string,
                    "chunk_count": number,
                    "kb_id": string
                },
                "e": null
            } | {
                "s": true, // submitted to background
                "d": {
                    "pending": true,
                    "upload_task_id": string,
                    "file_name": string,
                    "kb_id": string
                },
                "e": null
            } | {
                "s": false, // error
                "d": null,
                "e": string
            }
            ```

        Args:
            kb_id(string): Target knowledge base ID.
            file_name(string): File name with extension.
            file_content(string): File content as text. For binary files use binary=True or sandbox_path.
            binary(boolean): Whether file_content is base64-encoded. Default false.
            sandbox_path(string): Sandbox file path, takes priority over file_content/binary.
            chunk_size(number): Chunk size in characters. Default 512.
            chunk_overlap(number): Chunk overlap in characters. Default 50.
            timeout(number): Per-attempt timeout in seconds. Default 100, 0 = unlimited.
            max_retries(number): Number of retries on failure. Default 3.
            wait_completion(boolean): Whether to wait for vectorization.
                Set to false for background upload (returns upload_task_id).
        """
        self.access_control.check_kb_access(kb_id)
        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return _json.dumps({"s": False, "d": None, "e": f"知识库 {kb_id} 不存在。"})

        if not wait_completion:
            if await self._has_active_upload_lock():
                return _json.dumps({"s": False, "d": None, "e": "已有异步上传进行中（存在活跃的 upload_check cron job）"})
            upload_task_id = str(uuid.uuid4())
            self._async_pending[upload_task_id] = {"pending": True, "file_name": file_name, "kb_id": kb_id}
        else:
            upload_task_id = None

        async def _on_async_done(done_uid: str) -> None:
            pass  # Lock is managed by the cron job; no manual release needed

        uploader = KnowledgeBaseUploader(
            kb_helper,
            pending_store=self._async_pending,
            on_async_complete=_on_async_done,
        )

        if sandbox_path:
            raw_bytes = await self._read_sandbox_file(event, sandbox_path)
            if raw_bytes is None:
                return _json.dumps({"s": False, "d": None, "e": "无法从沙箱读取文件"})
            result = await uploader.upload_bytes(
                file_name=file_name, raw_bytes=raw_bytes,
                chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                timeout=timeout, max_retries=max_retries,
                wait_completion=wait_completion,
                upload_task_id=upload_task_id,
            )
        else:
            result = await uploader.upload(
                file_name=file_name, file_content=file_content, binary=binary,
                chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                timeout=timeout, max_retries=max_retries,
                wait_completion=wait_completion,
                upload_task_id=upload_task_id,
            )

        if result.pending:
            return _json.dumps({"s": True, "d": {"pending": True, "upload_task_id": upload_task_id, "file_name": file_name, "kb_id": kb_id}, "e": None})
        if result.success:
            return _json.dumps({"s": True, "d": {"pending": False, "doc_id": result.doc_id, "file_name": file_name, "chunk_count": result.chunk_count, "kb_id": kb_id}, "e": None})
        return _json.dumps({"s": False, "d": None, "e": result.error or "上传失败"})

    @llm_tool(name="astr_kb_upload_batch")
    async def upload_to_knowledge_base_batch(
        self,
        event: AstrMessageEvent,
        files: list,
    ) -> str:
        """Batch upload multiple files to a knowledge base, sequentially, blocking.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // batch results
                    "total": number,
                    "success": number,
                    "fail": number,
                    "results": {
                        "i": number, // item index (1-based)
                        "file_name": string | null,
                        "ok": boolean,
                        "e": string | null // error message if failed
                    }[]
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            files(array): List of upload tasks. Each item is a dict:
                - kb_id(string): Required.
                - file_name(string): Required.
                - file_content(string): Optional.
                - binary(boolean): Optional.
                - sandbox_path(string): Optional.
                - chunk_size(number): Optional.
                - chunk_overlap(number): Optional.
                - timeout(number): Optional, default 100.
                - max_retries(number): Optional, default 3.
        """
        if not files:
            return _json.dumps({"s": False, "d": None, "e": "文件列表为空。"})
        if len(files) > 20:
            return _json.dumps({"s": False, "d": None, "e": "单次最多上传 20 个文件。"})

        item_results: list[dict] = []
        success_count = 0
        fail_count = 0

        for i, item in enumerate(files, 1):
            if not isinstance(item, dict):
                item_results.append({"i": i, "file_name": None, "ok": False, "e": "无效的条目格式"})
                fail_count += 1
                continue

            kb_id = item.get("kb_id", "")
            file_name = item.get("file_name", "")
            if not kb_id or not file_name:
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": "缺少 kb_id 或 file_name"})
                fail_count += 1
                continue

            try:
                self.access_control.check_kb_access(kb_id)
            except PermissionError as e:
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": f"权限不足: {e}"})
                fail_count += 1
                continue

            kb_helper = await self.context.kb_manager.get_kb(kb_id)
            if not kb_helper:
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": f"知识库 {kb_id} 不存在"})
                fail_count += 1
                continue

            uploader = KnowledgeBaseUploader(kb_helper,
                pending_store=self._async_pending,
            )
            timeout = float(item.get("timeout", 100))
            max_retries = int(item.get("max_retries", 3))
            sandbox_path = item.get("sandbox_path", "") or ""
            file_content = item.get("file_content", "") or ""
            binary = bool(item.get("binary", False))
            chunk_size = int(item.get("chunk_size", 512))
            chunk_overlap = int(item.get("chunk_overlap", 50))

            try:
                if sandbox_path:
                    raw = await self._read_sandbox_file(event, sandbox_path)
                    if raw is None:
                        item_results.append({"i": i, "file_name": file_name, "ok": False, "e": "沙箱读取失败"})
                        fail_count += 1
                        continue
                    r = await uploader.upload_bytes(
                        file_name=file_name, raw_bytes=raw,
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                        timeout=timeout, max_retries=max_retries,
                        wait_completion=True,
                    )
                else:
                    r = await uploader.upload(
                        file_name=file_name, file_content=file_content, binary=binary,
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
                        timeout=timeout, max_retries=max_retries,
                        wait_completion=True,
                    )
            except Exception as e:
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": str(e)})
                fail_count += 1
                continue

            if r.success:
                success_count += 1
                item_results.append({"i": i, "file_name": file_name, "ok": True, "e": None})
            else:
                fail_count += 1
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": r.error or "上传失败"})

        return _json.dumps({
            "s": True,
            "d": {
                "total": len(files),
                "success": success_count,
                "fail": fail_count,
                "results": item_results,
            },
            "e": None,
        })

    @llm_tool(name="astr_kb_check_upload")
    async def check_upload_status(
        self,
        event: AstrMessageEvent,
        upload_task_id: str = "",
        file_name: str = "",
        kb_id: str = "",
    ) -> str:
        """Query the completion status of a background upload.

        Uses upload_task_id (UUID) first, falls back to file_name + kb_id.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // completed
                    "status": "completed",
                    "doc_id": string,
                    "chunk_count": number
                },
                "e": null
            } | {
                "s": true,
                "d": { // still processing
                    "status": "processing",
                    "stage": "pending" | "parsing" | "chunking" | "embedding" | "extracting" | "cleaning" | "unknown",
                    "current": number,
                    "total": number
                },
                "e": null
            } | {
                "s": true,
                "d": { "status": "not_found" }, // file not in KB yet
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            upload_task_id(string): Upload task UUID (returned by astr_kb_upload, recommended).
            file_name(string): File name (fallback when upload_task_id is empty).
            kb_id(string): Knowledge base ID (fallback when upload_task_id is empty).
        """
        if upload_task_id:
            cached = self._async_pending.get(upload_task_id)
            if cached:
                if "stage" in cached:
                    return _json.dumps({"s": True, "d": {
                        "status": "processing",
                        "stage": cached["stage"],
                        "current": cached.get("current", 0),
                        "total": cached.get("total", 100),
                    }, "e": None})
                if cached.get("pending"):
                    return _json.dumps({"s": True, "d": {"status": "processing", "stage": "pending", "current": 0, "total": 0}, "e": None})
                if cached.get("success"):
                    self._async_pending.pop(upload_task_id, None)
                    return _json.dumps({"s": True, "d": {"status": "completed", "doc_id": cached.get("doc_id"), "chunk_count": cached.get("chunk_count")}, "e": None})
                self._async_pending.pop(upload_task_id, None)
                return _json.dumps({"s": False, "d": None, "e": cached.get("result", "上传失败")})

            if await self._has_active_upload_lock():
                return _json.dumps({"s": True, "d": {"status": "processing", "stage": "unknown", "current": 0, "total": 0}, "e": None})

        if file_name and kb_id:
            try:
                self.access_control.check_kb_access(kb_id)
            except PermissionError:
                pass  # Read-only check; don't block

            kb_helper = await self.context.kb_manager.get_kb(kb_id)
            if not kb_helper:
                return _json.dumps({"s": False, "d": None, "e": f"知识库 {kb_id} 不存在。"})
            try:
                docs = await kb_helper.list_documents()
            except Exception as e:
                return _json.dumps({"s": False, "d": None, "e": f"查询失败: {e}"})
            for doc in docs or []:
                if doc.file_name == file_name or doc.doc_id == file_name:
                    chunk_count = getattr(doc, "chunk_count", 0)
                    if chunk_count > 0:
                        return _json.dumps({"s": True, "d": {"status": "completed", "doc_id": doc.doc_id, "chunk_count": chunk_count}, "e": None})
                    return _json.dumps({"s": True, "d": {"status": "processing"}, "e": None})
            return _json.dumps({"s": True, "d": {"status": "not_found"}, "e": None})

        return _json.dumps({"s": False, "d": None, "e": "请提供 upload_task_id，或 file_name + kb_id。"})

    @llm_tool(name="astr_kb_schedule_check")
    async def schedule_upload_check(
        self,
        event: AstrMessageEvent,
        upload_task_id: str,
        interval_seconds: int,
        note_text: str = "",
    ) -> str:
        """Schedule a recurring FutureTask to check upload status.

        The scheduled job survives plugin restarts.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // scheduled
                    "job_id": string,
                    "upload_task_id": string,
                    "interval_seconds": number
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            upload_task_id(string): Upload task UUID (returned by astr_kb_upload).
            interval_seconds(number): Polling interval in seconds. Minimum 180 (3 minutes).
            note_text(string): Instruction to execute when woken. Auto-generated by default.
        """
        cron_mgr = getattr(self.context, "cron_manager", None)
        if cron_mgr is None:
            return _json.dumps({"s": False, "d": None, "e": "cron_manager 不可用，请启用主动型能力。"})

        interval = max(180, int(interval_seconds))

        pending_info = self._async_pending.get(upload_task_id, {})
        file_name = pending_info.get("file_name", upload_task_id[:8])

        default_note = (
            f"Call astr_kb_check_upload(upload_task_id='{upload_task_id}'). "
            f"If status is 'completed', report the doc_id and chunk_count. "
            f"If status is 'processing', do nothing — cron will fire again."
        )

        payload = {
            "session": event.unified_msg_origin,
            "sender_id": event.get_sender_id(),
            "upload_task_id": upload_task_id,
            "file_name": file_name,
            "note": note_text or default_note,
            "origin": "plugin_upload_check",
        }

        try:
            from astrbot.core.cron.manager import CronJobSchedulingError
            job = await cron_mgr.add_active_job(
                name=f"upload_check_{upload_task_id[:12]}",
                cron_expression=f"*/{interval} * * * * *",
                payload=payload,
                description=note_text or default_note,
                run_once=False,
            )
        except CronJobSchedulingError:
            return _json.dumps({"s": False, "d": None, "e": "cron 调度器配置无效。"})
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": str(e)})

        return _json.dumps({
            "s": True,
            "d": {
                "job_id": job.job_id,
                "upload_task_id": upload_task_id,
                "interval_seconds": interval,
            },
            "e": None,
        })

    @llm_tool(name="astr_kb_estimate_upload_time")
    async def estimate_upload_time(
        self,
        event: AstrMessageEvent,
        file_size_bytes: int,
        file_name: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> str:
        """Estimate vectorization time from file size and type, for upload strategy selection.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // estimation results
                    "file_name": string,
                    "file_size_bytes": number,
                    "estimated_chunks": number,
                    "estimated_seconds": number,
                    "strategy": "empty" | "sync_fast" | "sync" | "async",
                    "strategy_label": string,
                    "polling_interval_seconds": number
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            file_size_bytes(number): File size in bytes.
            file_name(string): File name with extension, used to infer file type.
            chunk_size(number): Chunk size. Default 512.
            chunk_overlap(number): Chunk overlap. Default 50.
        """
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        text_ratio_map = {
            "txt": 1.0, "md": 1.0, "markdown": 1.0, "mkd": 1.0, "mdx": 1.0,
            "rst": 0.9, "adoc": 0.9,
            "pdf": 0.4,
            "docx": 0.25, "epub": 0.25,
            "xls": 0.1, "xlsx": 0.1,
        }
        text_ratio = text_ratio_map.get(ext, 0.3)

        estimated_chars = file_size_bytes * text_ratio
        effective_chunk_size = max(chunk_size - chunk_overlap, 1)
        estimated_chunks = max(1, int(estimated_chars / effective_chunk_size))
        estimated_seconds = estimated_chunks * self._avg_embedding_time

        polling_interval = max(180, min(600, int(estimated_seconds / 10)))

        if estimated_chunks == 0:
            strategy = "empty"
        elif estimated_seconds <= 30:
            strategy = "sync_fast"
        elif estimated_seconds <= 100:
            strategy = "sync"
        else:
            strategy = "async"

        return _json.dumps({
            "s": True,
            "d": {
                "file_name": file_name,
                "ext": ext,
                "file_size_bytes": file_size_bytes,
                "text_ratio": text_ratio,
                "estimated_chars": int(estimated_chars),
                "estimated_chunks": estimated_chunks,
                "avg_embedding_time": self._avg_embedding_time,
                "estimated_seconds": int(estimated_seconds),
                "strategy": strategy,
                "strategy_label": {
                    "empty": "文件为空",
                    "sync_fast": "极快（< 30s）",
                    "sync": "较快（30-100s）",
                    "async": "可能超时（> 100s）",
                }.get(strategy, ""),
                "polling_interval_seconds": polling_interval,
            },
            "e": None,
        })

    @staticmethod
    def _format_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        elif n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        elif n < 1024 * 1024 * 1024:
            return f"{n / 1024 / 1024:.1f} MB"
        return f"{n / 1024 / 1024 / 1024:.1f} GB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m{s}s"
        else:
            h, r = divmod(int(seconds), 3600)
            m, _ = divmod(r, 60)
            return f"{h}h{m}m"

    async def _has_active_upload_lock(self) -> bool:
        """Check the database for an active upload-check cron job (distributed lock)."""
        try:
            cron_mgr = getattr(self.context, "cron_manager", None)
            if cron_mgr is None:
                return False
            jobs = await cron_mgr.db.list_cron_jobs("active_agent")
            for job in jobs or []:
                if job.name and job.name.startswith("upload_check_") and job.enabled:
                    return True
        except Exception:
            pass
        return False

    async def _read_sandbox_file(
        self, event: AstrMessageEvent, sandbox_path: str
    ) -> bytes | None:
        """Read a file from the sandbox as raw bytes.

        ``download_file`` can only access files under ``/workspace/`` (the sandbox
        workspace root), while ``python.exec`` runs inside the container with full
        filesystem access.  To work around the ``download_file`` Unicode path
        limitation, the file is first copied to an ASCII-only name under
        ``/workspace/`` via Python, then downloaded from that ASCII path.

        Both the sandbox temp file and the local temp file are cleaned up before return.

        Args:
            event: The message event (provides unified_msg_origin).
            sandbox_path: Path inside the sandbox (may contain Unicode).

        Returns:
            Raw file bytes, or None if reading failed.
        """
        import os
        import uuid
        from astrbot.core.computer.computer_client import get_booter
        from astrbot.core.utils.astrbot_path import get_astrbot_temp_path

        sb = await get_booter(self.context, event.unified_msg_origin)

        # download_file only supports ASCII paths and is restricted to /workspace/;
        # copy the file to an ASCII temp name under /workspace/ first.
        ascii_key = uuid.uuid4().hex
        ascii_name = f"sandbox_{ascii_key}.tmp"
        copy_code = (
            "import shutil\n"
            f"shutil.copy2({sandbox_path!r}, '/workspace/{ascii_name}')\n"
        )
        py_result = await sb.python.exec(copy_code, timeout=30)
        if not py_result.get("success", True):
            logger.error(
                "Failed to copy sandbox file to ASCII name: "
                f"{py_result.get('error', 'unknown')}"
            )
            return None

        local_path: str | None = None
        try:
            local_path = os.path.join(
                get_astrbot_temp_path(),
                ascii_name,
            )
            await sb.download_file(ascii_name, local_path)
            with open(local_path, "rb") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read sandbox file {sandbox_path}: {e}")
            return None
        finally:
            if local_path and os.path.exists(local_path):
                os.unlink(local_path)
            try:
                await sb.python.exec(
                    f"import os; os.unlink('/workspace/{ascii_name}')",
                    timeout=10,
                )
            except Exception:
                pass

    @llm_tool(name="astr_kb_create")
    async def create_knowledge_base(
        self,
        event: AstrMessageEvent,
        kb_name: str,
        description: str = "",
        embedding_provider: str = "",
        rerank_provider: str = "",
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> str:
        """Create a new knowledge base.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // created kb
                    "kb_id": string,
                    "kb_name": string,
                    "embedding_provider": string | null,
                    "rerank_provider": string | null,
                    "chunk_size": number,
                    "chunk_overlap": number
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            kb_name(string): Knowledge base name.
            description(string): Knowledge base description.
            embedding_provider(string): Embedding provider ID or name keyword.
                Leave empty to auto-select the first available.
            rerank_provider(string): Rerank provider ID or name keyword.
                Leave empty to disable reranking.
            chunk_size(number): Chunk size in characters. Default 512.
            chunk_overlap(number): Chunk overlap in characters. Default 50.

        Note:
            If auto_whitelist_created is enabled, the new KB ID is automatically
            added to the whitelist and persisted.
        """
        embedding_providers = self.context.get_all_embedding_providers()
        if not embedding_providers:
            return _json.dumps({"s": False, "d": None, "e": "没有可用的 Embedding 模型提供商。"})

        emb_id = self._match_provider(embedding_providers, embedding_provider, "Embedding")
        if not emb_id:
            return _json.dumps({"s": False, "d": None, "e": f"未找到匹配的 Embedding 提供商: {embedding_provider}"})

        rerank_id = None
        if rerank_provider.strip():
            rerank_providers = getattr(self.context.provider_manager, "rerank_provider_insts", [])
            if not rerank_providers:
                return _json.dumps({"s": False, "d": None, "e": "未配置 Rerank 模型提供商。"})
            rerank_id = self._match_provider(rerank_providers, rerank_provider, "Rerank")
            if not rerank_id:
                return _json.dumps({"s": False, "d": None, "e": f"未找到匹配的 Rerank 提供商: {rerank_provider}"})

        try:
            kb_helper = await self.context.kb_manager.create_kb(
                kb_name=kb_name,
                description=description.strip() or None,
                embedding_provider_id=emb_id,
                rerank_provider_id=rerank_id,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": f"创建失败: {e!s}"})

        kb = kb_helper.kb

        if self.access_control.auto_whitelist_created:
            self.access_control.add_to_whitelist(kb.kb_id)
            self._persist_config()

        return _json.dumps({
            "s": True,
            "d": {
                "kb_id": kb.kb_id,
                "kb_name": kb.kb_name,
                "embedding_provider": emb_id,
                "rerank_provider": rerank_id,
                "chunk_size": kb.chunk_size,
                "chunk_overlap": kb.chunk_overlap,
            },
            "e": None,
        })

    # ── Provider fuzzy matching helper ─────────────────────────

    @staticmethod
    def _match_provider(
        providers: list, query: str, label: str,
    ) -> str | None:
        """Fuzzy-match a provider ID by name keyword or exact ID.

        Args:
            providers: List of provider instances (must have meta() returning an object with .id).
            query: User-provided search keyword or full ID. Empty string returns the first available.
            label: Provider type name for logging.

        Returns:
            Matched provider_id, or None.
        """
        if not providers:
            return None
        q = query.strip()
        if not q:
            return providers[0].meta().id

        q_lower = q.lower()

        for p in providers:
            pid = p.meta().id.lower()
            if pid == q_lower:
                return p.meta().id
            if q_lower in pid:
                return p.meta().id
            try:
                pname = (p.meta().model or "").lower()
                if q_lower in pname:
                    return p.meta().id
            except Exception:
                pass

        return None

    @llm_tool(name="astr_kb_delete")
    async def delete_knowledge_base(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        confirm: bool = False,
    ) -> str:
        """Delete a knowledge base and all its documents and vector data.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // deleted
                    "kb_id": string,
                    "kb_name": string,
                    "removed_from_whitelist": boolean
                },
                "e": null
            } | {
                "s": true,
                "d": { // confirmation required
                    "confirm_required": true,
                    "kb_id": string
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            kb_id(string): Knowledge base ID to delete.
            confirm(boolean): Whether to confirm the deletion. Default false.

        Note:
            Automatically cleans up whitelist/blacklist entries and persists config.
        """
        if not confirm:
            return _json.dumps({"s": True, "d": {"confirm_required": True, "kb_id": kb_id}, "e": None})

        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return _json.dumps({"s": False, "d": None, "e": f"权限不足: {e}"})

        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        kb_name = kb_helper.kb.kb_name if kb_helper else kb_id

        try:
            success = await self.context.kb_manager.delete_kb(kb_id)
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": f"删除失败: {e!s}"})

        if not success:
            return _json.dumps({"s": False, "d": None, "e": "知识库不存在或未加载。"})

        removed_wl = kb_id in self.access_control.whitelist
        removed_bl = kb_id in self.access_control.blacklist
        self.access_control.whitelist.discard(kb_id)
        self.access_control.blacklist.discard(kb_id)
        if removed_wl or removed_bl:
            self._persist_config()

        return _json.dumps({
            "s": True,
            "d": {"kb_id": kb_id, "kb_name": kb_name, "removed_from_whitelist": removed_wl or removed_bl},
            "e": None,
        })

    @llm_tool(name="astr_kb_delete_document")
    async def delete_document(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        doc_id: str = "",
        file_name: str = "",
        confirm: bool = False,
    ) -> str:
        """Delete a document from a knowledge base.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // deleted
                    "doc_id": string,
                    "file_name": string
                },
                "e": null
            } | {
                "s": true,
                "d": { // confirmation required
                    "confirm_required": true,
                    "doc_id": string,
                    "file_name": string
                },
                "e": null
            } | {
                "s": true,
                "d": { // multiple matches
                    "multiple_matches": true,
                    "matches": { "doc_id": string, "file_name": string }[]
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            kb_id(string): Knowledge base ID.
            doc_id(string): Document ID (either doc_id or file_name is required).
            file_name(string): File name for fuzzy matching (fallback when doc_id is empty).
            confirm(boolean): Whether to confirm the deletion. Default false.
        """
        if not doc_id and not file_name:
            return _json.dumps({"s": False, "d": None, "e": "请提供 doc_id 或 file_name。"})

        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return _json.dumps({"s": False, "d": None, "e": f"权限不足: {e}"})

        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return _json.dumps({"s": False, "d": None, "e": f"知识库 {kb_id} 不存在。"})

        target_doc = None
        if doc_id:
            target_doc = await kb_helper.get_document(doc_id)
            if not target_doc:
                return _json.dumps({"s": False, "d": None, "e": f"未找到文档: doc_id={doc_id}"})
        elif file_name:
            docs = await kb_helper.list_documents(limit=500)
            matches = [d for d in docs if file_name.lower() in d.doc_name.lower()]
            if not matches:
                return _json.dumps({"s": False, "d": None, "e": f"未找到文件名包含 '{file_name}' 的文档。"})
            if len(matches) > 1:
                return _json.dumps({
                    "s": True,
                    "d": {
                        "multiple_matches": True,
                        "matches": [{"doc_id": d.doc_id, "file_name": d.doc_name} for d in matches],
                    },
                    "e": None,
                })
            target_doc = matches[0]

        if not confirm:
            return _json.dumps({
                "s": True,
                "d": {"confirm_required": True, "doc_id": target_doc.doc_id, "file_name": target_doc.doc_name},
                "e": None,
            })

        try:
            await kb_helper.delete_document(target_doc.doc_id)
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": f"删除失败: {e!s}"})

        return _json.dumps({
            "s": True,
            "d": {"doc_id": target_doc.doc_id, "file_name": target_doc.doc_name},
            "e": None,
        })

    @llm_tool(name="astr_kb_search_ext")
    async def search_knowledge_base(
        self,
        event: AstrMessageEvent,
        query: str,
    ) -> str:
        """Search knowledge bases allowed by the plugin's access control.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // search results
                    "results": string | null, // context text or null if no results
                    "kb_count": number
                },
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            query(string): Search keyword or question.
        """
        if not query.strip():
            return _json.dumps({"s": False, "d": None, "e": "请输入搜索关键词。"})

        all_kbs = await self.context.kb_manager.list_kbs()
        allowed_kbs = self.access_control.filter_kb_list(all_kbs)

        if not allowed_kbs:
            return _json.dumps({"s": True, "d": {"results": None, "kb_count": 0}, "e": None})

        kb_names = [kb.kb_name for kb in allowed_kbs]

        try:
            result = await self.context.kb_manager.retrieve(
                query=query.strip(),
                kb_names=kb_names,
                top_k_fusion=20,
                top_m_final=5,
            )
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": f"搜索失败: {e!s}"})

        if not result or not result.get("context_text"):
            return _json.dumps({"s": True, "d": {"results": None, "kb_count": len(kb_names)}, "e": None})

        return _json.dumps({"s": True, "d": {"results": result["context_text"], "kb_count": len(kb_names)}, "e": None})

    @llm_tool(name="astr_kb_list_documents")
    async def list_documents_in_kb(
        self,
        event: AstrMessageEvent,
        kb_id: str,
    ) -> str:
        """List all documents in a knowledge base.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "d": { // list of documents
                    "doc_id": string,
                    "file_name": string,
                    "file_type": string,
                    "file_size": number,
                    "chunk_count": number
                }[],
                "e": null
            } | {
                "s": false,
                "d": null,
                "e": string
            }
            ```

        Args:
            kb_id(string): Knowledge base ID (obtained from astr_kb_list).
        """
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return _json.dumps({"s": False, "d": None, "e": f"权限不足: {e}"})

        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return _json.dumps({"s": False, "d": None, "e": f"知识库 {kb_id} 不存在。"})

        try:
            docs = await kb_helper.list_documents(limit=500)
        except Exception as e:
            return _json.dumps({"s": False, "d": None, "e": f"查询失败: {e!s}"})

        data = [
            {
                "doc_id": doc.doc_id,
                "file_name": doc.doc_name,
                "file_type": doc.file_type,
                "file_size": doc.file_size,
                "chunk_count": doc.chunk_count,
            }
            for doc in (docs or [])
        ]
        return _json.dumps({"s": True, "d": data, "e": None})

    @llm_tool(name="astr_kb_get_document_content_chunk")
    async def get_document_content_chunk(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        doc_id: str,
        chunk_index: int = 0,
    ) -> str:
        """Get one text chunk from a document by its index. Single chunk per call, no truncation.

        Return schema (JSON):
            ```typescript
            type Return = {
                "s": true, // is success
                "c": string, // chunk text content
                "e": null
            } | {
                "s": false, // error
                "c": null,
                "e": string // error message
            }
            ```

        Args:
            kb_id(string): Knowledge base ID.
            doc_id(string): Document ID (obtained from astr_kb_list_documents).
            chunk_index(number): Zero-based chunk index. Default 0.
        """
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return _json.dumps({"s": False, "c": None, "e": f"权限不足: {e}"})

        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return _json.dumps({"s": False, "c": None, "e": f"知识库 {kb_id} 不存在。"})

        try:
            doc = await kb_helper.get_document(doc_id)
        except Exception as e:
            return _json.dumps({"s": False, "c": None, "e": f"查询文档失败: {e}"})

        if not doc:
            return _json.dumps({"s": False, "c": None, "e": f"未找到文档: doc_id={doc_id}"})

        try:
            chunks = await kb_helper.get_chunks_by_doc_id(doc_id, limit=9999)
        except Exception as e:
            return _json.dumps({"s": False, "c": None, "e": f"读取文档失败: {e}"})

        if not chunks:
            return _json.dumps({"s": False, "c": None, "e": "该文档没有文本分块。"})

        chunks.sort(key=lambda c: c["chunk_index"])

        if chunk_index < 0 or chunk_index >= len(chunks):
            return _json.dumps({
                "s": False, "c": None,
                "e": f"chunk_index {chunk_index} 越界，有效范围 0-{len(chunks) - 1}",
            })

        return _json.dumps({"s": True, "c": chunks[chunk_index]["content"], "e": None})

    def _persist_config(self) -> None:
        """Persist the current access control configuration to a JSON file."""
        import json as pyjson
        import os

        try:
            from astrbot.core.utils.astrbot_path import get_astrbot_config_path
            config_path = os.path.join(
                get_astrbot_config_path(),
                "astrbot_kb_ext_access_config.json",
            )
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8-sig") as f:
                    disk_config = pyjson.load(f)
            else:
                disk_config = {}
            disk_config.setdefault("kb_access_control", {})
            disk_config["kb_access_control"]["mode"] = self.access_control.mode
            disk_config["kb_access_control"]["whitelist"] = sorted(
                self.access_control.whitelist
            )
            disk_config["kb_access_control"]["blacklist"] = sorted(
                self.access_control.blacklist
            )
            with open(config_path, "w", encoding="utf-8") as f:
                pyjson.dump(disk_config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("astrbot_kb_ext_access: failed to persist config — %s", e)
