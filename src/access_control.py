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

"""Knowledge base access controller — whitelist/blacklist mechanism."""


class KbAccessControl:
    """知识库访问控制器 — 白名单/黑名单机制。

    Knowledge base access controller with whitelist/blacklist support.

    判定逻辑（由高到低）:
    1. kb_id 在黑名单中 → 拒绝
    2. whitelist 模式且 kb_id 不在白名单中 → 拒绝
    3. 其他情况 → 允许

    配置项 whitelist/blacklist 存储的是知识库 ID。
    插件页面保存时直接写入 ID（而非显示名），
    所有匹配操作均基于 ID 进行。
    保留 resolve_names() 方法用于兼容旧配置中的名称。
    """

    MODE_WHITELIST = "whitelist"
    MODE_BLACKLIST = "blacklist"

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        kb_ac = config.get("kb_access_control", {}) if isinstance(config, dict) else {}
        self.mode: str = kb_ac.get("mode", self.MODE_WHITELIST)
        # 配置存储的是 kb_id，保留 raw 用于 resolve_names 兼容
        self._raw_whitelist: set[str] = set(kb_ac.get("whitelist", []) or [])
        self._raw_blacklist: set[str] = set(kb_ac.get("blacklist", []) or [])
        self.whitelist: set[str] = set()
        self.blacklist: set[str] = set()
        self._resolved = False
        self._auto_whitelist: bool = bool(
            kb_ac.get("auto_whitelist_created", True)
        )

    # ── name→id resolution (backward compatibility) ───────────────

    def resolve_names(self, kbs: list) -> None:
        """将旧配置中的知识库名称解析为 kb_id（兼容旧版）。
        新版配置直接存储 ID，此方法仅用于迁移旧数据。

        Args:
            kbs: KnowledgeBase 对象列表（来自 kb_manager.list_kbs()）。
        """
        # 建立 name→id 映射（首次名称为准，处理撞名）
        name_to_id: dict[str, str] = {}
        for kb in kbs:
            kid = kb.kb_id if hasattr(kb, "kb_id") else ""
            kname = kb.kb_name if hasattr(kb, "kb_name") else ""
            if kid and kname and kname not in name_to_id:
                name_to_id[kname] = kid

        def _resolve(raw: set[str]) -> set[str]:
            resolved: set[str] = set()
            for item in raw:
                if item in name_to_id:
                    resolved.add(name_to_id[item])
                else:
                    resolved.add(item)  # 保留原值（可能是已存在的 ID 或无效值）
            return resolved

        self.whitelist = _resolve(self._raw_whitelist)
        self.blacklist = _resolve(self._raw_blacklist)
        self._resolved = True

    # ── config validation ─────────────────────────────────────────

    def validate_config(self) -> None:
        """校验配置合法性。

        Validate the access control configuration.
        """
        if self.mode not in (self.MODE_WHITELIST, self.MODE_BLACKLIST):
            raise ValueError(
                f"kb_access_control.mode 必须是 '{self.MODE_WHITELIST}' "
                f"或 '{self.MODE_BLACKLIST}'，当前值: {self.mode!r}"
            )

    # ── access checks (IDs only) ──

    def check_kb_access(self, kb_id: str, kbs: list | None = None) -> None:
        """检查是否允许操作指定知识库。

        Check if the specified knowledge base is accessible.

        Args:
            kb_id: 知识库 ID。
            kbs: 已弃用，保留参数签名兼容。

        Raises:
            PermissionError: 当知识库不在白名单或在黑名单中时。
        """
        if kb_id in self.blacklist:
            raise PermissionError(
                f"知识库 {kb_id} 在黑名单中，禁止访问。"
            )
        if self.mode == self.MODE_WHITELIST and kb_id not in self.whitelist:
            raise PermissionError(
                f"知识库 {kb_id} 不在白名单中，禁止访问。"
            )

    def filter_kb_list(self, kbs: list) -> list:
        """过滤知识库列表，仅返回当前配置允许访问的条目。

        Filter a knowledge base list according to the current access control rules.

        Args:
            kbs: KnowledgeBase 对象列表（来自 kb_manager.list_kbs()）。

        Returns:
            过滤后的列表。
        """
        return [
            kb for kb in kbs
            if kb.kb_id not in self.blacklist
            and (self.mode != self.MODE_WHITELIST or kb.kb_id in self.whitelist)
        ]

    @property
    def auto_whitelist_created(self) -> bool:
        """是否将新建的知识库自动加入白名单。

        Whether newly created KBs are automatically added to the whitelist.
        """
        return self._auto_whitelist

    def add_to_whitelist(self, kb_id: str) -> None:
        """将知识库 ID 加入白名单（仅 whitelist 模式有效）。

        Add a KB ID to the whitelist. Only effective in whitelist mode.
        """
        if self.mode == self.MODE_WHITELIST:
            self.whitelist.add(kb_id)
