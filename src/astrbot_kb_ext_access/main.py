"""AstrBot KB External Access Plugin — main entry point.

Provides five Agent-facing LLM tools:
  - astr_kb_list           : List available knowledge bases
  - astr_kb_upload         : Upload a file to a knowledge base
  - astr_kb_create         : Create a new knowledge base
  - astr_kb_delete         : Delete a knowledge base
  - astr_kb_delete_document: Delete a document from a knowledge base

All tools bypass HTTP and directly call kb_manager Python APIs within
the AstrBot process. Access is controlled by KbAccessControl
(whitelist/blacklist).
"""

from astrbot.api import logger
from astrbot.api import star, llm_tool
from astrbot.api.event import AstrMessageEvent

from .access_control import KbAccessControl
from .kb_uploader import KnowledgeBaseUploader


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
        # config is an AstrBotConfig dict-like object from _conf_schema.json
        self.access_control = KbAccessControl(dict(config) if config else {})

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

        if not kbs:
            return "当前没有可用的知识库。"

        lines = [f"可用知识库列表（共 {len(kbs)} 个）："]
        for kb in kbs:
            desc = (kb.description or "").strip() or "(无描述)"
            lines.append(
                f'- kb_id: "{kb.kb_id}" | name: "{kb.kb_name}" | '
                f"文档: {kb.doc_count} | 切片: {kb.chunk_count} | {desc}"
            )
        return "\n".join(lines)

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
    ) -> str:
        """向指定的 AstrBot 知识库上传文件。

        Upload file content to a specified knowledge base.
        优先使用 sandbox_path 直接传输二进制文件，其次使用 file_content。

        Args:
            kb_id(string): 目标知识库ID
            file_name(string): 文件名（含扩展名）
            file_content(string): 文本内容或 base64 编码的原始数据（sandbox_path 为空时使用）
            binary(bool): file_content 是否为 base64 编码（仅 file_content 模式有效）
            sandbox_path(string): 沙箱中的文件路径（优先使用，无需 base64 转码）
            chunk_size(number): 分块大小（字符数），默认 512
            chunk_overlap(number): 分块重叠（字符数），默认 50
        """
        # 权限检查：白名单/黑名单（ID 已在 initialize() 中解析完成）
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return f"❌ 权限不足: {e}"

        # 获取知识库
        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return (
                f"❌ 上传失败\n"
                f"- 错误: 知识库 {kb_id} 不存在或未加载。\n"
                f"请先调用 astr_kb_list 确认可用的知识库 ID。"
            )

        # 执行上传
        uploader = KnowledgeBaseUploader(kb_helper)

        if sandbox_path:
            # 通过沙箱 Python 执行读取二进制文件并 base64 编码，避免 LLM 中转
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
                    err = py_result.get("error", "unknown error")
                    return f"❌ 上传失败\n- 错误: 沙箱读取文件失败 — {err}"
                b64_data = (py_result.get("output", "") or "").strip()
                if not b64_data:
                    return "❌ 上传失败\n- 错误: 沙箱返回空数据"
                raw_bytes = base64.b64decode(b64_data)
            except Exception as e:
                return f"❌ 上传失败\n- 错误: 无法从沙箱读取文件 — {e!s}"
            result = await uploader.upload_bytes(
                file_name=file_name,
                raw_bytes=raw_bytes,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        else:
            result = await uploader.upload(
                file_name=file_name,
                file_content=file_content,
                binary=binary,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        return result["result"]

    # ── Tool 3: Create knowledge base ─────────────────────────────

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

        Create a new knowledge base with the specified parameters.

        Args:
            kb_name(string): 知识库名称
            description(string): 知识库描述
            embedding_provider(string): Embedding 模型提供商 ID 或名称关键词。留空自动选择第一个可用。
            rerank_provider(string): Rerank 模型提供商 ID 或名称关键词。留空不启用。
            chunk_size(number): 分块大小（字符数），默认 512
            chunk_overlap(number): 分块重叠（字符数），默认 50
        """
        # ── 解析 embedding provider ─────────────────────────────
        embedding_providers = self.context.get_all_embedding_providers()
        if not embedding_providers:
            return (
                "❌ 创建失败\n"
                "- 错误: 没有可用的 Embedding 模型提供商。\n"
                "请先在 Dashboard 中配置 Embedding 模型。"
            )

        emb_id = self._match_provider(
            embedding_providers, embedding_provider,
            "Embedding",
        )
        if not emb_id:
            candidates = "\n".join(
                f"  - {p.meta().id}" for p in embedding_providers
            )
            return (
                "⚠️ 未找到匹配的 Embedding 提供商。\n"
                f"可用的 Embedding 提供商:\n{candidates}\n"
                "请提供上述列表中的完整 ID。"
            )

        # ── 解析 rerank provider（可选）─────────────────────────
        rerank_id = None
        if rerank_provider.strip():
            rerank_providers = getattr(
                self.context.provider_manager, "rerank_provider_insts", []
            )
            if not rerank_providers:
                return (
                    "❌ 创建失败\n"
                    "- 错误: 未配置 Rerank 模型提供商，但指定了 rerank_provider。\n"
                    "请先在 Dashboard 中配置 Rerank 模型，或留空 rerank_provider。"
                )
            rerank_id = self._match_provider(
                rerank_providers, rerank_provider, "Rerank",
            )
            if not rerank_id:
                candidates = "\n".join(
                    f"  - {p.meta().id}" for p in rerank_providers
                )
                return (
                    "⚠️ 未找到匹配的 Rerank 提供商。\n"
                    f"可用的 Rerank 提供商:\n{candidates}\n"
                    "请提供上述列表中的完整 ID。"
                )

        # ── 创建知识库 ──────────────────────────────────────────
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
            return (
                f"❌ 创建失败\n"
                f"- 知识库名称: {kb_name}\n"
                f"- 错误: {e!s}"
            )

        kb = kb_helper.kb

        # 自动加入白名单
        if self.access_control.auto_whitelist_created:
            self.access_control.add_to_whitelist(kb.kb_id)
            self._persist_config()

        parts = [f"✅ 知识库创建成功"]
        parts.append(f"- 名称: {kb.kb_name}")
        parts.append(f"- ID: {kb.kb_id}")
        parts.append(f"- Embedding: {emb_id}")
        if rerank_id:
            parts.append(f"- Rerank: {rerank_id}")
        parts.append(f"- 分块大小: {kb.chunk_size}")
        parts.append(f"- 分块重叠: {kb.chunk_overlap}")
        return "\n".join(parts)

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

        注意：此操作不可撤销！除非用户明确要求跳过确认，否则必须要求用户确认后再执行。

        Args:
            kb_id(string): 要删除的知识库ID
            confirm(bool): 是否确认执行删除。默认为 false，设为 true 时执行。
        """
        # 确认检查
        if not confirm:
            return (
                "⚠️ 确认请求\n"
                f"- 操作: 删除知识库\n"
                f"- ID: {kb_id}\n"
                f"- 警告: 此操作将永久删除该知识库及其所有文档和向量数据，不可撤销。\n"
                f"请回复确认，或再次调用时将 confirm 设为 true。"
            )

        # 权限检查
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return f"❌ 权限不足: {e}"

        # 获取知识库信息（用于返回提示）
        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        kb_name = kb_helper.kb.kb_name if kb_helper else kb_id

        # 执行删除
        try:
            success = await self.context.kb_manager.delete_kb(kb_id)
        except Exception as e:
            return f"❌ 删除失败\n- 知识库: {kb_name}\n- 错误: {e!s}"

        if not success:
            return f"❌ 删除失败\n- 知识库: {kb_name}\n- 原因: 知识库不存在或未加载。"

        # 清理白名单/黑名单中的孤儿条目
        removed_wl = kb_id in self.access_control.whitelist
        removed_bl = kb_id in self.access_control.blacklist
        self.access_control.whitelist.discard(kb_id)
        self.access_control.blacklist.discard(kb_id)
        if removed_wl or removed_bl:
            self._persist_config()

        return (
            f"✅ 知识库已删除\n"
            f"- 名称: {kb_name}\n"
            f"- ID: {kb_id}\n"
            f"{'- 已从白名单中移除' if removed_wl else ''}"
            f"{'- 已从黑名单中移除' if removed_bl else ''}"
        )

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

        注意：此操作不可撤销！除非用户明确要求跳过确认，否则必须要求用户确认后再执行。
        可通过 doc_id 或 file_name 指定要删除的文档，至少需要提供其中一个。

        Args:
            kb_id(string): 知识库ID
            doc_id(string): 文档ID（与 file_name 二选一）
            file_name(string): 文件名（与 doc_id 二选一，用于模糊匹配）
            confirm(bool): 是否确认执行删除。默认为 false。
        """
        if not doc_id and not file_name:
            return "❌ 参数错误: 请提供 doc_id 或 file_name。"

        # 权限检查
        try:
            self.access_control.check_kb_access(kb_id)
        except PermissionError as e:
            return f"❌ 权限不足: {e}"

        # 获取知识库
        kb_helper = await self.context.kb_manager.get_kb(kb_id)
        if not kb_helper:
            return f"❌ 错误: 知识库 {kb_id} 不存在或未加载。"

        # 查找目标文档
        target_doc = None
        if doc_id:
            target_doc = await kb_helper.get_document(doc_id)
            if not target_doc:
                return f"❌ 未找到文档: doc_id={doc_id}"
        elif file_name:
            docs = await kb_helper.list_documents(limit=500)
            matches = [d for d in docs if file_name.lower() in d.doc_name.lower()]
            if not matches:
                return f"❌ 未找到文件名包含 '{file_name}' 的文档。"
            if len(matches) > 1:
                lines = [f"⚠️ 找到多个匹配的文档，请通过 doc_id 指定："]
                for d in matches:
                    lines.append(f"  - doc_id: {d.doc_id} | 文件名: {d.doc_name}")
                return "\n".join(lines)
            target_doc = matches[0]

        # 确认检查
        if not confirm:
            return (
                "⚠️ 确认请求\n"
                f"- 操作: 删除文档\n"
                f"- 知识库: {kb_id}\n"
                f"- 文档: {target_doc.doc_name} ({target_doc.doc_id})\n"
                f"- 警告: 此操作将永久删除该文档及其向量数据，不可撤销。\n"
                f"请回复确认，或再次调用时将 confirm 设为 true。"
            )

        # 执行删除
        try:
            await kb_helper.delete_document(target_doc.doc_id)
        except Exception as e:
            return (
                f"❌ 删除失败\n"
                f"- 知识库: {kb_id}\n"
                f"- 文档: {target_doc.doc_name}\n"
                f"- 错误: {e!s}"
            )

        return (
            f"✅ 文档已删除\n"
            f"- 知识库: {kb_id}\n"
            f"- 文档: {target_doc.doc_name}\n"
            f"- 文档ID: {target_doc.doc_id}"
        )

    # ── Tool 6: Search knowledge bases (access-controlled) ────────

    @llm_tool(name="astr_kb_search_ext")
    async def search_knowledge_base(
        self,
        event: AstrMessageEvent,
        query: str,
    ) -> str:
        """在插件白名单/黑名单允许的知识库中搜索相关内容。

        Search knowledge bases allowed by the plugin's access control.

        Args:
            query(string): 搜索关键词或问题
        """
        if not query.strip():
            return "❌ 请输入搜索关键词。"

        # 获取所有知识库并按访问控制过滤
        all_kbs = await self.context.kb_manager.list_kbs()
        allowed_kbs = self.access_control.filter_kb_list(all_kbs)

        if not allowed_kbs:
            return "当前没有可搜索的知识库。"

        kb_names = [kb.kb_name for kb in allowed_kbs]

        try:
            result = await self.context.kb_manager.retrieve(
                query=query.strip(),
                kb_names=kb_names,
                top_k_fusion=20,
                top_m_final=5,
            )
        except Exception as e:
            return f"❌ 搜索失败: {e!s}"

        if not result or not result.get("context_text"):
            return "未找到相关知识。"

        return result["context_text"]

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
