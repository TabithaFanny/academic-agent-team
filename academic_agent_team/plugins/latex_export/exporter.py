"""
LaTeX 导出器 — 将论文内容导出为 LaTeX 格式。

支持多种模板（CSSCI、IEEE 等）和 GB/T 7714 引用格式。
"""

from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


TEMPLATES_DIR = Path(__file__).parent / "templates"


@dataclass
class Author:
    """作者信息。"""
    name: str
    affiliation: str = ""
    email: str = ""
    orcid: str = ""
    is_corresponding: bool = False


@dataclass
class Figure:
    """图片信息。"""
    path: str
    caption: str
    label: str = ""
    width: str = "0.8\\textwidth"


@dataclass
class Table:
    """表格信息。"""
    caption: str
    label: str
    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class Reference:
    """参考文献条目 — 支持 GB/T 7714 格式。"""
    cite_key: str
    entry_type: str  # article, book, inproceedings, etc.
    title: str
    authors: list[str] = field(default_factory=list)
    year: str = ""
    journal: str = ""
    volume: str = ""
    number: str = ""
    pages: str = ""
    publisher: str = ""
    booktitle: str = ""  # for inproceedings
    doi: str = ""
    url: str = ""
    
    def to_bibtex(self) -> str:
        """转换为 BibTeX 格式。"""
        lines = [f"@{self.entry_type}{{{self.cite_key},"]
        
        if self.authors:
            lines.append(f"  author = {{{' and '.join(self.authors)}}},")
        lines.append(f"  title = {{{self.title}}},")
        
        if self.year:
            lines.append(f"  year = {{{self.year}}},")
        if self.journal:
            lines.append(f"  journal = {{{self.journal}}},")
        if self.booktitle:
            lines.append(f"  booktitle = {{{self.booktitle}}},")
        if self.volume:
            lines.append(f"  volume = {{{self.volume}}},")
        if self.number:
            lines.append(f"  number = {{{self.number}}},")
        if self.pages:
            lines.append(f"  pages = {{{self.pages}}},")
        if self.publisher:
            lines.append(f"  publisher = {{{self.publisher}}},")
        if self.doi:
            lines.append(f"  doi = {{{self.doi}}},")
        if self.url:
            lines.append(f"  url = {{{self.url}}},")
        
        lines.append("}")
        return "\n".join(lines)


@dataclass
class Section:
    """章节内容。"""
    title: str
    content: str
    level: int = 1  # 1=section, 2=subsection, 3=subsubsection
    label: str = ""


@dataclass
class PaperContent:
    """论文内容数据结构。"""
    title: str
    authors: list[Author] = field(default_factory=list)
    abstract: str = ""
    abstract_en: str = ""  # 英文摘要（中文期刊需要）
    keywords: list[str] = field(default_factory=list)
    keywords_en: list[str] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    figures: list[Figure] = field(default_factory=list)
    tables: list[Table] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    acknowledgments: str = ""
    # 元数据
    document_class: str = "article"
    font_size: str = "12pt"
    paper_size: str = "a4paper"
    language: str = "chinese"  # chinese or english


