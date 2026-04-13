"""
PDF 解析插件 — 提供 parse_pdf 工具供 Agent 调用。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..base import BasePlugin
from .parser import parse_pdf, PdfExtractPayload


class PdfExtractPlugin(BasePlugin):
    """PDF 解析插件 — 基于 pymupdf4llm 实现结构化 PDF 内容提取。"""
    
    name = "pdf_extract"
    version = "1.0.0"
    description = "PDF 解析插件：提取文本、章节、表格、公式、元数据"
    
    def _register_tools(self) -> list[Callable[..., Any]]:
        """注册 PDF 解析工具。"""
        return [self.parse_pdf_tool]
    
    def parse_pdf_tool(self, file_path: str) -> dict[str, Any]:
        """
        解析 PDF 文件，返回结构化内容。
        
        Args:
            file_path: PDF 文件路径
            
        Returns:
            dict: 包含以下字段的结构化结果：
                - file_path: 源文件路径
                - metadata: 文档元数据 (title, author, keywords, page_count 等)
                - full_text: 完整 Markdown 文本
                - sections: 章节列表 [{level, title, content, page_start}]
                - tables: 表格列表 [{page, content, caption}]
                - formulas: 公式列表 [{page, content, inline}]
                - raw_pages: 按页原始文本列表
        """
        try:
            result: PdfExtractPayload = parse_pdf(file_path)
            return result.model_dump()
        except FileNotFoundError as e:
            return {"error": str(e), "type": "FileNotFoundError"}
        except ValueError as e:
            return {"error": str(e), "type": "ValueError"}
        except Exception as e:
            return {"error": f"PDF 解析失败: {e}", "type": type(e).__name__}
    
    def health_check(self) -> bool:
        """检查 pymupdf4llm 是否可用。"""
        try:
            import pymupdf4llm
            import pymupdf
            return True
        except ImportError:
            return False
