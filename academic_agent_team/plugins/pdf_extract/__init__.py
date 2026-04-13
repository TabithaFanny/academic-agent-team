"""
PDF 解析插件 — 基于 pymupdf4llm 实现结构化 PDF 内容提取。

支持提取：文本、章节、表格、公式、元数据。
"""

from .parser import parse_pdf, PdfExtractPayload
from .plugin import PdfExtractPlugin

__all__ = ["parse_pdf", "PdfExtractPayload", "PdfExtractPlugin"]
