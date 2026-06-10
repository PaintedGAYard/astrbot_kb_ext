"""AstrBot KB External Access Plugin — main entry point.

Provides three Agent-facing LLM tools:
  - astr_kb_list     : List available knowledge bases
  - astr_kb_upload   : Upload a file to a knowledge base
  - astr_kb_create   : Create a new knowledge base

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
        import json as pyjson
        import os

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
            disk_config["kb_access_control"]["mode"] = mode
            disk_config["kb_access_control"]["whitelist"] = whitelist
            disk_config["kb_access_control"]["blacklist"] = blacklist
            with open(config_path, "w", encoding="utf-8") as f:
                pyjson.dump(disk_config, f, ensure_ascii=False, indent=2)

            logger.info(
                "astrbot_kb_ext_access: config saved — whitelist=%s, blacklist=%s",
                whitelist, blacklist,
            )
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
        file_content: str,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> str:
        """向指定的 AstrBot 知识库上传文件。

        Upload file content to a specified knowledge base.

        Args:
            kb_id(string): 目标知识库ID
            file_name(string): 文件名（含扩展名，如 report.txt）
            file_content(string): 文件文本内容
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
        result = await uploader.upload(
            file_name=file_name,
            file_content=file_content,
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
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ) -> str:
        """创建一个新的知识库。

        Create a new knowledge base with the specified parameters.

        Args:
            kb_name(string): 知识库名称
            description(string): 知识库描述
            chunk_size(number): 分块大小（字符数），默认 512
            chunk_overlap(number): 分块重叠（字符数），默认 50
        """
        embedding_providers = self.context.get_all_embedding_providers()
        if not embedding_providers:
            return (
                "❌ 创建失败\n"
                "- 错误: 没有可用的 Embedding 模型提供商。\n"
                "请先在 Dashboard 中配置 Embedding 模型。"
            )

        emb_provider = embedding_providers[0]
        emb_id = emb_provider.meta().id

        try:
            kb_helper = await self.context.kb_manager.create_kb(
                kb_name=kb_name,
                description=description.strip() or None,
                embedding_provider_id=emb_id,
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

        return (
            f"✅ 知识库创建成功\n"
            f"- 名称: {kb.kb_name}\n"
            f"- ID: {kb.kb_id}\n"
            f"- 分块大小: {kb.chunk_size}\n"
            f"- 分块重叠: {kb.chunk_overlap}\n"
            f"- Embedding: {emb_id}"
        )
