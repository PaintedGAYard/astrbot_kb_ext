"""AstrBot Knowledge Base External Access Plugin.

Provides Agent-facing tools for listing, uploading to, and creating
knowledge bases with configurable whitelist/blacklist access control.

Version is read from metadata.yaml (single source of truth).
"""

import pathlib
import re


def _get_version() -> str:
    """Read version from metadata.yaml."""
    meta = pathlib.Path(__file__).parent / "metadata.yaml"
    try:
        for line in meta.read_text(encoding="utf-8").splitlines():
            if line.startswith("version:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return "0.0.0"


__version__ = _get_version()
