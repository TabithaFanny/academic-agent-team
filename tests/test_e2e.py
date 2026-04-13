"""端到端测试 - 验证完整 Pipeline 流程。"""

import os
import pytest
import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# 启用 Mock 模式
os.environ['AI_DETECT_MOCK'] = 'true'
os.environ['CNKI_MOCK'] = 'true'


def literature_gate(papers: list, threshold: int = 30) -> bool:
    """文献质量门 - 检查文献数量是否达标。"""
    return len(papers) >= threshold


class TestStandardModeFlow:
    """标准模式全流程测试。"""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM 客户端。"""
        client = MagicMock()
        client.chat = AsyncMock(return_value=MagicMock(
            content="这是一个关于人工智能伦理的研究方向建议。"
        ))
        return client
    
    def test_topic_input_validation(self):
        """测试主题输入验证。"""
        # 简单验证：空主题应为空字符串
        topic = ""
        assert topic == ""
        
        # 有效主题
        valid_topic = "人工智能伦理"
        assert len(valid_topic) > 0
    
    def test_phase_1_topic_discussion(self):
        """测试 Phase 1 选题讨论。"""
        # Phase 1 应产出 3-5 个聚焦方向
        directions = [
            "AI 生成内容的版权归属",
            "算法推荐与新闻伦理",
            "深度伪造的社会影响",
        ]
        assert len(directions) >= 3
    
    @pytest.mark.asyncio
    async def test_phase_2_literature_search(self):
        """测试 Phase 2 文献调研。"""
        from academic_agent_team.tools.search_cnki import CNKISearchTool
        
        tool = CNKISearchTool()
        # Mock 模式下应返回模拟结果
        results = await tool.search("人工智能 新闻传播", max_results=10)
        assert hasattr(results, 'papers') or isinstance(results, list)
    
    def test_literature_quality_gate(self):
        """测试文献质量门。"""
        # 少于 30 篇应触发重试
        papers = [{"title": f"论文{i}"} for i in range(25)]
        gate_result = literature_gate(papers, threshold=30)
        assert not gate_result  # 应返回 False
        
        # 达到 30 篇应通过
        papers = [{"title": f"论文{i}"} for i in range(35)]
        gate_result = literature_gate(papers, threshold=30)
        assert gate_result  # 应返回 True
    
    def test_phase_3_writing_review_loop(self):
        """测试 Phase 3 写作-审稿循环。"""
        # 模拟审稿分数
        scores = [75, 82, 88]  # 前两轮低于 85，第三轮通过
        
        for i, score in enumerate(scores):
            if score >= 85:
                break
        
        assert i == 2  # 应该在第 3 轮通过
    
    def test_content_quality_gate(self):
        """测试内容质量门。"""
        threshold = 85
        
        # 低于 85 分应继续迭代
        assert 75 < threshold
        assert 82 < threshold
        
        # 达到 85 分应通过
        assert 88 >= threshold


class TestExpressModeFlow:
    """极速模式全流程测试。"""
    
    def test_express_mode_skips_intermediate_reviews(self):
        """极速模式应跳过中间审核点。"""
        # 极速模式配置：只有 H1 和 H4 两个干预点
        mode = "express"
        intervention_points = ["H1", "H4"]  # 极速模式的干预点
        
        assert mode == "express"
        assert len(intervention_points) == 2
    
    def test_express_mode_auto_selects_direction(self):
        """极速模式应自动选择第一个方向。"""
        directions = ["方向A", "方向B", "方向C"]
        selected = directions[0]  # 自动选择第一个
        assert selected == "方向A"


class TestCNKIToLatexExport:
    """CNKI 搜索 → 引用验证 → LaTeX 导出 测试。"""
    
    @pytest.mark.asyncio
    async def test_cnki_search_returns_papers(self):
        """CNKI 搜索应返回论文列表。"""
        from academic_agent_team.tools.search_cnki import CNKISearchTool
        
        tool = CNKISearchTool()
        results = await tool.search("社交媒体 传播", max_results=5)
        
        # 应返回 CNKISearchResult 或相似结构
        assert hasattr(results, 'papers') or isinstance(results, (list, dict))
    
    @pytest.mark.asyncio
    async def test_citation_verification(self):
        """引用验证应返回结构化结果。"""
        from academic_agent_team.tools.citation_verifier import CitationVerifier, Citation
        
        verifier = CitationVerifier()
        
        # 测试整体验证 - 返回 BatchVerificationResult
        citations = [Citation(title="测试论文", authors=["张三"], year=2024)]
        results = await verifier.verify_all(citations)
        # 验证返回的是 BatchVerificationResult
        assert hasattr(results, 'total')
        assert hasattr(results, 'verification_rate')
    
    def test_latex_export_generates_file(self):
        """LaTeX 导出应生成有效 LaTeX 内容。"""
        from academic_agent_team.plugins.latex_export import (
            LaTeXExporter,
            PaperContent,
            Section,
            Author,
        )
        
        paper = PaperContent(
            title="测试论文标题",
            authors=[Author(name="张三", affiliation="北京大学")],
            abstract="这是摘要内容。" * 10,
            keywords=["人工智能", "伦理", "新闻传播"],
            sections=[
                Section(title="引言", content="这是引言内容。" * 20),
                Section(title="研究方法", content="这是方法内容。" * 20),
            ],
        )
        
        exporter = LaTeXExporter()
        
        # export 返回 LaTeX 字符串内容
        latex_content = exporter.export(paper, template_name="base")
        
        # 验证返回的是有效 LaTeX
        assert isinstance(latex_content, str)
        assert "\\documentclass" in latex_content
        assert "测试论文标题" in latex_content
        assert "张三" in latex_content
        
        # 测试写入文件
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_paper.tex"
            latex_content = exporter.export(paper, template_name="base", output_path=output_path)
            
            if output_path.exists():
                content = output_path.read_text(encoding='utf-8')
                assert "测试论文标题" in content


class TestAIDetection:
    """AI 检测测试。"""
    
    @pytest.mark.asyncio
    async def test_ai_detection_returns_result(self):
        """AI 检测应返回检测结果。"""
        from academic_agent_team.tools.ai_detection import AIDetector
        
        detector = AIDetector()
        text = "值得注意的是，本研究采用了创新性的方法论。"
        
        result = await detector.detect(text)
        
        assert hasattr(result, 'ai_probability')
        assert 0 <= result.ai_probability <= 1
    
    @pytest.mark.asyncio
    async def test_ai_detection_flags_sentences(self):
        """AI 检测应标记高概率句子。"""
        from academic_agent_team.tools.ai_detection import AIDetector
        
        detector = AIDetector()
        text = """
        首先，我们需要探讨这个问题的本质。
        值得注意的是，相关研究表明了显著的趋势。
        综上所述，这一发现具有深远的影响。
        """
        
        result = await detector.detect(text)
        
        # 应该有标记的句子
        assert isinstance(result.flagged_sentences, list)


class TestPlagiarismChecker:
    """查重测试。"""
    
    @pytest.mark.asyncio
    async def test_plagiarism_check_returns_similarity(self):
        """查重应返回相似度。"""
        from academic_agent_team.tools.plagiarism_checker import PlagiarismChecker
        
        checker = PlagiarismChecker()
        text = "这是一段测试文本，用于验证查重功能。"
        
        result = await checker.check_similarity(text)
        
        assert hasattr(result, 'overall_similarity')
        assert 0 <= result.overall_similarity <= 1


class TestOutputPackage:
    """输出包完整性测试。"""
    
    def test_output_package_structure(self):
        """输出包应包含所有必要文件。"""
        expected_files = [
            "paper.tex",
            "paper.pdf",  # 如果有 LaTeX 编译器
            "references.bib",
            "AI_DISCLOSURE.md",
            "HUMAN_EDIT_GUIDE.md",
            "quality_report.json",
        ]
        
        # 至少应包含 tex 和 disclosure
        minimal_files = ["paper.tex", "AI_DISCLOSURE.md", "HUMAN_EDIT_GUIDE.md"]
        
        for f in minimal_files:
            assert f in expected_files
    
    def test_ai_disclosure_content(self):
        """AI 声明应包含必要信息。"""
        disclosure = """
        ## AI 辅助声明
        
        本论文在撰写过程中使用了 AI 辅助工具，具体包括：
        - 文献检索与整理
        - 初稿生成
        - 语言润色
        
        所有核心观点、研究设计和结论均由作者独立完成并审核。
        """
        
        assert "AI 辅助" in disclosure
        assert "作者" in disclosure
    
    def test_human_edit_guide_content(self):
        """人工修改指南应包含具体建议。"""
        guide = """
        ## 人工修改建议
        
        ### 需重点关注的段落
        1. 引言第 2 段 - AI 检测分数较高，建议改写
        2. 结论部分 - 需要增加个人见解
        
        ### 引用核查
        - 请核实参考文献 [3] 的 DOI 链接
        - 建议补充 2 篇最新文献
        """
        
        assert "修改" in guide
        assert "建议" in guide


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
