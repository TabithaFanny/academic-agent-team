"""
LaTeX 导出插件 — 将论文导出为 LaTeX 格式。

支持模板：
- base: 基础通用模板
- cssci: CSSCI 中文期刊模板
- ieee: IEEE 会议/期刊模板

使用示例：
    from academic_agent_team.plugins.latex_export import export_to_latex, compile_pdf
    
    # 导出论文
    paper = {
        "title": "人工智能辅助学术写作研究",
        "authors": [{"name": "张三", "affiliation": "北京大学"}],
        "abstract": "本文研究了...",
        "keywords": ["人工智能", "学术写作", "自然语言处理"],
        "sections": [
            {"title": "引言", "content": "随着人工智能技术的发展..."},
        ],
    }
    
    # 生成 LaTeX
    latex_code = export_to_latex(paper, template="cssci")
    
    # 或导出到文件
    export_to_latex(paper, template="cssci", output_path="output/paper.tex")
    
    # 编译 PDF（需要安装 TeX Live）
    pdf_path = compile_pdf("output/paper.tex")
"""

from .exporter import (
    # 数据类
    Author,
    Figure,
    Table,
    Reference,
    Section,
    PaperContent,
    # 导出器
    LaTeXExporter,
    # 便捷函数
    export_to_latex,
    compile_pdf,
    check_latex_available,
    # 常量
    HAS_JINJA2,
    TEMPLATES_DIR,
)

from .plugin import LaTeXExportPlugin


__all__ = [
    # 数据类
    "Author",
    "Figure",
    "Table",
    "Reference",
    "Section",
    "PaperContent",
    # 导出器
    "LaTeXExporter",
    # 便捷函数
    "export_to_latex",
    "compile_pdf",
    "check_latex_available",
    # 插件
    "LaTeXExportPlugin",
    # 常量
    "HAS_JINJA2",
    "TEMPLATES_DIR",
]