class LaTeXExporter:
    """LaTeX 导出器 — 使用 Jinja2 模板引擎。"""
    
    AVAILABLE_TEMPLATES = ["base", "cssci", "ieee"]
    
    def __init__(self, templates_dir: Path | None = None):
        """
        初始化导出器。
        
        Args:
            templates_dir: 自定义模板目录，默认使用内置模板
        """
        if not HAS_JINJA2:
            raise ImportError(
                "Jinja2 is required for LaTeX export. "
                "Install with: pip install jinja2 or pip install academic-agent-team[latex]"
            )
        
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(enabled_extensions=()),
            # LaTeX 特殊字符处理
            block_start_string="<%",
            block_end_string="%>",
            variable_start_string="<<",
            variable_end_string=">>",
            comment_start_string="<#",
            comment_end_string="#>",
        )
        self._setup_filters()
    
    def _setup_filters(self) -> None:
        """设置 Jinja2 过滤器。"""
        self._env.filters["escape_latex"] = self._escape_latex
        self._env.filters["format_authors_latex"] = self._format_authors_latex
        self._env.filters["format_keywords"] = self._format_keywords
        self._env.filters["section_cmd"] = self._section_command
    
    @staticmethod
    def _escape_latex(text: str) -> str:
        """转义 LaTeX 特殊字符。"""
        if not text:
            return ""
        # 特殊字符映射
        replacements = [
            ("\\", "\\textbackslash{}"),
            ("&", "\\&"),
            ("%", "\\%"),
            ("$", "\\$"),
            ("#", "\\#"),
            ("_", "\\_"),
            ("{", "\\{"),
            ("}", "\\}"),
            ("~", "\\textasciitilde{}"),
            ("^", "\\textasciicircum{}"),
        ]
        result = text
        for char, replacement in replacements:
            result = result.replace(char, replacement)
        return result
    
    @staticmethod
    def _format_authors_latex(authors: list[Author], style: str = "default") -> str:
        """格式化作者列表。"""
        if not authors:
            return ""
        
        if style == "ieee":
            # IEEE 格式：作者名用逗号分隔
            author_strs = []
            for author in authors:
                name = author.name
                if author.is_corresponding:
                    name += "*"
                author_strs.append(name)
            return ", ".join(author_strs)
        else:
            # 中文格式：作者名用空格分隔
            author_strs = []
            for i, author in enumerate(authors, 1):
                name = author.name
                if author.is_corresponding:
                    name += "$^{*}$"
                author_strs.append(name)
            return " \\quad ".join(author_strs)
    
    @staticmethod
    def _format_keywords(keywords: list[str], separator: str = "; ") -> str:
        """格式化关键词列表。"""
        return separator.join(keywords)
    
    @staticmethod
    def _section_command(level: int) -> str:
        """根据层级返回章节命令。"""
        commands = {1: "section", 2: "subsection", 3: "subsubsection"}
        return commands.get(level, "paragraph")
    
    def get_available_templates(self) -> list[str]:
        """获取可用模板列表。"""
        templates = []
        for path in self.templates_dir.glob("*.tex.jinja2"):
            name = path.stem.replace(".tex", "")
            templates.append(name)
        return templates
    
    def export(
        self,
        paper_content: PaperContent,
        template_name: str = "base",
        output_path: str | Path | None = None,
    ) -> str:
        """
        导出论文为 LaTeX 格式。
        
        Args:
            paper_content: 论文内容数据
            template_name: 模板名称（base, cssci, ieee）
            output_path: 输出文件路径，None 则返回字符串
            
        Returns:
            生成的 LaTeX 代码
        """
        template_file = f"{template_name}.tex.jinja2"
        try:
            template = self._env.get_template(template_file)
        except Exception as e:
            raise ValueError(f"Template '{template_name}' not found: {e}")
        
        # 生成 BibTeX 内容
        bibtex_content = self._generate_bibtex(paper_content.references)
        
        # 渲染模板
        latex_content = template.render(
            paper=paper_content,
            bibtex=bibtex_content,
            has_figures=bool(paper_content.figures),
            has_tables=bool(paper_content.tables),
        )
        
        # 输出到文件
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(latex_content, encoding="utf-8")
            
            # 同时生成 .bib 文件
            if bibtex_content:
                bib_path = output_path.with_suffix(".bib")
                bib_path.write_text(bibtex_content, encoding="utf-8")
        
        return latex_content
    
    def _generate_bibtex(self, references: list[Reference]) -> str:
        """生成 BibTeX 文件内容。"""
        if not references:
            return ""
        entries = [ref.to_bibtex() for ref in references]
        return "\n\n".join(entries)


def check_latex_available() -> bool:
    """检查 LaTeX 编译器是否可用。"""
    return shutil.which("latexmk") is not None or shutil.which("pdflatex") is not None


