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

"""Knowledge base access controller — whitelist/blacklist mechanism.

Decision logic (highest priority first):
1. kb_id is in blacklist → deny
2. whitelist mode and kb_id not in whitelist → deny
3. otherwise → allow

Config stores kb_id. The plugin settings page writes IDs directly;
resolve_names() provides backward compatibility for old configs using names.
"""


class KbAccessControl:
    """Knowledge base access controller with whitelist/blacklist support."""

    MODE_WHITELIST = "whitelist"
    MODE_BLACKLIST = "blacklist"

    def __init__(self, config: dict | None = None) -> None:
        """Initialise the access controller.

        Reads mode, whitelist, blacklist, and auto_whitelist_created from config.
        whitelist/blacklist are empty after init; call resolve_names() to populate.

        Args:
            config: Plugin config dict, expected to contain kb_access_control.

        Side effects:
            Sets instance attributes: mode, whitelist, blacklist, _resolved,
            _auto_whitelist, etc.
        """
        kb_ac = config.get("kb_access_control", {}) if isinstance(config, dict) else {}
        self.mode: str = kb_ac.get("mode", self.MODE_WHITELIST)
        # Config stores kb_id; raw lists kept for resolve_names() compatibility
        self._raw_whitelist: set[str] = set(kb_ac.get("whitelist", []) or [])
        self._raw_blacklist: set[str] = set(kb_ac.get("blacklist", []) or [])
        self.whitelist: set[str] = set()
        self.blacklist: set[str] = set()
        self._resolved = False
        self._auto_whitelist: bool = bool(
            kb_ac.get("auto_whitelist_created", True)
        )

    def resolve_names(self, kbs: list) -> None:
        """Resolve KB names to IDs from a live KB list (backward compatibility for old config).

        Args:
            kbs: list of KnowledgeBase objects from kb_manager.list_kbs().

        Side effects:
            Updates self.whitelist and self.blacklist with resolved IDs.
            Sets self._resolved = True.
        """
        # Build name→id map; first occurrence wins for duplicate names
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
                    resolved.add(item)  # Preserve as-is (existing ID or invalid entry)
            return resolved

        self.whitelist = _resolve(self._raw_whitelist)
        self.blacklist = _resolve(self._raw_blacklist)
        self._resolved = True

    def validate_config(self) -> None:
        """Validate the access control configuration.

        Raises:
            ValueError: If mode is not whitelist or blacklist.
        """
        if self.mode not in (self.MODE_WHITELIST, self.MODE_BLACKLIST):
            raise ValueError(
                f"kb_access_control.mode 必须是 '{self.MODE_WHITELIST}' "
                f"或 '{self.MODE_BLACKLIST}'，当前值: {self.mode!r}"
            )

    def check_kb_access(self, kb_id: str, kbs: list | None = None) -> None:
        """Check if the specified KB is accessible.

        Args:
            kb_id: The KB ID to check.
            kbs: Deprecated, kept for signature compatibility.

        Raises:
            PermissionError: If the KB is blacklisted, or not in whitelist (whitelist mode).
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
        """Filter a KB list according to the current access control rules.

        Args:
            kbs: list of KnowledgeBase objects from kb_manager.list_kbs().

        Returns:
            Filtered list of accessible knowledge bases.
        """
        return [
            kb for kb in kbs
            if kb.kb_id not in self.blacklist
            and (self.mode != self.MODE_WHITELIST or kb.kb_id in self.whitelist)
        ]

    @property
    def auto_whitelist_created(self) -> bool:
        """Whether newly created KBs are automatically added to the whitelist."""
        return self._auto_whitelist

    def add_to_whitelist(self, kb_id: str) -> None:
        """Add a KB ID to the whitelist. Only effective in whitelist mode.

        Args:
            kb_id: The KB ID to add to the whitelist.

        Side effects:
            When mode is whitelist, adds kb_id to self.whitelist.
        """
        if self.mode == self.MODE_WHITELIST:
            self.whitelist.add(kb_id)
