"""
PDF 解析器 — 基于 pymupdf4llm 提取结构化内容。

提取内容包括：文本、章节、表格、公式、元数据。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TableData(BaseModel):
    """表格数据模型。"""
    
    page: int = Field(description="所在页码")
    content: str = Field(description="表格内容 (Markdown 格式)")
    caption: str | None = Field(default=None, description="表格标题")


class FormulaData(BaseModel):
    """公式数据模型。"""
    
    page: int = Field(description="所在页码")
    content: str = Field(description="公式内容 (LaTeX 格式)")
    inline: bool = Field(default=False, description="是否为行内公式")


class SectionData(BaseModel):
    """章节数据模型。"""
    
    level: int = Field(description="章节层级 (1-6)")
    title: str = Field(description="章节标题")
    content: str = Field(description="章节内容")
    page_start: int = Field(description="起始页码")
    page_end: int | None = Field(default=None, description="结束页码")


class MetaData(BaseModel):
    """PDF 元数据模型。"""
    
    title: str | None = Field(default=None, description="文档标题")
    author: str | None = Field(default=None, description="作者")
    subject: str | None = Field(default=None, description="主题")
    keywords: list[str] = Field(default_factory=list, description="关键词")
    creator: str | None = Field(default=None, description="创建工具")
    producer: str | None = Field(default=None, description="PDF 生成器")
    creation_date: str | None = Field(default=None, description="创建日期")
    modification_date: str | None = Field(default=None, description="修改日期")
    page_count: int = Field(default=0, description="页数")


class PdfExtractPayload(BaseModel):
    """PDF 提取结果 Payload。"""
    
    file_path: str = Field(description="源文件路径")
    metadata: MetaData = Field(description="文档元数据")
    full_text: str = Field(description="完整文本内容 (Markdown)")
    sections: list[SectionData] = Field(default_factory=list, description="章节列表")
    tables: list[TableData] = Field(default_factory=list, description="表格列表")
    formulas: list[FormulaData] = Field(default_factory=list, description="公式列表")
    raw_pages: list[str] = Field(default_factory=list, description="按页原始文本")


def _extract_metadata(doc: Any) -> MetaData:
    """从 PyMuPDF 文档提取元数据。"""
    meta = doc.metadata or {}
    
    # 解析关键词
    keywords_str = meta.get("keywords", "") or ""
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]
    
    return MetaData(
        title=meta.get("title") or None,
        author=meta.get("author") or None,
        subject=meta.get("subject") or None,
        keywords=keywords,
        creator=meta.get("creator") or None,
        producer=meta.get("producer") or None,
        creation_date=meta.get("creationDate") or None,
        modification_date=meta.get("modDate") or None,
        page_count=len(doc),
    )


def _extract_sections(markdown_text: str) -> list[SectionData]:
    """从 Markdown 文本提取章节结构。"""
    sections: list[SectionData] = []
    
    # 匹配 Markdown 标题 (# ~ ######)
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    
    matches = list(header_pattern.finditer(markdown_text))
    
    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()
        start_pos = match.end()
        
        # 找到下一个同级或更高级标题的位置
        end_pos = len(markdown_text)
        for next_match in matches[i + 1:]:
            next_level = len(next_match.group(1))
            if next_level <= level:
                end_pos = next_match.start()
                break
        
        content = markdown_text[start_pos:end_pos].strip()
        
        # 估算页码 (简化处理：基于字符位置估算)
        page_estimate = max(1, match.start() // 3000 + 1)
        
        sections.append(SectionData(
            level=level,
            title=title,
            content=content,
            page_start=page_estimate,
            page_end=None,
        ))
    
    return sections


def _extract_tables(markdown_text: str) -> list[TableData]:
    """从 Markdown 文本提取表格。"""
    tables: list[TableData] = []
    
    # 匹配 Markdown 表格 (包含 | 和 --- 分隔行)
    table_pattern = re.compile(
        r"(\|[^\n]+\|\n\|[-:\s|]+\|\n(?:\|[^\n]+\|\n?)+)",
        re.MULTILINE
    )
    
    for match in table_pattern.finditer(markdown_text):
        table_content = match.group(1).strip()
        page_estimate = max(1, match.start() // 3000 + 1)
        
        # 尝试找表格标题 (表格前一行)
        caption = None
        pre_text = markdown_text[:match.start()].rstrip()
        if pre_text:
            last_line = pre_text.split("\n")[-1].strip()
            # 如果前一行看起来像标题 (Table X: 或 表X:)
            if re.match(r"^(Table|表|Tab\.?)\s*\d*[:：]?\s*.+", last_line, re.IGNORECASE):
                caption = last_line
        
        tables.append(TableData(
            page=page_estimate,
            content=table_content,
            caption=caption,
        ))
    
    return tables


def _extract_formulas(markdown_text: str) -> list[FormulaData]:
    """从 Markdown 文本提取公式。"""
    formulas: list[FormulaData] = []
    
    # 匹配块级公式 $$...$$
    block_formula_pattern = re.compile(r"\$\$([^$]+)\$\$", re.DOTALL)
    for match in block_formula_pattern.finditer(markdown_text):
        page_estimate = max(1, match.start() // 3000 + 1)
        formulas.append(FormulaData(
            page=page_estimate,
            content=match.group(1).strip(),
            inline=False,
        ))
    
    # 匹配行内公式 $...$  (排除已匹配的 $$)
    inline_formula_pattern = re.compile(r"(?<!\$)\$([^$\n]+)\$(?!\$)")
    for match in inline_formula_pattern.finditer(markdown_text):
        page_estimate = max(1, match.start() // 3000 + 1)
        formulas.append(FormulaData(
            page=page_estimate,
            content=match.group(1).strip(),
            inline=True,
        ))
    
    return formulas


def parse_pdf(file_path: str | Path) -> PdfExtractPayload:
    """
    解析 PDF 文件，返回结构化内容。
    
    Args:
        file_path: PDF 文件路径
        
    Returns:
        PdfExtractPayload: 包含文本、章节、表格、公式、元数据的结构化结果
        
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 文件不是有效的 PDF
    """
    import pymupdf4llm
    import pymupdf
    
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {file_path}")
    
    if path.suffix.lower() != ".pdf":
        raise ValueError(f"不是 PDF 文件: {file_path}")
    
    # 使用 pymupdf4llm 转换为 Markdown (支持表格、公式等)
    markdown_text = pymupdf4llm.to_markdown(
        str(path),
        page_chunks=False,  # 返回完整文本而非分页
    )
    
    # 使用 pymupdf 获取元数据和按页文本
    doc = pymupdf.open(str(path))
    metadata = _extract_metadata(doc)
    
    # 提取按页文本
    raw_pages: list[str] = []
    for page in doc:
        raw_pages.append(page.get_text())
    
    doc.close()
    
    # 提取结构化内容
    sections = _extract_sections(markdown_text)
    tables = _extract_tables(markdown_text)
    formulas = _extract_formulas(markdown_text)
    
    return PdfExtractPayload(
        file_path=str(path.resolve()),
        metadata=metadata,
        full_text=markdown_text,
        sections=sections,
        tables=tables,
        formulas=formulas,
        raw_pages=raw_pages,
    )