def compile_pdf(
    tex_path: str | Path,
    output_dir: str | Path | None = None,
    engine: str = "xelatex",
) -> Path | None:
    """
    编译 LaTeX 文件为 PDF。
    
    Args:
        tex_path: .tex 文件路径
        output_dir: 输出目录，默认与 tex 文件同目录
        engine: 编译引擎 (xelatex, pdflatex, lualatex)
        
    Returns:
        PDF 文件路径，编译失败返回 None
    """
    tex_path = Path(tex_path)
    if not tex_path.exists():
        raise FileNotFoundError(f"TeX file not found: {tex_path}")
    
    output_dir = Path(output_dir) if output_dir else tex_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 优先使用 latexmk
    if shutil.which("latexmk"):
        cmd = [
            "latexmk",
            f"-{engine}",
            "-interaction=nonstopmode",
            "-file-line-error",
            f"-output-directory={output_dir}",
            str(tex_path),
        ]
    elif shutil.which(engine):
        cmd = [
            engine,
            "-interaction=nonstopmode",
            "-file-line-error",
            f"-output-directory={output_dir}",
            str(tex_path),
        ]
    else:
        raise RuntimeError(
            f"LaTeX compiler not found. Please install TeX Live or MiKTeX."
        )
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=tex_path.parent,
        )
        
        pdf_path = output_dir / tex_path.with_suffix(".pdf").name
        if pdf_path.exists():
            return pdf_path
        else:
            # 编译失败，返回错误信息
            print(f"LaTeX compilation failed:\n{result.stderr}")
            return None
            
    except subprocess.TimeoutExpired:
        print("LaTeX compilation timed out")
        return None
    except Exception as e:
        print(f"LaTeX compilation error: {e}")
        return None


def export_to_latex(
    paper: PaperContent | dict[str, Any],
    template: str = "base",
    output_path: str | Path | None = None,
) -> str:
    """
    便捷函数：导出论文为 LaTeX。
    
    Args:
        paper: PaperContent 对象或字典
        template: 模板名称
        output_path: 输出路径
        
    Returns:
        LaTeX 代码
    """
    # 如果是字典，转换为 PaperContent
    if isinstance(paper, dict):
        paper = _dict_to_paper_content(paper)
    
    exporter = LaTeXExporter()
    return exporter.export(paper, template, output_path)


def _dict_to_paper_content(data: dict[str, Any]) -> PaperContent:
    """将字典转换为 PaperContent。"""
    # 处理作者
    authors = []
    for author_data in data.get("authors", []):
        if isinstance(author_data, str):
            authors.append(Author(name=author_data))
        elif isinstance(author_data, dict):
            authors.append(Author(**author_data))
        elif isinstance(author_data, Author):
            authors.append(author_data)
    
    # 处理章节
    sections = []
    for section_data in data.get("sections", []):
        if isinstance(section_data, dict):
            sections.append(Section(**section_data))
        elif isinstance(section_data, Section):
            sections.append(section_data)
    
    # 处理图片
    figures = []
    for fig_data in data.get("figures", []):
        if isinstance(fig_data, dict):
            figures.append(Figure(**fig_data))
        elif isinstance(fig_data, Figure):
            figures.append(fig_data)
    
    # 处理表格
    tables = []
    for table_data in data.get("tables", []):
        if isinstance(table_data, dict):
            tables.append(Table(**table_data))
        elif isinstance(table_data, Table):
            tables.append(table_data)
    
    # 处理参考文献
    references = []
    for ref_data in data.get("references", []):
        if isinstance(ref_data, dict):
            references.append(Reference(**ref_data))
        elif isinstance(ref_data, Reference):
            references.append(ref_data)
    
    return PaperContent(
        title=data.get("title", "Untitled"),
        authors=authors,
        abstract=data.get("abstract", ""),
        abstract_en=data.get("abstract_en", ""),
        keywords=data.get("keywords", []),
        keywords_en=data.get("keywords_en", []),
        sections=sections,
        figures=figures,
        tables=tables,
        references=references,
        acknowledgments=data.get("acknowledgments", ""),
        document_class=data.get("document_class", "article"),
        font_size=data.get("font_size", "12pt"),
        paper_size=data.get("paper_size", "a4paper"),
        language=data.get("language", "chinese"),
    )
