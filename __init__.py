"""
AstrBot KB Tools Plugin v2.0
Agent-only, minimal output, token-efficient JSON.
"""

from .main import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION,
    TOOLS, DEPENDENCIES,
    TOOL_KB_LIST, TOOL_KB_UPLOAD,
    get_astrbot_kb_list, add_astrbot_kb_document,
)

__all__ = [
    "PLUGIN_NAME", "PLUGIN_VERSION", "PLUGIN_DESCRIPTION",
    "TOOLS", "DEPENDENCIES",
    "TOOL_KB_LIST", "TOOL_KB_UPLOAD",
    "get_astrbot_kb_list", "add_astrbot_kb_document",
]
