"""
LaTeX 导出插件 — 将论文导出为 LaTeX 格式。

符合 PRD F106 插件系统要求。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..base import BasePlugin
from .exporter import (
    LaTeXExporter,
    PaperContent,
    check_latex_available,
    compile_pdf,
    export_to_latex,
    HAS_JINJA2,
)


class LaTeXExportPlugin(BasePlugin):
    """LaTeX 导出插件。"""
    
    name = "latex_export"
    version = "0.1.0"
    description = "导出论文为 LaTeX 格式，支持 CSSCI、IEEE 等模板"
    
    def __init__(self, templates_dir: Path | None = None):
        """
        初始化插件。
        
        Args:
            templates_dir: 自定义模板目录
        """
        super().__init__()
        self._templates_dir = templates_dir
        self._exporter: LaTeXExporter | None = None
    
    @property
    def exporter(self) -> LaTeXExporter:
        """延迟初始化导出器。"""
        if self._exporter is None:
            self._exporter = LaTeXExporter(self._templates_dir)
        return self._exporter
    
    def _register_tools(self) -> list[Callable[..., Any]]:
        """注册工具函数供 Agent 调用。"""
        return [
            self.export_paper,
            self.compile_to_pdf,
            self.list_templates,
        ]
    
    def export_paper(
        self,
        paper: PaperContent | dict[str, Any],
        template: str = "base",
        output_path: str | None = None,
    ) -> dict[str, Any]:
        """
        导出论文为 LaTeX 格式。
        
        Args:
            paper: 论文内容（PaperContent 或字典）
            template: 模板名称（base, cssci, ieee）
            output_path: 输出文件路径
            
        Returns:
            包含状态和内容的字典
        """
        try:
            latex_content = export_to_latex(paper, template, output_path)
            result = {
                "success": True,
                "template": template,
                "content_length": len(latex_content),
            }
            if output_path:
                result["output_path"] = str(output_path)
                result["bib_path"] = str(Path(output_path).with_suffix(".bib"))
            else:
                result["content"] = latex_content
            return result
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def compile_to_pdf(
        self,
        tex_path: str,
        output_dir: str | None = None,
        engine: str = "xelatex",
    ) -> dict[str, Any]:
        """
        编译 LaTeX 文件为 PDF。
        
        Args:
            tex_path: .tex 文件路径
            output_dir: 输出目录
            engine: 编译引擎 (xelatex, pdflatex, lualatex)
            
        Returns:
            包含状态和路径的字典
        """
        if not check_latex_available():
            return {
                "success": False,
                "error": "LaTeX compiler not found. Please install TeX Live or MiKTeX.",
            }
        
        try:
            pdf_path = compile_pdf(tex_path, output_dir, engine)
            if pdf_path:
                return {
                    "success": True,
                    "pdf_path": str(pdf_path),
                }
            else:
                return {
                    "success": False,
                    "error": "Compilation failed. Check the LaTeX source for errors.",
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def list_templates(self) -> dict[str, Any]:
        """
        列出可用模板。
        
        Returns:
            包含模板列表的字典
        """
        try:
            templates = self.exporter.get_available_templates()
            return {
                "success": True,
                "templates": templates,
                "descriptions": {
                    "base": "基础模板 — 通用学术论文格式",
                    "cssci": "CSSCI 期刊模板 — 中文社会科学引文索引期刊格式",
                    "ieee": "IEEE 模板 — 国际电气与电子工程师学会会议/期刊格式",
                },
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
            }
    
    def health_check(self) -> bool:
        """检查插件是否可用。"""
        if not HAS_JINJA2:
            return False
        try:
            # 检查模板目录是否存在
            templates_dir = self._templates_dir or (Path(__file__).parent / "templates")
            return templates_dir.exists()
        except Exception:
            return False
    
    def cleanup(self) -> None:
        """清理插件资源。"""
        super().cleanup()
        self._exporter = None
