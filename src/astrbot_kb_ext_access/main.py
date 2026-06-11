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

"""AstrBot KB External Access Plugin — main entry point.

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
from .kb_uploader import KnowledgeBaseUploader

import datetime
import json as _json
import uuid


class AstrBotKnowledgeBaseExtAccess(star.Star):
    """为 AstrBot Agent 提供知识库搜索、文件上传与知识库创建能力。

    Provides Agent-facing LLM tools for listing, uploading to, and creating knowledge bases.
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
        """初始化插件：校验配置，注册插件页面 API。

        Validate access control config and register plugin page web APIs.
        """
        try:
            self.access_control.validate_config()
        except ValueError as e:
            logger.error("astrbot_kb_ext_access: invalid config — %s", e)

        # 从配置 JSON 文件读取已保存的 ID（插件页面写入的是纯 ID）
        self._load_config_from_file()

        logger.info(
            "astrbot_kb_ext_access: mode=%s, whitelist=%s, blacklist=%s",
            self.access_control.mode,
            sorted(self.access_control.whitelist),
            sorted(self.access_control.blacklist),
        )

        # 注册插件页面 API —— 路由需以插件名开头，桥接 SDK 发送的请求路径
        # 为 /api/plug/<plugin_name>/<endpoint>，_match_registered_web_api
        # 将 <plugin_name>/<endpoint> 整体与已注册路由匹配。
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

    # ── Plugin page web APIs ──────────────────────────────────────

    async def _api_kb_list(self):
        """返回所有知识库列表供插件页面渲染。"""
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
        """返回当前访问控制配置。"""
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
        """保存访问控制配置（纯 kb_id，不做名称解析）。"""
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

            # 更新内存中的访问控制
            self.access_control.mode = mode
            self.access_control.whitelist = set(whitelist)
            self.access_control.blacklist = set(blacklist)

            # 持久化到插件配置 JSON 文件
            self._persist_config()

            return jsonify({"status": "ok", "data": {"message": "saved"}})

        except Exception as e:
            logger.error("astrbot_kb_ext_access: save config failed — %s", e)
            return jsonify({"status": "error", "message": str(e)}), 500

    def _load_config_from_file(self) -> None:
        """从插件配置 JSON 文件加载 kb_id（插件页面写入的是纯 ID）。"""
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

    # ── Tool 1: List knowledge bases ──────────────────────────────

    @llm_tool(name="astr_kb_list")
    async def list_knowledge_bases(
        self,
        event: AstrMessageEvent,
        query: str = "",
    ) -> str:
        """获取 AstrBot 后台所有可用知识库的列表。

        List all available knowledge bases in AstrBot.

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
            query(string): 可选，用于过滤知识库名称的关键词
        """
        # 获取所有知识库
        kbs = await self.context.kb_manager.list_kbs()

        # 应用白名单/黑名单过滤
        kbs = self.access_control.filter_kb_list(kbs)

        # 可选关键词过滤
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

    # ── Tool 2: Upload file to knowledge base ─────────────────────

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
        """向指定的 AstrBot 知识库上传文件。

        Upload file content to a specified knowledge base.

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
            kb_id(string): 目标知识库ID
            file_name(string): 文件名（含扩展名）
            file_content(string): 文本内容或 base64 编码的原始数据（sandbox_path 为空时使用）
            binary(bool): file_content 是否为 base64 编码（仅 file_content 模式有效）
            sandbox_path(string): 沙箱中的文件路径（优先使用，无需 base64 转码）
            chunk_size(number): 分块大小（字符数），默认 512
            chunk_overlap(number): 分块重叠（字符数），默认 50
            timeout(number): 单次同步尝试的超时秒数，默认 100。
                如果同步上传超时，说明该文件不适合同步模式。
                ⚠️ 不要增大 timeout——超时说明文件太大，即使加到 120s 也可能失败。
                正确做法: 改用 wait_completion=false 异步上传 + future_task 轮询。
            max_retries(number): 失败重试次数，默认 3。设为 0 不重试。
            wait_completion(bool): 是否等待向量化完成。默认 True。
                设为 False 进入异步模式: 文件提交到后台处理后立即返回，
                不等待向量化。适用于同步上传超时的文件。
                提交后必须使用 future_task 安排轮询检查，不得主动轮询。
                ⚠️ 并发限制: 同一时间只允许一个 wait_completion=false 上传。
                若有其他异步上传进行中，工具会拒绝。
        """
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return _json.dumps({"s": False, "d": None, "e": f"权限不足: {e}"})

        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return _json.dumps({"s": False, "d": None, "e": f"知识库 {kb_id} 不存在。"})

        if not wait_completion:
            # 数据库级分布式锁：检查是否有活跃的上传检查 cron job
            if await self._has_active_upload_lock():
                return _json.dumps({"s": False, "d": None, "e": "已有异步上传进行中（存在活跃的 upload_check cron job）"})
            upload_task_id = str(uuid.uuid4())
            self._async_pending[upload_task_id] = {"pending": True, "file_name": file_name, "kb_id": kb_id}
        else:
            upload_task_id = None

        async def _on_async_done(done_uid: str) -> None:
            pass  # 锁由 cron job 管理，上传完成无需释放

        uploader = KnowledgeBaseUploader(
            kb_helper,
            pending_store=self._async_pending,
            on_async_complete=_on_async_done,
        )

        if sandbox_path:
            try:
                from astrbot.core.computer.computer_client import get_booter
                import base64
                sb = await get_booter(self.context, event.unified_msg_origin)
                py_code = (
                    "import base64\n"
                    f"with open({sandbox_path!r}, 'rb') as f:\n"
                    "    print(base64.b64encode(f.read()).decode())\n"
                )
                py_result = await sb.python.exec(py_code, timeout=60)
                if not py_result.get("success", True):
                    return _json.dumps({"s": False, "d": None, "e": f"沙箱读取文件失败: {py_result.get('error', 'unknown')}"})
                b64_data = (py_result.get("output", "") or "").strip()
                if not b64_data:
                    return _json.dumps({"s": False, "d": None, "e": "沙箱返回空数据"})
                raw_bytes = base64.b64decode(b64_data)
            except Exception as e:
                return _json.dumps({"s": False, "d": None, "e": f"无法从沙箱读取文件: {e!s}"})
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

        if result.get("pending"):
            return _json.dumps({"s": True, "d": {"pending": True, "upload_task_id": upload_task_id, "file_name": file_name, "kb_id": kb_id}, "e": None})
        if result.get("success"):
            return _json.dumps({"s": True, "d": {"result_text": result["result"]}, "e": None})
        return _json.dumps({"s": False, "d": None, "e": result.get("result", "上传失败")})

    # ── Tool 3b: Batch upload files ───────────────────────────────

    @llm_tool(name="astr_kb_upload_batch")
    async def upload_to_knowledge_base_batch(
        self,
        event: AstrMessageEvent,
        files: list,
    ) -> str:
        """批量上传多个文件到知识库，逐个上传，阻断等待。

        Batch upload multiple files to a knowledge base.

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
            files(list): 上传任务列表，每项为 dict:
                - kb_id(string): 必填
                - file_name(string): 必填
                - file_content(string): 可选
                - binary(bool): 可选
                - sandbox_path(string): 可选
                - chunk_size(number): 可选
                - chunk_overlap(number): 可选
                - timeout(number): 可选，默认 100
                - max_retries(number): 可选，默认 3
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
                    from astrbot.core.computer.computer_client import get_booter
                    import base64 as b64
                    sb = await get_booter(self.context, event.unified_msg_origin)
                    py_code = (
                        "import base64\n"
                        f"with open({sandbox_path!r}, 'rb') as f:\n"
                        "    print(base64.b64encode(f.read()).decode())\n"
                    )
                    py_result = await sb.python.exec(py_code, timeout=60)
                    if not py_result.get("success", True):
                        item_results.append({"i": i, "file_name": file_name, "ok": False, "e": "沙箱读取失败"})
                        fail_count += 1
                        continue
                    raw = b64.b64decode((py_result.get("output", "") or "").strip())
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

            if r.get("success"):
                success_count += 1
                item_results.append({"i": i, "file_name": file_name, "ok": True, "e": None})
            else:
                fail_count += 1
                item_results.append({"i": i, "file_name": file_name, "ok": False, "e": r.get("result", "上传失败")})

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

    # ── Tool 3c: Check pending upload status ──────────────────────

    @llm_tool(name="astr_kb_check_upload")
    async def check_upload_status(
        self,
        event: AstrMessageEvent,
        upload_task_id: str = "",
        file_name: str = "",
        kb_id: str = "",
    ) -> str:
        """查询后台上传任务的完成状态。

        Check if a background upload has finished vectorization.
        优先使用 upload_task_id（UUID）查询，其次用 file_name + kb_id 回退。

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
            upload_task_id(string): 上传任务 UUID（从 astr_kb_upload 返回，推荐）
            file_name(string): 文件名（当 upload_task_id 为空时的回退）
            kb_id(string): 知识库 ID（当 upload_task_id 为空时的回退）
        """
        # 优先用 upload_task_id 查 pending_store
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

            # 缓存中没有但 cron job 存在 → 仍在处理中（可能跨实例）
            if await self._has_active_upload_lock():
                return _json.dumps({"s": True, "d": {"status": "processing", "stage": "unknown", "current": 0, "total": 0}, "e": None})

        # 回退：用 file_name + kb_id 查知识库
        if file_name and kb_id:
            try:
                self.access_control.check_kb_access(kb_id)
            except PermissionError:
                pass  # 仅查询，不阻止

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

    # ── Tool 3d: Schedule FutureTask check (server-side time) ────

    @llm_tool(name="astr_kb_schedule_check")
    async def schedule_upload_check(
        self,
        event: AstrMessageEvent,
        upload_task_id: str,
        interval_seconds: int,
        note_text: str = "",
    ) -> str:
        """安排一个按固定间隔重复激活的 FutureTask 来检查上传状态。

        Schedule a RECURRING FutureTask to check upload status.
        Payload 中包含 upload_task_id，即使插件重启也能通过 cron DB 恢复。

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
            upload_task_id(string): 上传任务 UUID（从 astr_kb_upload 返回）
            interval_seconds(number): 轮询间隔（秒），最小 180（3分钟）
            note_text(string): 被唤醒时的指令。默认自动生成。
        """
        cron_mgr = getattr(self.context, "cron_manager", None)
        if cron_mgr is None:
            return _json.dumps({"s": False, "d": None, "e": "cron_manager 不可用，请启用主动型能力。"})

        interval = max(180, int(interval_seconds))

        # 从 _async_pending 获取 file_name 和 kb_id
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
            f"- 轮询间隔: {self._format_duration(interval)}\n"
            f"- 预计首次触发: {first_run.isoformat()}\n"
            f"- 删除指令: 上传完成后，调用 future_task(action=\"delete\", job_id=\"{job.job_id}\")"
            f" 停止此重复任务，然后继续处理下一个文件。\n"
            f"⏰ AstrBot 将每 {self._format_duration(interval)} 自动唤醒并检查。"
        )

    # ── Tool 3e: Estimate upload time ─────────────────────────────

    @llm_tool(name="astr_kb_estimate_upload_time")
    async def estimate_upload_time(
        self,
        event: AstrMessageEvent,
        file_size_bytes: int,
        file_name: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> str:
        """根据文件大小和类型预估向量化耗时，用于决定上传策略（同步/异步/批量）。

        Estimate vectorization time from file size and type.

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
            file_size_bytes(number): 文件大小（字节），可用 ls -l 或 stat 获得
            file_name(string): 文件名（含扩展名），用于推断文件类型
            chunk_size(number): 分块大小，默认 512
            chunk_overlap(number): 分块重叠，默认 50
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
        """查询数据库，检查是否存在活跃的上传检查 cron job（分布式锁）。"""
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

    # ── Tool 4: Create knowledge base ─────────────────────────────

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
        """创建一个新的知识库。

        Create a new knowledge base.

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
            kb_name(string): 知识库名称
            description(string): 知识库描述
            embedding_provider(string): Embedding 模型提供商 ID 或名称关键词。留空自动选择第一个可用。
            rerank_provider(string): Rerank 模型提供商 ID 或名称关键词。留空不启用。
            chunk_size(number): 分块大小（字符数），默认 512
            chunk_overlap(number): 分块重叠（字符数），默认 50
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
        """模糊匹配提供商 ID。

        Args:
            providers: 提供商实例列表（需有 meta() 方法返回带 .id 的对象）。
            query: 用户输入的搜索关键词或完整 ID。空字符串时返回第一个可用 ID。
            label: 提供商类型名称（用于日志）。

        Returns:
            匹配到的完整 provider_id，或 None。
        """
        if not providers:
            return None
        q = query.strip()
        if not q:
            # 未指定，使用第一个可用
            return providers[0].meta().id

        q_lower = q.lower()

        for p in providers:
            pid = p.meta().id.lower()
            # 精确匹配
            if pid == q_lower:
                return p.meta().id
            # 包含匹配
            if q_lower in pid:
                return p.meta().id
            # 名称模糊匹配（meta().model 或类似字段）
            try:
                pname = (p.meta().model or "").lower()
                if q_lower in pname:
                    return p.meta().id
            except Exception:
                pass

        return None

    # ── Tool 4: Delete knowledge base ─────────────────────────────

    @llm_tool(name="astr_kb_delete")
    async def delete_knowledge_base(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        confirm: bool = False,
    ) -> str:
        """删除指定的知识库及其所有文档和向量数据。

        Delete a knowledge base and all its documents and vector data.

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
            kb_id(string): 要删除的知识库ID
            confirm(bool): 是否确认执行删除。默认为 false，设为 true 时执行。
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

    # ── Tool 5: Delete document from knowledge base ───────────────

    @llm_tool(name="astr_kb_delete_document")
    async def delete_document(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        doc_id: str = "",
        file_name: str = "",
        confirm: bool = False,
    ) -> str:
        """删除指定知识库中的某个文档及其向量数据。

        Delete a document from a knowledge base.

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
            kb_id(string): 知识库ID
            doc_id(string): 文档ID（与 file_name 二选一）
            file_name(string): 文件名（与 doc_id 二选一，用于模糊匹配）
            confirm(bool): 是否确认执行删除。默认为 false。
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

    # ── Tool 6: Search knowledge bases (access-controlled) ────────

    @llm_tool(name="astr_kb_search_ext")
    async def search_knowledge_base(
        self,
        event: AstrMessageEvent,
        query: str,
    ) -> str:
        """在插件白名单/黑名单允许的知识库中搜索相关内容。

        Search knowledge bases allowed by the plugin's access control.

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
            query(string): 搜索关键词或问题
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

    # ── Tool 7: List documents in a knowledge base ────────────────

    @llm_tool(name="astr_kb_list_documents")
    async def list_documents_in_kb(
        self,
        event: AstrMessageEvent,
        kb_id: str,
    ) -> str:
        """列出指定知识库中的所有文档。

        List all documents in a knowledge base.

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
            kb_id(string): 知识库 ID（从 astr_kb_list 获得）
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

    # ── Tool 8: Get a single chunk from a document ────────────────

    @llm_tool(name="astr_kb_get_document_content_chunk")
    async def get_document_content_chunk(
        self,
        event: AstrMessageEvent,
        kb_id: str,
        doc_id: str,
        chunk_index: int = 0,
    ) -> str:
        """获取知识库中指定文档的指定文本分块。

        Get one text chunk from a document by its index.
        一次只返回一个分块，无截断限制。

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
            kb_id(string): 知识库 ID
            doc_id(string): 文档 ID（从 astr_kb_list_documents 获得）
            chunk_index(number): 分块序号（从 0 开始），默认 0
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

    # ── Config persistence helper ─────────────────────────────────

    def _persist_config(self) -> None:
        """将当前访问控制配置持久化到 JSON 文件。"""
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
