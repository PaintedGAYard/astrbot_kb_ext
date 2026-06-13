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

"""Custom Markdown extraction for file formats that produce poor text via AstrBot's default pipeline.

AstrBot uses pandas.to_html() for Excel files, which converts empty cells to "NaN" strings
and dramatically inflates text volume for sparse spreadsheets. This module provides clean
Markdown table generation that bypasses that pipeline.
"""

from __future__ import annotations

import io
import re

from astrbot.api import logger


class MarkdownExtractor:
    """Extract clean Markdown text from binary file formats.

    Usage:
        text = MarkdownExtractor.extract(raw_bytes, "report.xlsx")
        if text is not None:
            upload_as_md(text)
    """

    @staticmethod
    def extract(raw_bytes: bytes, file_name: str) -> str | None:
        """Return clean Markdown for supported formats, or None to let AstrBot handle it.

        Args:
            raw_bytes: File content as bytes.
            file_name: Original file name (extension determines dispatch).

        Returns:
            Markdown text, or None if the format needs no custom extraction.

        Raises:
            ImportError: A required backend library (openpyxl, xlrd, pythoncom)
                is not installed.
            Exception: Propagates format-specific errors from underlying parsers
                (openpyxl, xlrd, olefile) for corrupt or malformed files.
        """
        ext = _get_ext(file_name)
        logger.info("MarkdownExtractor: dispatching %s (ext=%s)", file_name, ext)
        if ext == "xlsx":
            result = _xlsx_to_markdown(raw_bytes)
            logger.info("MarkdownExtractor: xlsx result length=%s", len(result) if result else 0)
            return result
        if ext == "xls":
            result = _xls_to_markdown(raw_bytes)
            logger.info("MarkdownExtractor: xls result length=%s", len(result) if result else 0)
            return result
        if ext == "doc":
            logger.warning(
                "MarkdownExtractor: .doc is not supported. "
                "The old binary .doc format cannot be reliably converted to text "
                "in the current environment. Use .docx instead."
            )
            return None
        logger.info("MarkdownExtractor: unsupported ext=%s, returning None", ext)
        return None


def _get_ext(file_name: str) -> str:
    return file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""


def _build_markdown_table(title: str, rows: list[list[str]]) -> list[str]:
    """Build a Markdown table fragment. rows[0] is the header."""
    if not rows:
        return []
    lines: list[str] = [f"## {title}\n"]
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join("---" for _ in rows[0]) + " |")
    for row in rows[1:]:
        while len(row) < len(rows[0]):
            row.append("")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")
    return lines


def _xlsx_to_markdown(raw_bytes: bytes) -> str:
    """Convert .xlsx to Markdown tables via openpyxl, bypassing pandas.to_html()."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
    parts: list[str] = []

    for ws in wb.worksheets:
        rows: list[list[str]] = []
        for row in ws.iter_rows(values_only=True):
            cleaned = [str(c).strip() if c is not None else "" for c in row]
            if not any(v for v in cleaned):
                continue
            rows.append(cleaned)
        if rows:
            parts.extend(_build_markdown_table(ws.title, rows))

    return "\n".join(parts)


def _xls_to_markdown(raw_bytes: bytes) -> str:
    """Convert .xls to Markdown tables via xlrd, bypassing pandas.to_html()."""
    import xlrd

    wb = xlrd.open_workbook(file_contents=raw_bytes)
    parts: list[str] = []

    for i in range(wb.nsheets):
        ws = wb.sheet_by_index(i)
        rows: list[list[str]] = []
        for row_idx in range(ws.nrows):
            cleaned = [
                str(ws.cell_value(row_idx, col)).strip()
                if ws.cell_type(row_idx, col) != xlrd.XL_CELL_EMPTY
                else ""
                for col in range(ws.ncols)
            ]
            if not any(v for v in cleaned):
                continue
            rows.append(cleaned)
        if rows:
            parts.extend(_build_markdown_table(ws.name, rows))

    return "\n".join(parts)
